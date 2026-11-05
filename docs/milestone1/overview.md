# Crawling architecture

*Author: La Anh Hào · code: `src/05_run_pipeline.ipynb`*

## Pipeline

The crawl is one notebook, `src/05_run_pipeline.ipynb`, run on Google Colab (CPU). It loads the
notebooks of the four members with `%run -i` and runs three stages:

```text
[setup]      clone/update the repository, install src/requirements.txt, mount Google Drive,
             read S2_API_KEY (Colab Secrets or .env), start the RAM monitor
   │
[1] discovery (01_discovery)              arXiv API, 100 IDs per request, one request every 3 s
   │   20,000 assigned IDs → which papers exist, how many versions, metadata of every version
   │   checkpoint after every batch → state/discovery_batches/, state/discovery_manifest.json
   ▼
[2] sources (02_download)  ─────────────  main thread, arXiv /src, one request every 3 s
   │   every version vN of every paper → raw archive on the local disk (/tmp)
   │     → 2 worker threads: unpack, keep only .tex/.bib, copy to Drive, write a receipt
   │
   └── references (03_references) ──────  background thread, Semantic Scholar batch API
           100 papers per request → references.json in the paper folder
   ▼
[3] report (04_monitor + 05)
       logs/papers.csv, logs/benchmark.json (all sessions), logs/performance.json, logs/figures/
```

The arXiv limit and the Semantic Scholar limit are independent, so the references are fetched while
the downloader waits for arXiv. Every stage resumes from what is saved on Drive: after a Colab disconnect
the notebook is simply run again (see *Resuming after a disconnect* in [Source download](download.md)).

`src/06_test_100_versions.ipynb` runs the same pipeline on the first 100 source versions only, in a
separate folder, and checks the result; it was used to test every change before the full crawl.

## Tools and libraries

| Purpose | Tool |
|---|---|
| entry discovery, paper metadata | arXiv API through the `arxiv` library 4.x (`Client.results(Search(id_list=...))`) |
| LaTeX sources | `requests` on the source mirror `https://export.arxiv.org/src/{id}vN` |
| unpacking | Python standard library: `tarfile`, `zipfile`, `gzip`, `bz2`, `lzma` |
| reference metadata | Semantic Scholar Graph API, `POST /graph/v1/paper/batch` (with an API key) |
| concurrency | `concurrent.futures.ThreadPoolExecutor` (extraction workers, reference thread) |
| monitoring | `psutil` (RSS), wall clock, disk usage from the receipts (or a `du`-style walk with `MEASURE_DISK = True`) |
| progress | `tqdm` bars (discovery, papers, current file and MB left) |
| analysis, figures | `pandas`, `matplotlib` |

OAI-PMH was not needed: the arXiv API already returns every version's metadata when it is asked for the
versioned IDs (see [Entry discovery](discovery.md)).

## Rate limits and politeness

- **arXiv (API and `/src/`)**: one connection, at least **3 s** between requests (`ARXIV_DELAY = 3.0`),
  retries included, and a descriptive `User-Agent`. Automated downloads go to `export.arxiv.org`, never to
  `arxiv.org`. On HTTP 429, discovery waits 30 s, doubling each time (see [Entry discovery](discovery.md));
  the source downloader does not retry a refused version at once but moves on and asks for it again later,
  honouring a `Retry-After` from arXiv (see [Source download](download.md)).
- **Semantic Scholar**: an API key, at most one request every `S2_DELAY` seconds, exponential back-off on
  HTTP 429. Even with the key, a large share of requests is refused with 429 at any spacing (see
  [References](references.md)), so the client sends few, large requests: batches of 100 papers, about 200
  requests for the whole range.

## Data layout

The corpus follows the convention suggested by the lab book: one folder per paper named after its ID
with the dot replaced by a hyphen, containing the `.tex` and `.bib` files of every version and the
metadata of the paper and of its references.

```text
MyDrive/arxiv-project/
├── data/raw/
│   └── 2609-32834/
│       ├── metadata.json        paper metadata, one record per version (title, authors, dates, venue, ...)
│       ├── references.json      every reference found by Semantic Scholar (not only arXiv ones)
│       ├── v1/                  .tex and .bib files of version 1, original folder structure kept
│       └── v2/                  ... one folder per version; empty if the version is PDF-only
├── state/                       resume state: discovery manifest and batches, download receipts, errors
└── logs/                        papers.csv, references.csv, benchmark.json, performance.json, figures/
```

A version without LaTeX source (PDF or Word only) keeps an **empty** `vN/` folder and an `empty_source`
receipt, so the paper stays in the corpus, as the lab book asks.

### Table `papers`

| Column | Type | Description |
| :--- | :--- | :--- |
| `arxiv_id` | string (PK) | base arXiv identifier (e.g. `2310.12345`) |
| `title` | string | paper title |
| `authors` | list of strings | author names |
| `submission_date` | string (ISO) | date of the first version (v1) |
| `revised_dates` | list of strings | dates of the later versions |
| `venue` | string (nullable) | journal reference, if any |

`metadata.json` keeps its own field names (`id`, `submitted`, `revised`) and adds `status`, `versions` and
`version_info` (title, authors, abstract, date, `journal_ref`, DOI, comment and categories of every version).
`papers_rows()` in `01_discovery.ipynb` turns the saved files into the rows of this table.

### Table `references`

| Column | Type | Description |
| :--- | :--- | :--- |
| `arxiv_id` | string (FK) | citing paper |
| `ref_arxiv_id` | string | arXiv identifier of the cited paper |
| `ref_title` | string | title of the cited work |
| `ref_authors` | list of strings | authors of the cited work |
| `ref_submission_date` | string | submission date of the cited work |
| `ref_s2_id` | string | Semantic Scholar paper ID |

Only references that carry an arXiv ID become rows of `references` (`references_rows()` in
`03_references.ipynb`); all of them stay in `references.json`.
