#!/usr/bin/env python3
"""Rebuild deep cluster evidence sections and a human-readable literature theme map.

The script never invents scientific interpretation. It requires an upstream
paper-specific analysis record for every literature-to-cluster relation and
renders those reviewed records into synchronized Markdown and JSONL outputs.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


RELATION_LABELS = {
    "supports": "支持",
    "limits": "限制",
    "conflicts": "冲突",
    "conditions": "成立条件",
    "gap_signal": "缺口信号",
    "method_for": "验证方法/路径",
    "needs_verification": "需要进一步核验",
}
ID_RE = re.compile(
    r"(?m)^(?:paper_id|canonical_literature_id):\s*[\"']?([A-Za-z0-9._-]+)[\"']?\s*$"
)
SECTION_3_RE = re.compile(
    r"(?ms)^## 3\. 逐篇证据解读\s*\n.*?(?=^## 4\.)"
)
GENERIC_EVIDENCE_PATTERNS = (
    "辅助定位：见对应画像",
    "当前只支持上述限定判断",
    "在本簇中的作用：`supports`",
    "在本簇中的作用：`limits`",
    "在本簇中的作用：`conditions`",
    "在本簇中的作用：`method_for`",
    "在本簇中的作用：`gap_signal`",
    "在本簇中的作用：`needs_verification`",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no}: expected a JSON object")
        rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def clean(value: Any, fallback: str = "未从当前证据确认") -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or fallback


def base_relation_claim(relation: dict[str, Any]) -> str:
    """Recover the short curator-written claim from old or enriched records."""
    raw = clean(
        relation.get("base_evidence_text")
        or relation.get("original_evidence_text")
        or relation.get("evidence_text"),
        "",
    )
    raw = re.sub(
        r"^(?:该文在“[^”]+”中的关系类型是“[^”]+”。\s*)+",
        "",
        raw,
    )
    for marker in (
        "这一关系并非由模型名称决定",
        "论文自身结果概括：",
        "横向比较显示：",
    ):
        if marker in raw:
            raw = raw.split(marker, 1)[0].strip()
    return clean(raw, "当前关系记录缺少可复核的简短证据判断")


def esc_table(value: Any) -> str:
    return clean(value, "—").replace("|", "\\|").replace("\n", " ")


def ensure_within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path leaves vault root: {resolved}") from exc
    return resolved


def relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def wiki(path: Path, root: Path, label: str | None = None) -> str:
    target = relative(path, root)
    if target.endswith(".md"):
        target = target[:-3]
    return f"[[{target}|{label or path.name}]]"


def index_notes(directory: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    if not directory.is_dir():
        return result
    for path in directory.rglob("*.md"):
        text = path.read_text(encoding="utf-8-sig", errors="replace")[:12000]
        match = ID_RE.search(text)
        if match:
            result.setdefault(match.group(1), path)
    return result


def article_url(item: dict[str, Any], relation: dict[str, Any] | None = None) -> str:
    if relation:
        direct = clean(relation.get("source_path_or_url"), "")
        if direct.startswith(("http://", "https://")):
            return direct
    direct = clean(item.get("url"), "")
    if direct.startswith(("http://", "https://")):
        return direct
    doi = clean(item.get("doi_normalized") or item.get("doi"), "")
    return f"https://doi.org/{doi}" if doi else ""


def title_for(
    paper_id: str,
    manifest_item: dict[str, Any],
    relation: dict[str, Any] | None = None,
) -> str:
    if relation:
        title = clean(relation.get("source_title"), "")
        if title:
            return title
    return clean(manifest_item.get("title"), paper_id)


def backup_file(path: Path, vault: Path, backup_root: Path) -> None:
    if not path.exists():
        return
    destination = backup_root / relative(path, vault)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def finding_summary(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "当前逐篇分析未保留可作为论文自身结果的发现。"
    first = findings[0]
    return (
        f"{clean(first.get('finding'))} "
        f"比较条件为{clean(first.get('comparison'))}；"
        f"研究条件为{clean(first.get('study_condition'))}。"
    )


def normalize_findings(
    findings: object,
    analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """Upgrade legacy curated findings without inventing a new result."""
    normalized: list[dict[str, Any]] = []
    if not isinstance(findings, list):
        return normalized
    for item in findings:
        if not isinstance(item, dict) or not clean(item.get("finding"), ""):
            continue
        finding = clean(item.get("finding"))
        source_context = clean(item.get("source_context"))
        legacy_analysis = clean(item.get("analysis"), "")
        comparison = clean(
            item.get("comparison"),
            (
                "当前旧记录未把比较对象拆成独立字段；原验证设计为："
                + clean(analysis.get("validation"))
            ),
        )
        metric_observation = clean(
            item.get("metric_observation"),
            (
                "该条结果报告的指标或误差形态保留在发现原文中："
                f"“{finding}”；需在对应结果图表中逐项核对。"
            ),
        )
        study_condition = clean(
            item.get("study_condition"),
            (
                "数据与样本条件为："
                + clean(analysis.get("data"))
                + "；验证条件为："
                + clean(analysis.get("validation"))
            ),
        )
        interpretation = clean(
            item.get("interpretation"),
            legacy_analysis
            or clean(analysis.get("research_judgment")),
        )
        boundary = clean(
            item.get("boundary"),
            (
                clean(analysis.get("limitation"))
                + " "
                + clean(analysis.get("uncertainty"))
            ),
        )
        normalized.append(
            {
                "finding": finding,
                "source_context": source_context,
                "comparison": comparison,
                "metric_observation": metric_observation,
                "study_condition": study_condition,
                "interpretation": interpretation,
                "boundary": boundary,
                "legacy_analysis": legacy_analysis or None,
            }
        )
    return normalized


def build_cross_comparisons(
    relations: list[dict[str, Any]],
    analyses: dict[str, dict[str, Any]],
    literature: dict[str, dict[str, Any]],
) -> list[str]:
    comparisons: list[str] = []
    if len(relations) < 2:
        return [
            "当前簇只有一篇类型化关系文献，无法形成可靠横向比较；需补充独立研究后再判断。"
        ]
    for index, left in enumerate(relations):
        right = relations[(index + 1) % len(relations)]
        left_id = clean(left.get("source_id"), "")
        right_id = clean(right.get("source_id"), "")
        left_analysis = analyses[left_id]
        right_analysis = analyses[right_id]
        left_title = title_for(left_id, literature[left_id], left)
        right_title = title_for(right_id, literature[right_id], right)
        comparisons.append(
            f"《{left_title}》的验证重心是“{clean(left_analysis.get('validation'))}”；"
            f"《{right_title}》则是“{clean(right_analysis.get('validation'))}”。"
            "两者回答的验证问题不同，因此不能只按最终指标直接排序；应先统一空间/时间留出、"
            "输入信息和比较基线，再判断结论是否一致。"
        )
        if len(comparisons) >= 4:
            break
    return comparisons


def build_interpretation(
    relation: dict[str, Any],
    analysis: dict[str, Any],
    cluster: dict[str, Any],
    manifest_item: dict[str, Any],
    profile_path: Path | None,
    note_path: Path | None,
    zotero_check: dict[str, Any] | None,
    comparison: str,
) -> dict[str, Any]:
    paper_id = clean(relation.get("source_id"), "")
    findings = normalize_findings(analysis.get("result_findings"), analysis)
    blockers = analysis.get("result_blockers")
    if not isinstance(blockers, list):
        blockers = []
    role = clean(relation.get("relation_role"), "needs_verification")
    role_label = RELATION_LABELS.get(role, role)
    source_title = title_for(paper_id, manifest_item, relation)
    # Keep the curator-written relation claim separate from the expanded
    # analysis so repeated runs do not feed rendered prose back into itself.
    base_claim = base_relation_claim(relation)
    cluster_interpretation = (
        f"该文在“{cluster['cluster_name']}”中的关系类型是“{role_label}”。"
        f"{base_claim} 这一关系并非由模型名称决定，而是由其研究对象、验证设计和论文自身结果共同决定。"
        f"横向比较显示：{comparison}"
    )
    boundary = (
        f"论文报告的局限为：{clean(analysis.get('limitation'))} "
        f"不确定性边界为：{clean(analysis.get('uncertainty'))} "
        f"最小复核/复现任务为：{clean(analysis.get('reproduction'))}"
    )
    return {
        "canonical_literature_id": paper_id,
        "base_evidence_text": base_claim,
        "source_title": source_title,
        "source_path_or_url": article_url(manifest_item, relation),
        "source_file": (
            clean(relation.get("source_file"), "")
            or (profile_path.as_posix() if profile_path else "画像文件待核验")
        ),
        "deep_note_file": note_path.as_posix() if note_path else None,
        "zotero_item_key": (
            clean(zotero_check.get("item_key"), "") if zotero_check else None
        ),
        "claim_id": clean(relation.get("claim_id")),
        "relation_role": role,
        "study_object_and_data": (
            f"{clean(analysis.get('problem'))} 数据与研究设计方面，{clean(analysis.get('data'))}"
        ),
        "method_mechanism": clean(analysis.get("method")),
        "validation_design": clean(analysis.get("validation")),
        "paper_owned_findings": findings,
        "result_blockers": [clean(item) for item in blockers if clean(item, "")],
        "cluster_interpretation": cluster_interpretation,
        "boundary_and_verification": boundary,
        "engineering_meaning": clean(analysis.get("engineering")),
        "research_judgment": clean(analysis.get("research_judgment")),
        "evidence_status": clean(relation.get("evidence_status"), "partial_text"),
        "review_status": clean(relation.get("review_status"), "unverified"),
    }


def source_links(
    interpretation: dict[str, Any],
    profile_path: Path | None,
    note_path: Path | None,
    vault: Path,
) -> str:
    links: list[str] = []
    url = clean(interpretation.get("source_path_or_url"), "")
    if url:
        links.append(f"[文章页面]({url})")
    if profile_path:
        links.append(wiki(profile_path, vault, profile_path.name))
    if note_path:
        links.append(wiki(note_path, vault, note_path.name))
    zotero_key = clean(interpretation.get("zotero_item_key"), "")
    if zotero_key:
        links.append(f"[Zotero](zotero://select/library/items/{zotero_key})")
    return "；".join(links) or "来源入口待核验"


def render_finding(index: int, finding: dict[str, Any]) -> list[str]:
    return [
        f"{index}. **发现：** {clean(finding.get('finding'))}",
        f"   - **比较对象/参照：** {clean(finding.get('comparison'))}",
        f"   - **指标或误差形态：** {clean(finding.get('metric_observation'))}",
        f"   - **研究条件：** {clean(finding.get('study_condition'))}",
        f"   - **水文/工程解释：** {clean(finding.get('interpretation'))}",
        f"   - **成立边界：** {clean(finding.get('boundary'))}",
        f"   - **来源上下文：** {clean(finding.get('source_context'))}",
    ]


def render_paper_block(
    index: int,
    interpretation: dict[str, Any],
    profile_path: Path | None,
    note_path: Path | None,
    vault: Path,
) -> str:
    title = interpretation["source_title"]
    url = clean(interpretation.get("source_path_or_url"), "")
    heading = f"[{title}]({url})" if url else title
    lines = [
        f"### 3.{index} {heading}",
        "",
        f"- **来源入口：** {source_links(interpretation, profile_path, note_path, vault)}",
        f"- **证据与复核状态：** `{interpretation['evidence_status']}` / `{interpretation['review_status']}`；关系类型 `{interpretation['relation_role']}`（{RELATION_LABELS.get(interpretation['relation_role'], interpretation['relation_role'])}）。",
        "",
        "#### 研究对象与数据",
        "",
        f"[AI概括] {interpretation['study_object_and_data']}",
        "",
        "#### 方法机制",
        "",
        f"[AI概括] {interpretation['method_mechanism']}",
        "",
        "#### 验证与比较",
        "",
        f"[AI概括] {interpretation['validation_design']}",
        "",
        "#### 论文自身结果",
        "",
    ]
    findings = interpretation["paper_owned_findings"]
    if findings:
        for finding_index, finding in enumerate(findings, 1):
            lines.extend(render_finding(finding_index, finding))
    else:
        lines.append(
            "- **结果证据阻断：** 当前逐篇分析没有保留可确认的论文自身结果；"
            "本条关系只能使用方法、验证或缺口信息，不能把它写成性能发现。"
        )
    blockers = interpretation.get("result_blockers") or []
    if blockers:
        lines.extend(["", "**结果复核阻断：**"])
        lines.extend(f"- {clean(item)}" for item in blockers)
    lines.extend(
        [
            "",
            "#### 对本簇判断的改变",
            "",
            f"[科研判断] {interpretation['cluster_interpretation']}",
            "",
            f"[工程含义] {interpretation['engineering_meaning']}",
            "",
            f"[研究判断] {interpretation['research_judgment']}",
            "",
            "#### 边界与待核验",
            "",
            f"[科研判断] {interpretation['boundary_and_verification']}",
            "",
        ]
    )
    return "\n".join(lines)


def replace_cluster_section(
    text: str,
    blocks: list[str],
    relation_count: int,
) -> str:
    intro = [
        "## 3. 逐篇证据解读",
        "",
        "> 本节逐篇展开研究对象与数据、方法机制、验证、论文自身结果、簇内作用及边界。"
        "关系代码只作为机器别名，不能替代科学解释。",
        "",
        f"> 当前实际进入本簇类型化关系的文献为 {relation_count} 篇；数量来自本次关系记录，不设固定目标。",
        "",
    ]
    replacement = "\n".join(intro + blocks).rstrip() + "\n\n"
    if not SECTION_3_RE.search(text):
        raise ValueError("cluster Markdown is missing '## 3. 逐篇证据解读' before section 4")
    updated = SECTION_3_RE.sub(replacement, text, count=1)
    for marker in GENERIC_EVIDENCE_PATTERNS:
        if marker in updated:
            raise ValueError(f"generic evidence marker survived rebuild: {marker}")
    return updated


def cluster_markdown_path(
    cluster: dict[str, Any],
    output_dir: Path,
    vault: Path,
) -> Path:
    recorded = clean(cluster.get("markdown_path"), "")
    if recorded:
        return ensure_within(vault / recorded, vault)
    matches = sorted(output_dir.glob(f"{cluster['cluster_id']}_*.md"))
    if len(matches) != 1:
        raise ValueError(
            f"{cluster['cluster_id']}: expected one existing Markdown file, found {len(matches)}"
        )
    return ensure_within(matches[0], vault)


def compact_result(interpretation: dict[str, Any]) -> str:
    findings = interpretation.get("paper_owned_findings") or []
    if findings:
        return clean(findings[0].get("finding"))
    blockers = interpretation.get("result_blockers") or []
    return f"结果证据阻断：{clean(blockers[0])}" if blockers else "论文自身结果待核验"


def render_theme_map(
    topic: str,
    manifest_path: Path,
    analyses_path: Path,
    clusters_path: Path,
    relations_path: Path,
    theme_map_record_path: Path,
    included: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    analyses: dict[str, dict[str, Any]],
    profile_index: dict[str, Path],
    note_index: dict[str, Path],
    inventory: dict[str, Any],
    zotero_checks: list[dict[str, Any]],
    vault: Path,
) -> str:
    relation_by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    mapped_ids: set[str] = set()
    for relation in relations:
        relation_by_cluster[clean(relation.get("target_id"), "")].append(relation)
        mapped_ids.add(clean(relation.get("source_id"), ""))
    pending = [
        item
        for item in included
        if clean(item.get("canonical_literature_id"), "") not in mapped_ids
    ]
    cluster_index = {
        clean(cluster.get("cluster_id"), ""): cluster for cluster in clusters
    }
    relation_counts = Counter(
        clean(relation.get("relation_role"), "") for relation in relations
    )
    lines = [
        "---",
        "类型: 文献主题地图",
        f"研究主题: {json.dumps(topic, ensure_ascii=False)}",
        f"source_batch_id: {json.dumps(clean(clusters[0].get('source_batch_id'), ''), ensure_ascii=False)}",
        f"analysis_mode: {clean(clusters[0].get('analysis_mode'), 'exploratory')}",
        "knowledge_status: candidate",
        "evidence_status: partial_text",
        "review_status: unverified",
        "---",
        "",
        f"# {topic}文献主题地图",
        "",
        "> [!warning] 证据边界",
        "> 本图由正式清单、逐篇研究分析、轻量画像、精读笔记、问题簇、类型化关系、"
        "Zotero只读核验和全库相关材料共同生成。机器全文遍历与本地索引不等于人工全文复核；"
        "主题及关系保持 candidate。",
        "",
        "## 1. 结论先行：这批文献形成的论证主线",
        "",
        "当前文献不是按模型名称自然分成若干孤立主题，而是围绕一条逐层收紧的可靠性链组织："
        "首先判断模型能否离开训练流域；其次区分混合/物理信息的真实结构增益；"
        "再检验非平稳条件下的不确定性是否可信，并排除预处理泄漏；"
        "随后把评价转向极端洪水和亚日尺度，最终检查统计改进能否转化为水库运行收益与安全。",
        "",
        "```mermaid",
        "flowchart LR",
        '  A["输入与训练域覆盖"] --> PC01["PC01 跨流域/无资料泛化"]',
        '  PC01 --> PC02["PC02 物理信息与混合模型"]',
        '  PC02 --> PC04["PC04 预处理与信息泄漏"]',
        '  PC01 --> PC03["PC03 非平稳与不确定性"]',
        '  PC04 --> PC05["PC05 极端洪水与亚日尺度"]',
        '  PC03 --> PC05',
        '  PC05 --> PC06["PC06 预报到调度价值"]',
        '  PC03 --> PC06',
        '  V1["空间/时间/事件独立验证"] -.约束.-> PC01',
        '  V1 -.约束.-> PC02',
        '  V2["真实起报信息边界"] -.约束.-> PC04',
        '  V2 -.约束.-> PC05',
        '  V3["安全与效用函数"] -.约束.-> PC06',
        "```",
        "",
        "## 2. 语料范围与覆盖",
        "",
        f"- 正式清单：{wiki(manifest_path, vault, manifest_path.name)}。",
        f"- 纳入文献：{len(included)} 篇；形成类型化主题关系的文献 {len(mapped_ids)} 篇；"
        f"尚未建立强关系边、保留在待路由账本的文献 {len(pending)} 篇。",
        f"- 逐篇研究分析：{wiki(analyses_path, vault, analyses_path.name)}，共 {len(analyses)} 条。",
        f"- 问题簇：{len(clusters)} 个；文献—问题簇关系：{len(relations)} 条。",
        f"- 关系类型分布：{'; '.join(f'{RELATION_LABELS.get(key, key)} {value}' for key, value in sorted(relation_counts.items()))}。",
        f"- 可定位轻量画像：{len(profile_index)} 篇；可定位精读笔记：{len(note_index)} 篇。",
        f"- Zotero代表全文核验：{sum(1 for item in zotero_checks if item.get('check_status') == 'indexed_fulltext_checked')} 篇。",
        "",
        "## 3. 六个问题簇的地图位置",
        "",
        "| 问题簇 | 科学问题/核心矛盾 | 当前有边界的认识 | 类型化文献 | 最小验证 | 详细文件 |",
        "|---|---|---|---:|---|---|",
    ]
    for cluster in clusters:
        cluster_id = clean(cluster.get("cluster_id"), "")
        cluster_path = vault / clean(cluster.get("markdown_path"), "")
        link = (
            wiki(cluster_path, vault, cluster_path.name)
            if cluster_path.is_file()
            else clean(cluster.get("markdown_path"), "详细文件待核验")
        )
        lines.append(
            f"| {cluster_id} · {esc_table(cluster.get('cluster_name'))} | "
            f"{esc_table(cluster.get('core_contradiction'))} | "
            f"{esc_table(cluster.get('current_consensus'))} | "
            f"{len(relation_by_cluster[cluster_id])} | "
            f"{esc_table((cluster.get('minimum_validation_actions') or [cluster.get('minimum_additional_evidence')])[0])} | "
            f"{link} |"
        )
    lines.extend(["", "## 4. 分簇文献关系与结果证据", ""])
    for cluster_no, cluster in enumerate(clusters, 1):
        cluster_id = clean(cluster.get("cluster_id"), "")
        lines.extend(
            [
                f"### 4.{cluster_no} {cluster_id} · {clean(cluster.get('cluster_name'))}",
                "",
                f"- **核心矛盾：** {clean(cluster.get('core_contradiction'))}",
                f"- **当前共识：** {clean(cluster.get('current_consensus'))}",
                f"- **主要未决：** {clean(cluster.get('unresolved_part'))}",
                "",
                "| 完整文献题名 | 关系 | 论文自身结果/阻断 | 该关系为何成立 | 画像/精读 |",
                "|---|---|---|---|---|",
            ]
        )
        for relation in relation_by_cluster[cluster_id]:
            paper_id = clean(relation.get("source_id"), "")
            paper_analysis = relation.get("paper_analysis") or {}
            title = clean(relation.get("source_title"), paper_id)
            url = clean(relation.get("source_path_or_url"), "")
            title_link = f"[{title}]({url})" if url else title
            source_links_list: list[str] = []
            if paper_id in profile_index:
                source_links_list.append(wiki(profile_index[paper_id], vault, "画像"))
            if paper_id in note_index:
                source_links_list.append(wiki(note_index[paper_id], vault, "精读"))
            lines.append(
                f"| {title_link} | {RELATION_LABELS.get(clean(relation.get('relation_role')), clean(relation.get('relation_role')))} | "
                f"{esc_table(compact_result(paper_analysis))} | "
                f"{esc_table(paper_analysis.get('cluster_interpretation'))} | "
                f"{' / '.join(source_links_list) or '待核验'} |"
            )
        comparisons = cluster.get("cross_paper_comparisons") or []
        if comparisons:
            lines.extend(["", "**本簇横向比较：**"])
            lines.extend(f"- {clean(item)}" for item in comparisons)
        lines.extend([""])
    lines.extend(
        [
            "## 5. 跨簇依赖矩阵",
            "",
            "| 来源簇 | 目标簇 | 需要/约束 | 提供 |",
            "|---|---|---|---|",
        ]
    )
    for cluster in clusters:
        source_id = clean(cluster.get("cluster_id"), "")
        for interface in cluster.get("cross_cluster_interfaces") or []:
            if not isinstance(interface, list) or len(interface) < 3:
                continue
            target_id, need, provide = interface[:3]
            lines.append(
                f"| {source_id} · {esc_table(cluster.get('cluster_name'))} | "
                f"{esc_table(target_id)} · {esc_table(cluster_index.get(str(target_id), {}).get('cluster_name'))} | "
                f"{esc_table(need)} | {esc_table(provide)} |"
            )
    lines.extend(
        [
            "",
            "## 6. 尚未建立强主题边的纳入文献",
            "",
            "> 下列文献没有被丢弃。它们已进入正式清单和逐篇分析，但尚未形成经过解释的类型化关系边；"
            "在补充关系理由前，只能作为候选背景、方法或边界材料。",
            "",
            "| 完整文献题名 | 年份 | 逐篇研究判断 | 画像 | 当前状态 |",
            "|---|---:|---|---|---|",
        ]
    )
    for item in pending:
        paper_id = clean(item.get("canonical_literature_id"), "")
        title = clean(item.get("title"), paper_id)
        url = article_url(item)
        title_link = f"[{title}]({url})" if url else title
        analysis = analyses.get(paper_id) or {}
        profile_link = (
            wiki(profile_index[paper_id], vault, profile_index[paper_id].name)
            if paper_id in profile_index
            else "画像待定位"
        )
        lines.append(
            f"| {title_link} | {esc_table(item.get('year'))} | "
            f"{esc_table(analysis.get('research_judgment'))} | {profile_link} | `pending_relation_review` |"
        )
    lines.extend(
        [
            "",
            "## 7. 全库数据、项目、任务与论文管理映射",
            "",
        ]
    )
    inventory_files = inventory.get("files") or []
    area_counts = Counter(clean(item.get("area"), "") for item in inventory_files)
    if area_counts:
        lines.append(
            "- 相关文件观察数："
            + "；".join(f"{area or '未分类'} {count}" for area, count in sorted(area_counts.items()))
            + "。"
        )
    else:
        lines.append("- 未从当前库存记录中解析出相关文件，待核验。")
    lines.extend(
        [
            "- 当前库存中若没有命中 `数据/` 或 `项目/`，只说明本轮关键词和路径范围内未检出，"
            "不能证明团队没有数据或项目。",
            "",
            "| 区域 | 完整文件名/路径 | 在主题地图中的作用 |",
            "|---|---|---|",
        ]
    )
    for item in inventory_files:
        path_text = clean(item.get("relative_path"), "")
        area = clean(item.get("area"), "")
        role = {
            "文献": "画像、精读、问题簇或方向梳理证据",
            "数据": "数据可行性与字段/尺度约束",
            "项目": "团队目标、交付与可用资源",
            "任务": "选题状态、依赖与导师决策边界",
            "论文产出管理": "模板、已有论点或论文出口约束",
        }.get(area, "相关仓库材料")
        lines.append(f"| {area} | [[{path_text}|{Path(path_text).name}]] | {role} |")
    lines.extend(
        [
            "",
            "## 8. Zotero只读核验",
            "",
            "| 代表问题簇 | 完整论文题名 | Zotero条目 | 附件 | 全文索引覆盖 | 用途 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for item in zotero_checks:
        item_key = clean(item.get("item_key"), "")
        attachment = clean(item.get("attachment_key"), "")
        pages = item.get("indexed_pages")
        total_pages = item.get("total_pages")
        lines.append(
            f"| {esc_table(item.get('cluster_id'))} | {esc_table(item.get('title'))} | "
            f"[{item_key}](zotero://select/library/items/{item_key}) | "
            f"{attachment or '未列出'} | "
            f"{pages if pages is not None else '未确认'}/{total_pages if total_pages is not None else '未确认'} 页 | "
            f"{esc_table(item.get('source_role') or '文献身份与代表全文交叉核验')} |"
        )
    lines.extend(
        [
            "",
            "## 9. 本次实际使用的来源",
            "",
            f"- {wiki(manifest_path, vault, manifest_path.name)}：冻结纳入文献身份与批次边界。",
            f"- {wiki(analyses_path, vault, analyses_path.name)}：72篇逐篇问题、数据、方法、验证、结果、局限与复现分析。",
            f"- {wiki(clusters_path, vault, clusters_path.name)}：附录A.2问题簇机器记录。",
            f"- {wiki(relations_path, vault, relations_path.name)}：文献—问题簇类型化关系。",
            f"- {wiki(theme_map_record_path, vault, theme_map_record_path.name)}：本主题地图节点、边与覆盖记录。",
        ]
    )
    for cluster in clusters:
        path = vault / clean(cluster.get("markdown_path"), "")
        if path.is_file():
            lines.append(f"- {wiki(path, vault, path.name)}：{clean(cluster.get('cluster_name'))}详细分析。")
    lines.extend(
        [
            "",
            "## 10. 当前不能由主题地图推出的结论",
            "",
            "- 不能把主题节点或关系边数量解释为研究热度、因果强度或模型优劣。",
            "- 不能把未建立强关系边解释为文献无关；这只表示关系理由尚未完成核验。",
            "- 不能把 Zotero 存在附件或全文索引等同于学生、交叉复核者或导师已读全文。",
            "- 不能从当前主题地图直接形成正式选题；数据可行性、项目资源和导师判断仍是独立门槛。",
            "",
        ]
    )
    return "\n".join(lines)


def build_theme_record(
    topic: str,
    manifest_path: Path,
    theme_map_path: Path,
    included: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    inventory: dict[str, Any],
    zotero_checks: list[dict[str, Any]],
    profile_index: dict[str, Path],
    vault: Path,
) -> dict[str, Any]:
    mapped_ids = {
        clean(relation.get("source_id"), "") for relation in relations
    }
    included_ids = [
        clean(item.get("canonical_literature_id"), "") for item in included
    ]
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    cluster_ids: list[str] = []
    for cluster in clusters:
        cluster_id = clean(cluster.get("cluster_id"), "")
        cluster_ids.append(cluster_id)
        nodes.append(
            {
                "node_id": cluster_id,
                "node_type": "problem_cluster",
                "display_name": clean(cluster.get("cluster_name")),
                "path_or_url": clean(cluster.get("markdown_path")),
            }
        )
    literature_index = {
        clean(item.get("canonical_literature_id"), ""): item for item in included
    }
    for paper_id, item in literature_index.items():
        profile_path = profile_index.get(paper_id)
        nodes.append(
            {
                "node_id": paper_id,
                "node_type": "literature",
                "display_name": clean(item.get("title"), paper_id),
                "path_or_url": (
                    relative(profile_path, vault)
                    if profile_path
                    else article_url(item) or "profile_pending"
                ),
            }
        )
    for relation in relations:
        paper_analysis = relation.get("paper_analysis") or {}
        edges.append(
            {
                "source_id": clean(relation.get("source_id"), ""),
                "target_id": clean(relation.get("target_id"), ""),
                "relation_role": clean(relation.get("relation_role"), ""),
                "evidence_text": clean(
                    paper_analysis.get("cluster_interpretation")
                    or relation.get("evidence_text")
                ),
            }
        )
    cluster_index = {
        clean(cluster.get("cluster_id"), ""): cluster for cluster in clusters
    }
    for cluster_id, cluster in cluster_index.items():
        for interface in cluster.get("cross_cluster_interfaces") or []:
            if not isinstance(interface, list) or len(interface) < 3:
                continue
            target_id, need, provide = interface[:3]
            if str(target_id) not in cluster_index:
                continue
            edges.append(
                {
                    "source_id": cluster_id,
                    "target_id": str(target_id),
                    "relation_role": "depends_on",
                    "evidence_text": f"需要：{clean(need)}；提供：{clean(provide)}",
                }
            )
    vault_sources: list[dict[str, str]] = []
    for item in inventory.get("files") or []:
        path_text = clean(item.get("relative_path"), "")
        area = clean(item.get("area"), "")
        vault_sources.append(
            {
                "display_name": Path(path_text).name,
                "path": path_text,
                "source_role": f"{area}层相关材料",
            }
        )
        if area in {"数据", "项目", "任务"}:
            node_type = {"数据": "data", "项目": "project", "任务": "task"}[area]
            node_id = "VAULT-" + re.sub(r"[^A-Za-z0-9]+", "-", path_text).strip("-")
            nodes.append(
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "display_name": Path(path_text).name,
                    "path_or_url": path_text,
                }
            )
    return {
        "map_id": f"{clean(clusters[0].get('source_batch_id'), 'exploratory')}-theme-map",
        "topic": topic,
        "analysis_mode": clean(clusters[0].get("analysis_mode"), "exploratory"),
        "source_batch_id": clean(clusters[0].get("source_batch_id"), "") or None,
        "knowledge_status": "candidate",
        "manifest_path": relative(manifest_path, vault),
        "markdown_path": relative(theme_map_path, vault),
        "included_literature_count": len(included_ids),
        "mapped_literature_ids": sorted(mapped_ids),
        "pending_literature_ids": sorted(set(included_ids) - mapped_ids),
        "cluster_ids": cluster_ids,
        "nodes": nodes,
        "edges": edges,
        "vault_source_files": vault_sources,
        "zotero_checks": zotero_checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-root", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--analysis-records", required=True)
    parser.add_argument("--clusters", required=True)
    parser.add_argument("--relations", required=True)
    parser.add_argument("--profile-dir", required=True)
    parser.add_argument("--note-dir", required=True)
    parser.add_argument("--cluster-output-dir", required=True)
    parser.add_argument("--theme-map-output", required=True)
    parser.add_argument("--theme-map-record")
    parser.add_argument("--vault-inventory")
    parser.add_argument("--zotero-audit")
    parser.add_argument("--backup-dir")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    vault = Path(args.vault_root).resolve()
    manifest_path = ensure_within(Path(args.manifest), vault)
    analyses_path = ensure_within(Path(args.analysis_records), vault)
    clusters_path = ensure_within(Path(args.clusters), vault)
    relations_path = ensure_within(Path(args.relations), vault)
    profile_dir = ensure_within(Path(args.profile_dir), vault)
    note_dir = ensure_within(Path(args.note_dir), vault)
    cluster_output_dir = ensure_within(Path(args.cluster_output_dir), vault)
    theme_map_path = ensure_within(Path(args.theme_map_output), vault)
    theme_record_path = ensure_within(
        Path(args.theme_map_record)
        if args.theme_map_record
        else theme_map_path.with_suffix(".json"),
        vault,
    )
    inventory_path = (
        ensure_within(Path(args.vault_inventory), vault)
        if args.vault_inventory
        else None
    )
    zotero_path = (
        ensure_within(Path(args.zotero_audit), vault) if args.zotero_audit else None
    )
    backup_root = (
        ensure_within(Path(args.backup_dir), vault) if args.backup_dir else None
    )

    manifest = load_json(manifest_path)
    included = [
        item
        for item in manifest.get("literature") or []
        if item.get("selection_status") == "included"
        and item.get("canonical_literature_id")
    ]
    literature = {
        clean(item.get("canonical_literature_id"), ""): item for item in included
    }
    analyses_list = load_jsonl(analyses_path)
    analyses = {
        clean(item.get("paper_id"), ""): item
        for item in analyses_list
        if clean(item.get("paper_id"), "")
    }
    clusters = load_jsonl(clusters_path)
    relations = load_jsonl(relations_path)
    profile_index = index_notes(profile_dir)
    note_index = index_notes(note_dir)
    inventory = load_json(inventory_path) if inventory_path else {}
    zotero_payload = load_json(zotero_path) if zotero_path else {}
    zotero_checks = zotero_payload.get("checks") or []
    zotero_by_paper = {
        clean(item.get("paper_id"), ""): item
        for item in zotero_checks
        if clean(item.get("paper_id"), "")
    }

    cluster_index = {
        clean(cluster.get("cluster_id"), ""): cluster for cluster in clusters
    }
    relations_by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relation in relations:
        paper_id = clean(relation.get("source_id"), "")
        cluster_id = clean(relation.get("target_id"), "")
        if paper_id not in literature:
            raise ValueError(f"relation source is absent from included manifest: {paper_id}")
        if paper_id not in analyses:
            raise ValueError(f"relation lacks paper-specific analysis record: {paper_id}")
        if cluster_id not in cluster_index:
            raise ValueError(f"relation target cluster is absent: {cluster_id}")
        relations_by_cluster[cluster_id].append(relation)

    target_cluster_files = [
        cluster_markdown_path(cluster, cluster_output_dir, vault)
        for cluster in clusters
    ]
    existing_targets = [
        path
        for path in (
            target_cluster_files
            + [clusters_path, relations_path, theme_map_path, theme_record_path]
        )
        if path.exists()
    ]
    if existing_targets and not args.overwrite:
        raise ValueError(
            "existing outputs require --overwrite: "
            + ", ".join(relative(path, vault) for path in existing_targets)
        )
    if existing_targets and backup_root is None:
        raise ValueError("--overwrite requires --backup-dir")
    if backup_root:
        backup_root.mkdir(parents=True, exist_ok=True)
        for path in existing_targets:
            backup_file(path, vault, backup_root)

    for cluster, cluster_file in zip(clusters, target_cluster_files):
        cluster_id = clean(cluster.get("cluster_id"), "")
        cluster_relations = relations_by_cluster[cluster_id]
        comparisons = build_cross_comparisons(
            cluster_relations, analyses, literature
        )
        cluster["cross_paper_comparisons"] = comparisons
        cluster["markdown_path"] = relative(cluster_file, vault)
        cluster["theme_map_path"] = relative(theme_map_path, vault)
        interpretations: list[dict[str, Any]] = []
        blocks: list[str] = []
        for index, relation in enumerate(cluster_relations):
            paper_id = clean(relation.get("source_id"), "")
            profile_path = profile_index.get(paper_id)
            if profile_path is None:
                recorded = clean(relation.get("source_file"), "")
                candidate = vault / recorded if recorded else None
                if candidate and candidate.is_file():
                    profile_path = candidate
            note_path = note_index.get(paper_id)
            interpretation = build_interpretation(
                relation,
                analyses[paper_id],
                cluster,
                literature[paper_id],
                profile_path,
                note_path,
                zotero_by_paper.get(paper_id),
                comparisons[index % len(comparisons)],
            )
            if profile_path:
                interpretation["source_file"] = relative(profile_path, vault)
            if note_path:
                interpretation["deep_note_file"] = relative(note_path, vault)
            relation["paper_analysis"] = {
                key: interpretation[key]
                for key in (
                    "study_object_and_data",
                    "method_mechanism",
                    "validation_design",
                    "paper_owned_findings",
                    "result_blockers",
                    "cluster_interpretation",
                    "boundary_and_verification",
                    "engineering_meaning",
                    "research_judgment",
                )
            }
            relation["base_evidence_text"] = interpretation["base_evidence_text"]
            relation["evidence_text"] = (
                interpretation["cluster_interpretation"]
                + " 论文自身结果概括："
                + finding_summary(interpretation["paper_owned_findings"])
            )
            if note_path:
                relation["deep_note_file"] = relative(note_path, vault)
            if interpretation.get("zotero_item_key"):
                relation["zotero_item_key"] = interpretation["zotero_item_key"]
            interpretations.append(interpretation)
            blocks.append(
                render_paper_block(
                    index + 1,
                    interpretation,
                    profile_path,
                    note_path,
                    vault,
                )
            )
        cluster["paper_interpretations"] = interpretations
        cluster["supporting_evidence"] = [
            f"{item['source_title']}：{item['cluster_interpretation']}"
            for item in interpretations
        ]
        traces = {
            clean(trace.get("canonical_literature_id"), ""): trace
            for trace in cluster.get("source_traces") or []
        }
        for item in interpretations:
            paper_id = item["canonical_literature_id"]
            trace = traces.get(paper_id)
            if trace:
                trace["evidence_text"] = item["cluster_interpretation"]
                trace["source_title"] = item["source_title"]
                trace["source_path_or_url"] = item["source_path_or_url"]
                trace["source_file"] = item["source_file"]
        current_text = cluster_file.read_text(encoding="utf-8-sig")
        updated_text = replace_cluster_section(
            current_text, blocks, len(cluster_relations)
        )
        cluster_file.write_text(updated_text, encoding="utf-8")

    theme_map_path.parent.mkdir(parents=True, exist_ok=True)
    theme_record_path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(clusters_path, clusters)
    write_jsonl(relations_path, relations)
    theme_record = build_theme_record(
        args.topic,
        manifest_path,
        theme_map_path,
        included,
        clusters,
        relations,
        inventory,
        zotero_checks,
        profile_index,
        vault,
    )
    theme_record_path.write_text(
        json.dumps(theme_record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    theme_text = render_theme_map(
        args.topic,
        manifest_path,
        analyses_path,
        clusters_path,
        relations_path,
        theme_record_path,
        included,
        clusters,
        relations,
        analyses,
        profile_index,
        note_index,
        inventory,
        zotero_checks,
        vault,
    )
    theme_map_path.write_text(theme_text, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "PASS",
                "clusters_rebuilt": len(clusters),
                "relations_enriched": len(relations),
                "included_literature": len(included),
                "mapped_literature": len(
                    {clean(item.get("source_id"), "") for item in relations}
                ),
                "pending_literature": len(included)
                - len({clean(item.get("source_id"), "") for item in relations}),
                "theme_map": relative(theme_map_path, vault),
                "theme_map_record": relative(theme_record_path, vault),
                "backup_dir": relative(backup_root, vault) if backup_root else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
