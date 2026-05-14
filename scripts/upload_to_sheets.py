"""
upload_to_sheets.py
====================
One-time upload: reads a local CSV file and pushes it to a configured
Google Sheet using the Sheets API v4 (service account credentials).

Usage:
    python upload_to_sheets.py

Config:
    Set SPREADSHEET_ID below to your actual Google Sheet ID.
    The Sheet ID is the long string in the URL:
    https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit

Requires:
    - credentials.json (Google Service Account key) in the same folder
    - pip install google-api-python-client google-auth
"""

import os
import csv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ── Configuration ──
CSV_FILE_PATH   = "usability_evaluation.csv"
CREDENTIALS_FILE = "credentials.json"

# ✏️  Replace with your actual Google Sheet ID from the URL
SPREADSHEET_ID = "1dYj9RUoNNPSyGjJ_A9yP5AFsM4i1SQB3y9M0drY45tg"
RANGE_NAME     = "Sheet1!A1"


def get_google_sheets_service():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds  = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return build("sheets", "v4", credentials=creds)


def upload_csv_to_sheets():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ Error: {CREDENTIALS_FILE} not found.")
        print("   Download it from Google Cloud Console → Service Accounts → Keys.")
        return

    if not os.path.exists(CSV_FILE_PATH):
        print(f"❌ Error: {CSV_FILE_PATH} not found.")
        return

    print("Connecting to Google Sheets...")
    service = get_google_sheets_service()
    sheet   = service.spreadsheets()

    print(f"Reading data from {CSV_FILE_PATH}...")
    with open(CSV_FILE_PATH, "r", encoding="utf-8") as file:
        data = list(csv.reader(file))

    body = {"values": data}

    print("Uploading data...")
    try:
        result = sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME,
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        print(f"✅ Success! {result.get('updatedCells')} cells updated.")
        print(f"   View: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
    except Exception as e:
        print(f"❌ Upload failed: {e}")


if __name__ == "__main__":
    upload_csv_to_sheets()
