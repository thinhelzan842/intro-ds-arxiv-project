# Source download

*Author: Võ Nguyễn Vân Anh · code: `src/02_download.ipynb`*

Every version of every discovered paper is downloaded from the arXiv source mirror, unpacked, and reduced
to its `.tex` and `.bib` files. Code: `src/02_download.ipynb` (`SourceClient`, `extract_source`,
`download_sources`), tested by 46 offline tests in the same notebook.

## Requests

- One request per version: `https://export.arxiv.org/src/{arxiv_id}v{N}`, so all versions are covered,
  from `v1` to the latest. Automated downloads never go to `arxiv.org`.
- One connection, at least **3 s** between request starts (`ARXIV_DELAY`). Retries go through the same
  gate, so they never break the pacing.
- A 404 or another 4xx is not retried: the version is marked failed (and asked again in the next run).
- HTTP 429 (arXiv's rate limit: `Rate exceeded.` per IP over a short window, and Colab IPs are shared), HTTP
  5xx, a timeout or a connection lost before any byte arrived is not a problem of the version, so it is not
  marked failed and is **never retried at once**. After that one request the crawl moves on to the next
  version and puts the refused one back at the end of the same run (up to 3 times; after that it waits for the
  next run). The next request often succeeds, so the crawl keeps downloading instead of waiting on one version.
  The spacing stays `ARXIV_DELAY` (3 s): a 429 does not slow the crawl down.
  No cooldown either: only a `Retry-After` sent by arXiv is honoured, and after 50 in a row the run stops with a message to switch runtime: that IP is rate-limited.
- The one retry in place: arXiv often cuts long transfers (`IncompleteRead`). When part of the file has
  arrived and the server sent an `ETag`, the retry asks only for the missing bytes with an HTTP `Range`
  request, guarded by `If-Range` on the `ETag` (a changed file starts over), instead of the whole archive
  again (moving on would throw those bytes away).
- When such a cut transfer still fails after its last attempt (4), the next
  request waits a cooldown: 10 s, doubled after each such failure up to 60 s, reset by the next successful
  download. A period of throttling then costs a few pauses instead of dozens of failed versions to redo later;
  a normal download never waits for it.
- The archive is streamed in 1 MB blocks to the runtime's **local disk** (`/tmp`), not to Google Drive.

## What a source can be, and what is kept

`extract_source` recognises the content, not the file name:

| arXiv returns | Result |
|---|---|
| TAR (any compression) or ZIP with `.tex` files | the `.tex` and `.bib` files, with their folder structure |
| one gzip / bzip2 / xz-compressed or plain TeX file | `main.tex` |
| PDF or Word file (no source) | empty `vN/` folder, status `empty_source` |
| HTML or JSON (an error page served with HTTP 200) | rejected, retried on the next run |

Only **`.tex` and `.bib`** are written to Drive, byte for byte, so `figure` environments and
`\includegraphics` lines stay untouched for the parsing milestone. Figures, PDFs, `.bbl`, `.sty`, `.cls`
and the archive itself never reach Drive. An archive without any `.tex` file keeps nothing (a lone `.bib`
is not a usable source).

**Safety.** Every path in an archive is checked before anything is written: absolute paths, `..`, links
and special files are rejected, as is a file whose path is also used as a folder. A single text file is
limited to 128 MB.

**Names that differ only in case.** A real archive (`2609.32867v1`) contains both
`sections/limitations.tex` and `sections/Limitations.tex`, with different text. Both are kept. On a
case-insensitive disk the second one is stored as `Limitations~2.tex` and the receipt records the original
name. A name listed twice in a TAR keeps its last copy, as `tar` does.

## Pipelined downloads

The 3 s pacing is the floor for any compliant scraper, so the download is organised to add nothing to it:

```text
main thread     fetch v1 ─3 s─ fetch v2 ─3 s─ fetch v3 ─3 s─ ...      (only network)
worker 1               └ unpack, copy .tex/.bib to Drive, receipt
worker 2                              └ unpack, copy .tex/.bib to Drive, receipt
```

Unpacking and the slow writes to Google Drive run in two worker threads (`DOWNLOAD_WORKERS`) while the
main thread waits for the next request slot. At most `2 × DOWNLOAD_WORKERS` fetched archives wait for a
worker, which bounds the space used in `/tmp`. Each version therefore costs about `max(3 s, transfer time)`
instead of transfer + unpacking + Drive writes.

## Resuming after a disconnect

A free Colab session lasts at most about 12 hours, and the full crawl needs more than one session.

- Every finished version gets a **receipt** (sizes and SHA-256 of the kept files) in
  `state/download/receipts/<id>/vN.json`, also appended to the index `state/download/receipts.jsonl`.
- A version is written to a staging folder and renamed into place only when complete, so an interrupted
  version is never mistaken for a finished one.
- At start-up the index is read once and trusted (`DOWNLOAD_VERIFY = "receipt"`), because a receipt is written
  only after its version was renamed into place; this takes seconds. Checking the saved files themselves costs
  ~17 Drive calls per version (about 10-30 ms each), hours for the whole corpus, so `"size"` (sizes) and
  `"sha256"` (re-hash) are for an occasional full check, e.g. after a session Colab killed before Drive synced.
- Stopping the cell lets the archives already fetched be processed before it exits. A failed version is
  written to `errors.jsonl` and downloaded again on the next run.
- Every request is logged in `attempts.jsonl` before it is sent, so each run starts with the versions never
  requested. Versions requested before but not finished (404, throttled, cut, or the run was stopped or killed
  mid-download) come after them, the least-tried first, so a new session does not open with the same failures.

**Failures that would hit every version.** The run stops early, with the reason, instead of failing (and
requesting) every remaining version: at once on a storage error (Google Drive or the local disk full, Drive
unmounted), and after 20 failed versions in a row (arXiv, the network or Drive down). An HTTP 404/410 (arXiv
has no source for that version, e.g. a withdrawn one) does not count: those versions are retried in a row at the end
of a run, and counting them would stop it. Before the first request
it checks that Drive and `/tmp` have room for the rest of the crawl. Staging folders left by a killed run are
removed at start-up. A lock file with a heartbeat (`pipeline.lock`, `download.lock`) refuses a second runtime
working on the same Drive folder, and is taken over once the other runtime has been gone for 3 minutes. At
the end of a session the pipeline flushes Google Drive, whose writes are asynchronous.

## Progress and logs

Two progress bars show the papers done out of every discovered paper (with versions, MB downloaded and
the remaining time) and the file being downloaded (its size and the MB left). The downloader writes
`progress.json`, `run_summary.json`, `run_history.jsonl` and `papers.csv` (one row per paper: versions,
sizes before and after, status, time) to `state/download/`; the pipeline turns them into the
[statistics](statistics.ipynb) and the [benchmark](performance.ipynb).

Two more files there record what went wrong, one JSON line per event:

- `errors.jsonl`: a version that **failed** (it is asked for again in the next run);
- `throttles.jsonl`: a request arXiv **refused** (HTTP 429/5xx) or did not answer; not a failure of the
  version, which goes back to the end of the queue.

Every line carries `arxiv_id`, `version`, the HTTP `status` (or `null`), the time and an `error_kind` label,
set by `error_kind()` in `02_download.ipynb`:

| `error_kind` | Meaning | File |
|---|---|---|
| `HTTP_429`, `HTTP_5XX` | arXiv rate-limited the IP or was busy | `throttles.jsonl` |
| `TIMEOUT`, `NO_CONNECTION` | no answer, or the connection was lost before any byte arrived | `throttles.jsonl` |
| `NOT_FOUND` | HTTP 404/410: arXiv has no source for this version (e.g. withdrawn) | `errors.jsonl` |
| `HTTP_<code>` | another HTTP 4xx (e.g. `HTTP_403`) | `errors.jsonl` |
| `TRANSFER_CUT` | a transfer cut midway that still failed after its `Range` retries | `errors.jsonl` |
| `EMPTY_RESPONSE`, `MARKUP_RESPONSE` | an empty body, or an HTML/JSON error page served with HTTP 200 | `errors.jsonl` |
| `CORRUPT_ARCHIVE` | an archive that cannot be unpacked (broken TAR, ZIP, gzip or xz data) | `errors.jsonl` |
| `REJECTED_ARCHIVE` | an unsafe path, a link or special file, or a text file over 128 MB | `errors.jsonl` |
| `STORAGE`, `IO_ERROR` | Google Drive or the local disk full or unmounted, another file-system error | `errors.jsonl` |

Lines written before this label existed have only `error` (the exception text).
