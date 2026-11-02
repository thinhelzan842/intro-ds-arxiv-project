# Full-Text Source Download & Figure Pruning

## 1. Dedicated Source Mirror
All full-text archives are fetched strictly via `https://export.arxiv.org/src/{arxiv_id}v{N}`, avoiding the main `arxiv.org` portal to prevent bot flags.

## 2. Archive Types & Extraction
1. **Gzipped Tarballs (`.tar.gz`):** Standard archive containing multiple `.tex` files, `.bib` bibliographies, and figures.
2. **Single Compressed TeX (`.gz`):** A standalone TeX source without bundled figures.
3. **PDF-Only Submissions (~3% of arXiv):** Papers without TeX sources are noted with empty working records rather than discarded.

## 3. Figure Pruning Policy
To stay within storage limits on CPU Colab instances:
* Figures (`.png`, `.jpg`, `.jpeg`, `.eps`, `.pdf`, `.svg`) are pruned upon extraction.
* `.tex` and `.bib` files remain completely untouched, ensuring LaTeX macros such as `\begin{figure}` and `\includegraphics` remain intact for AST parsing in Milestone 2.
