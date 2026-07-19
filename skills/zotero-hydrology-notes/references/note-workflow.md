# Note construction workflow

## Source inventory

Create an internal record for each paper before drafting:

- Zotero top-level item key and bibliographic metadata
- parsed attachment key and numeric cache ID
- original `full.md` path and temporary extraction path
- manifest section/page anchors
- source coverage: read, partially read, missing, or unreadable

Do not expose temporary paths as evidence anchors when a stable Zotero key, section, page, figure, or table anchor exists.

## Template filling rules

1. Copy the live template as the structural base. Preserve all headings and their order.
2. Fill YAML with Zotero metadata and paper evidence. Quote YAML strings when punctuation could be parsed as YAML syntax.
3. Replace `{{date}}` with the current local date.
4. Mark Zotero-only bibliographic fields `待核验` unless independently verified.
5. Use `未报告` when the read source does not report a requested value; use `不适用` when the analytical module does not apply.
6. Keep checkboxes unchecked unless the work in that checkbox was actually completed.
7. Keep quantitative values with units, conditions, comparison baseline, and source anchors.
8. Distinguish direct observations from the authors' explanations and the reader's evaluation.

## Evidence anchors

Prefer anchors in this order:

1. PDF page plus figure/table/equation label when the manifest or Markdown supports it
2. figure/table/equation label plus section heading
3. section heading plus a stable local anchor such as `Zotero:ITEMKEY/Attachment:KEY`
4. `[待核验]` when no stable anchor exists

MinerU manifest pages are zero-based in some plugin versions. When a page value is `0`, or when printed and manifest page numbering may differ, write `MinerU page index N（PDF页码待核验）` rather than converting it silently.

## Comprehensive reading map

- Frontmatter and section 1: Zotero metadata, paper title block, abstract, author affiliations, DOI text
- Sections 2–4: definitions, notation, introduction, study area, engineering context
- Sections 5–6: data, preprocessing, equations, model, optimization, assumptions
- Sections 7–8: experimental design, metrics, uncertainty, sensitivity, robustness
- Section 9: results, figure/table captions, quantitative comparisons
- Sections 10–12: discussion, limitations, transferability, engineering feasibility, validity
- Sections 13–16: relevance to the current project, writing uses, reproducibility, final judgment and next actions

Do not fill every table row with generic prose. Prefer a precise `未报告` or `不适用` over decorative content.

## Batch mode

Resolve and extract all papers before drafting. Build a terminology ledger across the batch so the same concept, unit, reservoir level, forecast horizon, and uncertainty term use one canonical form.

Create one full note per paper. After all drafts exist:

- check Zotero keys and titles are not mixed between files
- check numeric results trace to the correct paper
- add cross-links using Obsidian `[[note name]]` syntax
- classify relations as support, conflict, complement, or combinable only when both papers were actually read
- state likely sources of disagreement such as data, scale, method, constraints, or evaluation target

Create a synthesis note only when explicitly requested. Include a source inventory and a claim-evidence matrix; do not collapse conflicting findings into a false consensus.

## Filename and collision handling

Sanitize Windows-invalid characters `< > : " / \\ | ? *`, remove trailing dots/spaces, and keep the filename concise. Search destination files for `zotero_item_key: "ITEMKEY"` before writing. If found, stop at the overwrite gate.
