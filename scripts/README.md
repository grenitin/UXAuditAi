# UX Audit — Scripts Guide

## Overview
This folder contains all automation scripts for the UX Audit pipeline.

---

## 🚀 Core Scripts (Run These)

| Script | Purpose | Command |
|--------|---------|---------|
| `ai_evaluator.py` | **Main engine** — crawls any URL, screenshots pages, runs Gemini AI heuristic analysis, saves CSV | Called by Flask app or directly |
| `sync_ux_audits.py` | **Syncs CSV → Google Sheets** with full formatting (color coding, dropdowns, column widths) | `python sync_ux_audits.py` |

---

## 🛠️ Utility Scripts

| Script | Purpose |
|--------|---------|
| `capture_bikedekho.py` | Screenshots all pages from BikeDekho CSV, uploads to catbox.moe |
| `capture_swiggy.py` | Screenshots all pages from Swiggy CSV, uploads to catbox.moe |
| `upload_images_fix.py` | Fixes Screenshot column in existing CSVs using images from `../screenshots/` |
| `update_sheet_with_images.py` | Uploads local screenshots directly into Google Sheet columns J & K |
| `append_home_audit.py` | Manually appends Home Page issues to an existing audit sheet |
| `upload_to_sheets.py` | Simple one-time CSV upload to Google Sheets (no formatting) |
| `sync_to_sheets.py` | ⚠️ DEPRECATED — superseded by `sync_ux_audits.py` |

---

## 📁 Folder Structure

```
UX Audit/
├── scripts/                  ← All automation scripts live here
├── screenshots/              ← Place PNG screenshots here for upload scripts
├── credentials.json          ← Google Service Account key (DO NOT COMMIT)
└── *.csv                     ← Generated audit CSV files (one per brand)
```

---

## 🔑 Requirements

```bash
pip install playwright playwright-chromium requests beautifulsoup4 \
            google-generativeai Pillow gspread gspread-formatting pandas \
            google-api-python-client google-auth
```

---

## 🔄 Standard Workflow

```
1. ai_evaluator.py  →  Crawls site, runs Gemini analysis  →  Saves CSV
2. sync_ux_audits.py  →  Pushes CSV to Google Sheets with formatting
```
