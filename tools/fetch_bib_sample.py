"""Download a small real sample of arXiv sources to test `src/12_bibtex.ipynb` offline.

    python tools/fetch_bib_sample.py                 # about 30 papers, 10 of them with several versions
    python tools/fetch_bib_sample.py --papers 40 --multi 15 --seed 3

What it does
1. reads `ID_RANGES`, `USER_AGENT` and `ARXIV_DELAY` from `src/00_config.ipynb`;
2. asks the arXiv API (export.arxiv.org) how many versions a few candidate IDs have;
3. downloads every version of the chosen papers from `https://export.arxiv.org/src/<id>vN`,
   one connection, at least 3 s between requests, with a back-off on HTTP 429 / 5xx;
4. keeps only `.tex`, `.bib` and `.bbl` files under `data/raw/<yymm-id>/vN/` (a PDF-only version
   becomes an empty folder), the same layout as `02_download.ipynb` plus the `.bbl` files;
5. writes `data/bib_sample.json` with what was fetched.

`data/` is git-ignored: nothing downloaded here is ever committed. Standard library only.
This is a test helper, not the Milestone 1 crawler (`src/02_download.ipynb`).
"""
import argparse
import ast
import gzip
import http.client
import io
import json
import random
import re
import shutil
import sys
import tarfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parent.parent
CONFIG_NB = REPO / "src" / "00_config.ipynb"
KEEP = {".tex", ".bib", ".bbl"}            # .bbl is kept here only to test the .bbl parsers
MAX_FILE_BYTES = 30 * 1024 * 1024          # skip absurdly large members
MIN_DELAY = 3.0                            # arXiv terms of use: one request every 3 s
ATOM = "{http://www.w3.org/2005/Atom}"


def load_config():
    """ID_RANGES, USER_AGENT and ARXIV_DELAY as literals from 00_config.ipynb (nothing is executed)."""
    nb = json.loads(CONFIG_NB.read_text(encoding="utf-8"))
    wanted, found = {"ID_RANGES", "USER_AGENT", "ARXIV_DELAY"}, {}
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        try:
            tree = ast.parse("".join(cell["source"]))
        except SyntaxError:                 # cells with IPython magics
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and \
                    getattr(node.targets[0], "id", None) in wanted:
                found[node.targets[0].id] = ast.literal_eval(node.value)
    missing = wanted - set(found)
    if missing:
        raise SystemExit(f"00_config.ipynb does not define {sorted(missing)}")
    return found


class Client:
    """One connection, a fixed pause between requests, back-off on 429 / 5xx / network errors."""

    def __init__(self, user_agent, delay, retries=3, backoff=30.0):
        self.user_agent, self.delay = user_agent, max(MIN_DELAY, float(delay))
        self.retries, self.backoff = retries, backoff
        self.last, self.requests = 0.0, 0

    def get(self, url):
        """(status, body): 200 with the bytes, or 404 / other final status with b''."""
        wait = self.backoff
        for attempt in range(self.retries + 1):
            pause = self.last + self.delay - time.monotonic()
            if pause > 0:
                time.sleep(pause)
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            self.requests += 1
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = resp.read()
                self.last = time.monotonic()
                return 200, body
            except urllib.error.HTTPError as e:
                self.last = time.monotonic()
                if e.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    return e.code, b""
                retry_after = e.headers.get("Retry-After", "")
                pause = float(retry_after) if retry_after.isdigit() else wait
            except (OSError, http.client.HTTPException) as e:   # timeout, reset, truncated body
                self.last = time.monotonic()
                if attempt == self.retries:
                    print(f"  network error, giving up: {type(e).__name__}: {e}")
                    return 0, b""
                pause = min(wait, 10.0 * (attempt + 1))
                print(f"  network error: {type(e).__name__}")
            print(f"  retry {attempt + 1}/{self.retries} in {pause:.0f} s ({url})")
            time.sleep(pause)
            wait *= 2
        return 0, b""


