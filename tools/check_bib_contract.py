"""Integration check: `parse_paper` of `13_dedup_export` running on top of `12_bibtex`.

    python tools/check_bib_contract.py                    # notebooks of src/, sample of data/bib_sample.json
    python tools/check_bib_contract.py --src ../other-checkout/src --tests

It needs `13_dedup_export.ipynb` and `12_bibtex.ipynb` in the same `src/` folder and the sample
downloaded by `tools/fetch_bib_sample.py`. No Jupyter is needed: the code cells are executed in one
namespace, the way `%run -i` does. What it checks:

1. no top-level name of `12_bibtex` is defined by another notebook of `src/` (they share a namespace);
2. 13 really uses the four functions of 12 (`extract_bib`, `bib_source`, `dedup_bib`, `rename_cites`);
3. for every sample paper, `parse_paper` gives the same `bibtex` rows, the same number of entries
   before and after deduplication and the same source labels as `process_paper_bib` run alone on
   the same gathered text;
4. after renaming, no element of a version cites a key that the key map of that version replaces.
   This is run twice: with `parse_paper` as it is, and with the one-line change that passes the
   key map of the version (`key_map.get(version, {})`).

Exit code 0 when 1-3 hold and 4 holds with the per-version line.
"""
import argparse
import ast
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTRACT = ("extract_bib", "bib_source", "dedup_bib", "rename_cites")
OLD_CALL = "rename_cites(normalize_math(clean_latex(expand_macros(raw))), key_map or {})"
NEW_CALL = ("rename_cites(normalize_math(clean_latex(expand_macros(raw))), "
            "key_map.get(version, {}) if key_map and all(isinstance(m, dict) for m in key_map.values()) "
            "else key_map)")


def code_cells(path):
    nb = json.loads(Path(path).read_text(encoding="utf-8"))
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] == "code":
            yield i, re.sub(r"^\s*[%!].*$", "", "".join(cell["source"]), flags=re.M)


class Shell:
    """The two things the notebooks ask of IPython: `%run -i ./x.ipynb` in the same namespace."""

    def __init__(self, ns):
        self.ns = ns

    def run_line_magic(self, name, line):
        if name != "run":
            raise ValueError(f"unsupported magic %{name}")
        run_notebook(line.replace("-i", "").strip(), self.ns)


def run_notebook(path, ns):
    for i, source in code_cells(path):
        exec(compile(source, f"{Path(path).name}[{i}]", "exec"), ns)


def top_level_names(path):
    names = set()
    for _, source in code_cells(path):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names.update(n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name))
    return names


SHARED_ON_PURPOSE = {"RUN_TEST", "rename_cites", "extract_bib", "bib_source", "dedup_bib"}


def shared_names(src):
    mine = top_level_names(src / "12_bibtex.ipynb") - SHARED_ON_PURPOSE
    clashes = {}
    for path in sorted(src.glob("*.ipynb")):
        if path.name != "12_bibtex.ipynb":
            common = sorted(mine & top_level_names(path))
            if common:
                clashes[path.name] = common
    return clashes


def ensure_metadata(pdir, arxiv_id, n_versions):
    """parse_paper reads the versions from metadata.json; the sample only has the vN/ folders."""
    path = pdir / "metadata.json"
    if not path.exists():
        path.write_text(json.dumps({"id": arxiv_id, "status": "ok", "versions": n_versions,
                                    "version_info": [{"version": v} for v in range(1, n_versions + 1)]}),
                        encoding="utf-8")
        return True
    return False


