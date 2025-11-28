from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    """Load .env (template) then .env.local with override=True so local values win."""
    pkg_dir = Path(__file__).resolve().parent
    env_base = pkg_dir.parent / ".env"
    env_local = pkg_dir.parent / ".env.local"
    load_dotenv(env_base, override=True)
    load_dotenv(env_local, override=True)


_load_env()


def env_str(key: str, default: str | None = None, required: bool = False) -> str | None:
    val = os.environ.get(key, default)
    if required and not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # .../ACDevHub

DATA_DIR = Path(env_str("DATA_DIR", "../../data")).resolve()
if not DATA_DIR.is_absolute():
    DATA_DIR = (PROJECT_ROOT / DATA_DIR).resolve()

LOG_DIR = (PROJECT_ROOT / "agents" / "python" / "logs").resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Salesforce connection
API_VERSION = env_str("SF_API_VERSION", "65.0")
SF_CLIENT_ID = env_str("SF_CLIENT_ID", required=True)
SF_USERNAME = env_str("SF_USERNAME", required=True)
SF_LOGIN_URL = env_str("SF_LOGIN_URL", required=True)
SF_AUDIENCE = env_str("SF_AUDIENCE", required=True)
raw_key_path = Path(env_str("SF_JWT_KEY_PATH", required=True)).expanduser()
candidate_paths = []
if raw_key_path.is_absolute():
    candidate_paths.append(raw_key_path)
else:
    # Try resolving relative to project root, agents/python, and repo config/
    candidate_paths.append((PROJECT_ROOT / raw_key_path).resolve())
    candidate_paths.append((PROJECT_ROOT / "agents" / "python" / raw_key_path).resolve())
    candidate_paths.append((PROJECT_ROOT / "config" / raw_key_path.name).resolve())

SF_JWT_KEY_PATH = None
for p in candidate_paths:
    if p.exists():
        SF_JWT_KEY_PATH = p
        break
if SF_JWT_KEY_PATH is None:
    raise FileNotFoundError(f"SF_JWT_KEY_PATH not found. Tried: {candidate_paths}")

def ensure_output_dir(object_name: str) -> Path:
    out_dir = PROJECT_ROOT / "data" / "output" / object_name
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
