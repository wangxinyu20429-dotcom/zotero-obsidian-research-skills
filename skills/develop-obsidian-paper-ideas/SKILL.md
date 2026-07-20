---
name: develop-obsidian-paper-ideas
description: Read an Obsidian research vault—prioritizing literature problem clusters, datasets, projects, and tasks—combine the user's research prompt with relevant Nature academic skills, evaluate paper ideas for value, novelty, feasibility, methods, risks, and publishable contribution, then create one source-traceable Markdown document per Idea in the matching task project's 03_选题管理 directory, creating the directory when missing. Use for 论文 Idea 分析, 博士选题建议, 汛限水位选题, 研究构想筛选, 选题可行性, Idea 对比排序, or requests to archive evidence-backed paper ideas into Obsidian.
---

# Develop Obsidian Paper Ideas

Turn a user prompt into testable, evidence-backed paper ideas. Answer five questions for every Idea: why it matters, what exactly to study, why it is feasible, how to do it, and what publishable contribution it can produce.

## Required reading and routing

1. Read the vault's applicable `AGENTS.md` completely.
2. Read [references/evidence-and-routing.md](references/evidence-and-routing.md) before inventorying the vault or choosing a target directory.
3. Read [references/idea-document-spec.md](references/idea-document-spec.md) completely before drafting; preserve every mandatory section.
4. Read [references/quality-gates.md](references/quality-gates.md) before scoring or recommending an Idea.
5. Use `analyze-obsidian-research` when a literature problem cluster needs a fresh source-traceable synthesis before Idea selection.
6. Invoke only the minimum relevant Nature skills: academic discovery, full-text reading, reference verification, citation support, paper argument design, or statistics. Read each selected skill's `SKILL.md` first.

Keep unpublished papers, internal project material, private data, and vault content local. Use external services only for public literature discovery and verification, following `web-access`.

## Workflow

### 1. Parse the request

Separate the user's problem, suggestion, facts, assumptions, constraints, expected paper type, study object/region, and desired number of Ideas. If the user gives no count, develop 1–3 materially distinct Ideas rather than superficial variants.

Compute the inclusive recent-five-year window from the current year and record it explicitly. Do not treat earlier seminal work as recent progress.

### 2. Resolve the target

Run the bundled resolver in dry-run mode:

```powershell
python scripts/idea_vault_inventory.py resolve-target --vault-root "<vault-root>" --topic "<topic>"
```

For 汛限水位/动态汛限水位 topics, use `任务/汛限水位动态控制试点/03_选题管理`. Otherwise select the matching `任务/<研究项目>/03_选题管理`. If no matching task project or category exists, create the narrowest justified `任务/<规范化主题>试点/03_选题管理` only when writing is authorized:

```powershell
python scripts/idea_vault_inventory.py resolve-target --vault-root "<vault-root>" --topic "<topic>" --create
```

Confirm that the resolved absolute path remains inside the vault. Do not repurpose a loosely related project directory.

### 3. Inventory evidence before prose

Run:

```powershell
python scripts/idea_vault_inventory.py inventory --vault-root "<vault-root>" --keyword "<关键词1>" --keyword "<关键词2>"
```

Prioritize, in order:

1. `文献/*/文献问题簇/` descriptions, analyses, literature cards, and deep reading notes;
2. `数据/` schemas, variables, spatiotemporal coverage, quality notes, and reproducible entry points;
3. `项目/` objectives, methods, deliverables, data rights, collaborators, and constraints;
4. `任务/` decisions, status, dependencies, minimum validation, meeting records, and existing Ideas;
5. `论文产出/` only when it contains relevant claims, outlines, or journal boundaries.

Use the inventory only for discovery. Read the relevant source text before citing it. Never infer content or quality from filenames.

### 4. Build the evidence ledger

Record only materials actually read and used. Distinguish:

- literature evidence and exact source anchor/DOI;
- data existence, fields, scope, quality, access, and limitations;
- project capability, delivery, permissions, and engineering constraints;
- task status, decisions, dependencies, deadlines, and termination conditions;
- user-provided questions, suggestions, facts, and assumptions.

Use `[原文]`, `[AI概括]`, `[科研判断]`, `[导师确认]`, and exact text `待核验`. “Not found in the current search” is not a research gap.

### 5. Develop and screen candidate Ideas

Generate distinct candidates around different scientific questions, data leverage, mechanisms, methods, or engineering decisions. Reject candidates that are merely renamed duplicates, simple region substitutions without new knowledge, or method piles without a coherent paper argument.

For each candidate, verify:

- 2–4 testable scientific questions map to result sections;
- hypotheses can be supported or falsified;
- existing/obtainable/missing data are separated;
- the minimum validation can eliminate a weak Idea quickly;
- the closest 5–10 studies are compared when evidence allows;
- novelty is stated relative to checked prior work;
- risks have backups and explicit termination gates;
- expected contribution is a claim, method, dataset/product, mechanism, or engineering decision—not workload.

### 6. Use external academic skills only for identified gaps

- `nature-academic-search`: discover recent representative and closest competing papers.
- `nature-reader`: inspect full text, figures, tables, methods, limitations, and exact support.
- `nature-ref-verifier`: verify author order, title, year, journal, pages/article number, and DOI.
- `nature-citation`: attach verified sources to major claims.
- `nature-writing`: construct the one-sentence argument, terminology ledger, paragraph/section map, and claim–evidence map.
- `nature-statistics`: audit validation, sensitivity, uncertainty, sample size, and statistical reporting plans.

Do not invent journal metrics or claim a source supports a statement without checking the relevant content.

### 7. Write one file per Idea

Use the complete template in [references/idea-document-spec.md](references/idea-document-spec.md). Default filename:

```text
Idea_YYYY-MM-DD_<简短题名>.md
```

For multiple Ideas, also create `Idea_YYYY-MM-DD_<主题>_候选索引.md` containing only ranking, links, decisive evidence, shared dependencies, and next decision. Do not merge full Idea analyses into the index.

Before writing, compare normalized title, core question, and YAML `idea_id` with existing files. Never overwrite or silently update an existing Idea. Use `_02`, `_03`, or ask whether to revise when the substantive Idea already exists.

### 8. Verify delivery

Reread every created file and confirm:

- it is inside the resolved `03_选题管理` directory;
- all 16 mandatory analytical sections and the actual-source appendix exist;
- major judgments have evidence or `待核验`;
- literature, data, project, and task sources are listed with vault-relative Obsidian links;
- the score and recommendation follow [references/quality-gates.md](references/quality-gates.md);
- no source literature, raw data, project file, or existing Idea was modified.

Report each created absolute path, the target project/category created if any, the main evidence used, decisive unknowns, and the recommended next minimum validation.

## Bundled utility

`scripts/idea_vault_inventory.py` is read-only except `resolve-target --create`, which creates only the resolved target directory inside the vault. It never edits evidence or Idea files.
