# Kết quả hoàn thiện pipeline Milestone 2 (18/11/2026)

Làm trên nhánh local `m2-pipeline`, tiếp theo `4e3ca2c`. Có 4 commit mới, **chưa push**: nhánh đi trước
`origin/m2-pipeline` 4 commit. Không merge vào `main`, không tạo PR, không sửa nhánh của ai khác.

| Commit | Việc | File | Sửa code của ai |
|---|---|---|---|
| `e2a2c57` | 2. `gather` / `find_root` bỏ sót file, chọn sai root | `src/10_parse_tree.ipynb`, `src/13_dedup_export.ipynb` | **Member 2** (notebook 10) và của tôi (13) |
| `3dee56b` | 3. `clean_latex` đổi `--` trong toán, thiếu lệnh cần bỏ/bóc | `src/11_normalize.ipynb`, `src/13_dedup_export.ipynb` | **Member 4** (notebook 11), 13 chỉ tăng `PARSER_BASE` |
| `56227f6` | 4. Ghi rõ `build_tree` đang dùng fallback của 13 | `README.md`, `src/13_dedup_export.ipynb` | của tôi |
| `253b7e8` | 5. Report Jupyter Book cho Milestone 2 | `docs/_toc.yml`, `docs/milestone2/statistics.ipynb`, `docs/milestone2/report_data.py`, `docs/README.md`, `docs/intro.md`, `docs/_config.yml`, `README.md` | của tôi |

`PARSER_BASE` của 13: `13.3` → `13.4` (việc 2) → **`13.5`** (việc 3). Vì vậy notebook 15 sẽ parse lại mọi paper.

---

## Việc 1: notebook 10 mới của Member 2

**Không merge.** Sau `git fetch`, `origin/feat/latex-tree-parser` vẫn dừng ở `fb8d516`
("feat: add LaTeX hierarchy parsing and fix source resolution"). File `notebooks/10_parse_tree.ipynb` ở đó
vẫn chỉ còn 2.717 byte, và `json.load` báo lỗi `Expecting value: line 97 column 1 (char 2717)`. Không nhánh
nào khác có bản 10 mới. Notebook 10 vẫn **chưa có `build_tree`**, nên tôi chuyển sang việc 2 và làm việc 4.

## Việc 2: `gather` và `find_root` của notebook 10 (commit `e2a2c57`)

### Bên nào đúng ở hai version chọn root khác nhau

| Version | Notebook 10 chọn | Fallback chọn | Đúng | Lý do |
|---|---|---|---|---|
| `2609-32879/v1` | `cl.tex` | `main_rev2__3_.tex` | **fallback** | `cl.tex` là thư gửi ban biên tập ("Dear Editors"), bài báo là `main_rev2__3_.tex`. Hai file bằng điểm (65), 10 phân định theo thứ tự chữ cái. |
| `2609-32908/v1` | `main.tex` | `main_with_appendix.tex` | **fallback** | `main_with_appendix.tex` = `\def\mathnlpappendix{1}` + `\input{main.tex}` (bản build có phụ lục). Theo quy tắc "root là file không bị file khác include", root là file này. |

### Nguyên nhân 8 version gom lệch hơn 10% (prompt ghi 7; đo lại được 8)

| Version | 10 trước sửa | Fallback | Nguyên nhân |
|---|---|---|---|
| `2609-32846/v1` | 60.076 | 105.508 | `\input{Sections/1.Introduction}`: dấu chấm bị hiểu là đuôi file, nên 10 không thêm `.tex` |
| `2609-32975/v1` | 66.532 | 86.423 | như trên: `\input{4.5_Results}` |
| `2609-32922/v1` | 2.246 | 53.141 | dùng `\import{Introduction/}{index.tex}` (lồng nhau); 10 chưa hỗ trợ `\import` |
| `2609-32879/v1` | 2.667 | 15.045 | chọn sai root (thư gửi kèm) |
| `2609-32911/v1` | 41.091 | 31.259 | 10 coi môi trường `comment` là verbatim nên **giữ nguyên** nội dung (không được in ra PDF) |
| `2609-33015/v1` | 152.520 | 123.236 | như trên (12 môi trường `comment`) |
| `2609-33084/v1` | 195.803 | 119.224 | như trên (28 môi trường `comment`) |
| `2609-33093/v1` | 94.350 | 79.764 | như trên |

