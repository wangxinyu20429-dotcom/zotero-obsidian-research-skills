# Skill packages

Each folder is a complete Codex Skill. Install the whole folder, including `agents/`, `references/`, `scripts/`, and any `evals/` directory.

| Skill | Pipeline stage | Main safeguards |
| --- | --- | --- |
| `zotero-literature-import` | Discovery, ranking, duplicate audit, Zotero collection filing and guarded PDF import | Candidate and library deduplication, item-level approval, lawful PDF validation, dry-run writes |
| `zotero-hydrology-notes` | Identity resolution, lightweight profiles, evidence audit, Appendix A.1 core screening and intensive reading | Formal/exploratory separation, evidence/review separation, paper-specific synthesis, no theme-map or Idea output |
| `analyze-obsidian-research` | Appendix A.2 problem clusters and literature theme map | Manifest binding, typed relations, paper-by-paper interpretation, named source ledger |
| `develop-obsidian-paper-ideas` | Appendix A.3 directions and cross-theme candidate pool | Zero-to-three gate, falsifiability, data/experiment minimums, mentor-decision boundary |

## Required files

- `SKILL.md`: routing, workflow and hard boundaries.
- `agents/openai.yaml`: Codex display metadata.
- `references/`: contracts, schemas, templates and detailed procedures.
- `scripts/`: repeatable inventory, import, rendering and validation logic.
- `evals/`: skill evaluation cases when present.

Do not install a single file in isolation. Relative links in `SKILL.md` assume the original folder structure.

## Responsibility handoff

```text
zotero-literature-import
  → zotero-hydrology-notes
    → analyze-obsidian-research
      → develop-obsidian-paper-ideas
```

The handoff is evidence-based rather than automatic:

- imported metadata is not a reviewed profile;
- an extracted full text is not human-verified evidence;
- a reading note is not a problem cluster;
- a theme-map node is not evidence strength;
- a model-generated Idea is not a mentor decision.

## Public-package boundary

These folders must remain portable. Do not add:

- API keys, cookies, passwords, MFA data or browser profiles;
- local absolute paths or user-specific institution settings;
- Zotero databases, PDF attachments or exported private libraries;
- Obsidian vault content, unpublished manuscripts, internal reports or sensitive datasets;
- generated caches such as `__pycache__`, logs or local run outputs.

Run the repository validator after every update:

```powershell
python scripts/validate_repo.py
```
