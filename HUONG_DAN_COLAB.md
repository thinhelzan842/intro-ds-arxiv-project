# Hướng dẫn treo máy chạy crawl trên Google Colab

Dành cho thành viên được giao **treo máy** chạy pipeline Milestone 1 (20.000 arXiv ID).
Không cần biết code: chỉ cần làm đúng các bước dưới đây.

> **Tóm tắt:** mở `src/05_run_pipeline.ipynb` từ branch `VA` → runtime **CPU** → thêm `S2_API_KEY`
> vào Secrets → **Run all** → để tab mở. Bị ngắt thì **Run all** lại, nó tự chạy tiếp từ chỗ dừng.

---

## 1. Chuẩn bị (làm một lần)

| Cần gì | Ghi chú |
|---|---|
| Một tài khoản Google | **Dùng đúng một tài khoản từ đầu tới cuối**: dữ liệu nằm trên Drive của tài khoản đó. |
| Google Drive còn trống | Chỉ lưu `.tex`/`.bib` nên không lớn, nhưng nên chừa **ít nhất 5 GB** cho chắc. |
| `S2_API_KEY` | Key Semantic Scholar, xin trưởng nhóm. Không có vẫn chạy được nhưng phần references chậm và hay bị HTTP 429. |
| Máy tính để mở tab cả ngày | Cắm sạc, tắt chế độ Sleep (xem mục 3). |

**Thời gian:** khoảng 3 giây cho mỗi phiên bản (version) bài báo → **18–23 giờ** cho ~22.000 version.
Colab miễn phí cho tối đa ~12 giờ mỗi phiên, nên sẽ cần **2–3 lần chạy**.

---

## 2. Chạy lần đầu

1. Vào <https://colab.research.google.com> → **File → Open notebook** → tab **GitHub**.
2. Dán `https://github.com/thinhelzan842/intro-ds-arxiv-project`, chọn branch **`VA`**,
   mở **`src/05_run_pipeline.ipynb`**.
3. **Runtime → Change runtime type → CPU** (không cần GPU, GPU còn bị giới hạn nhanh hơn).
4. Thêm API key: bấm biểu tượng **🔑 Secrets** ở thanh bên trái → **Add new secret**
   - Name: `S2_API_KEY`, Value: key được đưa
   - Bật công tắc **Notebook access**.
5. **Runtime → Run all**.
6. Khi hiện cửa sổ cho phép truy cập Google Drive: chọn **đúng tài khoản ở bước 1** và bấm cho phép.
   Notebook tự tạo thư mục `MyDrive/arxiv-project/`, không cần tạo tay.

**Thấy những dòng này là đang chạy đúng:**

- `Code in use: <mã commit> ...` (đã tải code mới nhất của branch `VA`)
- Thanh **Discovery**: số ID đã kiểm tra / 20.000 (vài phút)
- Thanh **Papers**: số bài đã xong / tổng số bài, kèm MB đã tải và **ETA** (thời gian còn lại)
- Thanh bên dưới: file đang tải (`<id>vN`)
- Mỗi 100 bài in một dòng log; dòng `[references] ...` là phần references chạy song song

> Muốn ghi email liên hệ vào User-Agent gửi arXiv (không bắt buộc): tạo file
> `MyDrive/arxiv-project/.env` chứa dòng `ARXIV_CONTACT=email@cua.ban`.

---

## 3. Trong lúc treo máy

**Nên làm**

- Giữ tab Colab **mở**, không đóng trình duyệt.
- Cắm sạc; Windows: **Settings → System → Power** → *Sleep* = **Never**.
  Laptop: chỉnh "When I close the lid" = **Do nothing** nếu muốn gập máy.
- Khoảng 1 giờ ghé xem tab một lần: Colab có thể ngắt nếu thấy không có ai tương tác,
  hoặc hiện hộp thoại "Are you still there?" cần bấm xác nhận.
- Mạng ổn định (Wi-Fi rớt lâu có thể làm Colab ngắt).

**Không được làm**

- **Không** mở notebook 05 (hoặc 06) ở tab/runtime thứ hai trên cùng Drive: notebook có khoá
  (`pipeline.lock`), runtime thứ hai sẽ báo lỗi và dừng.
- **Không** sửa `ARXIV_DELAY` (phải ≥ 3 giây theo lab book, giảm xuống dễ bị arXiv chặn).
- **Không** xoá thư mục `data/`, `state/`, `logs/` trong `MyDrive/arxiv-project/`: đó là dữ liệu và
  bằng chứng benchmark cho báo cáo.
