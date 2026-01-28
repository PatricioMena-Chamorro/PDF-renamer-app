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
3. Your browser will open automatically at:
    ```text
    http://localhost:8501
4. Paste the path to the folder containing your PDF files

5. Use Preview mode first, then rename the files

## 🧪 Recommended workflow

1. Enable Preview mode
2. Review proposed filenames
3. Pay attention to rows marked with ⚠️
4. Disable Preview mode
5. Rename files
6. Manually fix only the remaining edge cases

This approach typically automates 70–90% of the renaming work.

## ⚠️ Notes & troubleshooting

- If the page appears blank:
 - Open the app in Incognito mode
 - Or temporarily disable browser ad-blockers / privacy extensions

- When using OneDrive:
 - Pausing sync may prevent file-locking issues
 
- The app never modifies files unless explicitly confirmed

## 📁 Project structure

pdf_renamer_app/
│
├─ app.py
├─ requirements.txt
├─ run_app.bat
└─ README.md

## 🧠 Limitations

- PDF metadata extraction is heuristic-based
- Some journal layouts or author naming conventions may require manual correction
- Designed as a productivity tool, not a full bibliographic parser