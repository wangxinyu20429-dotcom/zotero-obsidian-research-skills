# Lightweight profile workflow

## Purpose

A profile supports screening, evidence-bounded comparison, navigation, journal observation, and core-paper selection. It is not a full reading note and must not repeat the schema or a complete run log.

## Separated records

Keep each concern in one place:

| Record | Location | Contains | Must not contain |
|---|---|---|---|
| Schema | `10_文献知识/paper_profile.schema.json` | field contract | paper records |
| OpenAlex discovery batch | `10_文献知识/sources/openalex/<batch-id>/` | query, candidates, duplicate decisions, download manifest | API key, PDF copies, scientific conclusions |
| Batch/source list | `10_文献知识/sources/batches/` | query, keys, identifiers, dedup status | scientific conclusions |
| Profile JSONL | `10_文献知识/profiles/` | one compact paper profile per line | full run logs, PDF copies |
| Run log | `10_文献知识/runs/` | command, time, input, output, counts, versions | profile prose |
| Failure record | `10_文献知识/errors/` | stage, item, cause, action, status | silently dropped items |
| Quality check | `10_文献知识/quality/` | checked fields and corrections | unchecked assumptions |
| Core selection | `10_文献知识/core/` | question-relative scores, roles, status | theme maps |
| Evidence index | `10_文献知识/evidence/` | selected full-text anchors and note links | original PDF |
| Obsidian companion/navigation | beside each machine record and `10_文献知识/<batch-id>_Obsidian导航.md` | human-readable Markdown tables/cards and wikilinks | replacement for authoritative CSV/JSONL |

## Identity and deduplication

1. Normalize DOI by lowercasing and removing `https://doi.org/`, `http://doi.org/`, and `doi:` prefixes.
2. When DOI exists, reuse the matching `paper_id`.
3. Without DOI, compare normalized title + year + first author. Normalize titles with Unicode NFKC, lowercase, collapsed whitespace, and punctuation removal.
4. Record preprint/version-of-record relations explicitly. Do not double count a preprint and the published version merely because their item keys differ.
5. Keep Zotero top-level key separate from attachment key and BibTeX citekey.
6. Do not copy PDFs into the vault. Use `zotero://select/library/items/<KEY>` and the deep-note link.

## Required profile fields

Follow `paper_profile.schema.json`. Every object contains all fields; unavailable scalar fields use `null`, and unavailable repeated fields use `[]`.

- Identity: `profile_version`, `paper_id`.
- Bibliography: `title`, `authors`, `year`, `venue`, `doi`, `url`, `journal_tier`.
- Evidence state: `access_level`, `review_level`, `confidence`.
- Problem: `research_problem`, `forecast_target`, `forecast_horizon`.
- Scale: `spatial_scale`, `temporal_resolution`, `study_region`.
- Study: `datasets`, `methods`, `baselines`, `metrics`.
- Understanding: `main_findings`, `claimed_innovations`, `limitations`.
- Organization: compatibility field `candidate_themes`, plus `provenance` and `notes`.

Target 3000–5500 Chinese-character-equivalent useful body content, not boilerplate. A completed profile requires traversal of the whole available MinerU full text; the abstract is only one evidence section. If full text is missing, create a blocker/stub outside the completed-profile index rather than an abstract-only profile.

## Evidence levels

Set `access_level` to the strongest source actually read:

- `metadata`: bibliographic record only.
- `abstract`: abstract read; conclusions are abstract-reported claims.
- `partial_text`: one or more identifiable full-text sections/fragments read, but coverage is incomplete. Record section/page/paragraph coverage in provenance and `notes`.
- `fulltext`: the complete article was read with auditable section/page or figure/table anchors.
- `project_material`: internal project material read; do not make it public.
- `secondary_web`: a secondary page read; do not treat it as the paper.

Do not upgrade to `partial_text` or `fulltext` because a PDF attachment exists. Use `partial_text` for identifiable but incomplete article coverage; an abstract, indexed snippet, or metadata page remains `abstract`, `secondary_web`, or `metadata` as applicable.

Set `review_level` independently:

- `auto_extracted`: machine/AI output not yet checked.
- `student_checked`: one person checked identity and claims against the available source.
- `cross_checked`: another person independently checked the required fields.
- `mentor_confirmed`: the mentor explicitly confirmed the judgment.

## Field boundaries

- `research_problem`: the problem the paper states or clearly addresses; use `null` when metadata cannot establish it.
- `forecast_target` and `forecast_horizon`: record only explicit targets/horizons.
- `datasets`, `baselines`, `metrics`: do not infer typical datasets or metrics from the method name.
- `main_findings`: label abstract-derived items in the wording, for example `摘要报告：...`.
- `claimed_innovations`: author claims, not the profiler's novelty judgment.
- `limitations`: leave empty when the available evidence does not report them.
- `confidence`: confidence in profile extraction, not paper quality or conclusion truth.
- `notes`: compact evidence boundary, Zotero key relation, version relation, and unresolved conflicts; not a run log.

## Compatibility field

The project Schema retains `candidate_themes` for compatibility with older records and other skills. This skill does not perform theme discovery or classification:

- write `candidate_themes: []` in new profiles;
- preserve but do not interpret existing user-authored values;
- do not create candidate categories, relation tables, theme cards, problem clusters, or paper ideas;
- use the user-supplied research question only for sample selection and core-paper scoring.

## Provenance

Every non-empty claim group needs at least one provenance entry with:

- `source_type` matching the source actually read;
- a stable locator such as Zotero key, DOI, section, page, table, figure, or local note link;
- `retrieved_at` in ISO 8601 date format when available.

Do not paste long abstracts or copyrighted text into profiles. Paraphrase compactly and preserve the evidence boundary.

