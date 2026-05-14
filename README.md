# UX Audit Engine (Public Domain Edition)

A high-fidelity, AI-powered UX Heuristic Evaluation tool. This engine uses Playwright for visual discovery and Gemini/GPT-4o/Claude-3.5 for intelligent usability analysis.

## 🚀 Key Features
- **Visual Intelligence**: Captures above-the-fold, mid-page, and footer context automatically.
- **Heuristic Mapping**: Maps issues to Nielsen’s 10 Usability Heuristics.
- **Deep Insights**: Provides Behavioral and Attitudinal insights for every issue found.
- **Professional Reports**: Generates interactive dashboards and downloadable Excel reports.
- **Sharing Protocol**: Integrated invitation system to share reports with clients via email.

## 🛠 Technical Stack
- **Backend**: Python / Flask
- **Vision Engine**: Playwright (Headless Chrome)
- **Intelligence**: LiteLLM (Supporting Gemini, OpenAI, Anthropic)
- **Data Layers**: JSON, CSV, and Excel (Pandas)
- **Frontend**: Modern Vanilla JS, CSS3 (Glassmorphism), HTML5

### 1. Prerequisites

- Python 3.9+
- [Node.js](https://nodejs.org/) (Required for Playwright browser engines)

### 2. Installation
Clone the repository and install the dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configuration
1. Copy the template environment file:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your settings:
   - `SMTP_USER` / `SMTP_PASS`: For sending invitation emails.
   - `FLASK_PORT`: Default is 5051.

### 4. Launching the Engine
```bash
python app.py
```
Then visit `http://localhost:5051` in your browser.

## 📂 Project Structure
- `app.py`: Main Flask entry point and API routes.
- `scripts/`: Vision logic and AI heuristic analysis.
- `templates/`: High-fidelity HTML5 dashboards.
- `static/`: Modern UI assets, CSS, and dynamic screenshots.

## 📄 License

This project is released into the Public Domain.

---
*Created for the UX Community to automate professional-grade heuristic audits.*
