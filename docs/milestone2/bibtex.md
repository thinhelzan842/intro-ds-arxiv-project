# BibTeX extraction and reference deduplication

Owner: Member 3. Code: `src/12_bibtex.ipynb` (definitions and 36 offline tests). `parse_paper()`
calls it after the hierarchy is built and before full-text deduplication, because the renamed
`\cite` keys have to be in the element text before identical elements are matched.

```{note}
Every number on this page comes from a **sample of 32 papers (46 versions) measured on a local
machine**. It is a correctness check, not the benchmark. The official numbers will be measured on
Google Colab CPU over the full data of the group and will replace the ones below.
```

## 1. Where the references of a version come from

The parser reads the **gathered** LaTeX of each version (comments removed, `\input`/`\include`
expanded) and gives the version exactly one source label:

| Source label | Rule |
|---|---|
| `bib` | `.bib` files named by `\bibliography{a,b}` or `\addbibresource{x.bib}` (path or base name, case-insensitive) |
| `bibitem` | a `thebibliography` block with `\bibitem` entries written directly in the `.tex` |
| `bbl` | no usable `.bib`: entries recovered from a `.bbl` file, classic or biblatex |
| `missing_bbl` | a bibliography is declared, but neither its `.bib` nor a `.bbl` is in the source folder |
| `none` | no bibliography at all, including empty-source (PDF-only) versions |

The `.bib` parser is our own (standard library only). It handles nested braces, `"..."` values,
`@string` macros, `#` concatenation, `@comment` and `@preamble`, and it skips a broken entry
instead of stopping the file.

**Only cited entries are kept.** A `.bib` file is often a shared library. In the sample, one paper
declares a `.bib` of 864 entries and cites 19 of them. BibTeX prints only cited entries, so the
parser keeps the entries whose key appears in a `\cite`-family command of that version.
`\nocite{*}`, and versions without any `\cite`, keep every entry. The number of dropped entries is
recorded per version.

**About `.bbl` files.** Some authors upload only the compiled `.bbl` and not the `.bib`. We asked
the teacher whether to keep these files; the answer was to try converting the `.bbl` back to
BibTeX, and otherwise to keep the `.bbl` so the references are not lost. The parser therefore
converts both kinds of `.bbl`: the classic one (a `\bibitem` list, read by the same function as
`\bibitem` in a `.tex`) and the biblatex one (`\entry … \endentry` records).

The sample was downloaded **with** `.bbl` files, so it has no `missing_bbl` version. The crawl of
Milestone 1 keeps only `.tex` and `.bib`: on that data the four `bbl` versions of the sample would
be labelled `missing_bbl` and their references would be lost. Following the teacher's answer, the
download step should also keep `.bbl` files (Member 2); the parser is ready for them.

## 2. Converting `\bibitem` to BibTeX

A `\bibitem` is free text, so fields are recovered with regular expressions. The most reliable
rules run first:

1. **Identifiers.** DOI (from `\doi{}`, `doi.org/` links or `doi:` text), URL, arXiv id and year
   (the year in parentheses, a year written right after the title, otherwise the last year in the
   text).
2. **Layout of the text.** Six layouts cover the styles found so far:
   - `\newblock` blocks (natbib/BibTeX styles, and every classic `.bbl`): authors, then title, then venue
   - IEEE: ``` A. Author, ``Title,'' \emph{Venue} ```
   - Springer LNCS: `Author, A.: Title. Venue (year)`
   - small-caps authors (JFM): `\textsc{Author, A. \& Author, B.} 2003 Title. \textit{Journal} …`
   - emphasized title after the authors (amsplain, JHEP): `Authors, \emph{Title}, Venue`, where
     `\bysame` repeats the previous authors and `DES collaboration` counts as an author
   - elsarticle and many math styles: `A. B, C. D, Title, Venue vol (year) pages`

   A text that fits none of them is split as `Authors. Title. Venue.`
3. **Venue.** The emphasized text after the title becomes `journal`, or `booktitle` when the text
   reads `In …`, `Proceedings`, `Conference`, and so on. Volume and pages are read from the rest.

A person name is detected per comma segment: 1–5 capitalized words or initials, with particles
such as *van der* allowed. The raw text of every item is kept in a private field, so nothing is
lost when a rule fails.

The small-caps and collaboration layouts were added after the sample: before that, one paper with
114 JFM-style items had every title wrong. This is why the conversion is checked on real items and
not only on unit tests.

## 3. Deduplication inside and across versions

Every entry of every version is a node. A union–find merges two nodes when **one** rule holds:

1. the same key appears twice in one version;
2. both entries have the same **DOI**;
3. both entries have the same **arXiv id**, taken from `eprint`, the URL, `arXiv preprint …`, or an arXiv DOI;
4. both entries have the same **normalized title** (LaTeX and accents removed, lower case, only
   letters and digits, so `Rayleigh-Bénard` and `Rayleigh--B\'enard` are equal) and compatible
   years: equal, or one is missing. Titles shorter than four words also need the same first-author
   surname;
5. the **same key appears in two versions**, **both** entries have a title, and the titles share at
   least 60% of their words. Purely numeric keys (`15`) never use this rule, because numbered
   reference lists are renumbered between versions.

Rules 2–4 are what the statement asks for: entries that point to the same underlying reference.
**Rule 5 is a choice of our group**, not a requirement of the statement. It only catches a title
that was edited between versions while the key stayed the same, and it never merges on the key
alone. An entry without a title is not merged by its key.