In human-facing Markdown, provenance must have semantic content. A bare location such as `全文相关章节`、`第 123 行`、`Front matter` or `§3.2` is invalid by itself. Render each selected anchor as an evidence card containing:

1. the complete linked article title;
2. a short original excerpt or a paper-specific Chinese analysis;
3. what the excerpt supports;
4. what remains unsupported or needs review;
5. an informative section, figure, or table name only as optional secondary navigation.

When retaining English source text, limit each excerpt to at most 8 words and at most three excerpts per paper in the human Markdown. Pair it with `中文分析（AI概括）`. Longer source text, paragraph numbers, page-extraction offsets, and line numbers remain only in the authoritative machine evidence record. Human-facing Markdown must not expose `L145`, `抽取行 145`, a paragraph number, claim ID, `全文相关章节`, `原文证据卡（见……）`, or any other locator as if it were evidence.

## Obsidian-readable companions

- Keep CSV/JSON/JSONL for scripts, but never make them the only human-facing deliverable.
- Run `scripts/obsidian_companion.py --vault-root <root> --batch-id <batch>` after profiles, source inventory, core selection, failures, and quality records are final.
- Write UTF-8 Markdown with YAML frontmatter, descriptive headings, compact tables or cards, evidence/review labels, and Obsidian wikilinks.
- Split the Obsidian reading surface into one Markdown file per paper and one index note. For machine-learning/deep-learning hydrological forecasting, use `10_文献知识/profiles/机器学习水文预报/`; keep any parent-level legacy note as a navigation stub only.
- Link all companions and deep notes from one batch navigation note.
- Check for `�`, mojibake, broken tables, unresolved note links, and machine-specific paths presented as user navigation.
- An Obsidian companion is a view, not a second scientific record. Do not introduce claims that are absent from its authoritative machine source.
- Use the complete article title as the visible heading and link it to the DOI/publisher page; add a Zotero deep link. Do not expose `paper_id` or item keys as the human-facing paper label.
- The index must show the complete article title as the Obsidian link alias and provide the article-page link. Deep-reading notes must link directly to the corresponding individual profile file, not to a batch heading anchor.
- Render each profile as a substantive 3000–5500 Chinese-character-equivalent full-text screening analysis. Prioritize depth inside data, method, validation and limitation: each must contain at least three non-duplicate paper-specific analytical items. Result count is evidence-driven and has no minimum. Include full-text coverage; research proposition; argument chain; data/period/scale/sample design; method mechanism; inputs/outputs; baselines/metrics; validation and leakage audit; selected evidence cards; individually interpreted findings; claimed versus actual contribution; alternative explanations; limitations/conflicts; uncertainty/extremes/robustness; five validity dimensions; physical/engineering value; reproduction conditions; five-dimension screening evidence; and human-review tasks.
- In the result module, render only curated paper-owned findings. For each finding, state the result, comparison or reference condition, metric/error pattern, validation context, hydrologic interpretation and boundary when the source permits. Never split punctuation automatically or borrow validation, engineering, limitation or audit prose to inflate the finding count.
- Treat depth as reasoning density. Each module must add a paper-specific fact, connect two evidence fields, test an inference, or define a verification action. Repeating the same synthesis sentence under several headings, adding empty template tables, or listing generic leakage/engineering checks fails the profile even if the character target is met.
- Add `本文件实际使用的来源`. List the complete article title, DOI/publisher link, Zotero link, authoritative profile/evidence record name, input-manifest name, and deep-note link when present. Do not show only IDs.
- Require evidence from methods, results, discussion/limitations, and availability in addition to abstract/introduction. Store extraction line/paragraph/page offsets in the authoritative full-text profile record only; human companions may retain useful section/figure/table names after content-based analysis.
- Reject a companion when most profile cards repeat identical prose or when the paper-specific portion is too short to support a core-reading decision.
- Reject any profile that converts extracted tokens into prose, including `涉及：关键词列表`, `当前可核验关键词为`, `论文提出了这一问题`, `方法存在不等于性能提升`, or equivalent stock wording. Candidate extraction is a navigation step; it is not synthesis.
- Before rendering, require a paper-specific synthesis record with distinct fields for problem, data/design, method chain, validation, findings, limitations, uncertainty/robustness, engineering meaning, research judgment, and minimum reproduction. Each field must name the actual study object or evidence condition. Missing fields become explicit blockers, never keyword-filled sentences.
- Default every visible paper label, heading, status, synthesis, evidence explanation, and section locator to Chinese. Store the exact original title in YAML `title_original` and machine records; use the Chinese translated title as the visible H1 and index alias.
- Preserve long raw English evidence only in the authoritative machine JSONL. Human Markdown may show a bounded original excerpt under the 8-word/three-excerpt gate, followed by `中文分析（AI概括）`; it must not claim that the analysis is a verbatim translation. Retain standard dataset/model names, acronyms, symbols, formulas, units, authors, journal names, DOI, and URLs in their authoritative form.
- Reject a companion whose visible body contains a raw English abstract, caption, result paragraph, or another long English sentence. When no reliable local translation is available, provide a bounded Chinese explanation plus the exact source anchor and require human review.
- Maintain `10_文献知识/sources/<batch-id>_中文题名映射.json` for deterministic batch reruns. Missing Chinese titles are blocking errors, not permission to fall back to English visible labels.

## Quality sampling

- Structural required-field presence must be at least 90%.
- For a pilot smaller than 10 papers, check every profile; otherwise randomly sample at least 10.
- A second checker verifies title, year, DOI, task, method, main finding, and evidence level.
- If more than two checked papers contain key-field errors, revise the rule and rerun the sample.
- Record all failures and corrections; do not delete failed papers silently.
