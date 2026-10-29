# Entry Discovery & Metadata Resolution

## 1. arXiv API Querying
The discovery stage queries `https://export.arxiv.org/api/query` using batches of 100 IDs to minimize round-trips while complying with the 3-second delay.

The API response returns Atom XML containing structured entry fields:
* Submission version identifier (e.g., `2310.12345v3`), indicating the latest version number $N=3$.
* Normalized title and abstract texts (collapsing excessive whitespace).
* Submission timestamp and list of authors.

## 2. Handling Missing and Edge-Case Papers
* Papers in the ID sequence that do not exist or were withdrawn receive status `not_found` in `logs/papers.csv`.
* Pre-2007 legacy identifier schemas (e.g., `hep-th/9901001`) are recognized and preserved.
