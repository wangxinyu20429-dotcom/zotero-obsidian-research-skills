---
name: zotero-hydrology-notes
description: Search OpenAlex for hydrology literature, deduplicate against local Zotero, retrieve lawful open-access full text, create source-traceable lightweight profiles, screen core-paper candidates with Appendix A.1 fields, and create Chinese full-text reading notes without treating AI traversal as human verification. Use for OpenAlex 文献检索、Zotero 去重、文献画像、核心文献筛选、全文审计、中文精读笔记 and MinerU workflows in hydrology, water resources, hydraulic engineering, or basin forecasting. Batch sizes and deep-reading targets are optional manifest parameters, never fixed defaults. This skill does not create theme maps or paper ideas.
---

# Zotero Hydrology Notes

## Objective and boundary

Use Zotero as the local bibliographic authority and Obsidian as the profile, evidence, candidate-card and reading-note layer. Search/public APIs may receive search terms and public identifiers only. Never upload local papers, unpublished material, internal reports, attachments or Zotero library data.

This skill stops at literature identity, evidence, profiles, Appendix A.1 core-paper candidates and reading notes. Route problem-cluster synthesis to `analyze-obsidian-research`; route paper directions to `develop-obsidian-paper-ideas`.

## Required reading

Before acting, read:

1. vault `AGENTS.md`;
2. `00_系统规则/平台目录与四技能路由映射.md` when present;
3. `00_系统规则/V0状态与证据规则.md` when present;
4. the relevant workflow under `references/`;
5. `references/appendix-a1-core-candidate.md` for core selection;
6. `references/input-manifest-contract.md` for formal batches;
7. the actual vault note template before creating intensive-reading notes.

The vault state contract is authoritative. Without it, formal mode is unavailable; only exploratory/candidate output may be produced.

## Modes

### `exploratory`

Use when the user is browsing Zotero, trying a query, building a provisional profile or has no unique `input_manifest`.

- label outputs `mode: exploratory` and `knowledge_status: candidate`;
- do not claim batch completeness;
- do not create a formal core set;
- counts are observed results, not targets.

### `formal`

Use only when exactly one `input_manifest` identifies the batch and its included literature.

- verify `manifest_version`, `source_batch_id`, item identities and source paths;
- read optional targets only from `expected_counts`;
- a missing expected count means no quantity gate;
- a mismatch blocks formal downstream output and must be recorded;
- never insert historical test counts or an empirical percentage as a fallback.

## Stable identity and compatibility

Every new machine record and new Markdown frontmatter should include:

- `canonical_literature_id`;
- `source_batch_id`;
- `doi_normalized`;
- `title_normalized`;
- `source_path`;
- `selection_status`;
- `evidence_status`;
- `review_status`;
- `knowledge_status`.

Keep `paper_id`, Zotero item key, OpenAlex ID, `access_level` and `review_level` when already used. They are compatibility aliases, not competing authorities. A suspected duplicate/version is `selection_status: duplicate` or `unknown` until a person resolves it; never auto-merge or overwrite.

## Evidence and review

`evidence_status` describes material actually checked; `review_status` describes human review. They are independent.

- metadata import → `metadata_only` + `unverified`;
- abstract read → `abstract_only` + the actual review state;
- OCR/MinerU/LLM traversal without human verification → at most `partial_text` + `unverified`;
- `full_text_main` requires a student to check the decisive context, methods, results and limitations;
- `full_text_with_supplement` also requires the relevant supplement;
- scripts and models never upgrade `review_status`, `knowledge_status`, or mentor decisions.

Author conclusion, student judgment and AI summary must remain separate. Every formal claim needs a source location.

A location is navigation, not evidence. In human-facing profiles and reading notes, do not display extraction line numbers, paragraph numbers, MinerU line indexes, or placeholders such as `§结果，L145` and `原文证据卡（见……）`. Keep those technical offsets only in the authoritative machine JSONL. A useful section, figure, or table name may be retained only as secondary navigation after the source content has been explained. Every visible evidence item must lead with either:

