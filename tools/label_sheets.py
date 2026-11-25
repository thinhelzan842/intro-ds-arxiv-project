"""Manual labelling helper (Milestone 3): write the two sheets of a paper, check the filled files.

Reads data/m3/{entries,refs,pubs}.parquet (src/20_m3_data.ipynb). While data/m3/ is not built, it reads
the M2 and M1 files of the named papers instead (data/parsed/<fid>.json, data/raw/<fid>/references.json).
Never reads the automatic labels.

    make_sheets(ROOT, labeler="TV4")           # picks 5 papers of the member (needs data/m3) -> labels/sheets/
    make_sheets(ROOT, "TV4", papers=[...])     # or the papers you name ("2603.20581", ...)
    check_labels(ROOT, "TV4")                  # checks labels/manual/<fid>.csv
"""

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

ROOT = "/content/drive/MyDrive/arxiv-project"   # the shared project folder
LABEL_COLUMNS = ["arxiv_id", "citation_key", "ref_arxiv_id", "confidence", "note", "labeler"]
_CITE_RE = re.compile(r"\\[A-Za-z]*cite[A-Za-z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}")


def _from_json(root, papers):
    """entries, refs, pubs of the named papers from the M2 and M1 files (the columns this helper uses)."""
    entries, refs, pubs = [], [], []
    for arxiv_id in papers:
        fid = arxiv_id.replace(".", "-")
        parsed = Path(root) / "data" / "parsed" / f"{fid}.json"
        saved = Path(root) / "data" / "raw" / fid / "references.json"
        if not parsed.is_file() or not saved.is_file():
            print(f"{arxiv_id}: no parsed file or no references.json")
            continue
        doc = json.loads(parsed.read_text(encoding="utf-8"))
        cited = {}                                       # citation key -> first sentence that cites it
        for sentence in doc["elements"]["content"]:
            for group in _CITE_RE.findall(_text(sentence)):
                for key in group.split(","):
                    cited.setdefault(key.strip(), sentence)
        bib = doc["bibtex"]
        for i, key in enumerate(bib["citation_key"]):
            entries.append({"arxiv_id": arxiv_id, "citation_key": key, "position": i,
                            "context": [cited[key]] if key in cited else [],
                            **{c: bib[c][i] for c in ("title", "authors", "year", "journal", "doi", "url")}})
        seen = set()
        for i, ref in enumerate(json.loads(saved.read_text(encoding="utf-8"))["references"]):
            ref_id = ref.get("arxiv_id")
            if ref_id and ref_id not in seen:
                seen.add(ref_id)
                refs.append({"arxiv_id": arxiv_id, "ref_arxiv_id": ref_id, "ref_title": ref.get("title"),
                             "ref_authors": ref.get("authors") or [], "ref_year": ref.get("year"),
                             "ref_position": i})
        # Left empty: a carried-over file still says 13.7 although the paper counts as 13.8 (see 20), and
        # validate_labels() of 21 rejects another version. An empty cell is accepted.
        pubs.append({"arxiv_id": arxiv_id, "parser_version": ""})
    frames = (pd.DataFrame(entries, columns=["arxiv_id", "citation_key", "position", "context", "title",
                                             "authors", "year", "journal", "doi", "url"]),
              pd.DataFrame(refs, columns=["arxiv_id", "ref_arxiv_id", "ref_title", "ref_authors", "ref_year",
                                          "ref_position"]),
              pd.DataFrame(pubs, columns=["arxiv_id", "parser_version"]))
    frames[1]["ref_year"] = pd.to_numeric(frames[1]["ref_year"])
    return frames


def _tables(root, papers=None):
    """(entries, refs, pubs) from data/m3/ when it is built, else from the JSON files of `papers`."""
    files = [Path(root) / "data" / "m3" / f"{t}.parquet" for t in ("entries", "refs", "pubs")]
    if all(f.is_file() for f in files):
        return tuple(pd.read_parquet(f) for f in files)
    if not papers:
        raise FileNotFoundError("data/m3 is not built: name the papers, e.g. papers=['2603.20581', ...]")
    return _from_json(root, papers)


def _text(value):
    return "" if value is None or (not hasattr(value, "__len__") and pd.isna(value)) else str(value)


def _join(values):
    return "" if values is None else "; ".join(map(str, values))


def _norm(title):
    return " ".join(re.findall(r"[a-z0-9]+", _text(title).lower()))


def _hints(entry, refs, k=3):
    """The k references with the most similar title (for entries without a title: nothing). Not a label."""
    title = _norm(entry.title)
    if not title:
        return [""] * k
    scored = sorted(((SequenceMatcher(None, title, _norm(r.ref_title)).ratio(), r.ref_arxiv_id, _text(r.ref_title))
                     for r in refs.itertuples()), reverse=True)[:k]
    return [f"{ref_id} | {t}" for _, ref_id, t in scored] + [""] * (k - len(scored))


