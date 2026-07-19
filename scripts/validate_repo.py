#!/usr/bin/env python3
"""Validate public skill structure, Python syntax, and common secret/path leaks."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
EXPECTED = {
    "zotero-literature-import",
    "zotero-hydrology-notes",
    "analyze-obsidian-research",
}
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py", ".ps1", ".toml", ".txt"}
FORBIDDEN = {
    "Windows user profile path": re.compile(r"[A-Za-z]:\\Users\\[^<\\\s]+", re.I),
    "absolute Windows drive path": re.compile(r"\b[A-Za-z]:[\\/]"),
    "GitHub token": re.compile(r"\b(?:gho_|ghp_|github_pat_)[A-Za-z0-9_]+"),
    "OpenAI-style token": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def main() -> int:
    failures: list[str] = []
    found = {path.name for path in SKILLS.iterdir() if path.is_dir()}
    if found != EXPECTED:
        fail(f"Expected skills {sorted(EXPECTED)}, found {sorted(found)}", failures)

    for folder in sorted(SKILLS.iterdir()):
        if not folder.is_dir():
            continue
        skill_md = folder / "SKILL.md"
        metadata = folder / "agents" / "openai.yaml"
        if not skill_md.is_file():
            fail(f"Missing {skill_md.relative_to(ROOT)}", failures)
            continue
        if not metadata.is_file():
            fail(f"Missing {metadata.relative_to(ROOT)}", failures)
        text = skill_md.read_text(encoding="utf-8-sig")
        front = re.match(r"^---\s*\nname:\s*([^\n]+)\ndescription:\s*([^\n]+)\n---", text)
        if not front:
            fail(f"Invalid frontmatter: {skill_md.relative_to(ROOT)}", failures)
        elif front.group(1).strip().strip('"') != folder.name:
            fail(f"Skill name does not match folder: {folder.name}", failures)

    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() in {".pyc", ".pyo"} or path.name == "Thumbs.db":
            fail(f"Forbidden generated file: {path.relative_to(ROOT)}", failures)
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"LICENSE", ".gitignore"}:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            fail(f"Non-UTF-8 text file: {path.relative_to(ROOT)}", failures)
            continue
        for label, pattern in FORBIDDEN.items():
            if pattern.search(text):
                fail(f"{label}: {path.relative_to(ROOT)}", failures)
        if path.suffix.lower() == ".py":
            try:
                compile(text, str(path), "exec")
            except SyntaxError as exc:
                fail(f"Python syntax error in {path.relative_to(ROOT)}: {exc}", failures)

    if failures:
        print("VALIDATION_FAILED")
        for item in failures:
            print(f"- {item}")
        return 1
    print(f"VALIDATION_OK skills={len(EXPECTED)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
