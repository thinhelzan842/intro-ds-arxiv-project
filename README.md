# 📚 arXiv Paper Corpus & Reference Matching Pipeline
> **Course:** Introduction to Data Science (HCMUS)  
> **Project:** arXiv Data Mining & Matching Pipeline

---

## 📌 Project Overview
This repository contains the full source code and pipeline for our **Introduction to Data Science** project at VNU-HCMUS. The project processes a large corpus of arXiv papers through three major milestones:

1. **Milestone 1 — Data Crawling:** Scrapes raw arXiv papers, metadata, and full-text LaTeX source packages.
2. **Milestone 2 — Hierarchical Parsing & Standardization:** Parses LaTeX content into structured trees, standardizes bibitems into BibTeX format, and deduplicates corpus data.
3. **Milestone 3 — Reference Matching Pipeline:** Features engineering, modeling, and predicting reference links evaluated using **MRR@5**.

---

## 🔗 Important Links
* **Jupyter Book Report:** [Link to GitHub Pages Report](https://your-group-username.github.io/repo-name)
* **Hugging Face Dataset:** [Link to Hugging Face Dataset](https://huggingface.co/datasets/your-username/dataset-name)
* **Course Lab Book:** [HCMUS Intro DS Lab Book](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/)

---

## 📁 Repository Structure
```text
├── .github/              # GitHub Actions for automated deployment
├── data/                 # Sample & local datasets (gitignored large files)
├── docs/                 # Jupyter Book source files for reports
├── src/                  # Core Python modules
│   ├── crawler/          # arXiv scraping & rate-limit handling
│   ├── parser/           # LaTeX hierarchical parsing & BibTeX extraction
│   └── matching/         # Feature engineering & ML matching pipeline
├── notebooks/            # Exploratory Data Analysis (EDA) & experiments
├── requirements.txt      # Python dependencies
└── README.md             # Project documentation
