# 📚 arXiv Paper Corpus & Reference Matching Pipeline
> **Course:** Introduction to Data Science (HCMUS)  
> **Project:** arXiv Data Mining & Matching Pipeline

---

## 📌 Project Overview
This repository contains the complete codebase and pipeline for our **Introduction to Data Science** project at VNU-HCMUS. The project processes a large corpus of arXiv papers across three consecutive milestones:

1. **Milestone 1 — Data Crawling:** Automated discovery of assigned arXiv paper IDs, retrieval of multi-version LaTeX source packages, figure pruning, and citation graph scraping via Semantic Scholar.
2. **Milestone 2 — Hierarchical Parsing & Standardization:** Parsing LaTeX content into structured AST trees, standardizing bibliography items into BibTeX, and cross-revision deduplication.
3. **Milestone 3 — Citation Matching Pipeline:** Machine learning models predicting citation links evaluated using **MRR (Mean Reciprocal Rank)**, published as a Hugging Face Dataset.

---

## 🔗 Important Links
* **Report (GitHub Pages):** [View Milestone 1 Report](https://harkone22-12.github.io/Arxiv-report/) (source: <https://github.com/Harkone22-12/Arxiv-report>)
* **Hugging Face Dataset:** to be published in Milestone 3
* **Course Lab Book:** [HCMUS Intro DS Lab Book](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/crawling/)

---

## 🛠️ Environment Setup

### 1. Prerequisites
* **Python:** 3.10 or 3.11 recommended
* **Hardware:** Tested on Google Colab (CPU-only) and local environments

### 2. Installation
Clone the repository and install required dependencies:
```bash
git clone https://github.com/thinhelzan842/intro-ds-arxiv-project.git
cd intro-ds-arxiv-project
pip install -r src/requirements.txt
```

---

## 🚀 Execution Guide (Milestone 1)

The pipeline is organized into modular notebooks inside `src/`, linked seamlessly via `%run`:

```text
src/
├── 00_config.ipynb          # Shared configurations, ID ranges, rate limits & logging helpers
├── 01_discovery.ipynb       # Member 1: Paper entry discovery & metadata extraction (arXiv API)
├── 02_download.ipynb        # Member 2: Source download, keeps only .tex/.bib (pipelined, resumable)
├── 03_references.ipynb      # Member 3: Citation graph fetching (Semantic Scholar Graph API)
├── 04_monitor.ipynb         # Member 4: Performance monitoring, metrics & statistics helpers
├── 05_run_pipeline.ipynb    # End-to-end execution pipeline with auto-resume capability
├── 06_test_100_versions.ipynb   # Test: real pipeline on the first 100 source versions (~5 min)
└── 07_run_references.ipynb  # Optional: references on a teammate's Colab, exported as one zip
```

`06_test_100_versions.ipynb` runs `05_run_pipeline.ipynb` with
`TEST_VERSIONS = 100`: only the first assigned IDs (up to 100 source
versions), written to `test_runs/100_versions/` so the real crawl is not
touched. It then checks that every version was processed, that only `.tex`/`.bib`
were stored and that a second run sends no request, and prints the timing,
size savings and an estimate for all 20,000 IDs. It also fetches the references
of those papers and checks that each has a final `references.json`.
`FRESH_RUN = True` (default) deletes the previous test folder first, so every run
measures the speed from scratch; set it to `False` to resume an interrupted test.

### Running Individual Notebooks
Notebooks 01–04 only define functions and their tests (`RUN_TEST = True` when
opened on their own); none of them starts the crawl. The downloader's 46 offline
tests are in `02_download.ipynb`. Open the notebooks (`01_discovery.ipynb`, `03_references.ipynb`,
`04_monitor.ipynb`) in JupyterLab / VS Code / Colab to run their quick tests.

### Running on Google Colab
Step-by-step guide (Vietnamese) for the teammate keeping the Colab crawl running: [`HUONG_DAN_COLAB.md`](HUONG_DAN_COLAB.md).

When running on Google Colab, `00_config.ipynb` automatically mounts Google Drive (`/content/drive/MyDrive/arxiv-project`) so that data and execution logs persist across session disconnects.

To run the crawl, open **`src/05_run_pipeline.ipynb`** from branch `VA` in a
**CPU** runtime and run all cells. Its first cell clones or updates branch `VA`,
installs dependencies and moves into `src/`; `00_config.ipynb` mounts Drive. No
Drive folder needs to be created manually. `05_run_pipeline.ipynb` loads
notebooks 00–04 with `%run -i` (`RUN_TEST = False`) and then:

1. **Discovery** (`discover_all()` from `01_discovery.ipynb`): each completed
   batch of up to 100 IDs is saved under
   `MyDrive/arxiv-project/state/discovery_batches/` and the result in
   `state/discovery_manifest.json`. If a batch still fails after retries
   (including HTTP 429), the run stops and a later run reuses completed batches
   and retries only unresolved IDs.
2. **Sources and references at the same time:** `download_sources(...)` from
   `02_download.ipynb` (arXiv, one connection, `ARXIV_DELAY` apart, at least 3 s)
   in the main thread, and `crawl_references` from `03_references.ipynb` (Semantic
   Scholar batch endpoint, 100 papers per request) in one background thread. The
   two rate limits are separate, and the references finish long before the
   download.
3. **Report and benchmark:** if `references_export.zip` is in
   `MyDrive/arxiv-project/`, it is imported first. `logs/papers.csv` is rebuilt
   from the download log plus the reference counts. Each session appends its
   wall time, RAM and disk to `logs/benchmark_sessions.jsonl` (RAM samples every
   5 s to `logs/ram_timeseries.csv`), and `logs/benchmark.json` is recomputed
   over all sessions with the lab book's metrics (success rate, sizes,
   references per paper, reference success rate, time per paper, discovery
   time, peak/average RAM, maximum disk incl. temporary archives, final output
   size). `logs/performance.json` is written in `04_monitor`'s format from the
   same numbers, including `ram_timeseries` for the RAM plot, and the four
   `04_monitor` charts are saved as PNG in `logs/figures/` (RAM usage, size
   before/after, versions per paper, references per paper).

