# Full-Text Source Download & Figure Pruning

## 1. Dedicated Source Mirror
All full-text archives are fetched strictly via `https://export.arxiv.org/src/{arxiv_id}v{N}`, avoiding the main `arxiv.org` portal to prevent bot flags.

## 2. Archive Types & Extraction
1. **Gzipped Tarballs (`.tar.gz`):** Standard archive containing multiple `.tex` files, `.bib` bibliographies, and figures.
2. **Single Compressed TeX (`.gz`):** A standalone TeX source without bundled figures.
3. **PDF-Only Submissions (~3% of arXiv):** Papers without TeX sources are noted with empty working records rather than discarded.

## 3. File Filtering Policy
To stay within storage limits on CPU Colab instances, only two file types are kept:
* `.tex` and `.bib` files are written to Drive byte-for-byte, so LaTeX macros such as `\begin{figure}` and `\includegraphics` remain intact for AST parsing in Milestone 2.
* Everything else (figures such as `.png`, `.jpg`, `.eps`, `.pdf`, `.svg`, plus `.bbl`, `.sty`, `.cls` and the raw archive) is never written to Drive. Archives are unpacked on local runtime disk first.
* Files other than `.tex`/`.bib` left by earlier runs are removed on resume, without re-downloading.

## 4. Download Performance
The arXiv rule of one connection and at least 3 seconds between requests sets the lower bound: about 3 s per source version.
* **Pipeline:** the main thread only downloads; extraction and Drive writes run in background threads (`DOWNLOAD_WORKERS`, default 2), so each version costs `max(3 s, download time)` instead of download + extraction + Drive writes.
* **Fast resume:** receipts are indexed in `state/download/receipts.jsonl` and saved files are checked by size at start-up (`DOWNLOAD_VERIFY = "sha256"` re-hashes them instead).
* The downloader code lives in `src/02_download.ipynb`, in the same style as `01_discovery.ipynb`; the crawl is started from `src/05_run_pipeline.ipynb`.
