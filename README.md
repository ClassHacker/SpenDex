# Spendex - auth helper

This small workspace contains a helper to re-authenticate Gmail and Google Sheets tokens when they expire or get revoked.

Files:
- `fetch_transactions.py` - main script; now supports `--auth-only` to trigger auth flows without fetching.
- `reauth_helper.py` - helper script that removes stale tokens and runs the interactive auth flows.

Quick usage:

1. Ensure you have `credentials.json` (OAuth client secrets) in the project root.
2. Run the helper:

```bash
python3 reauth_helper.py
```

This will:
- Remove `./token.json` and `~/.config/gspread/authorized_user.json` (if present).
- Run `python3 -m gspread auth` to authorize Google Sheets access.
- Run `python3 fetch_transactions.py --auth-only` to trigger the Gmail OAuth flow.

Troubleshooting:
- If the browser does not open, copy the URL printed in the terminal into an incognito/private browsing window to ensure you pick the correct Google account.
- Make sure your system clock/timezone is correct.
- If the flows still fail with `invalid_grant`, revoke access from your Google account security page and try again.
