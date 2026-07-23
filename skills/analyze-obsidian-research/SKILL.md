---
name: analyze-obsidian-research
description: Read and synthesize an Obsidian research vault into source-traceable scientific problem clusters and a human-readable literature theme map, combining lightweight profiles, deep-reading notes, Zotero identities/full-text checks, literature claims, data, projects, and tasks. Use for 研究问题分析、文献问题簇、文献主题地图、主题图、近年进展、共识/冲突/缺口判断、项目与数据可行性映射, or archiving a research synthesis. Supports formal manifest-bound analysis and clearly labeled exploratory analysis; batch counts are parameters, never defaults. Produces Appendix A.2 cluster cards, deep paper-by-paper interpretations, a literature theme map, and machine-readable typed relations, and marks uncertain claims 待核验.
---

# Obsidian Research Analysis and Literature Theme Map

## Objective

Turn a research question into scientific problem clusters and a literature theme map that can be traced to literature identities, claims, lightweight profiles, deep-reading notes, Zotero records, datasets, projects and tasks. A problem cluster is named as a scientific question or contradiction, not as a model family or buzzword.

Never infer conclusions from filenames, equate “not found” with “no research”, or treat an abstract/AI summary as full-text evidence.

The theme map is a required synthesis layer whenever a run produces or updates more than one problem cluster. It must show how papers, problem clusters, validation constraints, local data, projects and tasks connect. A directory listing, keyword cloud or method-name grouping is not a theme map.

## Required reading

Before acting, read:

1. vault `AGENTS.md`;
2. `00_系统规则/平台目录与四技能路由映射.md`;
3. `00_系统规则/V0状态与证据规则.md`;
4. `references/vault-routing.md`;
5. `references/analysis-template.md`;
6. `references/problem-cluster.schema.json`;
7. `references/theme-relation.schema.json`;
8. `references/theme-map.schema.json`;
9. upstream manifest and core-candidate/evidence records when formal mode is requested.

## Modes

### Formal analysis

Formal mode requires exactly one valid `input_manifest` and one `source_batch_id`.

- analyze only literature included by the manifest;
- verify canonical IDs and source paths before synthesis;
- read optional expected quantities only from `expected_counts`;
- if counts/IDs/batch disagree, stop formal output and create a blocker record;
- do not silently broaden the corpus from vault-wide search results;
- downstream status remains `candidate` until the required human checks occur.

### Exploratory analysis

Use when there is no unique manifest or the user explicitly wants discovery.

- search the relevant vault scope and record the search boundary;
- label every output `analysis_mode: exploratory`;
- do not write into or replace the formal theme map;
- present clusters as hypotheses and use `待核验` where evidence is incomplete.

## Workflow

1. **Restate the scientific question.** Define target phenomenon, spatial/temporal scope and intended decision.
2. **Choose the mode.** Record manifest path and batch in formal mode, or the search scope in exploratory mode.
3. **Inventory before reading.** Use `scripts/inventory_vault.ps1` and exclude system/plugin/attachment/output directories.
4. **Route the question.** Map it to problem-cluster, data, project and task paths using `references/vault-routing.md`.
5. **Read sources in layers.** Prefer verified claim records and full-text notes; then profiles/abstracts; then project/data/task records. Preserve `evidence_status` and `review_status`.
6. **Extract claims.** Separate author conclusion, student judgment and AI summary. Every major statement gets `claim_id`, literature ID and location. Reject upstream `result` claims that are actually cited-study statements, metric definitions, methods, future work, evidence gaps, `待回查`, `未确认`, or “不能作为本文结果”. Require a paper-owned result finding plus source context and study condition; otherwise retain only a blocker and do not use it to support a cluster.
7. **Resolve visible sources.** For every used literature/data/project/task identity, resolve the complete title or file name and a DOI/publisher/Zotero/Obsidian link. IDs remain aliases only.
8. **Build paper interpretations before clusters.** For every paper used by a cluster, reconstruct the study object/data, method mechanism, validation design, paper-owned findings, interpretation, limitations/uncertainty and the exact reason it changes the cluster judgment. Do not reduce this to one sentence plus a relation label.
9. **Build clusters.** Group by shared scientific contradiction or unresolved validation need, not just shared method.
10. **Represent relations.** Use `supports`, `limits`, `conflicts`, `conditions`, `gap_signal`, and where needed `method_for` or `needs_verification`. Every relation must carry the paper interpretation used to justify it.
11. **Complete Appendix A.2.** Use `references/analysis-template.md`.
12. **Build the literature theme map.** Read the complete included manifest and inventory the relevant vault. Use every included paper either as a typed theme relation or in an explicit unmapped/pending-review ledger. Show cross-cluster dependencies, evidence coverage, local data/project/task availability and unresolved relation gaps.
13. **Write three synchronized layers.**
    - human-readable Markdown cluster cards in the established problem-cluster asset path;
    - `problem_clusters.jsonl` and typed relation JSONL/CSV for validation and graph use.
    - a human-readable theme map under `20_主题地图/<主题>/`, plus its machine-readable node/edge record when required by the run.
