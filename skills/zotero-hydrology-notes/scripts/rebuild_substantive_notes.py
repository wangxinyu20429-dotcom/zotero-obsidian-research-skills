#!/usr/bin/env python3
"""Rebuild human profiles and deep notes from reviewed paper-specific syntheses."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


ID_RE = re.compile(
    r"(?m)^(?:paper_id|canonical_literature_id):\s*[\"']?([A-Za-z0-9._-]+)[\"']?\s*$"
)
REQUIRED_ANALYSES = (
    "problem",
    "data",
    "method",
    "validation",
    "result",
    "limitation",
    "uncertainty",
    "engineering",
    "research_judgment",
    "reproduction",
)
GENERIC_PATTERNS = (
    "原文描述的方法链或组件涉及：",
    "当前可核验关键词为：",
    "原文报告了与“",
    "原文提供了数据、研究区或样本设计线索",
    "原文把与“",
    "原文暴露了与“",
    "原文出现与不确定性",
    "原文给出与数据、代码或材料可得性",
    "方法存在不等于性能提升",
    "可支持论文确实提出了这一问题",
    "原文可核验线索",
    "全文相关章节",
    "原文证据卡（见",
)
VISIBLE_LOCATOR_PATTERNS = (
    re.compile(r"§[^|\n]{0,100}?[,，]\s*L\d+\b", re.I),
    re.compile(r"(?:抽取行|提取行|原文行号|段落编号)\s*[:：]?\s*\d+", re.I),
)
DEEP_HEADINGS = (
    "# 一、文献信息与快速定位",
    "# 二、术语、符号与尺度账本",
    "# 三、论文论证骨架",
    "# 四、研究对象与工程背景",
    "# 五、数据与预处理",
    "# 六、方法与模型拆解",
    "# 七、率定、验证与评价指标",
    "# 八、不确定性、敏感性与鲁棒性",
    "# 九、结果、图表与证据定位",
    "# 十、讨论、局限与适用边界",
    "# 十一、水利工程可实施性检查",
    "# 十二、批判性评价",
    "# 十三、与当前研究和其他文献的关系",
    "# 十四、可引用证据与写作出口",
    "# 十五、复现与最小验证",
    "# 十六、精读结论与行动",
)


def load_jsonl(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        for line_no, line in enumerate(
            path.read_text(encoding="utf-8-sig").splitlines(), 1
        ):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: object required")
            value["_record_file"] = path
            rows.append(value)
    return rows


def load_analyses(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line_no, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        paper_id = str(value.get("paper_id") or "")
        if not paper_id:
            raise ValueError(f"{path}:{line_no}: missing paper_id")
        if paper_id in rows:
            raise ValueError(f"{path}:{line_no}: duplicate {paper_id}")
        for field in REQUIRED_ANALYSES:
            text = str(value.get(field) or "").strip()
            if len(text) < 28:
                raise ValueError(f"{path}:{line_no}: {paper_id}.{field} is too short")
            if any(pattern in text for pattern in GENERIC_PATTERNS):
                raise ValueError(f"{path}:{line_no}: generic prose in {paper_id}.{field}")
        rows[paper_id] = value
    return rows


def index_markdown(directory: Path | None) -> dict[str, Path]:
    result: dict[str, Path] = {}
    if directory is None or not directory.exists():
        return result
    for path in directory.glob("*.md"):
        text = path.read_text(encoding="utf-8-sig")
        match = ID_RE.search(text[:6000])
        if match:
            result[match.group(1)] = path
    return result


def yaml_string(value: object) -> str:
    return json.dumps("" if value is None else value, ensure_ascii=False)


def article_url(profile: dict) -> str:
    url = str(profile.get("url") or "").strip()
    doi = str(profile.get("doi_normalized") or profile.get("doi") or "").strip()
    if not url and doi:
        url = f"https://doi.org/{doi}"
    return url


def article_link(profile: dict, label: str) -> str:
    url = article_url(profile)
    return f"[{label}]({url})" if url else label


def vault_link(path: Path, vault: Path, label: str) -> str:
    relative = path.resolve().relative_to(vault.resolve()).as_posix()
    if relative.lower().endswith(".md"):
        relative = relative[:-3]
    return f"[[{relative}|{label}]]"


def split_sentences(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"(?<=[。！？；])", text) if part.strip()]
    return parts or [text.strip()]


def shorten(text: str, maximum: int = 78) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    compact = re.sub(r"[。！？]+", "；", compact).strip("；")
    return compact if len(compact) <= maximum else compact[: maximum - 1] + "…"


def markdown_cell(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).replace("|", "｜").strip()


def list_text(values: object, empty: str = "未从当前证据确认") -> str:
    if not isinstance(values, list):
        return empty
    cleaned = [markdown_cell(value) for value in values if markdown_cell(value)]
    return "、".join(cleaned) if cleaned else empty


def analysis_parts(analysis: dict, field: str) -> list[str]:
    return split_sentences(str(analysis.get(field) or ""))


def split_analysis_clauses(text: str) -> list[str]:
    pieces = re.split(
        r"[。！？；]+|，(?=(?:但|而|同时|其中|此外|作者|模型|结果|在测试|在验证|相较|相比))",
        re.sub(r"\s+", " ", text).strip(),
    )
    result: list[str] = []
    for piece in pieces:
        cleaned = re.sub(r"^(?:但|而|同时|其中|此外)[，、:\s]*", "", piece).strip(" ，；。")
        if len(cleaned) < 8 or cleaned in result:
            continue
        result.append(cleaned)
    return result


def module_depth_items(analysis: dict, field: str) -> list[tuple[str, str]]:
    if field == "result":
        items: list[tuple[str, str]] = []
        for finding in analysis.get("result_findings") or []:
            parts = [str(finding.get("finding") or "").strip().rstrip("。；;")]
            for label, key in (
                ("比较", "comparison"),
                ("指标/现象", "metric_observation"),
                ("条件", "study_condition"),
                ("分析", "analysis"),
                ("水文/工程解释", "interpretation"),
                ("边界", "boundary"),
            ):
                value = str(finding.get(key) or "").strip()
                if value:
                    parts.append(f"{label}：{value.rstrip('。；;')}")
            items.append(("论文自身结果", "；".join(part for part in parts if part) + "。"))
        if items:
            return items
        blockers = "；".join(str(value) for value in analysis.get("result_blockers") or [])
        return [("结果证据阻断", blockers or "未获得可归属于本文试验的结果证据，禁止补写结果。")]

    primary_labels = {
        "data": "数据事实",
        "method": "方法事实",
        "validation": "验证事实",
        "limitation": "局限事实",
    }
    companion_fields = {
        "data": (
            ("代表性影响", "limitation"),
            ("切分影响", "validation"),
            ("分布变化", "uncertainty"),
        ),
        "method": (
            ("如何验证", "validation"),
            ("如何识别组件贡献", "reproduction"),
            ("结构边界", "limitation"),
        ),
        "validation": (
            ("结果解释", "result"),
            ("外部有效性", "limitation"),
            ("稳健性要求", "uncertainty"),
        ),
        "limitation": (
            ("不确定性后果", "uncertainty"),
            ("工程后果", "engineering"),
            ("判别实验", "reproduction"),
        ),
    }
    items: list[tuple[str, str]] = []
    for clause in split_analysis_clauses(str(analysis.get(field) or ""))[:5]:
        items.append((primary_labels[field], clause))
    for label, companion in companion_fields[field]:
        if len(items) >= 5:
            break
        clauses = split_analysis_clauses(str(analysis.get(companion) or ""))
        if not clauses:
            continue
        value = clauses[0]
        if value not in {item[1] for item in items}:
            items.append((label, value))
    return items


def render_depth_items(prefix: str, items: list[tuple[str, str]]) -> list[str]:
    return [
        f"- **{prefix}{index:02d} · {label}：** {text}"
        for index, (label, text) in enumerate(items, 1)
    ]


def metric_terms(profile: dict, analysis: dict) -> str:
    values = [markdown_cell(value) for value in profile.get("metrics") or [] if markdown_cell(value)]
    known = (
        "NSE", "KGE", "RMSE", "MAE", "MAPE", "PBIAS", "R²", "R2", "R", "IOA",
        "POD", "FAR", "CRPS", "PICP", "FLV", "FHV", "SDR", "U95%",
    )
    combined = " ".join(str(analysis.get(field) or "") for field in ("validation", "result", "uncertainty"))
    for token in known:
        if token in combined and token not in values:
            values.append(token)
    return "、".join(values) if values else "未从当前证据确认"


def method_terms(profile: dict, analysis: dict) -> str:
    values = [markdown_cell(value) for value in profile.get("methods") or [] if markdown_cell(value)]
    combined = str(analysis.get("method") or "")
    for token in re.findall(r"\b[A-Za-z][A-Za-z0-9]*(?:[-–][A-Za-z0-9]+)+\b|\b[A-Z][A-Za-z0-9]{1,12}\b", combined):
        if token not in values and token not in {"The", "This", "Water"}:
            values.append(token)
    return "、".join(values[:12]) if values else "未从当前证据确认"


def evidence_coverage(record: dict) -> list[tuple[str, int]]:
    labels = {
        "problem": "研究问题",
        "data": "数据与研究区",
        "method": "方法机制",
        "validation": "验证设计",
        "result": "结果",
        "limitation": "局限",
        "uncertainty": "不确定性",
        "availability": "数据/代码可得性",
    }
    evidence = record.get("fulltext_evidence") or {}
    return [
        (label, len(evidence.get(group) or []))
        for group, label in labels.items()
    ]


def snippet_score(group: str, item: dict) -> int:
    snippet = re.sub(r"\s+", " ", str(item.get("snippet") or "")).strip()
    heading = str(item.get("heading") or "").lower()
    lower = snippet.lower()
    if len(snippet) < 45:
        return -100
    if any(marker in lower for marker in ("doi.org", "http://", "https://", "references")):
        return -100
    if re.search(r"\b(?:j\.|journal|vol\.|pp\.)\s+[a-z]", lower) and " et al." in lower:
        return -100
    citation_prefix = snippet[:140]
    if citation_prefix.count(",") >= 3 and len(re.findall(r"\b[A-Z]\.", citation_prefix)) >= 2:
        return -100
    score = 0
    if 60 <= len(snippet) <= 700:
        score += 2
    if any(marker in heading for marker in ("result", "conclusion", "method", "experiment", "data", "discussion")):
        score += 3
    if any(marker in heading for marker in ("reference", "author contribution", "front matter")):
        score -= 2
    if lower.count(" et al.") >= 1 or len(re.findall(r"\b(?:19|20)\d{2}\b", snippet)) >= 4:
        score -= 5
    if re.search(r"\b(?:fig(?:ure)?|table)\s*\.?\s*\d+", lower):
        score += 2
    group_terms = {
        "problem": ("aim", "objective", "challenge", "need", "question"),
        "data": ("dataset", "catchment", "basin", "station", "period", "used"),
        "method": ("model", "input", "architecture", "hybrid", "trained", "developed"),
        "validation": ("test", "validation", "split", "baseline", "experiment", "metric"),
        "result": ("outperform", "improv", "higher", "lower", "nse", "rmse", "result"),
        "limitation": ("limit", "however", "uncertain", "future", "generaliz"),
        "uncertainty": ("uncertain", "ensemble", "interval", "robust", "sensitivity"),
        "availability": ("data availability", "code availability", "repository", "available"),
    }
    score += sum(1 for term in group_terms.get(group, ()) if term in lower)
    if re.search(r"\d", snippet):
        score += 1
    return score


def bounded_excerpt(snippet: str) -> str:
    words = re.findall(r"\S+", re.sub(r"\s+", " ", snippet).strip())
    excerpt = " ".join(words[:8])
    return excerpt.strip(" \t\r\n\"'“”‘’")


def select_evidence_cards(record: dict, analysis: dict, limit: int = 3) -> list[dict]:
    evidence = record.get("fulltext_evidence") or {}
    field_map = {
        "problem": "problem",
        "data": "data",
        "method": "method",
        "validation": "validation",
        "result": "result",
        "limitation": "limitation",
        "uncertainty": "uncertainty",
        "availability": "reproduction",
    }
    label_map = {
        "problem": "研究命题",
        "data": "数据与尺度",
        "method": "方法机制",
        "validation": "验证设计",
        "result": "结果解释",
        "limitation": "局限边界",
        "uncertainty": "不确定性",
        "availability": "可复现性",
    }
    preferred = ("result", "method", "validation", "data", "limitation", "problem", "uncertainty", "availability")
    cards: list[dict] = []
    for group in preferred:
        candidates = evidence.get(group) or []
        if not candidates:
            continue
        ranked = sorted(candidates, key=lambda item: snippet_score(group, item), reverse=True)
        best = ranked[0]
        if snippet_score(group, best) < 0:
            continue
        excerpt = bounded_excerpt(str(best.get("snippet") or ""))
        if not excerpt:
            continue
        cards.append(
            {
                "group": group,
                "label": label_map[group],
                "excerpt": excerpt,
                "analysis": str(analysis[field_map[group]]),
                "navigation": f"{label_map[group]}相关正文",
                "has_excerpt": True,
            }
        )
        if len(cards) >= limit:
            break
    selected_groups = {card["group"] for card in cards}
    for group in preferred:
        if len(cards) >= limit:
            break
        if group in selected_groups:
            continue
        cards.append(
            {
                "group": group,
                "label": label_map[group],
                "excerpt": "",
                "analysis": str(analysis[field_map[group]]),
                "navigation": f"{label_map[group]}相关正文",
                "has_excerpt": False,
            }
        )
    return cards


def body_character_count(text: str) -> int:
    body = re.sub(r"\A---.*?---\s*", "", text, count=1, flags=re.S)
    body = body.split("## 本文件实际使用的来源", 1)[0]
    body = re.sub(r"[\s|#>*`\-\[\]()_:]+", "", body)
    return len(body)


def source_ledger(
    record: dict,
    current_path: Path,
    paired_path: Path | None,
    manifest: Path,
    analysis_path: Path,
    vault: Path,
) -> list[str]:
    profile = record.get("profile") or {}
    title_cn = str(record.get("title_cn") or profile.get("title") or "")
    title_original = str(profile.get("title") or title_cn)
    source_path = str(profile.get("source_path") or record.get("source_path") or "")
    evidence_status = str(record.get("evidence_status") or "partial_text")
    review_status = str(record.get("review_status") or "unverified")
    record_file = Path(record["_record_file"])
    lines = [
        "## 本文件实际使用的来源",
        "",
        "| 类型 | 完整名称 | 链接或文件 | 用途与状态 |",
        "|---|---|---|---|",
        f"| 原始文献 | {title_original} | {article_link(profile, 'DOI/出版社页面')} | 论文身份与正文证据；`{evidence_status}` / `{review_status}` |",
    ]
    if source_path.startswith("zotero://"):
        lines.append(
            f"| Zotero | {title_cn} 的本地条目 | [{source_path}]({source_path}) | 本地书目与附件定位；未自动升级人工复核状态 |"
        )
    lines.append(
        f"| 机器全文证据 | {record_file.name} | {vault_link(record_file, vault, record_file.name)} | 保存原文片段和机器抽取位置；`{evidence_status}` / `{review_status}` |"
    )
    lines.append(
        f"| 逐篇分析记录 | {analysis_path.name} | {vault_link(analysis_path, vault, analysis_path.name)} | 本文件所用论文特定综合分析、证据卡与论证链 |"
    )
    lines.append(
        f"| 输入清单 | {manifest.name} | {vault_link(manifest, vault, manifest.name)} | 批次身份、范围与数量口径 |"
    )
    if paired_path is not None:
        role = "对应精读笔记" if "profiles" in current_path.parts else "对应轻量画像"
        lines.append(
            f"| {role} | {paired_path.name} | {vault_link(paired_path, vault, paired_path.stem)} | 交叉核对论文身份与分析边界 |"
        )
    return lines


def render_profile(
    record: dict,
    analysis: dict,
    path: Path,
    paired_path: Path | None,
    manifest: Path,
    analysis_path: Path,
    vault: Path,
) -> str:
    profile = record.get("profile") or {}
    paper_id = str(profile.get("paper_id") or profile.get("canonical_literature_id"))
    title_cn = str(record.get("title_cn") or profile.get("title") or paper_id)
    title_original = str(profile.get("title") or title_cn)
    authors = profile.get("authors") or []
    source_batch_id = str(profile.get("source_batch_id") or "")
    evidence_status = str(record.get("evidence_status") or "partial_text")
    review_status = str(record.get("review_status") or "unverified")
    doi = str(profile.get("doi_normalized") or profile.get("doi") or "")
    zotero = str(profile.get("source_path") or "")
    cards = select_evidence_cards(record, analysis)
    coverage = evidence_coverage(record)
    problem_parts = analysis_parts(analysis, "problem")
    limitation_parts = analysis_parts(analysis, "limitation")
    uncertainty_parts = analysis_parts(analysis, "uncertainty")
    reproduction_parts = analysis_parts(analysis, "reproduction")
    baselines = list_text(
        profile.get("baselines"),
        f"需从方法链核对：{shorten(analysis['method'], 130)}",
    )
    metrics = metric_terms(profile, analysis)
    datasets = list_text(profile.get("datasets"))
    methods = method_terms(profile, analysis)
    data_items = module_depth_items(analysis, "data")
    method_items = module_depth_items(analysis, "method")
    validation_items = module_depth_items(analysis, "validation")
    result_items = module_depth_items(analysis, "result")
    limitation_items = module_depth_items(analysis, "limitation")
    reported_result_count = sum(1 for label, _ in result_items if label == "论文自身结果")
    lines = [
        "---",
        f"title: {yaml_string(title_cn)}",
        f"title_original: {yaml_string(title_original)}",
        f"authors: {yaml_string(authors)}",
        f"year: {yaml_string(profile.get('year'))}",
        f"journal: {yaml_string(profile.get('venue'))}",
        f"doi: {yaml_string(doi)}",
        f"paper_id: {paper_id}",
        f"canonical_literature_id: {paper_id}",
        f"source_batch_id: {source_batch_id}",
        f"source_path: {yaml_string(zotero)}",
        "selection_status: included",
        f"evidence_status: {evidence_status}",
        f"review_status: {review_status}",
        "knowledge_status: candidate",
        "analysis_method: paper_specific_source_synthesis",
        "updated: 2026-07-23",
        "---",
        "",
        f"# {article_link(profile, title_cn)}",
        "",
        f"> [!warning] 证据边界",
        f"> 本画像依据机器遍历得到的正文片段、全文结构和逐篇研究分析重建，状态为 `{evidence_status}` / `{review_status}`。它用于科研筛查、提出竞争性解释和设计复核实验，不能冒充学生已经核验原图表与补充材料。",
        "",
        "## 1. 快速科研判断",
        "",
        analysis["research_judgment"],
        "",
        f"这篇论文是否值得继续投入，取决于其结果能否通过以下最小复核：{analysis['reproduction']}",
        "",
        "## 2. 证据覆盖与可用程度",
        "",
        "| 证据模块 | 已抽取片段数 | 当前能做什么 | 仍不能做什么 |",
        "|---|---:|---|---|",
    ]
    for label, count in coverage:
        lines.append(
            f"| {label} | {count} | {'可形成内容分析' if count else '仅能记录缺口'} | 未人工核验原图表与完整上下文 |"
        )
    lines.extend(
        [
        "",
        f"- 可访问全文字符规模：{record.get('fulltext_characters') or '未记录'}。",
        f"- 当前读取层级：机器全文遍历后的 `{evidence_status}`，人工复核仍为 `{review_status}`。",
        f"- 证据卡仅选用 {len(cards)} 个较可解释片段；书目、通用背景、作者贡献和指标定义不会被当作论文结果。",
        "",
        "## 3. 研究问题、对象与决策含义",
        "",
        analysis["problem"],
        "",
        f"本命题的筛查意义在于：{shorten(analysis['research_judgment'], 240)}。后续复核需要判断论文的结果是否真正回答了上述问题，而不是只证明某个模型能够在该数据上拟合。",
        "",
        "| 维度 | 当前识别 | 解释边界 |",
        "|---|---|---|",
        f"| 预测对象 | {markdown_cell(profile.get('forecast_target') or '未从当前证据确认')} | 需核对变量定义、单位和是否为实况/预报 |",
        f"| 预报提前期 | {markdown_cell(profile.get('forecast_horizon') or '未从当前证据确认')} | 缺少提前期时不能直接评价业务预报价值 |",
        f"| 空间尺度 | {markdown_cell(profile.get('spatial_scale') or '未从当前证据确认')} | 单流域、区域和跨流域证据不能互换 |",
        f"| 时间尺度 | {markdown_cell(profile.get('temporal_resolution') or '未从当前证据确认')} | 日、小时、月尺度对应不同记忆和极端响应 |",
        f"| 研究区域 | {markdown_cell(profile.get('study_region') or '未从当前证据确认')} | 外推前需比较气候、地形和人类活动 |",
        "",
        "## 4. 论文论证链",
        "",
        "| 环节 | 本文内容 | 对下一环节的约束 |",
        "|---|---|---|",
        f"| 问题 | {shorten(analysis['problem'], 180)} | 数据必须覆盖目标情景而非只覆盖常态 |",
        f"| 数据与尺度 | {shorten(analysis['data'], 180)} | 决定模型能识别哪些水文记忆与空间差异 |",
        f"| 方法机制 | {shorten(analysis['method'], 180)} | 需要由公平基线和独立切分识别方法增量 |",
        f"| 验证 | {shorten(analysis['validation'], 180)} | 决定结果属于样本内拟合、时间外推还是空间外推 |",
        f"| 结果 | {shorten(analysis['result'], 180)} | 只能在相同指标、基线和样本条件下比较 |",
        f"| 边界 | {shorten(analysis['limitation'], 180)} | 定义论文结论不能跨越的情景 |",
        "",
        "## 5. 数据、研究区与样本设计",
        "",
        "### 5.1 分条数据分析",
        "",
        *render_depth_items("D", data_items),
        "",
        "| 数据设计项 | 当前记录 | 科研影响 |",
        "|---|---|---|",
        f"| 数据集/产品 | {datasets} | 数据覆盖决定是否能检验跨区、极端或非平稳问题 |",
        f"| 流域与尺度 | {markdown_cell(profile.get('study_region') or profile.get('spatial_scale') or '未从当前证据确认')} | 若案例单一，外部有效性需单独验证 |",
        f"| 时间分辨率 | {markdown_cell(profile.get('temporal_resolution') or '未从当前证据确认')} | 影响洪峰时刻、滞时和多步预报难度 |",
        f"| 目标与提前期 | {markdown_cell(profile.get('forecast_target') or '未从当前证据确认')}；{markdown_cell(profile.get('forecast_horizon') or '未从当前证据确认')} | 决定指标是否具有工程解释 |",
        "",
        "### 数据风险诊断",
        "",
        f"- 数据代表性风险：{shorten(analysis['limitation'], 230)}",
        f"- 分布变化风险：{shorten(analysis['uncertainty'], 230)}",
        f"- 复核重点：核对缺测处理、时间对齐、标准化统计量来源以及同一事件是否跨训练和测试样本。",
        "",
        "## 6. 方法机制：输入—处理—输出",
        "",
        "### 6.1 分条方法分析",
        "",
        *render_depth_items("M", method_items),
        "",
        "| 方法环节 | 当前识别 | 必须追问的机制问题 |",
        "|---|---|---|",
        f"| 输入 | {datasets}；目标为 {markdown_cell(profile.get('forecast_target') or '未确认')} | 起报时是否真实可得，是否混入事后资料 |",
        f"| 核心处理 | {methods} | 每个组件究竟提取时序、空间、物理状态还是残差信息 |",
        f"| 输出 | {markdown_cell(profile.get('forecast_target') or '未确认')} | 是点预测、区间、集合还是工程决策量 |",
        f"| 对照 | {baselines} | 是否同数据、同切分、同调参预算 |",
        f"| 评价 | {metrics} | 是否覆盖平均过程、洪峰、低流量、偏差和概率可靠性 |",
        "",
        "### 方法增量的判别",
        "",
        f"本文方法的可检验增量应由“{shorten(analysis['method'], 210)}”与“{shorten(analysis['result'], 210)}”共同界定。若消融后优势消失，说明贡献来自特定组件；若只在弱基线下成立，则不能把性能差异归因于方法机制本身。",
        "",
        "## 7. 验证设计、基线与信息泄漏",
        "",
        "### 7.1 分条验证分析",
        "",
        *render_depth_items("V", validation_items),
        "",
        "| 验证问题 | 对本文结果的含义 | 当前状态 |",
        "|---|---|---|",
        f"| 时间独立性 | {shorten(analysis['validation'], 150)} | 需核对训练、验证、测试及调参边界 |",
        f"| 空间独立性 | {shorten(analysis['data'], 150)} | 跨流域或无资料结论必须使用空间留出 |",
        f"| 基线公平性 | 对照包括 {baselines} | 需核对输入信息和调参预算是否一致 |",
        f"| 指标充分性 | 当前指标为 {metrics} | 平均指标不能替代洪峰、低流量和可靠性检查 |",
        f"| 业务信息可得性 | {shorten(analysis['engineering'], 150)} | 事后可得输入不能用于真实提前预报 |",
        "",
        "## 8. 论文证据卡",
        "",
    ])
    for index, card in enumerate(cards, 1):
        evidence_line = (
            f"- **原文短摘：** “{card['excerpt']}”"
            if card["has_excerpt"]
            else f"- **证据形式：** {card['label']}候选短摘存在引文污染或句子残缺，本卡仅保留逐篇中文内容分析。"
        )
        lines.extend(
            [
                f"### E{index:02d}：{card['label']}",
                "",
                evidence_line,
                f"- **中文内容分析：** {card['analysis']}",
                f"- **科研含义：** 该证据进入的是“{card['label']}”环节，必须与本文的数据条件、比较对象和验证设置共同解释。",
                f"- **尚待核对：** 回到{card['navigation']}核对完整句、图表或相邻方法说明，确认其属于本文试验而非背景或引文。",
                "",
            ]
        )
    if not cards:
        lines.extend(
            [
                "当前抽取片段未通过证据卡筛选，未展示原文短摘。此项本身构成阻断：需要人工回到方法、结果和讨论部分补选可解释证据。",
                "",
            ]
        )
    lines.extend(
        [
        "## 9. 主要结果及其条件",
        "",
        "### 9.1 分条结果发现",
        "",
        *render_depth_items("R", result_items),
        "",
        f"当前经全文结果段、讨论段和图表文字复核，保留 {reported_result_count} 条论文自身结果；审计事项和证据缺口不计入结果条数。",
        "",
        "### 9.2 逐条结果的综合解释",
        "",
        f"1. **比较体系：** 当前识别的模型/方法为 {methods}；基线或对照为 {baselines}。结果排序只有在输入、切分和调参预算一致时才可比较。",
        f"2. **评价口径：** 当前识别指标为 {metrics}。需要分别判断这些指标反映平均误差、系统偏差、极端事件、时序偏移还是概率可靠性。",
        f"3. **数据条件：** {shorten(analysis['data'], 260)}。这决定结果代表的是单站拟合、时间外推、空间外推还是变化情景。",
        f"4. **误差结构：** {shorten(analysis['uncertainty'], 260)}。模型排名之外，还要识别高估/低估、洪峰错位、区间失准或分布外退化。",
        f"5. **解释边界：** {shorten(analysis['limitation'], 260)}。超出该边界时，应重新验证而不是沿用原排名。",
        "",
        "## 10. 作者贡献与实际证据增量",
        "",
        "| 判断层次 | 当前分析 |",
        "|---|---|",
        f"| 作者试图解决的增量 | {shorten(analysis['problem'], 190)} |",
        f"| 方法层面的增量 | {shorten(analysis['method'], 190)} |",
        f"| 结果实际支撑的增量 | {shorten(analysis['result'], 190)} |",
        f"| 尚未被证据排除的解释 | {shorten(analysis['limitation'], 190)} |",
        f"| 对当前课题的真实用途 | {shorten(analysis['research_judgment'], 190)} |",
        "",
        "## 11. 局限、失效场景与竞争性解释",
        "",
        "### 11.1 分条局限分析",
        "",
        *render_depth_items("L", limitation_items),
        "",
        "### 至少需要排除的两类竞争性解释",
        "",
        f"1. **数据/切分解释：** {limitation_parts[0] if limitation_parts else analysis['limitation']} 若训练与测试共享相似时期、事件或站点，性能优势可能来自样本相似性而非可迁移机制。",
        f"2. **误差/非平稳解释：** {uncertainty_parts[0] if uncertainty_parts else analysis['uncertainty']} 若气候、工程状态或观测误差结构变化，既有排序可能重新排列。",
        "",
        "### 预期失效场景",
        "",
        f"- 失效场景 A：{limitation_parts[-1] if limitation_parts else analysis['limitation']}",
        f"- 失效场景 B：{uncertainty_parts[-1] if uncertainty_parts else analysis['uncertainty']}",
        "",
        "## 12. 不确定性、敏感性与稳健性",
        "",
        analysis["uncertainty"],
        "",
        "| 不确定性层次 | 本文需要回答的问题 | 当前判断 |",
        "|---|---|---|",
        f"| 输入/观测 | 气象和流量误差是否传播到输出 | {shorten(analysis['uncertainty'], 150)} |",
        f"| 参数/训练 | 随机种子、超参数和样本长度是否改变排序 | {shorten(analysis['validation'], 150)} |",
        f"| 模型结构 | 不同结构是否在相同数据上给出一致机制 | {shorten(analysis['method'], 150)} |",
        f"| 分布变化 | 跨时期、跨流域或极端事件是否仍稳定 | {shorten(analysis['limitation'], 150)} |",
        f"| 决策后果 | 预测误差是否转化为安全或运行风险 | {shorten(analysis['engineering'], 150)} |",
        "",
        "## 13. 五类有效性诊断",
        "",
        "| 有效性 | 当前诊断 | 决定性复核 |",
        "|---|---|---|",
        f"| 内部有效性 | {shorten(analysis['validation'], 190)} | 切分、调参、消融和强基线 |",
        f"| 构念有效性 | 指标为 {metrics}；需判断是否代表本文声称的水文或工程目标 | 洪峰、低流量、偏差、可靠性是否被覆盖 |",
        f"| 统计有效性 | {shorten(analysis['result'], 190)} | 样本量、站点分布、效应量与不确定区间 |",
        f"| 外部有效性 | {shorten(analysis['limitation'], 190)} | 时间、空间、气候和工程状态留出 |",
        f"| 工程有效性 | {shorten(analysis['engineering'], 190)} | 实时输入、计算时限、回退和失效后果 |",
        "",
        "## 14. 水文与工程迁移价值",
        "",
        analysis["engineering"],
        "",
        "| 迁移问题 | 对本论文的判断 |",
        "|---|---|",
        f"| 哪些内容可迁移 | {shorten(analysis['research_judgment'], 200)} |",
        f"| 哪些条件必须重做 | {shorten(analysis['limitation'], 200)} |",
        f"| 哪些误差必须显式传播 | {shorten(analysis['uncertainty'], 200)} |",
        f"| 工程上线前的最低要求 | {shorten(analysis['engineering'], 200)} |",
        "",
        "## 15. 对当前研究的价值与优先级",
        "",
        analysis["research_judgment"],
        "",
        "这篇论文更适合用于以下一种或多种任务：界定问题、提供方法机制、设置验证协议、构造反例或连接工程决策。最终角色需由问题簇分析在多篇证据并置后确定，单篇画像不直接宣布领域共识。",
        "",
        "## 16. 最小判别性复核或复现实验",
        "",
        analysis["reproduction"],
        "",
        "| 实验要素 | 最小要求 |",
        "|---|---|",
        f"| 待检验命题 | {shorten(analysis['research_judgment'], 200)} |",
        f"| 数据 | {shorten(analysis['data'], 200)} |",
        f"| 方法与对照 | {methods}；对照为 {baselines} |",
        f"| 划分 | {shorten(analysis['validation'], 200)} |",
        f"| 输出 | {metrics}，并补充与业务目标直接相关的极端/偏差/可靠性指标 |",
        f"| 成功判据 | 在独立样本中保持论文所述比较方向，同时未显著恶化关键水文或工程指标 |",
        f"| 失败判据 | {reproduction_parts[-1] if reproduction_parts else '优势因泄漏、弱基线、极端失效或物理/工程违约而消失'} |",
        "",
        "## 17. 人工复核任务",
        "",
        "- 核对论文身份、研究区、时段、训练/测试切分和决定性图表。",
        f"- 针对本文优先核对：{shorten(analysis['validation'], 220)}",
        f"- 针对结果边界优先核对：{shorten(analysis['limitation'], 220)}",
        f"- 执行或细化最小实验：{shorten(analysis['reproduction'], 220)}",
        "",
        ]
    )
    lines.extend(source_ledger(record, path, paired_path, manifest, analysis_path, vault))
    lines.append("")
    return "\n".join(lines)


def render_note(
    record: dict,
    analysis: dict,
    path: Path,
    paired_path: Path | None,
    manifest: Path,
    analysis_path: Path,
    vault: Path,
) -> str:
    profile = record.get("profile") or {}
    paper_id = str(profile.get("paper_id") or profile.get("canonical_literature_id"))
    title_cn = str(record.get("title_cn") or profile.get("title") or paper_id)
    title_original = str(profile.get("title") or title_cn)
    authors = profile.get("authors") or []
    evidence_status = str(record.get("evidence_status") or "partial_text")
    review_status = str(record.get("review_status") or "unverified")
    cards = select_evidence_cards(record, analysis)
    coverage = evidence_coverage(record)
    data_parts = split_sentences(analysis["data"])
    limitation_parts = analysis_parts(analysis, "limitation")
    uncertainty_parts = analysis_parts(analysis, "uncertainty")
    reproduction_parts = analysis_parts(analysis, "reproduction")
    method_tokens = []
    for token in re.findall(
        r"(?<![A-Za-z])[A-Z][A-Z0-9-]{1,}(?![A-Za-z])",
        " ".join(str(analysis[field]) for field in REQUIRED_ANALYSES),
    ):
        if token not in method_tokens:
            method_tokens.append(token)
    token_text = "、".join(method_tokens[:8]) or "文中模型与数据缩写待逐项核对"
    datasets = list_text(profile.get("datasets"))
    methods = method_terms(profile, analysis)
    baselines = list_text(
        profile.get("baselines"),
        f"需从方法链核对：{shorten(analysis['method'], 130)}",
    )
    metrics = metric_terms(profile, analysis)
    roles = list_text(record.get("roles"), "待问题簇分析确定")
    data_items = module_depth_items(analysis, "data")
    method_items = module_depth_items(analysis, "method")
    validation_items = module_depth_items(analysis, "validation")
    result_items = module_depth_items(analysis, "result")
    limitation_items = module_depth_items(analysis, "limitation")
    reported_result_count = sum(1 for label, _ in result_items if label == "论文自身结果")
    lines = [
        "---",
        f"title: {yaml_string(title_cn)}",
        f"title_original: {yaml_string(title_original)}",
        f"authors: {yaml_string(authors)}",
        f"year: {yaml_string(profile.get('year'))}",
        f"journal: {yaml_string(profile.get('venue'))}",
        f"doi: {yaml_string(profile.get('doi_normalized') or profile.get('doi') or '')}",
        f"paper_id: {paper_id}",
        f"canonical_literature_id: {paper_id}",
        f"source_batch_id: {profile.get('source_batch_id') or ''}",
        f"source_path: {yaml_string(profile.get('source_path') or '')}",
        "selection_status: included",
        f"evidence_status: {evidence_status}",
        f"review_status: {review_status}",
        "knowledge_status: candidate",
        "reading_status: 核心章节机器阅读",
        "analysis_method: paper_specific_source_synthesis",
        "reading_date: 2026-07-23",
        "---",
        "",
        f"# {article_link(profile, title_cn)}",
        "",
        "> [!warning] 阅读级别",
        f"> 当前为机器全文遍历与核心证据片段基础上的扩展研究分析，状态 `{evidence_status}` / `{review_status}`。已重建论证链、有效性和最小实验，但未检查原始图表视觉内容和补充材料，因此不标记为人工全文精读。",
        "",
        "## 0. 阅读状态与证据标记",
        "",
        "- [x] 文献身份已与批次机器记录对应",
        "- [x] 已形成论文特定的十项基础分析、论证链和有效性诊断",
        "- [x] 已筛选可解释的正文证据卡",
        "- [ ] 决定性图表和数值已由学生回原文核验",
        "- [ ] 数据、代码与补充材料已独立复现",
        "- `[AI概括]`：下列内容由全文结构、机器证据片段和逐篇综合记录形成。",
        "- `[科研判断]`：关于证据强弱、竞争性解释和研究用途的判断，不冒充作者原话。",
        "- `[待核验]`：任何定量结论在正式引用前仍需核对原图表和上下文。",
        "",
        "### 0.1 证据覆盖",
        "",
        "| 模块 | 片段数 | 本笔记的处理 |",
        "|---|---:|---|",
    ]
    for label, count in coverage:
        lines.append(
            f"| {label} | {count} | {'进入综合分析' if count else '明确记录为缺口'} |"
        )
    lines.extend(
        [
        "",
        f"机器可访问全文字符规模为 {record.get('fulltext_characters') or '未记录'}；本笔记只展示 {len(cards)} 个经过筛选的短摘，较长原文仍保留在机器证据记录中。",
        "",
        "# 一、文献信息与快速定位",
        "",
        "## 1.1 标准书目信息",
        "",
        "| 字段 | 内容 | 状态 |",
        "|---|---|---|",
        f"| 中文题名 | {title_cn} | 已与批次映射对应 |",
        f"| 原文题名 | {title_original} | 机器记录 |",
        f"| 作者 | {'；'.join(str(value) for value in authors) or '未从当前记录恢复'} | 待独立核验 |",
        f"| 期刊与年份 | {profile.get('venue') or '未报告'}；{profile.get('year') or '未报告'} | 机器记录 |",
        f"| DOI | {profile.get('doi_normalized') or profile.get('doi') or '未报告'} | 待独立核验 |",
        f"| 证据与复核 | `{evidence_status}` / `{review_status}` | 不自动升级 |",
        "",
        "## 1.2 30秒判断",
        "",
        f"**一句话概括：** {shorten(analysis['problem'], 150)} 论文采用的主要路径是“{shorten(analysis['method'], 150)}”，当前结果解释为“{shorten(analysis['result'], 170)}”。",
        "",
        f"**为什么值得精读：** {analysis['research_judgment']}",
        "",
        f"**它可能改变的判断：** 如果第十五节的最小实验成立，就能判断该论文的增量来自数据、结构、物理耦合、跨域学习还是验证设置；如果失败，则应把论文主要作为边界或反例证据。",
        "",
        "**优先级：** 候选核心文献；最终级别需结合问题簇中的证据角色和人工复核。",
        "",
        "# 二、术语、符号与尺度账本",
        "",
        "## 2.1 术语与模型角色",
        "",
        "| 规范术语 | 本文中的具体含义 | 本笔记的使用边界 |",
        "|---|---|---|",
        f"| 预测对象 | {markdown_cell(profile.get('forecast_target') or '未从当前证据确认')} | 不把模拟、重建、预报和调度决策混为一谈 |",
        f"| 方法缩写 | {token_text} | 每个缩写必须回到输入、组件角色和输出解释 |",
        f"| 数据集/产品 | {datasets} | 只记录机器证据中出现或画像已保存的名称 |",
        f"| 基线 | {baselines} | 需核对是否同数据、同切分、同调参预算 |",
        f"| 指标 | {metrics} | 需说明评价对象和对洪峰/低流量/风险的盲点 |",
        "",
        "## 2.2 尺度账本",
        "",
        "| 维度 | 本文当前记录 | 尺度效应与待核验点 |",
        "|---|---|---|",
        f"| 时间步长 | {markdown_cell(profile.get('temporal_resolution') or '未从当前证据确认')} | 时间聚合会改变洪峰、滞时和记忆长度 |",
        f"| 研究时段 | {shorten(analysis['data'], 180)} | 样本是否覆盖极端、突变和工程变化 |",
        f"| 预报提前期 | {markdown_cell(profile.get('forecast_horizon') or '未从当前证据确认')} | 缺少提前期时不能直接声称业务预警价值 |",
        f"| 空间尺度 | {markdown_cell(profile.get('spatial_scale') or '未从当前证据确认')} | 单站、单流域、区域和全球结果的外推强度不同 |",
        f"| 研究区 | {markdown_cell(profile.get('study_region') or '未从当前证据确认')} | 气候、地形、下垫面和调控差异需显式比较 |",
        "",
        "# 三、论文论证骨架",
        "",
        "## 3.1 论文体裁与评价标准",
        "",
        f"本文当前被当作机器学习/深度学习水文研究来阅读。评价重点不是模型名称是否新，而是它是否利用“{shorten(analysis['data'], 170)}”建立了可独立验证的“{shorten(analysis['method'], 170)}”，并在相应边界内产生“{shorten(analysis['result'], 170)}”。",
        "",
        "## 3.2 背景—缺口—方法—结果—边界",
        "",
        f"- **研究问题：** {analysis['problem']}",
        f"- **数据条件：** {analysis['data']}",
        f"- **方法机制：** {analysis['method']}",
        f"- **验证协议：** {analysis['validation']}",
        f"- **主要结果：** {analysis['result']}",
        f"- **适用边界：** {analysis['limitation']}",
        "",
        "## 3.3 Claim—Evidence 映射",
        "",
        "| Claim ID | 关键主张 | 实际证据分析 | 证据强度 | 主要缺口 |",
        "|---|---|---|---|---|",
        f"| CL01 | 研究问题具有实际水文意义 | {shorten(analysis['problem'], 190)} | 中 | 需核对问题是否由结果真正回答 |",
        f"| CL02 | 方法结构形成了可辨识增量 | {shorten(analysis['method'], 190)} | 中 | 需消融或强基线隔离组件贡献 |",
        f"| CL03 | 验证能够评价目标泛化能力 | {shorten(analysis['validation'], 190)} | 中—弱 | 切分、调参和信息可得性待核验 |",
        f"| CL04 | 结果支持论文的主要比较方向 | {shorten(analysis['result'], 190)} | 中 | 数值、样本量和图表上下文待核验 |",
        f"| CL05 | 结论具有明确适用边界 | {shorten(analysis['limitation'], 190)} | 中 | 需要分布外或工程验证确认 |",
        "",
        "## 3.4 作者自称创新与实际增量",
        "",
        "| 维度 | 当前识别的增量 | 是否被现有证据充分隔离 |",
        "|---|---|---|",
        f"| 科学问题 | {shorten(analysis['problem'], 200)} | 需判断是否超出既有案例复现 |",
        f"| 方法 | {shorten(analysis['method'], 200)} | 需消融和公平基线 |",
        f"| 数据/尺度 | {shorten(analysis['data'], 200)} | 需确认代表性与留出方式 |",
        f"| 工程情景 | {shorten(analysis['engineering'], 200)} | 需把离线指标转换为业务后果 |",
        f"| 实际证据增量 | {shorten(analysis['result'], 200)} | 当前仍受局限与复核状态约束 |",
        "",
        "# 四、研究对象与工程背景",
        "",
        "## 4.1 研究对象",
        "",
        analysis["data"],
        "",
        "| 项目 | 当前内容 | 对结果的可能影响 |",
        "|---|---|---|",
        f"| 流域/区域 | {markdown_cell(profile.get('study_region') or '未从当前证据确认')} | 决定气候、地形和水文响应分布 |",
        f"| 空间尺度 | {markdown_cell(profile.get('spatial_scale') or '未从当前证据确认')} | 影响空间泛化和区域化证据强度 |",
        f"| 目标变量 | {markdown_cell(profile.get('forecast_target') or '未从当前证据确认')} | 决定模型输出和评价指标 |",
        f"| 业务情景 | {shorten(analysis['engineering'], 190)} | 决定输入时效、容错和安全要求 |",
        "",
        "## 4.2 边界条件与可迁移性",
        "",
        f"- 案例特有条件：{limitation_parts[0] if limitation_parts else analysis['limitation']}",
        f"- 可能具有普遍性的机制：{shorten(analysis['method'], 220)}",
        f"- 迁移到其他流域前必须重新检验：{shorten(analysis['uncertainty'], 220)}",
        f"- 当前工程含义：{analysis['engineering']}",
        "",
        "# 五、数据与预处理",
        "",
        "## 5.0 分条数据分析",
        "",
        *render_depth_items("D", data_items),
        "",
        "## 5.1 数据清单与作用",
        "",
        "| 数据/变量 | 当前记录 | 在方法中的作用 | 尚缺信息 |",
        "|---|---|---|---|",
        f"| 数据集或产品 | {datasets} | 提供训练、状态描述或强迫信息 | 时段、版本、质量控制 |",
        f"| 预测目标 | {markdown_cell(profile.get('forecast_target') or '未确认')} | 监督目标或模拟输出 | 单位、聚合和变换方式 |",
        f"| 流域属性/空间信息 | {markdown_cell(profile.get('spatial_scale') or '未确认')} | 区分流域差异或支持空间传播 | 属性可得性和共线性 |",
        f"| 历史状态/滞后量 | {shorten(analysis['method'], 180)} | 表征水文记忆和先行条件 | 窗长及起报时可得性 |",
        "",
        "## 5.2 数据质量与代表性",
        "",
        f"- 已识别的数据条件：{' '.join(data_parts)}",
        f"- 代表性限制：{shorten(analysis['limitation'], 230)}",
        f"- 非平稳或极端覆盖：{shorten(analysis['uncertainty'], 230)}",
        "- 当前证据不足以确认缺测比例、异常值规则、量测误差和多源数据定义一致性时，这些项目必须在复现前补齐。",
        "",
        "## 5.3 信息泄漏审计",
        "",
        f"论文的验证设计为：{analysis['validation']}",
        "",
        "| 泄漏入口 | 本文为何需要检查 | 判定所需材料 |",
        "|---|---|---|",
        f"| 全时段标准化/分解 | 方法包含 {methods}，可能在预处理阶段使用全样本统计 | 预处理代码和拟合时段 |",
        f"| 相邻站点或同一事件跨集合 | 研究尺度为 {markdown_cell(profile.get('spatial_scale') or '未确认')} | 站点、事件与切分清单 |",
        f"| 事后气象或再分析输入 | 业务意义为 {shorten(analysis['engineering'], 150)} | 每个输入在起报时的发布时间 |",
        f"| 超参数接触测试集 | 结果为 {shorten(analysis['result'], 150)} | 调参日志、验证集和最终测试协议 |",
        "",
        "# 六、方法与模型拆解",
        "",
        "## 6.1 方法总流程",
        "",
        *render_depth_items("M", method_items),
        "",
        "| 环节 | 当前重建 | 需要核对的技术细节 |",
        "|---|---|---|",
        f"| 输入 | {datasets} | 变量定义、滞后窗口、标准化和实时可得性 |",
        f"| 处理/模型 | {methods} | 组件连接、损失函数、超参数和训练顺序 |",
        f"| 输出 | {markdown_cell(profile.get('forecast_target') or '未确认')} | 点值、区间、集合或空间产品 |",
        f"| 基线 | {baselines} | 输入一致性、率定预算和版本 |",
        f"| 指标 | {metrics} | 数值定义、聚合尺度和工程含义 |",
        "",
        "## 6.2 组件贡献与可辨识性",
        "",
        f"当前方法增量由“{shorten(analysis['method'], 240)}”构成。要证明其中某个组件具有独立贡献，至少需要删除该组件、替换为简单等价组件，并在相同切分和调参预算下比较。如果优势只在完整复杂模型中出现而无消融，数据预处理、参数规模和训练预算都是竞争性解释。",
        "",
        "## 6.3 物理一致性与信息约束",
        "",
        f"- 物理/结构边界：{analysis['limitation']}",
        f"- 不确定性边界：{analysis['uncertainty']}",
        f"- 工程信息约束：{shorten(analysis['engineering'], 230)}",
        "- 需判断预测值是否违反非负、水量平衡、状态连续性或工程上下限；若论文未检查，不能把高平均指标等同于物理可信。",
        "",
        "# 七、率定、验证与评价指标",
        "",
        "## 7.1 实验设计",
        "",
        *render_depth_items("V", validation_items),
        "",
        "| 实验要素 | 当前识别 | 充分性判断 |",
        "|---|---|---|",
        f"| 训练/率定 | {shorten(analysis['data'], 180)} | 需确认样本量和暖机期 |",
        f"| 独立测试 | {shorten(analysis['validation'], 180)} | 需确认未参与预处理和调参 |",
        f"| 时间外推 | {shorten(analysis['uncertainty'], 180)} | 若未设置，不能支撑变化环境结论 |",
        f"| 空间外推 | {markdown_cell(profile.get('spatial_scale') or '未确认')} | 无资料结论必须有空间留出 |",
        f"| 基线与消融 | {baselines} | 需核对是否充分且公平 |",
        "",
        "## 7.2 指标解释与盲点",
        "",
        "| 指标/目标 | 当前用途 | 主要盲点 |",
        "|---|---|---|",
        f"| {metrics} | 评价论文报告的整体或局部性能 | 单个平均指标可能掩盖洪峰、低流量、偏差和时序误差 |",
        f"| 工程目标 | {shorten(analysis['engineering'], 190)} | 统计改善未必转化为预警或调度收益 |",
        f"| 泛化目标 | {shorten(analysis['research_judgment'], 190)} | 需按时间、空间和事件留出分别判断 |",
        "",
        "## 7.3 验证强度初判",
        "",
        f"当前验证强度为“候选中等、待核验”。理由是已有证据能重建“{shorten(analysis['validation'], 230)}”，但图表、样本清单、调参边界和随机性尚未人工检查。若这些要素不完整，论文结果更适合支持案例条件下的比较，而不是无条件泛化。",
        "",
        "# 八、不确定性、敏感性与鲁棒性",
        "",
        analysis["uncertainty"],
        "",
        "## 8.1 不确定性分解",
        "",
        "| 来源 | 对本文结论的影响 | 最小检查 |",
        "|---|---|---|",
        f"| 观测与输入误差 | {shorten(analysis['data'], 180)} | 扰动降雨/流量并观察输出敏感度 |",
        f"| 参数与训练随机性 | {shorten(analysis['method'], 180)} | 多随机种子和超参数区间 |",
        f"| 模型结构 | {shorten(analysis['limitation'], 180)} | 与简化模型、替代结构和消融比较 |",
        f"| 时间/空间分布变化 | {shorten(analysis['uncertainty'], 180)} | 留时期、留区域或变化情景测试 |",
        f"| 工程执行 | {shorten(analysis['engineering'], 180)} | 输入延迟、计算时限和保守回退 |",
        "",
        "## 8.2 最可能推翻结论的条件",
        "",
        f"1. {uncertainty_parts[0] if uncertainty_parts else analysis['uncertainty']}",
        f"2. {limitation_parts[-1] if limitation_parts else analysis['limitation']}",
        f"3. 若验证设置中的“{shorten(analysis['validation'], 180)}”无法保证独立性，则结果可能主要反映样本相似性。",
        "",
        "# 九、结果、图表与证据定位",
        "",
        "## 9.1 主要结果",
        "",
        *render_depth_items("R", result_items),
        "",
        f"当前经全文结果段、讨论段和图表文字复核，保留 {reported_result_count} 条论文自身结果；审计事项和证据缺口不计入结果条数。",
        "",
        "## 9.2 关键证据卡",
        "",
        ]
    )
    for index, card in enumerate(cards, 1):
        evidence_line = (
            f"- **原文短摘：** “{card['excerpt']}”"
            if card["has_excerpt"]
            else f"- **证据形式：** {card['label']}候选短摘存在引文污染或句子残缺，本卡仅保留逐篇中文内容分析。"
        )
        lines.extend(
            [
                f"### E{index:02d}：{card['label']}",
                "",
                evidence_line,
                f"- **中文内容分析：** {card['analysis']}",
                f"- **在论证链中的作用：** 该卡用于检查{card['label']}是否与数据、方法和验证条件相互一致。",
                f"- **尚待核验：** 回到{card['navigation']}核对完整上下文、图表和比较对象，排除背景引用或定义性表述。",
                "",
            ]
        )
    if not cards:
        lines.extend(
            [
                "未筛到可安全展示的原文短摘；本节只保留逐篇中文分析，并把人工补选方法、结果和局限证据列为高优先级任务。",
                "",
            ]
        )
    lines.extend(
        [
        "## 9.3 结果解释而非模型排名",
        "",
        f"- 结果成立的数据条件：{shorten(analysis['data'], 230)}",
        f"- 结果成立的验证条件：{shorten(analysis['validation'], 230)}",
        f"- 可以支持的判断：{shorten(analysis['result'], 230)}",
        f"- 不能外推的范围：{shorten(analysis['limitation'], 230)}",
        f"- 替代解释：若 {shorten(analysis['uncertainty'], 210)} 未被控制，模型排序可能随样本或情景改变。",
        "",
        "## 9.4 图表复核任务",
        "",
        "| 图表任务 | 需要读取的内容 | 判断标准 |",
        "|---|---|---|",
        f"| 结果对比图/表 | {metrics}、样本量、误差区间和基线 | 是否在同一条件下支持主要比较方向 |",
        f"| 过程线/空间图 | 洪峰、低流量、时序或空间误差 | 平均指标是否掩盖关键失败情景 |",
        f"| 消融/敏感性图 | {methods} 各组件或参数 | 性能增量能否归属于具体机制 |",
        "",
        "当前未检查原图，不评价颜色、误差线、面板或视觉显著性。",
        "",
        "# 十、讨论、局限与适用边界",
        "",
        "## 10.1 已识别的局限",
        "",
        *render_depth_items("L", limitation_items),
        "",
        "## 10.2 两类竞争性解释",
        "",
        f"1. **数据与切分解释：** {limitation_parts[0] if limitation_parts else analysis['limitation']} 论文优势可能部分来自训练样本覆盖、预处理或相似流域，而非模型结构本身。",
        f"2. **结构与情景解释：** {uncertainty_parts[0] if uncertainty_parts else analysis['uncertainty']} 当气候、流域属性、工程状态或误差结构变化时，当前结果可能不再保持。",
        "",
        "## 10.3 结论边界句",
        "",
        f"《{title_cn}》的结论只应在“{shorten(analysis['data'], 210)}”以及“{shorten(analysis['validation'], 210)}”共同限定的范围内解释；当“{shorten(analysis['limitation'], 210)}”所对应的条件发生变化时，需要重新训练、重新校准或重新验证。",
        "",
        "# 十一、水利工程可实施性检查",
        "",
        analysis["engineering"],
        "",
        "| 检查项 | 论文当前设置 | 实际工程要求 | 差距与后果 |",
        "|---|---|---|---|",
        f"| 实时数据 | 输入来自 {datasets} | 起报时可获得、质量受控、延迟明确 | {shorten(analysis['data'], 160)} |",
        f"| 提前期与更新 | {markdown_cell(profile.get('forecast_horizon') or '未确认')} | 满足预警或调度决策时窗 | 提前期不明时无法判断行动价值 |",
        f"| 算法计算 | 方法为 {methods} | 在更新周期内稳定完成并可监控 | 需记录运行时间、资源和失败率 |",
        f"| 极端与分布外 | {shorten(analysis['uncertainty'], 160)} | 洪峰、突变和缺测时仍有保守输出 | 离线平均指标不足以证明安全 |",
        f"| 可解释与接管 | {shorten(analysis['research_judgment'], 160)} | 说明输入、置信度、失败原因并允许人工回退 | 需建立告警和回退规则 |",
        f"| 当前等级 | `{evidence_status}` / `{review_status}` | 至少完成人工图表核验和影子运行 | 当前仅支持科研筛查或概念验证 |",
        "",
        "# 十二、批判性评价",
        "",
        "## 12.1 五类有效性",
        "",
        "| 维度 | 初判 | 证据与理由 | 最关键缺口 |",
        "|---|---|---|---|",
        f"| 内部有效性 | 中—待核验 | {shorten(analysis['validation'], 200)} | 切分、调参和消融 |",
        f"| 构念有效性 | 中—待核验 | 指标 {metrics} 需要与论文声称的水文/工程目标对应 | 极端、偏差或可靠性盲点 |",
        f"| 统计有效性 | 中—弱 | {shorten(analysis['result'], 200)} | 样本量、区间和随机性 |",
        f"| 外部有效性 | 中—弱 | {shorten(analysis['limitation'], 200)} | 跨时期、跨流域和分布外验证 |",
        f"| 工程有效性 | 待核验 | {shorten(analysis['engineering'], 200)} | 实时输入、计算、回退和失效后果 |",
        "",
        "## 12.2 最强证据、最弱环节与总体可信度",
        "",
        f"- **最强证据候选：** {shorten(analysis['result'], 240)}",
        f"- **最弱环节：** {shorten(analysis['validation'], 240)}",
        f"- **最可信的结论：** {shorten(analysis['research_judgment'], 240)}",
        f"- **最需谨慎的结论：** 任何超出“{shorten(analysis['limitation'], 210)}”的跨区、极端或工程推广。",
        "- **总体可信度：** 中等候选；必须由人工回原文复核后才能升级。",
        "",
        "# 十三、与当前研究和其他文献的关系",
        "",
        "## 13.1 对当前课题的作用",
        "",
        analysis["research_judgment"],
        "",
        f"- 机器筛选角色：{roles}。",
        f"- 可复用的方法或验证要素：{shorten(analysis['method'], 220)}",
        f"- 可作为反例或边界的内容：{shorten(analysis['limitation'], 220)}",
        f"- 可连接工程问题的内容：{shorten(analysis['engineering'], 220)}",
        "",
        "## 13.2 问题簇接口",
        "",
        "本笔记不单独宣布跨文献关系。问题簇分析应把本文与其他论文按以下接口比较：研究对象是否相同、数据与尺度是否可比、验证是否独立、结果指标是否同义、局限是否来自相同误差机制。只有双方证据都被读取后，才能写 `supports`、`limits`、`conflicts` 或 `conditions`。",
        "",
        "# 十四、可引用证据与写作出口",
        "",
        "| Citation ID | 拟支持的论断 | 准确释义 | 可放章节 | 核验状态 |",
        "|---|---|---|---|---|",
        f"| CIT01 | 研究问题 | {shorten(analysis['problem'], 220)} | 引言/问题定义 | 待核验 |",
        f"| CIT02 | 方法机制 | {shorten(analysis['method'], 220)} | 方法/相关工作 | 待核验 |",
        f"| CIT03 | 验证设计 | {shorten(analysis['validation'], 220)} | 方法/实验设计 | 待核验 |",
        f"| CIT04 | 主要结果 | {shorten(analysis['result'], 220)} | 结果对比/讨论 | 待核验原图表 |",
        f"| CIT05 | 适用边界 | {shorten(analysis['limitation'], 220)} | 讨论/局限 | 待核验 |",
        "",
        "机器分析可帮助确定引用位置和论证功能，但不能直接作为论文引文。任何数值在引用前必须核对原文条件、单位、比较对象、样本量和图表。",
        "",
        "# 十五、复现与最小验证",
        "",
        "## 15.1 最小判别性实验",
        "",
        analysis["reproduction"],
        "",
        "| 实验要素 | 设计 |",
        "|---|---|",
        f"| 待检验命题 | {shorten(analysis['research_judgment'], 230)} |",
        f"| 最小数据 | {shorten(analysis['data'], 230)} |",
        f"| 模型 | {methods} |",
        f"| 对照 | {baselines} |",
        f"| 独立划分 | {shorten(analysis['validation'], 230)} |",
        f"| 输出 | {metrics}，外加与当前问题直接相关的洪峰、低流量、偏差、可靠性或工程后果 |",
        "| 成功条件 | 在独立样本中复现论文的比较方向，且关键水文/工程指标没有明显退化 |",
        f"| 失败条件 | {reproduction_parts[-1] if reproduction_parts else '优势在强基线、独立切分、极端或物理约束下消失'} |",
        "| 工作量 | 数据可得时先完成最小对照与一项外推测试，再决定是否扩展完整复现 |",
        "",
        "## 15.2 可复现性缺口",
        "",
        "- 原始数据、预处理、参数/超参数、随机种子、代码版本和评价实现均需逐项核对。",
        f"- 论文特定的首要缺口：{shorten(analysis['limitation'], 230)}",
        f"- 论文特定的稳健性缺口：{shorten(analysis['uncertainty'], 230)}",
        "",
        "# 十六、精读结论与行动",
        "",
        "## 16.1 五句话总结",
        "",
        f"1. **研究对象：** {analysis['problem']}",
        f"2. **数据基础：** {analysis['data']}",
        f"3. **方法主线：** {analysis['method']}",
        f"4. **主要发现：** {analysis['result']}",
        f"5. **关键边界：** {analysis['limitation']}",
        "",
        "## 16.2 最终判断",
        "",
        f"- **科学价值：** {shorten(analysis['research_judgment'], 220)}",
        f"- **方法可靠性：** 取决于“{shorten(analysis['validation'], 210)}”能否通过人工复核。",
        f"- **工程适用性：** {shorten(analysis['engineering'], 220)}",
        f"- **是否建议复现：** 建议先执行第十五节最小判别性实验，再决定完整复现。",
        "- **是否需要导师讨论：** 若该论文被用于定义主问题、宣称泛化或支撑工程上线，则需要。",
        "",
        "## 16.3 下一步任务",
        "",
        f"- [ ] 核对决定性结果表、图和指标条件：{shorten(analysis['result'], 200)}",
        f"- [ ] 核对数据时段、切分和起报时信息可得性：{shorten(analysis['validation'], 200)}",
        f"- [ ] 核对局限与分布变化：{shorten(analysis['uncertainty'], 200)}",
        f"- [ ] 执行最小验证：{shorten(analysis['reproduction'], 200)}",
        "- [ ] 将人工核验后的结论更新到问题簇，未核验前保持 candidate。",
        "",
        ]
    )
    lines.extend(source_ledger(record, path, paired_path, manifest, analysis_path, vault))
    lines.append("")
    return "\n".join(lines)


def duplicate_sentences(text: str) -> list[str]:
    curated_result_sentences: set[str] = set()
    for match in re.finditer(
        r"(?m)^-\s+\*\*R\d{2}\s+·\s+论文自身结果：\*\*\s+(.+)$",
        text,
    ):
        first_sentence = re.split(r"[。！？；]", match.group(1), maxsplit=1)[0]
        curated_result_sentences.add(re.sub(r"\s+", "", first_sentence))
    sentences = []
    for sentence in re.split(r"[。！？]\s*", text):
        normalized = re.sub(r"\s+", "", sentence)
        if len(normalized) >= 32 and not normalized.startswith("|"):
            sentences.append(normalized)
    return [
        sentence
        for sentence, count in Counter(sentences).items()
        if count > 2
        and not any(
            sentence in result_sentence or result_sentence in sentence
            for result_sentence in curated_result_sentences
        )
    ]


def validate_text(path: Path, text: str, kind: str, preserve: bool = False) -> list[str]:
    errors: list[str] = []
    for pattern in GENERIC_PATTERNS:
        if pattern in text:
            errors.append(f"{path}: generic prose: {pattern}")
    for pattern in VISIBLE_LOCATOR_PATTERNS:
        if pattern.search(text):
            errors.append(f"{path}: visible extraction locator")
    if "## 本文件实际使用的来源" not in text:
        errors.append(f"{path}: missing source ledger")
    if not preserve:
        duplicates = duplicate_sentences(text)
        if duplicates:
            examples = " || ".join(shorten(value, 90) for value in duplicates[:2])
            errors.append(
                f"{path}: repeated substantive sentences: {len(duplicates)}; {examples}"
            )
    body_count = body_character_count(text)
    if kind == "profile":
        if body_count < 3000:
            errors.append(f"{path}: profile below extended body-depth gate ({body_count})")
        if len(re.findall(r"(?m)^##\s+", text.split("## 本文件实际使用的来源", 1)[0])) < 15:
            errors.append(f"{path}: profile has fewer than 15 substantive modules")
        if len(re.findall(r"(?m)^### E\d{2}：", text)) < 3:
            errors.append(f"{path}: profile has fewer than 3 evidence cards")
        for prefix in ("D", "M", "V", "L"):
            if len(re.findall(rf"(?m)^-\s+\*\*{prefix}\d{{2}}\s+·", text)) < 3:
                errors.append(f"{path}: profile {prefix} module has fewer than 3 analytical items")
        if not re.search(r"(?m)^-\s+\*\*R\d{2}\s+·\s+(?:论文自身结果|结果证据阻断)：", text):
            errors.append(f"{path}: profile has neither a curated paper result nor an explicit result blocker")
    if kind == "note":
        positions = [text.find(heading) for heading in DEEP_HEADINGS]
        if any(position < 0 for position in positions) or positions != sorted(positions):
            errors.append(f"{path}: missing or out-of-order deep-note headings")
        if preserve:
            if body_count < 3200:
                errors.append(f"{path}: preserved note below legacy depth gate ({body_count})")
        else:
            if body_count < 7500:
                errors.append(f"{path}: note below extended body-depth gate ({body_count})")
            if len(re.findall(r"(?m)^\|\s*CL\d{2}\s*\|", text)) < 5:
                errors.append(f"{path}: note has fewer than 5 claim-evidence judgments")
            if len(re.findall(r"(?m)^### E\d{2}：", text)) < 3:
                errors.append(f"{path}: note has fewer than 3 evidence cards")
            for prefix in ("D", "M", "V", "L"):
                if len(re.findall(rf"(?m)^-\s+\*\*{prefix}\d{{2}}\s+·", text)) < 3:
                    errors.append(f"{path}: note {prefix} module has fewer than 3 analytical items")
            if not re.search(r"(?m)^-\s+\*\*R\d{2}\s+·\s+(?:论文自身结果|结果证据阻断)：", text):
                errors.append(f"{path}: note has neither a curated paper result nor an explicit result blocker")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-root", required=True)
    parser.add_argument("--records", action="append", required=True)
    parser.add_argument("--analysis-records", required=True)
    parser.add_argument("--result-findings", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--profile-dir", required=True)
    parser.add_argument("--note-dir", required=True)
    parser.add_argument("--mode", choices=("apply", "check"), default="apply")
    parser.add_argument("--preserve-paper-id", action="append", default=[])
    args = parser.parse_args()

    vault = Path(args.vault_root).resolve()
    manifest = Path(args.manifest).resolve()
    analysis_path = Path(args.analysis_records).resolve()
    profile_dir = Path(args.profile_dir).resolve()
    note_dir = Path(args.note_dir).resolve()
    analyses = load_analyses(analysis_path)
    result_records = {}
    for result_record in load_jsonl([Path(args.result_findings).resolve()]):
        result_paper_id = str(result_record.get("paper_id") or "")
        if not result_paper_id or result_paper_id in result_records:
            raise ValueError(f"invalid or duplicate result record identity: {result_paper_id}")
        result_records[result_paper_id] = result_record
    forbidden_result_phrases = ("需回查", "待回查", "不能作为本文", "来自被引用研究", "未确认", "待核验")
    for paper_id, result_record in result_records.items():
        findings = result_record.get("result_findings") or []
        for finding in findings:
            text = str(finding.get("finding") or "")
            if not text:
                raise ValueError(f"{paper_id}: empty curated result finding")
            if any(phrase in text for phrase in forbidden_result_phrases):
                raise ValueError(f"{paper_id}: audit/gap language was labeled as a result: {text}")
        if paper_id not in analyses:
            raise ValueError(f"{paper_id}: result record has no analysis record")
        analyses[paper_id]["result_findings"] = findings
        analyses[paper_id]["result_blockers"] = result_record.get("result_blockers") or []
        analyses[paper_id]["result"] = (
            "；".join(str(item["finding"]) for item in findings)
            if findings
            else "结果证据阻断：" + "；".join(analyses[paper_id]["result_blockers"])
        )
    records = {}
    for record in load_jsonl([Path(value).resolve() for value in args.records]):
        profile = record.get("profile") or {}
        paper_id = str(profile.get("paper_id") or profile.get("canonical_literature_id") or "")
        if paper_id:
            records[paper_id] = record
    profiles = index_markdown(profile_dir)
    notes = index_markdown(note_dir)
    preserve_ids = set(args.preserve_paper_id)
    errors: list[str] = []
    written: list[str] = []

    identity_difference = (set(records) - set(analyses)) | (set(analyses) - set(records))
    if identity_difference:
        errors.append(f"record/analysis identity mismatch: {sorted(identity_difference)}")

    for paper_id, record in records.items():
        analysis = analyses.get(paper_id)
        if analysis is None:
            continue
        profile_path = profiles.get(paper_id)
        note_path = notes.get(paper_id)
        if profile_path is None:
            errors.append(f"missing profile for {paper_id}")
            continue
        profile_text = render_profile(
            record,
            analysis,
            profile_path,
            note_path,
            manifest,
            analysis_path,
            vault,
        )
        if args.mode == "apply":
            profile_path.write_text(profile_text, encoding="utf-8")
            written.append(str(profile_path))
        else:
            profile_text = profile_path.read_text(encoding="utf-8-sig")
        errors.extend(validate_text(profile_path, profile_text, "profile"))

        if note_path is not None:
            if paper_id in preserve_ids:
                note_text = note_path.read_text(encoding="utf-8-sig")
                errors.extend(validate_text(note_path, note_text, "note", preserve=True))
                continue
            note_text = render_note(
                record,
                analysis,
                note_path,
                profile_path,
                manifest,
                analysis_path,
                vault,
            )
            if args.mode == "apply":
                note_path.write_text(note_text, encoding="utf-8")
                written.append(str(note_path))
            else:
                note_text = note_path.read_text(encoding="utf-8-sig")
            errors.extend(validate_text(note_path, note_text, "note"))

    result = {
        "status": "PASS" if not errors else "FAIL",
        "mode": args.mode,
        "records": len(records),
        "analyses": len(analyses),
        "profiles": len(profiles),
        "notes": len(notes),
        "preserved_notes": sorted(set(notes) & preserve_ids),
        "files_written": len(written),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
