#!/usr/bin/env python3
"""Resolve an Idea target and inventory relevant Obsidian evidence (stdlib only)."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PRIORITY_ROOTS = ("文献", "数据", "项目", "任务", "论文产出")
TEXT_SUFFIXES = {".md", ".txt", ".yaml", ".yml", ".json", ".csv", ".tsv", ".py", ".ps1", ".r", ".m"}
EXCLUDED_DIRS = {".git", ".obsidian", ".trash", "node_modules", "__pycache__"}
FLOOD_LIMIT_ALIASES = ("汛限水位", "动态汛限水位", "flood limit water level", "flood-control water level")


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(ch for ch in text if ch.isalnum())


def safe_topic(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"(?:研究|问题|分析|论文|idea)$", "", text, flags=re.I)
    if not text:
        raise ValueError("Topic becomes empty after filesystem sanitization")
    return text[:60]


def vault_root(path: str) -> Path:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Vault root does not exist: {root}")
    if not (root / ".obsidian").exists():
        raise ValueError(f"Not an Obsidian vault (missing .obsidian): {root}")
    return root


def inside(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Resolved path escapes the vault: {resolved}") from exc
    return resolved


def rel_string(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def resolve_target(root: Path, topic: str, target_relative: str | None = None) -> dict[str, Any]:
    if target_relative:
        parts = [part for part in re.split(r"[\\/]+", target_relative) if part]
        relative = Path(*parts)
        target = inside(root, root / relative)
        return {"status": "resolved", "matched_by": "explicit_target", "target": target}

    normalized_topic = normalize(topic)
    if any(normalize(alias) in normalized_topic or normalized_topic in normalize(alias) for alias in FLOOD_LIMIT_ALIASES):
        target = inside(root, root / "任务" / "汛限水位动态控制试点" / "03_选题管理")
        return {"status": "resolved", "matched_by": "flood_limit_alias", "target": target}

    task_root = root / "任务"
    matches: list[tuple[int, Path]] = []
    if task_root.is_dir():
        for project in task_root.iterdir():
            if not project.is_dir():
                continue
            project_norm = normalize(project.name.replace("试点", ""))
            if not project_norm:
                continue
            score = 0
            if normalized_topic == project_norm:
                score = 100
            elif normalized_topic in project_norm or project_norm in normalized_topic:
                score = 80
            else:
                topic_chars, project_chars = set(normalized_topic), set(project_norm)
                if topic_chars and project_chars:
                    score = round(50 * len(topic_chars & project_chars) / len(topic_chars | project_chars))
            if score >= 35:
                matches.append((score, project))
    matches.sort(key=lambda item: (-item[0], item[1].name))
    if matches:
        top_score = matches[0][0]
        top = [path for score, path in matches if score == top_score]
        if len(top) > 1:
            return {"status": "ambiguous", "matched_by": "task_project_similarity",
                    "candidates": [inside(root, path / "03_选题管理") for path in top]}
        return {"status": "resolved", "matched_by": "existing_task_project",
                "target": inside(root, top[0] / "03_选题管理")}

    proposed = inside(root, root / "任务" / f"{safe_topic(topic)}试点" / "03_选题管理")
    return {"status": "resolved", "matched_by": "new_task_project_proposal", "target": proposed}


def command_resolve(args: argparse.Namespace) -> dict[str, Any]:
    root = vault_root(args.vault_root)
    result = resolve_target(root, args.topic, args.target_relative)
    if result["status"] == "ambiguous":
        return {"ok": False, "status": "ambiguous", "matched_by": result["matched_by"],
                "candidates": [{"relative": rel_string(root, path), "absolute": str(path)} for path in result["candidates"]]}
    target: Path = result["target"]
    existed_before = target.is_dir()
    if args.create:
        target.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "status": "resolved", "matched_by": result["matched_by"],
            "vault_root": str(root), "target_relative": rel_string(root, target),
            "target_absolute": str(target), "existed_before": existed_before,
            "created": bool(args.create and not existed_before), "dry_run": not args.create}


def read_prefix(path: Path, limit: int) -> str:
    if path.suffix.casefold() not in TEXT_SUFFIXES:
        return ""
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as stream:
            return stream.read(limit)
    except OSError:
        return ""


def first_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()[:200]
        if re.match(r"^(?:title|题目|名称)\s*:", stripped, flags=re.I):
            return stripped.split(":", 1)[-1].strip()[:200]
    return ""


def iter_files(root: Path):
    for priority in PRIORITY_ROOTS:
        base = root / priority
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            yield priority, path


def command_inventory(args: argparse.Namespace) -> dict[str, Any]:
    root = vault_root(args.vault_root)
    if args.limit < 1 or args.content_chars < 1:
        raise ValueError("--limit and --content-chars must be positive")
    raw_keywords = [value.strip() for value in (args.keyword or []) if value.strip()]
    if not raw_keywords:
        raise ValueError("Provide at least one --keyword")
    keywords = [(raw, normalize(raw)) for raw in raw_keywords if normalize(raw)]
    rows: list[dict[str, Any]] = []
    category_weight = {"文献": 10, "数据": 8, "项目": 8, "任务": 9, "论文产出": 5}

    for category, path in iter_files(root):
        relative = rel_string(root, path)
        path_norm = normalize(relative)
        prefix = read_prefix(path, args.content_chars)
        content_norm = normalize(prefix)
        path_hits = [raw for raw, norm in keywords if norm in path_norm]
        content_hits = [raw for raw, norm in keywords if norm in content_norm]
        matched = list(dict.fromkeys(path_hits + content_hits))
        if not matched:
            continue
        score = category_weight[category] + 10 * len(path_hits) + 4 * len(content_hits)
        reasons = []
        if "文献问题簇" in relative:
            score += 18
            reasons.append("literature_problem_cluster")
        if "03_选题管理" in relative:
            score += 12
            reasons.append("existing_idea_or_decision")
        if "04_最小验证" in relative:
            score += 10
            reasons.append("minimum_validation")
        if category == "数据":
            reasons.append("data_evidence")
        elif category == "项目":
            reasons.append("project_evidence")
        elif category == "任务":
            reasons.append("task_or_decision_evidence")
        elif category == "文献":
            reasons.append("literature_evidence")
        stat = path.stat()
        rows.append({"relative_path": relative, "category": category, "title": first_title(prefix),
                     "suffix": path.suffix.casefold(), "size": stat.st_size,
                     "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).astimezone().isoformat(timespec="seconds"),
                     "matched_keywords": matched, "score": score, "reasons": reasons})

    rows.sort(key=lambda row: (-row["score"], row["relative_path"].casefold()))
    rows = rows[: args.limit]
    return {"ok": True, "read_only": True, "vault_root": str(root), "keywords": raw_keywords,
            "counts": {"returned": len(rows), "by_category": dict(Counter(row["category"] for row in rows))},
            "items": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve-target", help="Resolve or safely create a 03_选题管理 target")
    resolve.add_argument("--vault-root", required=True)
    resolve.add_argument("--topic", required=True)
    resolve.add_argument("--target-relative")
    resolve.add_argument("--create", action="store_true")

    inventory = sub.add_parser("inventory", help="List relevant evidence candidates without modifying files")
    inventory.add_argument("--vault-root", required=True)
    inventory.add_argument("--keyword", action="append")
    inventory.add_argument("--limit", type=int, default=300)
    inventory.add_argument("--content-chars", type=int, default=65536)

    args = parser.parse_args()
    try:
        result = command_resolve(args) if args.command == "resolve-target" else command_inventory(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 3
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
