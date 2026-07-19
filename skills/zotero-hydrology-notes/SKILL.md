---
name: zotero-hydrology-notes
description: Read papers from the local Zotero library and llm-for-zotero/MinerU Markdown cache, then create evidence-labeled intensive-reading notes from the user's hydrology, water-resources, and hydraulic-engineering template. Use when the user supplies a title, author, year, DOI, Zotero item key, or a list of papers and asks for 单篇文献精读、多篇文献笔记、批量精读、对比笔记、汛限水位动态控制文献笔记, or asks to turn llm-for-zotero Markdown papers into Obsidian notes.
---

# Zotero Hydrology Notes

Operate only on the user's local Zotero library and local files. Do not upload manuscript text, Zotero metadata, or cached Markdown to public services.

## Required path configuration

Resolve both paths before drafting:

1. Prefer paths explicitly supplied in the current prompt.
2. Otherwise read `HYDROLOGY_NOTE_TEMPLATE` for the Markdown template and `HYDROLOGY_NOTE_OUTPUT` for the note directory.
3. If either value is missing, ask the user. Never infer a private vault path or scan unrelated home directories.

Read the resolved template completely before drafting and write finished notes only under the resolved output directory. If either path is unavailable, stop and name the missing configuration; do not silently substitute another template or destination.

## Workflow

1. Inventory every identifier the user supplied: title, author, year, DOI, Zotero item key, and requested mode.
2. Run the bundled script's `status` command. Keep all Zotero operations read-only.
3. Resolve each paper with `search`. Prefer exact DOI or Zotero item key, then exact title plus author/year. Never select the first of multiple plausible matches.
4. Run `inspect --item-key KEY` to confirm that llm-for-zotero produced a MinerU `full.md` source for the paper.
5. Run `extract --item-key KEY` to materialize a temporary, read-only bundle. Use `--attachment-key` when a paper has multiple parsed PDF attachments.
6. Read `manifest.json` first. Read `full.md` progressively by the manifest's section offsets when possible. For a comprehensive template note, cover the abstract/introduction, data, methods, results, discussion, conclusion, limitations, references needed for context, and relevant figure/table captions. If the manifest has one section or `noSections: true`, read the full Markdown.
7. Read the live note template and fill it without changing its section order. Apply the rules in [references/note-workflow.md](references/note-workflow.md).
8. Validate the note against [references/quality-gates.md](references/quality-gates.md).
9. Write the final Markdown file to the fixed destination. Report the absolute path, matched Zotero item key, attachment key, and source `full.md` path.

Use the runtime's available Python executable. Example:

```powershell
python scripts/zotero_mineru.py status
python scripts/zotero_mineru.py search --query "paper title" --author "first author" --year 2024
python scripts/zotero_mineru.py inspect --item-key ABCD1234
python scripts/zotero_mineru.py extract --item-key ABCD1234
```

Resolve `scripts/zotero_mineru.py` relative to this `SKILL.md`, not relative to the current workspace.

## Mode selection

- For one paper, create one complete note.
- For multiple papers, create one complete note per paper by default, then run a cross-paper consistency pass and populate section 13.2 with only evidence-supported relations.
- When the user explicitly asks for a 综合、对比、综述、证据矩阵, create the per-paper notes and one additional synthesis note. In the synthesis, replace single-paper assumptions with a clearly labeled source inventory while preserving the template's analytical categories.
- Do not merge papers into one note merely because several identifiers appeared in the same prompt.

## Resolution and ambiguity gates

- Treat a Zotero item key as different from an attachment key and a BibTeX citekey.
- If `search` reports more than one plausible top-level item, show title, authors, year, DOI, and item key, then ask the user to choose.
- If `inspect` reports more than one parsed attachment, show attachment title/key and cache source, then ask the user to choose unless the user's information uniquely identifies it.
- If no llm-for-zotero Markdown exists, report that exact blocker. Do not silently replace it with an abstract or indexed PDF text. Offer indexed full text only as an explicit fallback choice.

## Evidence discipline

- Preserve the template labels: `[原文]`, `[作者结论]`, `[AI概括]`, `[科研判断]`, `[待核验]`, `[导师确认]`.
- Treat Zotero metadata as library metadata, not independently verified bibliography.
- Treat MinerU Markdown as extracted text. It can support structured reading, but page anchors, equations, tables, OCR, and exact quotations may still require PDF verification.
- Use `未报告`, `不适用`, or `[待核验]` for unsupported fields. Never invent results, mechanisms, references, sample sizes, statistics, equations, page numbers, or engineering constraints.
- Do not imply that a figure was visually inspected when only its caption or extracted text was read.
- Use short direct quotations only when exact source text and a stable source anchor are available.

## Output and overwrite policy

- Use a filesystem-safe name: `第一作者_年份_中文短题名.md`; append `_ZoteroItemKey` only to resolve collisions.
- Preserve YAML frontmatter. Set `zotero_item_key`, `source_file`, `source_url`, `reading_date`, and evidence status explicitly.
- Use `source_file` for the extracted or original `full.md` path and `source_url` as `zotero://select/library/items/ITEMKEY`.
- Before writing, search the destination for the same `zotero_item_key`. Never overwrite or silently revise an existing note. Ask whether to update it or create a timestamped side-by-side version.
- Write no raw extraction bundles into the final note directory; extraction bundles belong in the system temporary directory.

## Metadata verification

When the user additionally asks to verify reference metadata, invoke `nature-ref-verifier` and keep factual metadata corrections separate from note prose. Do not browse or call external bibliographic services merely to fill blank template fields unless the user requests verification or external research.