def pick_papers(pubs, member, n=5, seed=42):
    """n papers of the member with 20-60 entries and >= 10 arXiv references, mixing bib and bibitem."""
    pool = pubs[(pubs["member"] == member) & pubs["eligible"] & pubs["n_entries"].between(20, 60)
                & (pubs["n_refs"] >= 10)].sort_values("arxiv_id").sample(frac=1, random_state=seed)
    mixed = pool.assign(turn=pool.groupby("bib_source").cumcount()).sort_values("turn", kind="mergesort")
    if len(mixed) < n:
        print(f"only {len(mixed)} papers of {member} satisfy the rule")
    return mixed["arxiv_id"].head(n).tolist()


def make_sheets(root=ROOT, labeler="TV4", papers=None, n=5):
    entries, refs, pubs = _tables(root, papers)
    papers = papers or pick_papers(pubs, labeler, n)
    out = Path(root) / "labels" / "sheets"           # NOT labels/manual: only filled <fid>.csv files go there
    out.mkdir(parents=True, exist_ok=True)
    for arxiv_id in papers:
        fid = arxiv_id.replace(".", "-")
        if (out / f"{fid}.csv").exists():
            print(f"{fid}: sheet already there, left as it is")
            continue
        e = entries[entries["arxiv_id"] == arxiv_id].sort_values("position")
        r = refs[refs["arxiv_id"] == arxiv_id].sort_values("ref_position")
        if e.empty or r.empty:
            print(f"{arxiv_id}: no entries or no references, skipped")
            continue
        parser = _text(pubs.loc[pubs["arxiv_id"] == arxiv_id, "parser_version"].iloc[0])
        rows = []
        for x in e.itertuples():
            context = _text(x.context[0])[:300] if x.context is not None and len(x.context) else ""
            rows.append([arxiv_id, x.citation_key, "", "", "", labeler, _text(x.title), _join(x.authors),
                         "" if pd.isna(x.year) else int(x.year), _text(x.journal), _text(x.doi), _text(x.url),
                         *_hints(x, r), context, parser])
        columns = LABEL_COLUMNS + ["title", "authors", "year", "journal", "doi", "url",
                                   "hint_1", "hint_2", "hint_3", "context", "parser_version"]
        pd.DataFrame(rows, columns=columns).to_csv(out / f"{fid}.csv", index=False)
        pd.DataFrame({"ref_arxiv_id": r["ref_arxiv_id"], "ref_title": r["ref_title"].map(_text),
                      "ref_authors": r["ref_authors"].map(_join), "ref_year": r["ref_year"].astype("Int64"),
                      "link": "https://arxiv.org/abs/" + r["ref_arxiv_id"]}
                     ).to_csv(out / f"{fid}_refs.csv", index=False)
        print(f"{fid}: {len(e)} entries, {len(r)} references")
    return papers


def check_labels(root=ROOT, labeler="TV4"):
    """Check every labels/manual/<fid>.csv that holds rows of `labeler`. Returns True when all are fine."""
    files = sorted((Path(root) / "labels" / "manual").glob("*.csv"))
    if not files:
        print(f"no file in {Path(root) / 'labels' / 'manual'}")
        return False
    entries, refs, _ = _tables(root, [path.stem.replace("-", ".", 1) for path in files])
    fine, n_papers, n_entries = True, 0, 0
    for path in files:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        missing = [c for c in LABEL_COLUMNS if c not in df.columns]
        if missing:
            print(f"{path.name}: missing columns {missing}")
            fine = False
            continue
        df = df.apply(lambda c: c.str.strip())
        if labeler not in set(df["labeler"]):
            continue
        arxiv_id = path.stem.replace("-", ".", 1)
        keys = set(entries.loc[entries["arxiv_id"] == arxiv_id, "citation_key"])
        known = set(refs.loc[refs["arxiv_id"] == arxiv_id, "ref_arxiv_id"])
        used = df.loc[df["ref_arxiv_id"] != "", "ref_arxiv_id"]
        problems = {
            "arxiv_id differs from the file name": sorted(set(df["arxiv_id"]) - {arxiv_id}),
            "entries not in the file": sorted(keys - set(df["citation_key"])),
            "keys that are not entries of the paper": sorted(set(df["citation_key"]) - keys),
            "keys written twice": sorted(df.loc[df["citation_key"].duplicated(), "citation_key"]),
            "ids that are not references of the paper": sorted(set(used) - known),
            "references used for two entries": sorted(set(used[used.duplicated()])),
            "confidence not sure/unsure": df.loc[~df["confidence"].isin(["sure", "unsure"]), "citation_key"].tolist(),
            "unsure without a note": df.loc[(df["confidence"] == "unsure") & (df["note"] == ""), "citation_key"].tolist(),
            "empty labeler": df.loc[df["labeler"] == "", "citation_key"].tolist(),
            "fewer than 20 entries": [len(keys)] if len(keys) < 20 else [],
        }
        problems = {k: v for k, v in problems.items() if v}
        fine &= not problems
        n_papers, n_entries = n_papers + 1, n_entries + len(df)
        print(f"{path.name}: {len(df)} rows, {len(used)} matched, "
              f"{(df['confidence'] == 'unsure').sum()} unsure -> {'OK' if not problems else 'FIX'}")
        for name, values in problems.items():
            print(f"    {name} ({len(values)}): {values[:8]}")
    print(f"{labeler}: {n_papers} papers, {n_entries} entries (need 5 papers, >= 100 entries)")
    return bool(fine and n_papers >= 5 and n_entries >= 100)
