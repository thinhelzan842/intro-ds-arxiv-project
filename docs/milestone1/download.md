# Source download

Every version of every discovered paper is downloaded from the arXiv source mirror, unpacked, and reduced
to its `.tex` and `.bib` files. Code: `src/02_download.ipynb` (`SourceClient`, `extract_source`,
`download_sources`), tested by 27 offline tests in the same notebook.

## Requests

- One request per version: `https://export.arxiv.org/src/{arxiv_id}v{N}`, so all versions are covered,
  from `v1` to the latest. Automated downloads never go to `arxiv.org`.
- One connection, at least **3 s** between request starts (`ARXIV_DELAY`). Retries go through the same
  gate, so they never break the pacing.
- HTTP 5xx is retried (up to 4 attempts); the next request waits at least `2^attempt` seconds or
  the server's `Retry-After`, whichever is longer. A 404 is not retried.
- HTTP 429 (arXiv's rate limit) is not a problem of the version: it uses up no attempt and the version is not
  marked failed. The client waits a cooldown (30 s, doubled after each 429 in a row up to 10 min, or
  `Retry-After` if longer) and asks for the same version again. Each 429 also doubles the spacing between
  requests (3 s up to 60 s), and each success brings it 10% back towards 3 s, so the crawl settles near the rate
  arXiv accepts instead of alternating bursts of refused requests and 10-minute pauses. After 50 answers 429 in
  a row without a success, a 429 counts as a normal failure again.
- arXiv often cuts long transfers (`IncompleteRead`). The retry then asks only for the missing bytes with an
  HTTP `Range` request, guarded by `If-Range` on the `ETag` (a changed file starts over), instead of the whole
  archive again.
- When a version still fails on a 5xx or a cut connection after its last attempt, the next
  request waits a cooldown: 30 s, doubled after each such failure up to 10 min, reset by the next successful
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
