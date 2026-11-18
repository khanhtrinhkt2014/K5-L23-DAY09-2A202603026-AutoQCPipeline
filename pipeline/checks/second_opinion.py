"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★

Test:  pytest tests/test_second_opinion.py -q

Chỉ CẢNH BÁO (model cũng có thể sai): ảnh bị cờ vào hàng đợi cho NGƯỜI duyệt.
`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]`. Ngưỡng ở `cfg["second_opinion"]`.

Với từng dự đoán r (conf >= conf, diện tích px >= min_area_px), cands = nhãn MỌI lớp có IoU >= iou_missing:
  (1) cands rỗng                                   -> POSSIBLE_MISSING
  (2) có cands cùng lớp: IoU tốt nhất < iou_loose  -> POSSIBLE_LOOSE_BOX, ngược lại không cờ
  (3) chỉ có cands khác lớp: IoU tốt nhất >= iou_match -> POSSIBLE_WRONG_CLASS, ngược lại không cờ
Với từng dòng nhãn hợp lệ: IoU với MỌI dự đoán (conf >= fp_conf) < iou_missing -> POSSIBLE_FALSE_POS (có số dòng).
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds

NAME = "second_opinion"


def _labels(ds, stem):
    """[(số dòng gốc, lớp, (cx, cy, w, h))] các dòng hợp lệ."""
    out = []
    for no, text in ds.read_label_lines(stem) or []:
        try:
            c, x, y, w, h = parse_yolo_line(text)
        except ValueError:
            continue
        if 0 <= c < len(ds.classes):
            out.append((no, c, (x, y, w, h)))
    return out


def run(ds, cfg, preds=None):
    sc = cfg["second_opinion"]
    if preds is None:
        preds = get_preds(ds, cfg, "checker")
    names = ds.classes
    issues = []
    for p in ds.image_files():
        stem = p.stem
        if stem not in preds or ds.read_label_lines(stem) is None:
            continue
        size = ds.image_size(stem)
        if not size:
            continue
        W, H = size
        labels = _labels(ds, stem)
        rows = preds[stem] or []

        for r in rows:
            rc, conf, box = int(r[0]), float(r[1]), tuple(float(v) for v in r[2:6])
            if conf < sc["conf"] or box[2] * W * box[3] * H < sc["min_area_px"]:
                continue
            cands = [(iou_xywh(box, lb), lc) for _, lc, lb in labels]
            cands = [(iou, lc) for iou, lc in cands if iou >= sc["iou_missing"]]
            rname = names[rc] if 0 <= rc < len(names) else str(rc)
            if not cands:
                issues.append(Issue(NAME, WARN, "POSSIBLE_MISSING", stem,
                                    f"model thấy {rname} (conf {conf:.2f}) nhưng nhãn không có box", None,
                                    {"conf": conf, "cls": rc, "box": [round(v, 4) for v in box]}))
                continue
            same = [iou for iou, lc in cands if lc == rc]
            if same:
                best = max(same)
                if best < sc["iou_loose"]:
                    issues.append(Issue(NAME, WARN, "POSSIBLE_LOOSE_BOX", stem,
                                        f"box {rname} lệch/lỏng so với model (IoU {best:.2f})", None,
                                        {"conf": conf, "iou": round(best, 4), "cls": rc}))
                continue
            best_iou, best_cls = max(cands)
            if best_iou >= sc["iou_match"]:
                lname = names[best_cls] if 0 <= best_cls < len(names) else str(best_cls)
                issues.append(Issue(NAME, WARN, "POSSIBLE_WRONG_CLASS", stem,
                                    f"nhãn là {lname}, model nói {rname} (conf {conf:.2f}, IoU {best_iou:.2f})", None,
                                    {"conf": conf, "iou": round(best_iou, 4), "label_cls": best_cls, "pred_cls": rc}))

        fp_boxes = [tuple(float(v) for v in r[2:6]) for r in rows if float(r[1]) >= sc["fp_conf"]]
        for no, lc, lb in labels:
            best = max((iou_xywh(lb, pb) for pb in fp_boxes), default=0.0)
            if best < sc["iou_missing"]:
                lname = names[lc]
                issues.append(Issue(NAME, WARN, "POSSIBLE_FALSE_POS", stem,
                                    f"box {lname} không khớp vật nào model thấy (IoU tốt nhất {best:.2f})", no,
                                    {"iou": round(best, 4), "cls": lc}))
    return issues
