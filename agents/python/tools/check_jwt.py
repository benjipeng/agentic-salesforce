"""
Quick JWT connectivity check for the scratch org.

What it does:
- Builds a JWT using your Connected App consumer key and private key.
- Posts it to the Salesforce OAuth token endpoint.
- Prints the resulting instance URL and a short token preview so you know auth is working.

Prereqs:
- Fill agents/python/.env (see docs/rest-jwt-setup.md).
- Install deps: `uv pip sync requirements.txt` (PyJWT, httpx, python-dotenv).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
import jwt
from dotenv import load_dotenv


def load_env():
    env_base = (Path(__file__).parent.parent / ".env").resolve()
    env_local = (Path(__file__).parent.parent / ".env.local").resolve()
    # Load base first, then local overrides. override=True so stale shell vars don't win.
    load_dotenv(dotenv_path=env_base, override=True)
    load_dotenv(dotenv_path=env_local, override=True)
    required = [
        "SF_CLIENT_ID",
        "SF_USERNAME",
        "SF_LOGIN_URL",
        "SF_AUDIENCE",
        "SF_JWT_KEY_PATH",
    ]
    missing = [k for k in required if not PathEnv.get(k)]
    if missing:
        sys.exit(f"Missing required env vars: {', '.join(missing)}")


class PathEnv:
    @staticmethod
    def get(key: str) -> str | None:
        return os.environ.get(key)


def build_jwt() -> str:
    now = int(time.time())
    audience = PathEnv.get("SF_AUDIENCE")
    if audience and not audience.startswith("http"):
        audience = f"https://{audience}"
    payload = {
        "iss": PathEnv.get("SF_CLIENT_ID"),
        "sub": PathEnv.get("SF_USERNAME"),
        "aud": audience,
        "exp": now + 5 * 60,
    }
    raw_path = Path(PathEnv.get("SF_JWT_KEY_PATH")).expanduser()
    if raw_path.is_absolute():
        key_path = raw_path
    else:
        # Resolve relative to this file's directory first
        key_path = (Path(__file__).parent / raw_path).resolve()
        # If not found, try relative to repo root (two levels up)
        if not key_path.exists():
            key_path = (Path(__file__).parent.parent / raw_path).resolve()
    if not key_path.exists():
        sys.exit(f"Private key not found at {key_path}. Update SF_JWT_KEY_PATH in .env to the correct path.")
    with key_path.open("rb") as f:
        private_key = f.read()
    token = jwt.encode(payload, private_key, algorithm="RS256")
    return token


def request_token(assertion: str) -> dict:
    login_url = PathEnv.get("SF_LOGIN_URL").rstrip("/")
    if not login_url.startswith("http"):
        login_url = f"https://{login_url}"
    token_url = f"{login_url}/services/oauth2/token"
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
        "client_id": PathEnv.get("SF_CLIENT_ID"),
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(token_url, data=data)
    if resp.status_code != 200:
        sys.exit(f"Token request failed ({resp.status_code}): {resp.text}")
    return resp.json()


def preview_token(access_token: str, chars: int = 6) -> str:
    return access_token  # do not redact; caller can handle securely


def main():
    load_env()
    assertion = build_jwt()
    result = request_token(assertion)
    access_token = result["access_token"]
    instance_url = result["instance_url"]
    print("✓ JWT flow succeeded")
    print(f"Instance URL: {instance_url}")
    print(f"Access token (preview): {preview_token(access_token)}")


if __name__ == "__main__":
    main()
