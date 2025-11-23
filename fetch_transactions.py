"""
Script to fetch transaction emails from Gmail, parse them, and store results in Google Sheets.
"""

# Notes:
# - Gmail OAuth token is stored as `token.json` in the project directory by this script.
# - If you see `invalid_grant`/`Bad Request` errors, delete `token.json` and re-run the script to re-authenticate.
# - For Google Sheets via gspread, run `python -m gspread auth` to generate `~/.config/gspread/credentials.json` and authorized tokens.

import os
import datetime
import base64
import logging
from bs4 import BeautifulSoup
from email import message_from_bytes
from email.header import decode_header
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import gspread

from google.auth.transport.requests import Request

from helper_functions import *
import time
from googleapiclient.errors import HttpError

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# SCOPES for Gmail and Google Sheets
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/spreadsheets'
]

# TODO: Set your spreadsheet ID here
SPREADSHEET_ID = '1nLp1mqmX0IciJ-cS8noPyD_NcL89CZZDjfsAXhH5A_M'
SHEET_NAME = 'AxisBank'


def authenticate_gmail():
    """Authenticate and return Gmail API service."""
    try:
        logging.info("Authenticating with Gmail API...")
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        if not creds or not creds.valid:
            # Try to refresh if possible
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as refresh_err:
                    logging.warning(f"Failed to refresh token: {refresh_err}")
                    creds = None

            # If no valid creds, start a fresh OAuth flow
            if not creds:
                if not os.path.exists('credentials.json'):
                    logging.error("Missing 'credentials.json' (OAuth client secrets). Place it in the project directory.")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            # persist credentials
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        service = build('gmail', 'v1', credentials=creds)
        logging.info("Gmail API authentication successful.")
        return service
    except Exception as e:
        # Detect common OAuth errors (expired / revoked tokens) and try a one-time re-auth
        msg = str(e)
        logging.error(f"Error in authenticate_gmail: {e}")

        if 'invalid_grant' in msg or 'Bad Request' in msg or 'expired' in msg or 'revoked' in msg:
            logging.warning("OAuth token appears invalid or revoked. Removing local 'token.json' and attempting re-authentication...")
            try:
                if os.path.exists('token.json'):
                    os.remove('token.json')
                    logging.info("Removed stale token.json")
            except OSError as rm_err:
                logging.warning(f"Could not remove token.json: {rm_err}")

            # Try fresh OAuth flow once more
            try:
                if not os.path.exists('credentials.json'):
                    logging.error("Missing 'credentials.json' (OAuth client secrets). Place it in the project directory and re-run.")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
                service = build('gmail', 'v1', credentials=creds)
                logging.info("Gmail API authentication successful after re-auth.")
                return service
            except Exception as reauth_err:
                logging.error(f"Re-authentication failed: {reauth_err}")
                logging.error("If this persists, check: (1) system clock/timezone, (2) that the OAuth consent wasn't revoked in your Google account, or (3) delete any other stored tokens.")
                return None

        return None


def fetch_transaction_emails(service):
    """Fetch emails from alerts@axisbank.com for the current month only."""
    try:
        logging.info("Fetching transaction emails for current month from alerts@axisbank.com...")
        today = datetime.date.today()
        first_day = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year+1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month+1, day=1)
        after = first_day.strftime('%Y/%m/%d')
        before = next_month.strftime('%Y/%m/%d')
        query = f"from:alerts@axisbank.com after:{after} before:{before}"
        logging.debug(f"Gmail search query: {query}")
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        logging.info(f"Found {len(messages)} messages.")
        emails = []
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='raw').execute()
            msg_bytes = base64.urlsafe_b64decode(msg_data['raw'].encode('ASCII'))
            mime_msg = message_from_bytes(msg_bytes)
            yield mime_msg
            emails.append(mime_msg)
        logging.info(f"Fetched {len(emails)} emails.")
        return emails
    except Exception as e:
        logging.error(f"Error in fetch_transaction_emails: {e}")
        return []


