# PayNodo Brazil V2 Python Demo

Backend-only Python demo for PayNodo Brazil V2.

## Requirements

- Python 3.10+
- `cryptography`

## Setup

```shell
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and replace sandbox values with the credentials from the merchant cabinet.
Save the merchant private key as `merchant-private-key.pem`, or set `PAYNODO_PRIVATE_KEY_PEM` directly in `.env`.

## Generate a signed PayIn preview

```shell
python3 -m paynodo_demo.demo sign-payin
```

## Send sandbox requests

```shell
python3 -m paynodo_demo.demo payin
python3 -m paynodo_demo.demo payout
python3 -m paynodo_demo.demo status
python3 -m paynodo_demo.demo balance
python3 -m paynodo_demo.demo methods
```

## Verify a callback signature

```shell
PAYNODO_CALLBACK_BODY='{"orderNo":"ORDPI2026000001","status":"SUCCESS"}' \
PAYNODO_CALLBACK_TIMESTAMP='2026-04-17T13:25:10.000Z' \
PAYNODO_CALLBACK_SIGNATURE='replace_with_callback_signature' \
python3 -m paynodo_demo.demo verify-callback
```

The private key and merchant secret must stay on the merchant backend.
