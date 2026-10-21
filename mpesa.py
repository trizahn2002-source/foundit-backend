import base64
import os
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://sandbox.safaricom.co.ke"
SHORTCODE = os.getenv("MPESA_SHORTCODE", "174379")
PASSKEY = os.getenv("MPESA_PASSKEY")
CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL", "https://example.com/mpesa/callback")


def format_phone(phone):
    """0712345678 / +254712345678 -> 254712345678"""
    phone = str(phone).strip().replace(" ", "").replace("+", "")
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    return phone


def get_token():
    res = requests.get(
        f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
        auth=(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=30,
    )
    res.raise_for_status()
    return res.json()["access_token"]


def make_password():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    raw = f"{SHORTCODE}{PASSKEY}{timestamp}"
    return base64.b64encode(raw.encode()).decode(), timestamp


def send_stk_push(phone, amount, reference):
    """Sends the M-Pesa PIN prompt to the phone."""
    password, timestamp = make_password()
    body = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": format_phone(phone),
        "PartyB": SHORTCODE,
        "PhoneNumber": format_phone(phone),
        "CallBackURL": CALLBACK_URL,
        "AccountReference": reference,
        "TransactionDesc": "FoundIt thank-you tip",
    }
    res = requests.post(
        f"{BASE_URL}/mpesa/stkpush/v1/processrequest",
        json=body,
        headers={"Authorization": f"Bearer {get_token()}"},
        timeout=30,
    )
    return res.json()


def check_stk_status(checkout_request_id):
    """Asks M-Pesa: did this payment go through?"""
    password, timestamp = make_password()
    body = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }
    res = requests.post(
        f"{BASE_URL}/mpesa/stkpushquery/v1/query",
        json=body,
        headers={"Authorization": f"Bearer {get_token()}"},
        timeout=30,
    )
    return res.json()