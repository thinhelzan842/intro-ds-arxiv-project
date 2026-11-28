# BibTeX extraction and reference deduplication

Owner: Member 3. Code: `src/12_bibtex.ipynb` (definitions and 41 offline tests). `parse_paper()`
calls it after the hierarchy is built and before full-text deduplication, because the renamed
`\cite` keys have to be in the element text before identical elements are matched.

```{note}
Sections 1–5 describe the method. Section 6 is the check on a **sample of 32 papers** made while the
parser was written (local machine); section 7 gives the numbers of the **full run on Google Colab**
(20,000 papers, parser `13.9`) and the history of the parser versions. The charts of the full run are on
the page *Parsing statistics*.
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
Milestone 1 kept only `.tex` and `.bib`, as the statement asks: on the full data, **2,231 of the
25,767 versions with LaTeX (8.7%) are `missing_bbl`** (section 7), and their references are not in the
`bibtex` table. Getting them back means downloading these versions again and keeping their `.bbl`
(about two hours at one request every 3 s), then parsing them again; the parser is ready for them. We
record it as the main known loss of Milestone 2.

## 2. Converting `\bibitem` to BibTeX

A `\bibitem` is free text, so fields are recovered with regular expressions, except in one style.
**REVTeX** (`apsrev4-1`/`4-2`, the Physical Review styles, often pasted from the `.bbl` into the
`.tex`) wraps every field in `\bibinfo{author}{…}`, `\bibinfo{title}{…}`, `\bibinfo{journal}{…}`
between `\BibitemOpen` and `\BibitemShut{NoStop}`: since parser 13.9 these fields are read directly
(`revtex_to_fields`), and a REVTeX item without `\bibinfo` is parsed as free text once the macros are
removed. For every other item, the most reliable rules run first:

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

The sample is small: only 12 papers have several versions, which is why the full run below matters.

## 7. Full run (Google Colab) and parser versions

`src/15_run_parsing.ipynb` parsed the 20,000 papers of the group on Google Colab CPU (6 sessions,
4.2 h of wall time, see *Parsing statistics*). Numbers from `logs/m2_stats.json`, parser
`13.9|10:team|11:team|12:team`:

| Quantity (full run, 20,000 papers) | Value |
|---|---|
| Versions in `metadata.json` / with a `.tex` file | 27,035 / 25,767 |
| Versions parsed (`ok`) / `empty_source` / `no_root` | 25,760 / 1,268 / 7 |
| Parse success rate: versions with a `.tex` file / all versions | 99.97% / 95.28% |
| `empty_source` reasons | PDF only 1,165; source not found on arXiv (HTTP 404) 100; not downloaded 3 |
| Source of the references (versions with a `.tex` file) | `bib` 18,577; `bibitem` 4,463; `missing_bbl` 2,231; `none` 496 |
| BibTeX entries before → after deduplication | 1,023,822 → 766,398 (−25.1%) |

The versions that arXiv lists but serves no source for (HTTP 404) are kept as empty records, like the
PDF-only versions, as the teacher advised. `none` means that the parser found no bibliography: no
`.bib` declared and no `thebibliography` block. It includes the few papers whose authors typed their
references by hand under a `\section{References}` heading; the parser does not read those lists.

**Parser versions.** The output of `parse_paper` carries a version (`PARSER_BASE` of `13`); a new
version parses again only the papers it can change (`CARRY_OVER` in `15`), and a random sample of the
other papers is parsed again to prove that their files are unchanged.

| Version | Change | Papers parsed again | Check |
|---|---|---|---|
| 13.7 (21 Nov) | first full run | 20,000 | — |
| 13.8 (22 Nov) | `10` reads CR-only and CRLF files; `11` no longer cuts the text after a nested macro definition | 1,775 (a `.tex` with a carriage return or such a definition) | sample of 300 others unchanged; 436 papers changed, all in the list |
| 13.9 (27 Nov) | `12` reads the `\bibinfo` fields of REVTeX items | 190 (`\BibitemOpen` in a `.tex` or `.bbl` of any version) | sample of 300 others plus the 20 manually labelled papers of Milestone 3: unchanged |

Before 13.9, a REVTeX item was read as free text and the macro names ended up in the fields (a
title such as `BibitemOpen K. Ahnert and A. Pikovsky, …`, a journal `Lett`). On the 190 papers, the
entries with a macro name in their title or authors went from 10,727 to 0, the entries with authors
from 6,282 to 11,325, and all 11,597 items that carry a `\bibinfo{title}` now have their title; the
3,755 items without one (journal, volume and page only, the usual Physical Review style) now have no
title instead of a wrong one. The parser version is locked for the labels of Milestone 3, which are
keyed by `(arxiv_id, citation_key)`; the labels made on 13.8 stay valid because 13.9 changed none of
the labelled papers.

## 8. Interface with `13_dedup_export`

`parse_paper()` of notebook 13 loads this notebook with `%run -i` and calls four functions:

| Function | Returns |
|---|---|
| `extract_bib(vdir, raw_text)` | `list[dict]` with the keys `citation_key, entry_type, title, authors, year, doi, journal, url` |
| `bib_source(vdir, raw_text)` | `bib`, `bibitem`, `bbl`, `missing_bbl` or `none` |
| `dedup_bib(by_version)` | `(entries, key_map)` with `key_map = {version: {old_key: chosen_key}}` |
| `rename_cites(text, key_map)` | the text with renamed cite keys |

They wrap the functions of the sections above. Every dict also carries the original entry in a
key that starts with `_` (notebook 13 ignores unknown keys), so deduplication still unions every
field of the `.bib` entry and not only the eight columns of the table.

The key map is **per version**, for the reason given in section 4: `parse_paper` should call
`rename_cites(text, key_map.get(version, {}))`. When the whole map is passed instead, only the
renames that are the same in every version are applied and the ambiguous keys are left as they
are.

`tools/check_bib_contract.py` runs `parse_paper` on the sample with this notebook loaded and
compares it with the standalone run on the same gathered text. On the sample of 32 papers (local
machine) both give 2,009 entries before deduplication and 1,393 after, the same `bibtex` rows and
the same source labels. The count before deduplication is 2,009 here and 2,020 in section 6
because section 6 reads every `.tex` file of a version, while `parse_paper` reads only the root
file and what it includes: one paper has a supplementary `.tex` with its own `.bib` that the root
does not include. With the per-version call, no element cites a replaced key; with the whole map,
two versions of one paper keep such a key (the shifted keys of section 4). The script also checks
that no helper name of this notebook is defined by another notebook, because notebooks loaded with
`%run -i` share one namespace.

## 9. Running it

```python
RUN_TEST = False
%run -i ./12_bibtex.ipynb
written, tables, errors = build_bibtex_tables(DATA_DIR, PROJECT_ROOT / "data" / "parsed" / "bibtex", limit=500)
summary = bibtex_summary(tables, errors)   # source labels, entries before/after, renamed keys, errors
```

With `limit=None` the whole corpus is processed. Opening the notebook on its own (`RUN_TEST = True`)
runs the 41 offline tests first, then the same run on the first 500 paper folders when `DATA_DIR`
holds crawled sources.
