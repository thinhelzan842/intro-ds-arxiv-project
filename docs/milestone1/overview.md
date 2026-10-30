# Milestone 1: Data Crawling Architecture

## 1. Objectives & Workflow
Milestone 1 establishes the ground-truth corpus for subsequent parsing and modeling milestones. Given an assigned range of arXiv IDs (20,000 IDs across group members), the pipeline performs:
1. **Entry Discovery:** Querying the arXiv HTTP API to identify paper existence and total revision counts ($v1, v2, \dots$).
2. **Source Retrieval:** Fetching full TeX source archives per revision from mirror `export.arxiv.org/src/{id}vN`.
3. **Figure Pruning:** Unpacking archives, stripping binary figures (`.png`, `.jpg`, `.pdf`, `.eps`), while strictly preserving `\includegraphics` markup in `.tex` files.
4. **Citation Extraction:** Querying Semantic Scholar Graph API for outbound citations and retaining arXiv-indexed references.

## 2. Rate Limits & Compliance
* **arXiv API & Mirrors:** At least **3 seconds** between consecutive calls, single connection, descriptive `User-Agent`.
* **Semantic Scholar:** **1 request/second** pacing with exponential backoff on HTTP 429 status codes.
* **Parallel Optimization:** Because arXiv and Semantic Scholar have independent rate limits, references are scraped concurrently in a dedicated background thread pool while sources download.

## 3. Data Schema
The crawl produces two primary relational tables:

### Table `papers`
| Column | Type | Description |
| :--- | :--- | :--- |
| `arxiv_id` | string (PK) | Base arXiv paper identifier (e.g. `2310.12345`) |
| `title` | string | Paper title |
| `authors` | list of strings | List of author names |
| `submission_date` | string (ISO) | Date/time of original $v1$ submission |
| `revised_dates` | list of strings | Timestamps of subsequent version revisions |
| `venue` | string (nullable) | Published venue or journal reference |

### Table `references`
| Column | Type | Description |
| :--- | :--- | :--- |
| `arxiv_id` | string (FK) | Identifier of citing paper |
| `ref_arxiv_id` | string (PK) | arXiv identifier of cited paper |
| `ref_title` | string | Title of cited work |
| `ref_authors` | list of strings | Authors of cited work |
| `ref_submission_date` | string | Submission date of cited work |
| `ref_s2_id` | string | Semantic Scholar paper ID |
