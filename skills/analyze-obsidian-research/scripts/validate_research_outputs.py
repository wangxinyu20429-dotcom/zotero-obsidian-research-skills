#!/usr/bin/env python3
"""Validate Appendix A.2 problem clusters and typed relations using stdlib only."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


CLUSTER_REQUIRED = {
    "cluster_id", "cluster_name", "analysis_mode", "knowledge_status",
    "core_contradiction", "supporting_evidence", "limitations_conflicts",
    "current_consensus", "evidence_grade", "unresolved_part",
    "unresolved_type", "china_team_relevance", "minimum_additional_evidence",
    "confidence", "confidence_reason", "resolved_items", "open_questions",
    "testable_hypotheses", "minimum_validation_actions", "cross_paper_comparisons",
    "competing_explanations", "markdown_path", "theme_map_path",
    "paper_interpretations", "source_files", "source_traces",
}
TRACE_REQUIRED = {
    "canonical_literature_id", "source_title", "source_path_or_url",
    "source_file", "claim_id", "evidence_text", "evidence_status",
    "review_status",
}
RELATION_REQUIRED = {
    "relation_id", "source_id", "source_title", "source_path_or_url",
    "source_file", "target_id", "target_name", "relation_role", "claim_id",
    "evidence_text", "paper_analysis", "evidence_status", "review_status",
}
RELATIONS = {"supports", "limits", "conflicts", "conditions", "gap_signal", "method_for", "needs_verification"}
EVIDENCE = {"metadata_only", "abstract_only", "partial_text", "full_text_main", "full_text_with_supplement"}
REVIEWS = {"unverified", "self_checked", "cross_checked", "mentor_checked"}
UNRESOLVED = {"real_conflict", "validation_gap", "definition_mismatch", "missing_material"}
PAPER_ANALYSIS_REQUIRED = {
    "study_object_and_data", "method_mechanism", "validation_design",
    "paper_owned_findings", "cluster_interpretation",
    "boundary_and_verification",
}
PAPER_MARKERS = (
    "研究对象与数据",
    "方法机制",
    "验证与比较",
    "论文自身结果",
    "对本簇判断的改变",
    "边界与待核验",
)
GENERIC_MARKERS = (
    "辅助定位：见对应画像",
    "当前只支持上述限定判断",
    "在本簇中的作用：`supports`",
    "在本簇中的作用：`limits`",
    "在本簇中的作用：`conditions`",
    "在本簇中的作用：`method_for`",
    "在本簇中的作用：`gap_signal`",
    "在本簇中的作用：`needs_verification`",
)


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no}: each record must be an object")
        rows.append(value)
    return rows


def load_manifest(path: Path | None, formal: bool) -> tuple[dict, set[str], list[str]]:
    errors: list[str] = []
    if path is None:
        if formal:
            errors.append("formal mode requires exactly one --manifest")
        return {}, set(), errors
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    if manifest.get("analysis_mode") != "formal" and formal:
        errors.append("formal validation requires manifest analysis_mode=formal")
    batch = str(manifest.get("source_batch_id") or "")
    if formal and not batch:
        errors.append("manifest missing source_batch_id")
    included = {
        str(row.get("canonical_literature_id"))
        for row in manifest.get("literature") or []
        if row.get("selection_status") == "included" and row.get("canonical_literature_id")
    }
    if formal and not included:
        errors.append("manifest has no included literature identities")
    return manifest, included, errors


def substantive_length(value: object) -> int:
    return len(re.sub(r"[\s|#>*`\-\[\]()_:]+", "", str(value or "")))


def validate_paper_analysis(
    value: object,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label}: paper analysis must be an object")
        return
    missing = sorted(PAPER_ANALYSIS_REQUIRED - set(value))
    if missing:
        errors.append(f"{label}: paper analysis missing {', '.join(missing)}")
    for field, minimum in (
        ("study_object_and_data", 40),
        ("method_mechanism", 40),
        ("validation_design", 40),
        ("cluster_interpretation", 80),
        ("boundary_and_verification", 60),
    ):
        if substantive_length(value.get(field)) < minimum:
            errors.append(f"{label}: {field} is too thin")
    findings = value.get("paper_owned_findings")
    if not isinstance(findings, list):
        errors.append(f"{label}: paper_owned_findings must be an array")
        return
    for finding_no, finding in enumerate(findings, 1):
        if not isinstance(finding, dict):
            errors.append(f"{label}: finding {finding_no} must be an object")
            continue
        for field in (
            "finding", "source_context", "comparison", "metric_observation",
            "study_condition", "interpretation", "boundary",
        ):
            if not str(finding.get(field) or "").strip():
                errors.append(f"{label}: finding {finding_no} missing {field}")
    if not findings:
        blockers = value.get("result_blockers")
        if not isinstance(blockers, list) or not any(str(item).strip() for item in blockers):
            errors.append(
                f"{label}: no paper-owned finding and no explicit result blocker"
            )


def validate_theme_map(
    theme_map_path: Path | None,
    record_path: Path | None,
    clusters: list[dict],
    included_ids: set[str],
    vault_root: Path | None,
    errors: list[str],
) -> dict:
    summary: dict[str, object] = {}
    if len(clusters) <= 1 and theme_map_path is None:
        return summary
    if theme_map_path is None:
        errors.append("multi-cluster run requires --theme-map")
        return summary
    if not theme_map_path.is_file():
        errors.append(f"theme map not found: {theme_map_path}")
        return summary
    if vault_root is not None:
        try:
            theme_map_path.resolve().relative_to(vault_root)
        except ValueError:
            errors.append("theme map leaves vault root")
    text = theme_map_path.read_text(encoding="utf-8-sig")
    body = re.sub(r"\A---.*?---\s*", "", text, count=1, flags=re.S)
    if substantive_length(body) < 6000:
        errors.append(
            f"theme map below 6000-character depth gate ({substantive_length(body)})"
        )
    for heading in (
        "结论先行",
        "语料范围与覆盖",
        "问题簇",
        "跨簇依赖",
        "尚未建立强主题边",
        "全库数据、项目、任务",
        "Zotero",
        "本次实际使用的来源",
    ):
        if heading not in text:
            errors.append(f"theme map missing module: {heading}")
    if "```mermaid" not in text:
        errors.append("theme map missing Mermaid dependency graph")
    if record_path is None:
        errors.append("theme map validation requires --theme-map-record")
        return summary
    if not record_path.is_file():
        errors.append(f"theme map record not found: {record_path}")
        return summary
    try:
        record = json.loads(record_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid theme map record: {exc}")
        return summary
    if not isinstance(record, dict):
        errors.append("theme map record must be an object")
        return summary
    mapped = {str(item) for item in record.get("mapped_literature_ids") or []}
    pending = {str(item) for item in record.get("pending_literature_ids") or []}
    if mapped & pending:
        errors.append("theme map mapped and pending literature overlap")
    if included_ids and mapped | pending != included_ids:
        missing = sorted(included_ids - (mapped | pending))
        extra = sorted((mapped | pending) - included_ids)
        errors.append(
            f"theme map literature coverage mismatch; missing={missing}, extra={extra}"
        )
    cluster_ids = {str(item) for item in record.get("cluster_ids") or []}
    expected_clusters = {str(item.get("cluster_id") or "") for item in clusters}
    if cluster_ids != expected_clusters:
        errors.append("theme map cluster coverage mismatch")
    nodes = record.get("nodes")
    edges = record.get("edges")
    if not isinstance(nodes, list) or not nodes:
        errors.append("theme map record has no nodes")
    if not isinstance(edges, list) or not edges:
        errors.append("theme map record has no edges")
    summary.update(
        {
            "theme_map": str(theme_map_path),
            "mapped_literature": len(mapped),
            "pending_literature": len(pending),
            "theme_nodes": len(nodes) if isinstance(nodes, list) else 0,
            "theme_edges": len(edges) if isinstance(edges, list) else 0,
        }
    )
    return summary


def validate(args: argparse.Namespace) -> tuple[list[str], dict]:
    errors: list[str] = []
    clusters = load_jsonl(Path(args.clusters))
    relations = load_jsonl(Path(args.relations))
    manifest_path = Path(args.manifest) if args.manifest else None
    manifest, included_ids, manifest_errors = load_manifest(manifest_path, args.formal)
    errors.extend(manifest_errors)
    batch = str(manifest.get("source_batch_id") or "")
    cluster_ids: set[str] = set()
    vault_root = Path(args.vault_root).resolve() if args.vault_root else None
    relation_count_by_cluster = Counter(
        str(relation.get("target_id") or "") for relation in relations
    )

    for index, cluster in enumerate(clusters, 1):
        missing = sorted(CLUSTER_REQUIRED - set(cluster))
        if missing:
            errors.append(f"cluster {index} missing: {', '.join(missing)}")
        cluster_id = str(cluster.get("cluster_id") or "")
        if cluster_id in cluster_ids:
            errors.append(f"duplicate cluster_id: {cluster_id}")
        cluster_ids.add(cluster_id)
        if cluster.get("analysis_mode") not in {"formal", "exploratory"}:
            errors.append(f"{cluster_id}: invalid analysis_mode")
        if args.formal and cluster.get("analysis_mode") != "formal":
            errors.append(f"{cluster_id}: formal run contains exploratory cluster")
        if args.formal and str(cluster.get("source_batch_id") or "") != batch:
            errors.append(f"{cluster_id}: source_batch_id mismatch")
        if cluster.get("knowledge_status") == "formal":
            errors.append(f"{cluster_id}: skill output cannot self-promote to formal")
        if cluster.get("unresolved_type") not in UNRESOLVED:
            errors.append(f"{cluster_id}: invalid unresolved_type")
        if cluster.get("confidence") not in {"high", "medium", "low"}:
            errors.append(f"{cluster_id}: invalid confidence")
        markdown_path = str(cluster.get("markdown_path") or "").strip()
        if not markdown_path:
            errors.append(f"{cluster_id}: missing markdown_path")
        elif vault_root is None:
            if args.formal:
                errors.append(f"{cluster_id}: formal depth validation requires --vault-root")
        else:
            candidate = (vault_root / markdown_path).resolve()
            try:
                candidate.relative_to(vault_root)
            except ValueError:
                errors.append(f"{cluster_id}: markdown_path leaves vault root")
            else:
                if not candidate.is_file():
                    errors.append(f"{cluster_id}: markdown file not found: {markdown_path}")
                else:
                    text = candidate.read_text(encoding="utf-8-sig")
                    body = re.sub(r"\A---.*?---\s*", "", text, count=1, flags=re.S)
                    body = body.split("## 9. 本次实际使用的来源", 1)[0]
                    body_count = substantive_length(body)
                    if body_count < 6000:
                        errors.append(
                            f"{cluster_id}: markdown body below 6000-character depth gate ({body_count})"
                        )
                    heading_groups = (
                        ("逐篇证据",),
                        ("已解决",),
                        ("尚未解决",),
                        ("竞争性解释",),
                        ("可检验假设", "可证伪问题与假设"),
                        ("最小验证",),
                        ("本次实际使用的来源", "本文件实际使用的来源"),
                    )
                    for alternatives in heading_groups:
                        if not any(heading in text for heading in alternatives):
                            errors.append(
                                f"{cluster_id}: markdown missing depth module: "
                                + "/".join(alternatives)
                            )
                    for marker in GENERIC_MARKERS:
                        if marker in text:
                            errors.append(
                                f"{cluster_id}: generic paper-evidence marker survived: {marker}"
                            )
                    section_match = re.search(
                        r"(?ms)^## 3\. 逐篇证据解读\s*\n(.*?)(?=^## 4\.)",
                        text,
                    )
                    if not section_match:
                        errors.append(f"{cluster_id}: missing paper-by-paper evidence section")
                    else:
                        blocks = re.split(
                            r"(?m)^### 3\.\d+\s+",
                            section_match.group(1),
                        )[1:]
                        expected = relation_count_by_cluster.get(cluster_id, 0)
                        if len(blocks) != expected:
                            errors.append(
                                f"{cluster_id}: paper blocks {len(blocks)} != typed relations {expected}"
                            )
                        for block_no, block in enumerate(blocks, 1):
                            if substantive_length(block) < 700:
                                errors.append(
                                    f"{cluster_id}: paper block {block_no} below depth gate"
                                )
                            for marker in PAPER_MARKERS:
                                if marker not in block:
                                    errors.append(
                                        f"{cluster_id}: paper block {block_no} missing {marker}"
                                    )
        for field, minimum in (
            ("supporting_evidence", 1),
            ("resolved_items", 3),
            ("open_questions", 3),
            ("testable_hypotheses", 3),
            ("minimum_validation_actions", 2),
            ("cross_paper_comparisons", 1),
            ("competing_explanations", 2),
        ):
            values = cluster.get(field)
            if not isinstance(values, list) or len([value for value in values if str(value).strip()]) < minimum:
                errors.append(f"{cluster_id}: {field} needs at least {minimum} substantive entries")
        paper_interpretations = cluster.get("paper_interpretations")
        expected_relations = relation_count_by_cluster.get(cluster_id, 0)
        if not isinstance(paper_interpretations, list):
            errors.append(f"{cluster_id}: paper_interpretations must be an array")
        else:
            if len(paper_interpretations) != expected_relations:
                errors.append(
                    f"{cluster_id}: paper_interpretations {len(paper_interpretations)} "
                    f"!= typed relations {expected_relations}"
                )
            seen_papers: set[str] = set()
            for paper_no, paper in enumerate(paper_interpretations, 1):
                if not isinstance(paper, dict):
                    errors.append(f"{cluster_id}: paper interpretation {paper_no} must be an object")
                    continue
                paper_id = str(paper.get("canonical_literature_id") or "")
                if not paper_id:
                    errors.append(f"{cluster_id}: paper interpretation {paper_no} missing literature id")
                if paper_id in seen_papers:
                    errors.append(f"{cluster_id}: duplicate paper interpretation: {paper_id}")
                seen_papers.add(paper_id)
                for field in (
                    "source_title", "source_path_or_url", "source_file",
                    "claim_id", "relation_role", "evidence_status", "review_status",
                ):
                    if not str(paper.get(field) or "").strip():
                        errors.append(
                            f"{cluster_id}:{paper_id}: missing {field}"
                        )
                validate_paper_analysis(paper, f"{cluster_id}:{paper_id}", errors)
        source_files = cluster.get("source_files")
        if not isinstance(source_files, list) or not source_files:
            errors.append(f"{cluster_id}: source_files must be non-empty")
        else:
            for source_no, source in enumerate(source_files, 1):
                if not isinstance(source, dict):
                    errors.append(f"{cluster_id}: source_file {source_no} must be an object")
                    continue
                for field in ("display_name", "source_path_or_url", "source_role"):
                    if not str(source.get(field) or "").strip():
                        errors.append(f"{cluster_id}: source_file {source_no} missing {field}")
        traces = cluster.get("source_traces")
        if not isinstance(traces, list) or len(traces) < expected_relations:
            errors.append(
                f"{cluster_id}: source_traces needs at least {expected_relations} relation traces"
            )
            continue
        for trace_no, trace in enumerate(traces, 1):
            if not isinstance(trace, dict):
                errors.append(f"{cluster_id}: trace {trace_no} must be an object")
                continue
            missing_trace = sorted(TRACE_REQUIRED - set(trace))
            if missing_trace:
                errors.append(f"{cluster_id}: trace {trace_no} missing {', '.join(missing_trace)}")
            literature_id = str(trace.get("canonical_literature_id") or "")
            if args.formal and literature_id not in included_ids:
                errors.append(f"{cluster_id}: trace literature not included by manifest: {literature_id}")
            if trace.get("evidence_status") not in EVIDENCE:
                errors.append(f"{cluster_id}: trace {trace_no} invalid evidence_status")
            if trace.get("review_status") not in REVIEWS:
                errors.append(f"{cluster_id}: trace {trace_no} invalid review_status")
            for field in ("source_title", "source_path_or_url", "source_file"):
                if not str(trace.get(field) or "").strip():
                    errors.append(f"{cluster_id}: trace {trace_no} missing named source field {field}")
            evidence_text = str(trace.get("evidence_text") or "").strip()
            if len(evidence_text) < 20:
                errors.append(f"{cluster_id}: trace {trace_no} evidence_text is too short")
            if evidence_text in {str(trace.get("location") or "").strip(), str(trace.get("claim_id") or "").strip()}:
                errors.append(f"{cluster_id}: trace {trace_no} uses a locator/ID as evidence")

    relation_counts: dict[str, int] = {}
    seen_relations: set[str] = set()
    for index, relation in enumerate(relations, 1):
        missing = sorted(RELATION_REQUIRED - set(relation))
        if missing:
            errors.append(f"relation {index} missing: {', '.join(missing)}")
        relation_id = str(relation.get("relation_id") or "")
        if relation_id in seen_relations:
            errors.append(f"duplicate relation_id: {relation_id}")
        seen_relations.add(relation_id)
        role = relation.get("relation_role")
        if role not in RELATIONS:
            errors.append(f"{relation_id}: invalid relation_role")
        else:
            relation_counts[role] = relation_counts.get(role, 0) + 1
        if relation.get("target_id") not in cluster_ids:
            errors.append(f"{relation_id}: target cluster not found")
        if args.formal and relation.get("source_id") not in included_ids:
            errors.append(f"{relation_id}: source literature not included by manifest")
        if relation.get("evidence_status") not in EVIDENCE:
            errors.append(f"{relation_id}: invalid evidence_status")
        if relation.get("review_status") not in REVIEWS:
            errors.append(f"{relation_id}: invalid review_status")
        for field in ("source_title", "source_path_or_url", "source_file", "target_name"):
            if not str(relation.get(field) or "").strip():
                errors.append(f"{relation_id}: missing named source field {field}")
        evidence_text = str(relation.get("evidence_text") or "").strip()
        if substantive_length(evidence_text) < 80:
            errors.append(f"{relation_id}: evidence_text is too short")
        validate_paper_analysis(
            relation.get("paper_analysis"),
            f"{relation_id}",
            errors,
        )

    theme_summary = validate_theme_map(
        Path(args.theme_map).resolve() if args.theme_map else None,
        Path(args.theme_map_record).resolve() if args.theme_map_record else None,
        clusters,
        included_ids,
        vault_root,
        errors,
    )
    return errors, {
        "clusters": len(clusters),
        "relations": len(relations),
        "relation_counts": relation_counts,
        "manifest_expected_counts": manifest.get("expected_counts") or {},
        **theme_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clusters", required=True, help="problem_clusters.jsonl")
    parser.add_argument("--relations", required=True, help="typed_relations.jsonl")
    parser.add_argument("--manifest")
    parser.add_argument("--vault-root")
    parser.add_argument("--theme-map")
    parser.add_argument("--theme-map-record")
    parser.add_argument("--formal", action="store_true")
    args = parser.parse_args()
    try:
        errors, summary = validate(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors, summary = [str(exc)], {}
    print(json.dumps({"status": "PASS" if not errors else "FAIL", **summary, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
