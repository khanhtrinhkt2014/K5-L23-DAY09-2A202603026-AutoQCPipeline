"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]` (khoá: image, line, action, before, after) = file `03_fixes.csv`.

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file, chuyển người gán            | "needs_label"    |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml             | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Chỉ sửa lỗi ERROR, chỉ sửa trong `ds` (không bao giờ `data/raw`). Gom theo file, ghi MỘT lần, số dòng là số dòng GỐC.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
CLIP = {"BOX_OUT_OF_IMAGE"}
REMOVE = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _fx(image, line, action, before, after):
    return dict(image=image, line="" if line is None else line, action=action, before=before, after=after)


def _clip(text):
    """Trả dòng mới đã cắt về [0,1], hoặc None nếu box không còn diện tích."""
    c, x, y, w, h = parse_yolo_line(text)
    x1, x2 = max(0.0, x - w / 2), min(1.0, x + w / 2)
    y1, y2 = max(0.0, y - h / 2), min(1.0, y + h / 2)
    nw, nh = round(x2 - x1, 6), round(y2 - y1, 6)
    if nw <= 0 or nh <= 0:
        return None
    return f"{c} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {nw:.6f} {nh:.6f}"


def _remove_image(ds, stem):
    img = ds.image_path(stem)
    if img is None:                              # đã xoá ở issue khác: bỏ qua êm
        return None
    lab = ds.label_path(stem)
    before = img.name + (f" + {lab.name}" if lab.exists() else "")
    img.unlink()
    lab.unlink(missing_ok=True)
    return before


def fix(ds, issues, cfg):
    fixes = []
    errors = [i for i in issues if i.severity == ERROR]

    # 1) xoá ảnh trước: các issue dòng của ảnh đã xoá sẽ tự bị bỏ qua
    removed = set()
    for i in errors:
        if i.code in REMOVE and i.image not in removed:
            before = _remove_image(ds, i.image)
            if before is not None:
                removed.add(i.image)
                fixes.append(_fx(i.image, None, "remove_image", before, f"(đã xoá: {i.code})"))

    # 2) data.yaml
    if any(i.code == "BAD_CLASS_NAME" for i in errors) and ds.yaml_path.exists():
        d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        old = d.get("names")
        new = {k: v for k, v in enumerate(cfg["classes"])}
        if ds.yaml_names() != new:
            d["names"] = new
            ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
            fixes.append(_fx("data.yaml", None, "rename_classes", str(old), str(list(cfg["classes"]))))

    # 3) ảnh thiếu nhãn: không bịa nhãn, chuyển người
    for stem in sorted({i.image for i in errors if i.code == "MISSING_LABEL_FILE"}):
        if stem not in removed and ds.image_path(stem) is not None and not ds.label_path(stem).exists():
            fixes.append(_fx(stem, None, "needs_label", "(không có file)", "chuyển người gán"))

    # 4) lỗi theo dòng: gom theo file
    drop, clip = defaultdict(set), defaultdict(set)
    for i in errors:
        if i.line in (None, "") or i.image in removed:
            continue
        if i.code in DROP:
            drop[i.image].add(int(i.line))
        elif i.code in CLIP:
            clip[i.image].add(int(i.line))

    for stem in sorted(set(drop) | set(clip)):
        p = ds.label_path(stem)
        if not p.exists() or ds.image_path(stem) is None:
            continue
        raw = p.read_text(encoding="utf-8", errors="replace").splitlines()
        out, changed = [], False
        for no, text in enumerate(raw, 1):
            if no in drop[stem]:
                fixes.append(_fx(stem, no, "drop_line", text, "(đã xoá)"))
                changed = True
                continue
            if no in clip[stem]:
                try:
                    new = _clip(text)
                except ValueError:
                    new = None
                changed = True
                if new is None:
                    fixes.append(_fx(stem, no, "drop_line", text, "(đã xoá: box nằm hẳn ngoài ảnh)"))
                    continue
                fixes.append(_fx(stem, no, "clip_box", text, new))
                out.append(new)
                continue
            out.append(text)
        if changed:
            p.write_text("".join(l + "\n" for l in out), encoding="utf-8")
    return fixes
