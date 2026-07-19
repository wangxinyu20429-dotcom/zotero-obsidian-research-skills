#!/usr/bin/env python3
"""Read-only Zotero candidate and library duplicate audit (stdlib only)."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE = "http://127.0.0.1:23119/api"


def request_json(url: str, timeout: int = 10) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def paged(base: str, resource: str, extra: dict[str, str] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start, limit = 0, 100
    while True:
        params = {"format": "json", "limit": str(limit), "start": str(start)}
        if extra:
            params.update(extra)
        url = f"{base.rstrip('/')}/users/0/{resource}?{urllib.parse.urlencode(params)}"
        page = request_json(url)
        if not isinstance(page, list):
            raise RuntimeError(f"Unexpected Zotero response for {resource}")
        rows.extend(page)
        if len(page) < limit:
            return rows
        start += limit


def normalize_doi(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text)
    return text.rstrip(". ,;)")


def normalize_id(value: Any, prefix: str = "") -> str:
    text = str(value or "").strip().lower()
    if prefix:
        text = re.sub(rf"^{re.escape(prefix.lower())}:?\s*", "", text)
    return text


def normalize_title(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = "".join(ch if ch.isalnum() else " " for ch in text)
    return " ".join(text.split())


def title_tokens(value: Any) -> set[str]:
    return set(normalize_title(value).split())


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def year_of(value: Any) -> str:
    match = re.search(r"(?:19|20)\d{2}", str(value or ""))
    return match.group(0) if match else ""


def author_surname(record: dict[str, Any]) -> str:
    authors = record.get("authors") or record.get("creators") or []
    if authors and isinstance(authors[0], dict):
        first = authors[0]
        return normalize_title(first.get("lastName") or first.get("name") or "")
    value = record.get("first_author") or ""
    return normalize_title(str(value).split(",")[0].split()[-1] if value else "")


def extra_ids(extra: Any) -> dict[str, str]:
    result = {"pmid": "", "pmcid": "", "arxiv_id": ""}
    for line in str(extra or "").splitlines():
        match = re.match(r"\s*(PMID|PMCID|arXiv)\s*:\s*(\S+)", line, flags=re.I)
        if match:
            key = {"pmid": "pmid", "pmcid": "pmcid", "arxiv": "arxiv_id"}[match.group(1).lower()]
            result[key] = normalize_id(match.group(2), match.group(1))
    return result


def normalized(record: dict[str, Any], zotero: bool = False) -> dict[str, Any]:
    data = record.get("data", record) if zotero else record
    ids = extra_ids(data.get("extra"))
    return {
        "doi": normalize_doi(data.get("DOI") or data.get("doi")),
        "pmid": normalize_id(data.get("pmid") or ids["pmid"], "pmid"),
        "pmcid": normalize_id(data.get("pmcid") or ids["pmcid"], "pmcid"),
        "arxiv_id": normalize_id(data.get("arxiv_id") or ids["arxiv_id"], "arxiv"),
        "title": normalize_title(data.get("title")),
        "tokens": title_tokens(data.get("title")),
        "author": author_surname(data),
        "year": year_of(data.get("year") or data.get("date")),
    }


def exact_id_match(a: dict[str, Any], b: dict[str, Any]) -> tuple[str, str] | None:
    for key in ("doi", "pmid", "pmcid", "arxiv_id"):
        if a[key] and a[key] == b[key]:
            return key, a[key]
    return None


def probable_match(a: dict[str, Any], b: dict[str, Any], threshold: float) -> tuple[bool, float]:
    similarity = jaccard(a["tokens"], b["tokens"])
    author_ok = not a["author"] or not b["author"] or a["author"] == b["author"]
    year_ok = not a["year"] or not b["year"] or a["year"] == b["year"]
    return similarity >= threshold and author_ok and year_ok, similarity


def compact_zotero(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data", {})
    return {
        "key": item.get("key") or data.get("key"),
        "version": item.get("version") or data.get("version"),
        "title": data.get("title", ""),
        "date": data.get("date", ""),
        "DOI": data.get("DOI", ""),
        "itemType": data.get("itemType", ""),
        "collections": data.get("collections", []),
    }


def load_candidates(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(value, dict):
        value = value.get("candidates", [value] if value.get("title") else None)
    if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
        raise ValueError("Candidate file must be a JSON array or an object with a candidates array")
    return value


def collection_map(collections: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    by_key = {str(c.get("key") or c.get("data", {}).get("key")): c for c in collections}
    paths: dict[str, str] = {}

    def build(key: str, seen: set[str] | None = None) -> str:
        if key in paths:
            return paths[key]
        seen = set() if seen is None else seen
        if key in seen or key not in by_key:
            return key
        seen.add(key)
        data = by_key[key].get("data", {})
        name = data.get("name", key)
        parent = data.get("parentCollection")
        path = f"{build(str(parent), seen)}/{name}" if parent else name
        paths[key] = path
        return path

    for key in by_key:
        build(key)
    return by_key, paths


def resolve_collection(query: str | None, collections: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not query:
        return None
    _, paths = collection_map(collections)
    folded = query.replace("\\", "/").strip("/").casefold()
    matches = [(key, path) for key, path in paths.items() if key.casefold() == folded or path.casefold() == folded]
    if len(matches) != 1:
        suffix = [(key, path) for key, path in paths.items() if path.casefold().endswith("/" + folded)]
        matches = suffix if len(suffix) == 1 else matches
    if len(matches) != 1:
        choices = [path for _, path in paths.items() if folded in path.casefold()][:20]
        raise ValueError(f"Target collection is missing or ambiguous: {query!r}; possible matches: {choices}")
    key, path = matches[0]
    return {"key": key, "path": path}


def cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    items = paged(args.base, "items/top")
    collections = paged(args.base, "collections")
    return {"ok": True, "base": args.base, "top_level_items": len(items), "collections": len(collections)}


def cmd_collections(args: argparse.Namespace) -> list[dict[str, str]]:
    collections = paged(args.base, "collections")
    _, paths = collection_map(collections)
    return [{"key": key, "path": path} for key, path in sorted(paths.items(), key=lambda x: x[1].casefold())]


def cmd_audit(args: argparse.Namespace) -> dict[str, Any]:
    candidates = load_candidates(Path(args.candidates))
    items = paged(args.base, "items/top")
    collections = paged(args.base, "collections")
    target = resolve_collection(args.target_collection, collections)

    unique: list[dict[str, Any]] = []
    unique_norm: list[dict[str, Any]] = []
    candidate_duplicates: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        norm = normalized(candidate)
        duplicate = None
        for kept_index, kept_norm in enumerate(unique_norm):
            exact = exact_id_match(norm, kept_norm)
            probable, similarity = probable_match(norm, kept_norm, args.threshold)
            if exact or probable:
                duplicate = {"candidate_index": index, "duplicate_of_unique_index": kept_index,
                             "reason": f"exact_{exact[0]}" if exact else "probable_title_author_year",
                             "similarity": round(similarity, 4)}
                break
        if duplicate:
            candidate_duplicates.append(duplicate)
        else:
            unique.append(candidate)
            unique_norm.append(norm)

    item_norms = [normalized(item, zotero=True) for item in items]
    existing_exact, existing_probable, conflicts, new_items = [], [], [], []
    for index, (candidate, norm) in enumerate(zip(unique, unique_norm)):
        exact_hits, probable_hits = [], []
        for item, item_norm in zip(items, item_norms):
            exact = exact_id_match(norm, item_norm)
            probable, similarity = probable_match(norm, item_norm, args.threshold)
            if exact:
                hit = compact_zotero(item)
                hit.update({"identifier": exact[0], "identifier_value": exact[1]})
                exact_hits.append(hit)
                if norm["title"] and item_norm["title"] and jaccard(norm["tokens"], item_norm["tokens"]) < 0.6:
                    conflicts.append({"unique_index": index, "candidate": candidate, "existing": hit,
                                      "reason": "same_identifier_materially_different_title"})
            elif probable:
                hit = compact_zotero(item)
                hit["similarity"] = round(similarity, 4)
                probable_hits.append(hit)
        entry = {"unique_index": index, "candidate": candidate}
        if exact_hits:
            entry["matches"] = exact_hits
            existing_exact.append(entry)
        elif probable_hits:
            entry["matches"] = probable_hits
            existing_probable.append(entry)
        else:
            new_items.append(entry)

    return {
        "ok": True,
        "read_only": True,
        "target_collection": target,
        "counts": {"input": len(candidates), "unique": len(unique), "candidate_duplicates": len(candidate_duplicates),
                   "existing_exact": len(existing_exact), "existing_probable": len(existing_probable),
                   "conflicts": len(conflicts), "new": len(new_items), "zotero_items_scanned": len(items)},
        "candidate_duplicates": candidate_duplicates,
        "existing_exact": existing_exact,
        "existing_probable": existing_probable,
        "conflicts": conflicts,
        "new_items": new_items,
        "unique_candidates": unique,
    }


def emit(value: Any, output: str | None = None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
    print(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE, help="Zotero local API base")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("collections")
    audit = sub.add_parser("audit")
    audit.add_argument("--candidates", required=True)
    audit.add_argument("--target-collection")
    audit.add_argument("--threshold", type=float, default=0.90)
    audit.add_argument("--output")
    args = parser.parse_args()
    try:
        if args.command == "status":
            emit(cmd_status(args))
        elif args.command == "collections":
            emit(cmd_collections(args))
        else:
            emit(cmd_audit(args), args.output)
        return 0
    except (urllib.error.URLError, OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
