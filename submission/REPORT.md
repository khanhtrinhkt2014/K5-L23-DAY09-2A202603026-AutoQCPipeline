# Báo cáo Day 09 — Nguyễn Khánh Trình, 2A202603026

## 1. Kết luận trước
Pipeline kết luận **HOLD** (mã thoát 10). **224** ảnh vào; **22** ảnh bị loại ở cửa vào → **202** ảnh vào QC; xuất **202/202** ảnh ra `export/clean_v1/` dưới dạng **bản NHÁP** (`manifest.json`: `decision: Hold`), chưa phát hành.
Lý do: không còn lỗi bắt buộc (`n_errors = 0`), nhưng **38/202 ảnh (18,8%)** còn cảnh báo chưa người duyệt, ≥ ngưỡng 10%: hàng đợi cần duyệt có **125 ảnh** trong khi ngân sách chỉ **80 ảnh** (`08_summary.json`).

## 2. Lỗi và phân việc
Số liệu từ `01_intake` + `02_error_list_v1` (QC vòng 1 trên 202 ảnh) và `03_fixes.csv`.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8 ảnh / 224 | máy (loại ở cửa vào) | md5 trùng từng byte, chắc chắn |
| `DUP_IMAGE_NEAR` | 4 ảnh / 224 | máy (loại) | phash ≤ 12; đã mở xem từng cặp (§3) |
| `LEAK_TEST` | 5 ảnh / 224 | máy (loại) | trùng ảnh test/gold_val → metric đẹp giả |
| `BAD_SIZE` / `CORRUPT_IMAGE` | 3 / 2 ảnh | máy (loại) | quy tắc cứng, không cần mắt người |
| `BOX_OUT_OF_IMAGE` | 8 dòng | máy (`clip_box` 8) | cắt về [0,1], giữ lớp — sửa cú pháp, không đổi nghĩa |
| `DUP_BOX` / `BAD_CLASS_ID` / `BOX_ZERO` / `BAD_FORMAT` | 7 / 6 / 4 / 3 dòng | máy (`drop_line` 20) | dòng vô nghĩa hoặc lặp: xoá an toàn, có log trước→sau |
| `BAD_CLASS_NAME` | 2 issue, 1 file | máy (`rename_classes` 1) | `data.yaml` ghi `Person`, `Bus` → đúng `cfg.classes` |
| `MISSING_LABEL_FILE` | 6 ảnh / 202 | **người** (`needs_label` 6) | máy không bịa nhãn; đẩy lên đầu hàng đợi (trọng số 10) |
| `POSSIBLE_MISSING` | 53 | **người** | model thấy vật mà nhãn không có — có thể model sai |
| `POSSIBLE_FALSE_POS` | 29 | **người** | box không khớp vật nào model thấy |
| `POSSIBLE_LOOSE_BOX` | 28 | **người** | đúng vật, IoU thấp |
| `POSSIBLE_WRONG_CLASS` | 18 | **người** | nhầm lớp hợp lệ: cần ngữ nghĩa |
| `EMPTY_LABEL` / `BOX_TINY` / `BOX_HUGE` / `CLASS_RARE` | 12 / 6 / 3 / 4 | **người** | cảnh báo: ảnh nền hay thiếu nhãn? box nhỏ có nên gán? |

Tổng: 36 lỗi bắt buộc + 153 cảnh báo ở v1 → sau autofix còn **6** lỗi bắt buộc (đều `MISSING_LABEL_FILE`) → sau người duyệt **0**.

**Hàng đợi** (`05_review_queue.csv`, 125 ảnh): điểm = Σ trọng số mã lỗi × (1 + conf của model). Đầu hàng là `img_0020` (11,5: một dòng `BAD_CLASS_ID` 93 đã bị xoá + model nói bus với conf 0,95 ở chỗ nhãn ghi truck + thiếu một người) và 6 ảnh `NEEDS_LABEL` (10,0) — không có người gán thì các ảnh này là Rework. Người duyệt mô phỏng xem 80/125 ảnh; cảnh báo ngữ nghĩa giảm từ 123 (v2: MISSING 53 + LOOSE 28 + FALSE_POS 24 + WRONG 18) xuống 57 (v3), tức người xử lý được ~54% cảnh báo ngữ nghĩa; 45 ảnh còn lại (điểm thấp: thường chỉ 1 `POSSIBLE_FALSE_POS` hoặc `BOX_TINY`) không được xem.

