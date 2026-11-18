"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line

NAME = "label_format"


def _check_file(ds, stem, lines, lc):
    issues = []
    n_cls = len(ds.classes)
    size = ds.image_size(stem)
    seen = []                                   # [(line, cls, box)] các dòng hợp lệ phía trước
    for no, text in lines:
        try:
            c, x, y, w, h = parse_yolo_line(text)
        except ValueError as e:
            issues.append(Issue(NAME, ERROR, "BAD_FORMAT", stem, f"dòng không đúng 5 cột số: {e}", no, {"text": text.strip()}))
            continue
        if not 0 <= c < n_cls:
            issues.append(Issue(NAME, ERROR, "BAD_CLASS_ID", stem, f"id lớp {c} ngoài 0..{n_cls - 1}", no, {"class_id": c}))
            continue
        if w <= 0 or h <= 0:
            issues.append(Issue(NAME, ERROR, "BOX_ZERO", stem, f"box rộng/cao <= 0 (w={w}, h={h})", no))
            continue

        overflow = max(0.0, -(x - w / 2), (x + w / 2) - 1.0, -(y - h / 2), (y + h / 2) - 1.0)
        if overflow > lc["overflow_tol"]:
            issues.append(Issue(NAME, ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ra ngoài ảnh {overflow:.4f}", no,
                                {"overflow": round(overflow, 6)}))

        box = (x, y, w, h)
        for pno, pc, pbox in seen:
            if pc == c:
                iou = iou_xywh(pbox, box)
                if iou > lc["dup_box_iou"]:
                    issues.append(Issue(NAME, ERROR, "DUP_BOX", stem, f"trùng box dòng {pno} (cùng lớp, IoU={iou:.3f})", no,
                                        {"dup_of": pno, "iou": round(iou, 4)}))
                    break
        seen.append((no, c, box))

        if size:
            W, H = size
            short = min(w * W, h * H)
            if short < lc["min_box_px"]:
                issues.append(Issue(NAME, WARN, "BOX_TINY", stem, f"box nhỏ: cạnh ngắn {short:.1f}px < {lc['min_box_px']}px", no,
                                    {"short_px": round(short, 2)}))
        if w * h > lc["max_box_frac"]:
            issues.append(Issue(NAME, WARN, "BOX_HUGE", stem, f"box phủ {w * h:.0%} ảnh", no, {"area_frac": round(w * h, 4)}))
    return issues


def run(ds, cfg):
    lc = cfg["label_format"]
    issues = []
    for p in ds.image_files():
        lines = ds.read_label_lines(p.stem)
        if lines is None:                       # thiếu file nhãn: missing_labels báo
            continue
        issues.extend(_check_file(ds, p.stem, lines, lc))
    return issues
