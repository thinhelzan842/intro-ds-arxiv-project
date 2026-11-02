# Entry discovery

Discovery answers two questions for each of the 20,000 assigned IDs: **does the paper exist**, and **how
many versions does it have**. It also collects the metadata of every version. Code: `src/01_discovery.ipynb`
(`fetch_metadata`, `resolve_discovery_batches`, `discover_all`).

## Assigned IDs

The four ranges given by the instructors (5,000 IDs each, both ends inclusive) are listed in
`src/00_config.ipynb` (`ID_RANGES`) and expanded by `all_assigned_ids()`:

| Range | IDs |
|---|---|
| `2609.32834` – `2609.37833` | 5,000 |
| `2605.17338` – `2605.22337` | 5,000 |
| `2605.07338` – `2605.12337` | 5,000 |
| `2603.20580` – `2603.25579` | 5,000 |

## Two passes over the arXiv API

1. **Latest versions.** The API is queried with up to **100 plain IDs per call** (`id_list`). For a plain
   ID arXiv returns the *latest* version, e.g. `2609.32867v2`, so the suffix gives the number of versions.
   IDs that do not exist are simply missing from the answer.
2. **Older versions.** The versioned IDs `v1 … v(n-1)` are queried, again 100 per call. For a versioned ID
   the API returns that version's own title, authors, abstract and date, which gives the revision dates and
   the per-version metadata.

With the mandatory 3 s between calls, batching is what keeps discovery short: the 20,000 IDs need about
200 calls in the first pass instead of 20,000.

Each paper is saved as `data/raw/<id>/metadata.json` with its `status`: `ok` (all versions found),
`partial` (an older version could not be fetched), `not_found` (the ID does not exist on arXiv) or `error`
(the request kept failing).

## Errors and rate limiting

- **HTTP 429** (too many requests): wait `ARXIV_BACKOFF` = 30 s, doubling each time, up to `ARXIV_RETRIES`
  = 3 times, then mark the batch as failed (splitting would only send more requests).
- **Other failures** (e.g. HTTP 500): split the batch in half and retry each half, down to single IDs, so
  one bad ID cannot block the other 99; an ID that still fails gets status `error`.
- Old-style IDs (`hep-th/9711200`) are not affected in practice: all assigned ranges are new-style.

## Checkpoints and resume

`resolve_discovery_batches` saves every finished batch of 100 IDs to `state/discovery_batches/` **before**
the next API call, and `discover_all` merges them into `state/discovery_manifest.json`. A batch that still
fails after the retries stops the run *before* any download starts; running the pipeline again reuses the
saved batches and only queries the IDs that are missing or ended in `error`. The API time of every run is
added up in the manifest (`discovery_seconds`), which is the **entry discovery time** reported on the
[performance page](performance.ipynb).
