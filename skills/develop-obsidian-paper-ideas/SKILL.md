---
name: develop-obsidian-paper-ideas
description: Read an Obsidian research vault and turn a manifest-bound theme map, verified problem clusters, literature claims, datasets, projects, and tasks into zero to three falsifiable paper-direction candidates, or explicitly conclude that no candidate should be formed. Use for 论文 Idea 分析、博士选题建议、研究构想筛选、选题可行性、Idea 对比排序, 40_选题池汇总, or archiving evidence-backed directions. Produces synchronized Appendix A.3 detail files under 任务/<项目>/03_选题管理/ and a cross-theme comparison and veto view under 40_选题池/; every direction stays candidate/V0临时判断 and waiting for mentor decision.
---

# Develop Obsidian Paper Ideas

## Objective

Create only paper directions that are traceable, falsifiable and executable. The valid output is **zero to three** candidates. Zero is preferable to a direction supported only by model enthusiasm, a vague “few studies exist” claim or unavailable data.

## Required reading

Before acting, read:

1. vault `AGENTS.md`;
2. `00_系统规则/平台目录与四技能路由映射.md`;
3. `00_系统规则/V0状态与证据规则.md`;
4. `references/evidence-and-routing.md`;
5. `references/idea-document-spec.md`;
6. `references/quality-gates.md`;
7. `references/idea-candidate.schema.json`;
8. `references/idea-pool-spec.md`;
9. `references/idea-pool.schema.json`;
10. upstream manifest, current human-readable literature theme map, Appendix A.2 cluster cards, typed relations and relevant data/project/task evidence.

Use `nature-ref-verifier` when source identity is disputed and `nature-writing` only after the candidate direction is established. Do not ask a writing skill to manufacture missing evidence.

## Entry modes

### Formal candidate development

Requires:

- one upstream `input_manifest` and `source_batch_id`;
- traceable Appendix A.2 problem clusters;
- evidence and review states preserved;
- dataset/project/task evidence checked for actual availability;
- no unresolved identity or batch blocker that changes the decision.

If a gate fails, output the zero-direction decision record instead of candidates.

### Exploratory ideation

Allowed without a formal manifest, but outputs must say `development_mode: exploratory`, remain `candidate`, and cannot enter the formal candidate pool.

## Workflow

1. **Inventory upstream evidence.** Read the current theme map and problem clusters before general literature notes. Use the theme map to identify cross-cluster dependencies and literature still awaiting relation review; do not treat map node counts as evidence strength.
2. **Resolve source names and links.** Expand every cluster/literature/data/project/task ID to its complete human-readable name and a DOI/publisher/Zotero/Obsidian link.
3. **Separate facts from judgments.** Preserve author conclusion, student judgment and AI inference. Exclude any upstream “result” that is actually a cited-study statement, metric definition, method description, future work or evidence-gap note. A candidate may rely on a result claim only when it is marked as a paper-owned finding with source context and study condition; a blocker never counts as positive evidence.
4. **Generate privately, gate publicly.** Consider alternatives, but only write candidates that pass every required gate.
5. **Test the causal/scientific question.** A model substitution (“A+B”) is not a direction unless it isolates a scientific mechanism or boundary and defines evidence that could refute it.
6. **Check minimum data.** Name basin, period, spatial/temporal resolution, attributes, meteorology, discharge and split design; mark unavailable items explicitly.
7. **Check minimum experiment.** Require strong baselines, controls, extrapolation design, ablation, extremes and uncertainty where relevant.
8. **Complete Appendix A.3.** Use `references/idea-document-spec.md`.
9. **Apply stop conditions.** Reject or defer a candidate when the necessary data, contrast, evidence or team capacity cannot be obtained.
10. **Rank at most three.** Ranking is provisional and cannot replace mentor judgment.
11. **Write detailed Ideas.** Write one complete Appendix A.3 Markdown file per accepted candidate in the established task project's `03_选题管理/`; also write a machine-readable candidate JSONL. Preserve older zero-direction decisions and prior Ideas as history. A new run may supersede an older assessment only through a new dated index and explicit links.
12. **Write the control-layer pool.** For every formal run, including a zero-candidate result, write a human-readable cross-theme comparison under `40_选题池/` and a machine-readable pool record. The pool contains ranking, veto/fatal-gate status, decisive evidence, decisive unknown, and links to detailed Ideas; it never duplicates the full sixteen-section analyses.
13. **Synchronize status.** Detailed Ideas use `knowledge_status: candidate` and `decision_status: waiting_for_mentor_decision`; the pool uses `status: V0临时判断`. Neither layer may emit `mentor_confirmed` without an explicit dated mentor decision record.
14. **Validate.** Run `scripts/validate_idea_contract.py` with the candidate JSONL, task Idea directory, pool Markdown and pool record.

## Appendix A.3 gate

Every candidate must contain:

- specific scientific question;
- current understanding;
- specific gap, not merely “not done”;
- falsifiable judgment with support and refutation criteria;
- minimum data;
- minimum experiment;
- innovation type: theory, method, understanding or application;
- team fit;
- main risks;
- preliminary target output;
- stop conditions;
- `knowledge_status: candidate`;
- `decision_status: waiting_for_mentor_decision`.
- a source ledger in which every used cluster, paper, dataset, project and task is shown by complete name plus a usable link/path; an ID-only ledger fails the gate.

AI/model output never changes either status.

## Zero-direction path

If no candidate passes:

- state “暂不形成候选方向”;
- list failed gates and traceable blockers;
- specify the smallest evidence/data action that could reopen evaluation;
- set a review owner and status;
- do not create placeholder candidates to satisfy a count.
- list blocking clusters and files by complete name and link, not only by cluster IDs.
- still create/update a dated `40_选题池/` decision view that links the zero-direction record and shows why no candidate entered ranking.

## Dual-output contract

The two output layers answer different questions:

- `任务/<项目>/03_选题管理/`: one full Idea analysis per candidate, including scientific question, closest work, minimum data, minimum experiment, risks, stop conditions and next tasks;
- `40_选题池/`: cross-theme ranking, veto checks and mentor comparison. It must link to the detailed file and show only decision-critical fields.

Every candidate present in the machine candidate JSONL must appear in both layers. A pool-only direction may be shown as `reserve` or `rejected` for comparison, but it is not an accepted Appendix A.3 candidate unless a complete task-level file and candidate JSONL record exist.

## Preservation and completion report

Do not overwrite existing idea documents or elevate them to formal. When the user explicitly requests regeneration, create a versioned new run and back up any machine file that must be replaced. Report mode, upstream manifest/cluster IDs, candidates accepted/rejected, zero-direction reason if applicable, data/experiment gaps, both output paths, validation result and decisions reserved for the mentor.