**Optional: references on a second account.** Set `RUN_REFERENCES = False` in 05 and a teammate opens
`src/07_run_references.ipynb` on their own Colab, with their own `S2_API_KEY`,
at any time: it needs neither the sources nor the discovery (without a manifest
it queries all 20,000 IDs; missing ones come back `not_found`). Results go to
`MyDrive/arxiv-project/references_run/`, it resumes after a disconnect, and its
last cell writes `references_export.zip`. Copy that file into the main
`MyDrive/arxiv-project/` folder of the person running 05; the 05 report imports
it (an `ok` result is never replaced by an `error`).

**Progress bars** (05 and the 06 test): *Discovery* shows the IDs checked out of
all assigned IDs with the papers and versions found; *Papers* shows the papers
done out of every discovered paper, with versions, MB downloaded and the ETA;
the bar below it shows the file being downloaded (`<id>vN`), its size and the
MB left. They use `tqdm` (preinstalled on Colab; listed in `src/requirements.txt`).

`RUN_DISCOVERY`, `RUN_DOWNLOAD` and `RUN_REFERENCES` in the setup cell turn
stages on or off. `ARXIV_CONTACT` is optional: if set to an email address, it is
appended to the `USER_AGENT` from `00_config.ipynb`. Use the notebooks under
`src/`; the root `download.py` is an earlier standalone downloader, not used by the pipeline.
Expect about `ARXIV_DELAY` (3 s, the lab-book minimum) per source version:
about 18–23 hours for ~22,000 versions, so 2–3 Colab sessions.

**API key.** Copy `.env.example` to `.env` and set `S2_API_KEY` (and optionally
`ARXIV_CONTACT`). `00_config.ipynb` reads `.env` from the repo root when run
locally, or from `MyDrive/arxiv-project/.env` on Colab (a fresh clone has no
`.env`); Colab Secrets also work. Variables already set in the environment win.
`.env` is git-ignored: never commit a real key.

