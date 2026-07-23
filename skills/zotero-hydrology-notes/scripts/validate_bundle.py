#!/usr/bin/env python3
"""Offline structural validator for the zotero-hydrology-notes skill bundle."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REQUIRED_FILES = [
    "SKILL.md",
    "agents/openai.yaml",
    "references/openalex-workflow.md",
    "references/profile-workflow.md",
    "references/core-journal-workflow.md",
    "references/note-workflow.md",
    "references/quality-gates.md",
    "references/input-manifest-contract.md",
    "references/appendix-a1-core-candidate.md",
    "references/paper_profile.schema.json",
    "references/检索记录模板.csv",
    "references/失败记录模板.csv",
    "references/样本文献清单模板.csv",
    "references/质量抽检模板.csv",
    "references/期刊分层与样本观察模板.md",
    "references/核心文献选择模板.csv",
    "scripts/profile_pipeline.py",
    "scripts/openalex_oa.py",
    "scripts/zotero_mineru.py",
    "scripts/fulltext_profile_batch.py",
    "scripts/fulltext_deep_read_batch.py",
]


def simple_top_level_yaml(text: str) -> dict[str, str]:
    """Parse the flat scalar YAML used by SKILL.md frontmatter."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")) or ":" not in line:
            raise ValueError("frontmatter must contain flat top-level scalar fields")
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"missing required file: {relative}")

    skill_path = root / "SKILL.md"
    if skill_path.is_file():
        content = skill_path.read_text(encoding="utf-8")
        match = re.match(r"^---\r?\n(.*?)\r?\n---", content, re.DOTALL)
        if not match:
            errors.append("invalid or missing SKILL.md YAML frontmatter")
        else:
            try:
                frontmatter = simple_top_level_yaml(match.group(1))
            except ValueError as exc:
                errors.append(str(exc))
            else:
                allowed = {"name", "description", "license", "allowed-tools", "metadata"}
                unexpected = sorted(set(frontmatter) - allowed)
                if unexpected:
                    errors.append(f"unexpected frontmatter keys: {unexpected}")
                name = frontmatter.get("name", "")
                description = frontmatter.get("description", "")
                if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
                    errors.append("invalid skill name")
                if not description or len(description) > 1024 or "<" in description or ">" in description:
                    errors.append("invalid skill description")

    openai_path = root / "agents" / "openai.yaml"
    if openai_path.is_file():
        openai_text = openai_path.read_text(encoding="utf-8")
        for field in ("interface:", "display_name:", "short_description:", "default_prompt:"):
            if field not in openai_text:
                errors.append(f"agents/openai.yaml missing {field}")
        if "$zotero-hydrology-notes" not in openai_text:
            errors.append("default_prompt does not invoke $zotero-hydrology-notes")

    schema_path = root / "references" / "paper_profile.schema.json"
    if schema_path.is_file():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid profile schema JSON: {exc}")
        else:
            access = schema.get("properties", {}).get("access_level", {}).get("enum", [])
            required_access = {"metadata", "abstract", "partial_text", "fulltext"}
            if not required_access.issubset(set(access)):
                errors.append("profile schema does not distinguish metadata/abstract/partial_text/fulltext")
            evidence = schema.get("properties", {}).get("evidence_status", {}).get("enum", [])
            if set(evidence) != {"metadata_only", "abstract_only", "partial_text", "full_text_main", "full_text_with_supplement"}:
                errors.append("profile schema missing normalized evidence_status contract")
            review = schema.get("properties", {}).get("review_status", {}).get("enum", [])
            if set(review) != {"unverified", "self_checked", "cross_checked", "mentor_checked"}:
                errors.append("profile schema missing normalized review_status contract")

    obsolete = root / "references" / "topic-core-journal-workflow.md"
    if obsolete.exists():
        errors.append("obsolete theme-workflow reference still exists")

    pipeline_path = root / "scripts" / "profile_pipeline.py"
    if pipeline_path.is_file():
        pipeline_text = pipeline_path.read_text(encoding="utf-8")
        forbidden = ["20_" + "主题地图", "文献主题关系_", "候选主题卡"]
        for value in forbidden:
            if value in pipeline_text:
                errors.append(f"profile pipeline still contains theme-map output marker: {value}")

    for relative in ("scripts/fulltext_profile_batch.py", "scripts/fulltext_deep_read_batch.py"):
        script_path = root / relative
        if script_path.is_file():
            text = script_path.read_text(encoding="utf-8")
            if re.search(r"default\s*=\s*0\.30\b", text):
                errors.append(f"{relative} contains a default deep-reading ratio")
            if "expected_counts.core_deep_reads" not in text:
                errors.append(f"{relative} does not support the manifest quantity contract")
            if 'evidence_status: "partial_text"' not in text or 'review_status: "unverified"' not in text:
                errors.append(f"{relative} does not keep machine full-text output at partial_text/unverified")

    openalex_path = root / "scripts" / "openalex_oa.py"
    if openalex_path.is_file():
        openalex_text = openalex_path.read_text(encoding="utf-8")
        for marker in (
            "OPENALEX_API_KEY",
            "--zotero-check",
            "--openalex-id",
            "--accept-openalex-content-cost",
            "%PDF-",
        ):
            if marker not in openalex_text:
                errors.append(f"OpenAlex helper missing safety marker: {marker}")
        if re.search(r"(?:api_key|OPENALEX_API_KEY)\s*=\s*['\"][A-Za-z0-9_-]{16,}['\"]", openalex_text):
            errors.append("OpenAlex helper appears to contain a hard-coded API key")

    for relative in (
        "scripts/profile_pipeline.py", "scripts/openalex_oa.py", "scripts/zotero_mineru.py",
        "scripts/fulltext_profile_batch.py", "scripts/fulltext_deep_read_batch.py",
    ):
        script_path = root / relative
        if script_path.is_file():
            try:
                compile(script_path.read_text(encoding="utf-8"), str(script_path), "exec")
            except SyntaxError as exc:
                errors.append(f"syntax error in {relative}: {exc}")

    privacy_patterns = [
        re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+", re.IGNORECASE),
        re.compile(r"[A-Za-z]:[\\/]+Program Files(?: \(x86\))?", re.IGNORECASE),
    ]
    for path in root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".zip", ".pyc"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in privacy_patterns:
            if pattern.search(text):
                errors.append(f"machine-specific path found in {path.relative_to(root)}")

    return errors


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
    errors = validate(root)
    payload = {"status": "PASS" if not errors else "FAIL", "skill_root": str(root), "errors": errors}
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
