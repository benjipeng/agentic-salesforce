"""
Lightweight REST ping to validate JWT auth + a SOQL query.

Usage (from agents/python):
    uv run python tools/rest_ping.py

What it does:
- Builds a JWT using the same env/config as check_jwt.py.
- Exchanges it for an access token.
- Runs a SOQL query (default: SELECT Id, Name FROM Account LIMIT 5).
- Prints record count and the instance URL.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
import jwt
from dotenv import load_dotenv


def load_env() -> None:
    env_base = Path(__file__).parent.parent / ".env"
    env_local = Path(__file__).parent.parent / ".env.local"
    load_dotenv(env_base, override=True)
    load_dotenv(env_local, override=True)
    required = [
        "SF_CLIENT_ID",
        "SF_USERNAME",
        "SF_LOGIN_URL",
        "SF_AUDIENCE",
        "SF_JWT_KEY_PATH",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        sys.exit(f"Missing env vars: {', '.join(missing)}")


def resolve_key_path(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.is_absolute():
        # relative to repo/agents/python
        p = (Path(__file__).parent.parent / p).resolve()
        if not p.exists():
            # relative to repo root
            p = (Path(__file__).parent.parent.parent / p).resolve()
    return p


def build_jwt() -> str:
    now = int(time.time())
    audience = os.environ["SF_AUDIENCE"]
    if not audience.startswith("http"):
        audience = f"https://{audience}"
    payload = {
        "iss": os.environ["SF_CLIENT_ID"],
        "sub": os.environ["SF_USERNAME"],
        "aud": audience,
        "exp": now + 5 * 60,
    }
    key_path = resolve_key_path(os.environ["SF_JWT_KEY_PATH"])
    if not key_path.exists():
        sys.exit(f"Private key not found at {key_path}")
    private_key = key_path.read_bytes()
    return jwt.encode(payload, private_key, algorithm="RS256")


def request_token(assertion: str) -> dict:
    login_url = os.environ["SF_LOGIN_URL"].rstrip("/")
    if not login_url.startswith("http"):
        login_url = f"https://{login_url}"
    token_url = f"{login_url}/services/oauth2/token"
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
        "client_id": os.environ["SF_CLIENT_ID"],
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(token_url, data=data)
    if resp.status_code != 200:
        sys.exit(f"Token request failed ({resp.status_code}): {resp.text}")
    return resp.json()


def soql_query(instance_url: str, access_token: str, soql: str) -> dict:
    q_url = f"{instance_url}/services/data/v{os.environ.get('SF_API_VERSION','65.0')}/query"
    params = {"q": soql}
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=30) as client:
        resp = client.get(q_url, headers=headers, params=params)
    if resp.status_code != 200:
        sys.exit(f"SOQL failed ({resp.status_code}): {resp.text}")
    return resp.json()


def main():
    load_env()
    assertion = build_jwt()
    token_resp = request_token(assertion)
    access_token = token_resp["access_token"]
    instance_url = token_resp["instance_url"]

    soql = "SELECT Id, Name FROM Account LIMIT 5"
    result = soql_query(instance_url, access_token, soql)
    records = result.get("records", [])

    print("✓ REST ping succeeded")
    print(f"Instance URL: {instance_url}")
    print(f"Records returned: {len(records)}")
    if records:
        for r in records:
            print(f"- {r.get('Id')} | {r.get('Name')}")


if __name__ == "__main__":
    main()
