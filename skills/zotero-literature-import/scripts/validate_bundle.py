#!/usr/bin/env python3
"""Dependency-free structural, privacy, and syntax validator for this Skill."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REQUIRED = [
    "SKILL.md",
    "agents/openai.yaml",
    "evals/evals.json",
    "references/openalex-search-and-pdf.md",
    "references/search-and-ranking.md",
    "references/zotero-write-policy.md",
    "references/existing-item-pdf-reconciliation.md",
    "references/institutional-access.md",
    "scripts/openalex_import.py",
    "scripts/zotero_dedup.py",
    "scripts/zotero_connector_import.py",
    "scripts/zotero_webapi_collection.py",
]


def frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not match:
        raise ValueError("missing SKILL.md YAML frontmatter")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")) or ":" not in line:
            raise ValueError("frontmatter must use flat scalar fields")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip("\"'")
    return fields


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append(f"missing required file: {relative}")

    skill = root / "SKILL.md"
    if skill.is_file():
        try:
            fields = frontmatter(skill.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if set(fields) != {"name", "description"}:
                errors.append(f"frontmatter fields must be name and description: {sorted(fields)}")
            if fields.get("name") != "zotero-literature-import":
                errors.append("unexpected skill name")
            description = fields.get("description", "")
            if not description or len(description) > 1024 or "<" in description or ">" in description:
                errors.append("invalid skill description")

    openai = root / "agents" / "openai.yaml"
    if openai.is_file():
        text = openai.read_text(encoding="utf-8")
        for marker in ("interface:", "display_name:", "short_description:", "default_prompt:"):
            if marker not in text:
                errors.append(f"agents/openai.yaml missing {marker}")
        if "$zotero-literature-import" not in text:
            errors.append("default_prompt does not invoke the Skill")

    evals = root / "evals" / "evals.json"
    if evals.is_file():
        try:
            payload = json.loads(evals.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid eval JSON: {exc}")
        else:
            if payload.get("skill_name") != "zotero-literature-import":
                errors.append("eval skill_name mismatch")

    for script in (root / "scripts").glob("*.py"):
        try:
            text = script.read_text(encoding="utf-8")
            compile(text, str(script), "exec")
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append(f"invalid Python script {script.name}: {exc}")

    helper = root / "scripts" / "openalex_import.py"
    if helper.is_file():
        text = helper.read_text(encoding="utf-8")
        for marker in (
            "OPENALEX_API_KEY",
            "--zotero-check",
            "--openalex-id",
            "--accept-openalex-content-cost",
            "%PDF-",
        ):
            if marker not in text:
                errors.append(f"OpenAlex helper missing safety marker: {marker}")
        if re.search(r"(?:api_key|OPENALEX_API_KEY)\s*=\s*['\"][A-Za-z0-9_-]{16,}['\"]", text):
            errors.append("OpenAlex helper appears to contain a hard-coded API key")

    privacy_patterns = {
        "specific institution": re.compile("Dalian " + "University|" + "大连" + "理工", re.IGNORECASE),
        "Windows user path": re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+", re.IGNORECASE),
        "Program Files path": re.compile(r"[A-Za-z]:[\\/]+Program Files(?: \(x86\))?", re.IGNORECASE),
    }
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".zip"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in privacy_patterns.items():
            if pattern.search(text):
                errors.append(f"{label} found in {path.relative_to(root)}")

    return errors


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
    errors = validate(root)
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
