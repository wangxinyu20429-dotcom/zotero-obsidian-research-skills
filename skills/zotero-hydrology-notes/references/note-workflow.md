# Intensive-reading note workflow

Use this workflow only after the paper is selected as core or explicitly selected by the user.

## Selection record

Before reading, record:

- `paper_id`, Zotero top-level item key, DOI, and profile path;
- user research question and role (`classic`, `representative`, `frontier`, `conflict`, `closest`, or user-selected);
- core-selection record or explicit user request;
- intended evidence question;
- evidence route and deep-read status.

Journal tier may be context but must not be the selection gate.

## Source inventory

Create an internal record for:

- Zotero top-level item key and bibliographic metadata;
- parsed attachment key and cache ID when available;
- original `full.md` path and temporary extraction path;
- manifest section/page anchors;
- source coverage: metadata, abstract, partial text, complete full text, missing, or unreadable.

Do not expose a temporary path as the only evidence anchor when a stable Zotero key, DOI, section, page, figure, table, or note link exists.

## Source and coverage gates

1. Run `inspect --item-key KEY`.
2. A PDF attachment does not prove a MinerU/full-text source exists.
3. If multiple parsed attachments exist, resolve the intended attachment explicitly.
4. If MinerU Markdown is absent, record the exact blocker. Do not replace it silently with an abstract or indexed fragment.
5. Use another local full-text route only when the user explicitly accepts it.
6. Label partial-section reading separately from complete full-text reading.

## Template filling

1. Read the live hydrology note template in full and preserve heading order.
2. Fill YAML and source blocks with the full article title, DOI/publisher link, Zotero deep link, a direct link to the paper's individual lightweight-profile file, core-selection link, source path, access level, review level, and reading date. Keep `paper_id`, Zotero item key, attachment key, and citekey out of visible literature labels; retain them only in machine records or a clearly labeled technical provenance block when strictly required.
3. Mark Zotero-only bibliographic fields `待核验` unless independently verified.
4. Use `未报告` when the read source does not report a value and `不适用` when a module does not apply.
5. Keep checkboxes unchecked unless completed.
6. Keep quantitative values with units, conditions, comparison baseline, and anchors.
7. Distinguish direct observations, author explanations, AI summaries, and research judgments.
8. Use Chinese for all visible prose, titles, evidence explanations, status labels, and index aliases. Keep the exact original title only in YAML `title_original` and the authoritative machine record. Preserve proper names, acronyms, symbols, formulas, units, authors, journal names, DOI, and URLs.
9. Do not display extraction line numbers, paragraph numbers, MinerU offsets, or placeholders such as `§结果，L145`. Render an evidence card with a bounded original excerpt or a paper-specific `中文分析（AI概括）`, plus what it supports and what remains uncertain. A section, figure, or table name is optional secondary navigation, never the evidence itself.
10. Keep long raw English full-text snippets outside the human note. A human note may retain at most three original excerpts per paper, each at most 8 words, only when needed to make the evidence anchor intelligible. Pair each with Chinese analysis and keep all longer text in the authoritative machine record.
11. Add `本文件实际使用的来源`, listing the complete linked article title, DOI/publisher page, Zotero link, individual profile file, core-selection record, full-text evidence record and input manifest. Identifiers may appear only as technical aliases.

## Detailed-note completeness gate

A deep-read note is not a polished abstract. Preserve the live template's 16 major sections in their original order. Preserve relevant subsections; for irrelevant modules write `不适用（原因）`, and for absent evidence write `未报告（已检查的章节）`.

For `access_level=fulltext` and a claimed complete intensive read, require all of the following:

- at least 8 non-duplicate evidence anchors distributed across problem, data/method, results, discussion/limitations, and availability;
- a claim–evidence map with at least 3 major claims, their required evidence, actual evidence, strength, and gap;
- at least 3 quantitative result cards when quantitative results exist, retaining units, conditions, baseline, sample size, and figure/table/section anchor;
- at least 2 figure/table reading blocks based on inspected content; if only caption/text was inspected, say `未检查原图，不评价视觉证据`;
- explicit dataset period, spatial/temporal scale, train/validation/test design, baseline list, metrics, and preprocessing/data-leakage audit;
- method reconstruction sufficient to state inputs, outputs, model chain, objective/loss, key hyperparameters or `未报告`, and operational information availability;
- uncertainty, sensitivity, robustness, distribution-shift, and extreme-event assessment;
- internal, construct, statistical, external, and engineering validity judgments, each with evidence;
- engineering feasibility table even when the result is `仅概念验证`;
- a minimum reproduction experiment with data, model, baseline, output, success condition, failure condition, work estimate, and file/code destinations;
- five-sentence synthesis, final scientific/method/engineering judgment, and actionable next tasks.

