import gspread
import pandas as pd
import json

CREDENTIALS_FILE = 'credentials.json'
SPREADSHEET_URL = 'https://docs.google.com/spreadsheets/d/1dYj9RUoNNPSyGjJ_A9yP5AFsM4i1SQB3y9M0drY45tg/edit?usp=sharing'

new_issues = [
  {
    "Heuristic": "Visibility of system status",
    "Issue Description": "The search overlay remains sticky and covers content even when scrolling deep into the page, with no clear close button.",
    "Behavioral Insight": "Users attempt to scroll away from the search bar to see content, but the overlay persists, blocking their view.",
    "Attitudinal Insight": "Users feel frustrated and 'trapped' by the UI, perceiving the site as buggy or intrusive.",
    "Cognitive Load": "High",
    "Severity": 4,
    "Priority": "P1",
    "Recommendation": "Implement an auto-close trigger on scroll or adds a prominent 'X' close button to the search overlay.",
    "Page_URL": "https://www.cardekho.com/"
  },
  {
    "Heuristic": "Consistency and standards",
    "Issue Description": "Inconsistent casing in main navigation links: 'NEW CARS' vs 'Used cars'.",
    "Behavioral Insight": "Users may momentarily pause to determine if the different styles signify different types of functionality.",
    "Attitudinal Insight": "The inconsistency reduces the perceived professionalism and 'polish' of the platform.",
    "Cognitive Load": "Low",
    "Severity": 1,
    "Priority": "P4",
    "Recommendation": "Standardize all navigation labels to either Sentence case or Title case for brand consistency.",
    "Page_URL": "https://www.cardekho.com/"
  },
  {
    "Heuristic": "Aesthetic and minimalist design",
    "Issue Description": "Redundant entry points for car searching (Header Search vs 'Find your right car' section) create visual noise.",
    "Behavioral Insight": "Users are presented with two different ways to do the same task in close proximity, leading to choice paralysis.",
    "Attitudinal Insight": "The page feels cluttered and overwhelming, making it harder to focus on featured content.",
    "Cognitive Load": "Medium",
    "Severity": 2,
    "Priority": "P3",
    "Recommendation": "Consolidate the search functionality or differentiate the 'Find your car' section with more unique tool-based interactions.",
    "Page_URL": "https://www.cardekho.com/"
  },
  {
    "Heuristic": "Aesthetic and minimalist design",
    "Issue Description": "High information density with multiple competing banners and sticky headers.",
    "Behavioral Insight": "Users' eyes jump between multiple moving or high-contrast elements, missing the intended call-to-actions.",
    "Attitudinal Insight": "A sense of 'ad-fatigue' and lack of trust in the hierarchy of information.",
    "Cognitive Load": "High",
    "Severity": 2,
    "Priority": "P2",
    "Recommendation": "Reduce the number of sticky elements and use whitespace more effectively to guide the user's focus.",
    "Page_URL": "https://www.cardekho.com/"
  },
  {
    "Heuristic": "Help and documentation",
    "Issue Description": "FAQs and support links are only accessible in the footer, which is difficult to reach on a long, content-heavy page.",
    "Behavioral Insight": "Users struggling with a task may give up before reaching the bottom of the page to find help.",
    "Attitudinal Insight": "Users feel unsupported when they encounter issues or have specific questions about the car buying process.",
    "Cognitive Load": "Medium",
    "Severity": 3,
    "Priority": "P2",
    "Recommendation": "Add a 'Help' or 'Support' link to the top-level navigation or 'Login' dropdown for quicker access.",
    "Page_URL": "https://www.cardekho.com/"
  }
]

def main():
    print("Connecting to Google Sheets...")
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    sh = gc.open_by_url(SPREADSHEET_URL)
    worksheet = sh.sheet1
    
    # We will append to rows 12-16
    start_row = 12
    values_to_append = []
    
    for i, issue in enumerate(new_issues):
        index = str(start_row + i - 1)
        # Using a generic UI image for the placeholder
        formula = '=IMAGE("https://files.catbox.moe/1hgplx.png")'
        
        row = [
            index,
            issue["Heuristic"],
            formula,
            issue["Issue Description"],
            issue["Behavioral Insight"],
            issue["Attitudinal Insight"],
            issue["Cognitive Load"],
            issue["Severity"],
            issue["Priority"],
            issue["Recommendation"],
            issue["Page_URL"]
        ]
        values_to_append.append(row)
        
    print("Appending new Home Page Usability Issues...")
    import string
    end_row = start_row + len(new_issues) - 1
    range_name = f'A{start_row}:K{end_row}'
    worksheet.update(values=values_to_append, range_name=range_name, value_input_option='USER_ENTERED')
    
    print("Done adding Home Page issues!")

if __name__ == "__main__":
    main()
