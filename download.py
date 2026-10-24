"""Download and filter arXiv sources with JSON-based resume (Python >= 3.10).

Requires python-magic, requests, urllib3, and system libmagic. Mount Drive first.

Usage:
    python download.py local ./raw_50 ./sources --expected-papers 50
    python download.py resume --progress ./drive/progress.json --output ./drive --temp /content/temp
    python download.py scan --progress ./progress.json --output ./saved_papers

Input names need an ID and version, e.g. 2603.20580v1.bin. Output: yymm-id/vN/.
Resume verifies existing folders and ZIPs once, then caches IDs in progress.json.
Use --rescan after output changes. Run one writer per progress file.
Collects source versions and arXiv metadata, without ZIP batching or Semantic Scholar.
"""

from __future__ import annotations

import argparse
import bz2
import contextlib
from dataclasses import dataclass
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
import time
from urllib.parse import urljoin, urlsplit
import uuid
from xml.etree import ElementTree as ET
import zipfile

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

try:
    import magic
except (ImportError, OSError):
    magic = None  # JSON-only resume and --help do not need libmagic.


KEEP_EXTENSIONS = frozenset({".tex", ".bib", ".bbl", ".cls", ".sty"})
ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
ID_RE = re.compile(r"(?P<month>\d{4})[.-](?P<number>\d{4,5})")
VERSION_RE = re.compile(r"(?:__|[._-])?v([1-9]\d*)", re.I)
IGNORED_DIRS = {"arxiv_state", "progress_parts", "_cache", "_interrupted", ".staging"}
TRANSIENT_HTTP = {429, 500, 502, 503, 504}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path, document):
    """Replace JSON only after the temporary file is fully written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_progress(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        document = json.load(stream)
    if isinstance(document, list):
        document = {"papers": document}
    if not isinstance(document, dict) or not isinstance(document.get("papers"), list):
        raise ValueError("progress.json phải chứa danh sách papers.")
    return document


def normalize_id(value):
    value = str(value).strip()
    value = re.sub(r"^https?://(?:export\.)?arxiv\.org/(?:abs|pdf)/", "", value)
    value = re.sub(r"^arxiv:", "", value, flags=re.I)
    value = re.sub(r"(?:v[1-9]\d*)?(?:\.pdf)?$", "", value)
    match = ID_RE.fullmatch(value)
    if not match or not 1 <= int(match["month"][-2:]) <= 12 or int(match["number"]) == 0:
        raise ValueError(f"arXiv ID yymm.id không hợp lệ: {value!r}")
    return match["month"] + "." + match["number"]


def record_id(record):
    if isinstance(record, str):
        return normalize_id(record)
    if isinstance(record, dict):
        for key in ("arxiv_id", "id", "paper_id"):
            if record.get(key):
                return normalize_id(record[key])
    raise ValueError(f"Record không có arxiv_id: {record!r}")


def paper_folder(identifier):
    return normalize_id(identifier).replace(".", "-")


def hash_stream(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def hash_file(path):
    with Path(path).open("rb") as stream:
        return hash_stream(stream)


def safe_relative(name):
    name = str(name).replace("\\", "/")
    parts = PurePosixPath(name)
    if not name or parts.is_absolute() or ".." in parts.parts or ":" in name or "\x00" in name:
        raise ValueError(f"Đường dẫn archive không an toàn: {name!r}")
    return parts.as_posix()


# Module 1: Local files

@dataclass(frozen=True)
class ArchiveFormat:
    kind: str
    mime: str


@dataclass(frozen=True)
class LocalArchive:
    path: Path
    arxiv_id: str
    version: int
    format: ArchiveFormat


def detect_archive(path):
    """Detect the format from header bytes, not the extension."""
    if magic is None:
        raise RuntimeError("Cần python-magic và libmagic của hệ thống để nhận diện header.")
    with Path(path).open("rb") as stream:
        header = stream.read(65536)
    if not header:
        raise ValueError(f"File rỗng: {path}")
    mime = magic.from_buffer(header, mime=True).split(";", 1)[0].strip()
    formats = {
        "application/zip": "zip", "application/x-zip": "zip",
        "application/x-zip-compressed": "zip", "application/x-tar": "tar",
        "application/gzip": "gzip", "application/x-gzip": "gzip",
        "application/x-bzip2": "bzip2", "application/x-xz": "xz",
    }
    if mime in formats:
        return ArchiveFormat(formats[mime], mime)
    if mime in {"text/x-tex", "text/x-latex"} or (mime.startswith("text/") and re.search(
        rb"\\(?:documentclass|documentstyle|begin|input|def|newcommand|section)\b", header
    )):
        return ArchiveFormat("tex", mime)
    raise ValueError(f"Định dạng không hỗ trợ/không phải source LaTeX: {mime} ({path})")


def identity_from_path(path):
    """Read the ID and version from file or parent folder names."""
    identifier = None
    version = None
    for component in reversed(Path(path).parts):
        match = ID_RE.search(component)
        if match:
            candidate = normalize_id(match.group())
            if identifier is not None and identifier != candidate:
                raise ValueError(f"ID không nhất quán trong đường dẫn: {path}")
            identifier = candidate
            revision = VERSION_RE.match(component[match.end():])
            if revision and version is None:
                version = int(revision.group(1))
        elif version is None and re.fullmatch(r"v[1-9]\d*", component, re.I):
            version = int(component[1:])
    if identifier is None or version is None:
        raise ValueError(f"Tên file/thư mục phải chỉ rõ arXiv ID và vN: {path}")
    return identifier, version


def scan_local_archives(input_dir, expected_papers=50):
    """List sources, counting revisions of one ID as one paper."""
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise NotADirectoryError(input_dir)
    result = []
    identities = set()
    for path in sorted(input_dir.rglob("*")):
        if (not path.is_file() or path.is_symlink() or path.name.endswith((".part", ".tmp"))
                or any(p.startswith(".") for p in path.relative_to(input_dir).parts)):
            continue
        identifier, version = identity_from_path(path)
        if (identifier, version) in identities:
            raise ValueError(f"Trùng source của {identifier}v{version}")
        identities.add((identifier, version))
        result.append(LocalArchive(path, identifier, version, detect_archive(path)))
    count = len({item.arxiv_id for item in result})
    if expected_papers is not None and count != expected_papers:
        raise ValueError(f"Cần {expected_papers} bài, nhưng nhận diện được {count} bài.")
    return sorted(result, key=lambda item: (item.arxiv_id, item.version))


# Module 2: Extraction and filtering

def _extract_raw(path, destination, depth=0):
    if depth > 4:
        raise ValueError("Quá nhiều lớp nén lồng nhau.")
    detected = detect_archive(path)
    if detected.kind == "zip":
        with zipfile.ZipFile(path) as archive:
            seen = set()
            for member in archive.infolist():
                name = safe_relative(member.filename)
                if name in seen:
                    raise ValueError(f"ZIP có tên file trùng: {name}")
                seen.add(name)
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError(f"ZIP chứa symlink: {name}")
                target = destination / name
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
    elif detected.kind == "tar":
        with tarfile.open(path, "r:") as archive:
            for member in archive:
                name = safe_relative(member.name)
                target = destination / name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
                else:
                    raise ValueError(f"TAR chứa link/file đặc biệt: {name}")
    elif detected.kind in {"gzip", "bzip2", "xz"}:
        opener = {"gzip": gzip.open, "bzip2": bz2.open, "xz": lzma.open}[detected.kind]
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            inner = Path(temporary) / "payload"
            with opener(path, "rb") as source, inner.open("wb") as output:
                shutil.copyfileobj(source, output)
            _extract_raw(inner, destination, depth + 1)
    else:
        shutil.copyfile(path, destination / "main.tex")
    return detected


def filter_sources(directory):
    """Keep whitelisted files and verify their contents are unchanged."""
    directory = Path(directory)
    files = [p for p in directory.rglob("*") if p.is_file()]
    if any(p.is_symlink() for p in directory.rglob("*")):
        raise ValueError("Source chứa symlink.")
    before = sum(p.stat().st_size for p in files)
    hashes = {p.relative_to(directory).as_posix(): hash_file(p)
              for p in files if p.suffix.lower() in KEEP_EXTENSIONS}
    for path in files:
        if path.suffix.lower() not in KEEP_EXTENSIONS:
            path.unlink()
    for path in sorted(directory.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir():
            with contextlib.suppress(OSError):
                path.rmdir()
    if not any(Path(name).suffix.lower() == ".tex" for name in hashes):
        raise ValueError("Source không có file .tex; không đánh dấu hoàn tất.")
    if any(hash_file(directory / name) != digest for name, digest in hashes.items()):
        raise ValueError("Nội dung source đã bị thay đổi ngoài ý muốn.")
    after = sum((directory / name).stat().st_size for name in hashes)
    print(f"{directory.name}: {before:,} -> {after:,} bytes; xóa {before - after:,} bytes")
    return {"before_bytes": before, "after_bytes": after, "sha256": hashes}


def _reusable_version(directory, identifier, version):
    metadata_path = directory / f"metadata/arxiv_v{version}_metadata.json"
    source = directory / f"v{version}"
    if (not metadata_path.is_file() or not source.is_dir() or source.is_symlink()
            or any(p.is_symlink() for p in source.rglob("*"))):
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        hashes = metadata["source_files_sha256"]
        actual = {p.relative_to(source).as_posix(): hash_file(p)
                  for p in source.rglob("*") if p.is_file() and not p.is_symlink()}
        if (metadata["arxiv_id"] == identifier and metadata["version"] == version
                and hashes and actual == hashes
                and all(Path(p).suffix.lower() in KEEP_EXTENSIONS for p in actual)
                and any(Path(p).suffix.lower() == ".tex" for p in actual)):
            return metadata
    except (ValueError, KeyError, TypeError):
        pass
    return None


def extract_and_filter(archive, output_dir, arxiv_id=None, version=None):
    """Extract to yymm-id/vN, backing up any incomplete version."""
    path = archive.path if isinstance(archive, LocalArchive) else Path(archive)
    if isinstance(archive, LocalArchive):
        arxiv_id, version = archive.arxiv_id, archive.version
    if arxiv_id is None or version is None:
        arxiv_id, version = identity_from_path(path)
    identifier = normalize_id(arxiv_id)
    if type(version) is not int or version < 1:
        raise ValueError("version phải là số nguyên dương.")
    output_dir = Path(output_dir)
    directory = output_dir / paper_folder(identifier)
    target = directory / f"v{version}"
    previous = _reusable_version(directory, identifier, version)
    if previous is not None:
        print(f"Tái sử dụng {identifier}v{version}")
        return dict(previous, source_directory=str(target))
    staging_root = output_dir / ".staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=staging_root) as temporary:
        source = Path(temporary) / "source"
        source.mkdir()
        detected = _extract_raw(path, source)
        statistics = filter_sources(source)
        directory.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = output_dir / "_interrupted" / f"{directory.name}_v{version}_{uuid.uuid4().hex}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(backup))
            print("Giữ bản dở dang tại:", backup)
        os.replace(source, target)
    metadata = {
        "arxiv_id": identifier, "version": version, "detected_mime": detected.mime,
        "before_bytes": statistics["before_bytes"], "after_bytes": statistics["after_bytes"],
        "source_size_after_bytes": statistics["after_bytes"],
        "source_files_sha256": statistics["sha256"],
    }
    atomic_write_json(directory / f"metadata/arxiv_v{version}_metadata.json", metadata)
    return dict(metadata, source_directory=str(target))


# Module 3: Scan and resume

def _validate_paper(identifier, sizes, read, digest):
    """Validate a paper from a folder or ZIP view."""
    manifest_name = "metadata/arxiv_versions.json"
    if manifest_name not in sizes:
        return False
    try:
        manifest = json.loads(read(manifest_name))
        count = manifest["version_count"]
        versions = manifest["versions"]
        if (normalize_id(manifest["arxiv_id"]) != identifier
                or type(count) is not int or not 1 <= count <= 10000
                or [v["version"] for v in versions] != list(range(1, count + 1))):
            return False
        marker_name = "metadata/collection_complete.json"
        marker_hashes = None
        if marker_name in sizes:
            marker = json.loads(read(marker_name))
            if not isinstance(marker["files"], dict):
                return False
            marker_hashes = {safe_relative(k): v for k, v in marker["files"].items()}
            if (normalize_id(marker["arxiv_id"]) != identifier
                    or not marker_hashes or manifest_name not in marker_hashes):
                return False
            if any(name not in sizes or digest(name) != checksum
                   for name, checksum in marker_hashes.items()):
                return False
        for version in range(1, count + 1):
            prefixes = (f"v{version}/", f"sources/v{version}/")
            prefix = next((p for p in prefixes if any(n.startswith(p) for n in sizes)), None)
            if prefix is None:
                return False
            files = {n: size for n, size in sizes.items() if n.startswith(prefix)}
            if (not any(Path(n).suffix.lower() == ".tex" for n in files)
                    or any(Path(n).suffix.lower() not in KEEP_EXTENSIONS for n in files)):
                return False
            if marker_hashes is not None:
                if any(n not in marker_hashes for n in files):
                    return False
            # A completion marker does not replace version metadata.
            name = f"metadata/arxiv_v{version}_metadata.json"
            if name not in sizes or (marker_hashes is not None and name not in marker_hashes):
                return False
            metadata = json.loads(read(name))
            if (normalize_id(metadata["arxiv_id"]) != identifier
                    or metadata["version"] != version
                    or metadata["source_size_after_bytes"] != sum(files.values())):
                return False
            hashes = metadata.get("source_files_sha256")
            if hashes is not None:
                if not isinstance(hashes, dict):
                    return False
                expected = {prefix + safe_relative(k): v for k, v in hashes.items()}
                if set(expected) != set(files) or any(digest(n) != h for n, h in expected.items()):
                    return False
            elif marker_hashes is None:
                # Read legacy ZIP members to check CRC, not just sizes.
                for name in files:
                    digest(name)
        return True
    except (ValueError, KeyError, TypeError):
        return False


def is_complete_paper(directory, identifier):
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        return False
    paths = {}
    for path in directory.rglob("*"):
        if path.is_symlink():
            return False
        if path.is_file():
            paths[path.relative_to(directory).as_posix()] = path
    return _validate_paper(
        normalize_id(identifier), {n: p.stat().st_size for n, p in paths.items()},
        lambda n: paths[n].read_bytes(), lambda n: hash_file(paths[n]),
    )


def _scan_zip(path):
    result = set()
    with zipfile.ZipFile(path) as archive:
        members = {}
        prefixes = {}
        for member in archive.infolist():
            name = safe_relative(member.filename)
            if member.is_dir():
                continue
            if name in members or (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("ZIP chứa tên trùng/symlink.")
            members[name] = member
            parts = PurePosixPath(name).parts
            for index, part in enumerate(parts[:-1]):
                if ID_RE.fullmatch(part):
                    prefixes["/".join(parts[:index + 1]) + "/"] = normalize_id(part)
        for prefix, identifier in prefixes.items():
            subset = {n[len(prefix):]: item for n, item in members.items() if n.startswith(prefix)}
            def read(name):
                return archive.read(subset[name])
            def digest(name):
                with archive.open(subset[name]) as stream:
                    return hash_stream(stream)
            try:
                if _validate_paper(identifier, {n: item.file_size for n, item in subset.items()}, read, digest):
                    result.add(identifier)
            except (zipfile.BadZipFile, ValueError, EOFError) as error:
                print(f"Không tính bài lỗi {identifier} trong {path}: {error}")
    return result


def scan_downloaded_ids(output_dir):
    """Find complete papers in existing folders and ZIPs."""
    output_dir = Path(output_dir)
    if not output_dir.is_dir():
        raise NotADirectoryError(f"Chưa thấy thư mục đầu ra/Drive chưa mount: {output_dir}")
    downloaded_ids = set()
    def walk_error(error):
        raise error  # Do not cache a scan interrupted by a Drive error.
    for current, directories, filenames in os.walk(output_dir, onerror=walk_error, followlinks=False):
        current = Path(current)
        directories[:] = [n for n in directories if n not in IGNORED_DIRS
                          and not n.startswith(".") and not (current / n).is_symlink()]
        if ID_RE.fullmatch(current.name):
            identifier = normalize_id(current.name)
            if is_complete_paper(current, identifier):
                downloaded_ids.add(identifier)
            else:
                print("Chưa đủ bằng chứng hoàn tất, không skip:", current)
            directories[:] = []
            continue
        for name in sorted(filenames):
            path = current / name
            if (path.is_symlink() or name.endswith((".part", ".tmp", ".download"))
                    or name.startswith(".") or path.stat().st_size == 0):
                continue
            try:
                detected = detect_archive(path)
            except ValueError:
                continue
            if detected.kind == "zip":
                try:
                    downloaded_ids.update(_scan_zip(path))
                except (zipfile.BadZipFile, ValueError, EOFError) as error:
                    print(f"Không tính ZIP lỗi {path}: {error}")
    print(f"Quét đầu ra: xác minh {len(downloaded_ids):,} arXiv ID đã hoàn tất.")
    return downloaded_ids


def initialize_downloaded_ids(progress_path, output_dir, rescan=False):
    """Use cached IDs unless missing or a rescan is requested."""
    document = read_progress(progress_path)
    if "downloaded_ids" in document and not rescan:
        if not isinstance(document["downloaded_ids"], list):
            raise ValueError("downloaded_ids phải là một danh sách JSON.")
        cached_root = document.get("downloaded_ids_scan_root")
        if cached_root and cached_root != str(Path(output_dir).resolve()):
            raise ValueError("Thư mục đầu ra đã đổi; dùng --rescan để xây dựng lại danh sách.")
        return {normalize_id(value) for value in document["downloaded_ids"]}
    downloaded_ids = scan_downloaded_ids(output_dir)
    document["downloaded_ids"] = sorted(downloaded_ids)
    document["downloaded_ids_scanned_at"] = utc_now()
    document["downloaded_ids_scan_root"] = str(Path(output_dir).resolve())
    atomic_write_json(progress_path, document)
    return downloaded_ids


class PoliteRetry(Retry):
    def sleep(self, response=None):
        time.sleep(max(3, self.get_backoff_time()))


def create_session(max_attempts=6):
    if max_attempts < 1:
        raise ValueError("max_attempts phải >= 1.")
    retry = PoliteRetry(total=max_attempts - 1, connect=max_attempts - 1,
                        read=0, status=0, redirect=0, backoff_factor=3,
                        respect_retry_after_header=False, raise_on_status=False)
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update({"Accept-Encoding": "identity"})
    return session


def retry_delay(headers, attempt):
    value = headers.get("Retry-After")
    if value:
        try:
            return max(3, float(value))
        except ValueError:
            try:
                date = parsedate_to_datetime(value)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                return max(3, (date - datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    return min(300, 15 * 2 ** attempt)


def request_data(session, url, *, destination=None, params=None, max_attempts=6):
    """Retry throttled or broken downloads from the beginning."""
    if max_attempts < 1:
        raise ValueError("max_attempts phải >= 1.")
    destination = Path(destination) if destination is not None else None
    partial = destination.with_name(destination.name + ".part") if destination else None
    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
    attempt = redirects = 0
    while attempt < max_attempts:
        wait = 3
        try:
            with session.get(url, params=params, stream=True, timeout=(30, 120),
                             allow_redirects=False) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    redirects += 1
                    if redirects > 10:
                        raise ValueError("Quá nhiều redirect.")
                    url = urljoin(url, response.headers["Location"])
                    if urlsplit(url).scheme not in {"https", "http"}:
                        raise ValueError("Redirect không phải HTTP/HTTPS.")
                    params = None
                    continue
                if response.status_code in TRANSIENT_HTTP:
                    wait = retry_delay(response.headers, attempt)
                response.raise_for_status()
                count = 0
                stream = partial.open("wb") if partial else None
                if partial is None:
                    from io import BytesIO
                    stream = BytesIO()
                with stream:
                    for block in response.iter_content(1024 * 1024):
                        if block:
                            stream.write(block)
                            count += len(block)
                    expected = response.headers.get("Content-Length")
                    if (expected is not None
                            and response.headers.get("Content-Encoding", "identity") == "identity"
                            and count != int(expected)):
                        raise requests.exceptions.ChunkedEncodingError("Thiếu byte so với Content-Length.")
                    data = stream.getvalue() if partial is None else None
                if partial:
                    os.replace(partial, destination)
                    return destination
                return data
        except requests.RequestException as error:
            status = error.response.status_code if error.response is not None else None
            if status is not None and status not in TRANSIENT_HTTP:
                raise
            if attempt == max_attempts - 1:
                print(f"Hết {max_attempts} lần thử: {url} ({type(error).__name__})")
                raise
            if status is None:
                wait = retry_delay({}, attempt)
            print(f"{status or 'network'}: chờ {wait:.0f}s; {url}")
        finally:
            if partial and partial.exists():
                partial.unlink()
            time.sleep(3)  # Also wait after errors and redirects.
        attempt += 1
        time.sleep(max(0, wait - 3))


def arxiv_metadata(session, identifier, max_attempts=6):
    data = request_data(session, ARXIV_API, params={"id_list": identifier, "max_results": 1},
                        max_attempts=max_attempts)
    entries = ET.fromstring(data).findall("a:entry", ATOM)
    if len(entries) != 1:
        raise ValueError(f"Không có đúng một metadata: {identifier}")
    entry = entries[0]
    returned = entry.findtext("a:id", default="", namespaces=ATOM).split("/abs/")[-1]
    match = re.fullmatch(r"(.+)v([1-9]\d*)", returned)
    if (not match or normalize_id(match.group(1)) != normalize_id(identifier)
            or (re.search(r"v\d+$", identifier) and returned != identifier)):
        raise ValueError(f"Metadata sai ID/phiên bản: yêu cầu {identifier}, nhận {returned}")
    return {"arxiv_id": normalize_id(match.group(1)), "version": int(match.group(2)),
            "title": entry.findtext("a:title", default="", namespaces=ATOM),
            "atom_entry_xml": ET.tostring(entry, encoding="unicode")}


def collect_paper(session, arxiv_id, temp_dir, output_dir, max_attempts=6):
    """Collect all versions, then verify and save the paper to Drive."""
    identifier = normalize_id(arxiv_id)
    temp_dir, output_dir = Path(temp_dir), Path(output_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    local = temp_dir / paper_folder(identifier)
    target = output_dir / paper_folder(identifier)
    if is_complete_paper(target, identifier):
        return target
    if not is_complete_paper(local, identifier):
        latest = arxiv_metadata(session, identifier, max_attempts)
        count = latest["version"]
        versions = []
        for number in range(1, count + 1):
            metadata = latest if number == count else arxiv_metadata(session, f"{identifier}v{number}", max_attempts)
            previous = _reusable_version(local, identifier, number)
            if previous is None:
                archive = temp_dir / f"{identifier}__v{number}.download"
                url = f"https://export.arxiv.org/e-print/{identifier}v{number}"
                print("Tải source:", url)
                request_data(session, url, destination=archive, max_attempts=max_attempts)
                previous = extract_and_filter(archive, temp_dir, identifier, number)
                archive.unlink()
            metadata.update({k: v for k, v in previous.items() if k != "source_directory"})
            atomic_write_json(local / f"metadata/arxiv_v{number}_metadata.json", metadata)
            versions.append(metadata)
        atomic_write_json(local / "metadata/arxiv_versions.json", {
            "arxiv_id": identifier, "version_count": count,
            "versions": versions, "discovered_at": utc_now(),
        })
        marker = local / "metadata/collection_complete.json"
        hashes = {p.relative_to(local).as_posix(): hash_file(p)
                  for p in local.rglob("*") if p.is_file() and p != marker}
        atomic_write_json(marker, {"arxiv_id": identifier, "files": hashes,
                                  "all_versions_collected": True, "collected_at": utc_now()})
    if not is_complete_paper(local, identifier):
        raise ValueError(f"Chưa đủ mọi phiên bản của {identifier}.")
    # Verify the Drive copy before replacing the destination.
    staging_root = output_dir / ".staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=staging_root) as temporary:
        staged = Path(temporary) / target.name
        shutil.copytree(local, staged)
        if not is_complete_paper(staged, identifier):
            raise OSError("Bản sao trên Drive không khớp checksum; không cập nhật downloaded_ids.")
        if target.exists():
            backup = output_dir / "_interrupted" / f"{target.name}_{uuid.uuid4().hex}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(backup))
            print("Giữ đầu ra dở dang tại:", backup)
        os.replace(staged, target)
    return target


def resume_downloads(progress_path, output_dir, temp_dir="/content/temp", *,
                     rescan=False, session=None, max_attempts=6):
    """Skip saved IDs and update progress after each verified Drive save."""
    output_dir = Path(output_dir)
    if not output_dir.is_dir():
        raise NotADirectoryError(f"Mount Drive/kiểm tra thư mục trước: {output_dir}")
    downloaded_ids = initialize_downloaded_ids(progress_path, output_dir, rescan)
    document = read_progress(progress_path)
    identifiers = [record_id(record) for record in document["papers"]]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Danh sách papers có ID trùng.")
    errors = document.setdefault("download_errors", {})
    for identifier in downloaded_ids:
        errors.pop(identifier, None)
    skipped = downloaded = 0
    def save():
        document["downloaded_ids"] = sorted(downloaded_ids)
        document["failed_ids"] = sorted(errors)
        atomic_write_json(progress_path, document)
    save()
    manager = create_session(max_attempts) if session is None else contextlib.nullcontext(session)
    with manager as active_session:
        for identifier in identifiers:
            if identifier in downloaded_ids:
                skipped += 1
                continue
            print("Đang thu thập:", identifier)
            try:
                target = collect_paper(active_session, identifier, Path(temp_dir), output_dir,
                                       max_attempts=max_attempts)
            except (requests.RequestException, ValueError, tarfile.TarError, gzip.BadGzipFile,
                    zipfile.BadZipFile, EOFError, ET.ParseError) as error:
                errors[identifier] = {"error": repr(error), "failed_at": utc_now()}
                save()
                print(f"BỎ QUA {identifier}: {error}")
                continue
            # Stop on storage errors rather than treating them as network failures.
            if not is_complete_paper(target, identifier):
                raise OSError(f"Đầu ra chưa xác minh được trên Drive: {target}")
            downloaded_ids.add(identifier)
            errors.pop(identifier, None)
            downloaded += 1
            save()
            print("Đã lưu trên Drive:", identifier)
    return {"total": len(identifiers), "skipped": skipped, "downloaded": downloaded,
            "failed_ids": sorted(errors)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    local = sub.add_parser("local", help="Nhận diện, giải nén, lọc thư mục 50 bài")
    local.add_argument("input_dir", type=Path)
    local.add_argument("output_dir", type=Path)
    local.add_argument("--expected-papers", type=int, default=50)
    for command in ("scan", "resume"):
        item = sub.add_parser(command)
        item.add_argument("--progress", required=True, type=Path)
        item.add_argument("--output", required=True, type=Path)
        if command == "resume":
            item.add_argument("--temp", type=Path, default=Path("/content/temp"))
            item.add_argument("--rescan", action="store_true")
            item.add_argument("--max-attempts", type=int, default=6)
    args = parser.parse_args(argv)
    if args.command == "local":
        for archive in scan_local_archives(args.input_dir, args.expected_papers):
            extract_and_filter(archive, args.output_dir)
    elif args.command == "scan":
        values = initialize_downloaded_ids(args.progress, args.output, rescan=True)
        print(f"Đã ghi {len(values):,} downloaded_ids vào {args.progress}")
    else:
        result = resume_downloads(args.progress, args.output, args.temp,
                                  rescan=args.rescan, max_attempts=args.max_attempts)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
