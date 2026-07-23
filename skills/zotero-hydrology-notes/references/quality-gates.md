# Quality gates

## OpenAlex discovery and PDF retrieval

- The API key is supplied only through `OPENALEX_API_KEY` or an approved secret store and is absent from commands saved to disk, logs, records, URLs, and outputs.
- Exact query, filters, sort, date, counts, request signature, and API-reported cost/rate information are recorded.
- The complete candidate list is deduplicated before download by DOI, then normalized title + year + first author.
- Every download is explicitly selected by OpenAlex work ID from the reviewed candidate list; no unreviewed whole-batch download occurs.
- The read-only Zotero check runs before download; existing items are reused and skipped unless a missing-attachment repair is explicitly authorized.
- The default route accepts only a direct OA PDF reported through an OpenAlex OA location. Missing license information is recorded as unknown, never inferred.
- OpenAlex cached content remains disabled unless current cost is checked and the user explicitly accepts it with both required flags.
- PDF staging is outside the vault; public host/redirect safety, maximum size, `%PDF-` signature, checksum, version, source, license, rights note, and failures are recorded.
- No paywall, login, CAPTCHA, institutional restriction, robots rule, or publisher control is bypassed.
- A PDF is not reported as attached until the correct Zotero top-level item and child attachment are re-queried and verified.

## Batch and identity

- Batch ID, seed question, operator, item keys, date, and scope are recorded.
- DOI duplicates are removed; fallback title + year + first-author duplicates are flagged.
- `paper_id` remains stable across machine records. Every human-facing Markdown view resolves it to the full linked article title and does not expose the identifier as the paper name.
- Zotero item keys, attachment keys, BibTeX citekeys, and paper IDs are not confused.
- Identical reruns create no duplicate records; conflicting reruns stop and create a failure record.

## Profile

- Every object follows the schema and includes all required fields.
- Unavailable scalars use `null`; unavailable lists use `[]`.
- Access and review levels are independent and use approved enums.
- A completed lightweight profile has `access_level=fulltext`, whole-file traversal evidence, section coverage, and anchors from methods, results, discussion/limitations, and availability when those sections exist.
- Metadata/abstract/partial-text items are blockers or incomplete stubs and are excluded from the completed-profile count.
- Main findings, claimed innovations, and limitations contain at most three items each.
- New profiles keep the legacy `candidate_themes` compatibility field empty; this skill does not generate theme-map content.
- No schema or full run log is repeated inside a profile.

## Independent analyses

- Journal tier is not a core-selection hard gate.
- Core selection uses the five required scientific/evidence dimensions—theme relevance, representativeness, frontier, conflict, and evidence value—and records roles and reasons.
- Classic value is a role; journal tier is non-scoring context and cannot approve, reject, or change reading depth.
- Representativeness and proximity are judged against the user-supplied research question, not a generated theme.
- Small-sample journal observations state sample count, time range, evidence distribution, and limitations.
- No output is written to `20_主题地图/`; no candidate category, relation table, problem cluster, or paper idea is created.

## Deep reading

- Deep reading is backed by an explicit user choice or core-selection record.
- The title, authors, year, DOI, Zotero item key, and attachment belong to the same paper.
- The live template remains structurally complete.
- Read coverage is labeled metadata, abstract, partial text, or complete full text.
- Major claims have content-based evidence explanations; useful section/figure/table names may follow as secondary navigation.
- Human-facing Markdown contains no extraction line number, paragraph number, MinerU offset, `§…，L数字`, `抽取行 数字`, `全文相关章节`, `原文证据卡（见……）`, or bare claim ID presented as evidence. These technical offsets remain only in the machine JSONL.
- Every visible evidence item contains a bounded original excerpt or paper-specific substantive Chinese analysis, the supported claim, and the evidence boundary. Generic phrases such as “该段用于界定……” fail this gate unless the sentence names what the source actually says.
- Zero visible matches are allowed for keyword-list prose or stock analysis, including `涉及：…、…`, `当前可核验关键词为`, `原文报告了与`, `原文提供了…线索`, `论文确实提出了这一问题`, and `方法存在不等于性能提升`. Equivalent paraphrases fail as well.
- Every included paper has one reviewed synthesis record with ten distinct content fields: problem, data/design, method chain, validation, findings, limitations, uncertainty/robustness, engineering meaning, research judgment, and minimum verification/reproduction.
- At least six of those fields must contain paper-specific nouns beyond the title. No non-status sentence may be duplicated more than twice in one file. A bibliography fragment, general background sentence, or metric definition cannot be labeled as the paper's result.
- Values retain units, conditions, baselines, and source anchors.
- Caption-only analysis does not claim figure inspection.
- No page, equation, statistic, mechanism, constraint, limitation, or reference is invented.
- All 16 live-template major sections are present in order; omitted content is marked `未报告` or `不适用` with a reason.
- Complete-full-text notes satisfy the evidence-anchor, claim–evidence, quantitative-result, figure/table, leakage-audit, validity, engineering, and minimum-reproduction thresholds in `note-workflow.md`.
- Short synopsis-style notes are labeled `核心章节阅读/partial_text`, not complete intensive reading.