If these gates cannot be met because only selected sections were read, set `reading_status: 核心章节阅读`, `access_level: partial_text`, list exact coverage, and do not present the note as a complete full-text intensive read. Never inflate length with copied abstracts, repeated caveats, empty tables, or generic textbook material.

For `partial_text` core-section notes, do not collapse the template to a synopsis. Require:

- at least 7500 Chinese-character-equivalent body text excluding YAML and source ledger;
- at least five explicit claim–evidence judgments distributed across problem, data/method, validation, result and limitation;
- three selected evidence cards when usable source fragments exist, each with a paper-specific implication and unresolved check;
- a reconstructed argument chain and method mechanism, not only a list of model names;
- separate diagnoses of validation strength, alternative explanations, transferability and engineering feasibility;
- at least two paper-specific failure scenarios;
- a minimum discriminating experiment with hypothesis, split, comparator, outputs, success and failure conditions.
- at least three non-duplicate analytical items inside each of the data, method, validation and limitation modules;
- a result module containing every curated paper-owned finding supported by the inspected material, with no artificial minimum. A result card must analyze comparison, metric/error behavior, validation condition, hydrologic meaning and boundary. If no finding survives inspection, write a blocker and downgrade the note rather than filling R01–R03 with audit prose.

If evidence cannot support one of these modules, explain the missing material and its consequence for interpretation. Do not fill the space with generic checklist prose.

## Evidence anchors

Prefer:

1. PDF page plus figure/table/equation label;
2. figure/table/equation plus section;
3. section plus `Zotero:ITEMKEY/Attachment:KEY`;
4. `[待核验]` when no stable anchor exists.

MinerU page indexes can be zero-based. When numbering is uncertain, write `MinerU page index N（PDF页码待核验）`.

An evidence item never consists of navigation alone. For every item displayed in the note, also state:

- `证据内容`: original short excerpt or substantive Chinese analysis;
- `支持`: the exact claim the evidence can support;
- `边界`: what cannot be concluded from the selected passage.

Keep extraction line and paragraph numbers only in the authoritative machine JSONL. Before writing the note, convert every machine locator into content-based analysis. Before delivery, reject visible patterns such as `§…，L数字`, `抽取行 数字`, `段落编号 数字`, `原文证据卡（见……）`, and generic sentences such as “该段用于界定……” that do not name the paper-specific content.

Keyword-to-sentence conversion is also prohibited. Do not write `原文描述的方法链或组件涉及：A、B、C`, `当前可核验关键词为`, or the same support/boundary pair for multiple claims. Reconstruct what enters the model, what transformation or coupling occurs, what is predicted or decided, how it is tested, what the authors actually report, and where the inference stops. If a selected fragment is bibliography text, background-only text, or a metric definition rather than a study result, say so and do not promote it to evidence.

## Reading map

- Front matter and sections 1–4: identity, abstract, problem, definitions, study context.
- Sections 5–8: data, preprocessing, equations, models, experiments, uncertainty, sensitivity.
- Sections 9–12: results, figures/tables, discussion, limitations, transferability, validity.
- Sections 13–16: role relative to the user research question, conflict/support comparisons, reproducibility, final judgment, next actions.

Prefer precise `未报告` or `不适用` over decorative prose.

## Routing and filenames

- Save only to a destination explicitly supplied by the user or a clearly matching existing `文献/<category>/文献笔记/` or `文献/<category>/00_文献流转/文献笔记/`.
- If the destination is ambiguous, ask the user. Do not create, rename, or maintain a category or theme directory.
- Use `第一作者_年份_中文短题名.md`; append the Zotero item key only for collisions. Existing English filenames may be preserved during a non-destructive rerun, but their visible H1 and index alias must be Chinese.
- Search profiles and notes for DOI, fallback identity, Zotero key, and `paper_id` before writing.
- Never overwrite or silently revise an existing note.

## Batch deep reading

Create one note per selected paper. After drafting:

- Complete only the human-approved set. A quantity gate exists only when the current `input_manifest.expected_counts.core_deep_reads` or an explicit per-run count/ratio supplies it. With no gate, do not invent one.
- Approve papers only after five-dimension screening—theme relevance, representativeness, frontier, conflict/counterexample value, and evidence value—plus role-diversity review. Journal tier is context only.

- confirm identities and numeric claims are not mixed;
- use consistent terminology, units, horizons, and scales;
- add evidence-based support/conflict/complement comparisons only when both papers were actually read, without generating a theme map;
- create a synthesis note only when explicitly requested.
- run a structural check that all 16 major headings occur in order and the detailed-note completeness gate is met or explicitly downgraded.
