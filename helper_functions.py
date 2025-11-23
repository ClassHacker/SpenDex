import re

def extract_amount(text):
    match = re.search(r'INR\s*([0-9,.]+)', text)
    return match.group(1) if match else ''

def extract_date(text):
    match = re.search(r'(\d{2}-\d{2}-\d{2,4})', text)
    return match.group(1) if match else ''

def extract_merchant(text):
    # Transaction Info
    m = re.search(r'Transaction Info:\s*([\w\s\-/]+)', text)
    if m:
        merchant_candidate = m.group(1).strip()
        if merchant_candidate.startswith('UPI/'):
            # Extract up to the first occurrence of ' If this transaction' or ' Feel free to connect' or end of string
            end_idx = max(merchant_candidate.find(' If this transaction'), merchant_candidate.find(' Feel free to connect'))
            if end_idx != -1:
                return merchant_candidate[:end_idx].strip()
            # Otherwise, return the whole string
            return merchant_candidate
        return merchant_candidate
    # NEFT/IMPS/RTGS/CMS fallback: extract after last slash if present
    m4 = re.search(r'(NEFT|IMPS|RTGS|CMS)[^\s/]*\/([A-Z0-9 ]+)', text)
    if m4:
        merchant_full = m4.group(2).strip()
        merchant_words = merchant_full.split()
        return ' '.join(merchant_words[:2]) if len(merchant_words) >= 2 else merchant_full
    # UPI fallback
    m2 = re.search(r'(UPI/[\w/]+/[A-Z0-9 ]+)', text)
    if m2:
        merchant_candidate = m2.group(1).strip()
        end_idx = max(merchant_candidate.find(' If this transaction'), merchant_candidate.find(' Feel free to connect'))
        if end_idx != -1:
            return merchant_candidate[:end_idx].strip()
        return merchant_candidate
    # Credit card spend: Merchant Name
    m3 = re.search(r'Merchant Name:\s*([\w .,&-]+)', text)
    if m3:
        merchant_full = m3.group(1).strip()
        merchant_words = merchant_full.split()
        return ' '.join(merchant_words[:2]) if len(merchant_words) >= 2 else merchant_full
    return ''

def extract_transaction_type(text, subject):
    if re.search(r'\b(debited)\b', text, re.IGNORECASE) or re.search(r'\b(debited)\b', subject, re.IGNORECASE):
        return 'debit'
    elif re.search(r'\b(credited)\b', text, re.IGNORECASE) or re.search(r'\b(credited)\b', subject, re.IGNORECASE):
        return 'credit'
    elif re.search(r'\bspent\b', text, re.IGNORECASE) or re.search(r'\bspent\b', subject, re.IGNORECASE):
        return 'debit'
    return ''