### Sửa trong `src/10_parse_tree.ipynb` (Member 2)

Sửa tối thiểu, giữ phong cách code của Member 2 (comment tiếng Việt, xuống dòng kiểu của bạn ấy):

- **Tên có dấu chấm:** cả hai resolver (`_resolve_include` của `find_root` và `resolve` của `gather`) giờ thử
  `<tên>.tex` trước, rồi tới đúng tên đã ghi, như TeX vẫn làm. Trước đây, `Path("1.Introduction").suffix`
  được hiểu là đuôi file nên không thêm `.tex`.
- **`\subfile`, `\import`, `\subimport`** (và `\inputfrom`, `\includefrom`): thêm vào `_INCLUDE_RE`. Thêm
  helper `_include_argument(match)` để ghép `thư mục + file` cho `\import`. File có class `subfiles` hoặc
  `standalone` chỉ góp phần body của nó, để không có hai `\begin{document}`.
- **Môi trường `comment`** bị bỏ trong `_strip_tex_comments`, thay vì được giữ như verbatim.
- **`find_root`:**
  - file bị một file khác include (ngoài các file nó tự include, tức không tính vòng lặp) thì **không phải
    root**;
  - `\documentclass` có thể nằm trong preamble được include (`main.tex` có `\include{preamble}`);
  - tên có token `main`/`ms` (như `main_rev2__3_.tex`) cũng được +20 điểm;
  - khi bằng điểm, chọn file có nhiều text reachable hơn (`reachable_chars`).
- Cập nhật markdown của mục 4, Task 2 và mục 7 cho đúng với hành vi mới.

### Sửa trong `src/13_dedup_export.ipynb` (của tôi)

- Adapter gỡ cả `\subfile`/`\import` không resolve được, như đã làm với `\input`.
- **Lỗi của fallback:** `_fb_gather` từng cắt *mọi* file được inline có `\documentclass` +
  `\begin{document}` xuống chỉ còn body. Với `2609-32908`, phần bị cắt là preamble và title của `main.tex`.
  Giờ quy tắc này chỉ áp dụng cho class `subfiles`/`standalone`.
- Thêm test `test_root_and_gathering_rules`, chạy với **cả notebook 10 lẫn fallback**. Test gồm wrapper
  `\input{main.tex}`, preamble chứa `\documentclass`, `\input{Sections/1.Intro}`, `\import`, `\subfile`,
  môi trường `comment`, và thư gửi kèm cạnh bài báo. Với notebook 10 cũ, test này hỏng (`'sub.tex' != 'wrapper.tex'`).

### Đo lại trên `test_runs/1000_versions` (291 version có TeX)

| | Trước | Sau |
|---|---|---|
| Version có độ dài text gom lệch > 10% so với `_fb_gather` | 8 | **0** (lệch lớn nhất còn 3,1%) |
| Version chọn root khác fallback | 2 | **0** (không version nào khác bị đổi root) |
| Thời gian `find_root` + `gather` của 10, cả 291 version | 19,9 s | 19,7 s |

## Việc 3: notebook 11 (commit `3dee56b`, sửa code của **Member 4**)

- **Lỗi:** `re.sub(r"---|--", " - ", tex)` cũng chạy vào bên trong công thức, biến `$a--b$` thành `$a - b$`.
  Giờ phép thay này chỉ chạy trên phần text. Helper mới `_math_segments` đọc toán từ trái sang phải giống
  `_split_math` của 13:
  - nhận `$...$`, `$$...$$`, `\(...\)`, `\[...\]` và các môi trường toán;
  - `\$` và `\\` là escape, nên `\\[3pt]` không mở công thức;
  - toán inline không vượt qua dòng trắng;
  - `$` không có dấu đóng thì được coi là text.
- **Bỏ thêm:** `\date{...}`, `\pagenumbering{...}`, `\maketitle`, `\tableofcontents`, `\and`.
- **Bóc thêm** (giống `\textbf`): `\textsc{}`, `\texttt{}`, `\textsf{}`.
- **Self-test:** thêm B16–B20 cho các điểm trên. Với bản 11 cũ, cả 5 test hỏng.
- Cập nhật bảng markdown của mục 2 và xoá output cũ của cell self-test.

## Việc 4: `build_tree` (commit `56227f6`)

