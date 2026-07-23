#!/usr/bin/env python3
"""Validate Appendix A.3 candidates or a traceable zero-direction decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = {
    "idea_id", "development_mode", "source_cluster_ids", "knowledge_status",
    "decision_status", "scientific_question", "current_understanding",
    "specific_gap", "falsifiable_judgment", "support_condition",
    "refutation_condition", "minimum_data", "minimum_experiment",
    "innovation_type", "team_fit", "main_risks", "target_output",
    "stop_conditions", "markdown_path", "recommendation", "score_total",
    "fatal_gates", "next_actions", "source_records",
}
DATA_FIELDS = {"basin", "period", "spatiotemporal_resolution", "basin_attributes", "meteorology", "discharge", "split_design"}
EXPERIMENT_FIELDS = {"baselines", "controls", "extrapolation", "ablation", "extremes", "uncertainty"}
ZERO_REQUIRED = {
    "decision_type", "development_mode", "source_cluster_ids", "knowledge_status",
    "decision_status", "failed_gates", "blockers",
    "minimum_reopen_action", "review_owner", "source_records",
}
POOL_REQUIRED = {
    "pool_id", "source_batch_id", "status", "knowledge_status",
    "decision_status", "accepted_idea_ids", "entries", "source_records",
}
DETAIL_HEADINGS = [
    "## 五问结论卡",
    "## 1. Idea 概述",
    "## 2. 研究背景与问题来源",
    "## 3. 国内外研究进展",
    "## 4. 现有研究不足与真实文献空白",
    "## 5. 核心科学问题",
    "## 6. 研究目标与研究假设",
    "## 7. 研究内容与论文主线",
    "## 8. 数据基础与可行性",
    "## 9. 研究方法与技术路线",
    "## 10. 预期创新点",
    "## 11. 与最接近研究的差异",
    "## 12. 预期结果与图表设计",
    "## 13. 验证、敏感性与不确定性",
    "## 14. 风险与备选方案",
    "## 15. 论文结构与投稿期刊建议",
    "## 16. 综合评价与实施建议",
    "## 附录 A. 本次实际使用的证据",
]
POOL_HEADINGS = [
    "## 1. 本轮边界与状态",
    "## 2. 跨主题排序总表",
    "## 3. 否决检查",
    "## 4. 逐方向比较",
    "## 5. 共同依赖、重叠与互斥",
    "## 6. 导师快速决策入口",
    "## 7. 本次实际使用的来源",
]


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no}: record must be an object")
        rows.append(value)
    return rows


def nonempty_mapping(value: object, required: set[str]) -> list[str]:
    if not isinstance(value, dict):
        return sorted(required)
    return sorted(key for key in required if not value.get(key))


def inside(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve()
    target.relative_to(root.resolve())
    return target


def validate_source_records(records: object, label: str, errors: list[str]) -> None:
    if not isinstance(records, list) or not records:
        errors.append(f"{label}: source_records must be non-empty")
        return
    for source_no, source in enumerate(records, 1):
        if not isinstance(source, dict):
            errors.append(f"{label}: source record {source_no} must be an object")
            continue
        for field in ("display_name", "source_path_or_url", "used_content"):
            if not str(source.get(field) or "").strip():
                errors.append(f"{label}: source record {source_no} missing {field}")


def validate(args: argparse.Namespace) -> tuple[list[str], dict]:
    errors: list[str] = []
    candidates = load_jsonl(Path(args.candidates))
    manifest: dict = {}
    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8-sig"))
    elif args.formal:
        errors.append("formal mode requires exactly one --manifest")

    manifest_max = (manifest.get("expected_counts") or {}).get("candidate_directions_max")
    maximum = min(3, int(manifest_max)) if manifest_max is not None else 3
    if len(candidates) > maximum:
        errors.append(f"candidate count {len(candidates)} exceeds current maximum {maximum}")

    seen_ids: set[str] = set()
    for index, idea in enumerate(candidates, 1):
        missing = sorted(REQUIRED - set(idea))
        if missing:
            errors.append(f"candidate {index} missing: {', '.join(missing)}")
        idea_id = str(idea.get("idea_id") or "")
        if idea_id in seen_ids:
            errors.append(f"duplicate idea_id: {idea_id}")
        seen_ids.add(idea_id)
        if idea.get("knowledge_status") != "candidate":
            errors.append(f"{idea_id}: knowledge_status must remain candidate")
        if idea.get("decision_status") != "waiting_for_mentor_decision":
            errors.append(f"{idea_id}: decision_status must remain waiting_for_mentor_decision")
        if idea.get("development_mode") not in {"formal", "exploratory"}:
            errors.append(f"{idea_id}: invalid development_mode")
        if args.formal and idea.get("development_mode") != "formal":
            errors.append(f"{idea_id}: formal run contains exploratory candidate")
        if args.formal and str(idea.get("source_batch_id") or "") != str(manifest.get("source_batch_id") or ""):
            errors.append(f"{idea_id}: source_batch_id mismatch")
        clusters = idea.get("source_cluster_ids")
        if not isinstance(clusters, list) or not clusters:
            errors.append(f"{idea_id}: source_cluster_ids must be non-empty")
        data_missing = nonempty_mapping(idea.get("minimum_data"), DATA_FIELDS)
        if data_missing:
            errors.append(f"{idea_id}: minimum_data missing/empty: {', '.join(data_missing)}")
        experiment_missing = nonempty_mapping(idea.get("minimum_experiment"), EXPERIMENT_FIELDS)
        if experiment_missing:
            errors.append(f"{idea_id}: minimum_experiment missing/empty: {', '.join(experiment_missing)}")
        if idea.get("innovation_type") not in {"theory", "method", "understanding", "application"}:
            errors.append(f"{idea_id}: invalid innovation_type")
        gap = str(idea.get("specific_gap") or "")
        if gap.strip() in {"尚未开展", "研究较少", "未见研究", "暂无研究"}:
            errors.append(f"{idea_id}: specific_gap is only an absence claim")
        if "+" in str(idea.get("scientific_question") or "") and not idea.get("scientific_mechanism_or_boundary"):
            errors.append(f"{idea_id}: model-combination question requires scientific_mechanism_or_boundary")
        if idea.get("recommendation") not in {"建议优先开展", "建议修改后开展", "建议作为附属分析", "暂不建议开展"}:
            errors.append(f"{idea_id}: invalid recommendation")
        score = idea.get("score_total")
        if not isinstance(score, int) or isinstance(score, bool) or not 8 <= score <= 40:
            errors.append(f"{idea_id}: score_total must be an integer from 8 to 40")
        if not isinstance(idea.get("fatal_gates"), list) or not idea.get("fatal_gates"):
            errors.append(f"{idea_id}: fatal_gates must be non-empty")
        if not isinstance(idea.get("next_actions"), list) or not idea.get("next_actions"):
            errors.append(f"{idea_id}: next_actions must be non-empty")
        validate_source_records(idea.get("source_records"), idea_id, errors)

        if candidates and args.vault_root:
            try:
                detail_path = inside(Path(args.vault_root), str(idea.get("markdown_path") or ""))
            except (ValueError, OSError) as exc:
                errors.append(f"{idea_id}: invalid markdown_path: {exc}")
            else:
                if not detail_path.is_file():
                    errors.append(f"{idea_id}: detail Markdown not found: {detail_path}")
                else:
                    detail = detail_path.read_text(encoding="utf-8-sig")
                    for heading in DETAIL_HEADINGS:
                        if heading not in detail:
                            errors.append(f"{idea_id}: detail Markdown missing heading: {heading}")
                    if "knowledge_status: candidate" not in detail:
                        errors.append(f"{idea_id}: detail frontmatter must include knowledge_status: candidate")
                    if "decision_status: waiting_for_mentor_decision" not in detail:
                        errors.append(f"{idea_id}: detail frontmatter must include decision_status: waiting_for_mentor_decision")
                    if f"idea_id: {idea_id}" not in detail:
                        errors.append(f"{idea_id}: detail frontmatter idea_id mismatch")

    zero_record: dict = {}
    if not candidates:
        if not args.zero_decision:
            errors.append("zero candidates requires --zero-decision")
        else:
            zero_record = json.loads(Path(args.zero_decision).read_text(encoding="utf-8-sig"))
            missing = sorted(ZERO_REQUIRED - set(zero_record))
            if missing:
                errors.append(f"zero-direction record missing: {', '.join(missing)}")
            if zero_record.get("decision_type") != "zero_candidate_directions":
                errors.append("invalid zero-direction decision_type")
            if zero_record.get("knowledge_status") != "candidate":
                errors.append("zero-direction knowledge_status must remain candidate")
            if not zero_record.get("failed_gates") or not zero_record.get("blockers"):
                errors.append("zero-direction record needs failed_gates and blockers")
            validate_source_records(zero_record.get("source_records"), "zero-direction", errors)

    pool_record: dict = {}
    if candidates:
        if not args.vault_root:
            errors.append("non-zero candidates require --vault-root")
        if not args.pool_record:
            errors.append("non-zero candidates require --pool-record")
        if not args.pool_index:
            errors.append("non-zero candidates require --pool-index")
        if args.pool_record:
            pool_record = json.loads(Path(args.pool_record).read_text(encoding="utf-8-sig"))
            missing = sorted(POOL_REQUIRED - set(pool_record))
            if missing:
                errors.append(f"pool record missing: {', '.join(missing)}")
            if pool_record.get("status") != "V0临时判断":
                errors.append("pool status must remain V0临时判断")
            if pool_record.get("knowledge_status") != "candidate":
                errors.append("pool knowledge_status must remain candidate")
            if pool_record.get("decision_status") != "waiting_for_mentor_decision":
                errors.append("pool decision_status must remain waiting_for_mentor_decision")
            if args.formal and str(pool_record.get("source_batch_id") or "") != str(manifest.get("source_batch_id") or ""):
                errors.append("pool source_batch_id mismatch")
            accepted_ids = pool_record.get("accepted_idea_ids")
            if not isinstance(accepted_ids, list) or set(accepted_ids) != seen_ids:
                errors.append("pool accepted_idea_ids must exactly match candidate idea_ids")
            entries = pool_record.get("entries")
            if not isinstance(entries, list) or len(entries) < len(candidates):
                errors.append("pool entries must include every accepted candidate")
            else:
                accepted_entries = [entry for entry in entries if isinstance(entry, dict) and entry.get("pool_status") == "accepted"]
                if {str(entry.get("idea_id") or "") for entry in accepted_entries} != seen_ids:
                    errors.append("accepted pool entries must exactly match candidate idea_ids")
                for entry in accepted_entries:
                    if not str(entry.get("detail_path") or "").strip():
                        errors.append(f"{entry.get('idea_id')}: accepted pool entry needs detail_path")
            validate_source_records(pool_record.get("source_records"), "pool", errors)

        if args.pool_index and args.vault_root:
            try:
                pool_index = inside(Path(args.vault_root), args.pool_index)
            except (ValueError, OSError) as exc:
                errors.append(f"invalid pool index path: {exc}")
            else:
                if not pool_index.is_file():
                    errors.append(f"pool Markdown not found: {pool_index}")
                else:
                    pool_text = pool_index.read_text(encoding="utf-8-sig")
                    for heading in POOL_HEADINGS:
                        if heading not in pool_text:
                            errors.append(f"pool Markdown missing heading: {heading}")
                    if "status: V0临时判断" not in pool_text:
                        errors.append("pool frontmatter must include status: V0临时判断")
                    if "knowledge_status: candidate" not in pool_text:
                        errors.append("pool frontmatter must include knowledge_status: candidate")
                    if "decision_status: waiting_for_mentor_decision" not in pool_text:
                        errors.append("pool frontmatter must include decision_status: waiting_for_mentor_decision")
                    for idea_id in seen_ids:
                        if idea_id not in pool_text:
                            errors.append(f"pool Markdown missing accepted idea_id: {idea_id}")

    return errors, {
        "candidates": len(candidates),
        "maximum": maximum,
        "zero_direction": not candidates,
        "manifest_expected_counts": manifest.get("expected_counts") or {},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True, help="candidate JSONL; may be empty")
    parser.add_argument("--zero-decision", help="JSON object required when candidate JSONL is empty")
    parser.add_argument("--manifest")
    parser.add_argument("--formal", action="store_true")
    parser.add_argument("--vault-root")
    parser.add_argument("--pool-index", help="vault-relative human-readable pool Markdown")
    parser.add_argument("--pool-record", help="machine-readable pool JSON")
    args = parser.parse_args()
    try:
        errors, summary = validate(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors, summary = [str(exc)], {}
    print(json.dumps({"status": "PASS" if not errors else "FAIL", **summary, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