def parse_transaction_email(email_msg):
    """Parse transaction details from email message."""
    try:
        logging.debug("Parsing transaction email...")
        # Try to get the HTML part if available
        body = None
        if email_msg.is_multipart():
            for part in email_msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/html':
                    body = part.get_payload(decode=True)
                    break
                elif content_type == 'text/plain' and body is None:
                    body = part.get_payload(decode=True)
        else:
            body = email_msg.get_payload(decode=True)
        if not body:
            logging.warning("Email body is empty.")
            return None
        # If HTML, extract text
        try:
            soup = BeautifulSoup(body, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
        except Exception as e:
            logging.warning(f"BeautifulSoup failed, using raw body. Error: {e}")
            text = body.decode(errors='ignore') if isinstance(body, bytes) else str(body)

        # Decode subject if MIME-encoded
        raw_subject = email_msg['subject'] or ''
        try:
            dh = decode_header(raw_subject)
            subject = ''.join([
                (part.decode(enc or 'utf-8') if isinstance(part, bytes) else part)
                for part, enc in dh
            ])
        except Exception as e:
            logging.warning(f"Failed to decode subject: {e}")
            subject = raw_subject
        
        if "INR" not in subject:
            return None

        amount = float(extract_amount(text))
        date = extract_date(text)
        merchant = extract_merchant(text)
        tx_type = extract_transaction_type(text, subject)

        if (tx_type == 'credit'):
            amount = -amount

        parsed = {
            'amount': amount,
            'date': date,
            'merchant': merchant,
            'type': tx_type
        }
        logging.debug(f"Parsed transaction: {parsed}")
        return parsed
    except Exception as e:
        logging.error(f"Error in parse_transaction_email: {e}")
        return None


def authenticate_sheets():
    """Authenticate and return Google Sheets client."""
    try:
        logging.info("Authenticating with Google Sheets API via gspread...")
        gc = gspread.oauth()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet(SHEET_NAME)
        logging.info("Google Sheets authentication successful.")
        return worksheet
    except Exception as e:
        logging.error(f"Error in authenticate_sheets: {e}")

        # Common gspread errors include missing or expired credentials stored under
        # ~/.config/gspread or ~/.config/gspread/authorized_user.json. Attempt a one-time
        # cleanup and provide clear instructions.
        try:
            user_config = os.path.expanduser('~/.config/gspread')
            auth_file = os.path.join(user_config, 'authorized_user.json')
            cred_file = os.path.join(user_config, 'credentials.json')
            removed = []
            if os.path.exists(auth_file):
                os.remove(auth_file)
                removed.append(auth_file)
            if os.path.exists(cred_file):
                # do NOT remove user's client credentials.json automatically, only log it
                logging.info(f"Found gspread credentials at {cred_file}; ensure it's valid.")
            if removed:
                logging.info(f"Removed stale gspread token files: {removed}")

            logging.info("Please re-run the gspread OAuth flow: `python3 -m gspread auth` to recreate tokens.")
        except Exception as cleanup_err:
            logging.warning(f"Could not cleanup gspread tokens automatically: {cleanup_err}")

        return None


def main():
    try:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--auth-only', action='store_true', help='Run authentication flows and exit')
        args = parser.parse_args()

        gmail_service = authenticate_gmail()
        if gmail_service is None:
            logging.error("Gmail authentication failed. Exiting.")
            return
        if args.auth_only:
            logging.info('Auth-only mode: Gmail auth succeeded. Now authenticate Sheets if desired.')
            _ = authenticate_sheets()
            logging.info('Auth-only flow complete. Exiting.')
            return

        transactions = []
        for e in fetch_transaction_emails(gmail_service):
            transactions.append(parse_transaction_email(e))
        emails = fetch_transaction_emails(gmail_service)
        transactions = [parse_transaction_email(e) for e in emails]
        transactions = [t for t in transactions if t]
        worksheet = authenticate_sheets()
        if worksheet is None:
            logging.error('Google Sheets authentication failed. Skipping sheet writes.')
            return

        # Prepare rows and write in batches to avoid per-row write quota limits
        rows = [[t['date'], t['merchant'], t['amount'], t['type']] for t in transactions]

        def append_rows_with_retry(ws, rows_to_add, max_retries=5):
            attempt = 0
            base_delay = 1.0
            while attempt <= max_retries:
                try:
                    # gspread's worksheet.append_rows reduces number of write requests
                    ws.append_rows(rows_to_add, value_input_option='RAW')
                    logging.info(f'Appended {len(rows_to_add)} rows to sheet.')
                    return True
                except Exception as exc:
                    # Detect quota errors (HTTP 429) from HttpError or generic exceptions
                    code = None
                    if isinstance(exc, HttpError):
                        try:
                            code = exc.resp.status
                        except Exception:
                            code = None

                    msg = str(exc)
                    if (code == 429) or ('quota' in msg.lower()) or ('write requests' in msg.lower()) or ('Rate Limit Exceeded' in msg):
                        attempt += 1
                        delay = base_delay * (2 ** (attempt - 1))
                        # add jitter
                        delay = delay * (0.8 + 0.4 * (os.urandom(1)[0] / 255.0))
                        logging.warning(f'Quota hit (attempt {attempt}/{max_retries}). Retrying after {delay:.1f}s...')
                        time.sleep(delay)
                        continue
                    else:
                        logging.error(f'Failed to append rows to sheet: {exc}')
                        return False
            logging.error('Exceeded max retries for appending rows due to quota limits.')
            return False

        # chunk rows into groups (gspread may handle many rows, but keep sizes moderate)
        chunk_size = 100
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i:i+chunk_size]
            success = append_rows_with_retry(worksheet, chunk)
            if not success:
                logging.error('Stopping further writes due to repeated failures.')
                break
    except Exception as e:
        logging.error(f"Error in main: {e}")

if __name__ == '__main__':
    main()
