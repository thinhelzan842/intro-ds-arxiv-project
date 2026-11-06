"""Load the crawl results that the report pages are built from.

The files are copied from the crawl's `logs/` folder on Google Drive
(`MyDrive/arxiv-project/logs/`) into `docs/data/`; see `docs/README.md`.
Every table and figure of the report is computed from them when the book is built.
Set REPORT_DATA_DIR to read them from another folder.
"""

import json
import os
from pathlib import Path

import pandas as pd

DATA_DIR = Path(os.environ.get("REPORT_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
REQUIRED = ("benchmark.json", "benchmark_sessions.jsonl", "performance.json", "papers.csv")
MB = 1024 * 1024
ARXIV_DELAY = 3.0   # seconds between arXiv requests during the crawl (00_config.ARXIV_DELAY)


def check():
    """Stop the build with a clear message instead of publishing figures of missing data."""
    missing = [name for name in REQUIRED if not (DATA_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing in {DATA_DIR}: {', '.join(missing)}. Copy them from the crawl's "
            "MyDrive/arxiv-project/logs/ folder (see docs/README.md).")


def benchmark():
    """logs/benchmark.json: the Milestone 1 metrics over every Colab session."""
    return json.loads((DATA_DIR / "benchmark.json").read_text(encoding="utf-8"))


def sessions():
    """logs/benchmark_sessions.jsonl: one row per Colab session."""
    rows = [json.loads(line) for line in
            (DATA_DIR / "benchmark_sessions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    frame = pd.DataFrame(rows)
    for column in ("start", "end"):
        frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame


def performance():
    """logs/performance.json (04_monitor format), including the RAM time series."""
    return json.loads((DATA_DIR / "performance.json").read_text(encoding="utf-8"))


def papers():
    """logs/papers.csv: one row per assigned ID, with an `outcome` column added.

    outcome: not_on_arxiv (no version exists), incomplete (a version is still missing),
    latex (every version has LaTeX), pdf_only (no version has LaTeX), mixed (some do).
    """
    frame = pd.read_csv(DATA_DIR / "papers.csv", dtype={"id": str})
    for column in ("versions", "versions_ok", "size_before", "size_after", "n_refs", "n_arxiv_refs", "seconds"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    complete = frame["error"].fillna("") != "unprocessed source versions"

    def outcome(row, done):
        if row.versions == 0:
            return "not_on_arxiv"
        if not done:
            return "incomplete"
        if row.versions_ok == row.versions:
            return "latex"
        return "pdf_only" if row.versions_ok == 0 else "mixed"

    frame["outcome"] = [outcome(row, done) for row, done in zip(frame.itertuples(), complete)]
    return frame
