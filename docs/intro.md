# 📚 arXiv Scraping & Mining Project

Welcome to the project report for **Introduction to Data Science (VNU-HCMUS)**.

This Jupyter Book hosts the cumulative milestone reports documenting our end-to-end data science pipeline built upon the **arXiv** open repository.

## 🎯 Project Roadmap
1. **Milestone 1 — Data Crawling (Current):** Discovering assigned paper entries, retrieving multi-version LaTeX sources, filtering non-text figure binaries, and scraping citation graphs via Semantic Scholar API.
2. **Milestone 2 — Document Parsing & Standardization:** Hierarchical AST tree extraction from LaTeX, converting `\bibitem` to standardized BibTeX, and cross-version deduplication.
3. **Milestone 3 — Citation Matching Pipeline:** Machine learning model predicting paper citation links with **Mean Reciprocal Rank (MRR)** evaluation, published to Hugging Face Datasets.

## 👥 Group Contributions (Milestone 1)
| Member | Primary Role | Key Deliverables |
| :--- | :--- | :--- |
| **Member 1** | Discovery & Coordination | `00_config.ipynb`, `01_discovery.ipynb`, arXiv API batch resolver |
| **Member 2** | Source Download & Extraction | `02_download.ipynb`, tar/gzip extraction, figure pruning |
| **Member 3** | Citation Graph Extraction | `03_references.ipynb`, Semantic Scholar Graph API client & limiter |
| **Member 4** | Monitoring, Benchmarking & Report | `04_monitor.ipynb`, RAM/Disk profiler, Jupyter Book report |