After a disconnect, run all cells of `05_run_pipeline.ipynb` again (same Google
account, so the same Drive). If the downloader stops early with `STOPPED EARLY`
(Drive full, Drive unmounted, or 20 failures in a row), fix the cause and run
again. If it refuses to start because another run holds the lock, stop that
runtime, or wait 3 minutes when it no longer exists. The
downloader reads the `receipts.jsonl` index once and trusts it
(`DOWNLOAD_VERIFY = "receipt"`; `"size"` / `"sha256"` check every saved file,
which takes hours on Drive for the full corpus), prints paper and
version completion percentages at startup and periodically, and continues with
unfinished versions. The
output is under `MyDrive/arxiv-project/data/raw/<yymm-id>/vN/`; receipts,
`errors.jsonl` (failed versions), `throttles.jsonl` (requests arXiv refused with
429/5xx or did not answer), `run_summary.json`, `run_history.jsonl` and the
download `papers.csv` are under `MyDrive/arxiv-project/state/download/`. Every
row of `errors.jsonl` and `throttles.jsonl` has an `error_kind` label
(`HTTP_429`, `TIMEOUT`, `NOT_FOUND`, `TRANSFER_CUT`, `CORRUPT_ARCHIVE`, ...; see
`error_kind` in `02_download.ipynb`) and the HTTP `status`.
Keep this Drive directory across Colab sessions and use only one downloader
instance for it at a time.

The downloader requests each version from `export.arxiv.org/src/{id}vN` on one
connection with at least 3 seconds between requests. arXiv sends the entire
archive over the network; it is saved to local runtime disk, and the extractor
writes **only `.tex` and `.bib`** files to Drive, preserving the TeX bytes.
Extraction and Drive writes run in `DOWNLOAD_WORKERS` background threads, so
they overlap the 3-second wait instead of adding to it. Files other than
`.tex`/`.bib` left by older runs (`.bbl`, `.sty`, `.cls`) are deleted on resume
without new requests. A PDF/Word-only version gets an empty `vN/` folder and an
`empty_source` receipt. `run_summary.json` reports this download stage's
elapsed time, process RSS samples and an **estimate** of peak project disk
usage; the group's end-to-end Colab benchmark remains the source for the
Milestone 1 performance report. Do not remove benchmark evidence before the
report figures and tables have been generated.

A manifest accepts `{"papers": [{"id": "2603.20580", "versions": 1,
"status": "ok"}]}` or a list with `arxiv_id` and `version_count`.

---

## 🧩 Execution Guide (Milestone 2)

```text
src/
├── 10_parse_tree.ipynb      # Member 2: root file, \input gathering, build_tree
├── 11_normalize.ipynb       # Member 4: macros, LaTeX cleanup, math normalization, sentences
├── 12_bibtex.ipynb          # Member 3: .bib / \bibitem -> BibTeX, reference dedup, \cite renaming
├── 13_dedup_export.ipynb    # Member 1: loads 10-12, parse_paper, element IDs, cross-version dedup, the 3 tables
├── 15_run_parsing.ipynb     # Member 1: run on every paper on Drive, in parallel, with resume and benchmark
└── 16_test_m2_1000_papers.ipynb   # test of 15 on 1,000 papers in /content (real data only read), table checks
```

**Test first:** open `src/16_test_m2_1000_papers.ipynb` on Colab and run all cells. It runs `15` on 1,000 papers
in `/content/m2_test` (the real `data/raw` is linked and only read), checks the three Parquet tables against the
statement, tests resume and the time limits (a stuck and a killed worker), and saves `report.json` and the logs
to `MyDrive/arxiv-project/test_runs/m2_1000_papers/`.

Open **`src/15_run_parsing.ipynb`** on Colab (CPU runtime) and run all cells. Its first cell clones
branch `m2-pipeline` (`main` once merged), and it loads `00_config`, `02_download` (run lock, receipts) and
`13_dedup_export`. `13` loads the definitions of `10`–`12` (their demonstration cells are not run), each in
its own namespace, and binds them to the interface of its first cell through small adapters; a function a
notebook does not provide keeps the fallback of `13`. `15` prints which implementation each step uses;
`TEAM_USE = ()` runs the fallback alone. Opened alone, `13` runs its offline tests (`RUN_TEST = True`).

**Status (22 Nov):** every step comes from the members' notebooks (`10_parse_tree` has had `build_tree` since
the merge of `30719c2`; parser version `13.8|10:team|11:team|12:team`). On `test_runs/1000_versions` (900
papers, 291 versions with LaTeX): 291/291 versions parsed, about 30 s on one local CPU core.

