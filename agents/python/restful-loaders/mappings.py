from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable

from .rest_client import RestClient


def _chunk(seq: list[str], size: int = 200) -> Iterable[list[str]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def build_id_map(
    rest: RestClient,
    object_api: str,
    external_id_field: str,
    external_ids: Iterable[str],
) -> Dict[str, str]:
    """Return {external_id: sf_id} for the given object."""
    ids = [x for x in external_ids if x]
    result: Dict[str, str] = {}
    if not ids:
        return result
    for chunk in _chunk(ids, 200):
        ids_escaped = ["'%s'" % x.replace("'", "\\'") for x in chunk]
        soql = f"SELECT Id,{external_id_field} FROM {object_api} WHERE {external_id_field} IN ({','.join(ids_escaped)})"
        records = rest.query(soql)
        for r in records:
            key = r.get(external_id_field)
            if key:
                result[key] = r["Id"]
    return result


def external_ids_from_csv(csv_path: Path, column: str) -> list[str]:
    ids: list[str] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            val = row.get(column)
            if val:
                ids.append(val)
    return ids