Notebook 10 vẫn chưa có `build_tree`, nên tôi **không viết thay** Member 2. Tôi ghi rõ trong `README.md` (mục
Execution Guide Milestone 2) và trong cell đầu của 13 rằng cây của mọi version đang do `_fb_build_tree` của
13 dựng: `IMPLEMENTATION["build_tree"] == "fallback"`, và parser version hiện `10:mixed`. Khi 10 có
`build_tree`, 13 sẽ tự dùng mà không cần sửa gì thêm. Cây thư mục `src/` trong README giờ cũng liệt kê 10,
11 và 12.

## Việc 5: report Jupyter Book (commit `253b7e8`)

- `docs/_toc.yml`: thêm `milestone2/bibtex` (trang có sẵn của Member 3) và trang mới `milestone2/statistics`.
- `docs/milestone2/statistics.ipynb`: đọc `m2_stats.json` và `m2_benchmark.json`, rồi tính bảng và vẽ biểu đồ
  **lúc build book**, không dán ảnh tĩnh. Nội dung:
  - bảng tóm tắt; bước nào do notebook nào đảm nhận;
  - trạng thái version (`ok`/`empty_source`/`no_root`/`error`) và nguồn references (`bib_source`);
  - độ phủ version theo paper;
  - element theo kind trước/sau dedup (biểu đồ thang log kèm bảng);
  - BibTeX trước/sau;
  - thời gian, RAM peak/trung bình (kèm đường RAM theo thời gian), dung lượng output.
- `docs/milestone2/report_data.py` (theo mẫu `milestone1/report_data.py`): tìm file trong
  `REPORT_DATA_DIR`, rồi `docs/data/`, rồi `logs/` của repo. Cả hai file luôn lấy từ cùng một thư mục để
  không trộn hai lần chạy. Thiếu file thì trang **in thông báo, không crash**.
- `docs/README.md` (cần copy những file nào), `docs/intro.md` (thêm hai trang M2), tiêu đề book bỏ chữ
  "Milestone 1".
- **Kiểm chứng:** chạy notebook bằng `nbclient` trong 3 tình huống, cả 3 không lỗi:
  1. không có file nào: chỉ in thông báo;
  2. có đủ hai file, dựng từ lần chạy 900 paper: 4 biểu đồ;
  3. mặc định: đọc `logs/` của repo (lần chạy local 20.000 paper ngày 11/11, parser 13.1): 4 biểu đồ.

---

## Bảng so sánh số liệu (`test_runs/1000_versions`: 900 paper, 291 version có TeX)

### Tổng quan

| | Mốc `4e3ca2c` (nhóm) | Sau việc 2 (nhóm) | **Cuối (nhóm, 13.5)** | Fallback thuần (cuối) |
|---|---|---|---|---|
| Version ok / empty_source / no_root / error | 291 / 766 / 0 / 0 | 291 / 766 / 0 / 0 | **291 / 766 / 0 / 0** | 291 / 766 / 0 / 0 |
| Vi phạm bất biến (`check_paper`) | 0 | 0 | **0** | 0 |
| `bib_source`: bib / bibitem / missing_bbl / none | 205 / 50 / 33 / 3 | 205 / 51 / 33 / 2 | **205 / 51 / 33 / 2** | 205 / 51 / 33 / 2 |
| Node → element sau dedup | 180.926 → 155.513 | 180.576 → 155.253 | **180.542 → 155.224** | 175.648 → 150.635 |
| BibTeX trước → sau dedup | 10.509 → 9.340 | 10.560 → 9.392 | **10.560 → 9.392** | 10.577 → 9.402 |
| Thời gian 900 paper | 44,2 s | 44,0 s | **44,6 s** | 16,1 s |
| Version gom lệch > 10% so với fallback | 8 | 0 | **0** | – |
| Version chọn root khác fallback | 2 | 0 | **0** | – |

`bib_source` của bản nhóm giờ trùng hoàn toàn với fallback. Version `2609-32879` từ `none` thành `bibitem`
vì đã chọn đúng bài báo.

### Node → element theo kind

