# Evidence and routing rules

## Entry contract

- Formal Idea development consumes one manifest-bound Appendix A.2 problem-cluster set and its typed relations.
- An exploratory cluster can inspire a provisional note but cannot enter the formal candidate pool.
- Zero candidates is a valid result. Record blockers and the minimum evidence action instead of fabricating a direction.
- All candidates remain `candidate` and `waiting_for_mentor_decision`; no skill or model can promote them.

## Contents

1. Vault and target resolution
2. Evidence-source priorities
3. Nature-skill routing
4. Evidence ledger and links
5. Write safety

## 1. Vault and target resolution

Treat the active workspace as the default vault only when it contains `.obsidian/`. Otherwise use the explicit user path. Read applicable `AGENTS.md` files from the vault root down to the target.

Target rules:

- Topics containing `汛限水位`, `动态汛限水位`, `flood limit water level`, or an unambiguous synonym route to `任务/汛限水位动态控制试点/03_选题管理`.
- Other topics first search immediate task-project directories for the same research object and decision goal.
- If no task project matches, propose `任务/<规范化主题>试点/03_选题管理`.
- Create only missing directories needed for the target. Do not create empty mirror directories under literature, data, or projects.
- Store Idea files directly in `03_选题管理` unless an existing local taxonomy clearly requires a subcategory.
- Store the cross-theme comparison view in `40_选题池/`. This is the platform-control view for ranking, veto checks, and mentor comparison; it is not a substitute for the detailed Idea files.
- A formal non-zero run is incomplete until both layers exist and point to one another:
  - `任务/<项目>/03_选题管理/`: full Idea analysis, data needs, risks, minimum validation, and next tasks;
  - `40_选题池/`: concise cross-theme ranking, fatal gates, decisive evidence/unknowns, and links to the full analyses.

When a target already contains decision records or Idea cards, read them before writing. Preserve their naming conventions where compatible, but never let a short existing card reduce the mandatory completeness of the new Idea analysis.

When regenerating after new evidence or a skill revision, write a new versioned run. Preserve prior zero-direction records, mentor decisions, and Idea cards as dated history. The new pool must identify the superseded run assessment without rewriting that history.

## 2. Evidence-source priorities

### Literature and problem clusters

Start with `文献/<主题>/文献问题簇/`. Read cluster descriptions, most recent analyses, linked literature cards, deep-reading notes, and exact source anchors. Problem-cluster files can establish the team's current framing but do not replace checking a cited paper.

Use literature evidence to assess:

- what has been solved and under what boundary;
- what remains disputed or untested;
- closest competing papers and whether the Idea is duplicate work;
- which mechanism, scale, data, validation, uncertainty, or engineering gap is real.

### Data

Read metadata before values: data dictionary, provenance, ownership, format, variables, units, resolution, temporal coverage, missingness, version, quality control, license, and reproducible loader. Separate:

- `已有`: present and accessible now;
- `可获得`: credible acquisition route, owner, and time;
- `缺失`: required but no current route.

Do not claim statistical power, correlation, mechanism, or model performance without running the corresponding analysis.

### Projects

Use project files to determine available study sites, collaborators, instrumentation, models, expected deliverables, permissions, engineering constraints, and schedule. A project plan supports feasibility, not an academic conclusion.

### Tasks and decisions

Read existing Ideas, scientific-question trees, minimum validations, status trackers, meeting notes, and mentor decisions. Treat recorded decisions as internal evidence with date and owner. Identify conflicts between desired paper scope and current resources.

Read the current `40_选题池/` before ranking. A pool entry may be `accepted`, `reserve`, or `rejected`, but its knowledge identity remains `candidate` and its decision remains `waiting_for_mentor_decision`. Pool-only reserve or rejected directions do not require a full Idea file, but they must name their evidence, fatal gate, minimum reopening action, and next owner/action.

### User information

Label each input as `[用户问题]`, `[用户建议]`, `[用户事实]`, or `[用户假设]`. User information can define scope and priorities but does not independently prove a literature or data claim.

## 3. Nature-skill routing

Use local evidence first. Select only the missing external capability:

| Need | Skill | Required output |
|---|---|---|
| recent/closest papers | `nature-academic-search` | search strategy, deduplicated records, relevance and source provenance |
| full-paper support | `nature-reader` | exact section/page/figure/table-aware evidence and limitations |
| identity/DOI conflict | `nature-ref-verifier` | field-level status and authoritative sources |
| support major claim | `nature-citation` | verified source attached to the exact claim |
| paper argument design | `nature-writing` | terminology ledger, one-sentence argument, claim–evidence map, section map |
| validation/statistics | `nature-statistics` | estimand, design, uncertainty, sensitivity, reporting gaps |

Do not use external search to upload or expose private vault material. Search with abstracted public concepts only.

## 4. Evidence ledger and links

For every used source, record:

- stable ID (`L`, `D`, `P`, `T`, or `U` prefix);
- complete article title or file name;
- vault-relative path or DOI/direct source URL;
- exact section, page, table, field, variable, decision date, or status used;
- role in the Idea;
- evidence label and verification status;
- limitation.

Use Obsidian links relative to the vault root:

```markdown
[[数据/实测/数据说明|实测数据说明]]
[[项目/某项目/项目总览|项目总览]]
[[任务/某试点/04_最小验证/方案|最小验证方案]]
```

List only sources actually read and used. “Discovered but unread” materials belong in a separate follow-up list, not the evidence ledger.

The visible label must be the complete name with a usable link. An ID may appear in a separate technical column, but an ID-only row is invalid. When a source supports a judgment, include a short evidence excerpt or substantive analysis; a page/section/line locator alone is insufficient.

## 5. Write safety

- Resolve the final absolute target and require it to remain inside the vault.
- Do not overwrite existing Ideas, mentor decisions, project notes, task states, literature notes, or source data.
- Do not modify problem-cluster files merely to make an Idea appear supported.
- If creating a missing category, create only the target directory chain and report it.
- When a user requests revisions to an existing Idea, preserve a version trail or obtain explicit overwrite authorization.
- Never promote a direction because it ranks first. Until a dated mentor decision is recorded, detailed Ideas use `candidate` and the pool uses `V0临时判断`.
- Keep status synchronized: every accepted pool entry must resolve to a detailed Idea whose `idea_id`, recommendation, score, fatal gates, and next actions match the machine records.
