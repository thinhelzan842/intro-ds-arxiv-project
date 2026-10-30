"""Download every discovered arXiv source version on one paced connection.

The discovery notebook supplies a JSON list (or {"papers": [...]}) with
``id``/``versions``; ``arxiv_id``/``version_count`` is also accepted. Data,
receipts and logs belong on persistent storage, not in the code repository.

References: https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/crawling/
            https://info.arxiv.org/help/api/tou.html
            https://info.arxiv.org/help/mimetypes.html
"""

from __future__ import annotations

import argparse
import bz2
import csv
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import gzip
import hashlib
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile
import threading
import time
import uuid
import zipfile

import requests

try:
    import psutil
except ImportError:  # Downloader still works without optional RAM sampling.
    psutil = None


KEEP = frozenset({".tex", ".bib", ".bbl", ".sty", ".cls"})
ID_PATTERN = re.compile(r"^\d{2}(?:0[1-9]|1[0-2])\.\d{4,5}$")
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_TEXT_BYTES = 128 * 1024 * 1024
DEFAULT_USER_AGENT = "HCMUS-IntroDS-arXiv-source/1.0 (course project; contact: set ARXIV_CONTACT)"
ASSIGNED_RANGES = (("2609", 32834, 37833), ("2605", 17338, 22337),
                   ("2605", 7338, 12337), ("2603", 20580, 25579))
TEX_COMMAND = re.compile(rb"\\(?:documentclass|documentstyle|begin|input|def|newcommand|section)\b")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_manifest(records):
    """Normalize discovery records, rejecting ambiguous IDs and counts."""
    if not isinstance(records, list) or not records:
        raise ValueError("Manifest must contain a nonempty list of papers")
    normalized, seen = [], set()
    for item in records:
        if not isinstance(item, dict):
            raise ValueError("Each paper must be an object")
        identifier = item.get("arxiv_id", item.get("id"))
        count = item.get("version_count", item.get("versions"))
        if not isinstance(identifier, str) or not ID_PATTERN.fullmatch(identifier) or int(identifier.split(".")[1]) == 0:
            raise ValueError(f"Invalid modern arXiv ID: {identifier!r}")
        if identifier in seen:
            raise ValueError(f"Duplicate arXiv ID: {identifier}")
        if type(count) is not int or count < 0 or (count == 0 and item.get("status") not in ("not_found", "error")):
            raise ValueError(f"Invalid version count for {identifier}: {count!r}")
        seen.add(identifier)
        normalized.append(dict(item, arxiv_id=identifier, version_count=count))
    return normalized


def load_manifest(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        document = json.load(stream)
    return validate_manifest(document.get("papers") if isinstance(document, dict) else document)


def assigned_ids():
    """Return the exact 20,000 IDs assigned to the group, in instructor order."""
    return [f"{month}.{number:05d}" for month, low, high in ASSIGNED_RANGES
            for number in range(low, high + 1)]


def validate_assigned_manifest(records):
    normalized = validate_manifest(records)
    if {record["arxiv_id"] for record in normalized} != set(assigned_ids()):
        raise ValueError("Discovery manifest must cover exactly the 20,000 assigned IDs")
    return normalized


class SourceClient:
    """Single-threaded arXiv source client; retry attempts share the rate gate."""

    def __init__(self, session=None, user_agent=DEFAULT_USER_AGENT, delay=3.0,
                 max_attempts=4, clock=time.monotonic, sleeper=time.sleep):
        if delay < 3:
            raise ValueError("arXiv delay must be at least 3 seconds")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.session = session if session is not None else requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "identity"})
        self.delay, self.max_attempts = delay, max_attempts
        self.clock, self.sleeper = clock, sleeper
        self.last_start = None
        self.not_before = 0.0

    def _pace(self):
        wait = max(0.0, self.not_before - self.clock())
        if self.last_start is not None:
            wait = max(wait, self.delay - (self.clock() - self.last_start))
        if wait:
            self.sleeper(wait)
        self.last_start = self.clock()

    @staticmethod
    def _retry_after(value):
        if not value:
            return 0.0
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                return max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return 0.0

    def fetch(self, arxiv_id, version, destination):
        """Stream one version into a temporary file, then replace destination."""
        if not ID_PATTERN.fullmatch(arxiv_id) or type(version) is not int or version < 1:
            raise ValueError("Invalid arXiv ID/version")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://export.arxiv.org/src/{arxiv_id}v{version}"
        for attempt in range(self.max_attempts):
            self._pace()
            temporary = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".part")
            response = None
            try:
                response = self.session.get(url, stream=True, timeout=(10, 120), allow_redirects=False)
                status = response.status_code
                if status != 200:
                    error = requests.HTTPError(f"HTTP {status} from {url}", response=response)
                    if status in RETRY_STATUSES:
                        self.not_before = max(self.not_before,
                                              self.clock() + max(2 ** attempt, self._retry_after(response.headers.get("Retry-After"))))
                    if status not in RETRY_STATUSES or attempt + 1 == self.max_attempts:
                        raise error
                    continue
                size = 0
                with temporary.open("wb") as output:
                    for block in response.iter_content(chunk_size=1024 * 1024):
                        if block:
                            output.write(block)
                            size += len(block)
                    output.flush()
                    os.fsync(output.fileno())
                if not size:
                    raise requests.RequestException(f"Empty source response from {url}")
                os.replace(temporary, destination)
                return size
            except requests.HTTPError:
                raise
            except (requests.RequestException, OSError):
                if attempt + 1 == self.max_attempts:
                    raise
                self.sleeper(2 ** attempt)
            finally:
                if response is not None:
                    response.close()
                temporary.unlink(missing_ok=True)
        raise RuntimeError("Unreachable retry state")