| Kind | Mốc `4e3ca2c` (nhóm) | **Cuối (nhóm)** | Fallback thuần |
|---|---|---|---|
| sentence | 142.043 → 122.093 | **141.812 → 121.944** | 136.805 → 117.316 |
| formula | 17.706 → 15.179 | **17.558 → 15.044** | 17.552 → 14.994 |
| subsection | 4.365 → 3.875 | **4.372 → 3.882** | 4.396 → 3.898 |
| figure | 4.170 → 3.789 | **4.170 → 3.789** | 4.210 → 3.822 |
| item | 3.996 → 3.150 | **3.967 → 3.121** | 3.981 → 3.128 |
| paragraph | 3.199 → 2.735 | **3.227 → 2.763** | 3.249 → 2.781 |
| section | 2.884 → 2.573 | **2.885 → 2.574** | 2.900 → 2.587 |
| itemize | 1.027 → 843 | **1.017 → 833** | 1.021 → 835 |
| subsubsection | 954 → 753 | **951 → 750** | 951 → 750 |
| document | 291 → 263 | **291 → 263** | 291 → 263 |
| abstract | 280 → 254 | **281 → 255** | 281 → 255 |
| chapter | 11 → 6 | **11 → 6** | 11 → 6 |

Việc 2 làm thay đổi 16 version. Ở cả 16 version, số node đều tiến về phía fallback. Ví dụ:
- `2609-32846`: 411 → 672 (fallback 653);
- `2609-32922`: 20 → 217 (fallback 270);
- `2609-33084`: 1.254 → 754 (fallback 738).

### 10 paper chậm nhất (bản nhóm, cuối)

`2609-32873` 3,73 s · `2609-33023` 2,84 s · `2609-32893` 1,25 s · `2609-32965` 1,25 s · `2609-32848` 0,80 s ·
`2609-33089` 0,80 s · `2609-32877` 0,76 s · `2609-32856` 0,71 s · `2609-32967` 0,67 s · `2609-33098` 0,58 s

### Test

| | Trước | Sau |
|---|---|---|
| Test offline của 13, bản nhóm và `TEAM_USE = ()` | 23 qua | **24/24 qua** (cả hai chế độ) |
| Self-test của 11 (namespace `TEAM["11_normalize"]`) | 64/64 | **69/69** |
| Test của 12 | 39/40 | **39/40**: bài còn lại là test Parquet, bị chặn trên máy |

---

## Còn tồn tại / chưa kiểm chứng

- **Notebook 10 của Member 2 chưa được push lại.** `origin/feat/latex-tree-parser` vẫn ở `fb8d516` (file
  hỏng), nên `build_tree` vẫn dùng fallback của 13. Khi bạn ấy push lại, cần merge bằng tay: bên đó file nằm
  ở `notebooks/`, bên này ở `src/`. Cần giữ bản vá tốc độ và các sửa của commit `e2a2c57`.
- **Parquet và notebook 15 chưa chạy ở local.** Windows Application Control vẫn chặn DLL của pyarrow
  (`import pyarrow.parquet` → "An Application Control policy has blocked this file"), nên dòng `Checks:` và
  schema ba bảng Parquet chưa được kiểm ở local. Cần chạy trên Colab.
- **Chưa chạy trên Colab với 20.000 paper** bằng parser `13.5`. Số liệu ở trên chỉ là 900 paper local.
  Notebook 15 trên Colab clone nhánh `m2-pipeline`, nên **phải push** 4 commit này trước thì Colab mới dùng
  bản mới.
- **`WORKERS > 1` chưa kiểm** (Windows không có `fork`). Chỉ chạy được trên Colab/Linux.
- **Chưa build cả book.** Máy có `jupyter-book` 2.1.7, trong khi book theo định dạng 1.x, và file exe cũng bị
  chặn. Trang thống kê mới chỉ được kiểm bằng cách chạy notebook qua `nbclient`. `docs/data/` chưa có
  `m2_stats.json`/`m2_benchmark.json` của lần chạy chính thức: sau lần chạy Colab cuối, cần copy hai file đó
  từ `logs/` vào.
- Bản nhóm chậm hơn fallback khoảng 2,8 lần (44,6 s so với 16,1 s trên 900 paper). Phần lớn thời gian rơi vào
  `2609-32873` và `2609-33023`. Chưa tối ưu.
- `2609-32922` vẫn lệch fallback (217 so với 270 node) dù độ dài text gom đã bằng nhau. Phần lệch nằm ở bước
  11/`build_tree`, không phải ở `gather`. Chưa điều tra.
