"""
Small helper to clean stale tokens and run interactive re-auth flows for Gmail and Google Sheets.
Usage:
    python3 reauth_helper.py

This script will:
 - Remove local `token.json` (Gmail token used by this project)
 - Remove `~/.config/gspread/authorized_user.json` (gspread token)
 - Run `python3 -m gspread auth` to let you re-authorize Sheets
 - Run `python3 fetch_transactions.py --auth-only` to trigger Gmail OAuth flow

Note: Both flows are interactive (open a browser). Keep an eye on which Google account you choose during auth.
"""

import os
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

PROJECT_TOKEN = os.path.join(os.getcwd(), 'token.json')
GSPREAD_AUTH = os.path.expanduser('~/.config/gspread/authorized_user.json')

def remove_if_exists(path):
    try:
        if os.path.exists(path):
            os.remove(path)
            logging.info(f'Removed: {path}')
            return True
    except Exception as e:
        logging.warning(f'Could not remove {path}: {e}')
    return False


def run_command(cmd):
    logging.info(f'Running: {cmd}')
    subprocess.run(cmd, shell=True, check=False)


if __name__ == '__main__':
    logging.info('Starting reauth helper...')

    removed_project = remove_if_exists(PROJECT_TOKEN)
    removed_gspread = remove_if_exists(GSPREAD_AUTH)

    logging.info('Now run gspread auth. A browser window will open for you to pick the Google account.')
    run_command('python3 -m gspread auth')

    logging.info('Triggering Gmail OAuth flow via fetch_transactions in auth-only mode...')
    run_command('python3 fetch_transactions.py --auth-only')

    logging.info('reauth_helper done. Verify authentication by running your main script normally.')
