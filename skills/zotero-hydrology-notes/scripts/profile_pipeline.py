#!/usr/bin/env python3
"""Deterministic control-layer helpers for Zotero lightweight-paper profiles.

The script reads Zotero through the local read-only API. It never modifies the
Zotero library and never copies attachments or PDFs into the Obsidian vault.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


TOOL_VERSION = "0.3.0"
ACCESS = {"metadata", "abstract", "partial_text", "fulltext", "project_material", "secondary_web"}
REVIEW = {"auto_extracted", "student_checked", "cross_checked", "mentor_confirmed"}
EVIDENCE = {"metadata_only", "abstract_only", "partial_text", "full_text_main", "full_text_with_supplement"}
REVIEW_STATUS = {"unverified", "self_checked", "cross_checked", "mentor_checked"}
BATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")

TEMPLATES = {
    "paper_profile.schema.json": "paper_profile.schema.json",
    "检索记录模板.csv": "检索记录模板.csv",
    "失败记录模板.csv": "失败记录模板.csv",
    "样本文献清单模板.csv": "样本文献清单模板.csv",
    "质量抽检模板.csv": "质量抽检模板.csv",
    "核心文献选择模板.csv": "核心文献选择模板.csv",
}

SAMPLE_FIELDS = [
    "paper_id", "zotero_item_key", "title", "first_author", "year", "venue",
    "doi", "url", "source_search_id", "batch_id", "duplicate_status",
    "inclusion_status", "inclusion_reason", "access_level", "profile_status",
    "note_link",
]
SEARCH_FIELDS = [
    "search_id", "source", "query", "search_date", "result_count",
    "export_file", "operator", "notes",
]
FAILURE_FIELDS = [
    "failure_id", "stage", "paper_id", "input", "reason", "error_message",
    "action", "status", "owner",
]
QUALITY_FIELDS = [
    "check_id", "paper_id", "checker", "title_ok", "year_ok", "doi_ok",
    "task_ok", "method_ok", "finding_ok", "evidence_level_ok", "issue",
    "severity", "action",
]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    return datetime.now().astimezone().date().isoformat()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    tmp.replace(path)


def write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    atomic_write_text(path, text)


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no} is not a JSON object")
            rows.append(value)
    return rows


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_doi(value: Any) -> str:
    doi = str(value or "").strip().lower()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi)
    return doi.rstrip(" .")


def normalize_title(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def first_author_name(creators: Any) -> str:
    if not isinstance(creators, list) or not creators:
        return ""
    first = creators[0]
    if isinstance(first, str):
        return first.strip()
    if not isinstance(first, dict):
        return ""
    return str(first.get("lastName") or first.get("name") or "").strip()


def author_names(creators: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(creators, list):
        return names
    for creator in creators:
        if isinstance(creator, str):
            name = creator.strip()
        elif isinstance(creator, dict):
            name = " ".join(
                part for part in [str(creator.get("firstName") or "").strip(), str(creator.get("lastName") or "").strip()] if part
            ) or str(creator.get("name") or "").strip()
        else:
            name = ""
        if name:
            names.append(name)
    return names


def parse_year(value: Any) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", str(value or ""))
    return int(match.group(0)) if match else None


def identity_key(*, doi: Any, title: Any, year: Any, first_author: Any) -> str:
    normalized_doi = normalize_doi(doi)
    if normalized_doi:
        return "doi:" + normalized_doi
    return "fallback:" + "|".join(
        [normalize_title(title), str(year or ""), normalize_title(first_author)]
    )


def safe_batch_id(value: str) -> str:
    if not BATCH_ID_RE.fullmatch(value):
        raise ValueError("batch_id must use only letters, digits, dot, underscore, or hyphen")
    return value


def vault_paths(vault_root: Path) -> dict[str, Path]:
    control = vault_root / "10_文献知识"
    return {
        "control": control,
        "batches": control / "sources" / "batches",
        "profiles": control / "profiles",
        "runs": control / "runs",
        "errors": control / "errors",
        "quality": control / "quality",
        "core": control / "core",
        "evidence": control / "evidence",
    }


def init_layout(vault_root: Path) -> dict[str, Any]:
    if not vault_root.exists() or not vault_root.is_dir():
        raise FileNotFoundError(f"vault root does not exist: {vault_root}")
    paths = vault_paths(vault_root)
    for name, path in paths.items():
        if name != "control":
            path.mkdir(parents=True, exist_ok=True)

    references = Path(__file__).resolve().parent.parent / "references"
    created: list[str] = []
    preserved: list[str] = []
    paths["control"].mkdir(parents=True, exist_ok=True)
    for source_name, target_name in TEMPLATES.items():
        source = references / source_name
        target = paths["control"] / target_name
        if target.exists():
            preserved.append(str(target))
            continue
        if not source.exists():
            raise FileNotFoundError(f"bundled template missing: {source}")
        atomic_write_text(target, source.read_text(encoding="utf-8-sig"))
        created.append(str(target))

    return {"created": created, "preserved": preserved, "directories": {k: str(v) for k, v in paths.items()}}


def http_get_json(url: str, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object from {url}")
    return payload


def fetch_zotero_item(base_url: str, item_key: str) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/api/users/0/items/" + urllib.parse.quote(item_key)
    payload = http_get_json(url)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    return {
        "zotero_item_key": str(payload.get("key") or data.get("key") or item_key),
        "item_type": data.get("itemType"),
        "title": str(data.get("title") or "").strip(),
        "authors": author_names(data.get("creators")),
        "first_author": first_author_name(data.get("creators")),
        "year": parse_year(data.get("date")),
        "date": data.get("date"),
        "venue": data.get("publicationTitle") or data.get("conferenceName") or data.get("university") or None,
        "doi": normalize_doi(data.get("DOI")) or None,
        "url": data.get("url") or None,
        "abstract": str(data.get("abstractNote") or "").strip(),
        "retrieved_at": now_iso(),
    }


def collect_existing_identities(vault_root: Path) -> tuple[dict[str, str], set[str]]:
    identities: dict[str, str] = {}
    paper_ids: set[str] = set()
    paths = vault_paths(vault_root)
    for profile_file in sorted(paths["profiles"].glob("*.jsonl")):
        for profile in read_jsonl(profile_file):
            paper_id = str(profile.get("paper_id") or "").strip()
            if not paper_id:
                continue
            key = identity_key(
                doi=profile.get("doi"),
                title=profile.get("title"),
                year=profile.get("year"),
                first_author=(profile.get("authors") or [""])[0],
            )
            identities.setdefault(key, paper_id)
            paper_ids.add(paper_id)
    for batch_file in sorted(paths["batches"].glob("*_样本文献清单.csv")):
        for row in read_csv_rows(batch_file):
            paper_id = str(row.get("paper_id") or "").strip()
            if not paper_id:
                continue
            key = identity_key(
                doi=row.get("doi"), title=row.get("title"), year=row.get("year"), first_author=row.get("first_author")
            )
            identities.setdefault(key, paper_id)
            paper_ids.add(paper_id)
    return identities, paper_ids


def allocate_paper_id(year: int | None, used: set[str]) -> str:
    year_text = str(year) if year else "UNKN"
    prefix = f"P-{year_text}-"
    maximum = 0
    for paper_id in used:
        if paper_id.startswith(prefix):
            try:
                maximum = max(maximum, int(paper_id.rsplit("-", 1)[-1]))
            except ValueError:
                pass
    candidate = f"{prefix}{maximum + 1:04d}"
    used.add(candidate)
    return candidate


def skeleton_profile(item: dict[str, Any], paper_id: str, research_question: str, source_batch_id: str) -> dict[str, Any]:
    has_abstract = bool(item.get("abstract"))
    locator = f"zotero://select/library/items/{item['zotero_item_key']}"
    provenance = [
        {"source_type": "metadata", "locator": locator, "retrieved_at": today_iso()}
    ]
    if has_abstract:
        provenance.append({"source_type": "abstract", "locator": locator + "#abstract", "retrieved_at": today_iso()})
    return {
        "profile_version": "0.2",
        "paper_id": paper_id,
        "canonical_literature_id": paper_id,
        "source_batch_id": source_batch_id,
        "title": item["title"],
        "title_normalized": normalize_title(item["title"]),
        "authors": item["authors"],
        "year": item["year"],
        "venue": item["venue"],
        "doi": item["doi"],
        "doi_normalized": normalize_doi(item["doi"]) or None,
        "url": item["url"],
        "source_path": locator,
        "selection_status": "included",
        "journal_tier": None,
        "access_level": "abstract" if has_abstract else "metadata",
        "review_level": "auto_extracted",
        "evidence_status": "abstract_only" if has_abstract else "metadata_only",
        "review_status": "unverified",
        "knowledge_status": "candidate",
        "research_problem": None,
        "forecast_target": None,
        "forecast_horizon": None,
        "spatial_scale": None,
        "temporal_resolution": None,
        "study_region": None,
        "datasets": [],
        "methods": [],
        "baselines": [],
        "metrics": [],
        "main_findings": [],
        "claimed_innovations": [],
        "limitations": [],
        "candidate_themes": [],
        "provenance": provenance,
        "confidence": 0.35 if has_abstract else 0.15,
        "notes": f"自动骨架；研究问题“{research_question}”仅用于样本筛查和核心评分。本Skill不生成主题地图；candidate_themes保持空数组。需按可用证据完成轻量画像。",
    }


def append_failure(path: Path, row: dict[str, Any]) -> None:
    rows = read_csv_rows(path)
    if not row.get("failure_id"):
        row["failure_id"] = f"F{len(rows) + 1:03d}"
    rows.append({key: str(row.get(key) or "") for key in FAILURE_FIELDS})
    write_csv(path, FAILURE_FIELDS, rows)


def collect_zotero(args: argparse.Namespace) -> int:
    vault_root = Path(args.vault_root).resolve()
    init_layout(vault_root)
    batch_id = safe_batch_id(args.batch_id)
    keys = [key.strip().upper() for key in args.item_keys if key.strip()]
    if not keys:
        raise ValueError("at least one item key is required")
    paths = vault_paths(vault_root)
    prefix = paths["batches"] / batch_id
    search_path = prefix.with_name(prefix.name + "_检索记录.csv")
    sample_path = prefix.with_name(prefix.name + "_样本文献清单.csv")
    source_path = prefix.with_name(prefix.name + "_zotero_sources.jsonl")
    profile_path = paths["profiles"] / f"{batch_id}_paper_profiles.jsonl"
    failure_path = paths["errors"] / f"{batch_id}_失败记录.csv"
    quality_path = paths["quality"] / f"{batch_id}_质量抽检.csv"
    run_path = paths["runs"] / f"{batch_id}_run.json"

    if run_path.exists():
        previous = json.loads(run_path.read_text(encoding="utf-8"))
        previous_input = previous.get("input", {})
        previous_question = previous_input.get("research_question", previous_input.get("seed_topic"))
        same = sorted(previous_input.get("item_keys", [])) == sorted(keys) and previous_question == args.research_question
        if same:
            previous.setdefault("rerun_checks", []).append({"checked_at": now_iso(), "status": "unchanged", "duplicate_outputs": 0})
            write_json(run_path, previous)
            print(json.dumps({"status": "unchanged", "batch_id": batch_id, "duplicate_outputs": 0, "run_log": str(run_path)}, ensure_ascii=False, indent=2))
            return 0
        if not failure_path.exists():
            write_csv(failure_path, FAILURE_FIELDS, [])
        append_failure(
            failure_path,
            {
                "stage": "批次复跑",
                "paper_id": "",
                "input": batch_id,
                "reason": "同名batch_id输入冲突",
                "error_message": "existing item keys or research question differ",
                "action": "使用新batch_id或人工确认",
                "status": "open",
                "owner": args.operator,
            },
        )
        raise ValueError(f"batch_id already exists with different input: {batch_id}")

    identities, used_ids = collect_existing_identities(vault_root)
    batch_seen: dict[str, str] = {}
    source_rows: list[dict[str, Any]] = []
    profile_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    search_id = f"S-{batch_id}"

    for item_key in keys:
        try:
            item = fetch_zotero_item(args.base_url, item_key)
            if not item["title"]:
                raise ValueError("Zotero item has no title")
        except Exception as exc:  # continue the batch and expose the exact failure
            failures.append(
                {
                    "failure_id": f"F{len(failures) + 1:03d}",
                    "stage": "检索",
                    "paper_id": "",
                    "input": item_key,
                    "reason": "无法读取Zotero条目",
                    "error_message": str(exc),
                    "action": "检查Zotero Desktop、本地API和item key后重试",
                    "status": "open",
                    "owner": args.operator,
                }
            )
            continue

        key = identity_key(
            doi=item["doi"], title=item["title"], year=item["year"], first_author=item["first_author"]
        )
        existing_id = identities.get(key) or batch_seen.get(key)
        if existing_id:
            paper_id = existing_id
            duplicate_status = "duplicate"
            inclusion_status = "excluded"
            inclusion_reason = "DOI或规范化题名+年份+第一作者重复；复用既有paper_id"
            profile_status = "reused"
        else:
            paper_id = allocate_paper_id(item["year"], used_ids)
            identities[key] = paper_id
            batch_seen[key] = paper_id
            duplicate_status = "unique"
            inclusion_status = "included"
            inclusion_reason = "代表性试运行样本；具体角色见批次运行日志"
            profile_status = "skeleton"
            profile_rows.append(skeleton_profile(item, paper_id, args.research_question, batch_id))

        access_level = "abstract" if item.get("abstract") else "metadata"
        source_rows.append({"paper_id": paper_id, **item})
        sample_rows.append(
            {
                "paper_id": paper_id,
                "zotero_item_key": item_key,
                "title": item["title"],
                "first_author": item["first_author"],
                "year": item["year"] or "",
                "venue": item["venue"] or "",
                "doi": item["doi"] or "",
                "url": item["url"] or "",
                "source_search_id": search_id,
                "batch_id": batch_id,
                "duplicate_status": duplicate_status,
                "inclusion_status": inclusion_status,
                "inclusion_reason": inclusion_reason,
                "access_level": access_level,
                "profile_status": profile_status,
                "note_link": "",
            }
        )

    search_rows = [
        {
            "search_id": search_id,
            "source": "Zotero local API",
            "query": "item_keys=" + ",".join(keys),
            "search_date": today_iso(),
            "result_count": len(source_rows),
            "export_file": str(sample_path.relative_to(vault_root)).replace("\\", "/"),
            "operator": args.operator,
            "notes": f"代表性试运行；research_question={args.research_question}; 不声称穷尽检索；不生成主题地图",
        }
    ]
    write_csv(search_path, SEARCH_FIELDS, search_rows)
    write_csv(sample_path, SAMPLE_FIELDS, sample_rows)
    write_jsonl(source_path, source_rows)
    write_jsonl(profile_path, profile_rows)
    write_csv(failure_path, FAILURE_FIELDS, failures)
    write_csv(quality_path, QUALITY_FIELDS, [])

    run_log = {
        "tool": "profile_pipeline.py",
        "tool_version": TOOL_VERSION,
        "batch_id": batch_id,
        "started_at": now_iso(),
        "completed_at": now_iso(),
        "mode": "representative_pilot",
        "zotero_write": False,
        "pdf_copied": False,
        "input": {"item_keys": keys, "research_question": args.research_question, "operator": args.operator, "base_url": args.base_url},
        "counts": {"requested": len(keys), "retrieved": len(source_rows), "profiles_skeleton": len(profile_rows), "failures": len(failures)},
        "outputs": {
            "search_record": str(search_path.relative_to(vault_root)).replace("\\", "/"),
            "sample_list": str(sample_path.relative_to(vault_root)).replace("\\", "/"),
            "sources": str(source_path.relative_to(vault_root)).replace("\\", "/"),
            "profiles": str(profile_path.relative_to(vault_root)).replace("\\", "/"),
            "failures": str(failure_path.relative_to(vault_root)).replace("\\", "/"),
            "quality": str(quality_path.relative_to(vault_root)).replace("\\", "/"),
        },
        "evidence_boundary": "自动生成仅建立元数据/摘要骨架；科学字段须按实际证据补全。本工具不生成主题地图，candidate_themes保持空数组。",
        "rerun_checks": [],
    }
    write_json(run_path, run_log)
    print(json.dumps({"status": "created", "batch_id": batch_id, "counts": run_log["counts"], "outputs": run_log["outputs"]}, ensure_ascii=False, indent=2))
    return 0


def validate_profiles(args: argparse.Namespace) -> int:
    vault_root = Path(args.vault_root).resolve()
    profile_path = Path(args.profiles)
    if not profile_path.is_absolute():
        profile_path = (vault_root / profile_path).resolve()
    schema_path = vault_root / "10_文献知识" / "paper_profile.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
    required = set(schema.get("required") or [])
    allowed = set((schema.get("properties") or {}).keys())
    rows = read_jsonl(profile_path)
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    seen_identity: dict[str, str] = {}
    presence_rates: list[float] = []

    array_fields = {"authors", "datasets", "methods", "baselines", "metrics", "main_findings", "claimed_innovations", "limitations", "candidate_themes", "provenance"}
    for line_no, item in enumerate(rows, 1):
        missing = sorted(required - set(item))
        extra = sorted(set(item) - allowed)
        presence_rates.append((len(required) - len(missing)) / len(required) if required else 1.0)
        if missing:
            errors.append(f"line {line_no}: missing required fields: {', '.join(missing)}")
        if extra:
            errors.append(f"line {line_no}: additional properties not allowed: {', '.join(extra)}")
        for field in array_fields:
            if field in item and not isinstance(item[field], list):
                errors.append(f"line {line_no}: {field} must be an array")
        for field in ("main_findings", "claimed_innovations", "limitations"):
            if isinstance(item.get(field), list) and len(item[field]) > 3:
                errors.append(f"line {line_no}: {field} has more than 3 items")
        if item.get("profile_version") != "0.2":
            errors.append(f"line {line_no}: profile_version must be 0.2")
        if item.get("access_level") not in ACCESS:
            errors.append(f"line {line_no}: invalid access_level")
        if item.get("review_level") not in REVIEW:
            errors.append(f"line {line_no}: invalid review_level")
        if "evidence_status" in item and item.get("evidence_status") not in EVIDENCE:
            errors.append(f"line {line_no}: invalid evidence_status")
        if "review_status" in item and item.get("review_status") not in REVIEW_STATUS:
            errors.append(f"line {line_no}: invalid review_status")
        if item.get("access_level") == "fulltext" and item.get("review_level") == "auto_extracted":
            if item.get("evidence_status") not in {None, "partial_text"}:
                errors.append(f"line {line_no}: machine full-text traversal cannot exceed partial_text")
        if item.get("review_status") == "mentor_checked" and item.get("review_level") != "mentor_confirmed":
            errors.append(f"line {line_no}: incompatible old/new review states")
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            errors.append(f"line {line_no}: confidence must be between 0 and 1")
        tier = item.get("journal_tier")
        if tier not in {1, 2, 3, 4, None}:
            errors.append(f"line {line_no}: journal_tier must be 1, 2, 3, 4, or null")
        paper_id = str(item.get("paper_id") or "")
        if paper_id in seen_ids:
            errors.append(f"line {line_no}: duplicate paper_id {paper_id}")
        seen_ids.add(paper_id)
        authors = item.get("authors") if isinstance(item.get("authors"), list) else []
        key = identity_key(doi=item.get("doi"), title=item.get("title"), year=item.get("year"), first_author=authors[0] if authors else "")
        if key in seen_identity and seen_identity[key] != paper_id:
            errors.append(f"line {line_no}: duplicate paper identity with {seen_identity[key]}")
        seen_identity[key] = paper_id
        if item.get("access_level") == "abstract" and item.get("limitations"):
            warnings.append(f"line {line_no}: limitations from abstract require explicit abstract wording or review")

    average_presence = sum(presence_rates) / len(presence_rates) if presence_rates else 0.0
    if rows and average_presence < 0.90:
        errors.append(f"average required-field presence below 90%: {average_presence:.1%}")
    result = {
        "status": "PASS" if not errors else "FAIL",
        "profiles": len(rows),
        "required_field_presence": round(average_presence, 4),
        "errors": errors,
        "warnings": warnings,
        "profile_file": str(profile_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def journal_summary(args: argparse.Namespace) -> int:
    vault_root = Path(args.vault_root).resolve()
    profile_path = Path(args.profiles)
    if not profile_path.is_absolute():
        profile_path = (vault_root / profile_path).resolve()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in read_jsonl(profile_path):
        groups[str(item.get("venue") or "未知期刊")].append(item)
    summary: list[dict[str, Any]] = []
    for venue in sorted(groups):
        items = groups[venue]
        years = sorted({item.get("year") for item in items if isinstance(item.get("year"), int)})
        tiers = sorted({item.get("journal_tier") for item in items if item.get("journal_tier") is not None})
        summary.append(
            {
                "venue": venue,
                "journal_tiers_in_profiles": tiers,
                "sample_count": len(items),
                "year_min": min(years) if years else None,
                "year_max": max(years) if years else None,
                "access_levels": dict(Counter(str(item.get("access_level")) for item in items)),
                "review_levels": dict(Counter(str(item.get("review_level")) for item in items)),
                "paper_ids": [item.get("paper_id") for item in items],
                "research_problems": sorted({str(item.get("research_problem")) for item in items if item.get("research_problem")}),
                "forecast_targets": sorted({str(item.get("forecast_target")) for item in items if item.get("forecast_target")}),
                "boundary": "仅为本批已完成画像样本统计，不代表整本期刊。",
            }
        )
    payload = {"generated_at": now_iso(), "profile_file": str(profile_path), "journals": summary}
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = (vault_root / out).resolve()
        if out.exists():
            raise FileExistsError(f"refusing to overwrite: {out}")
        if out.suffix.lower() == ".md":
            lines = [
                "# 期刊分层与样本观察 V0",
                "",
                f"- 生成时间：{payload['generated_at']}",
                f"- 输入画像：`{profile_path.name}`",
                "- 独立性：本文件只观察期刊样本，不参与核心文献总分，也不生成主题地图。",
                "- 证据边界：只基于本批画像；不得用少量样本概括整本期刊。",
                "",
            ]
            for entry in summary:
                tiers = entry["journal_tiers_in_profiles"]
                tier_text = (
                    "、".join(f"第{tier}档" for tier in tiers) + "（来自画像中的已核验模板映射）"
                    if tiers
                    else "待独立核验；不根据期刊名称猜测"
                )
                year_text = (
                    str(entry["year_min"])
                    if entry["year_min"] == entry["year_max"]
                    else f"{entry['year_min']}—{entry['year_max']}"
                )
                access_text = "、".join(f"{key}={value}" for key, value in sorted(entry["access_levels"].items()))
                review_text = "、".join(f"{key}={value}" for key, value in sorted(entry["review_levels"].items()))
                problems = entry["research_problems"]
                targets = entry["forecast_targets"]
                lines.extend(
                    [
                        f"## {entry['venue']}",
                        "",
                        f"- 层级及理由：{tier_text}",
                        f"- 本轮样本数：{entry['sample_count']}（{year_text}）",
                        f"- 样本论文：{', '.join(str(value) for value in entry['paper_ids'])}",
                        f"- 数据范围与证据规模：{access_text}；复核级别 {review_text}",
                        "- 样本中的研究问题：本批样本不足以判断整刊；仅列出画像中已有问题。",
                    ]
                )
                if problems:
                    lines.extend(f"  - {problem}" for problem in problems)
                else:
                    lines.append("  - 无可用研究问题记录")
                lines.append("- 样本中的预测对象：" + ("、".join(targets) if targets else "未记录"))
                lines.extend(
                    [
                        "- 常见创新类型：本批样本不足，不作整刊概括。",
                        "- 方法在论文中的角色：需在全文级样本扩大后观察。",
                        "- 论文叙事特点：当前证据不足。",
                        "- 与当前研究问题的关系：本命令不自动判定；由核心筛选环节按用户问题记录。",
                        f"- 仅基于样本的局限：{entry['boundary']}",
                        "",
                    ]
                )
            atomic_write_text(out, "\n".join(lines).rstrip() + "\n")
        else:
            write_json(out, payload)
        print(json.dumps({"status": "created", "out": str(out), "journals": len(summary)}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="Create missing V0.2 control-layer directories and templates without overwriting")
    init_parser.add_argument("--vault-root", required=True)

    collect = sub.add_parser("collect-zotero", help="Create a representative batch from Zotero local API metadata/abstracts")
    collect.add_argument("--vault-root", required=True)
    collect.add_argument("--batch-id", required=True)
    collect.add_argument("--item-keys", nargs="+", required=True)
    question = collect.add_mutually_exclusive_group(required=True)
    question.add_argument("--research-question", dest="research_question")
    question.add_argument("--seed-topic", dest="research_question", help=argparse.SUPPRESS)
    collect.add_argument("--operator", default="Codex auto_extracted")
    collect.add_argument("--base-url", default="http://127.0.0.1:23119")

    validate = sub.add_parser("validate", help="Validate a profile JSONL against the project schema and duplicate rules")
    validate.add_argument("--vault-root", required=True)
    validate.add_argument("--profiles", required=True)

    journals = sub.add_parser("journal-summary", help="Create a neutral per-venue summary from completed profiles")
    journals.add_argument("--vault-root", required=True)
    journals.add_argument("--profiles", required=True)
    journals.add_argument("--out")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "init":
            print(json.dumps({"status": "ok", **init_layout(Path(args.vault_root).resolve())}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "collect-zotero":
            return collect_zotero(args)
        if args.command == "validate":
            return validate_profiles(args)
        if args.command == "journal-summary":
            return journal_summary(args)
        parser.error("unknown command")
    except (FileNotFoundError, FileExistsError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
