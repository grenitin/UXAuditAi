#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Install Playwright and its system-level dependencies
python -m playwright install --with-deps chromium
