# PDF Renamer for Scientific Papers

A lightweight **local Streamlit app** to automatically rename scientific PDF files using the format:

> **FirstAuthor et al. (Year). Title.pdf**

The app extracts metadata directly from the **first page of the PDF** (title, authors, year) and proposes standardized filenames.  
A safe *preview mode* allows reviewing changes before renaming files.

---

## ✨ Features

- Automatic extraction of:
  - First author
  - Publication year
  - Article title
- Robust heuristics for different journal layouts
- Safe **preview mode** (no files are renamed until confirmed)
- Visual indicators:
  - ✅ High confidence
  - ⚠️ Fallback or low confidence
- Works **locally** (no files are uploaded anywhere)

---

## 🖥️ Requirements

- **Python 3.10 or 3.11**  
  Download from: https://www.python.org  
  ⚠️ Make sure to check **“Add Python to PATH”** during installation.

- Windows (tested on Windows 10/11)

---

## 🚀 How to run the app (easy mode)

1. Download or clone this repository
2. Double-click the file:

```text
run_app.bat
