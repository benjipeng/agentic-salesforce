from __future__ import annotations

import urllib.parse

import httpx

from . import config


class RestClient:
    def __init__(self, access_token: str, instance_url: str):
        self.access_token = access_token
        self.instance_url = instance_url.rstrip("/")
        self.api_version = config.API_VERSION
        self._headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.instance_url}/services/data/v{self.api_version}/{path.lstrip('/')}"

    def query(self, soql: str) -> list[dict]:
        encoded_soql = urllib.parse.quote(soql)
        url = self._url(f"query?q={encoded_soql}")
        with httpx.Client(timeout=30, headers=self._headers) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        records = data.get("records", [])
        while not data.get("done"):
            next_url = data["nextRecordsUrl"]
            with httpx.Client(timeout=30, headers=self._headers) as client:
                resp = client.get(self._url(next_url))
                resp.raise_for_status()
                data = resp.json()
            records.extend(data.get("records", []))
        return records

    def insert(self, object_api: str, records: list[dict]) -> list[dict]:
        """Composite insert up to 200 records."""
        if not records:
            return []
        url = self._url("composite/sobjects")
        body = {
            "allOrNone": False,
            "records": [{"attributes": {"type": object_api}, **r} for r in records],
        }
        with httpx.Client(timeout=30, headers={**self._headers, "Content-Type": "application/json"}) as client:
            resp = client.post(url, json=body)
            resp.raise_for_status()
            return resp.json()
