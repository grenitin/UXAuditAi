"""
sync_to_sheets.py
==================
⚠️  DEPRECATED — This is the original interactive sync script.
    Use sync_ux_audits.py instead for automated, formatted uploads.

This script prompts for a Google Sheet URL manually and uploads a
single CSV (usability_evaluation.csv) without any rich formatting.
Kept for reference only.

Replacement:
    python sync_ux_audits.py
"""

import gspread
import pandas as pd
import os

# Configuration
CREDENTIALS_FILE = 'credentials.json'
CSV_FILE = 'usability_evaluation.csv'
SHEET_NAME = 'CarDekho Usability Evaluation Results'

def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Error: {CREDENTIALS_FILE} not found!")
        print("Please follow the instructions to create a Service Account and download the JSON file.")
        return

    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found!")
        return

    print("Authenticating with Google Sheets...")
    try:
        # Authenticate using the service account credentials
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
    except Exception as e:
        print(f"Authentication failed. Please verify your credentials.json file. Error: {e}")
        return

    print(f"Reading {CSV_FILE}...")
    try:
        df = pd.read_csv(CSV_FILE)
        # Handle nan values to prevent JSON errors
        df = df.fillna("")
    except Exception as e:
        print(f"Failed to read CSV file. Error: {e}")
        return

    import json
    with open(CREDENTIALS_FILE, 'r') as f:
        creds = json.load(f)
    sa_email = creds.get('client_email', 'Your Service Account Email')

    print("\n--------------------------------------------------------------")
    print(f"Service Account Email: {sa_email}")
    print("--------------------------------------------------------------")
    print("Because of a Google Cloud storage quota error, we cannot create")
    print("a new sheet automatically. Instead, let's use an existing one!")
    print("1. Go to your Google Drive and create a Blank Spreadsheet.")
    print("2. Click 'Share' and share it with the Service Account email above as Editor.")
    print("3. Copy the URL of that Spreadsheet.")
    
    sheet_url = input("\nEnter the URL of your new Google Sheet: ")
    
    try:
        sh = gc.open_by_url(sheet_url.strip())
        worksheet = sh.sheet1
        
        print("\nUploading data...")
        # Upload columns and then data
        worksheet.clear() # Clear existing content just in case
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        
        print("\n========================================================")
        print("UPLOAD COMPLETE! 🚀")
        print(f"You can view your sheet here: {sh.url}")
        print("========================================================\n")
    
    except gspread.exceptions.APIError as e:
        print(f"\nAPI Error: Make sure you have enabled the Google Sheets API and Google Drive API in your Google Cloud Console.")
        print(f"Details: {e}")
    except Exception as e:
        import traceback
        print("\nAn unexpected error occurred:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
