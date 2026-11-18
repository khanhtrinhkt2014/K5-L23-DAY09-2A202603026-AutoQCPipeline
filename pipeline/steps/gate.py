"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo, chưa người duyệt) / (tổng số ảnh).
Lỗi bắt buộc KHÔNG bao giờ được bỏ qua, kể cả ở ảnh đã duyệt.
"""
from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)
    reviewed = set(reviewed)
    thr = cfg["gate"]["warn_ratio_hold"]

    errors = [i for i in issues if i.severity == ERROR]
    warn_images = {i.image for i in issues
                   if i.severity == WARN and i.image in stems and i.image not in reviewed}
    n_images = len(stems)
    ratio = len(warn_images) / n_images if n_images else 0.0
    ratio_r = round(ratio, 4)

    reasons = []
    if errors:
        decision = "Rework"
        codes = {}
        for i in errors:
            codes[i.code] = codes.get(i.code, 0) + 1
        detail = ", ".join(f"{k}: {v}" for k, v in sorted(codes.items()))
        reasons.append(f"còn {len(errors)} lỗi bắt buộc ({detail})")
    elif ratio_r >= thr:
        decision = "Hold"
        reasons.append(f"{len(warn_images)}/{n_images} ảnh ({ratio_r:.1%}) còn cảnh báo chưa người duyệt, "
                       f">= ngưỡng {thr:.0%}")
    else:
        decision = "Release"
        reasons.append(f"không còn lỗi bắt buộc; {len(warn_images)}/{n_images} ảnh ({ratio_r:.1%}) còn cảnh báo "
                       f"chưa duyệt, < ngưỡng {thr:.0%}")
    if errors and warn_images:
        reasons.append(f"ngoài ra {len(warn_images)}/{n_images} ảnh ({ratio_r:.1%}) còn cảnh báo chưa duyệt")

    return dict(decision=decision, n_errors=len(errors), n_warn_images=len(warn_images),
                n_images=n_images, warn_ratio=ratio_r, reasons=reasons)
