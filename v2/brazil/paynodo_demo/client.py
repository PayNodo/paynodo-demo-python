from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

DEFAULT_BASE_URL = "https://sandbox-api.paynodo.com"


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        os.environ.setdefault(key, value)


def read_pem(value_or_path: str) -> bytes:
    if not value_or_path:
        raise ValueError("Missing PEM value or path")
    if "-----BEGIN" in value_or_path:
        return value_or_path.replace("\\n", "\n").encode()
    return Path(value_or_path).expanduser().resolve().read_bytes()


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())


def minify_json(payload: Any) -> str:
    value = json.loads(payload) if isinstance(payload, str) else payload
    return json.dumps(value if value is not None else {}, separators=(",", ":"))


def build_string_to_sign(timestamp: str, merchant_secret: str, payload: Any) -> str:
    return "|".join([timestamp, merchant_secret, minify_json(payload)])


def sign_payload(timestamp: str, merchant_secret: str, payload: Any, private_key_pem: bytes) -> dict[str, str]:
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    string_to_sign = build_string_to_sign(timestamp, merchant_secret, payload)
    signature = private_key.sign(
        string_to_sign.encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return {
        "signature": base64.b64encode(signature).decode(),
        "stringToSign": string_to_sign,
        "body": minify_json(payload),
    }


def signed_headers(
    merchant_id: str,
    timestamp: str,
    merchant_secret: str,
    payload: Any,
    private_key_pem: bytes,
) -> dict[str, Any]:
    signed = sign_payload(timestamp, merchant_secret, payload, private_key_pem)
    return {
        "headers": {
            "Content-Type": "application/json",
            "X-PARTNER-ID": merchant_id,
            "X-TIMESTAMP": timestamp,
            "X-SIGNATURE": signed["signature"],
        },
        "body": signed["body"],
        "stringToSign": signed["stringToSign"],
    }


def verify_callback(raw_body: str, timestamp: str, signature: str, platform_public_key_pem: bytes) -> bool:
    public_key = serialization.load_pem_public_key(platform_public_key_pem)
    string_to_verify = "|".join([timestamp, minify_json(raw_body)])
    try:
        public_key.verify(
            base64.b64decode(signature),
            string_to_verify.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


class PayNodoClient:
    def __init__(
        self,
        merchant_id: str,
        merchant_secret: str,
        private_key_pem: bytes,
        base_url: str = DEFAULT_BASE_URL,
        now: Callable[[], str] | None = None,
    ) -> None:
        if not merchant_id:
            raise ValueError("merchant_id is required")
        if not merchant_secret:
            raise ValueError("merchant_secret is required")
        if not private_key_pem:
            raise ValueError("private_key_pem is required")
        self.merchant_id = merchant_id
        self.merchant_secret = merchant_secret
        self.private_key_pem = private_key_pem
        self.base_url = base_url.rstrip("/")
        self.now = now or _utc_now

    def request(self, method: str, endpoint: str, payload: Any | None = None) -> dict[str, Any]:
        method = method.upper()
        payload = {} if payload is None else payload
        signature_payload = {} if method == "GET" else payload
        signed = signed_headers(
            self.merchant_id,
            self.now(),
            self.merchant_secret,
            signature_payload,
            self.private_key_pem,
        )

        data = None if method == "GET" else signed["body"].encode()
        request = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=data,
            headers=signed["headers"],
            method=method,
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                text = response.read().decode()
                return {
                    "status": response.status,
                    "headers": dict(response.headers.items()),
                    "data": _parse_json_or_text(text),
                }
        except urllib.error.HTTPError as error:
            text = error.read().decode()
            return {
                "status": error.code,
                "headers": dict(error.headers.items()),
                "data": _parse_json_or_text(text),
            }

    def create_payin(self, payload: Any) -> dict[str, Any]:
        return self.request("POST", "/v2.0/transaction/pay-in", payload)

    def create_payout(self, payload: Any) -> dict[str, Any]:
        return self.request("POST", "/v2.0/disbursement/pay-out", payload)

    def inquiry_status(self, payload: Any) -> dict[str, Any]:
        return self.request("POST", "/v2.0/inquiry-status", payload)

    def inquiry_balance(self, payload: Any) -> dict[str, Any]:
        return self.request("POST", "/v2.0/inquiry-balance", payload)

    def payment_methods(self) -> dict[str, Any]:
        return self.request("GET", "/v2.0/payment-methods", {})


def _parse_json_or_text(value: str) -> Any:
    try:
        return json.loads(value) if value else None
    except json.JSONDecodeError:
        return value


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
