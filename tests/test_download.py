"""Offline contract tests for the member-2 source downloader."""

import gzip
import ast
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from src import download


TEX = b"\\documentclass{article}\n\\begin{figure}\\includegraphics{plot}\n"


def tar_bytes(files):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as archive:
        for name, content in files:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return out.getvalue()


class FakeResponse:
    def __init__(self, content, status=200, headers=None):
        self.content = content
        self.status_code = status
        self.headers = headers or {}

    def iter_content(self, chunk_size):
        yield self.content

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)

    def close(self):
        pass


class DownloaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_manifest_accepts_group_discovery_schema(self):
        path = self.root / "manifest.json"
        path.write_text(json.dumps({"papers": [
            {"id": "2603.20580", "versions": 2, "title": "sample", "status": "ok"},
            {"id": "2603.20581", "versions": 0, "status": "not_found"},
        ]}), encoding="utf-8")
        records = download.load_manifest(path)
        self.assertEqual(records[0]["arxiv_id"], "2603.20580")
        self.assertEqual(records[0]["version_count"], 2)
        self.assertEqual(records[0]["title"], "sample")
        self.assertEqual(records[1]["version_count"], 0)

    def test_manifest_rejects_duplicate_and_bad_version_count(self):
        for records in (
            [{"arxiv_id": "2603.20580", "version_count": 1}] * 2,
            [{"id": "2603.20580", "versions": 0, "status": "ok"}],
            [{"arxiv_id": "2603.00000", "version_count": 1}],
        ):
            with self.subTest(records=records), self.assertRaises(ValueError):
                download.validate_manifest(records)

    def test_discovery_error_with_no_versions_stays_pending(self):
        records = download.validate_manifest([{"id": "2603.20580", "versions": 0, "status": "error"}])
        self.assertEqual(records[0]["version_count"], 0)
        self.assertEqual(download._progress(records, {})["papers_percent"], 0.0)

    def test_429_retry_after_and_request_pacing(self):
        session = FakeSession([FakeResponse(b"busy", 429, {"Retry-After": "5"}), FakeResponse(b"abc")])
        current = [0.0]
        def sleep(seconds):
            current[0] += seconds
        starts = []
        original_get = session.get
        def observed_get(url, **kwargs):
            starts.append(current[0])
            return original_get(url, **kwargs)
        session.get = observed_get
        client = download.SourceClient(session, "CourseBot/1.0 (contact@example.org)", clock=lambda: current[0], sleeper=sleep)
        target = self.root / "raw.bin"
        self.assertEqual(client.fetch("2603.20580", 2, target), 3)
        self.assertEqual(starts, [0.0, 5.0])
        self.assertEqual(target.read_bytes(), b"abc")
        self.assertEqual([c[0] for c in session.calls], ["https://export.arxiv.org/src/2603.20580v2"] * 2)
        self.assertEqual(session.headers["User-Agent"], "CourseBot/1.0 (contact@example.org)")

    def test_final_429_cooldown_applies_to_next_version(self):
        session = FakeSession([FakeResponse(b"busy", 429, {"Retry-After": "90"}), FakeResponse(b"ok")])
        now = [0.0]
        starts = []
        original = session.get
        def get(url, **kwargs):
            starts.append(now[0])
            return original(url, **kwargs)
        session.get = get
        client = download.SourceClient(session, max_attempts=1, clock=lambda: now[0], sleeper=lambda s: now.__setitem__(0, now[0] + s))
        with self.assertRaises(Exception):
            client.fetch("2603.20580", 1, self.root / "raw1")
        client.fetch("2603.20580", 2, self.root / "raw2")
        self.assertEqual(starts, [0.0, 90.0])

    def test_nonretryable_404_is_sent_once(self):
        session = FakeSession([FakeResponse(b"missing", 404)])
        client = download.SourceClient(session, sleeper=lambda seconds: None)
        with self.assertRaises(Exception):
            client.fetch("2603.20580", 1, self.root / "raw")
        self.assertEqual(len(session.calls), 1)

    def test_tar_keeps_tex_bytes_and_skips_figures(self):
        raw = self.root / "raw"
        raw.write_bytes(tar_bytes([("sub/main.tex", TEX), ("sub/refs.bib", b"@book{a}"), ("sub/pic.PNG", b"image"), ("sub/plot.pdf", b"%PDF")]))
        target = self.root / "v1"
        info = download.extract_source(raw, target)
        self.assertEqual(info["status"], "ok")
        self.assertEqual((target / "sub/main.tex").read_bytes(), TEX)
        self.assertEqual({p.suffix for p in target.rglob("*") if p.is_file()}, {".tex", ".bib"})
        self.assertEqual(info["before_bytes"], len(TEX) + len(b"@book{a}") + 5 + 4)
        self.assertEqual(info["after_bytes"], len(TEX) + len(b"@book{a}"))

    def test_gzip_single_tex_and_pdf_empty(self):
        raw = self.root / "raw"
        raw.write_bytes(gzip.compress(TEX))
        self.assertEqual(download.extract_source(raw, self.root / "v1")["status"], "ok")
        self.assertEqual((self.root / "v1/main.tex").read_bytes(), TEX)
        raw.write_bytes(b"%PDF-1.7\nxxx")
        info = download.extract_source(raw, self.root / "v2")
        self.assertEqual(info["status"], "empty_source")
        self.assertEqual(list((self.root / "v2").iterdir()), [])

    def test_single_tex_after_long_comment_is_kept(self):
        content = (b"% comment\n" * 1200) + TEX
        raw = self.root / "raw"
        for payload, folder in ((content, "plain"), (gzip.compress(content), "gz")):
            raw.write_bytes(payload)
            info = download.extract_source(raw, self.root / folder)
            self.assertEqual(info["status"], "ok")
            self.assertEqual((self.root / folder / "main.tex").read_bytes(), content)

    def test_unrecognized_success_body_is_not_cached_as_empty(self):
        raw = self.root / "raw"
        for payload in (b"<html>temporary gateway error</html>", b"nonsense bytes"):
            raw.write_bytes(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                download.extract_source(raw, self.root / "v1")

    def test_single_gzip_source_is_bounded_during_decompression(self):
        raw = self.root / "raw"
        raw.write_bytes(gzip.compress(TEX + b"x" * 100))
        original = download.MAX_TEXT_BYTES
        download.MAX_TEXT_BYTES = len(TEX) + 10
        try:
            with patch.object(download.tempfile, "TemporaryFile", side_effect=AssertionError("oversized source staged")), self.assertRaises(ValueError):
                download.extract_source(raw, self.root / "v1")
        finally:
            download.MAX_TEXT_BYTES = original

    def test_assigned_manifest_coverage_rejects_truncated_cache(self):
        self.assertEqual(len(download.assigned_ids()), 20000)
        complete = [{"id": identifier, "versions": 1} for identifier in download.assigned_ids()]
        self.assertEqual(len(download.validate_assigned_manifest(complete)), 20000)
        with self.assertRaises(ValueError):
            download.validate_assigned_manifest([{"id": "2603.20580", "versions": 1}])

    def test_unsafe_tar_and_duplicate_zip_are_rejected(self):
        raw = self.root / "raw"
        raw.write_bytes(tar_bytes([("../escape.tex", TEX)]))
        with self.assertRaises(ValueError):
            download.extract_source(raw, self.root / "unsafe")
        self.assertFalse((self.root / "escape.tex").exists())
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("A.tex", TEX)
            archive.writestr("a.tex", TEX)
        raw.write_bytes(out.getvalue())
        with self.assertRaises(ValueError):
            download.extract_source(raw, self.root / "duplicate")

    def test_zip_symlink_is_rejected(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("main.tex", TEX)
            member = zipfile.ZipInfo("link.tex")
            member.create_system = 3
            member.external_attr = 0o120777 << 16
            archive.writestr(member, "main.tex")
        raw = self.root / "raw"
        raw.write_bytes(out.getvalue())
        with self.assertRaises(ValueError):
            download.extract_source(raw, self.root / "v1")

    def test_tar_with_dot_prefix_is_accepted(self):
        raw = self.root / "raw"
        raw.write_bytes(tar_bytes([("./main.tex", TEX), ("./fig.png", b"image")]))
        info = download.extract_source(raw, self.root / "v1")
        self.assertEqual(info["status"], "ok")
        self.assertEqual((self.root / "v1/main.tex").read_bytes(), TEX)

    def test_archive_download_uses_runtime_temp_not_output_drive(self):
        output, state = self.root / "output", self.root / "state"
        seen = []
        class Client:
            def fetch(self, identifier, version, destination):
                seen.append(Path(destination))
                payload = tar_bytes([("main.tex", TEX), ("image.png", b"large image")])
                Path(destination).write_bytes(payload)
                return len(payload)
        download.collect_one(Client(), {"arxiv_id": "2603.20580"}, 1, output, state)
        self.assertFalse(seen[0].is_relative_to(output))
        self.assertEqual((output / "2603-20580/v1/main.tex").read_bytes(), TEX)

    def test_interruption_preserves_previous_version_receipt(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps([{"id": "2603.20580", "versions": 2}]), encoding="utf-8")
        class InterruptSession(FakeSession):
            def get(self, url, **kwargs):
                if len(self.calls) == 1:
                    raise KeyboardInterrupt()
                return super().get(url, **kwargs)
        first = download.run(manifest, self.root / "out", self.root / "state",
                             session=InterruptSession([FakeResponse(tar_bytes([("main.tex", TEX)]))]),
                             sleeper=lambda s: None)
        self.assertTrue(first["interrupted"])
        self.assertEqual(first["progress"]["versions_percent"], 50.0)
        later = download.run(manifest, self.root / "out", self.root / "state",
                             session=FakeSession([FakeResponse(tar_bytes([("main.tex", TEX)]))]),
                             sleeper=lambda s: None)
        self.assertEqual(later["versions_skipped"], 1)
        self.assertEqual(later["progress"]["versions_percent"], 100.0)

    def test_resume_verifies_receipt_and_reports_percent(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps([{"arxiv_id": "2603.20580", "version_count": 2}]), encoding="utf-8")
        out, state = self.root / "output", self.root / "state"
        session = FakeSession([FakeResponse(tar_bytes([("main.tex", TEX)])), FakeResponse(b"%PDF-1.7\n")])
        first = download.run(manifest, out, state, session=session, delay=3, sleeper=lambda s: None)
        self.assertEqual(first["progress"]["papers_percent"], 100.0)
        self.assertEqual(first["progress"]["versions_percent"], 100.0)
        self.assertEqual(first["versions_ok"], 1)
        self.assertEqual(first["versions_empty"], 1)
        with (state / "papers.csv").open(newline="", encoding="utf-8") as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row["id"], "2603.20580")
        self.assertEqual(row["versions"], "2")
        self.assertEqual(row["versions_ok"], "1")
        self.assertEqual(row["size_after"], str(len(TEX)))
        self.assertEqual(row["status"], "partial")
        again = download.run(manifest, out, state, session=FakeSession([]), delay=3, sleeper=lambda s: None)
        self.assertEqual(again["versions_skipped"], 2)
        (out / "2603-20580/v1/main.tex").write_bytes(b"corrupt")
        repaired = download.run(manifest, out, state, session=FakeSession([FakeResponse(tar_bytes([("main.tex", TEX)]))]), delay=3, sleeper=lambda s: None)
        self.assertEqual(repaired["versions_skipped"], 1)
        self.assertEqual((out / "2603-20580/v1/main.tex").read_bytes(), TEX)

    def test_failed_version_is_retried_on_next_run(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps([{"arxiv_id": "2603.20580", "version_count": 1}]), encoding="utf-8")
        output, state = self.root / "output", self.root / "state"
        failed = download.run(manifest, output, state, session=FakeSession([FakeResponse(b"missing", 404)]), sleeper=lambda s: None)
        self.assertEqual(failed["progress"]["versions_percent"], 0.0)
        self.assertEqual(failed["versions_failed_this_run"], 1)
        recovered = download.run(manifest, output, state, session=FakeSession([FakeResponse(tar_bytes([("main.tex", TEX)]))]), sleeper=lambda s: None)
        self.assertEqual(recovered["progress"]["versions_percent"], 100.0)
        self.assertGreaterEqual(recovered["disk_peak_estimate_bytes"], recovered["output_bytes"])
        history = (state / "run_history.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(history), 2)
        self.assertEqual([json.loads(line)["progress"]["versions_percent"] for line in history], [0.0, 100.0])

    def test_root_cli_exposes_manifest_arguments(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / "download.py"), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--manifest", result.stdout)
        self.assertIn("--state", result.stdout)

    def test_colab_notebooks_have_two_valid_code_cells(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root / "arxiv_colab_2_cells.ipynb", root / "src/02_download.ipynb"):
            with self.subTest(path=path):
                notebook = json.loads(path.read_text(encoding="utf-8"))
                code = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
                self.assertEqual(len(code), 2)
                for cell in code:
                    ast.parse("".join(cell["source"]))


if __name__ == "__main__":
    unittest.main()