- **Không** dán API key vào notebook rồi lưu/commit lên GitHub.

Bấm **Stop** (dừng cell) là an toàn: phần đã tải được giữ lại.

---

## 4. Khi bị ngắt kết nối hoặc hết 12 giờ

1. Mở lại đúng notebook (cùng tài khoản Google).
2. **Runtime → Run all**, cho phép mount Drive như lần đầu.
3. Notebook tự đọc lại những gì đã xong và **chỉ tải phần còn thiếu**. Đầu lần chạy sẽ in
   phần trăm bài và version đã hoàn thành.

Mỗi lần chạy được tính vào benchmark (`logs/sessions/`), kể cả lần bị Colab cắt ngang
(mất tối đa 5 phút số liệu), nên **cứ chạy lại, không cần làm gì thêm**.

---

## 5. Lỗi thường gặp

| Thấy gì | Làm gì |
|---|---|
| Báo **lock** / có run khác đang giữ khoá | Tắt runtime cũ (**Runtime → Disconnect and delete runtime**) ở tab kia. Nếu runtime cũ đã mất hẳn, **đợi 3 phút** rồi Run all lại. |
| `STOPPED EARLY: ... Drive full` | Drive đầy: dọn bớt Drive (hoặc thùng rác Drive), rồi Run all lại. |
| `STOPPED EARLY: ... unmounted` | Drive bị ngắt: Run all lại để mount lại. |
| `STOPPED EARLY: 20 versions failed in a row` | arXiv hoặc mạng đang lỗi: đợi 15–30 phút rồi Run all lại. |
| Discovery báo lỗi batch / HTTP 429 | arXiv đang giới hạn: đợi vài phút rồi Run all lại, các batch đã xong được giữ. |
| `S2 key: NOT SET` hoặc rất nhiều HTTP 429 ở references | Kiểm tra Secret `S2_API_KEY` đúng tên và đã bật **Notebook access**. |
| "You cannot currently connect to a GPU/backend" | Hết hạn mức Colab của tài khoản hôm nay: đợi vài giờ rồi chạy lại (cùng tài khoản). |
| Lỗi khác | Chụp màn hình **cả output của cell bị lỗi** gửi lên nhóm. Đừng xoá gì trên Drive. |

---

## 6. Khi nào là xong và gửi gì cho nhóm

Xong khi cell cuối (mục **3. Paper log and benchmark**) in bảng kết quả, trong đó
`Versions processed` có hai số bằng nhau (ví dụ `21,950 / 21,950`), và dòng cuối là
`Google Drive flushed and unmounted`.

Sau đó **chia sẻ thư mục `MyDrive/arxiv-project/`** cho cả nhóm (quyền *Viewer* là đủ), hoặc ít nhất gửi:

- `logs/benchmark.json`, `logs/performance.json`, `logs/papers.csv`, `logs/benchmark_sessions.jsonl`
- `logs/figures/` (4 biểu đồ PNG cho báo cáo)
- `data/raw/` (bộ dữ liệu: `<yymm-id>/vN/*.tex|*.bib` và `references.json`)

Báo lên nhóm: đã chạy bao nhiêu lần (session), tổng thời gian, và có lỗi gì không.

---

## 7. (Tuỳ chọn) Người thứ hai chạy riêng phần references

Chỉ làm khi nhóm muốn tách references sang tài khoản khác. Khi đó **người chạy 05** đổi
`RUN_REFERENCES = False` trong cell Setup đầu tiên của 05 trước khi Run all.

Người chạy references:

1. Mở **`src/07_run_references.ipynb`** (branch `VA`) trên Colab của mình, runtime CPU.
2. Thêm Secret `S2_API_KEY` của mình (như mục 2, bước 4).
3. **Run all**. Không cần đợi bên 05; bị ngắt thì Run all lại.
4. Cell cuối tạo `MyDrive/arxiv-project/references_export.zip`. Gửi file này cho người chạy 05.

Người chạy 05: đặt `references_export.zip` vào `MyDrive/arxiv-project/` (cạnh thư mục `data/`)
rồi Run all lại; bước báo cáo tự nhập file này.

---

## 8. Muốn thử trước cho chắc (khoảng 5 phút)

Mở `src/06_test_100_versions.ipynb` → Run all. Notebook này chạy pipeline thật trên 100 version đầu
tiên, ghi vào `test_runs/` nên **không đụng** tới dữ liệu thật. Chạy xong thì **Disconnect runtime**
trước khi mở 05 (hai notebook dùng chung khoá).
