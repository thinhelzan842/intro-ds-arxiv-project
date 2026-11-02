# Source download

Every version of every discovered paper is downloaded from the arXiv source mirror, unpacked, and reduced
to its `.tex` and `.bib` files. Code: `src/02_download.ipynb` (`SourceClient`, `extract_source`,
`download_sources`), tested by 27 offline tests in the same notebook.

## Requests

- One request per version: `https://export.arxiv.org/src/{arxiv_id}v{N}`, so all versions are covered,
  from `v1` to the latest. Automated downloads never go to `arxiv.org`.
- One connection, at least **3 s** between request starts (`ARXIV_DELAY`). Retries go through the same
  gate, so they never break the pacing.
- HTTP 429 and 5xx are retried (up to 4 attempts); the next request waits at least `2^attempt` seconds or
  the server's `Retry-After`, whichever is longer. A 404 is not retried.
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
- At start-up the index is read once and the saved files are checked against it by size (or by SHA-256
  with `DOWNLOAD_VERIFY = "sha256"`); this takes seconds, not a re-hash of the whole corpus.
- Stopping the cell lets the archives already fetched be processed before it exits. A failed version is
  written to `errors.jsonl` and downloaded again on the next run.

## Progress and logs

Two progress bars show the papers done out of every discovered paper (with versions, MB downloaded and
the remaining time) and the file being downloaded (its size and the MB left). The downloader writes
`progress.json`, `run_summary.json`, `run_history.jsonl` and `papers.csv` (one row per paper: versions,
sizes before and after, status, time) to `state/download/`; the pipeline turns them into the
[statistics](statistics.ipynb) and the [benchmark](performance.ipynb).
