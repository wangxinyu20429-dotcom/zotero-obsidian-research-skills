#!/usr/bin/env python3
"""Guarded Zotero Connector importer for new items and validated PDFs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import zotero_dedup as dedup

CONNECTOR = "http://127.0.0.1:23119"
LOCAL_API = "http://127.0.0.1:23119/api"


def http(path: str, payload: Any = None, raw: bytes | None = None,
         headers: dict[str, str] | None = None, timeout: int = 30) -> tuple[int, str, bytes]:
    url = CONNECTOR.rstrip("/") + path
    request_headers = {"Accept": "application/json"}
    body = raw
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Connector {path} returned HTTP {exc.code}: {detail}") from exc


def selected_target() -> dict[str, Any]:
    status, _, body = http("/connector/getSelectedCollection", payload={})
    if status != 200:
        raise RuntimeError(f"Unexpected target response: HTTP {status}")
    value = json.loads(body or b"{}")
    return {
        "libraryID": value.get("libraryID"),
        "libraryName": value.get("libraryName"),
        "libraryEditable": value.get("libraryEditable"),
        "filesEditable": value.get("filesEditable"),
        "collectionInternalID": value.get("id"),
        "collectionName": value.get("name"),
        "editable": value.get("editable"),
    }


def load_candidate(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(value, dict) and isinstance(value.get("candidates"), list):
        if len(value["candidates"]) != 1:
            raise ValueError("Importer accepts exactly one candidate per invocation")
        value = value["candidates"][0]
    if isinstance(value, list):
        if len(value) != 1:
            raise ValueError("Importer accepts exactly one candidate per invocation")
        value = value[0]
    if not isinstance(value, dict) or not str(value.get("title", "")).strip():
        raise ValueError("Candidate must be one JSON object with a non-empty title")
    return value


def validate_pdf(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"PDF does not exist: {path}")
    size = path.stat().st_size
    if size < 5:
        raise ValueError("PDF is empty or truncated")
    with path.open("rb") as stream:
        magic = stream.read(5)
    if magic != b"%PDF-":
        raise ValueError("File does not begin with %PDF-; refusing possible HTML/error page")
    return {"path": str(path.resolve()), "size": size, "magic": "%PDF-"}


def creators(candidate: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for author in candidate.get("authors") or candidate.get("creators") or []:
        if isinstance(author, dict):
            entry = {"creatorType": str(author.get("creatorType") or "author")}
            if author.get("name"):
                entry["name"] = str(author["name"])
            else:
                entry["firstName"] = str(author.get("firstName") or "")
                entry["lastName"] = str(author.get("lastName") or "")
            result.append(entry)
        elif str(author).strip():
            result.append({"creatorType": "author", "name": str(author).strip()})
    return result


def zotero_item(candidate: dict[str, Any], connector_id: str) -> dict[str, Any]:
    tags = candidate.get("tags") or []
    return {
        "id": connector_id,
        "itemType": str(candidate.get("itemType") or "journalArticle"),
        "title": str(candidate.get("title") or ""),
        "creators": creators(candidate),
        "abstractNote": str(candidate.get("abstract") or candidate.get("abstractNote") or ""),
        "publicationTitle": str(candidate.get("journal") or candidate.get("publicationTitle") or ""),
        "volume": str(candidate.get("volume") or ""),
        "issue": str(candidate.get("issue") or ""),
        "pages": str(candidate.get("pages") or ""),
        "date": str(candidate.get("date") or candidate.get("year") or ""),
        "DOI": dedup.normalize_doi(candidate.get("doi") or candidate.get("DOI")),
        "url": str(candidate.get("url") or ""),
        "language": str(candidate.get("language") or ""),
        "tags": [{"tag": str(x.get("tag"))} if isinstance(x, dict) else {"tag": str(x)} for x in tags],
        "attachments": [],
        "notes": [],
    }


def find_matches(candidate: dict[str, Any], threshold: float = 0.90) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    norm = dedup.normalized(candidate)
    exact, probable = [], []
    for item in dedup.paged(LOCAL_API, "items/top"):
        item_norm = dedup.normalized(item, zotero=True)
        hit = dedup.exact_id_match(norm, item_norm)
        near, similarity = dedup.probable_match(norm, item_norm, threshold)
        if hit:
            compact = dedup.compact_zotero(item)
            compact["reason"] = f"exact_{hit[0]}"
            exact.append(compact)
        elif near:
            compact = dedup.compact_zotero(item)
            compact.update({"reason": "probable_title_author_year", "similarity": round(similarity, 4)})
            probable.append(compact)
    return exact, probable


def target_details(path: str) -> dict[str, Any]:
    collections = dedup.paged(LOCAL_API, "collections")
    target = dedup.resolve_collection(path, collections)
    if target is None:
        raise ValueError("A target collection is required")
    target["leaf_name"] = target["path"].split("/")[-1]
    return target


def child_pdf_status(item_key: str) -> list[dict[str, Any]]:
    children = dedup.paged(LOCAL_API, f"items/{item_key}/children")
    result = []
    for child in children:
        data = child.get("data", {})
        if data.get("itemType") == "attachment" and (
            data.get("contentType") == "application/pdf" or str(data.get("filename", "")).lower().endswith(".pdf")
        ):
            result.append({"key": child.get("key"), "title": data.get("title"),
                           "filename": data.get("filename"), "contentType": data.get("contentType")})
    return result


def cmd_import(args: argparse.Namespace) -> dict[str, Any]:
    candidate = load_candidate(Path(args.candidate))
    target = target_details(args.target_collection)
    selected = selected_target()
    if not selected.get("editable") or not selected.get("libraryEditable"):
        raise RuntimeError("The currently selected Zotero target is not editable")
    if selected.get("collectionName") != target["leaf_name"]:
        raise RuntimeError(
            f"Zotero currently targets {selected.get('libraryName')!r}/{selected.get('collectionName')!r}; "
            f"select collection {target['path']!r} in Zotero first"
        )

    exact, probable = find_matches(candidate, args.threshold)
    if exact or probable:
        raise RuntimeError(json.dumps({"error": "DUPLICATE_GUARD", "exact": exact, "probable": probable}, ensure_ascii=False))

    pdf_info = validate_pdf(Path(args.pdf)) if args.pdf else None
    if not pdf_info and not args.resolver and not args.allow_metadata_only:
        raise ValueError("Provide --pdf, --resolver, or explicitly authorize --allow-metadata-only")
    if args.resolver and not args.accept_metadata_only_on_resolver_failure:
        raise ValueError("Resolver can fail after metadata is created; acknowledge with --accept-metadata-only-on-resolver-failure")

    plan = {"candidate": candidate.get("title"), "target": target, "selected": selected,
            "pdf": pdf_info, "resolver": bool(args.resolver), "metadata_only": bool(args.allow_metadata_only)}
    if not args.yes:
        return {"ok": True, "dry_run": True, "plan": plan}

    session_id = uuid.uuid4().hex
    connector_id = "item-1"
    item = zotero_item(candidate, connector_id)
    status, _, _ = http("/connector/saveItems", payload={"sessionID": session_id, "items": [item]}, timeout=60)
    if status != 201:
        raise RuntimeError(f"saveItems returned HTTP {status}")

    attachment_result: dict[str, Any] = {"attempted": False, "saved": False}
    if pdf_info:
        pdf_path = Path(pdf_info["path"])
        data = pdf_path.read_bytes()
        metadata = {"sessionID": session_id, "parentItemID": connector_id,
                    "title": pdf_path.stem, "url": str(candidate.get("pdf_url") or pdf_path.as_uri())}
        headers = {"Content-Type": "application/pdf", "Content-Length": str(len(data)),
                   "X-Metadata": json.dumps(metadata, ensure_ascii=False)}
        attach_status, _, _ = http("/connector/saveAttachment", raw=data, headers=headers, timeout=120)
        attachment_result = {"attempted": True, "saved": attach_status == 201, "method": "validated_local_pdf",
                             "status": attach_status}
    elif args.resolver:
        try:
            attach_status, _, body = http("/connector/saveAttachmentFromResolver",
                                          payload={"sessionID": session_id, "itemID": connector_id}, timeout=120)
            attachment_result = {"attempted": True, "saved": attach_status == 201, "method": "resolver",
                                 "status": attach_status, "message": body.decode("utf-8", errors="replace")}
        except RuntimeError as exc:
            attachment_result = {"attempted": True, "saved": False, "method": "resolver", "error": str(exc)}

    saved_matches: list[dict[str, Any]] = []
    for _ in range(10):
        time.sleep(0.5)
        exact_after, probable_after = find_matches(candidate, args.threshold)
        saved_matches = exact_after or probable_after
        if saved_matches:
            break
    if len(saved_matches) != 1:
        raise RuntimeError(f"Post-save verification found {len(saved_matches)} exact matches; inspect Zotero manually")
    saved = saved_matches[0]
    if target["key"] not in saved.get("collections", []):
        raise RuntimeError(f"Saved item {saved.get('key')} is not in target collection {target['key']}")
    pdf_children: list[dict[str, Any]] = []
    for _ in range(10):
        pdf_children = child_pdf_status(str(saved["key"]))
        if pdf_children or not (pdf_info or args.resolver):
            break
        time.sleep(0.5)
    verified_pdf = bool(pdf_children)
    if (pdf_info or args.resolver) and not verified_pdf:
        attachment_result["saved"] = False
        attachment_result["verification_error"] = "No PDF child attachment visible after save"

    return {"ok": True, "dry_run": False, "item": saved, "target": target,
            "attachment": attachment_result, "pdf_children": pdf_children,
            "status": "Saved" if (verified_pdf or args.allow_metadata_only) else "Failed"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selected-target")
    validate = sub.add_parser("validate")
    validate.add_argument("--candidate", required=True)
    validate.add_argument("--pdf")
    imp = sub.add_parser("import")
    imp.add_argument("--candidate", required=True)
    imp.add_argument("--target-collection", required=True)
    imp.add_argument("--pdf")
    imp.add_argument("--resolver", action="store_true")
    imp.add_argument("--accept-metadata-only-on-resolver-failure", action="store_true")
    imp.add_argument("--allow-metadata-only", action="store_true")
    imp.add_argument("--threshold", type=float, default=0.90)
    imp.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "selected-target":
            result = {"ok": True, "selected_target": selected_target()}
        elif args.command == "validate":
            candidate = load_candidate(Path(args.candidate))
            result = {"ok": True, "candidate": candidate.get("title"),
                      "pdf": validate_pdf(Path(args.pdf)) if args.pdf else None,
                      "duplicates": dict(zip(("exact", "probable"), find_matches(candidate)))}
        else:
            result = cmd_import(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 2
    except (urllib.error.URLError, OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