14. **Validate.** Run `scripts/validate_research_outputs.py` with `--theme-map` for a multi-cluster run; formal validation must fail when the manifest, named-source, paper-interpretation, theme-map, evidence-text, depth or traceability gate is missing.
15. **Report blockers.** Do not create a confident synthesis by filling absent evidence.

## Appendix A.2 gate

Each problem cluster must contain:

- a question-form cluster name;
- core contradiction;
- supporting evidence;
- limitations and conflicts;
- current consensus and its evidence grade;
- unresolved part classified as real conflict, validation gap, definition mismatch or missing material;
- China/team relevance;
- minimum additional evidence;
- `high`/`medium`/`low` confidence with reason;
- source trace: literature ID, claim ID, evidence status and reviewer.
- source trace: complete source title, source file/link, literature ID, claim ID, evidence text or analysis, location, evidence status and reviewer;
- at least two bounded “已解决/成立边界” statements, two unresolved statements, two testable hypotheses and one minimum-validation action when evidence supports them; otherwise explicitly record why the depth gate cannot be met;
- a `本次实际使用的来源` ledger listing every literature, data, project and task file by name and link.

No cluster may be `formal` solely because a model produced it.

### Cluster depth gate

A valid Appendix A.2 card is the contract header, not the whole analysis. For a corpus large enough to support synthesis, each detailed cluster file must additionally:

- compare at least six relevant papers by study object, data/scale, method mechanism, validation design, result and boundary; if fewer than six sources exist, explain the corpus limitation;
- contain a paper-by-paper evidence matrix and at least four explicit cross-paper comparisons or contradictions;
- separate performance improvement, hydrologic understanding, extrapolation reliability, uncertainty calibration and engineering value rather than treating them as one outcome;
- state at least three bounded resolved items, three unresolved items, three falsifiable hypotheses, two competing explanations and two minimum validation actions;
- explain why each source supports, limits, conflicts with or conditions the cluster claim;
- connect literature evidence to named local data, project and task files, or explicitly record that these local materials are absent;
- target 6000–12000 Chinese-character-equivalent body text excluding YAML and source ledger.

Depth is measured by distinct evidence and reasoning, not length alone. Repeated caveats, title lists, empty tables, method-name groupings and generic “需要进一步研究” prose fail the gate.

### Paper-by-paper interpretation gate

The `逐篇证据解读` module is the scientific core of a cluster, not a source list. For every paper represented by a typed relation:

- write separate content-bearing subsections for `研究对象与数据`, `方法机制`, `验证与比较`, `论文自身结果`, `对本簇判断的改变`, and `边界与待核验`;
- reconstruct the input–processing–output relation and identify the role of each component rather than listing model names;
- report zero to many paper-owned findings. Each finding must preserve the comparison, metric/error pattern, study condition, interpretation and boundary available in the source record;
- state how this paper differs from or complements at least one other paper in the same cluster;
- link the complete article title, profile and deep-reading note when available; include a Zotero link or Zotero audit entry when Zotero was queried;
- use a result blocker when no paper-owned finding survives inspection. Never turn the blocker, a method statement or a limitation into a result;
- avoid the stock form `证据分析：一句话` + `在本簇中的作用：supports` + repeated generic boundary. A bare relation code is never an explanation.

Do not impose a fixed number of papers per cluster. Validate all papers actually used by that cluster. When the corpus is too small for cross-paper comparison, state the exact corpus limitation instead of padding the list.

### Literature theme-map gate

A valid human-readable theme map must:

- state the formal manifest or exploratory search scope and the observed counts actually used;
- include all included literature identities: typed edges for papers used as evidence, and a named pending/unmapped ledger for the remainder;
- show problem-cluster nodes, literature nodes or ledgers, validation/decision axes, and named data/project/task nodes or explicit absence records;
- render cross-cluster dependencies as a Mermaid graph or an equivalent readable graph plus a relation matrix;
- explain each cluster with its scientific question, current bounded understanding, decisive evidence, main conflict, minimum validation and links to the full cluster files;
- distinguish `supports`, `limits`, `conflicts`, `conditions`, `gap_signal`, `method_for` and `needs_verification`;
- include a complete `本次实际使用的来源` ledger containing the manifest, analysis records, profile/deep-note indexes, cluster files, typed relations, Zotero checks and relevant vault files;
- remain `candidate` unless a mentor confirms it.

Reject a theme map that is only a list of topics, a keyword co-occurrence diagram, an unlinked Mermaid figure, or a copy of cluster titles. The map must make cross-source and cross-cluster reasoning visible.

## Output routing and preservation

Write detailed cluster analyses to the existing research asset path selected by the route map. Write the cross-cluster theme map and its validation artifact to `20_主题地图/<主题>/`. Never mass-migrate or overwrite existing assets. When a destination file exists, add a dated new analysis or update only with explicit authorization and a backup.

## Completion report

Report mode, manifest or search scope, included/excluded source counts, clusters created/updated, theme-map path, mapped and pending literature counts, relation counts by type, Zotero/full-text checks used, relevant data/project/task availability, evidence/review distribution, missing traces, validation result and items needing student/mentor action.
