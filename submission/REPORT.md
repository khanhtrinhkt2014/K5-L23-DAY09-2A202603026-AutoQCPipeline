# Báo cáo Day 09 — Nguyễn Khánh Trình, 2A202603026

## 1. Kết luận trước
**HOLD** (mã thoát 10). 224 ảnh vào, loại 22 ở cửa vào, còn 202 ảnh; xuất `export/clean_v1/` dạng **bản nháp**.
Không còn lỗi bắt buộc, nhưng **38/202 ảnh (18,8%)** còn cảnh báo chưa duyệt (≥ ngưỡng 10%): hàng đợi 125 ảnh, ngân sách người chỉ 80.

## 2. Lỗi và phân việc
| Mã lỗi | Số lượng | Ai sửa | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` / `NEAR`, `LEAK_TEST`, `BAD_SIZE`, `CORRUPT_IMAGE` | 8 / 4, 5, 3, 2 ảnh (/224) | máy: loại ảnh | quy tắc chắc chắn; rò rỉ test làm metric đẹp giả |
| `BOX_OUT_OF_IMAGE` | 8 dòng | máy: cắt về [0,1] | sửa cú pháp, giữ lớp |
| `DUP_BOX`, `BAD_CLASS_ID`, `BOX_ZERO`, `BAD_FORMAT` | 7, 6, 4, 3 dòng | máy: xoá dòng (20) | dòng vô nghĩa/lặp, có log trước→sau |
| `BAD_CLASS_NAME` | 1 file | máy: sửa `data.yaml` | `Person`/`Bus` → đúng `cfg.classes` |
| `MISSING_LABEL_FILE` | 6 ảnh (/202) | **người** | máy không bịa nhãn; đứng đầu hàng đợi |
| `POSSIBLE_MISSING` / `FALSE_POS` / `LOOSE_BOX` / `WRONG_CLASS` | 53 / 29 / 28 / 18 | **người** | cần ngữ nghĩa, model cũng có thể sai |

v1: 36 lỗi bắt buộc + 153 cảnh báo → sau autofix còn 6 (đều `MISSING_LABEL_FILE`) → sau người duyệt còn 0.
**Hàng đợi** xếp theo trọng số mã lỗi × (1 + conf model): đầu hàng là `img_0020` và 6 ảnh thiếu nhãn. Người duyệt 80/125 ảnh, cảnh báo ngữ nghĩa giảm 123 → 57; 45 ảnh điểm thấp không được xem.

## 3. Calibration
| Tham số | Khởi đầu → chọn | P/R trên calib (trước → sau) | Lý do |
|---|---|---|---|
| `phash_dist` | 2 → **12** | NEAR 1,00/0,50 → 1,00/0,67 | 4–14 cùng recall; 12 bắt hết cặp trùng thật trên raw (khoảng cách 6, 8, 10), còn xa mức bắt đầu gộp sai (16) |
| `second_opinion.conf` | 0,25 → **0,6** | MISSING 0,50/1,00 → 0,57/1,00; WRONG_CLASS 0,56/0,83 → 0,62/0,83 | giá trị cao nhất còn giữ recall MISSING = 1; đổi lại LOOSE recall giảm 0,40 → 0,20 |

**Điểm đánh lừa:** `phash_dist = 16` có F1 cao nhất trên calib (precision 1,00) nhưng trên raw loại thêm 9 ảnh khác hẳn nhau (vd. tay vợt tennis `img_0011` bị coi trùng ảnh trượt tuyết `img_0008`). Ngoài ra `conf = 0,8` cho ra Release (7,9%) nhưng recall MISSING chỉ còn 0,75 — nâng ngưỡng để qua cổng là tối ưu cho cổng, không cho chất lượng.

## 4. Cửa chặn và điểm mù
**Gate chặn thật:** `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` → **Rework**, mã thoát 20, còn 6 `MISSING_LABEL_FILE`, không tạo thư mục export.

**3 lỗi tôi tự thấy đều bị bắt:** `img_0001` thiếu box người lính (`POSSIBLE_MISSING`); `img_0030` người mép trái có 2 box (dòng 9 `BOX_OUT_OF_IMAGE` → `POSSIBLE_FALSE_POS`); `img_0035` lá cây gán person (`POSSIBLE_FALSE_POS`, nhưng nằm ngoài ngân sách 80 nên chưa được duyệt).

**Điểm mù** (so 84 ảnh "sạch" với nhãn người tham chiếu):
1. Nhầm lớp mà model lớn cũng nhầm: `img_0007` car ↔ truck, `img_0153` bus/car ↔ truck.
2. Thiếu box vật nhỏ, ở xa (38 box, vd. `img_0005`, `img_0074`): model không thấy với conf ≥ 0,6.
3. Box lỏng nhẹ (IoU 0,5–0,7) nằm trên `iou_loose` nên không bị cờ.

## 5. Train raw vs clean
Colab T4, `yolo26n`, 20 epoch, 2 seed, cùng val/test; `config_sha1` khớp `08_summary.json`.

| biến thể | ảnh | mAP50 | mAP50-95 | precision | recall |
|---|---|---|---|---|---|
| raw | 224 | 0,726 ± 0,000 | 0,512 ± 0,004 | 0,764 ± 0,061 | 0,649 ± 0,028 |
| clean | 202 | 0,701 ± 0,025 | 0,487 ± 0,008 | 0,759 ± 0,003 | 0,625 ± 0,019 |

**Chưa kết luận được.** Chênh mAP50 = −0,025, đúng bằng độ lệch giữa 2 seed của clean. Gần hết khoảng chênh nằm ở lớp truck (0,648 vs 0,538; test chỉ có 24 box truck); car/person/bus gần như bằng nhau.
Nguyên nhân có thể và cách kiểm:
1. raw có 5 ảnh rò rỉ test → đánh giá lại trên test bỏ 5 ảnh đó.
2. clean vẫn còn lỗi ngữ nghĩa (38 ảnh chưa duyệt, nhầm lớp liên quan truck) → train biến thể `oracle` làm chặn trên.
3. Nhiễu: test 100 ảnh, 2 seed → thêm seed.

## 6. Quyết định và ghi chú AI
**(a)** **Hold.** Muốn Release phải đưa số ảnh còn cảnh báo chưa duyệt xuống ≤ 20/202, tức duyệt thêm ≥ 18 ảnh trong hàng đợi (ngân sách ~100), không nới `conf`. Đổi sang Rework nếu còn ảnh chưa gán nhãn hoặc phát sinh lỗi cú pháp.

**(b)** Dùng Claude viết code và nháp báo cáo.
- Prompt chính: viết 4 module đúng docstring (vào/ra, mã lỗi, ca biên), ngưỡng đọc từ `cfg`, không sửa `data/raw`, chạy pytest đến khi xanh.
- Cách kiểm: pytest 79/79; `make run` rồi đối chiếu 3 lỗi tự thấy với `02_error_list_v1`; mở ảnh các cặp trùng để kiểm `phash_dist`.
- Một lần AI sai: khi đọc nhãn bằng mắt, Claude (trong chat) nói box tràn của `img_0030` ở **dòng 8**; pipeline báo **dòng 9**, vì Claude đếm nhầm (gán dòng đầu của `img_0030` cho file trước đó). Số dòng phải lấy từ báo cáo máy, không đếm tay.
