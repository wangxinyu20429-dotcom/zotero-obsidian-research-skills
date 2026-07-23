# Journal observation and core-paper workflow

These are independent analyses. Neither produces or updates a theme map.

## Journal-tier observation

Use the project framework:

1. Nature or Science main journals.
2. Relevant Nature/Science family journals.
3. Important hydrology/water journals such as WRR, HESS, Journal of Hydrology, and Advances in Water Resources.
4. Other SCI journals within the approved scope.

Use `null` when the venue cannot be assigned confidently. Do not browse for current impact factors unless the user asks.

For each venue, report:

- tier and project-rule reason;
- sample count and time range;
- access/review-level distribution;
- research problems, tasks, data scales, and method roles observed in this sample;
- explicit small-sample limitations.

Do not generalize from a small sample to the whole journal. Journal tier does not determine core status, truth, novelty, or reading depth.

## Core-paper screening

Use the user-supplied research question or scope as the comparison frame. Do not generate a topic, theme hierarchy, problem cluster, or paper idea.

Score each paper 0–3 on exactly five dimensions:

- `theme_relevance_score`: direct relevance to the supplied research scope;
- `representative_score`: representation of a method family, scale, data condition, or operational setting;
- `frontier_score`: frontier contribution and temporal relevance;
- `conflict_score`: contradiction, negative result, counterexample, failure boundary, or dispute value;
- `evidence_value_score`: availability and auditability of methods, results, limitations, figures/tables, and reproduction information in the full text.

The total ranks candidates but does not approve deep reading automatically. Record classic/foundational status as a role, not a sixth score. Journal tier may appear as context but must not add a score or act as a hard gate.

Do not infer a deep-reading quota. If the current `input_manifest.expected_counts.core_deep_reads` exists, use that explicit integer. An explicitly supplied ratio remains a backward-compatible per-run parameter, not a default. If neither exists, score and complete Appendix A.1 but leave the final treatment `deferred` until a person approves the set. Preserve overlapping roles—foundational/classic, representative, frontier, conflict/counterexample, direct relevance, and high evidence value.

Deep reading requires either an explicit user selection or a recorded core selection with role, evidence route, and `deep_read_status=approved`. Use `blocked` when a paper is important but no compliant full-text route exists. Use `deferred` when evidence is insufficient or its role is redundant.

## Evidence mix

Prefer coverage across eras, method families, forecast tasks, data conditions, and journal tiers when the sample allows. Tier coverage is a sample-design goal, not a paper gate.

Record section, page or stable paragraph/figure/table locator, short evidence summary, and checker. A PDF attachment alone is not full-text verification. Label incomplete article coverage `partial_text`.

## Outputs

- Core selection: `10_文献知识/core/核心文献选择_<batch>.csv`.
- Journal observation: `30_期刊与专家/期刊分层与样本观察_<batch>.md`.
- Evidence index: `10_文献知识/evidence/<batch>_核心文献证据索引.md`.
- Deep notes: a user-specified or clearly matching existing `文献/<category>/文献笔记/` directory.

Do not write to `20_主题地图/`, create candidate categories, or infer a paper idea.
