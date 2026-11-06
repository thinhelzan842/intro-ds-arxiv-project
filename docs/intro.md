# arXiv Scraping & Mining — Milestone 1 Report

Project report for **Introduction to Data Science** (VNU-HCMUS, Faculty of Information Technology).

This book documents **Milestone 1 — data crawling**: for the 20,000 arXiv IDs assigned to the group, find
every paper and all of its versions, download the LaTeX source of each version while keeping only the
`.tex` and `.bib` files, collect the paper metadata and the reference metadata, and measure how well and
how fast the scraper does it.

- **Code repository:** <https://github.com/thinhelzan842/intro-ds-arxiv-project> (source in `src/`,
  set-up instructions in `README.md`)
- **Testbed:** Google Colab, CPU-only runtime, data on Google Drive

## How to read this report

| Chapter | Content |
|---|---|
| [Crawling architecture](milestone1/overview.md) | the pipeline, tools and libraries, rate limits, data layout |
| [Entry discovery](milestone1/discovery.md) | finding the papers and their versions with the arXiv API |
| [Source download](milestone1/download.md) | downloading every version, keeping only `.tex`/`.bib`, resuming |
| [References](milestone1/references.md) | reference metadata from the Semantic Scholar API |
| [Scraping statistics](milestone1/statistics.ipynb) | success rates, sizes, versions, references |
| [Scraper performance](milestone1/performance.ipynb) | running time, RAM, disk — the benchmark |

Every table and figure in the last two chapters is computed from the crawl's log files when the book is
built; none of them is a pasted screenshot.

## Group and contributions

| Member | Role | Main deliverables |
|---|---|---|
| Member 1 | discovery, coordination | `00_config.ipynb`, `01_discovery.ipynb` (arXiv API, discovery checkpoints) |
| Member 2 | source download | `02_download.ipynb` (paced downloader, `.tex`/`.bib` extraction, resume) |
| Member 3 | references | `03_references.ipynb` (Semantic Scholar batch client) |
| Member 4 | monitoring, report | `04_monitor.ipynb` (RAM/disk monitor, statistics, charts) |
| all | pipeline and tests | `05_run_pipeline.ipynb`, `06_test_100_versions.ipynb`, `07_run_references.ipynb` |

## Roadmap

1. **Milestone 1 — data crawling** (this report).
2. **Milestone 2 — parsing and standardisation** of the LaTeX sources and bibliographies.
3. **Milestone 3 — citation matching** and the published dataset.