A merge is **refused** when the two groups carry different DOIs or different arXiv ids. This keeps
apart two different works that share a generic title.

For each group, the **chosen key** is the key used in the newest version. When that version has
two duplicate keys, the one cited most often wins. The **fields are unioned** over all members,
and newer values win on conflicts. If the same key names two different works, the older one gets
a suffix (`smith_2`). The keys that change are written to `key_map`, and every merge is logged
with its rule and the two `(version, key)` pairs, so each rule can be audited.

The statement's example is one of the tests. Version 1 cites `vaswani2017`, and versions 2 and 3
cite `vit_transformer`, with a DOI added in version 2 and `year` dropped in version 3. The result
is one row keyed `vit_transformer` with title, author, year and DOI, and
`key_map = {1: {vaswani2017 → vit_transformer}}`.

## 4. Renaming the cite keys

`rename_cites(text, key_map[v])` rewrites `\cite`, `\citep`, `\citet`, `\citeauthor`, `\nocite`,
their starred forms, biblatex `\parencite`, `\textcite` and multi-cite `\cites`. It keeps the
optional arguments (`\citep[see][p.~5]{a,b}`), leaves unknown keys untouched, and writes a key
only once when two old keys map to the same new one. `cited_keys(text)` counts the keys in use.

```{important}
`rename_cites` must be applied **exactly once** to the text of each version. A key map can chain.
In the sample, an author renumbered two references between versions, so the map of version 1 is
`Shevkar2025 → Shevkar2025a` together with `Shevkar2025a → Shevkar2025b`. One pass gives every
`\cite` its new key; a second pass would rename `Shevkar2025` twice.
```

## 5. Output

`process_paper_bib(arxiv_id, {version: (version_dir, gathered_tex)})` returns the rows of one paper.
`build_bibtex_tables(data_dir, out_dir, limit=None)` runs every paper folder and writes the tables
as Parquet (JSON lines without `pyarrow`). A paper that raises is recorded in `bib_errors` and the
run continues.

| Table | Content |
|---|---|
| `bibtex` | the 9 columns of the statement: `arxiv_id, citation_key, entry_type, title, authors (list), year (int, nullable), doi, journal, url`. `journal` falls back to `booktitle`, and `url` to the arXiv abstract page when only an arXiv id is known |
| `bib_key_map` | `arxiv_id, version, old_key, new_key` for every renamed key |
| `bib_version_stats` | source label, entries read, entries kept, uncited entries dropped, cited keys, cited keys without an entry |
| `bib_paper_stats` | entries before and after deduplication, renamed keys, merges per rule, seconds |
| `bib_merges` | one row per merge: the rule and the two `(version, key)` pairs |
| `bib_errors` | papers that failed, with the error message |

## 6. Check on a real sample (32 papers, local machine)

`tools/fetch_bib_sample.py` downloaded 32 papers of our ID ranges from `export.arxiv.org/src`
(46 versions, 12 papers with two or three versions, one PDF-only paper; one request every 3 s),
keeping `.tex`, `.bib` and `.bbl`. The table below is this sample only.

| Quantity (sample of 32 papers) | Value |
|---|---|
| Versions by source | 33 `bib`, 7 `bibitem`, 4 `bbl`, 0 `missing_bbl`, 2 `none` |
| Entries read | 3,513 |
| Uncited `.bib` entries dropped | 1,493 |
| Entries before deduplication (summed over versions) | 2,020 |
| Entries after deduplication | 1,393 (−31%) |
| Merges by rule | 388 title + year, 195 arXiv id, 31 DOI, 13 duplicate key in one version, 0 same key across versions |
| Renamed keys | 7 |
| Papers with an error | 0 |
| Run time on a local machine | 4.2 s for the 32 papers, file reading included |

What was checked by hand:

- **`\bibitem` conversion.** 45 random items from `\bibitem` and `.bbl` sources: title, authors
  and year are right in all of them. A screen of all 353 such items found no wrong row. All 353
  have a title and authors, 261 have a year and 259 a venue; most items without a year are
  preprints cited by arXiv id only.
- **`.bbl` against the true `.bib`.** One paper has only a `.bbl` in version 1 and the `.bib` in
  version 2. Of the 62 entries converted from the `.bbl`, 61 merge with their `.bib` entry (the
  last one is no longer cited in version 2).
- **Merges with different keys.** Four groups, all correct: one pair of keys with the same DOI,
  and three references whose key suffix changed between versions (`Samuel2024 → Samuel2024b`).
- **Renaming.** Of 2,006 cited keys, 7 are renamed, and after `rename_cites` every `\cite` carries
  the chosen key. One cited key, in both versions of one paper, has no entry in the source; the
  parser leaves it as it is.
- **Rule 5.** It made no merge in this sample, and no entry without a title shared its key across
  versions.

The sample is small: only 12 papers have several versions. The figures of this chapter are built
from the `bib_*` tables of the full run.

## 7. Running it

```python
RUN_TEST = False
%run -i ./12_bibtex.ipynb
written, tables, errors = build_bibtex_tables(DATA_DIR, PROJECT_ROOT / "data" / "parsed" / "bibtex", limit=500)
summary = bibtex_summary(tables, errors)   # source labels, entries before/after, renamed keys, errors
```

With `limit=None` the whole corpus is processed. Opening the notebook on its own (`RUN_TEST = True`)
runs the 36 offline tests first, then the same run on the first 500 paper folders when `DATA_DIR`
holds crawled sources.
