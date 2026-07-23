#!/usr/bin/env python3
"""Search OpenAlex, create Zotero-import candidates, and retrieve lawful OA PDFs.

The script is stdlib-only. It never writes to Zotero and never places PDFs in
an Obsidian vault. OpenAlex API keys are read only from the OPENALEX_API_KEY
environment variable and are never written to logs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import os
import re
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


TOOL_VERSION = "0.4.0"
OPENALEX_API = "https://api.openalex.org"
OPENALEX_CONTENT = "https://content.openalex.org"
DEFAULT_ZOTERO_API = "http://127.0.0.1:23119"
USER_AGENT = "zotero-literature-import/0.4 OpenAlex-OA-client"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_doi(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text)
    return text.rstrip(" .")


def normalize_title(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def identity_key(doi: Any, title: Any, year: Any, first_author: Any) -> str:
    normalized_doi = normalize_doi(doi)
    if normalized_doi:
        return "doi:" + normalized_doi
    return "fallback:" + "|".join(
        [normalize_title(title), str(year or ""), normalize_title(first_author)]
    )


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8", newline="")
    temp.replace(path)


def write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    atomic_write_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            rows.append(value)
    return rows


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def signature(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_api_key() -> str:
    key = (os.environ.get("OPENALEX_API_KEY") or "").strip()
    if not key:
        raise ValueError(
            "OpenAlex API key required. Set OPENALEX_API_KEY; "
            "never store the key in the skill, Obsidian, logs, or command transcripts."
        )
    return key


def redact_secret(value: str, secret: str | None) -> str:
    if not secret:
        return value
    return value.replace(secret, "[REDACTED]")


def request_json(
    base_url: str,
    params: dict[str, Any] | None = None,
    *,
    api_key: str | None = None,
    retries: int = 4,
    timeout: int = 30,
) -> tuple[Any, dict[str, str]]:
    query = {key: value for key, value in (params or {}).items() if value not in (None, "")}
    if api_key:
        query["api_key"] = api_key
    url = base_url + ("?" + urllib.parse.urlencode(query) if query else "")
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise ValueError("OpenAlex/Zotero JSON response exceeded 20 MiB safety limit")
                headers = {key.lower(): value for key, value in response.headers.items()}
                return json.loads(data.decode("utf-8")), headers
        except urllib.error.HTTPError as exc:
            message = exc.read(2048).decode("utf-8", errors="replace")
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries - 1:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"HTTP {exc.code} from {urllib.parse.urlsplit(base_url).netloc}: {message}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < retries - 1:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"network error from {urllib.parse.urlsplit(base_url).netloc}: {exc}") from exc
    raise RuntimeError("request failed after retries")


def author_names(work: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") if isinstance(authorship, dict) else None
        name = str((author or {}).get("display_name") or "").strip()
        if name:
            names.append(name)
    return names


def venue_name(work: dict[str, Any]) -> str | None:
    for field in ("primary_location", "best_oa_location"):
        location = work.get(field)
        if isinstance(location, dict):
            source = location.get("source")
            if isinstance(source, dict) and source.get("display_name"):
                return str(source["display_name"])
    return None


def direct_oa_location(work: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    best = work.get("best_oa_location")
    if isinstance(best, dict):
        candidates.append(best)
    candidates.extend(location for location in (work.get("locations") or []) if isinstance(location, dict))
    seen: set[str] = set()
    ranked: list[tuple[tuple[int, int], dict[str, Any]]] = []
    version_rank = {"publishedVersion": 3, "acceptedVersion": 2, "submittedVersion": 1}
    for location in candidates:
        url = str(location.get("pdf_url") or "").strip()
        if not location.get("is_oa") or not url or url in seen:
            continue
        seen.add(url)
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        if host == "content.openalex.org":
            continue
        ranked.append(((1, version_rank.get(str(location.get("version")), 0)), location))
    if not ranked:
        return None
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return ranked[0][1]


def openalex_id(work: dict[str, Any]) -> str:
    return str(work.get("id") or "").rstrip("/").rsplit("/", 1)[-1]


def zotero_creators(data: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for creator in data.get("creators") or []:
        if not isinstance(creator, dict):
            continue
        name = " ".join(
            part
            for part in [str(creator.get("firstName") or "").strip(), str(creator.get("lastName") or "").strip()]
            if part
        ) or str(creator.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def load_zotero_identities(base_url: str, max_items: int = 10000) -> dict[str, str]:
    identities: dict[str, str] = {}
    start = 0
    while start < max_items:
        payload, _ = request_json(
            base_url.rstrip("/") + "/api/users/0/items/top",
            {"limit": 100, "start": start},
            retries=2,
            timeout=20,
        )
        if not isinstance(payload, list):
            raise ValueError("unexpected Zotero local API list response")
        for item in payload:
            if not isinstance(item, dict):
                continue
            data = item.get("data") if isinstance(item.get("data"), dict) else item
            creators = zotero_creators(data)
            year_match = re.search(r"(?:19|20)\d{2}", str(data.get("date") or ""))
            key = identity_key(
                data.get("DOI"),
                data.get("title"),
                int(year_match.group(0)) if year_match else None,
                creators[0] if creators else "",
            )
            if key != "fallback:||":
                identities.setdefault(key, str(item.get("key") or data.get("key") or ""))
        if len(payload) < 100:
            break
        start += len(payload)
    return identities


def make_candidate(work: dict[str, Any], rank: int, zotero_identities: dict[str, str] | None) -> dict[str, Any]:
    authors = author_names(work)
    location = direct_oa_location(work)
    direct_url = str((location or {}).get("pdf_url") or "") or None
    work_id = openalex_id(work)
    identity = identity_key(work.get("doi"), work.get("title") or work.get("display_name"), work.get("publication_year"), authors[0] if authors else "")
    duplicate_key = (zotero_identities or {}).get(identity)
    has_content = work.get("has_content") if isinstance(work.get("has_content"), dict) else {}
    best = work.get("best_oa_location") if isinstance(work.get("best_oa_location"), dict) else {}
    open_access = work.get("open_access") if isinstance(work.get("open_access"), dict) else {}
    if duplicate_key:
        eligibility = "duplicate_in_zotero"
    elif direct_url:
        eligibility = "eligible_direct_oa"
    elif has_content.get("pdf"):
        eligibility = "content_api_available_costed"
    else:
        eligibility = "no_pdf_location"
    return {
        "rank": rank,
        "openalex_id": work_id,
        "openalex_url": str(work.get("id") or "") or None,
        "doi": normalize_doi(work.get("doi")) or None,
        "title": work.get("title") or work.get("display_name"),
        "authors": authors,
        "first_author": authors[0] if authors else None,
        "year": work.get("publication_year"),
        "publication_date": work.get("publication_date"),
        "work_type": work.get("type"),
        "language": work.get("language"),
        "venue": venue_name(work),
        "cited_by_count": work.get("cited_by_count"),
        "is_retracted": bool(work.get("is_retracted")),
        "is_paratext": bool(work.get("is_paratext")),
        "oa_status": open_access.get("oa_status"),
        "best_oa_is_oa": bool(best.get("is_oa")),
        "license": (location or best).get("license") if (location or best) else None,
        "version": (location or best).get("version") if (location or best) else None,
        "landing_page_url": (location or best).get("landing_page_url") if (location or best) else None,
        "direct_oa_pdf_url": direct_url,
        "has_content_pdf": bool(has_content.get("pdf")),
        "content_urls": work.get("content_urls"),
        "identity_key": identity,
        "zotero_check_status": "checked" if zotero_identities is not None else "not_checked",
        "duplicate_in_zotero": bool(duplicate_key),
        "zotero_item_key": duplicate_key or None,
        "download_eligibility": eligibility,
        "rights_note": "PDF retains its original copyright and license; OpenAlex grants no additional rights.",
    }


def to_import_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    landing = candidate.get("landing_page_url") or candidate.get("openalex_url")
    if candidate.get("doi"):
        landing = landing or f"https://doi.org/{candidate['doi']}"
    return {
        "title": candidate.get("title"),
        "authors": [
            {"creatorType": "author", "name": name}
            for name in candidate.get("authors") or []
        ],
        "year": candidate.get("year"),
        "date": candidate.get("publication_date"),
        "journal": candidate.get("venue"),
        "doi": candidate.get("doi"),
        "url": landing,
        "language": candidate.get("language"),
        "pdf_url": candidate.get("direct_oa_pdf_url"),
        "pdf_access": {
            "status": "open" if candidate.get("direct_oa_pdf_url") else "unavailable",
            "source": "openalex_oa_location" if candidate.get("direct_oa_pdf_url") else None,
            "license": candidate.get("license"),
            "version": candidate.get("version"),
            "checked_at": now_iso(),
        },
        "metadata_sources": [candidate["openalex_url"]] if candidate.get("openalex_url") else [],
        "venue_evidence": {
            "status": "unverified",
            "source": "OpenAlex metadata; verify ranking claims independently",
            "checked_at": now_iso(),
        },
        "selection_reason": "",
        "openalex": {
            "id": candidate.get("openalex_id"),
            "rank": candidate.get("rank"),
            "cited_by_count": candidate.get("cited_by_count"),
            "oa_status": candidate.get("oa_status"),
            "zotero_check_status": candidate.get("zotero_check_status"),
            "duplicate_in_zotero": candidate.get("duplicate_in_zotero"),
            "zotero_item_key": candidate.get("zotero_item_key"),
            "download_eligibility": candidate.get("download_eligibility"),
            "rights_note": candidate.get("rights_note"),
        },
    }


def search_command(args: argparse.Namespace) -> int:
    api_key = get_api_key()
    batch_dir = Path(args.batch_dir).resolve()
    run_path = batch_dir / "openalex_search_run.json"
    candidates_path = batch_dir / "openalex_candidates.jsonl"
    import_candidates_path = batch_dir / "openalex_candidates.json"
    duplicates_path = batch_dir / "openalex_duplicates.csv"
    filters = [value for value in args.filter if value]
    if args.work_type != "any":
        filters.append(f"type:{args.work_type}")
    filters.extend(["is_retracted:false", "is_paratext:false"])
    if args.oa_only:
        filters.append("open_access.is_oa:true")
    if args.has_content:
        filters.append("has_content.pdf:true")
    if args.year_from:
        filters.append(f"publication_year:>{args.year_from - 1}")
    if args.year_to:
        filters.append(f"publication_year:<{args.year_to + 1}")
    request_identity = {
        "tool_version": TOOL_VERSION,
        "query": args.query,
        "filters": filters,
        "sort": args.sort,
        "max_results": args.max_results,
        "zotero_check": args.zotero_check,
    }
    request_signature = signature(request_identity)
    if run_path.exists():
        previous = json.loads(run_path.read_text(encoding="utf-8"))
        if (
            previous.get("request_signature") == request_signature
            and candidates_path.exists()
            and import_candidates_path.exists()
            and duplicates_path.exists()
        ):
            print(json.dumps({"status": "unchanged", "batch_dir": str(batch_dir)}, ensure_ascii=False, indent=2))
            return 0
        raise FileExistsError(f"refusing conflicting rerun in existing batch directory: {batch_dir}")

    batch_dir.mkdir(parents=True, exist_ok=True)
    zotero_identities = load_zotero_identities(args.zotero_base_url) if args.zotero_check else None
    results: list[dict[str, Any]] = []
    cursor = "*"
    calls = 0
    reported_cost = 0.0
    last_rate_headers: dict[str, str] = {}
    select = ",".join(
        [
            "id", "doi", "title", "display_name", "publication_year", "publication_date", "type", "language",
            "cited_by_count", "is_retracted", "is_paratext", "authorships", "primary_location", "best_oa_location",
            "locations", "open_access", "has_content", "content_urls",
        ]
    )
    while len(results) < args.max_results:
        per_page = min(100, args.max_results - len(results))
        payload, headers = request_json(
            OPENALEX_API + "/works",
            {
                "search": args.query,
                "filter": ",".join(filters),
                "sort": args.sort,
                "per_page": per_page,
                "cursor": cursor,
                "select": select,
            },
            api_key=api_key,
        )
        calls += 1
        last_rate_headers = headers
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ValueError("unexpected OpenAlex works response")
        page_results = [item for item in payload["results"] if isinstance(item, dict)]
        results.extend(page_results)
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        try:
            reported_cost += float(meta.get("cost_usd") or 0)
        except (TypeError, ValueError):
            pass
        cursor = str(meta.get("next_cursor") or "")
        if not page_results or not cursor:
            break

    candidates: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for rank, work in enumerate(results[: args.max_results], 1):
        candidate = make_candidate(work, rank, zotero_identities)
        identity = candidate["identity_key"]
        if identity in seen:
            duplicate_rows.append(
                {
                    "duplicate_openalex_id": candidate["openalex_id"],
                    "kept_openalex_id": seen[identity],
                    "doi": candidate["doi"] or "",
                    "title": candidate["title"] or "",
                    "reason": "normalized DOI or title+year+first-author duplicate",
                }
            )
            continue
        seen[identity] = candidate["openalex_id"]
        candidates.append(candidate)

    write_jsonl(candidates_path, candidates)
    write_json(import_candidates_path, {"candidates": [to_import_candidate(item) for item in candidates]})
    write_csv(
        duplicates_path,
        ["duplicate_openalex_id", "kept_openalex_id", "doi", "title", "reason"],
        duplicate_rows,
    )
    run_log = {
        "tool": "openalex_import.py",
        "tool_version": TOOL_VERSION,
        "status": "completed",
        "completed_at": now_iso(),
        "request_signature": request_signature,
        "input": request_identity,
        "api_key_logged": False,
        "calls": calls,
        "reported_cost_usd": round(reported_cost, 6),
        "rate_limit_remaining": last_rate_headers.get("x-ratelimit-remaining"),
        "counts": {
            "retrieved": len(results[: args.max_results]),
            "unique_candidates": len(candidates),
            "within_search_duplicates": len(duplicate_rows),
            "zotero_duplicates": sum(1 for item in candidates if item["duplicate_in_zotero"]),
            "direct_oa_pdf_candidates": sum(1 for item in candidates if item["direct_oa_pdf_url"]),
            "content_api_only_candidates": sum(
                1 for item in candidates if not item["direct_oa_pdf_url"] and item["has_content_pdf"]
            ),
        },
        "outputs": {
            "download_candidates": candidates_path.name,
            "import_candidates": import_candidates_path.name,
            "duplicates": duplicates_path.name,
        },
        "rights_boundary": "OpenAlex discovery/OA metadata does not grant additional rights to PDFs.",
    }
    write_json(run_path, run_log)
    print(json.dumps({"status": "created", "batch_dir": str(batch_dir), **run_log["counts"]}, ensure_ascii=False, indent=2))
    return 0


def validate_remote_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("PDF URL must use http or https")
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        raise ValueError("local/private PDF host rejected")
    try:
        literal = ipaddress.ip_address(hostname)
        if not literal.is_global:
            raise ValueError("local/private PDF IP rejected")
        return
    except ValueError as exc:
        if "rejected" in str(exc):
            raise
    for info in socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise ValueError("PDF host resolved to a non-public IP")


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> urllib.request.Request | None:
        validate_remote_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_filename(candidate: dict[str, Any]) -> str:
    author = str(candidate.get("first_author") or "Unknown").split()[-1]
    year = str(candidate.get("year") or "n.d.")
    title = unicodedata.normalize("NFKC", str(candidate.get("title") or "paper"))
    title = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", " ", title)
    title = " ".join(title.split())[:90].rstrip(" .") or "paper"
    work_id = str(candidate.get("openalex_id") or "OpenAlex")
    return f"{author}_{year}_{title}_{work_id}.pdf"


def download_pdf(url: str, target: Path, *, api_key: str | None, max_bytes: int) -> tuple[str, int]:
    validate_remote_url(url)
    query_url = url
    if api_key:
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query.append(("api_key", api_key))
        query_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment))
    opener = urllib.request.build_opener(SafeRedirectHandler())
    request = urllib.request.Request(query_url, headers={"Accept": "application/pdf", "User-Agent": USER_AGENT})
    temp = target.with_suffix(target.suffix + ".part")
    hasher = hashlib.sha256()
    total = 0
    head = b""
    try:
        with opener.open(request, timeout=60) as response, temp.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"PDF exceeded size limit of {max_bytes} bytes")
                if len(head) < 1024:
                    head = (head + chunk)[:1024]
                hasher.update(chunk)
                handle.write(chunk)
        if b"%PDF-" not in head:
            raise ValueError("response is not a PDF (missing %PDF signature; possible HTML/login page)")
        temp.replace(target)
        return hasher.hexdigest(), total
    except Exception:
        if temp.exists():
            temp.unlink()
        raise


def download_command(args: argparse.Namespace) -> int:
    candidates_path = Path(args.candidates).resolve()
    pdf_dir = Path(args.pdf_dir).resolve()
    if args.vault_root:
        vault_root = Path(args.vault_root).resolve()
        try:
            pdf_dir.relative_to(vault_root)
        except ValueError:
            pass
        else:
            raise ValueError("PDF directory must be outside the Obsidian vault")
    pdf_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = candidates_path.parent / "openalex_pdf_manifest.csv"
    if manifest_path.exists() and not args.resume:
        raise FileExistsError(f"manifest exists; use --resume or a new batch: {manifest_path}")

    api_key = None
    if args.direct_or_content:
        if not args.accept_openalex_content_cost:
            raise ValueError("OpenAlex content fallback costs $0.01/PDF; pass --accept-openalex-content-cost explicitly")
        api_key = get_api_key()

    fields = [
        "openalex_id", "doi", "title", "license", "version", "pdf_source", "source_url", "pdf_filename",
        "sha256", "bytes", "status", "reason", "zotero_item_key", "downloaded_at", "rights_note",
    ]
    existing: list[dict[str, str]] = []
    completed_ids: set[str] = set()
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            existing = list(csv.DictReader(handle))
        completed_ids = {row.get("openalex_id", "") for row in existing if row.get("status") in {"downloaded", "existing"}}

    rows = list(existing)
    downloaded = 0
    failed = 0
    skipped = 0
    all_candidates = read_jsonl(candidates_path)
    selected_ids = {str(value).strip() for value in args.openalex_id if str(value).strip()}
    available_ids = {str(candidate.get("openalex_id") or "") for candidate in all_candidates}
    unknown_ids = sorted(selected_ids - available_ids)
    if unknown_ids:
        raise ValueError(f"selected OpenAlex IDs not found in candidate file: {unknown_ids}")

    for candidate in all_candidates:
        if str(candidate.get("openalex_id") or "") not in selected_ids:
            continue
        if downloaded >= args.max_files:
            break
        work_id = str(candidate.get("openalex_id") or "")
        if not work_id or work_id in completed_ids:
            continue
        reason = ""
        status = ""
        pdf_source = ""
        source_url = ""
        filename = ""
        digest = ""
        size = 0
        if candidate.get("zotero_check_status") != "checked" and not args.allow_unchecked:
            status, reason = "skipped", "Zotero duplicate check not completed"
        elif candidate.get("duplicate_in_zotero") and not args.include_zotero_duplicates:
            status, reason = "skipped", "duplicate already exists in Zotero"
        else:
            direct_url = str(candidate.get("direct_oa_pdf_url") or "")
            if direct_url:
                source_url = direct_url
                pdf_source = "best_or_ranked_oa_location"
            elif args.direct_or_content and candidate.get("has_content_pdf"):
                source_url = f"{OPENALEX_CONTENT}/works/{urllib.parse.quote(work_id)}.pdf"
                pdf_source = "openalex_content_api_costed"
            else:
                status, reason = "skipped", "no direct OA PDF URL; costed content fallback disabled or unavailable"

        if not status:
            filename = safe_filename(candidate)
            target = pdf_dir / filename
            try:
                if target.exists():
                    with target.open("rb") as handle:
                        head = handle.read(1024)
                    if b"%PDF-" not in head:
                        raise ValueError("existing target is not a valid PDF")
                    hasher = hashlib.sha256()
                    with target.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            hasher.update(chunk)
                    digest, size, status = hasher.hexdigest(), target.stat().st_size, "existing"
                else:
                    digest, size = download_pdf(
                        source_url,
                        target,
                        api_key=api_key if pdf_source == "openalex_content_api_costed" else None,
                        max_bytes=args.max_mb * 1024 * 1024,
                    )
                    status = "downloaded"
                downloaded += 1
            except Exception as exc:
                status, reason = "failed", redact_secret(str(exc), api_key)
                failed += 1
        if status == "skipped":
            skipped += 1
        rows.append(
            {
                "openalex_id": work_id,
                "doi": candidate.get("doi") or "",
                "title": candidate.get("title") or "",
                "license": candidate.get("license") or "",
                "version": candidate.get("version") or "",
                "pdf_source": pdf_source,
                "source_url": source_url,
                "pdf_filename": filename,
                "sha256": digest,
                "bytes": size or "",
                "status": status,
                "reason": reason,
                "zotero_item_key": candidate.get("zotero_item_key") or "",
                "downloaded_at": now_iso(),
                "rights_note": "Original copyright/license retained; no redistribution right granted by OpenAlex.",
            }
        )
        write_csv(manifest_path, fields, rows)

    print(
        json.dumps(
            {
                "status": "completed",
                "pdf_dir": str(pdf_dir),
                "manifest": str(manifest_path),
                "downloaded_or_existing": downloaded,
                "failed": failed,
                "skipped": skipped,
                "content_api_cost_authorized": bool(args.direct_or_content),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if failed == 0 else 1


def self_test() -> int:
    assert normalize_doi("https://doi.org/10.1234/ABC ") == "10.1234/abc"
    assert identity_key("10.1/X", "A", 2020, "B") == "doi:10.1/x"
    work = {
        "id": "https://openalex.org/W1",
        "best_oa_location": {
            "is_oa": True,
            "pdf_url": "https://example.org/a.pdf",
            "version": "publishedVersion",
        },
        "locations": [],
    }
    assert direct_oa_location(work)["pdf_url"] == "https://example.org/a.pdf"
    candidate = make_candidate(work, 1, {})
    assert candidate["direct_oa_pdf_url"] == "https://example.org/a.pdf"
    assert candidate["duplicate_in_zotero"] is False
    import_candidate = to_import_candidate(candidate)
    assert import_candidate["authors"] == []
    assert import_candidate["pdf_url"] == "https://example.org/a.pdf"
    assert redact_secret("url?api_key=secret-value", "secret-value") == "url?api_key=[REDACTED]"
    try:
        validate_remote_url("http://127.0.0.1/private.pdf")
    except ValueError:
        pass
    else:
        raise AssertionError("private PDF hosts must be rejected")
    print(json.dumps({"status": "PASS", "tool_version": TOOL_VERSION}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search OpenAlex and create a deduplicated candidate batch")
    search.add_argument("--query", required=True)
    search.add_argument("--batch-dir", required=True)
    search.add_argument("--max-results", type=int, default=50, choices=range(1, 1001), metavar="1..1000")
    search.add_argument("--year-from", type=int)
    search.add_argument("--year-to", type=int)
    search.add_argument("--work-type", default="article", choices=["article", "preprint", "book-chapter", "dissertation", "any"])
    search.add_argument("--oa-only", action="store_true")
    search.add_argument("--has-content", action="store_true")
    search.add_argument("--sort", default="relevance_score:desc", choices=["relevance_score:desc", "cited_by_count:desc", "publication_date:desc"])
    search.add_argument("--filter", action="append", default=[], help="Additional official OpenAlex work filter")
    search.add_argument("--zotero-check", action="store_true", help="Read local Zotero top-level items and flag duplicates")
    search.add_argument("--zotero-base-url", default=DEFAULT_ZOTERO_API)

    download = subparsers.add_parser("download", help="Download verified direct OA PDFs to a staging directory outside Obsidian")
    download.add_argument("--candidates", required=True)
    download.add_argument("--pdf-dir", required=True)
    download.add_argument(
        "--openalex-id",
        action="append",
        required=True,
        help="Approved OpenAlex work ID; repeat for each item selected from the dry-run manifest",
    )
    download.add_argument("--vault-root")
    download.add_argument("--max-files", type=int, default=10, choices=range(1, 101), metavar="1..100")
    download.add_argument("--max-mb", type=int, default=100, choices=range(1, 501), metavar="1..500")
    download.add_argument("--resume", action="store_true")
    download.add_argument("--allow-unchecked", action="store_true")
    download.add_argument("--include-zotero-duplicates", action="store_true")
    download.add_argument("--direct-or-content", action="store_true", help="Allow paid OpenAlex content API fallback")
    download.add_argument("--accept-openalex-content-cost", action="store_true")

    subparsers.add_parser("self-test", help="Run offline normalization and OA-location tests")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "search":
            if args.year_from and args.year_to and args.year_from > args.year_to:
                raise ValueError("year-from cannot exceed year-to")
            return search_command(args)
        if args.command == "download":
            return download_command(args)
        if args.command == "self-test":
            return self_test()
        parser.error("unknown command")
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
