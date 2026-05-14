#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Force Playwright to install inside the project directory for persistence
export PLAYWRIGHT_BROWSERS_PATH=/opt/render/project/pw-browsers
python -m playwright install --with-deps chromium