def check_sample(ns, papers, data_dir, label):
    """Run parse_paper and the standalone bibliography on every paper; returns (totals, problems)."""
    totals, problems, wrong_cites = Counter(), [], []
    key_maps = {}
    real_dedup = ns["dedup_bib"]

    def recording_dedup(by_version):
        entries, key_map = real_dedup(by_version)
        key_maps["last"] = key_map
        return entries, key_map

    ns["dedup_bib"] = recording_dedup
    started = time.perf_counter()
    try:
        for paper in papers:
            arxiv_id = paper["arxiv_id"]
            pdir = data_dir / arxiv_id.replace(".", "-").replace("/", "_")
            key_maps.pop("last", None)
            result = ns["parse_paper"](pdir)
            key_map = key_maps.get("last") or {}
            status = {r["version"]: r for r in result["versions"]}

            # the same bibliography, run alone on the same gathered text
            raws = {}
            for version, record in status.items():
                vdir = pdir / f"v{version}"
                if record["status"] in ("empty_source", "no_root"):
                    continue
                raws[version] = (vdir, ns["gather"](vdir))
            alone = ns["process_paper_bib"](arxiv_id, raws)

            rows = [{k: v for k, v in row.items() if k != "arxiv_id"} for row in alone["rows"]]
            got = [{k: v for k, v in row.items() if k != "arxiv_id"} for row in result["bibtex"]]
            key = lambda row: row["citation_key"]                       # noqa: E731
            before, after = result["counts"]["bib_entries_before"], len(result["bibtex"])
            totals.update(papers=1, versions=len(status), before=before, after=after,
                          alone_before=alone["paper_stats"]["entries_before"],
                          alone_after=alone["paper_stats"]["entries_after"],
                          renames=sum(len(m) for m in key_map.values()) if key_map else 0,
                          renames_flat=len(getattr(key_map, "flat", {})))
            totals.update(Counter("status_" + r["status"] for r in status.values()))
            totals.update(Counter("source_" + r["bib_source"] for r in status.values()))
            if (before, after) != (alone["paper_stats"]["entries_before"], alone["paper_stats"]["entries_after"]):
                problems.append(f"{arxiv_id}: entries {before}->{after} in parse_paper, "
                                f"{alone['paper_stats']['entries_before']}->{alone['paper_stats']['entries_after']} alone")
            elif sorted(got, key=key) != sorted(rows, key=key):
                problems.append(f"{arxiv_id}: bibtex rows differ from the standalone run")
            for stat in alone["version_stats"]:
                if status[stat["version"]]["bib_source"] != stat["bib_source"]:
                    problems.append(f"{arxiv_id} v{stat['version']}: source "
                                    f"{status[stat['version']]['bib_source']} != {stat['bib_source']}")
            for record in status.values():
                if record["status"] == "error":
                    problems.append(f"{arxiv_id} v{record['version']}: {record['error']}")

            # cites in the elements of each version, against the key map of that version
            content = {row["element_id"]: row["content"] for row in result["elements"]}
            in_version = {}
            for row in result["hierarchy"]:
                in_version.setdefault(row["version"], set()).add(row["element_id"])
            final_keys = {row["citation_key"] for row in result["bibtex"]}
            for version, ids in in_version.items():
                mapping = key_map.get(version, {}) if key_map else {}
                cited = set()
                for element_id in ids:
                    cited.update(ns["cited_keys"](content.get(element_id) or ""))
                raw = raws.get(version, (None, ""))[1] or ""
                expected = {mapping.get(k, k) for k in ns["cited_keys"](raw)}
                totals["cited_keys"] += len(cited)
                totals["cited_without_entry"] += len(cited - final_keys - {"*"})
                stale = sorted(cited - expected)
                if stale:
                    wrong_cites.append(f"{arxiv_id} v{version}: {stale}")
    finally:
        ns["dedup_bib"] = real_dedup
    totals["seconds"] = round(time.perf_counter() - started, 1)
    print(f"\n[{label}]")
    print(f"  papers {totals['papers']}, versions {totals['versions']}: "
          + ", ".join(f"{k[7:]} {v}" for k, v in sorted(totals.items()) if k.startswith("status_")))
    print("  source labels: " + ", ".join(f"{k[7:]} {v}" for k, v in sorted(totals.items()) if k.startswith("source_")))
    print(f"  entries before -> after dedup: {totals['before']} -> {totals['after']} in parse_paper, "
          f"{totals['alone_before']} -> {totals['alone_after']} standalone on the same text")
    print(f"  renamed keys: {totals['renames']} (version-independent: {totals['renames_flat']})")
    print(f"  cited keys in the elements: {totals['cited_keys']}, without an entry: {totals['cited_without_entry']}")
    print(f"  versions with a cite that kept a replaced key: {len(wrong_cites)}")
    for line in wrong_cites:
        print("    " + line)
    print(f"  differences from the standalone run: {len(problems)}")
    for line in problems:
        print("    " + line)
    print(f"  {totals['seconds']} s")
    return totals, problems, wrong_cites


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", type=Path, default=REPO / "src", help="folder with 13_dedup_export and 12_bibtex")
    ap.add_argument("--data", type=Path, default=REPO / "data" / "raw", help="folder with the sample papers")
    ap.add_argument("--sample", type=Path, default=REPO / "data" / "bib_sample.json")
    ap.add_argument("--tests", action="store_true", help="also run the offline tests of 12 and 13 (RUN_TEST)")
    args = ap.parse_args()
    src, data_dir = args.src.resolve(), args.data.resolve()
    for name in ("13_dedup_export.ipynb", "12_bibtex.ipynb", "00_config.ipynb"):
        if not (src / name).is_file():
            raise SystemExit(f"{src / name} not found: this check needs the Dedup branch merged "
                             f"(or --src pointing at a checkout that has both notebooks)")
    if not args.sample.is_file():
        raise SystemExit(f"{args.sample} not found: run tools/fetch_bib_sample.py first")
    papers = json.loads(args.sample.read_text(encoding="utf-8"))["papers"]
    created = sum(ensure_metadata(data_dir / p["arxiv_id"].replace(".", "-"), p["arxiv_id"], len(p["versions"]))
                  for p in papers)
    if created:
        print(f"wrote a minimal metadata.json for {created} sample papers")

    failed = False
    clashes = shared_names(src)
    print("1. names of 12_bibtex defined by another notebook:", clashes or "none")
    failed |= bool(clashes)

    os.chdir(src)                           # the notebooks use relative paths
    ns = {"__name__": "__main__", "RUN_TEST": args.tests}
    ns["get_ipython"] = lambda: Shell(ns)
    try:
        run_notebook(src / "13_dedup_export.ipynb", ns)
    except AssertionError as err:           # raised by the test cell, after every function is defined
        print(f"offline tests failed with 12_bibtex loaded: {err}")
        failed = True
    used = {name: ns["IMPLEMENTATION"].get(name) for name in CONTRACT}
    print("2. implementation used by 13:", used, "| parser", ns["PARSER_VERSION"])
    failed |= any(source != "12_bibtex" for source in used.values())

    print("3-4. parse_paper on the sample")
    _, problems_a, stale_a = check_sample(ns, papers, data_dir, "parse_paper as it is (whole key map)")
    cell = next(source for _, source in code_cells(src / "13_dedup_export.ipynb") if "def parse_paper(" in source)
    if cell.count(OLD_CALL) == 1:
        exec(compile(cell.replace(OLD_CALL, NEW_CALL), "13_dedup_export[parse_paper, per-version key map]", "exec"), ns)
        _, problems_b, stale_b = check_sample(ns, papers, data_dir, "parse_paper with key_map.get(version, {})")
        failed |= bool(problems_b or stale_b)
    else:
        print("\nparse_paper no longer contains the flat call: the per-version line is probably merged")
        failed |= bool(stale_a)
    failed |= bool(problems_a)
    print("\nRESULT:", "FAILED" if failed else "OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
