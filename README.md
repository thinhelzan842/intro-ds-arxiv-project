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
