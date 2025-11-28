from __future__ import annotations

import time
from pathlib import Path

import httpx
import jwt

from . import config


def build_jwt_assertion() -> str:
    now = int(time.time())
    audience = config.SF_AUDIENCE
    if not audience.startswith("http"):
        audience = f"https://{audience}"
    payload = {
        "iss": config.SF_CLIENT_ID,
        "sub": config.SF_USERNAME,
        "aud": audience,
        "exp": now + 5 * 60,
    }
    key_bytes = Path(config.SF_JWT_KEY_PATH).read_bytes()
    return jwt.encode(payload, key_bytes, algorithm="RS256")


def get_access_token() -> tuple[str, str]:
    """Return (access_token, instance_url)."""
    assertion = build_jwt_assertion()
    login_url = config.SF_LOGIN_URL.rstrip("/")
    if not login_url.startswith("http"):
        login_url = f"https://{login_url}"
    token_url = f"{login_url}/services/oauth2/token"
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
        "client_id": config.SF_CLIENT_ID,
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(token_url, data=data)
    resp.raise_for_status()
    j = resp.json()
    return j["access_token"], j["instance_url"]