def _safe_name(name):
    raw = str(name).replace("\\", "/")
    if (not raw or raw.startswith("/") or "\x00" in raw or ":" in raw
            or any(part in ("..", "") for part in raw.split("/"))):
        raise ValueError(f"Unsafe archive path: {name!r}")
    return "/".join(part for part in raw.split("/") if part != ".")


def _check_members(entries):
    seen, file_paths = set(), set()
    for name, is_file in entries:
        normalized = _safe_name(name).casefold()
        if not normalized:
            if is_file:
                raise ValueError("Archive file has no path")
            continue
        if is_file:
            if normalized in seen:
                raise ValueError(f"Duplicate archive path: {name!r}")
            seen.add(normalized)
            file_paths.add(normalized)
    for path in file_paths:
        parent = PurePosixPath(path).parent
        while str(parent) != ".":
            if str(parent) in file_paths:
                raise ValueError(f"Archive path conflicts with file: {path!r}")
            parent = parent.parent


def _copy_text(stream, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest, size = hashlib.sha256(), 0
    with destination.open("xb") as output:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            if size > MAX_TEXT_BYTES:
                raise ValueError("Source text file exceeds safety limit")
            digest.update(block)
            output.write(block)
    return {"size": size, "sha256": digest.hexdigest()}


def _known_non_tex(header):
    return header.startswith((b"%PDF-", b"\xd0\xcf\x11\xe0"))


def _scan_tex(stream):
    """Find TeX commands anywhere in a bounded single-file response."""
    found, tail, size = False, b"", 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        size += len(block)
        if size > MAX_TEXT_BYTES:
            raise ValueError("Single-file source exceeds safety limit")
        found = found or bool(TEX_COMMAND.search(tail + block))
        tail = block[-64:]
    return found, size


def extract_source(archive, destination):
    """Write only source text; compute uncompressed member sizes without storing figures."""
    archive, destination = Path(archive), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    result = {"status": "empty_source", "before_bytes": 0, "after_bytes": 0, "files": {}}
    with archive.open("rb") as stream:
        header = stream.read(8192)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as package:
            members = package.infolist()
            for member in members:
                mode = (member.external_attr >> 16) & 0o170000
                if mode not in (0, 0o100000, 0o040000):
                    raise ValueError(f"Special ZIP member: {member.filename!r}")
            _check_members([(m.filename.rstrip("/"), not m.is_dir()) for m in members])
            files = [m for m in members if not m.is_dir()]
            result["before_bytes"] = sum(m.file_size for m in files)
            if any(Path(m.filename).suffix.lower() == ".tex" for m in files):
                for member in files:
                    name = _safe_name(member.filename)
                    if Path(name).suffix.lower() in KEEP:
                        with package.open(member) as stream:
                            result["files"][name] = _copy_text(stream, destination / name)
    else:
        try:
            package = tarfile.open(archive, mode="r:*")
        except tarfile.TarError:
            package = None
        if package is not None:
            with package:
                members = package.getmembers()
                for member in members:
                    if not (member.isfile() or member.isdir()):
                        raise ValueError(f"Special TAR member: {member.name!r}")
                _check_members([(m.name.rstrip("/"), m.isfile()) for m in members])
                files = [m for m in members if m.isfile()]
                result["before_bytes"] = sum(m.size for m in files)
                if any(Path(m.name).suffix.lower() == ".tex" for m in files):
                    for member in files:
                        name = _safe_name(member.name)
                        if Path(name).suffix.lower() in KEEP:
                            with package.extractfile(member) as stream:
                                result["files"][name] = _copy_text(stream, destination / name)
        else:
            opener = gzip.open if header.startswith(b"\x1f\x8b") else (
                bz2.open if header.startswith(b"BZh") else (
                    lzma.open if header.startswith(b"\xfd7zXZ") else None))
            if opener is not None:
                with opener(archive, "rb") as stream:
                    first = stream.read(8192)
                    if _known_non_tex(first):
                        result["before_bytes"] = len(first) + sum(len(block) for block in iter(lambda: stream.read(1024 * 1024), b""))
                    else:
                        if len(first) > MAX_TEXT_BYTES:
                            raise ValueError("Single-file source exceeds safety limit")
                        if first.lstrip().lower().startswith((b"<html", b"<!doctype", b"<?xml", b"{")):
                            raise ValueError("Unrecognized HTML/JSON source response")
                        with tempfile.TemporaryFile() as reconstructed:
                            reconstructed.write(first)
                            found = bool(TEX_COMMAND.search(first))
                            tail, size = first[-64:], len(first)
                            for block in iter(lambda: stream.read(1024 * 1024), b""):
                                size += len(block)
                                if size > MAX_TEXT_BYTES:
                                    raise ValueError("Single-file source exceeds safety limit")
                                found = found or bool(TEX_COMMAND.search(tail + block))
                                tail = block[-64:]
                                reconstructed.write(block)
                            result["before_bytes"] = size
                            if not found:
                                raise ValueError("Unrecognized single-file source response")
                            reconstructed.seek(0)
                            result["files"]["main.tex"] = _copy_text(reconstructed, destination / "main.tex")
            elif _known_non_tex(header):
                result["before_bytes"] = archive.stat().st_size
            elif header.lstrip().lower().startswith((b"<html", b"<!doctype", b"<?xml", b"{")):
                raise ValueError("Unrecognized HTML/JSON source response")
            else:
                with archive.open("rb") as stream:
                    found, size = _scan_tex(stream)
                if not found:
                    raise ValueError("Unrecognized single-file source response")
                result["before_bytes"] = size
                with archive.open("rb") as stream:
                    result["files"]["main.tex"] = _copy_text(stream, destination / "main.tex")
    if any(Path(name).suffix.lower() == ".tex" for name in result["files"]):
        result["status"] = "ok"
        result["after_bytes"] = sum(entry["size"] for entry in result["files"].values())
    return result


def _folder(arxiv_id):
    return arxiv_id.replace(".", "-")


def _receipt_path(state_dir, arxiv_id, version):
    return Path(state_dir) / "receipts" / _folder(arxiv_id) / f"v{version}.json"


def verified_receipt(state_dir, output_dir, arxiv_id, version):
    receipt_path = _receipt_path(state_dir, arxiv_id, version)
    if not receipt_path.is_file():
        return None
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (receipt["arxiv_id"] != arxiv_id or receipt["version"] != version
                or receipt["status"] not in ("ok", "empty_source")):
            return None
        directory = Path(output_dir) / _folder(arxiv_id) / f"v{version}"
        if not directory.is_dir() or directory.is_symlink():
            return None
        files = receipt["files"]
        actual = {}
        for path in directory.rglob("*"):
            if path.is_symlink():
                return None
            if path.is_file():
                with path.open("rb") as stream:
                    digest = hashlib.sha256()
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                actual[path.relative_to(directory).as_posix()] = {"size": path.stat().st_size, "sha256": digest.hexdigest()}
        if actual != files or (receipt["status"] == "ok" and not any(Path(n).suffix.lower() == ".tex" for n in files)):
            return None
        if receipt["status"] == "empty_source" and files:
            return None
        return receipt
    except (OSError, ValueError, KeyError, TypeError):
        return None


def collect_one(client, record, version, output_dir, state_dir):
    started = time.perf_counter()
    identifier = record["arxiv_id"]
    output_dir, state_dir = Path(output_dir), Path(state_dir)
    stage = output_dir / ".staging"
    stage.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as local_temporary, tempfile.TemporaryDirectory(dir=stage) as temporary:
        temporary = Path(temporary)
        raw, extracted = Path(local_temporary) / "download.bin", temporary / "source"
        downloaded = client.fetch(identifier, version, raw)
        info = extract_source(raw, extracted)
        target = output_dir / _folder(identifier) / f"v{version}"
        target.parent.mkdir(parents=True, exist_ok=True)
        backup = None
        if target.exists():
            backup = state_dir / "replaced" / f"{_folder(identifier)}_v{version}_{uuid.uuid4().hex}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            os.replace(target, backup)
        try:
            os.replace(extracted, target)
            receipt = dict(info, arxiv_id=identifier, version=version,
                           downloaded_bytes=downloaded, finished_at=_now(),
                           elapsed_seconds=round(time.perf_counter() - started, 3))
            _atomic_json(_receipt_path(state_dir, identifier, version), receipt)
        except Exception:
            if backup is not None and not target.exists():
                os.replace(backup, target)
            raise
        if backup is not None:
            shutil.rmtree(backup)
        return receipt


class _MemorySampler:
    def __init__(self):
        self.values = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self):
        process = psutil.Process() if psutil else None
        while not self.stop.is_set():
            if process:
                self.values.append(process.memory_info().rss)
            self.stop.wait(2)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join()


