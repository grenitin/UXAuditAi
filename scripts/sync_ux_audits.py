"""
sync_ux_audits.py
==================
Syncs all UX Audit CSV files in the 'UX Audit/' folder to Google Sheets.
Applies professional formatting: color-coded Severity/Priority/Cognitive Load,
dropdowns, column widths, row heights, frozen header row.

Called automatically by ai_evaluator.py after each audit run.
Can also be run manually to re-upload a specific CSV.

Usage:
    python sync_ux_audits.py                        # syncs all CSVs
    python sync_ux_audits.py Girnarsoft_UX_Audit_-_Heuristic_Evaluation.csv  # sync one file

Requires:
    - credentials.json or GOOGLE_CREDENTIALS_JSON env var
    - pip install gspread gspread-formatting pandas
"""

import os
import csv
import json
import gspread
import pandas as pd
import sys
import time

CREDENTIALS_FILE = 'credentials.json'
SPREADSHEET_URL = 'https://docs.google.com/spreadsheets/d/1dYj9RUoNNPSyGjJ_A9yP5AFsM4i1SQB3y9M0drY45tg/edit?usp=sharing'
AUDIT_FOLDER = 'UX Audit'

def main():
    print("Connecting to Google Sheets...")
    try:
        if 'GOOGLE_CREDENTIALS_JSON' in os.environ:
            # Running on Render using an environment variable
            credentials_dict = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
            gc = gspread.service_account_from_dict(credentials_dict)
        else:
            # Fallback for local development
            gc = gspread.service_account(filename=CREDENTIALS_FILE)
            
        sh = gc.open_by_url(SPREADSHEET_URL)
    except Exception as e:
        print(f"Failed to connect to Google Sheets: {e}")
        print("Please ensure credentials.json is present in the directory.")
        sys.exit(1)

    if not os.path.exists(AUDIT_FOLDER):
        print(f"Folder '{AUDIT_FOLDER}' does not exist.")
        return

    valid_titles = []
    
    target_file = None
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
        
    for filename in os.listdir(AUDIT_FOLDER):
        if filename.endswith(".csv"):
            if target_file and filename != target_file:
                # Still track valid titles so we don't accidentally delete other sheets
                sheet_title = filename.split('_')[0][:50]
                valid_titles.append(sheet_title)
                continue
                
            filepath = os.path.join(AUDIT_FOLDER, filename)
            # Use only the brand name (first part before the underscore) for the Google Sheet tab title
            sheet_title = filename.split('_')[0][:50]
            valid_titles.append(sheet_title)
            print(f"Uploading {filepath} to sheet '{sheet_title}'...")
            
            # Read CSV
            df = pd.read_csv(filepath)
            df = df.fillna("")
            df.rename(columns={'Index': '#'}, inplace=True)
            
            # Formulate data list [headers, ...rows]
            data = [df.columns.values.tolist()] + df.values.tolist()
            
            # Handle existing sheets robustly regardless of case-sensitivity
            sheet_title_lower = sheet_title.lower()
            existing_ws = next((ws for ws in sh.worksheets() if ws.title.lower() == sheet_title_lower), None)
            
            stats = {"added": 0, "updated": 0, "skipped": 0}
            
            if existing_ws:
                print(f"  Existing sheet found: '{existing_ws.title}'. Merging and reconciling data...")
                worksheet = existing_ws
                
                # Load existing data to merge
                existing_data = worksheet.get_all_values()
                if len(existing_data) > 1:
                    existing_df = pd.DataFrame(existing_data[1:], columns=existing_data[0])
                    # Reconcile logic: Add only new indices or non-duplicate issues
                    # (Restoring the original reconciliation logic approximately)
                    new_issues = df[~df['#'].isin(existing_df['#'])]
                    if not new_issues.empty:
                        df = pd.concat([existing_df, new_issues], ignore_index=True)
                        stats["updated"] = len(new_issues)
                else:
                    stats["updated"] = len(df)
            else:
                print(f"  Creating new latest sheet '{sheet_title}'...")
                worksheet = sh.add_worksheet(title=sheet_title, rows=str(max(100, len(df)+10)), cols=str(max(20, len(df.columns)+5)))
                stats["added"] = len(df)
                
            # Formulate data list [headers, ...rows]
            df = df.fillna("")
            data = [df.columns.values.tolist()] + df.values.tolist()
            
            # Update the worksheet with the merged data
            worksheet.clear()
            worksheet.update(values=data, range_name=f'A1:{chr(ord("A") + len(df.columns) - 1)}{len(data)}', value_input_option='USER_ENTERED')
            
            # Internal logging for ai_evaluator parsing
            print(f"UPSERT_STATS:{json.dumps(stats)}")
            
            # Formatting
            from gspread_formatting import (
                cellFormat, color, textFormat, borders, border, format_cell_range,
                set_column_width, set_row_height, DataValidationRule, BooleanCondition, set_data_validation_for_cell_range,
                ConditionalFormatRule, BooleanRule, GridRange, get_conditional_format_rules, padding
            )

            num_rows = len(data)
            num_cols = len(df.columns)
            end_col_letter = chr(ord('A') + num_cols - 1)
            full_range = f'A1:{end_col_letter}{num_rows}'
            header_range = f'A1:{end_col_letter}1'

            # 1px solid black border for all rows and columns
            border_style = border('SOLID', color(0, 0, 0))
            all_borders = borders(top=border_style, bottom=border_style, left=border_style, right=border_style)

            fmt_header = cellFormat(
                backgroundColor=color(0.25, 0.35, 0.55), # Beautiful soft blue
                textFormat=textFormat(bold=True, foregroundColor=color(1, 1, 1), fontSize=11),
                horizontalAlignment='CENTER',
                verticalAlignment='MIDDLE',
                borders=all_borders
            )

            cell_padding = padding(top=8, bottom=8, left=8, right=8)

            fmt_body = cellFormat(
                verticalAlignment='MIDDLE',
                wrapStrategy='WRAP',
                borders=all_borders,
                padding=cell_padding
            )
            
            fmt_body_center = cellFormat(
                horizontalAlignment='CENTER',
                verticalAlignment='MIDDLE',
                wrapStrategy='WRAP',
                borders=all_borders,
                padding=cell_padding
            )

            format_cell_range(worksheet, header_range, fmt_header)
            
            if num_rows >= 2:
                format_cell_range(worksheet, f'F2:H{num_rows}', fmt_body)
                format_cell_range(worksheet, f'L2:M{num_rows}', fmt_body)
                format_cell_range(worksheet, f'B2:E{num_rows}', fmt_body)
                format_cell_range(worksheet, f'A2:A{num_rows}', fmt_body_center)
                format_cell_range(worksheet, f'I2:K{num_rows}', fmt_body_center)
                format_cell_range(worksheet, f'N2:O{num_rows}', fmt_body_center)
                
                # Format Cost column as Currency in INR (Rs.)
                worksheet.format(f"O2:O{num_rows}", {"numberFormat": {"type": "CURRENCY", "pattern": "\"₹\"#,##0.00"}})
            
            # Make proper spacing (column widths and row heights)
            set_column_width(worksheet, 'A', 60)   # Index
            set_column_width(worksheet, 'B', 180)  # Heuristic
            set_column_width(worksheet, 'C', 120)  # Screenshot
            set_column_width(worksheet, 'D', 200)  # Page URL
            set_column_width(worksheet, 'E', 120)  # Page Name
            set_column_width(worksheet, 'F', 350)  # Issue Description
            set_column_width(worksheet, 'G', 250)  # Behavioral Insight
            set_column_width(worksheet, 'H', 250)  # Attitudinal Insight
            set_column_width(worksheet, 'I', 140)  # Cognitive Load
            set_column_width(worksheet, 'J', 100)  # Severity
            set_column_width(worksheet, 'K', 100)  # Priority
            set_column_width(worksheet, 'L', 350)  # Recommendation
            set_column_width(worksheet, 'M', 150)  # Model
            set_column_width(worksheet, 'N', 100)  # Tokens
            set_column_width(worksheet, 'O', 120)  # Cost (Rs)
            
            # Set minimum height for data rows for better spacing
            set_row_height(worksheet, f'2:{num_rows}', 120)
            # Set explicit height for the sticky title row
            set_row_height(worksheet, '1', 50)
            
            # Add Dropdowns
            rule_cog_load = DataValidationRule(BooleanCondition('ONE_OF_LIST', ['Low', 'Medium', 'High']), showCustomUi=True)
            rule_severity = DataValidationRule(BooleanCondition('ONE_OF_LIST', ['1', '2', '3', '4', '5']), showCustomUi=True)
            rule_priority = DataValidationRule(BooleanCondition('ONE_OF_LIST', ['P0', 'P1', 'P2', 'P3', 'P4']), showCustomUi=True)

            if num_rows >= 2:
                set_data_validation_for_cell_range(worksheet, f'I2:I{num_rows}', rule_cog_load)
                set_data_validation_for_cell_range(worksheet, f'J2:J{num_rows}', rule_severity)
                set_data_validation_for_cell_range(worksheet, f'K2:K{num_rows}', rule_priority)
            
            time.sleep(2) # Prevent quota issues
            
            try:
                # Refresh worksheet metadata to ensure Grid ID is synchronized before applying rules
                worksheet = sh.get_worksheet_by_id(worksheet.id)
                rules = get_conditional_format_rules(worksheet)
                
                bg_red = color(1, 0.8, 0.8)
                bg_yellow = color(1, 0.95, 0.8)
                bg_green = color(0.85, 1, 0.85)
    
                if num_rows >= 2:
                    # Cognitive Load
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'I2:I{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['High']), format=cellFormat(backgroundColor=bg_red))))
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'I2:I{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['Medium']), format=cellFormat(backgroundColor=bg_yellow))))
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'I2:I{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['Low']), format=cellFormat(backgroundColor=bg_green))))
    
                    # Severity (4/5 = Red, 3 = Yellow, 1/2 = Green)
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'J2:J{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['5']), format=cellFormat(backgroundColor=bg_red))))
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'J2:J{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['4']), format=cellFormat(backgroundColor=bg_red))))
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'J2:J{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['3']), format=cellFormat(backgroundColor=bg_yellow))))
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'J2:J{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['2']), format=cellFormat(backgroundColor=bg_green))))
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'J2:J{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['1']), format=cellFormat(backgroundColor=bg_green))))
    
                    # Priority (P0/P1 = Red, P2 = Yellow, P3/P4 = Green)
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'K2:K{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['P0']), format=cellFormat(backgroundColor=bg_red))))
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'K2:K{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['P1']), format=cellFormat(backgroundColor=bg_red))))
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'K2:K{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['P2']), format=cellFormat(backgroundColor=bg_yellow))))
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'K2:K{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['P3']), format=cellFormat(backgroundColor=bg_green))))
                    rules.append(ConditionalFormatRule(ranges=[GridRange.from_a1_range(f'K2:K{num_rows}', worksheet)], booleanRule=BooleanRule(condition=BooleanCondition('TEXT_EQ', ['P4']), format=cellFormat(backgroundColor=bg_green))))
                
                rules.save()
            except Exception as formatting_err:
                print(f"  Formatting warning (skipping): {formatting_err}")
            
            # Freeze top row
            worksheet.freeze(rows=1)
            
            print(f"  Done updating and formatting '{sheet_title}'.")

    # Cleanup duplicate/old sheets from previous names to ensure only the latest sheet stays
    for ws in sh.worksheets():
        if ("Usability" in ws.title or "UX_Audit" in ws.title) and ws.title not in valid_titles:
            print(f"Deleting older duplicate sheet: {ws.title}")
            try:
                sh.del_worksheet(ws)
            except Exception as e:
                print(f"Error deleting sheet {ws.title}: {e}")

if __name__ == "__main__":
    main()