## 3. Calibration (2 ngưỡng)
Calib: 39 ảnh, 51 lỗi chèn (`submission/calibration/calibration_report.md`).

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | NEAR: 1,00/0,50 → 1,00/0,67 | Precision bằng 1,00 từ 2 đến 16 nên chọn theo recall. 4–14 cho cùng recall 0,67; 16 cao nhất trên calib (0,83) nhưng **gộp nhầm ảnh khác nhau trên raw** (xem dưới). Chọn 12: bắt hết cặp trùng thật thấy trên raw (khoảng cách 6, 8, 10), cách xa ngưỡng bắt đầu sai (16). |
| `second_opinion.conf` | 0,25 | **0,6** | MISSING 0,50/1,00 → 0,57/1,00 · WRONG_CLASS 0,56/0,83 → 0,62/0,83 · LOOSE 0,29/0,40 → 0,20/0,20 | Ngân sách người có hạn (80 ảnh) nên cần precision cao hơn để không phí lượt duyệt, nhưng **không được mất recall MISSING** (thiếu nhãn là lỗi nặng nhất): 0,6 là giá trị cao nhất còn giữ MISSING recall 1,00. Cái giá: LOOSE_BOX recall giảm 0,40 → 0,20. 0,8 cho WRONG_CLASS F1 0,91 nhưng MISSING recall rơi còn 0,75. |

**Chỗ calibration đánh lừa:**
1. `phash_dist = 16` có F1 cao nhất trên calib (0,91) và precision 1,00, nhưng trên raw nó loại thêm 9 ảnh (31 thay vì 22). Mở xem: `img_0011` (tay vợt tennis) bị coi là trùng `img_0008` (2 người trượt tuyết); `img_0013` (bàn làm việc với laptop) bị coi là rò rỉ `test_087` (trận bóng chày); `img_0177` (người lướt sóng) "trùng" `img_0113` (người đàn ông ngồi bàn). Calib 39 ảnh không có cặp "khác nhưng phash gần" nên precision 1,00 là ảo.
2. Ngưỡng `conf` quyết định luôn kết luận gate: cùng phash 12, conf 0,5 → Hold 21,8%; 0,6 → Hold 18,8%; **0,8 → Release 7,9%**. Nâng conf lên 0,8 để "được Release" là tối ưu cho cổng, không phải cho chất lượng: MISSING recall trên calib còn 0,75, tức ~¼ vật thiếu nhãn sẽ lọt qua. Tôi giữ 0,6 và báo Hold.

