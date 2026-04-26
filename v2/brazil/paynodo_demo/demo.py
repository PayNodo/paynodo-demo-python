from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .client import (
    DEFAULT_BASE_URL,
    PayNodoClient,
    load_dotenv,
    read_pem,
    signed_headers,
    verify_callback,
)

ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    command = sys.argv[1] if len(sys.argv) > 1 else "sign-payin"

    merchant_id = os.environ.get("PAYNODO_MERCHANT_ID", "replace_with_merchant_id")
    merchant_secret = os.environ.get("PAYNODO_MERCHANT_SECRET", "replace_with_merchant_secret")

    payin = payin_payload(merchant_id)
    payout = payout_payload(merchant_id)
    status = status_payload()
    balance = balance_payload()

    if command == "verify-callback":
        callback_body = required_env("PAYNODO_CALLBACK_BODY")
        callback_timestamp = required_env("PAYNODO_CALLBACK_TIMESTAMP")
        callback_signature = required_env("PAYNODO_CALLBACK_SIGNATURE")
        public_key = read_pem(
            os.environ.get("PAYNODO_PLATFORM_PUBLIC_KEY_PEM")
            or os.environ.get("PAYNODO_PLATFORM_PUBLIC_KEY_PATH")
            or str(ROOT_DIR / "paynodo-public-key.pem")
        )
        _print(
            {
                "valid": verify_callback(
                    callback_body,
                    callback_timestamp,
                    callback_signature,
                    public_key,
                )
            }
        )
        return

    private_key = read_pem(
        os.environ.get("PAYNODO_PRIVATE_KEY_PEM")
        or os.environ.get("PAYNODO_PRIVATE_KEY_PATH")
        or str(ROOT_DIR / "merchant-private-key.pem")
    )

    if command == "sign-payin":
        timestamp = os.environ.get("PAYNODO_TIMESTAMP") or _utc_now()
        _print(
            signed_headers(
                merchant_id,
                timestamp,
                merchant_secret,
                payin,
                private_key,
            )
        )
        return

    client = PayNodoClient(
        base_url=os.environ.get("PAYNODO_BASE_URL", DEFAULT_BASE_URL),
        merchant_id=merchant_id,
        merchant_secret=merchant_secret,
        private_key_pem=private_key,
    )

    commands = {
        "payin": lambda: client.create_payin(payin),
        "payout": lambda: client.create_payout(payout),
        "status": lambda: client.inquiry_status(status),
        "balance": lambda: client.inquiry_balance(
            {**balance, "accountNo": os.environ.get("PAYNODO_ACCOUNT_NO", balance["accountNo"])}
        ),
        "methods": client.payment_methods,
    }

    if command not in commands:
        raise SystemExit("Unknown command. Use one of: sign-payin, verify-callback, payin, payout, status, balance, methods")

    _print(commands[command]())


def _print(value: object) -> None:
    print(json.dumps(value, indent=2))


def payin_payload(merchant_id: str) -> dict[str, object]:
    return {
        "orderNo": os.environ.get("PAYNODO_PAYIN_ORDER_NO", "ORDPI2026000001"),
        "purpose": os.environ.get("PAYNODO_PAYIN_PURPOSE", "customer payment"),
        "merchant": {
            "merchantId": merchant_id,
            "merchantName": os.environ.get("PAYNODO_MERCHANT_NAME", "Integrated Merchant"),
        },
        "money": {
            "currency": "BRL",
            "amount": int(os.environ.get("PAYNODO_PAYIN_AMOUNT", "12000")),
        },
        "payer": {
            "pixAccount": os.environ.get("PAYNODO_PAYER_PIX_ACCOUNT", "48982488880"),
        },
        "paymentMethod": os.environ.get("PAYNODO_PAYIN_METHOD", "PIX"),
        "expiryPeriod": int(os.environ.get("PAYNODO_EXPIRY_PERIOD", "3600")),
        "redirectUrl": os.environ.get("PAYNODO_REDIRECT_URL", "https://merchant.example/return"),
        "callbackUrl": os.environ.get("PAYNODO_CALLBACK_URL", "https://merchant.example/webhooks/paynodo"),
    }


def payout_payload(merchant_id: str) -> dict[str, object]:
    return {
        "additionalParam": {},
        "cashAccount": os.environ.get("PAYNODO_PAYOUT_CASH_ACCOUNT", "12532481501"),
        "receiver": {
            "taxNumber": os.environ.get("PAYNODO_RECEIVER_TAX_NUMBER", "12345678909"),
            "accountName": os.environ.get("PAYNODO_RECEIVER_NAME", "Betty"),
        },
        "merchant": {
            "merchantId": merchant_id,
        },
        "money": {
            "amount": int(os.environ.get("PAYNODO_PAYOUT_AMOUNT", "10000")),
            "currency": "BRL",
        },
        "orderNo": os.environ.get("PAYNODO_PAYOUT_ORDER_NO", "ORDPO2026000001"),
        "paymentMethod": os.environ.get("PAYNODO_PAYOUT_METHOD", "CPF"),
        "purpose": os.environ.get("PAYNODO_PAYOUT_PURPOSE", "Purpose For Disbursement from API"),
        "callbackUrl": os.environ.get("PAYNODO_CALLBACK_URL", "https://merchant.example/webhooks/paynodo"),
    }


def status_payload() -> dict[str, object]:
    return {
        "tradeType": int(os.environ.get("PAYNODO_STATUS_TRADE_TYPE", "1")),
        "orderNo": os.environ.get("PAYNODO_STATUS_ORDER_NO", os.environ.get("PAYNODO_PAYIN_ORDER_NO", "ORDPI2026000001")),
    }


def balance_payload() -> dict[str, object]:
    return {
        "accountNo": os.environ.get("PAYNODO_ACCOUNT_NO", "YOUR_ACCOUNT_NO"),
        "balanceTypes": ["BALANCE"],
    }


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    main()