- a bounded original excerpt sufficient to understand what the anchor contains; or
- a substantive Chinese analysis that states what the source says, what it supports, and what it does not establish.

Also display the complete article title and at least one usable article/Zotero/profile link. Bare `paper_id`, claim ID, section label, paragraph number, or line number is never an acceptable visible source label. Human-facing validation must fail when visible prose still contains extraction locators or generic phrases that merely promise evidence elsewhere.

### Substantive-analysis gate

Do not let a token extractor, keyword scorer, regex, or template author scientific interpretation. Scripts may select source candidates and assemble validated fields, but a profile or deep note may be written only after a paper-specific synthesis record has been created from the inspected source.

Reject an analysis when any of the following is true:

- it inserts a keyword list into a sentence such as `涉及：A、B、C` or `可核验关键词为`;
- it says only that a passage describes a problem, method, result, limitation, or uncertainty;
- it repeats the same support/boundary sentence across unrelated evidence items;
- it names a model without reconstructing its role in the input–processing–output chain;
- it reports a result without its comparison object, condition, metric, or an explicit `未从当前证据确认`;
- it uses absence of an extracted snippet as proof that the paper did not report something.

For every paper, require distinct, content-bearing analysis of the research problem, data/design, method chain, validation, findings, limitations, uncertainty/robustness, engineering meaning, research judgment, and a minimum verification or reproduction task. State source conflicts and bibliography contamination explicitly. If these fields cannot be completed from inspected evidence, produce a blocker instead of a polished profile.

### Within-module depth and research-judgment gate

Passing the substantive-analysis gate is necessary but not sufficient. Do not respond to a thin analysis by adding more headings. Depth must primarily be added inside the scientific modules.

- Build an argument chain connecting problem → data/scale → method mechanism → validation → result → boundary. Do not render the ten synthesis fields as isolated one-paragraph answers.
- In the data, method, validation and limitation modules, require at least three non-duplicate paper-specific analytical items. Do not impose a minimum count on reported results.
- The result module accepts zero to many paper-owned findings. A finding is valid only when the paper's own results, table/figure text, discussion of its experiment, or conclusion cross-check reports an observation. Store `finding`, `source_context`, `comparison`, `metric_observation`, `study_condition`, `interpretation` and `boundary`; use `analysis` when interpretation and boundary are combined.
- Never label a cited study, background statement, metric definition, method description, future work, evidence audit, `待回查`, `未确认`, or `不能作为本文结果` as a result. Put these in `result_blockers` or another scientific module.
- If no paper-owned finding survives full-text inspection, render one explicit result-evidence blocker and mark the profile incomplete. Do not add conditions, engineering interpretations or limitations as `R02/R03`.
- Each result item must answer as many of these as the source permits: what changed, against what, under which sample/split, by which metric, in which flow regime or basin, and what the observed error pattern means.
- Method detail must separate inputs, transformations/components, component roles, outputs and the ablation needed to identify each contribution. Validation detail must separate data split, baseline fairness, metrics, leakage risk and extrapolation strength.
- Distinguish at least four levels: what the authors tested, what the evidence supports, which alternative explanation remains possible, and what transfer or reproduction would require.
- Add three source-grounded evidence cards when usable fragments exist. Each card must contain a bounded excerpt or paper-specific Chinese analysis, its scientific implication, and an unresolved check. Exclude bibliography, generic background and metric-definition fragments.
- Reconstruct study object, period/scale when available, target, inputs, preprocessing, model/component roles, outputs, baselines, split design, metrics and operational information timing. Write `未从当前证据确认` for missing elements.
- Evaluate internal, construct, statistical, external and engineering validity separately. A status-only table or repeated caution sentence does not count.
- Explain at least two plausible failure modes or competing explanations using the paper's actual data, model or validation setting.
- End with a discriminating experiment containing hypothesis, data, comparator, split, outputs, success criterion and failure criterion.

