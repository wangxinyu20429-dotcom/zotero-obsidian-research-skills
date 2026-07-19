#!/usr/bin/env python3
"""Add an existing synced Zotero item to a collection via the official Web API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

API = "https://api.zotero.org"
KEY_RE = re.compile(r"^[A-Z0-9]{8}$", re.I)


def config() -> tuple[str, str]:
    user_id = os.environ.get("ZOTERO_USER_ID", "").strip()
    api_key = os.environ.get("ZOTERO_API_KEY", "").strip()
    if not user_id or not api_key:
        raise ValueError("Set ZOTERO_USER_ID and a write-enabled ZOTERO_API_KEY; secrets are not accepted as CLI arguments")
    if not user_id.isdigit():
        raise ValueError("ZOTERO_USER_ID must be numeric")
    return user_id, api_key


def call(path: str, api_key: str, method: str = "GET", payload: Any = None,
         version: int | None = None, timeout: int = 30) -> tuple[int, dict[str, str], bytes]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json", "Zotero-API-Version": "3", "Zotero-API-Key": api_key}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if version is not None:
        headers["If-Unmodified-Since-Version"] = str(version)
    req = urllib.request.Request(API + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Zotero Web API returned HTTP {exc.code}: {detail}") from exc


def get_json(path: str, api_key: str) -> dict[str, Any]:
    status, _, body = call(path, api_key)
    if status != 200:
        raise RuntimeError(f"Expected HTTP 200, got {status}")
    value = json.loads(body)
    if not isinstance(value, dict):
        raise RuntimeError("Unexpected Zotero Web API response")
    return value


def validate_key(value: str, label: str) -> str:
    value = value.strip().upper()
    if not KEY_RE.fullmatch(value):
        raise ValueError(f"{label} must be an 8-character Zotero key")
    return value


def add(args: argparse.Namespace) -> dict[str, Any]:
    user_id, api_key = config()
    item_key = validate_key(args.item_key, "item key")
    collection_key = validate_key(args.collection_key, "collection key")

    collection = get_json(f"/users/{user_id}/collections/{collection_key}", api_key)
    item = get_json(f"/users/{user_id}/items/{item_key}", api_key)
    data = item.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Item has no writable data object")
    current = list(data.get("collections") or [])
    plan = {"item_key": item_key, "item_title": data.get("title"), "collection_key": collection_key,
            "collection_name": collection.get("data", {}).get("name"), "already_present": collection_key in current}
    if collection_key in current:
        return {"ok": True, "dry_run": not args.yes, "changed": False, "plan": plan, "verified": True}
    if not args.yes:
        return {"ok": True, "dry_run": True, "changed": False, "plan": plan}

    version = int(item.get("version") or data.get("version") or 0)
    data["collections"] = current + [collection_key]
    status, _, _ = call(f"/users/{user_id}/items/{item_key}", api_key, method="PUT", payload=data, version=version)
    if status not in (200, 204):
        raise RuntimeError(f"Unexpected update response HTTP {status}")
    verified = get_json(f"/users/{user_id}/items/{item_key}", api_key)
    memberships = verified.get("data", {}).get("collections") or []
    if collection_key not in memberships:
        raise RuntimeError("Update returned success but collection membership was not visible on reread")
    return {"ok": True, "dry_run": False, "changed": True, "plan": plan, "verified": True,
            "new_version": verified.get("version")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    add_parser = sub.add_parser("add")
    add_parser.add_argument("--item-key", required=True)
    add_parser.add_argument("--collection-key", required=True)
    add_parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "status":
            user_id, _ = config()
            result = {"ok": True, "configured": True, "user_id": user_id, "api_key_present": True}
        else:
            result = add(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (urllib.error.URLError, OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
