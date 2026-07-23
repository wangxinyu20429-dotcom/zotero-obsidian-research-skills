#!/usr/bin/env python3
"""Audit MinerU full-text coverage for an existing Zotero profile batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def read_jsonl(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def item_key(item: dict) -> str:
    direct = item.get("zotero_item_key") or item.get("item_key")
    if direct:
        return str(direct).upper()
    for source in item.get("provenance") or []:
        locator = str(source.get("locator") or "")
        match = re.search(r"zotero://select/library/items/([A-Z0-9]+)", locator, re.I)
        if match:
            return match.group(1).upper()
    match = re.search(r"Zotero item key\s*=\s*([A-Z0-9]+)", str(item.get("notes") or ""), re.I)
    return match.group(1).upper() if match else ""


def cache_index(cache_root: Path) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    if not cache_root.is_dir():
        return index
    for folder in cache_root.iterdir():
        if not folder.is_dir() or not folder.name.isdigit():
            continue
        source = read_json(folder / "_llm_source.json")
        parent = str(source.get("parentItemKey") or "").upper()
        markdown = folder / "full.md"
        if not markdown.is_file():
            markdown = folder / "_content.md"
        if not parent or not markdown.is_file():
            continue
        manifest = folder / "manifest.json"
        index.setdefault(parent, []).append(
            {
                "cache_id": folder.name,
                "attachment_key": source.get("attachmentKey"),
                "source_filename": source.get("sourceFilename"),
                "full_md_path": str(markdown.resolve()),
                "manifest_path": str(manifest.resolve()) if manifest.is_file() else None,
                "bytes": markdown.stat().st_size,
            }
        )
    return index


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def coverage(markdown: str) -> dict:
    headings = re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", markdown)
    lower = markdown.casefold()
    groups = {
        "introduction": ["introduction", "background"],
        "data": ["data", "study area", "materials"],
        "methods": ["method", "model", "methodology"],
        "results": ["result", "performance", "evaluation"],
        "discussion": ["discussion", "limitation"],
        "conclusion": ["conclusion", "summary"],
        "availability": ["data availability", "code availability", "author contributions"],
        "references": ["references", "bibliography"],
    }
    present = {name: any(term in lower for term in terms) for name, terms in groups.items()}
    return {
        "characters": len(markdown),
        "headings": headings[:120],
        "heading_count": len(headings),
        "coverage": present,
        "replacement_character": "�" in markdown,
    }


def article_link(item: dict) -> str:
    title = str(item.get("title") or "未命名文献").replace("|", "\\|")
    url = item.get("url") or (f"https://doi.org/{item['doi']}" if item.get("doi") else "")
    return f"[{title}]({url})" if url else title


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-root", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument(
        "--cache-root",
        required=True,
        help="Path to the user-controlled llm-for-zotero/MinerU cache root.",
    )
    args = parser.parse_args()

    root = Path(args.vault_root).resolve()
    profile_paths = sorted((root / "10_文献知识/profiles").glob(f"{args.batch_id}*_paper_profiles.jsonl"))
    profiles = read_jsonl(profile_paths)
    caches = cache_index(Path(args.cache_root))
    rows: list[dict] = []
    for item in profiles:
        key = item_key(item)
        sources = caches.get(key, [])
        status = "missing"
        selected = None
        audit = {}
        if len(sources) == 1:
            selected = sources[0]
            text = Path(selected["full_md_path"]).read_text(encoding="utf-8", errors="replace")
            audit = coverage(text)
            status = "ready" if audit["characters"] >= 10000 and not audit["replacement_character"] else "check_required"
        elif len(sources) > 1:
            hashes = {sha256(Path(source["full_md_path"])) for source in sources}
            if len(hashes) == 1:
                selected = sorted(sources, key=lambda source: source["cache_id"])[-1]
                text = Path(selected["full_md_path"]).read_text(encoding="utf-8", errors="replace")
                audit = coverage(text)
                audit["identical_duplicate_sources"] = len(sources)
                status = "ready" if audit["characters"] >= 10000 and not audit["replacement_character"] else "check_required"
            else:
                status = "ambiguous"
        rows.append(
            {
                "paper_id": item.get("paper_id"),
                "title": item.get("title"),
                "doi": item.get("doi"),
                "url": item.get("url"),
                "zotero_item_key": key or None,
                "status": status,
                "source_count": len(sources),
                "source": selected,
                "audit": audit,
            }
        )

    evidence = root / "10_文献知识/evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    jsonl_path = evidence / f"{args.batch_id}_全文覆盖审计.jsonl"
    jsonl_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    markdown_path = evidence / f"{args.batch_id}_全文覆盖审计.md"
    counts = {name: sum(1 for row in rows if row["status"] == name) for name in ("ready", "check_required", "missing", "ambiguous")}
    lines = [
        "---",
        'title: "机器学习水文预报全文覆盖审计"',
        'review_level: "auto_extracted"',
        "---",
        "",
        "# 机器学习水文预报全文覆盖审计",
        "",
        "> 本表只证明MinerU全文是否可读，不等于已经完成人工精读。正式轻量画像必须在通读全文后另行生成。",
        "",
        f"- 总数：{len(rows)}",
        f"- 可进入全文画像：{counts['ready']}",
        f"- 需检查：{counts['check_required']}",
        f"- 缺失：{counts['missing']}",
        f"- 多来源待消歧：{counts['ambiguous']}",
        "",
        "| 文献 | 状态 | 全文字符数 | 标题数 | 章节覆盖 |",
        "|---|---|---:|---:|---|",
    ]
    for row, item in zip(rows, profiles):
        audit = row.get("audit") or {}
        cover = audit.get("coverage") or {}
        labels = "、".join(name for name, present in cover.items() if present) or "—"
        lines.append(f"| {article_link(item)} | {row['status']} | {audit.get('characters', 0)} | {audit.get('heading_count', 0)} | {labels} |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "created", "total": len(rows), "counts": counts, "jsonl": str(jsonl_path), "markdown": str(markdown_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
