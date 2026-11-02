# 📖 Jupyter Book Milestone Report

This directory contains the complete source files for the **Milestone 1 Report** formatted for **Jupyter Book**.

## 🚀 How to Build Locally

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Build the Jupyter Book:**
   ```bash
   jupyter-book build .
   ```
   The generated HTML site will be located in `_build/html/index.html`.

3. **Open in browser:**
   ```bash
   # Windows PowerShell
   Start-Process _build/html/index.html
   ```

## 🌐 Deploying to GitHub Pages (Separate Repo)

According to the course guidelines, the milestone report should be maintained in a separate repository or hosted via GitHub Pages:
1. Initialize a separate repository (or use GitHub Actions):
   ```bash
   pip install ghp-import
   ghp-import -n -p -f _build/html
   ```
2. In your GitHub repository settings, navigate to **Settings -> Pages** and choose **Deploy from a branch (`gh-pages`)**.
