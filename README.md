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
├── 02_download.ipynb        # Member 2: Source archive download, unpacking & figure pruning
├── 03_references.ipynb      # Member 3: Citation graph fetching (Semantic Scholar Graph API)
├── 04_monitor.ipynb         # Member 4: Performance monitoring, metrics & statistics helpers
└── 05_run_pipeline.ipynb    # End-to-end execution pipeline with auto-resume capability
```

### Running Individual Notebooks
Each notebook includes a self-contained offline test (`RUN_TEST = True`):
* Open any notebook (`01_discovery.ipynb`, `03_references.ipynb`, `04_monitor.ipynb`) in JupyterLab / VS Code / Colab and run all cells.

### Running on Google Colab
When running on Google Colab, `00_config.ipynb` automatically mounts Google Drive (`/content/drive/MyDrive/arxiv-project`) so that data and execution logs persist across session disconnects.

For the source-download stage, open `src/02_download.ipynb` from branch `VA`
in a **CPU** runtime. Cell 1 mounts Drive, clones or updates branch `VA`,
installs dependencies, and creates the state directory on Drive. No Drive
folder needs to be created manually. `ARXIV_CONTACT` is optional: without it,
the notebook uses the descriptive User-Agent
`HCMUS-IntroDS-arXiv-source/1.0 (HCMUS course project)`. If you set
`ARXIV_CONTACT` to an email address, that address is included in the
User-Agent. Use the notebook under `src/`; the root
`arxiv_colab_2_cells.ipynb` is not the maintained Colab runner.

Cell 2 runs the full assigned set of 20,000 IDs. It uses
`src/01_discovery.ipynb` to resolve them when the Drive manifest is missing;
subsequent runs reuse the manifest and retry unresolved discovery IDs. For a
one-paper smoke test, run `src.download` with a small manifest separately
instead of running Cell 2.

Run Cell 2 again after a disconnect. It verifies completed versions using
their SHA-256 receipts, prints paper and version completion percentages at
startup and periodically, and continues with unfinished versions. The output
is under `MyDrive/arxiv-project/data/raw/<yymm-id>/vN/`; the manifest is at
`MyDrive/arxiv-project/state/discovery_manifest.json`; receipts, errors and
`run_summary.json`, `run_history.jsonl` and `papers.csv` are under
`MyDrive/arxiv-project/state/download/`. The CSV uses the columns expected
by `04_monitor.ipynb` for source sizes and version counts; reference columns
stay empty until the group's reference stage is joined.
Keep this Drive directory across Colab sessions and use only one downloader
instance for it at a time.

The downloader requests each version from `export.arxiv.org/src/{id}vN` with
at least 3 seconds between requests. arXiv sends the entire archive over the
network; the extractor writes only `.tex`, `.bib`, `.bbl`, `.sty` and `.cls`
files, preserving the TeX bytes. A PDF/Word-only version gets an empty `vN/`
folder and an `empty_source` receipt. `run_summary.json` reports this download
stage's elapsed time, process RSS samples and an **estimate** of peak project
disk usage; the group's end-to-end Colab benchmark remains the source for the
Milestone 1 performance report. Do not remove benchmark evidence before the
report figures and tables have been generated.

For a local or precomputed discovery manifest, use:

```bash
python -m src.download --manifest /path/to/discovery_manifest.json \
  --output /path/to/persistent/data/raw \
  --state /path/to/persistent/state/download \
  --user-agent "HCMUS-IntroDS-arXiv-source/1.0 (HCMUS course project)"
```

The manifest accepts `{"papers": [{"id": "2603.20580", "versions": 1,
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
