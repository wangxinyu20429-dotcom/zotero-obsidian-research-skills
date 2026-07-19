#!/usr/bin/env python3
"""Read-only resolver for Zotero items and llm-for-zotero MinerU Markdown caches."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


BASE_URL = os.environ.get("ZOTERO_LOCAL_API", "http://127.0.0.1:23119").rstrip("/")
LOCAL_USER = "/api/users/0"
API_LIMIT = 100
CACHE_DIR_NAME = "llm-for-zotero-mineru"
SYNC_TITLE_PREFIX = "[LLM for Zotero] MinerU cache"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


class ResolverError(RuntimeError):
    def __init__(self, message: str, *, code: str = "error", details: Any = None):
        super().__init__(message)
        self.code = code
        self.details = details


def emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def fail(exc: ResolverError) -> None:
    payload = {"status": exc.code, "message": str(exc)}
    if exc.details is not None:
        payload["details"] = exc.details
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    raise SystemExit(2)


def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
    url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Zotero-API-Version": "3"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ResolverError(
            f"Cannot reach Zotero local API at {BASE_URL}: {exc}",
            code="zotero_api_unavailable",
        ) from exc
    try:
        return json.loads(body) if body.strip() else None
    except json.JSONDecodeError as exc:
        raise ResolverError(f"Zotero returned invalid JSON for {path}", code="invalid_api_json") from exc


def api_ping() -> int:
    request = urllib.request.Request(f"{BASE_URL}/api/", headers={"Zotero-API-Version": "3"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read(1)
            return int(response.status)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ResolverError(
            f"Cannot reach Zotero local API at {BASE_URL}: {exc}",
            code="zotero_api_unavailable",
        ) from exc


def profile_candidates() -> list[Path]:
    home = Path.home()
    roots: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        roots.append(Path(appdata) / "Zotero" / "Zotero" / "Profiles")
    roots.extend(
        [
            home / "Library" / "Application Support" / "Zotero" / "Profiles",
            home / ".zotero" / "zotero",
        ]
    )
    profiles: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        profiles.extend(path for path in root.iterdir() if path.is_dir() and (path / "prefs.js").is_file())
    return sorted(profiles, key=lambda path: (path / "prefs.js").stat().st_mtime, reverse=True)


def parse_data_dir_from_prefs(prefs_path: Path) -> Path | None:
    text = prefs_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r'user_pref\("extensions\.zotero\.dataDir",\s*("(?:\\.|[^"\\])*")\s*\);',
        text,
    )
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return Path(value).expanduser() if value else None


def resolve_data_dir() -> tuple[Path, Path | None]:
    for profile in profile_candidates():
        custom = parse_data_dir_from_prefs(profile / "prefs.js")
        if custom and custom.exists():
            return custom.resolve(), profile.resolve()
    defaults = [Path.home() / "Zotero"]
    for candidate in defaults:
        if (candidate / "zotero.sqlite").exists():
            return candidate.resolve(), None
    raise ResolverError("Cannot resolve the Zotero data directory", code="zotero_data_dir_missing")


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()


def normalize_doi(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text)
    return text.rstrip(" .")


def creator_names(data: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for creator in data.get("creators") or []:
        name = creator.get("name") or " ".join(
            part for part in (creator.get("firstName"), creator.get("lastName")) if part
        )
        marker = normalize_text(name)
        if name and marker not in seen:
            names.append(name)
            seen.add(marker)
    return names


def year_of(data: dict[str, Any]) -> str | None:
    match = re.search(r"\b(?:19|20)\d{2}\b", str(data.get("date") or ""))
    return match.group(0) if match else None


def citekey_of(data: dict[str, Any]) -> str | None:
    direct = data.get("citationKey")
    if direct:
        return str(direct)
    match = re.search(r"(?im)^Citation Key:\s*(\S+)\s*$", str(data.get("extra") or ""))
    return match.group(1) if match else None


def item_summary(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data", item)
    return {
        "key": item.get("key") or data.get("key"),
        "itemType": data.get("itemType"),
        "title": data.get("title"),
        "creators": creator_names(data),
        "year": year_of(data),
        "date": data.get("date"),
        "DOI": data.get("DOI"),
        "publicationTitle": data.get("publicationTitle"),
        "volume": data.get("volume"),
        "issue": data.get("issue"),
        "pages": data.get("pages"),
        "url": data.get("url"),
        "citekey": citekey_of(data),
    }


def filters_match(item: dict[str, Any], *, author: str | None, year: str | None, doi: str | None) -> bool:
    data = item.get("data", item)
    if author:
        needle = normalize_text(author)
        if not any(needle in normalize_text(name) for name in creator_names(data)):
            return False
    if year and year_of(data) != str(year):
        return False
    if doi and normalize_doi(data.get("DOI")) != normalize_doi(doi):
        return False
    return True


def get_top_item(item_key: str) -> dict[str, Any]:
    item = api_get(f"{LOCAL_USER}/items/{urllib.parse.quote(item_key.strip())}")
    if not isinstance(item, dict):
        raise ResolverError(f"Zotero item not found: {item_key}", code="item_not_found")
    parent = (item.get("data") or {}).get("parentItem")
    if parent:
        item = api_get(f"{LOCAL_USER}/items/{urllib.parse.quote(str(parent))}")
    return item


def search_items(query: str | None, author: str | None, year: str | None, doi: str | None) -> list[dict[str, Any]]:
    q = query or doi or author
    if not q:
        raise ResolverError("Provide at least one of --query, --author, or --doi", code="missing_identifier")
    items = api_get(
        f"{LOCAL_USER}/items/top",
        {"q": q, "qmode": "everything", "limit": API_LIMIT},
    )
    if not isinstance(items, list):
        return []
    return [item for item in items if filters_match(item, author=author, year=year, doi=doi)]


def resolve_item(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "item_key", None):
        item = get_top_item(args.item_key)
        if not filters_match(item, author=args.author, year=args.year, doi=args.doi):
            raise ResolverError(
                "The supplied author/year/DOI conflicts with the resolved Zotero item key",
                code="identifier_conflict",
                details=item_summary(item),
            )
        return item
    matches = search_items(args.query, args.author, args.year, args.doi)
    if not matches:
        raise ResolverError("No Zotero item matched the supplied identifiers", code="no_match")
    if len(matches) != 1:
        raise ResolverError(
            "Multiple Zotero items matched; select an exact item key",
            code="ambiguous_item",
            details=[item_summary(item) for item in matches],
        )
    return matches[0]


def child_items(item_key: str) -> list[dict[str, Any]]:
    rows = api_get(
        f"{LOCAL_USER}/items/{urllib.parse.quote(item_key)}/children",
        {"limit": API_LIMIT},
    )
    return rows if isinstance(rows, list) else []


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def local_cache_sources(data_dir: Path, parent_key: str) -> list[dict[str, Any]]:
    root = data_dir / CACHE_DIR_NAME
    if not root.is_dir():
        return []
    sources: list[dict[str, Any]] = []
    for directory in root.iterdir():
        if not directory.is_dir() or not directory.name.isdigit():
            continue
        provenance = read_json(directory / "_llm_source.json") or {}
        if str(provenance.get("parentItemKey") or "").upper() != parent_key.upper():
            continue
        markdown = directory / "full.md"
        if not markdown.is_file():
            markdown = directory / "_content.md"
        if not markdown.is_file():
            continue
        sources.append(
            {
                "kind": "local_cache",
                "cache_id": directory.name,
                "attachment_key": provenance.get("attachmentKey"),
                "parent_item_key": provenance.get("parentItemKey"),
                "source_filename": provenance.get("sourceFilename"),
                "source_dir": str(directory.resolve()),
                "full_md_path": str(markdown.resolve()),
                "manifest_path": str((directory / "manifest.json").resolve())
                if (directory / "manifest.json").is_file()
                else None,
                "bytes": markdown.stat().st_size,
            }
        )
    return sources


def attachment_path(data_dir: Path, child: dict[str, Any]) -> Path | None:
    data = child.get("data") or {}
    raw = str(data.get("path") or "")
    key = str(child.get("key") or data.get("key") or "")
    if raw.startswith("storage:") and key:
        return data_dir / "storage" / key / raw.split(":", 1)[1]
    if raw and not raw.startswith(("attachments:", "http:", "https:")):
        candidate = Path(raw).expanduser()
        return candidate if candidate.is_absolute() else None
    filename = data.get("filename")
    if key and filename:
        return data_dir / "storage" / key / str(filename)
    return None


def zip_member_name(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
    except (OSError, zipfile.BadZipFile):
        return None
    exact = [name for name in names if PurePosixPath(name).name.casefold() == "full.md"]
    markdown = [name for name in names if PurePosixPath(name).suffix.casefold() == ".md"]
    return (exact or markdown or [None])[0]


def zip_sync_metadata(path: Path) -> dict[str, Any] | None:
    try:
        with zipfile.ZipFile(path) as archive:
            member = next(
                (
                    name
                    for name in archive.namelist()
                    if PurePosixPath(name).name.casefold() == "_llm_sync.json"
                ),
                None,
            )
            if not member:
                return None
            value = json.loads(archive.read(member).decode("utf-8", errors="replace"))
            return value if isinstance(value, dict) else None
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError):
        return None


def synced_zip_sources(data_dir: Path, parent_key: str, children: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for child in children:
        data = child.get("data") or {}
        title = str(data.get("title") or data.get("filename") or "")
        content_type = str(data.get("contentType") or "").casefold()
        if not (title.startswith(SYNC_TITLE_PREFIX) or "zip" in content_type):
            continue
        path = attachment_path(data_dir, child)
        if not path or not path.is_file() or path.suffix.casefold() != ".zip":
            continue
        member = zip_member_name(path)
        if not member:
            continue
        sync_metadata = zip_sync_metadata(path) or {}
        package_attachment_key = child.get("key") or data.get("key")
        sources.append(
            {
                "kind": "synced_zip",
                "attachment_key": sync_metadata.get("sourceAttachmentKey")
                or package_attachment_key,
                "package_attachment_key": package_attachment_key,
                "parent_item_key": parent_key,
                "title": title,
                "zip_path": str(path.resolve()),
                "full_md_member": member,
                "bytes": path.stat().st_size,
            }
        )
    return sources


def all_sources(data_dir: Path, item_key: str, children: list[dict[str, Any]]) -> list[dict[str, Any]]:
    local = local_cache_sources(data_dir, item_key)
    synced = synced_zip_sources(data_dir, item_key, children)
    local_attachment_keys = {str(row.get("attachment_key") or "").upper() for row in local}
    deduped_synced = [
        row
        for row in synced
        if not row.get("attachment_key")
        or str(row.get("attachment_key")).upper() not in local_attachment_keys
    ]
    return local + deduped_synced


def source_summary(source: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in source.items() if key not in {"markdown"}}


def choose_source(sources: list[dict[str, Any]], attachment_key: str | None) -> dict[str, Any]:
    if attachment_key:
        sources = [
            source
            for source in sources
            if str(source.get("attachment_key") or "").upper() == attachment_key.upper()
        ]
    if not sources:
        raise ResolverError(
            "No llm-for-zotero MinerU Markdown source matched this paper",
            code="mineru_markdown_missing",
        )
    if len(sources) != 1:
        raise ResolverError(
            "Multiple parsed Markdown sources matched; select --attachment-key",
            code="ambiguous_attachment",
            details=[source_summary(source) for source in sources],
        )
    return sources[0]


def safe_extract_zip(zip_path: Path, output_dir: Path) -> tuple[Path, Path | None]:
    allowed = {".md", ".json", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
    total = 0
    markdown_paths: list[Path] = []
    manifest_path: Path | None = None
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            parts = PurePosixPath(info.filename).parts
            if info.is_dir() or not parts or any(part in {"", ".", ".."} for part in parts):
                continue
            if PurePosixPath(info.filename).suffix.casefold() not in allowed:
                continue
            total += info.file_size
            if total > 512 * 1024 * 1024:
                raise ResolverError("MinerU ZIP exceeds the 512 MB safe extraction limit", code="zip_too_large")
            destination = output_dir.joinpath(*parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            if destination.name.casefold() == "full.md":
                markdown_paths.insert(0, destination)
            elif destination.suffix.casefold() == ".md":
                markdown_paths.append(destination)
            if destination.name.casefold() == "manifest.json":
                manifest_path = destination
    if not markdown_paths:
        raise ResolverError("MinerU ZIP contains no Markdown file", code="zip_markdown_missing")
    return markdown_paths[0], manifest_path


def materialize(source: dict[str, Any], output_dir: Path) -> tuple[Path, Path | None, str | None]:
    if source["kind"] == "local_cache":
        markdown_source = Path(source["full_md_path"])
        markdown_target = output_dir / "full.md"
        shutil.copy2(markdown_source, markdown_target)
        manifest_target: Path | None = None
        if source.get("manifest_path"):
            manifest_source = Path(source["manifest_path"])
            if manifest_source.is_file():
                manifest_target = output_dir / "manifest.json"
                shutil.copy2(manifest_source, manifest_target)
        return markdown_target, manifest_target, source.get("source_dir")
    extracted_dir = output_dir / "package"
    extracted_dir.mkdir()
    markdown, manifest = safe_extract_zip(Path(source["zip_path"]), extracted_dir)
    return markdown, manifest, str(extracted_dir.resolve())


def cmd_status(_: argparse.Namespace) -> None:
    api_status = api_ping()
    data_dir, profile = resolve_data_dir()
    cache_root = data_dir / CACHE_DIR_NAME
    count = 0
    if cache_root.is_dir():
        count = sum(1 for path in cache_root.iterdir() if path.is_dir() and (path / "full.md").is_file())
    emit(
        {
            "status": "ready",
            "api_status": api_status,
            "base_url": BASE_URL,
            "data_dir": str(data_dir),
            "profile": str(profile) if profile else None,
            "mineru_cache_dir": str(cache_root),
            "full_md_cache_count": count,
            "read_only": True,
        }
    )


def cmd_search(args: argparse.Namespace) -> None:
    matches = search_items(args.query, args.author, args.year, args.doi)
    emit({"status": "ok", "count": len(matches), "items": [item_summary(item) for item in matches]})


def cmd_inspect(args: argparse.Namespace) -> None:
    item = get_top_item(args.item_key)
    summary = item_summary(item)
    item_key = str(summary["key"])
    children = child_items(item_key)
    data_dir, _ = resolve_data_dir()
    sources = all_sources(data_dir, item_key, children)
    attachments = []
    for child in children:
        data = child.get("data") or {}
        if data.get("itemType") == "attachment":
            attachments.append(
                {
                    "key": child.get("key") or data.get("key"),
                    "title": data.get("title"),
                    "filename": data.get("filename"),
                    "contentType": data.get("contentType"),
                    "linkMode": data.get("linkMode"),
                }
            )
    emit(
        {
            "status": "ok",
            "item": summary,
            "attachments": attachments,
            "mineru_sources": [source_summary(source) for source in sources],
        }
    )


def cmd_extract(args: argparse.Namespace) -> None:
    item = resolve_item(args)
    summary = item_summary(item)
    item_key = str(summary["key"])
    children = child_items(item_key)
    data_dir, _ = resolve_data_dir()
    source = choose_source(all_sources(data_dir, item_key, children), args.attachment_key)

    base = Path(args.out_dir).expanduser().resolve() if args.out_dir else Path(tempfile.mkdtemp(prefix="zotero-hydrology-notes-"))
    base.mkdir(parents=True, exist_ok=True)
    source_id = str(source.get("attachment_key") or source.get("cache_id") or "source")
    bundle_dir = base / f"{item_key}-{source_id}"
    try:
        bundle_dir.mkdir(parents=False, exist_ok=False)
    except FileExistsError as exc:
        raise ResolverError(f"Extraction bundle already exists: {bundle_dir}", code="output_exists") from exc

    markdown_path, manifest_path, original_source_dir = materialize(source, bundle_dir)
    descriptor = {
        "status": "ok",
        "read_only_source": True,
        "item": summary,
        "source": source_summary(source),
        "bundle_dir": str(bundle_dir.resolve()),
        "full_md_path": str(markdown_path.resolve()),
        "manifest_path": str(manifest_path.resolve()) if manifest_path else None,
        "original_source_dir": original_source_dir,
        "zotero_url": f"zotero://select/library/items/{item_key}",
    }
    metadata_path = bundle_dir / "metadata.json"
    metadata_path.write_text(json.dumps(descriptor, ensure_ascii=False, indent=2), encoding="utf-8")
    descriptor["metadata_path"] = str(metadata_path.resolve())
    emit(descriptor)


def add_lookup_arguments(parser: argparse.ArgumentParser, *, item_key: bool) -> None:
    if item_key:
        parser.add_argument("--item-key")
    parser.add_argument("--query")
    parser.add_argument("--author")
    parser.add_argument("--year")
    parser.add_argument("--doi")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read Zotero and llm-for-zotero MinerU Markdown without modifying Zotero."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="Check local Zotero API and MinerU cache")
    status.set_defaults(func=cmd_status)

    search = commands.add_parser("search", help="Search top-level Zotero items")
    add_lookup_arguments(search, item_key=False)
    search.set_defaults(func=cmd_search)

    inspect = commands.add_parser("inspect", help="List attachments and MinerU sources for an item")
    inspect.add_argument("--item-key", required=True)
    inspect.set_defaults(func=cmd_inspect)

    extract = commands.add_parser("extract", help="Materialize one read-only Markdown bundle")
    add_lookup_arguments(extract, item_key=True)
    extract.add_argument("--attachment-key")
    extract.add_argument("--out-dir")
    extract.set_defaults(func=cmd_extract)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except ResolverError as exc:
        fail(exc)


if __name__ == "__main__":
    main()