def _progress(records, receipts):
    total_papers = len(records)
    total_versions = sum(r["version_count"] for r in records)
    completed_versions = len(receipts)
    completed_papers = sum(
        (r["version_count"] == 0 and r.get("status") == "not_found") or
        (r["version_count"] > 0 and all((r["arxiv_id"], v) in receipts for v in range(1, r["version_count"] + 1)))
        for r in records
    )
    return {"papers_completed": completed_papers, "papers_total": total_papers,
            "papers_percent": round(100 * completed_papers / total_papers, 2),
            "versions_completed": completed_versions, "versions_total": total_versions,
            "versions_percent": round(100 * completed_versions / total_versions, 2) if total_versions else 0.0}


def _print_progress(progress):
    print(f"Papers: {progress['papers_completed']:,}/{progress['papers_total']:,} ({progress['papers_percent']:.2f}%) | "
          f"versions: {progress['versions_completed']:,}/{progress['versions_total']:,} ({progress['versions_percent']:.2f}%)")


def _write_papers_csv(path, records, receipts):
    """Export downloader metrics in the column schema of 04_monitor.ipynb."""
    fields = ("id", "versions", "versions_ok", "size_before", "size_after",
              "n_refs", "n_arxiv_refs", "status", "seconds", "error", "logged_at")
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for record in records:
                identifier, count = record["arxiv_id"], record["version_count"]
                found = [receipts[(identifier, version)] for version in range(1, count + 1)
                         if (identifier, version) in receipts]
                status = (record.get("status", "error") if count == 0 else
                          "ok" if len(found) == count and all(r["status"] == "ok" for r in found) else
                          "partial" if found else "error")
                writer.writerow({"id": identifier, "versions": count,
                                 "versions_ok": sum(r["status"] == "ok" for r in found),
                                 "size_before": sum(r["before_bytes"] for r in found),
                                 "size_after": sum(r["after_bytes"] for r in found),
                                 "status": status,
                                 "seconds": round(sum(r.get("elapsed_seconds", 0) for r in found), 3),
                                 "error": "unprocessed source versions" if len(found) < count else "",
                                 "logged_at": _now()})
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run(manifest_path, output_dir, state_dir, *, user_agent=DEFAULT_USER_AGENT,
        delay=3.0, session=None, sleeper=time.sleep):
    """Run or resume one sequential worker; errors are logged for next run."""
    start = time.perf_counter()
    records = load_manifest(manifest_path)
    output_dir, state_dir = Path(output_dir), Path(state_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for record in records:
        for version in range(1, record["version_count"] + 1):
            receipt = verified_receipt(state_dir, output_dir, record["arxiv_id"], version)
            if receipt is not None:
                receipts[(record["arxiv_id"], version)] = receipt
    initial = _progress(records, receipts)
    print("Progress at start/resume:")
    _print_progress(initial)
    skipped = failed = 0
    current_bytes = sum(r["after_bytes"] for r in receipts.values())
    disk_peak_estimate = current_bytes
    client = SourceClient(session=session, user_agent=user_agent, delay=delay, sleeper=sleeper)
    owns_session = session is None
    interrupted = False
    try:
        with _MemorySampler() as memory:
            try:
                for index, record in enumerate(records, 1):
                    identifier = record["arxiv_id"]
                    for version in range(1, record["version_count"] + 1):
                        key = (identifier, version)
                        if key in receipts:
                            skipped += 1
                            continue
                        try:
                            receipt = collect_one(client, record, version, output_dir, state_dir)
                            disk_peak_estimate = max(disk_peak_estimate,
                                                     current_bytes + receipt["downloaded_bytes"] + receipt["after_bytes"])
                            current_bytes += receipt["after_bytes"]
                            receipts[key] = receipt
                        except Exception as exc:
                            failed += 1
                            with (state_dir / "errors.jsonl").open("a", encoding="utf-8") as errors:
                                errors.write(json.dumps({"arxiv_id": identifier, "version": version,
                                                         "error": repr(exc), "at": _now()}, ensure_ascii=False) + "\n")
                            print(f"FAILED {identifier}v{version}: {exc}")
                    if index % 100 == 0 or index == len(records):
                        current = _progress(records, receipts)
                        _print_progress(current)
                        _atomic_json(state_dir / "progress.json", current)
            except KeyboardInterrupt:
                interrupted = True
                print("Interrupted; completed version receipts are saved on persistent storage.")
    finally:
        if owns_session:
            client.session.close()
    progress = _progress(records, receipts)
    final_bytes = sum(r["after_bytes"] for r in receipts.values())
    summary = {"finished_at": _now(), "elapsed_seconds": round(time.perf_counter() - start, 3),
               "interrupted": interrupted, "progress": progress,
               "elapsed_per_assigned_paper_seconds": round((time.perf_counter() - start) / len(records), 6),
               "versions_ok": sum(r["status"] == "ok" for r in receipts.values()),
               "versions_empty": sum(r["status"] == "empty_source" for r in receipts.values()),
               "papers_all_sources": sum(
                   r["version_count"] > 0 and all(
                       (r["arxiv_id"], v) in receipts and receipts[(r["arxiv_id"], v)]["status"] == "ok"
                       for v in range(1, r["version_count"] + 1)) for r in records),
               "versions_skipped": skipped, "versions_failed_this_run": failed,
               "source_before_bytes": sum(r["before_bytes"] for r in receipts.values()),
               "source_after_bytes": final_bytes,
               "output_bytes": final_bytes,
               "disk_peak_estimate_bytes": max(disk_peak_estimate, final_bytes),
               "ram_peak_bytes": max(memory.values, default=None),
               "ram_average_bytes": round(sum(memory.values) / len(memory.values)) if memory.values else None}
    _atomic_json(state_dir / "run_summary.json", summary)
    _atomic_json(state_dir / "progress.json", progress)
    _write_papers_csv(state_dir / "papers.csv", records, receipts)
    with (state_dir / "run_history.jsonl").open("a", encoding="utf-8") as history:
        history.write(json.dumps(summary, ensure_ascii=False) + "\n")
        history.flush()
        os.fsync(history.fileno())
    _print_progress(progress)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    args = parser.parse_args(argv)
    run(args.manifest, args.output, args.state, user_agent=args.user_agent)


if __name__ == "__main__":
    main()
