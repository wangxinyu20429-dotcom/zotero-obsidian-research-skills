# Evidence and routing rules

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

When a target already contains decision records or Idea cards, read them before writing. Preserve their naming conventions where compatible, but never let a short existing card reduce the mandatory completeness of the new Idea analysis.

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

## 5. Write safety

- Resolve the final absolute target and require it to remain inside the vault.
- Do not overwrite existing Ideas, mentor decisions, project notes, task states, literature notes, or source data.
- Do not modify problem-cluster files merely to make an Idea appear supported.
- If creating a missing category, create only the target directory chain and report it.
- When a user requests revisions to an existing Idea, preserve a version trail or obtain explicit overwrite authorization.
