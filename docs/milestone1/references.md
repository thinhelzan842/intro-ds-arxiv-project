# Reference crawling (Semantic Scholar)

*Author: Member 3 · code: `src/03_references.ipynb`*

For every assigned paper we collect the list of works it cites from the
[Semantic Scholar Graph API](https://api.semanticscholar.org/api-docs/graph). These references
are the matching pool of Milestone 3: each BibTeX entry parsed in Milestone 2 will be matched
against the arXiv-keyed references collected here.

## Tools

- `requests` (one `Session` with a clear `User-Agent` and the API key in the `x-api-key` header),
- the Semantic Scholar Graph API, endpoint `GET /graph/v1/paper/arXiv:{id}`,
- `threading` / `concurrent.futures`, to fetch references while the arXiv downloads run.

## How it works

**One request per paper.** We ask for the paper's `paperId`, `title`, `externalIds` and the flat
reference fields `references.title`, `references.authors`, `references.year`,
`references.publicationDate`, `references.venue` and `references.externalIds`. Nested names such as
`references.authors.name` are rejected by the API, so the fields are requested flat. Every reference
also comes with its `paperId`, the Semantic Scholar ID. Semantic Scholar does not tell arXiv versions
apart, so the list is saved once per paper and applies to all its versions.

**Keep every reference, flag the arXiv ones.** As the statement asks, all references are kept
locally, not only those with an arXiv ID. A reference whose `externalIds` has an `ArXiv` key gets:

- `arxiv_id`: the ID as given, without any version suffix. Old-style IDs such as `hep-th/9901001`
  are kept in their original form, because that is their real identifier.
- `arxiv_folder_id`: the folder name used across our corpus (`2310.12345` → `2310-12345`,
  `hep-th/9901001` → `hep-th_9901001`), so a reference can be joined directly with a paper folder.

An `ArXiv` value that is not a valid new- or old-style ID is not counted as an arXiv reference.
It is still visible in `external_ids`, which also keeps `DOI`, `CorpusId`, `DBLP`, etc. for Milestone 3.

**Missing dates.** `submission_date` is the `publicationDate`. If that is missing, we use the
`year`; if that is missing too, we use the month encoded in the arXiv ID (`2310.12345` → `2023-10`).
The `date_source` field records which of the three was used.

**Output.** Each paper folder gets a `references.json`:

```json
{
  "id": "2609.32834", "status": "ok", "s2_id": "7a1dd005...", "s2_title": "...",
  "n_refs": 28, "n_arxiv_refs": 9, "n_dropped": 0, "error": null,
  "references": [
    {"s2_id": "50098b03...", "title": "On the CGGRT Criterion ...",
     "authors": ["Swastik Kopparty", "Shubhangi Saraf"],
     "submission_date": "2026-07-17", "date_source": "publicationDate", "year": 2026,
     "venue": "arXiv.org", "arxiv_id": "2607.15554", "arxiv_folder_id": "2607-15554",
     "external_ids": {"ArXiv": "2607.15554", "DBLP": "..."}}
  ],
  "fetched_at": "2026-10-28T14:22:08+00:00"
}
```

The file is written even when Semantic Scholar does not know the paper (empty list,
`status: "not_found"`), so every paper folder is complete. A failed request never overwrites a
file that an earlier run saved successfully. Entries with neither an S2 ID nor a title, which
S2 returns when a publisher hides the reference list, carry no information; they are dropped
and counted in `n_dropped`.

`references_rows()` turns the saved files into the `references` table of the statement
(`arxiv_id, ref_arxiv_id, ref_title, ref_authors, ref_submission_date, ref_s2_id`), keeping only
the arXiv-keyed references.

## Rate limits and error handling

| Situation | Handling |
|---|---|
| Rate limit | One shared limiter for all threads: 1 request/s with an API key, 1 request every 3 s without one (to stay under 100 requests per 5 minutes) |
| HTTP 429, 5xx, timeout | Retry up to 8 times, waiting 2 s, 4 s, 8 s, … up to 60 s (or the server's `Retry-After`), plus up to 1 s of random jitter |
| HTTP 404 | Paper not indexed (common for very recent papers: S2 indexes new uploads with 1–7 days of delay), `status: "not_found"` |
| HTTP 400 / 401 / 403 | Not retried; the error is logged, and 401/403 adds a hint to check `S2_API_KEY` |

The API key is read from the `S2_API_KEY` environment variable, or from Colab Secrets
(set up in `00_config.ipynb`). It is never written in a notebook.

Every call appends a row to `logs/references.csv` with `id, status, s2_id, n_refs,
n_arxiv_refs, n_dropped, attempts, seconds, error`. The log shows which paper failed and why, and
`crawl_references()` skips papers that are already `ok` or `not_found`, so after an interruption
only the missing and failed papers are fetched again.

## Running in parallel with the downloads

The arXiv limit (3 s between requests) and the Semantic Scholar limit (1 s) are separate.
`submit_references(id)` runs the S2 request on a single background thread while the main
thread downloads the sources from arXiv. Each service still sees one connection at its own rate,
but the total running time is roughly the arXiv time alone instead of the sum of both.

## Results

The statistics of the full crawl (success rate, references per paper, share of arXiv references)
are computed with `references_summary()` from the saved files and plotted in
[Statistics](statistics.ipynb) when the book is built.

Test run on 5 papers (28 Oct 2026, with an API key):

| Paper | Status | References | with arXiv ID |
|---|---|---:|---:|
| 1706.03762 | ok | 41 | 30 |
| hep-th/9711200 (old-style ID) | ok | 48 | 27 |
| 2310.06825 | ok | 29 | 24 |
| 2310.99999 (does not exist) | not_found | 0 | 0 |
| 2609.32834 (first ID of our range) | ok | 28 | 9 |

Success rate 4/5 = 80 %, 36.5 references per successful paper, 61.6 % of them with an
arXiv ID (27 in the old-style format). Of the 146 references, 118 have a `publicationDate`,
21 only a `year`, and 7 have no date at all (they also have no arXiv ID to fall back on).
The run took 25 s and made 10 requests. 5 of them were answered with 429 and succeeded on retry.

An earlier run without a key got the same results, but a second run right after it hit a long
throttling period of the shared unauthenticated pool and gave up after the retries. With the key,
429 answers still come back, sent by Semantic Scholar's CloudFront layer. A separate check sent
10 requests at each spacing of 1 s, 1.5 s and 2 s, plus 8 requests at 3 s. Between 40 % and 80 %
of them were refused with 429 at every spacing, so slowing down further would not remove them.
The retry with growing waits handles them, and no paper ended in `error`. At about 5 s per paper,
references are faster than the arXiv downloads they run alongside, so they do not lengthen the
full crawl.

## Limitations

- References are per paper, not per version (S2 does not distinguish versions).
- S2 indexes new uploads with 1–7 days of delay, so the newest papers of our range may be
  `not_found`; running `crawl_references()` again later fills them in.
- Some publishers hide reference lists from S2; those papers are `ok` with few or no references.
- Coverage of arXiv IDs depends on the field: higher in computer science and physics.