A lightweight profile must provide within-module depth before adding optional modules and target 3000–5500 Chinese-character-equivalent body text excluding YAML and the source ledger. A partial-text deep note must preserve the 16 major template sections, include at least five claim/evidence judgments and three source-grounded evidence cards when available, and target at least 7500 Chinese-character-equivalent body text. Length and heading count never excuse a module that still contains only one compressed result sentence, repetition, copied source text, empty tables or generic hydrology advice.

## Workflow

1. **Confirm scope.** Record the research question, mode, manifest path if formal, and whether the task is search, profile, A.1 screening or deep reading.
2. **Probe Zotero read-only access.** Prefer the Zotero plugin/local API. Do not modify Zotero unless the user separately asks.
3. **Resolve identities.** Normalize DOI and title, reuse a canonical ID, record aliases and possible duplicates.
4. **Search or collect.** Follow `references/openalex-workflow.md` or `references/profile-workflow.md`. Deduplicate before downloading.
5. **Build lightweight profiles.** Use `scripts/profile_pipeline.py`. Do not fill full-text-only fields from metadata/abstracts.
6. **Audit full text.** Follow `references/quality-gates.md`. Record source coverage and gaps; access is not verification.
7. **Screen core candidates.** Use the five dimensions as decision support and complete Appendix A.1. Scores never replace a written selection reason.
8. **Deep read only the authorized set.** An explicit count or ratio may come from the current manifest/command. If neither exists, do not auto-approve items.
9. **Synthesize before rendering.** Create or review one paper-specific synthesis record per included paper. Add structured source coverage and selected evidence cards, then build the cross-field argument chain and validity diagnosis. Never derive the synthesis by inserting extracted keywords into stock sentences.
10. **Render human evidence.** Use `scripts/rebuild_substantive_notes.py` with explicit `--analysis-records` and independently curated `--result-findings` JSONL files after one reviewed synthesis record exists for every included paper. The renderer rebuilds the complete profile or deep note from paper-specific analysis, replaces visible extraction-location labels and generic evidence placeholders, and writes a named source ledger with links. `scripts/enrich_human_evidence.py` is legacy-only and must fail when no reviewed custom analysis exists; it must never fall back to keyword-derived prose. Extraction line numbers remain only in machine records.
11. **Write safely.** Default to new files or skip existing files. Overwrite requires explicit authorization and a backup.
12. **Validate.** Run the relevant script validation, the substantive-analysis scan, and `scripts/validate_bundle.py`.

## Appendix A.1 gate

A core-paper candidate is valid only if it records:

1. literature identity;
2. which part of the test question it answers and its relation to cross-basin, ungauged or generalization issues;
3. a substantive selection reason;
4. evidence role;
5. research design;
6. evidence and review status plus full-text/figure/supplement availability;
7. intended downstream use;
8. final treatment: `approved_for_deep_read`, `deferred`, or `excluded`, with reason.

Selection can remain `deferred`. Model score alone cannot set `approved_for_deep_read`.

## Output routing

- existing research assets remain under `文献/` or the skill's established asset paths;
- machine profiles/evidence/core tables remain under `10_文献知识/`;
- platform summaries and validation records remain under the mapped control-layer paths;
- never move existing assets solely to make the platform tree look uniform.

## Human-readable source gate

Every generated profile, deep-reading note, evidence index and core-candidate companion must include `本文件实际使用的来源` or an equivalent source ledger. For each used item, show:

- the complete article or file name;
- a DOI/publisher, Zotero, or Obsidian link;
- the source role in this file;
- evidence/review status;
- an evidence excerpt or analysis when the item supports a scientific statement.

Identifiers may remain as technical aliases, but never replace names and links.

## Completion report

Report mode, manifest, observed counts, any manifest expectations, written/skipped files, identity conflicts, evidence/review distribution, A.1 completeness, validation result and unresolved human decisions.
