"""Load the parsing results (Milestone 2) that the report pages are built from.

`src/15_run_parsing.ipynb` writes two files to `logs/` at the end of every run (on Colab:
`MyDrive/arxiv-project/logs/`):

- `m2_stats.json`: version status, parse success rate, version coverage, elements and BibTeX entries
  before and after deduplication;
- `m2_benchmark.json`: wall time, time per paper, RAM, output size, over all Colab sessions.

They are read from the first folder that holds at least one of them: `REPORT_DATA_DIR` if set, else
`docs/data/` (where the Milestone 1 files are copied, see `docs/README.md`), else the code repository's
`logs/`. Both files always come from the same folder, so the page never mixes two runs.

Unlike Milestone 1, a missing file does not stop the build: the page says which file is missing and shows
what it can, so the book still builds before the full run on Colab.
"""

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = {"stats": "m2_stats.json", "benchmark": "m2_benchmark.json"}
MB = 1024 * 1024
STATUSES = ("ok", "empty_source", "no_root", "error")


def _folders():
    if os.environ.get("REPORT_DATA_DIR"):
        return [Path(os.environ["REPORT_DATA_DIR"])]
    return [HERE.parent / "data", HERE.parent.parent / "logs"]


def _data_dir():
    """The first folder with at least one of the two files, else None."""
    for folder in _folders():
        if any((folder / name).is_file() for name in FILES.values()):
            return folder
    return None


DATA_DIR = _data_dir()


def _load(name):
    """The JSON document of FILES[name], or None if it is missing or unreadable."""
    if DATA_DIR is None or not (DATA_DIR / FILES[name]).is_file():
        return None
    try:
        document = json.loads((DATA_DIR / FILES[name]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        print(f"{FILES[name]} could not be read: {type(err).__name__}: {err}")
        return None
    return document if isinstance(document, dict) else None


def stats():
    """logs/m2_stats.json, or None."""
    return _load("stats")


def benchmark():
    """logs/m2_benchmark.json, or None."""
    return _load("benchmark")


def missing_note(name):
    """Markdown for a section whose file is not available."""
    where = (f"`{DATA_DIR}`" if DATA_DIR else
             " or ".join(f"`{folder}`" for folder in _folders()))
    return (f"*`{FILES[name]}` is not available yet (looked in {where}). It is written by "
            f"`src/15_run_parsing.ipynb`; copy it from the run's `logs/` folder into `docs/data/` "
            f"and build the book again.*")


def source_note(stats_doc, bench_doc):
    """Markdown naming the files this page was built from."""
    if DATA_DIR is None:
        return ("**No parsing results yet.** Neither `m2_stats.json` nor `m2_benchmark.json` was found in "
                + " or ".join(f"`{folder}`" for folder in _folders())
                + ". Every section below says what it will show once they are copied.")
    lines = [f"Data read from `{DATA_DIR}`:"]
    for name, document in (("stats", stats_doc), ("benchmark", bench_doc)):
        if document is None:
            lines.append(f"- `{FILES[name]}`: missing")
            continue
        when = document.get("computed_at") or document.get("end") or "?"
        lines.append(f"- `{FILES[name]}`: parser `{document.get('parser_version', '?')}`, written {when}")
    return "\n".join(lines)