Đối chiếu khởi đầu (2 / 0,25) trên raw: chỉ loại 19 ảnh (sót 3 ảnh trùng thật: `img_0223`~`img_0077`, `img_0186`~`img_0061`, rò rỉ `img_0101`~`test_039`), hàng đợi 145 ảnh, Hold 29,3%.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` → log: `kết luận: REWORK — còn 6 lỗi bắt buộc (MISSING_LABEL_FILE: 6)`, **mã thoát 20**, `Bước 5/5 KHÔNG xuất`, thư mục `work/exp_nb` **không được tạo**. Không có người gán thì 6 ảnh chưa nhãn chặn cả lô, dù autofix đã sửa hết lỗi cú pháp.

**Lỗi tự nhìn thấy (Bước 1) đều được bắt:** `img_0001` thiếu box người lính → `POSSIBLE_MISSING` (conf 0,95); `img_0030` người ở mép trái có 2 box → dòng 9 `BOX_OUT_OF_IMAGE` (tràn 0,023, autofix cắt) rồi `POSSIBLE_FALSE_POS` (IoU 0,08); `img_0035` lá cây gán person → dòng 2 `POSSIBLE_FALSE_POS` (IoU 0). Hai ảnh đầu được người duyệt; `img_0035` (điểm 2,0) nằm ngoài ngân sách 80 → vẫn còn trong `07_error_list_v3`.

**(b) Điểm mù**, đo bằng cách so 84 ảnh "sạch" (không được duyệt và không có cảnh báo nào ở v3) với nhãn người tham chiếu (`data/review_reference/`):
1. **Nhầm lớp mà model lớn cũng nhầm** — 3 box: `img_0007` nhãn car, người gán truck (IoU 0,88); `img_0153` nhãn bus và car, người gán truck (IoU 0,92 / 0,79). yolo26l đồng ý với nhãn sai nên `second_opinion` im lặng.
2. **Thiếu box vật nhỏ/khuất** — 38 box người có mà nhãn không có (vd. `img_0005`, `img_0074` nhiều người nhỏ ở xa) vì model không thấy với conf ≥ 0,6 hoặc vật < `min_area_px`.
3. **Box lỏng nhẹ** — 28 box cùng lớp có IoU 0,5–0,7 với nhãn người (vd. `img_0023` 0,54): trên `iou_loose = 0,5` nên không bị cờ.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Colab T4, `yolo26n.pt`, 20 epoch, imgsz 640, batch 16, seed 0 và 1; cùng val (`gold_val`, 40 ảnh) và test (100 ảnh nhãn người). `config_sha1` của mọi lần chạy = `08_summary.json`; `clean` dùng manifest `bb2ba544…` (bản nháp Hold).

| biến thể | #ảnh train | số seed | mAP50 (TB ± độ lệch) | mAP50-95 | precision | recall |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 202 | 2 | 0.701 ± 0.025 | 0.487 ± 0.008 | 0.759 ± 0.003 | 0.625 ± 0.019 |

AP50 theo lớp (TB 2 seed): car raw 0.738 / clean 0.738 · person 0.822 / 0.823 · truck **0.648 / 0.538** · bus 0.695 / 0.703.

**Kết luận trung thực: chưa kết luận được.** Chênh mAP50 (clean − raw) = **−0.025**, bằng đúng độ lệch giữa 2 seed của `clean` (±0.025; hai seed 0.718 và 0.683). Seed 0 của `clean` (0.718) chỉ thấp hơn `raw` 0.008. Với 2 seed và test 100 ảnh, không thể nói `clean` tốt hơn hay kém hơn `raw`. Gần như toàn bộ khoảng chênh đến từ lớp **truck** (−0.11), lớp chỉ có 24 box trong test và dao động mạnh ngay trong `clean` (0.590 vs 0.486 giữa 2 seed); car/person/bus gần như bằng nhau.

Giả thuyết và cách kiểm:
1. **`raw` được lợi từ rò rỉ test**: 5 ảnh `raw` trùng ảnh test (`LEAK_TEST`: test_009, 033, 039, 044, 085 — 10 car, 11 person, 1 truck) nên model `raw` đã thấy 5% tập test lúc train; ngoài ra 8 cặp trùng y hệt + 4 cặp gần đúng làm `raw` có 224 ảnh nhưng ít ảnh khác nhau hơn. *Kiểm:* đánh giá lại cả hai model trên test bỏ 5 ảnh rò rỉ (95 ảnh) — nếu khoảng chênh thu hẹp, rò rỉ đã thổi phồng `raw`.
2. **`clean` vẫn còn lỗi nhãn ngữ nghĩa**: 38 ảnh còn cảnh báo chưa người duyệt (45 ảnh trong hàng đợi vượt ngân sách 80), và §4 cho thấy ảnh "sạch" vẫn thiếu 38 box, nhầm lớp 3 box (đều liên quan truck). `clean` có 41 box truck so với 32 ở `raw` (người duyệt thay nhãn bằng COCO) — phân phối truck đổi nên AP truck biến động. *Kiểm:* train biến thể `oracle` (nhãn người, chặn trên) và so AP truck; xem `07_error_list_v3` lọc theo lớp 2.
3. **Nhiễu thống kê**: test 100 ảnh, 24 box truck, 2 seed. *Kiểm:* thêm seed 2–4 và báo khoảng tin cậy.

Việc tiếp theo: đánh giá trên test bỏ ảnh rò rỉ, thêm 3 seed, chạy `oracle`; duyệt nốt 45 ảnh trong hàng đợi rồi train lại.

## 6. Quyết định và ghi chú AI
**(a)** Quyết định: **Hold** — bản `clean_v1` chỉ dùng thử nghiệm. Để thành Release cần đưa tỉ lệ ảnh còn cảnh báo chưa duyệt < 10% (≤ 20/202 ảnh), tức người duyệt thêm ≥ 18 trong 45 ảnh còn lại của hàng đợi (tăng ngân sách lên ~100 ảnh), **không** nới `conf` chỉ để qua cổng. Điều kiện đổi sang Rework: người duyệt để lại ảnh chưa gán nhãn hoặc lỗi cú pháp mới.

**(b) Dùng AI (Claude) viết code và nháp báo cáo.**
- Prompt chính: "viết 4 module theo đúng docstring (đầu vào/đầu ra, mã lỗi, ca biên), ngưỡng đọc từ `cfg`, không sửa `data/raw`, chạy pytest đến khi xanh".
- Cách kiểm: `pytest` 79/79 xanh; chạy `make run` và đối chiếu 3 lỗi tự thấy với `02_error_list_v1`; so ảnh "sạch" với `review_reference`; mở ảnh các cặp trùng để kiểm `phash_dist`.
- Một lần AI sai: khi đọc nhãn bằng mắt, Claude (trong chat) nói box tràn của `img_0030` ở **dòng 8**; pipeline báo **dòng 9** — Claude đã đếm nhầm vì gán dòng đầu của `img_0030` cho file trước đó. Số dòng phải lấy từ báo cáo máy, không đếm tay.
