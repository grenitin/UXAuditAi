# UX Audit Engine — Scripts & Backend Logic

This directory contains the core intelligence and automation scripts for the UX Audit Engine.

## 🧠 Core Scripts

### `ai_evaluator.py`
The "Brain" of the operation.
- Manages the Playwright browser lifecycle.
- Handles multi-fold screenshot capture and image encoding.
- Interfaces with LiteLLM to perform heuristic analysis.
- Generates localized issue crops and saves final JSON reports.

### `sync_to_sheets.py` (Optional)
Utility for synchronizing audit findings to Google Sheets for enterprise workflows.

### `README.md`
Architectural notes for backend developers.

## 🛠 Technology Stack
- **Browser Automation**: Playwright (Chromium)
- **AI Integration**: LiteLLM (Gemini 1.5 Flash, GPT-4o, Claude 3.5)
- **Image Processing**: Pillow (PIL)
- **Data Handling**: Pandas & OpenPyXL