def candidate_ids(id_ranges, n, rng):
    """About n IDs spread evenly over the assigned ranges ('2605.07338' .. '2605.12337')."""
    out, per_range = [], max(1, n // len(id_ranges))
    for first, last in id_ranges:
        prefix, lo = first.split(".")
        hi = last.split(".")[1]
        numbers = rng.sample(range(int(lo), int(hi) + 1), per_range)
        out += [f"{prefix}.{k:0{len(lo)}d}" for k in sorted(numbers)]
    return out


def latest_versions(client, ids):
    """{arxiv_id: number of versions} from the arXiv API; IDs that do not exist are left out."""
    found = {}
    for k in range(0, len(ids), 100):
        batch = ids[k:k + 100]
        url = f"https://export.arxiv.org/api/query?id_list={','.join(batch)}&max_results={len(batch)}"
        status, body = client.get(url)
        if status != 200:
            print(f"  API returned HTTP {status} for a batch of {len(batch)} IDs")
            continue
        for entry in ET.fromstring(body).iter(f"{ATOM}entry"):
            m = re.search(r"abs/(.+?)v(\d+)$", entry.findtext(f"{ATOM}id", ""))
            if m:
                found[m.group(1)] = int(m.group(2))
    return found


def _safe_relpath(name):
    """Archive member name -> safe relative path, or None (absolute paths and '..' are refused)."""
    parts = [p for p in PurePosixPath(name.replace("\\", "/")).parts if p not in ("", ".")]
    if not parts or any(p == ".." or p.startswith("/") or ":" in p for p in parts):
        return None
    return Path(*[re.sub(r'[<>"|?*\x00-\x1f]', "_", p).rstrip(" .") or "_" for p in parts])


def extract_source(payload, vdir):
    """Write the kept files of one e-print response into vdir; returns (kind, [relative paths])."""
    vdir.mkdir(parents=True, exist_ok=True)
    if payload[:2] == b"\x1f\x8b":
        try:
            payload = gzip.decompress(payload)
        except (OSError, EOFError):
            return "bad_gzip", []
    if payload[:5] == b"%PDF-":
        return "pdf_only", []
    try:
        archive = tarfile.open(fileobj=io.BytesIO(payload), mode="r:")
    except tarfile.TarError:
        archive = None
    kept = []
    if archive is None:                     # a single TeX file
        if b"\\" not in payload[:200000]:
            return "unknown", []
        (vdir / "main.tex").write_bytes(payload)
        return "single_tex", ["main.tex"]
    with archive:
        for member in archive:
            rel = _safe_relpath(member.name)
            if not member.isfile() or rel is None or rel.suffix.lower() not in KEEP or \
                    member.size > MAX_FILE_BYTES:
                continue
            data = archive.extractfile(member).read()
            target = vdir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            kept.append(rel.as_posix())
    return "tar", sorted(kept)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--papers", type=int, default=30, help="papers to download")
    ap.add_argument("--multi", type=int, default=10, help="of which papers with 2+ versions")
    ap.add_argument("--candidates", type=int, default=200, help="IDs checked through the API")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=REPO / "data" / "raw")
    args = ap.parse_args()

    cfg = load_config()
    client = Client(cfg["USER_AGENT"], cfg["ARXIV_DELAY"])
    rng = random.Random(args.seed)
    t0 = time.monotonic()

    ids = candidate_ids(cfg["ID_RANGES"], args.candidates, rng)
    print(f"checking {len(ids)} candidate IDs through the arXiv API ...")
    versions = latest_versions(client, ids)
    multi = [i for i in ids if versions.get(i, 0) >= 2]
    single = [i for i in ids if versions.get(i, 0) == 1]
    rng.shuffle(multi)
    rng.shuffle(single)
    chosen = multi[:args.multi]
    chosen += single[:max(0, args.papers - len(chosen))]
    chosen.sort()
    if not chosen:
        raise SystemExit("no existing paper among the candidates (API error?); nothing downloaded")
    total = sum(versions[i] for i in chosen)
    print(f"{len(versions)} IDs exist; chosen {len(chosen)} papers "
          f"({sum(versions[i] >= 2 for i in chosen)} with 2+ versions), {total} versions, "
          f"about {total * (client.delay + 1) / 60:.0f} min")

    manifest = []
    for n, arxiv_id in enumerate(chosen, 1):
        folder = args.out / arxiv_id.replace(".", "-").replace("/", "_")
        record = {"arxiv_id": arxiv_id, "versions": {}}
        for v in range(1, versions[arxiv_id] + 1):
            vdir = folder / f"v{v}"
            if vdir.is_dir():               # already fetched by an earlier run
                files = sorted(p.relative_to(vdir).as_posix() for p in vdir.rglob("*") if p.is_file())
                record["versions"][str(v)] = {"kind": "cached", "files": files}
                continue
            status, body = client.get(f"https://export.arxiv.org/src/{arxiv_id}v{v}")
            if status != 200:
                record["versions"][str(v)] = {"kind": f"http_{status}", "files": []}
                print(f"  {arxiv_id}v{v}: HTTP {status}, skipped")
                continue
            tmp = folder / f"v{v}.part"     # finish the folder before giving it its final name
            shutil.rmtree(tmp, ignore_errors=True)
            kind, files = extract_source(body, tmp)
            tmp.rename(vdir)
            record["versions"][str(v)] = {"kind": kind, "bytes": len(body), "files": files}
        manifest.append(record)
        kinds = ", ".join(f"v{v}: {r['kind']} ({len(r['files'])} files)" for v, r in record["versions"].items())
        print(f"[{n}/{len(chosen)}] {arxiv_id}  {kinds}", flush=True)

    out = args.out.parent / "bib_sample.json"
    out.write_text(json.dumps({"seed": args.seed, "requests": client.requests,
                               "seconds": round(time.monotonic() - t0, 1), "papers": manifest},
                              indent=2), encoding="utf-8")
    print(f"done: {len(manifest)} papers, {client.requests} requests, "
          f"{time.monotonic() - t0:.0f} s, manifest {out}")


if __name__ == "__main__":
    sys.exit(main())