## Records and filesystem

- Schema, batch/source list, profiles, run logs, failures, quality checks, evidence indexes, journal observations, core selection, and deep notes are in their separate destinations.
- Core selection is stored under `10_文献知识/core/`, not the theme-map layer.
- No PDF is copied into the vault.
- No existing output is overwritten silently.
- Temporary extraction bundles stay outside final note directories.
- Every human-reviewed CSV/JSON/JSONL has a UTF-8 Markdown companion and is linked from a batch navigation note.
- Markdown companions contain no replacement characters or mojibake and render readable headings/tables in Obsidian.
- Human-facing literature labels are linked article titles, never bare paper IDs, Zotero keys, attachment keys, or citekeys.
- Every human-facing output has a named source ledger. Each used literature/data/project/task file is shown by complete name and DOI/publisher/Zotero/Obsidian link; identifiers alone fail validation.
- Lightweight-profile Markdown cards meet the 3000–5500 Chinese-character-equivalent body-depth gate, use full-text evidence beyond the abstract, contain at least 15 substantive modules, and include an argument chain, three source-grounded evidence cards when available, competing explanations, five validity dimensions and a discriminating experiment.
- Partial-text intensive notes meet the 7500 Chinese-character-equivalent body-depth gate, preserve the 16 major sections, contain at least five claim–evidence judgments and three selected evidence cards when available, and add paper-specific validation, transfer and failure diagnoses rather than repeating the ten synthesis fields.
- The data, method, validation and limitation modules each contain at least three labeled, non-duplicate paper-specific analytical items. Result count has no minimum: render only paper-owned findings from inspected result/table/figure/discussion/conclusion evidence.
- A result finding fails validation if it is a cited-study statement, background claim, metric definition, method description, future work, audit note, missing-evidence statement, `待回查`, `未确认`, or `不能作为本文结果`. Conditions, interpretations and boundaries belong inside a real finding card or their scientific modules; they never become extra R-items.
- A section counts toward depth only when it contributes a paper-specific fact, cross-field inference, competing explanation, boundary or executable verification action. Empty tables, status rows, source ledgers, copied headings and generic checklists are excluded from the depth calculation.
- Lightweight profiles are stored one paper per Markdown file in the routed subject folder, with a complete title-linked index and no primary monolithic profile document.
- Human-facing profile and deep-note Markdown uses Chinese visible titles, prose, evidence explanations, status labels, and section locators. The exact English title may remain only in YAML `title_original` and machine records.
- Long raw English full-text sentences and captions remain in machine evidence records. Human Markdown may contain no more than three excerpts per paper and eight words per excerpt, each paired with `中文分析（AI概括）` and an auditable source anchor.
- A long-English-sentence scan passes after excluding YAML `title_original`, URLs, DOI, authors, journal names, proper dataset/model names, acronyms, formulas, symbols, and units.
- The batch Chinese-title map covers every completed profile; missing translations fail the run.

## Pilot completion

- Use 5–10 representative papers unless the user sets another size.
- Check every profile when the pilot has fewer than 10 papers; otherwise sample at least 10.
- Record failures even when profile generation continues at a lower access level.
- Include one repeated-run test and report `unchanged`/no duplicate output.
- Disclose any blocked full-text reads instead of manufacturing a deep-note example.
- Approved and completed deep reads match the current manifest only when `expected_counts.core_deep_reads` is present. Otherwise quantity is not a gate. No historical test count or default ratio may be substituted.