- `TEST_PAPERS = 100` (default) parses 100 papers spread over the four ranges plus the hard cases;
  `None` parses every paper. `WORKERS` processes parse in parallel (Drive reads are the bottleneck, try 4–8).
- **Output**: `data/parsed/<id>.json` per paper (versions, trees with element IDs, rows; the raw folders of
  Milestone 1 are only read);
  `data/m2/elements.parquet`, `hierarchy.parquet`, `bibtex.parquet` (the statement's columns);
  `logs/m2_parse_status.csv` (one row per version), `logs/m2_stats.json` (success rate, version coverage,
  element and entry counts before/after dedup), `logs/m2_benchmark.json` (time, RAM incl. worker
  processes, output size, over all sessions).
- **Resume**: after a disconnect, run all cells again. Papers listed in `state/m2/done.jsonl` with the
  same parser version are skipped. Set `FRESH_RUN = True` once before the full run to start the logs,
  the benchmark and `data/parsed/` from zero. Runs before 19 Nov wrote `parsed.json` inside each
  `data/raw/<id>/`; `CLEAN_OLD_PARSED = True` once deletes those files.
- **13.7 → 13.8 (22 Nov)**: `CARRY_OVER = True` (with `FRESH_RUN = False`) keeps the 13.7 results that 13.8
  cannot change and parses only the 1,775 papers of `REPARSE_13_8` (a `.tex` file with a carriage return or a
  nested macro definition) plus a sample of 300 others, whose new files must equal their 13.7 files.
- **13.8 → 13.9 (27 Nov)**: `12` reads the `\bibinfo` fields of REVTeX `\bibitem`s (`\BibitemOpen ...
  \BibitemShut`), which 13.8 read as free text (macro names in the authors and titles). Only the 190 papers
  of `REPARSE_13_9` can change; `CARRY_OVER = True` parses them again with a sample of 300 others and the 20
  manually labelled papers (`CARRY_CHECK`), whose new files must equal their 13.8 files. Set
  `TEST_PAPERS = None`: the tables of `data/m2/` are built again from every paper.

---

## 🏷️ Milestone 3 — Labels (`21_labeling`)

A labelled BibTeX entry matches **one** arXiv reference of the same publication, or none. Labels are keyed
by `(arxiv_id, citation_key)`, so they are made on a frozen parser: `13.9|10:team|11:team|12:team` since
27 Nov. Sheets made on `13.8` stay valid (`M3_LABEL_PARSER_VERSIONS` in `20`): 13.9 changed only the REVTeX
papers, none of them labelled by hand; a sheet made with another parser is rejected.

### Label files (Drive `MyDrive/arxiv-project/labels/`, never committed)
| File | Content |
|---|---|
| `selection.csv` | `member, arxiv_id, bib_source, n_entries, n_refs`: the 20 publications labelled by hand |
| `todo/<member>/<fid>.csv`, `<fid>_refs.csv` | the empty sheets, and every arXiv reference of the publication with its link |
| `manual/<fid>.csv` | a filled sheet: `ref_arxiv_id` (**empty = no match**), `confidence` (`sure` / `unsure`), `note`, `labeler`, plus the read-only columns of the sheet |
| `auto/auto_labels.parquet` | `arxiv_id, citation_key, ref_arxiv_id` (null = no match), `rule`, `score` |
| `split.json` | `{"seed": 42, "test": {"manual": [4 ids], "auto": [4 ids]}, "valid": {...}}`; every other labelled publication is train |
| `labels.parquet` | both kinds together (`source` = `manual` / `auto`), read by `22_features` |

### Manual labels
- Each member labels 5 publications of their own ID range: 20–60 entries, at least 10 arXiv references,
  2 of the 5 with `\bibitem` lists and 3 with `.bib` files (`pick_manual`, seed 42). **Every entry** is labelled.
- The sheet shows the entry (title, 3 authors, year, venue) and 3 hints: the references with the closest
  title. Hints are not labels, and the automatic label is never shown, so the manual labels measure the
  automatic matcher independently.
- Rules: the same work is a match (a conference version and its arXiv preprint, a title with or without a
  subtitle); another paper of the same authors, a book, a website, software or a dataset with no arXiv
  reference is no match; one reference matches at most one entry; when unsure, `confidence = unsure` and a `note`.
- `validate_labels()` checks every sheet: each entry exactly once, keys still in `entries`, references of
  the same publication only, the parser version, at least 20 entries per publication, 5 publications per
  member, 400 entries for the group (100 per member on average). It also repairs what a spreadsheet changes (`2504.1` → `2504.10000`, a key
  turned into a date, recovered from its position and title); `h1`/`h2`/`h3` may be typed for a hint.

### Automatic labels
Rules tried in order, the first that fires gives the label:

1. `arxiv`: the arXiv id given by the entry (`url`, `journal`, a `10.48550/arXiv.*` DOI) is a reference id;
   an entry whose id is not a reference gets no match (the other rules would contradict it);
2. `doi`: equal normalized DOIs;
3. `title_exact`: equal cleaned titles of at least `min_tokens` words, held by one reference only;
4. `title_fuzzy`: `token_sort_ratio ≥ fuzzy`, no tie, and the same first-author surname or years at most 1 apart;
5. one reference, one entry: the stronger rule keeps a reference claimed twice;
6. otherwise no match.

They are applied to every entry of a seeded 25% of the eligible publications outside the manual pool, raised
when needed so that it covers at least 10% of **all** publications outside the manual pool (the statement's
minimum). `fuzzy` and `min_tokens` are chosen on the **train** manual publications only (the largest recall
with a precision of at least 95%). Precision and recall are reported on all 20 manual publications and on
the manual test + valid publications only, which the tuning never saw.

<!-- Filled from logs/m3_labels.json after the real run (26/11). -->
| | Value |
|---|---|
| Manual publications / entries / share without a match | _TBD_ |
| Automatic publications / entries, labels per rule | _TBD_ |
| Automatic matcher parameters | _TBD_ |
| Automatic vs manual: precision / recall / F1 (all manual; held-out test + valid) | _TBD_ |

### Split
The statement scales the split with the group size k (4 members): test and valid each get 4 manual and
4 automatic publications, drawn with seed 42 among the publications with at least 20 labelled entries and
10 arXiv references. The manual picks are drawn before the automatic matcher is tuned, so its thresholds
never see them; it is tuned on the 12 train manual publications.

### Running
```python
selection = prepare_manual_sheets()   # once, before labelling: selection.csv and the sheets in labels/todo/
result = run_labeling()               # after labelling (25_run_m3): checks, split, automatic labels, files
```

---

## 🎯 Milestone 3 — Features and Model (`22_features`, `23_model`)

Owner: Member 3. The labels (`21_labeling`) and the data preparation (`20_m3_data`) have their own sections.

### Problem framing
For each publication, every BibTeX entry (M2 `bibtex` table, `m` entries) is matched against the
arXiv-keyed references of the **same** publication (M1 `references` table, `n` references). This gives an
`m × n` binary matrix in which a labelled entry has one positive cell, or none when it cites a paper that
is not in the list. We treat it as **learning to rank**: one query per entry, with its `n` references as
candidates. The top 5 are kept and scored with MRR@5. Only classical methods are used (no pretrained
model, no embedding, no LLM).

### Cleaning (`22_features`, section 1)
Both sides go through the same functions, which reuse the helpers of `12_bibtex` and `03_references`:

- **Titles**: LaTeX converted to text, accents folded, lower case, `[a-z0-9]` tokens (`norm_title`). For
  the word features, English stop words are removed and numbers are kept (`gpt 4`, `3d`).
- **Authors**: one key per author, the last word of the family name folded to `[a-z]`. `A. B. Smith`,
  `Smith, A. B.` and `Smith Jr., A.` give `smith`; `van der Waals, J. D.` and `J. D. van der Waals` both
  give `waals`. `others`, `et al.` and suffixes are dropped.
- **Identifiers**: `arxiv_hint` is read from the `doi`, `url` and `journal` fields (`arXiv:2310.06825`, an
  arxiv.org URL, a `10.48550/arXiv.*` DOI). Old ids keep their form (`hep-th/9901001`). DOIs are normalized.
- **Year**: the entry's year. For a reference, the S2 year, or else the year of `ref_submission_date`.
- **`raw_text`**: title, author keys and venue joined together. It is the fallback for `\bibitem` entries
  without a separate title.

`cleaning_report()` writes the share of entries that have each field, by `bib_source`, to
`logs/m3_cleaning_report.csv`.

### Features (`22_features`, section 3)
Every feature is computed on the full `m × n` matrix of the paper and then read at the labelled cells,
so the row and column ranks use all entries and references of the paper. Missing values stay `NaN`:
LightGBM handles them, and the logistic regression gets the train median plus a `*_missing` flag. The
table below is generated by `feature_table_markdown()`:

| Feature | Group | Formula | Idea |
|---|---|---|---|
| `f_arxiv_eq` | identifier | `arxiv_hint == ref_arxiv_id` | an entry that gives its arXiv id almost surely matches it |
| `f_has_arxiv_hint` | identifier | the entry has an `arxiv_hint` | tells the model when `f_arxiv_eq = 0` is real evidence |
| `f_doi_eq` | identifier | `doi_norm` equals the reference DOI or `10.48550/arxiv.<ref id>` | second identifier |
| `f_title_tfidf_char` | title | cosine of char_wb 3-5-gram TF-IDF of the cleaned titles | robust to typos, leftover LaTeX, hyphens |
| `f_title_jaccard` | title | Jaccard of title content tokens | shared content words |
| `f_title_ratio` | title | `fuzz.ratio / 100` | similarity of the whole string |
| `f_title_partial` | title | `fuzz.partial_ratio / 100` | truncated titles, with or without subtitle |
| `f_title_len_diff` | title | `\|len(t) - len(t_ref)\| / max(len)` | very different lengths mean different papers |
| `f_first_surname_eq` | author | same first-author key | how people remember a paper |
| `f_surname_jaccard` | author | Jaccard of author key sets | robust to missing authors |
| `f_author_cover` | author | share of the entry's author keys found in the reference | entries cut author lists with et al. |
| `f_n_authors_diff` | author | `\|n_authors - ref_n_authors\|` | very different author counts |
| `f_year_diff` | year_venue | `\|year - ref_year\|` (NaN if one is missing) | preprint and journal version differ by 0-1 year |
| `f_year_missing` | year_venue | one of the two years is missing | lets the model ignore `f_year_diff` |
| `f_venue_arxiv` | year_venue | the entry says it is an arXiv paper (journal, URL or DOI) | arXiv-cited entries are the ones S2 lists with an id |
| `f_venue_sim` | year_venue | `fuzz.token_set_ratio(venue, ref_venue) / 100` (NaN if one is empty) | same journal or conference |
| `f_raw_tfidf` | fallback | cosine of word TF-IDF of `raw_text` and reference title + author keys | fallback for `\bibitem` entries without a separate title |
| `f_title_rank_in_row` | context | rank of `f_title_tfidf_char` within the entry's row (1 = best) | compares this candidate with the other ones |
| `f_gap_to_best` | context | row maximum of `f_title_tfidf_char` minus this cell | distance to the best candidate |
| `f_margin` | context | best minus second best `f_title_tfidf_char` in the row | does the row have a clear winner |
| `f_col_rank` | context | rank of the cell within the reference's column | best match in both directions |
| `f_n_candidates` | context | `n`, references of the paper | a small `n` is an easier problem |
| `f_ctx_tfidf` | hierarchy | cosine of word TF-IDF of the citing sentences (M2 `elements`) and the reference title | the sentence that cites a paper often names its topic |
| `f_n_cites` | hierarchy | times the entry is cited in the text | much-cited entries are the main related work |
| `f_pos_diff` | experimental | `\|position/m - ref_position/n\|` | experimental: bibliography order vs the order of the S2 list |

The TF-IDF vectorizers are fitted on the titles (and citing sentences) of our own corpus, without labels.
This is unsupervised learning, not a pretrained model.

**Justification.** For every feature on the labelled pairs, `feature_report()` gives its mean on positive
and on negative pairs, its AUC when used alone, and the MRR@5 of ranking by that feature alone. It writes
them to `logs/m3_feature_report.csv`. `plot_feature_histograms()` draws positive vs negative histograms
for each group (`logs/figures/m3/feat_*.png`).

The features marked `row_constant` (`f_has_arxiv_hint`, `f_margin`, `f_n_candidates`, `f_n_cites`,
`f_venue_arxiv`) have one value per entry. They cannot rank candidates on their own; they tell the model
how much to trust the other features. `f_pos_diff` is kept only if its AUC is at least 0.55.

<!-- Filled from feature_findings() after the real run (26/11). -->
| Question | Answer |
|---|---|
| Entries that give their arXiv id | _TBD_ |
| Title similarity of true pairs (`f_title_ratio` median, share ≥ 0.9) | _TBD_ |
| Year difference of true pairs (0 / 1 / 2 / 3+) | _TBD_ |
| `\bibitem` entries without a title, and `f_raw_tfidf` on them | _TBD_ |
| Is `f_pos_diff` useful (AUC) | _TBD_ |

### Model (`23_model`)
| Scorer | Description |
|---|---|
| `baseline` | not learned: `10·f_arxiv_eq + 3·f_doi_eq + f_title_tfidf_char` |
| `logreg` | pointwise `StandardScaler` + `LogisticRegression(class_weight="balanced")`, `C ∈ {0.1, 1, 10}` |
| `ranker` | listwise `LGBMRanker(objective="lambdarank")`, one group per entry, `num_leaves ∈ {15, 31}`, learning rate 0.05, up to 500 trees with early stopping on valid (fallback `HistGradientBoostingClassifier`) |

- **Sample weights**: a manual entry weighs 1, 3 or 5 times an automatic one (tried in the grid).
- **Model choice**: every configuration gets two scores, the MRR@5 of a 5-fold `GroupKFold` by
  publication on train (a publication is never in both the training and the held-out fold) and the MRR@5
  on valid. We choose the configuration with the best mean of the two, because two valid publications
  alone give a noisy score. On a tie, the simpler model is kept.
- **Out-of-fold train predictions**: each train publication is ranked by a model that never saw it.
- **Post-processing**: two steps, each of which can be switched off for the ablation.
  1. A cell with an equal arXiv id is always rank 1.
  2. Inside each paper, a one-to-one assignment (Hungarian, `scipy.optimize.linear_sum_assignment`) is
     run on paper-normalized scores. The assigned reference moves to rank 1 when its score is at least
     `τ ×` the best score of its row; `τ` is tuned on valid.
- **Metric**: `MRR@5 = (1/|Q|) Σ 1/rank_i`, with 0 when the true reference is not in the top 5. We report
  two modes until the teacher confirms which one is official:
  - `zero`, the statement's wording: an entry without a true reference counts in `|Q|` with score 0;
  - `skip`: only entries that have a true reference are counted.

  Hit@1, Hit@5 and the precision and recall of "no match" detection (a threshold on the best score) are
  reported too, by partition, by label source (manual or automatic) and by `bib_source`.
- **Ablation**: the full model; without the identifier features and the arXiv rule; without the M2
  hierarchy features; without post-processing; with the title features only. Leave-one-publication-out
  over the manual publications gives a mean and a standard deviation.

<!-- Filled from logs/m3_metrics.json after the real run (26/11). -->
| Model | Valid MRR@5 (zero) | Valid MRR@5 (skip) | Test MRR@5 (zero) | Test MRR@5 (skip) |
|---|---|---|---|---|
| baseline | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| logreg | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| ranker | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| chosen + post-processing | _TBD_ | _TBD_ | _TBD_ | _TBD_ |

### Running
Both notebooks only define functions. With `RUN_TEST = True` (the default when a notebook is opened on
its own), they run their offline tests (21 in `22`, 8 in `23`) and a demonstration on the local dev
sample. `25_run_m3` loads them with `RUN_TEST = False` and calls:

```python
pairs, feature_report, cleaning = run_features()   # 22: reads data/m3/*.parquet and labels/
result = run_model(pairs)                           # 23: model choice, final model, predictions
```

| Output | Content |
|---|---|
| `data/m3/pairs.parquet` | one row per (labelled entry, reference): `arxiv_id, citation_key, ref_arxiv_id, n_candidates, source, label, partition, f_*` |
| `data/m3/predictions.parquet` | the statement's table: `arxiv_id, partition, citation_key, groundtruth_arxiv_id, cand_1..cand_5` (checked by `check_predictions`) |
| `logs/m3_feature_report.csv`, `logs/m3_cleaning_report.csv`, `logs/figures/m3/feat_*.png` | feature and cleaning analysis |
| `logs/m3_model_selection.csv` | CV and valid MRR@5 of every configuration |
| `logs/m3_metrics.json` | chosen model and `τ`, metrics per model and partition, ablation, leave-one-publication-out, feature importance |

Packages: `scikit-learn`, `scipy`, `rapidfuzz` and `lightgbm`, all listed in `src/requirements.txt`. Colab
ships all of them except `rapidfuzz`. Random seed: 42.

---

## 🤗 Milestone 3 — Hugging Face export (`26_export_hf`)

One public dataset per member, holding the rows of that member's arXiv ID range. Each of the six tables is
sharded Parquet in `data/<table>/train-0000i-of-0000n.parquet`, with the explicit schema of the statement
(`HF_SCHEMAS`: `list<string>`, dictionary columns, `int32`, non-null keys). The dataset card `README.md`
has one `configs` entry per table.

1. **Export** (on Colab, by whoever holds the Drive): set `EXPORT = True` and run all. Each source is read
   once, and its rows go to `hf/<member>/` on Drive. The run checks that member rows + rows outside the
   ranges = source rows, writes `logs/hf_export.json` and checks every folder (`check_export`). After a new
   `23_model` run, `EXPORT_TABLES = ("predictions",)` rebuilds only that table.
2. **Upload** (each member, in their own Colab): add a *write* `HF_TOKEN` to Colab Secrets, set
   `UPLOAD_MEMBER = "TV3"` (your own) and run all. The folder is checked, uploaded to
   `<hf-user>/khdl-arxiv-<range>`, then read back with `load_dataset(..., streaming=True)`. Paste the
   printed link on Moodle.

Packages: `huggingface_hub`, `datasets` (in `src/requirements.txt`). `hf/` is never committed.

---

## 📊 Performance Monitoring & Auditing
The pipeline implements an auditable profiling system (`src/04_monitor.ipynb`):
* **RAM Sampling:** Monitored via a background daemon thread utilizing `psutil` (capturing peak and average RSS memory).
* **Disk Footprint:** Storage tracked via recursive byte counting before and after figure deletion.
* **Execution Time:** Wall-clock time recorded end-to-end and broken down by sub-stages (`discovery`, `download`, `references`).
* **Logs Generated:**
  * `logs/papers.csv`: Per-paper status, versions, sizes before/after pruning, reference counts, and elapsed time.
  * `logs/references.csv`: Detailed call log for each Semantic Scholar request.
  * `logs/performance.json`: Auditable summary of peak/avg RAM, max/final disk usage, and stage durations.

---

## 📁 Repository Structure
```text
├── data/                 # Local data working directory: raw/<id>/vN/*.tex (Milestone 1),
│                         #   parsed/<id>.json and m2/*.parquet (Milestone 2)
├── docs/                 # Jupyter Book report source files & dynamic evaluation notebooks
│   ├── _config.yml       # Jupyter Book configuration (execute_notebooks: force)
│   ├── _toc.yml          # Table of contents
│   ├── milestone1/       # Milestone 1 chapters (overview, statistics, performance)
│   ├── milestone2/       # Milestone 2 chapters (BibTeX, parsing statistics from logs/m2_*.json)
│   └── data/             # Summarized datasets for Jupyter Book compilation
├── logs/                 # Execution logs (papers.csv, references.csv, performance.json)
├── src/                  # Pipeline notebooks & requirements
│   ├── 00_config.ipynb
│   ├── 01_discovery.ipynb
│   ├── 02_download.ipynb
│   ├── 03_references.ipynb
│   ├── 04_monitor.ipynb
│   ├── 05_run_pipeline.ipynb
│   ├── 06_test_100_versions.ipynb
│   ├── 07_run_references.ipynb
│   ├── 10_parse_tree.ipynb
│   ├── 11_normalize.ipynb
│   ├── 12_bibtex.ipynb
│   ├── 13_dedup_export.ipynb
│   ├── 15_run_parsing.ipynb
│   ├── 16_test_m2_1000_papers.ipynb
│   └── requirements.txt
├── download.py           # Earlier standalone downloader (not used by the pipeline)
├── HUONG_DAN_COLAB.md    # Colab guide (Vietnamese)
└── README.md             # Project documentation
```
