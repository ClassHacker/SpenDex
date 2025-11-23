# Spendex

Spendex is a small utility to fetch transaction alert emails from Gmail, extract structured transaction data (amount, date, merchant, type), and store the results in a Google Sheet. It supports parsing common transaction formats (credit card, UPI, NEFT/IMPS), handles HTML emails, and includes retries and batching for Google Sheets writes.

## Features
- Fetch transaction alert emails from a configured sender (default: `alerts@axisbank.com`) for the current month.
- Parse amounts, transaction dates, merchant names, and transaction types using modular helper functions.
- Store parsed transactions in Google Sheets with batching and retry logic to avoid write quota errors.
- Helper scripts to re-authenticate Gmail and Google Sheets when tokens expire.

## Files
- `fetch_transactions.py` — main script. Handles Gmail authentication, fetching emails, parsing, and writing to Google Sheets. Supports `--auth-only` to run auth flows without fetching.
- `helper_functions.py` — parsing helpers (amount, date, merchant, transaction type).
- `reauth_helper.py` — convenience script that removes stale tokens and triggers the interactive auth flows for Sheets and Gmail.
- `README.md` — this file.

## Setup
1. Create a Python 3.10+ virtual environment and install dependencies (use your venv manager):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Create OAuth client credentials for Google (OAuth 2.0 Client ID) via Google Cloud Console and download the `credentials.json` file into the project root.

3. Run the auth helper to authorize Sheets and Gmail (interactive — opens browser):

```bash
python3 reauth_helper.py
```

Alternatively, you can run each step manually:
- `python3 -m gspread auth` — authorize Google Sheets
- `python3 fetch_transactions.py --auth-only` — run Gmail OAuth flow

## Usage
Run the script to fetch and store transactions:

```bash
python3 fetch_transactions.py
```

Common environment variables / constants you may want to change inside `fetch_transactions.py`:
- `SPREADSHEET_ID` — Google Sheets ID where transactions are written.
- `SHEET_NAME` — worksheet name within the spreadsheet.

## Error handling & tips
- If you see OAuth errors like `invalid_grant` or token expired: delete `token.json` and re-run the auth flow.
- If you see Sheets quota errors (HTTP 429): the script batches writes and will retry on quota hits, but you may need to spread writes over time or upgrade quotas.
- Ensure your system clock is accurate; OAuth can fail if your clock is skewed.

## Contributing
- Feel free to open issues or PRs. If you add support for other banks or email formats, add parsing logic to `helper_functions.py` and include unit tests.

## License
This repository does not include a LICENSE file yet. Choose a license (MIT, Apache-2.0, GPL-3.0, etc.) and add `LICENSE`.

## Contact
If you need help configuring OAuth credentials or pushing this repo to GitHub, open an issue or reach out directly.
