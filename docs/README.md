# Milestone 1 report (Jupyter Book)

The report is a Jupyter Book 1.x. Its tables and figures are computed from the crawl's log files when the
book is built (`execute_notebooks: force`), as the lab book requires; nothing is a pasted screenshot.

## 1. Put the crawl results in `data/`

Copy these four files from the crawl's Google Drive folder `MyDrive/arxiv-project/logs/` into `data/`
(replace the sample `papers.csv` and `performance.json` that are there now):

| File | Used for |
|---|---|
| `benchmark.json` | every Milestone 1 metric, over all Colab sessions |
| `benchmark_sessions.jsonl` | the per-session table (wall time, RAM, disk) |
| `performance.json` | the RAM-over-time chart (`ram_timeseries`) |
| `papers.csv` | per-paper statistics: versions, sizes, references, times |

If one of them is missing, the notebooks stop with a message naming it, and the build (run with `-W`,
as the workflow does) fails instead of publishing a broken page. The files are rewritten after every run of `src/05_run_pipeline.ipynb`, so copy them after
the last session of the crawl.

## 2. Build locally

```bash
pip install -r requirements.txt     # jupyter-book 1.x (version 2 uses a different format)
jupyter-book build . --all -W -n --keep-going   # -W: any error fails the build
```

Open `_build/html/index.html`. To build from another folder of log files without copying them:
`REPORT_DATA_DIR=/path/to/logs jupyter-book build . --all -W -n --keep-going`.

## 3. Publish on GitHub Pages (separate report repository)

The lab book asks for the report in a public repository of its own, hosted on that repository's GitHub
Pages. The **contents of this `docs/` folder become the root** of the report repository:

```text
<report-repo>/
├── .github/workflows/deploy-book.yml   builds the book and deploys it on every push to main
├── _config.yml
├── _toc.yml
├── requirements.txt
├── intro.md
├── .gitignore                          ignores _build/
├── data/                               benchmark.json, benchmark_sessions.jsonl, performance.json, papers.csv
└── milestone1/
    ├── overview.md
    ├── discovery.md
    ├── download.md
    ├── references.md
    ├── statistics.ipynb
    ├── performance.ipynb
    └── report_data.py                  loads data/ for the two notebooks
```

Steps:

1. Copy everything above into the report repository (do not copy `_build/` or this `README.md`).
2. On GitHub: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Push to `main`. The workflow installs `requirements.txt`, runs `jupyter-book build . -W` (which
   executes the notebooks and fails on any error) and publishes `_build/html`. The address is shown in the workflow run and under
   Settings → Pages (usually `https://<user>.github.io/<report-repo>/`).
4. Submit on Moodle: the link to the code repository and the link to this report.
