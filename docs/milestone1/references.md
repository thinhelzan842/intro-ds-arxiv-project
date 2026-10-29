# Citation Graph Extraction (Semantic Scholar)

## 1. Graph API Integration
Outbound references are collected via `https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}` with requested fields:
`paperId,references.title,references.authors,references.year,references.publicationDate,references.externalIds`.

## 2. Identifier Normalization & Filtering
* References citing works without an arXiv entry (`externalIds.ArXiv == null`) are excluded from the final `references` table but preserved in local `references.json`.
* Version suffixes (e.g., `arXiv:2310.12345v2`) are stripped to base IDs (`2310.12345`), with folder IDs formatted as `2310-12345`.
* Legacy IDs prior to 2007 (`math/0501001`) maintain their canonical prefix format.
