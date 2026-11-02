# 📚 arXiv Paper Corpus & Reference Matching Pipeline
> **Course:** Introduction to Data Science (HCMUS)  
> **Project:** arXiv Data Mining & Matching Pipeline

---

## 📌 Project Overview
This repository contains the complete codebase and pipeline for our **Introduction to Data Science** project at VNU-HCMUS. The project processes a large corpus of arXiv papers across three consecutive milestones:

1. **Milestone 1 — Data Crawling:** Automated discovery of assigned arXiv paper IDs, retrieval of multi-version LaTeX source packages, figure pruning, and citation graph scraping via Semantic Scholar.
2. **Milestone 2 — Hierarchical Parsing & Standardization:** Parsing LaTeX content into structured AST trees, standardizing bibliography items into BibTeX, and cross-revision deduplication.
3. **Milestone 3 — Citation Matching Pipeline:** Machine learning models predicting citation links evaluated using **MRR (Mean Reciprocal Rank)**, published as a Hugging Face Dataset.

---

## 🔗 Important Links
* **Jupyter Book Report (GitHub Pages):** [View Milestone 1 Report](https://your-group-username.github.io/repo-name)
* **Hugging Face Dataset:** [Hugging Face Dataset Repo](https://huggingface.co/datasets/your-username/dataset-name)
* **Course Lab Book:** [HCMUS Intro DS Lab Book](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/crawling/)

---

## 🛠️ Environment Setup

### 1. Prerequisites
* **Python:** 3.10 or 3.11 recommended
* **Hardware:** Tested on Google Colab (CPU-only) and local environments

### 2. Installation
Clone the repository and install required dependencies:
```bash
git clone https://github.com/thinhelzan842/intro-ds-arxiv-project.git
cd intro-ds-arxiv-project
pip install -r src/requirements.txt
```

---

## 🚀 Execution Guide (Milestone 1)

The pipeline is organized into modular notebooks inside `src/`, linked seamlessly via `%run`:

```text
src/
├── 00_config.ipynb          # Shared configurations, ID ranges, rate limits & logging helpers
├── 01_discovery.ipynb       # Member 1: Paper entry discovery & metadata extraction (arXiv API)
├── 02_download.ipynb        # Member 2: Source download, keeps only .tex/.bib (pipelined, resumable)
├── 03_references.ipynb      # Member 3: Citation graph fetching (Semantic Scholar Graph API)
├── 04_monitor.ipynb         # Member 4: Performance monitoring, metrics & statistics helpers
├── 05_run_pipeline.ipynb    # End-to-end execution pipeline with auto-resume capability
├── 06_test_100_versions.ipynb   # Test: real pipeline on the first 100 source versions (~5 min)
└── 07_run_references.ipynb  # Optional: references on a teammate's Colab, exported as one zip
```

`06_test_100_versions.ipynb` runs `05_run_pipeline.ipynb` with
`TEST_VERSIONS = 100`: only the first assigned IDs (up to 100 source
versions), written to `test_runs/100_versions/` so the real crawl is not
touched. It then checks that every version was processed, that only `.tex`/`.bib`
were stored and that a second run sends no request, and prints the timing,
size savings and an estimate for all 20,000 IDs. It also fetches the references
of those papers and checks that each has a final `references.json`.
`FRESH_RUN = True` (default) deletes the previous test folder first, so every run
measures the speed from scratch; set it to `False` to resume an interrupted test.

### Running Individual Notebooks
Notebooks 01–04 only define functions and their tests (`RUN_TEST = True` when
opened on their own); none of them starts the crawl. The downloader's 26 offline
tests are in `02_download.ipynb`. Open the notebooks (`01_discovery.ipynb`, `03_references.ipynb`,
`04_monitor.ipynb`) in JupyterLab / VS Code / Colab to run their quick tests.

### Running on Google Colab
When running on Google Colab, `00_config.ipynb` automatically mounts Google Drive (`/content/drive/MyDrive/arxiv-project`) so that data and execution logs persist across session disconnects.

To run the crawl, open **`src/05_run_pipeline.ipynb`** from branch `VA` in a
**CPU** runtime and run all cells. Its first cell clones or updates branch `VA`,
installs dependencies and moves into `src/`; `00_config.ipynb` mounts Drive. No
Drive folder needs to be created manually. `05_run_pipeline.ipynb` loads
notebooks 00–04 with `%run -i` (`RUN_TEST = False`) and then:

1. **Discovery** (`discover_all()` from `01_discovery.ipynb`): each completed
   batch of up to 100 IDs is saved under
   `MyDrive/arxiv-project/state/discovery_batches/` and the result in
   `state/discovery_manifest.json`. If a batch still fails after retries
   (including HTTP 429), the run stops and a later run reuses completed batches
   and retries only unresolved IDs.
2. **Sources and references at the same time:** `download_sources(...)` from
   `02_download.ipynb` (arXiv, one connection, `ARXIV_DELAY` apart, at least 3 s)
   in the main thread, and `crawl_references` from `03_references.ipynb` (Semantic
   Scholar batch endpoint, 100 papers per request) in one background thread. The
   two rate limits are separate, and the references finish long before the
   download.
3. **Report and benchmark:** if `references_export.zip` is in
   `MyDrive/arxiv-project/`, it is imported first. `logs/papers.csv` is rebuilt
   from the download log plus the reference counts. Each session appends its
   wall time, RAM and disk to `logs/benchmark_sessions.jsonl` (RAM samples every
   5 s to `logs/ram_timeseries.csv`), and `logs/benchmark.json` is recomputed
   over all sessions with the lab book's metrics (success rate, sizes,
   references per paper, reference success rate, time per paper, discovery
   time, peak/average RAM, maximum disk incl. temporary archives, final output
   size). `logs/performance.json` is written in `04_monitor`'s format from the
   same numbers, including `ram_timeseries` for the RAM plot, and the four
   `04_monitor` charts are saved as PNG in `logs/figures/` (RAM usage, size
   before/after, versions per paper, references per paper).

**Optional: references on a second account.** Set `RUN_REFERENCES = False` in 05 and a teammate opens
`src/07_run_references.ipynb` on their own Colab, with their own `S2_API_KEY`,
at any time: it needs neither the sources nor the discovery (without a manifest
it queries all 20,000 IDs; missing ones come back `not_found`). Results go to
`MyDrive/arxiv-project/references_run/`, it resumes after a disconnect, and its
last cell writes `references_export.zip`. Copy that file into the main
`MyDrive/arxiv-project/` folder of the person running 05; the 05 report imports
it (an `ok` result is never replaced by an `error`).

**Progress bars** (05 and the 06 test): *Discovery* shows the IDs checked out of
all assigned IDs with the papers and versions found; *Papers* shows the papers
done out of every discovered paper, with versions, MB downloaded and the ETA;
the bar below it shows the file being downloaded (`<id>vN`), its size and the
MB left. They use `tqdm` (preinstalled on Colab; listed in `src/requirements.txt`).

`RUN_DISCOVERY`, `RUN_DOWNLOAD` and `RUN_REFERENCES` in the setup cell turn
stages on or off. `ARXIV_CONTACT` is optional: if set to an email address, it is
appended to the `USER_AGENT` from `00_config.ipynb`. Use the notebooks under
`src/`; the root `arxiv_colab_2_cells.ipynb` is not the maintained Colab runner.
Expect about `ARXIV_DELAY` (3 s, the lab-book minimum) per source version:
about 18–23 hours for ~22,000 versions, so 2–3 Colab sessions.

**API key.** Copy `.env.example` to `.env` and set `S2_API_KEY` (and optionally
`ARXIV_CONTACT`). `00_config.ipynb` reads `.env` from the repo root when run
locally, or from `MyDrive/arxiv-project/.env` on Colab (a fresh clone has no
`.env`); Colab Secrets also work. Variables already set in the environment win.
`.env` is git-ignored: never commit a real key.

After a disconnect, run all cells of `05_run_pipeline.ipynb` again. The
downloader reads the `receipts.jsonl` index once, checks the saved files by size
(`DOWNLOAD_VERIFY = "sha256"` re-hashes them instead), prints paper and
version completion percentages at startup and periodically, and continues with
unfinished versions. The
output is under `MyDrive/arxiv-project/data/raw/<yymm-id>/vN/`; receipts,
errors, `run_summary.json`, `run_history.jsonl` and the download `papers.csv`
are under `MyDrive/arxiv-project/state/download/`.
Keep this Drive directory across Colab sessions and use only one downloader
instance for it at a time.

The downloader requests each version from `export.arxiv.org/src/{id}vN` on one
connection with at least 3 seconds between requests. arXiv sends the entire
archive over the network; it is saved to local runtime disk, and the extractor
writes **only `.tex` and `.bib`** files to Drive, preserving the TeX bytes.
Extraction and Drive writes run in `DOWNLOAD_WORKERS` background threads, so
they overlap the 3-second wait instead of adding to it. Files other than
`.tex`/`.bib` left by older runs (`.bbl`, `.sty`, `.cls`) are deleted on resume
without new requests. A PDF/Word-only version gets an empty `vN/` folder and an
`empty_source` receipt. `run_summary.json` reports this download stage's
elapsed time, process RSS samples and an **estimate** of peak project disk
usage; the group's end-to-end Colab benchmark remains the source for the
Milestone 1 performance report. Do not remove benchmark evidence before the
report figures and tables have been generated.

A manifest accepts `{"papers": [{"id": "2603.20580", "versions": 1,
"status": "ok"}]}` or a list with `arxiv_id` and `version_count`.

---

## 📊 Performance Monitoring & Auditing
The pipeline implements an auditable profiling system (`src/04_monitor.ipynb`):
* **RAM Sampling:** Monitored via a background daemon thread utilizing `psutil` (capturing peak and average RSS memory).
* **Disk Footprint:** Storage tracked via recursive byte counting before and after figure deletion.
* **Execution Time:** Wall-clock time recorded end-to-end and broken down by sub-stages (`discovery`, `download`, `references`).
* **Logs Generated:**
  * `logs/papers.csv`: Per-paper status, versions, sizes before/after pruning, reference counts, and elapsed time.
  * `logs/references.csv`: Detailed call log for each Semantic Scholar request.
  * `logs/performance.json`: Auditable summary of peak/avg RAM, max/final disk usage, and stage durations.

---

## 📁 Repository Structure
```text
├── data/                 # Local data working directory (raw corpus: <id>/vN/*.tex)
├── docs/                 # Jupyter Book report source files & dynamic evaluation notebooks
│   ├── _config.yml       # Jupyter Book configuration (execute_notebooks: force)
│   ├── _toc.yml          # Table of contents
│   ├── milestone1/       # Milestone 1 chapters (overview, statistics, performance)
│   └── data/             # Summarized datasets for Jupyter Book compilation
├── logs/                 # Execution logs (papers.csv, references.csv, performance.json)
├── src/                  # Pipeline notebooks & requirements
│   ├── 00_config.ipynb
│   ├── 01_discovery.ipynb
│   ├── 03_references.ipynb
│   ├── 04_monitor.ipynb
│   └── requirements.txt
└── README.md             # Project documentation
```
