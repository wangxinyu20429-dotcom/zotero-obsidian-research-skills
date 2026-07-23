#!/usr/bin/env python3
"""Build full-text-grounded Obsidian profiles and five-dimension core selection."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from pathlib import Path


GROUPS = {
    "problem": ["objective", "aim", "research question", "we investigate", "we examine", "this study"],
    "data": ["dataset", "study area", "catchment", "basin", "observations", "data were", "data set", "stations", "gauges", "study period"],
    "method": ["method", "model", "modelling", "modeling", "architecture", "input", "training", "algorithm", "framework"],
    "validation": ["validation", "test period", "testing period", "cross-validation", "holdout", "split experiment", "benchmark"],
    "result": ["results show", "outperform", "improv", "nse", "kge", "rmse", "mae", "performance", "accuracy"],
    "limitation": ["limitation", "however", "fail", "challenge", "uncertain", "shortcoming", "future work", "remains"],
    "uncertainty": ["uncertainty", "robust", "sensitivity", "extreme", "flood", "drought", "distribution shift"],
    "availability": ["data availability", "code availability", "github", "repository", "available at", "open-source"],
}

SECTION_HINTS = {
    "problem": ["abstract", "introduction", "objective", "aim"],
    "data": ["data", "dataset", "study area", "materials", "catchment", "basin"],
    "method": ["method", "model", "approach", "framework", "architecture"],
    "validation": ["experiment", "validation", "evaluation", "training", "model setup", "benchmark"],
    "result": ["result", "performance", "evaluation", "discussion", "conclusion"],
    "limitation": ["discussion", "limitation", "conclusion", "outlook"],
    "uncertainty": ["uncertainty", "robust", "sensitivity", "extreme", "discussion", "result"],
    "availability": ["availability", "data and code", "code", "repository"],
}

GROUP_LABELS = {
    "problem": "研究问题",
    "data": "数据与研究区",
    "method": "方法与模型",
    "validation": "训练与验证",
    "result": "结果",
    "limitation": "局限与失效边界",
    "uncertainty": "不确定性与鲁棒性",
    "availability": "数据与代码可得性",
}

HEADING_TRANSLATIONS = (
    (r"references|bibliography|literature cited", "参考文献"),
    (r"abstract", "摘要"),
    (r"introduction|background", "引言与背景"),
    (r"study area|catchment|basin", "研究区与流域"),
    (r"data availability|code availability|data and code", "数据与代码可得性"),
    (r"data|dataset|observation", "数据与观测"),
    (r"method|model setup|architecture|framework|approach", "方法与模型"),
    (r"experiment|validation|cross-validation|evaluation|benchmark|training", "实验与验证"),
    (r"result|performance", "结果"),
    (r"discussion", "讨论"),
    (r"limitation|outlook|future work", "局限与展望"),
    (r"conclusion|summary", "结论"),
    (r"supplement|appendix", "补充材料或附录"),
)


def load_jsonl(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()


def safe_name(item: dict, used: set[str]) -> str:
    title = str(item.get("title") or "未命名文献")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", title)
    name = re.sub(r"\s+", " ", name).strip(" .")
    year = str(item.get("year") or "").strip()
    base = (f"{year}_{name}" if year else name)[:150].rstrip(" .") or "未命名文献"
    candidate = base
    ordinal = 2
    while candidate.casefold() in used:
        candidate = f"{base[:135].rstrip()}（同名文献{ordinal}）"
        ordinal += 1
    used.add(candidate.casefold())
    return candidate


def yaml_quote(value: object) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def compact(value: object, empty: str = "未报告") -> str:
    values = text_list(value) if isinstance(value, list) else []
    if values:
        return "；".join(values)
    text = str(value or "").strip()
    return text or empty


def human_compact(value: object, fallback: str = "未报告") -> str:
    """Keep Chinese/proper-name fields; suppress unreviewed English prose in human Markdown."""
    text = compact(value, fallback)
    if re.search(r"[\u4e00-\u9fff]", text):
        return text
    words = re.findall(r"[A-Za-z][A-Za-z-]+", text)
    if len(words) <= 8:
        return text
    return fallback


def md_escape(value: object) -> str:
    return str(value).replace("|", "\\|")


def clip(text: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for marker in (". ", "; ", "。", "；"):
        pos = cut.rfind(marker)
        if pos >= int(limit * 0.55):
            return cut[: pos + len(marker)].strip()
    return cut.rstrip() + "…"


def heading_cn(heading: object) -> str:
    text = str(heading or "").strip()
    normalized = norm(text)
    for pattern, label in HEADING_TRANSLATIONS:
        if re.search(pattern, normalized, re.I):
            number = re.match(r"^\s*(\d+(?:\.\d+)*)", text)
            return f"{number.group(1)} {label}" if number else label
    return "全文相关章节"


def evidence_clues(text: object) -> str:
    raw = str(text or "")
    numbers = re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?(?:\s?(?:%|km2|km²|km|mm|h|d|years?|days?|basins?|catchments?|stations?))?", raw, re.I)
    acronyms = re.findall(r"\b[A-Z][A-Z0-9-]{1,9}\b", raw)
    clues: list[str] = []
    for value in numbers + acronyms:
        value = re.sub(r"\s+", " ", value).strip()
        if value and value not in clues:
            clues.append(value)
    return "、".join(clues[:8])


def chinese_evidence_summary(item: dict, group: str, row: dict, index: int) -> str:
    findings = text_list(item.get("main_findings"))
    limitations = text_list(item.get("limitations"))
    templates = {
        "problem": f"该段用于界定论文的研究背景、目标或待解决问题；与画像中的研究命题“{human_compact(item.get('research_problem'), '研究问题需学生回到原文定稿')}”对应。",
        "data": f"该段交代研究数据、样本、研究区或时空范围；当前画像记录的数据为{human_compact(item.get('datasets'), '数据名称与样本范围待学生核验')}，区域为{human_compact(item.get('study_region'), '研究区待核验')}。",
        "method": f"该段描述模型结构、输入、训练或耦合流程，是重建{human_compact(item.get('methods'), '论文方法链')}的证据入口。",
        "validation": f"该段涉及训练/验证/测试划分、基线或评价设计；应结合{human_compact(item.get('baselines'), '基线')}与{human_compact(item.get('metrics'), '评价指标')}核验独立性和信息泄漏。",
        "result": (findings[index % len(findings)] if findings else "该段报告模型表现、对比结果或水文响应；关键数值、单位、基线和样本条件需按该锚点回查。"),
        "limitation": (limitations[index % len(limitations)] if limitations else "该段包含局限、偏差、失败情形或未来工作线索；需判断其是否削弱泛化、极端事件或工程应用结论。"),
        "uncertainty": "该段涉及不确定性、敏感性、极端事件或鲁棒性；需核验不确定性来源、传播方式及其对结论的影响。",
        "availability": "该段涉及数据、代码、仓库或补充材料的可得性；需人工确认访问条件、版本、许可证和复现所需文件。",
    }
    summary = templates[group]
    clues = evidence_clues(row.get("snippet"))
    if clues:
        summary += f" 原文可核验线索：{clues}。"
    return summary


def annotate_evidence(item: dict, evidence: dict[str, list[dict]]) -> None:
    for group, rows in evidence.items():
        for index, row in enumerate(rows):
            row["group"] = group
            row["heading_cn"] = heading_cn(row.get("heading"))
            row["cn_summary"] = chinese_evidence_summary(item, group, row, index)


def load_title_map(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SystemExit(f"Chinese title map not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Chinese title map must be a JSON object")
    return {str(key): str(value).strip() for key, value in data.items() if str(value).strip()}


def keyword_hit(text: str, keyword: str) -> bool:
    if " " in keyword or "-" in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def extract_evidence(markdown: str) -> tuple[dict[str, list[dict]], list[str]]:
    candidates: dict[str, list[tuple[int, int, dict]]] = {name: [] for name in GROUPS}
    heading = "Front matter"
    headings: list[str] = []
    seen: set[str] = set()
    in_references = False
    lines = markdown.splitlines()
    for number, raw in enumerate(lines, 1):
        heading_match = re.match(r"^#{1,6}\s+(.+?)\s*$", raw)
        if heading_match:
            heading = heading_match.group(1).strip()
            headings.append(heading)
            if re.match(r"(?i)^(references|bibliography|literature cited)\b", heading):
                in_references = True
            continue
        if any(term in norm(heading) for term in ("credit author", "author contribution", "acknowledg", "competing interest", "supplement")):
            continue
        if in_references:
            continue
        line = re.sub(r"<[^>]+>", "", raw).strip()
        if len(line) < 55 or line.startswith(("|---", "![", "http://", "https://")):
            continue
        normalized = norm(line)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        evidence = {"heading": heading, "line": number, "snippet": clip(line)}
        for group, keywords in GROUPS.items():
            hits = sum(1 for keyword in keywords if keyword_hit(normalized, keyword))
            if not hits:
                continue
            score = hits * 3
            heading_norm = norm(heading)
            score += 6 if any(keyword_hit(heading_norm, hint) for hint in SECTION_HINTS[group]) else 0
            if group == "result" and re.search(r"\d", line):
                score += 3
            if group in {"data", "validation"} and re.search(r"\b(?:19|20)\d{2}\b|\d+\s*(?:basins?|catchments?|stations?|years?|days?)", line, re.I):
                score += 2
            if "abstract" in norm(heading):
                score -= 1
            # A source line may support several groups. Keep independent copies so
            # group-specific Chinese paraphrases cannot overwrite one another.
            candidates[group].append((score, -number, dict(evidence)))
    limits = {"problem": 2, "data": 3, "method": 3, "validation": 3, "result": 4, "limitation": 3, "uncertainty": 3, "availability": 2}
    selected: dict[str, list[dict]] = {}
    for group, rows in candidates.items():
        rows.sort(reverse=True, key=lambda row: (row[0], row[1]))
        chosen: list[dict] = []
        chosen_text: set[str] = set()
        for _, _, evidence in rows:
            marker = norm(evidence["snippet"])[:120]
            if marker in chosen_text:
                continue
            chosen.append(evidence)
            chosen_text.add(marker)
            if len(chosen) >= limits[group]:
                break
        selected[group] = chosen
    return selected, headings


def manifest_summary(path: str | None) -> dict:
    if not path or not Path(path).is_file():
        return {"total_pages": None, "figures": [], "tables": []}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {"total_pages": None, "figures": [], "tables": []}
    figures: list[dict] = []
    tables: list[dict] = []
    for block in data.get("figureBlocks") or []:
        target = tables if block.get("kind") == "table" else figures
        target.append({
            "label": ", ".join(block.get("labelHints") or []) or block.get("blockId"),
            "caption": clip(" ".join(block.get("captionHints") or []), 260),
            "page": block.get("pageStart") or block.get("pageEnd"),
            "section": block.get("sectionHeading"),
        })
    if not figures and not tables:
        for section in data.get("sections") or []:
            for fig in section.get("figures") or []:
                figures.append({"label": fig.get("label"), "caption": clip(str(fig.get("caption") or ""), 260), "page": fig.get("page"), "section": section.get("heading")})
            for tab in section.get("tables") or []:
                tables.append({"label": tab.get("label"), "caption": clip(str(tab.get("caption") or ""), 260), "page": tab.get("page"), "section": section.get("heading")})
    return {"total_pages": data.get("totalPages"), "figures": figures[:12], "tables": tables[:12]}


def score_profile(item: dict, evidence: dict, manifest: dict) -> dict:
    title = norm(item.get("title"))
    body = " ".join([title, norm(item.get("research_problem")), norm(item.get("methods")), " ".join(norm(row.get("snippet")) for rows in evidence.values() for row in rows)])
    hydrology = any(term in body for term in ("streamflow", "runoff", "discharge", "flood", "hydrolog"))
    forecast = any(term in body for term in ("forecast", "predict", "nowcast", "simulation", "estimation"))
    ml = any(term in body for term in ("machine learning", "deep learning", "lstm", "neural", "transformer", "graph"))
    relevance = 3 if hydrology and forecast and ml else 2 if sum((hydrology, forecast, ml)) >= 2 else 1 if any((hydrology, forecast, ml)) else 0

    breadth = sum(term in body for term in ("camels", "global", "national", "multi basin", "large sample", "ungauged", "benchmark", "multiple catchment"))
    design = len(text_list(item.get("baselines"))) + len(text_list(item.get("metrics"))) + len(evidence.get("validation") or [])
    representative = 3 if breadth >= 2 and design >= 4 else 2 if breadth >= 1 or design >= 4 else 1 if design >= 2 else 0

    year = int(item.get("year") or 0)
    frontier_terms = sum(term in body for term in ("transformer", "graph neural", "hybrid", "physics informed", "uncertainty", "probabilistic", "transfer learning", "explain", "extreme", "foundation"))
    frontier = 3 if year >= 2023 and frontier_terms >= 2 else 2 if year >= 2022 or frontier_terms >= 2 else 1 if year >= 2019 or frontier_terms else 0

    conflict_terms = sum(term in body for term in ("however", "fail", "inferior", "outperform", "trade off", "limitation", "challenge", "counter", "uncertain", "not always"))
    comparisons = len(text_list(item.get("baselines"))) + len(evidence.get("limitation") or [])
    conflict = 3 if conflict_terms >= 4 and comparisons >= 3 else 2 if conflict_terms >= 2 or comparisons >= 3 else 1 if conflict_terms or comparisons else 0

    figure_count = len(manifest.get("figures") or []) + len(manifest.get("tables") or [])
    anchor_groups = sum(bool(evidence.get(group)) for group in ("problem", "data", "method", "validation", "result", "limitation", "availability"))
    evidence_score = 3 if anchor_groups >= 6 and figure_count >= 2 else 2 if anchor_groups >= 5 else 1
    scores = {
        "theme_relevance_score": relevance,
        "representative_score": representative,
        "frontier_score": frontier,
        "conflict_score": conflict,
        "evidence_value_score": evidence_score,
    }
    scores["total_score"] = sum(scores.values())
    return scores


def role_for(item: dict, scores: dict) -> list[str]:
    roles: list[str] = []
    if scores["theme_relevance_score"] == 3:
        roles.append("主题直接相关")
    if scores["representative_score"] == 3:
        roles.append("代表性")
    if scores["frontier_score"] == 3:
        roles.append("前沿")
    if scores["conflict_score"] == 3:
        roles.append("冲突/反例")
    if scores["evidence_value_score"] == 3:
        roles.append("高证据价值")
    if int(item.get("year") or 9999) <= 2021:
        roles.append("基础/经典角色")
    return roles or ["补充比较"]


def external_link(item: dict, visible_title: str | None = None) -> str:
    title = str(visible_title or item.get("title_cn") or item.get("title") or "未命名文献").replace("|", "\\|")
    url = item.get("url") or (f"https://doi.org/{item['doi']}" if item.get("doi") else "")
    return f"[{title}]({url})" if url else title


def zotero_key(item: dict) -> str:
    for source in item.get("provenance") or []:
        match = re.search(r"zotero://select/library/items/([A-Z0-9]+)", str(source.get("locator") or ""), re.I)
        if match:
            return match.group(1).upper()
    match = re.search(r"Zotero item key\s*=\s*([A-Z0-9]+)", str(item.get("notes") or ""), re.I)
    return match.group(1).upper() if match else ""


def evidence_lines(rows: list[dict], empty: str = "全文自动定位未发现明确陈述，需人工复核对应章节。") -> list[str]:
    if not rows:
        return [f"- {empty}"]
    return [f"- **§{row.get('heading_cn') or heading_cn(row.get('heading'))}，L{row['line']}｜中文释义（AI概括）：** {md_escape(row.get('cn_summary') or '该证据需重新生成中文释义。')}" for row in rows]


def profile_markdown(record: dict) -> list[str]:
    item = record["profile"]
    evidence = record["fulltext_evidence"]
    scores = record["scores"]
    roles = record["roles"]
    source_url = item.get("url") or (f"https://doi.org/{item['doi']}" if item.get("doi") else "")
    zkey = zotero_key(item)
    title_original = str(item.get("title") or "未命名文献")
    title = str(record.get("title_cn") or "中文题名待补")
    findings = text_list(item.get("main_findings"))
    innovations = text_list(item.get("claimed_innovations"))
    limitations = text_list(item.get("limitations"))
    synthesis = f"本文围绕“{human_compact(item.get('research_problem'), '论文研究问题待学生定稿')}”展开，以{human_compact(item.get('datasets'), '全文所述数据')}为主要数据基础，采用{human_compact(item.get('methods'), '论文方法')}处理{human_compact(item.get('forecast_target'), '径流或相关水文预测')}问题，并通过{human_compact(item.get('baselines'), '对照方法')}和{human_compact(item.get('metrics'), '水文评价指标')}评估。全文证据表明其结论需受数据划分、跨流域泛化、极端事件与工程输入可得性的共同约束。"
    lines = [
        "---",
        f"title: {yaml_quote(title)}",
        f"canonical_literature_id: {yaml_quote(item.get('canonical_literature_id') or item.get('paper_id'))}",
        f"source_batch_id: {yaml_quote(record.get('source_batch_id'))}",
        f"title_original: {yaml_quote(title_original)}",
        f"title_normalized: {yaml_quote(norm(title_original))}",
        f"year: {yaml_quote(item.get('year'))}",
        f"journal: {yaml_quote(item.get('venue'))}",
        f"doi: {yaml_quote(item.get('doi'))}",
        f"doi_normalized: {yaml_quote(str(item.get('doi') or '').lower().replace('https://doi.org/', '').replace('http://doi.org/', '').replace('doi:', '').strip())}",
        f"source_url: {yaml_quote(source_url)}",
        f"source_path: {yaml_quote(record.get('source_path'))}",
        'selection_status: "included"',
        'evidence_status: "partial_text"',
        'review_status: "unverified"',
        'knowledge_status: "candidate"',
        'access_level: "fulltext"',
        'review_level: "auto_extracted"',
        'reading_scope: "MinerU全文已完整遍历；证据锚点和科研判断待学生复核"',
        f"core_status: {yaml_quote(record['deep_read_status'])}",
        f"final_treatment: {yaml_quote('approved_for_deep_read' if record['deep_read_status'] == 'approved' else 'deferred')}",
        "---",
        "",
        f"# {external_link(item, title)}",
        "",
        (f"[在Zotero中打开](zotero://select/library/items/{zkey})" if zkey else "Zotero链接未解析"),
        "",
        "> [!important] 证据状态",
        f"> 已遍历MinerU全文{record['fulltext_characters']}字符、{len(record['headings'])}个标题，并结合图表清单形成轻量总结。当前为AI全文初读，不能替代学生对关键数值、原图和补充材料的复核。",
        "",
        "## 一分钟全文判断",
        "",
        f"- **全文轻量总结：** {synthesis}",
        f"- **论文角色：** {'；'.join(roles)}。",
        f"- **精读决定：** {'已批准精读' if record['deep_read_status'] == 'approved' else '暂缓精读'}；五维总分{scores['total_score']}/15。",
        "",
        "## 研究命题与论证入口",
        "",
        f"- **研究问题：** {human_compact(item.get('research_problem'), '待学生从引言和摘要定稿')}",
        f"- **预测对象/提前期：** {human_compact(item.get('forecast_target'), '待核验')}；{human_compact(item.get('forecast_horizon'), '未报告')}",
    ]
    lines += evidence_lines(evidence.get("problem") or [])
    lines += ["", "## 数据、尺度与样本设计", "", f"- **区域：** {human_compact(item.get('study_region'), '未报告')}", f"- **空间/时间尺度：** {human_compact(item.get('spatial_scale'), '未报告')}；{human_compact(item.get('temporal_resolution'), '未报告')}", f"- **数据：** {human_compact(item.get('datasets'), '数据名称与样本范围待核验')}"]
    lines += evidence_lines(evidence.get("data") or [])
    lines += ["", "## 方法链、输入输出与基线", "", f"- **方法：** {human_compact(item.get('methods'), '方法链待学生复核')}", f"- **基线：** {human_compact(item.get('baselines'), '基线待核验')}", f"- **指标：** {human_compact(item.get('metrics'), '评价指标待核验')}"]
    lines += evidence_lines(evidence.get("method") or [])
    lines += ["", "## 训练验证、指标适配与泄漏检查", "", "- 重点复核：训练/验证/测试是否独立；时间、空间或事件是否跨集合；标准化、分解、特征选择及超参数是否只在训练集拟合。"]
    lines += evidence_lines(evidence.get("validation") or [])
    lines += ["", "## 全文主要结果", ""]
    lines += ([f"- **原画像结论（已进入全文交叉核验）：** {value}" for value in findings] or ["- 原画像未提供可用结论。"])
    lines += evidence_lines(evidence.get("result") or [])
    lines += ["", "## 作者声称创新与实际增量", ""]
    lines += ([f"- **作者声称：** {value}" for value in innovations] or ["- 原画像未记录作者声称创新；需从引言和讨论人工复核。"])
    lines += ["- **实际增量判断：** 当前只确认其在数据、方法、验证或工程场景上的组合增量；是否构成科学创新须与同类全文比较，不能由期刊层级替代。"]
    lines += ["", "## 局限性、冲突与失效条件", ""]
    lines += ([f"- **已记录局限：** {value}" for value in limitations] or ["- 原画像未记录明确局限。"])
    lines += evidence_lines(evidence.get("limitation") or [])
    lines += ["- **失效检查：** 若跨流域/跨时期独立测试、极端事件指标或强基线比较缺失，则平均性能提升不足以支撑工程泛化。"]
    lines += ["", "## 不确定性、极端事件与鲁棒性", ""]
    lines += evidence_lines(evidence.get("uncertainty") or [])
    lines += ["- 需人工确认是否同时报告区间覆盖、参数/结构不确定性、随机种子、分布外流域和洪峰/峰现时间。"]
    lines += ["", "## 物理一致性与工程可用性", "", "- 检查质量守恒、非负流量、上下游一致性及输入在业务预报时刻是否真实可得。", "- 统计性能只有在提前期、更新频率、计算时间、失效后果和人工接管条件匹配时才具有工程意义。"]
    lines += ["", "## 数据、代码与最小复现条件", ""]
    lines += evidence_lines(evidence.get("availability") or [])
    lines += [f"- **最小复现框架：** 使用{human_compact(item.get('datasets'), '论文数据')}，重建{human_compact(item.get('methods'), '论文方法')}，与{human_compact(item.get('baselines'), '强基线')}比较，并同时报告{human_compact(item.get('metrics'), '水文评价指标')}及极端/泛化指标。"]
    lines += ["", "## 核心筛选五维", "", "| 维度 | 得分（0–3） | 全文依据 |", "|---|---:|---|", f"| 主题相关性 | {scores['theme_relevance_score']} | 是否直接回答机器学习/深度学习流域水文预测问题 |", f"| 代表性 | {scores['representative_score']} | 数据广度、方法家族、强基线和验证设计 |", f"| 前沿性 | {scores['frontier_score']} | 年代与混合、图网络、不确定性、迁移、极端等前沿问题 |", f"| 冲突性 | {scores['conflict_score']} | 是否包含失败流域、相反结果、边界或强方法比较 |", f"| 证据价值 | {scores['evidence_value_score']} | 全文、图表、结果与可复现信息的可审计性 |", f"| **总分** | **{scores['total_score']}/15** | 期刊层级未计入总分，也不构成精读门槛 |"]
    lines += ["", "## 全文证据锚点与图表入口", "", "| 类型 | 位置 | 自动提取的短证据 |", "|---|---|---|"]
    for group in ("problem", "data", "method", "validation", "result", "limitation", "availability"):
        for row in (evidence.get(group) or [])[:2]:
            snippet = str(row.get("cn_summary") or "中文释义待重新生成").replace("|", "\\|")
            lines.append(f"| {GROUP_LABELS[group]} | §{row.get('heading_cn') or heading_cn(row.get('heading'))}，L{row['line']} | {snippet} |")
    for figure in (record["manifest"].get("figures") or [])[:2]:
        lines.append(f"| 图 | {figure.get('label')}，MinerU页{figure.get('page')} | 图注原文保留在机器记录；请打开原图核验坐标、单位、样本量和限定条件。 |")
    for table in (record["manifest"].get("tables") or [])[:2]:
        lines.append(f"| 表 | {table.get('label')}，MinerU页{table.get('page')} | 表注原文保留在机器记录；请打开原表核验指标、单位、样本和比较条件。 |")
    lines += ["", "## 阅读边界与人工复核任务", "", "- 当前完成的是AI全文通读型轻量画像，不是逐图逐公式的正式精读；规范证据状态固定为`partial_text`。", "- 优先回查：所有进入论文写作的定量结果、数据划分、图表原图、补充材料、代码版本与作者局限。", "- 复核后由学生人工把`review_status`升级为`self_checked`；脚本不得升级。导师确认前不得把筛选判断写成既定创新。"]
    return lines


def requested_deep_read_target(args: argparse.Namespace, root: Path, total: int) -> tuple[int | None, str]:
    sources: list[tuple[int, str]] = []
    if args.input_manifest:
        manifest_path = Path(args.input_manifest)
        if not manifest_path.is_absolute():
            manifest_path = (root / manifest_path).resolve()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if str(manifest.get("source_batch_id") or "") != args.batch_id:
            raise SystemExit("input_manifest source_batch_id does not match --batch-id")
        expected = (manifest.get("expected_counts") or {}).get("core_deep_reads")
        if expected is not None:
            sources.append((int(expected), "input_manifest.expected_counts.core_deep_reads"))
    if args.deep_read_count is not None:
        sources.append((args.deep_read_count, "--deep-read-count"))
    if args.minimum_deep_read_ratio is not None:
        if not 0 <= args.minimum_deep_read_ratio <= 1:
            raise SystemExit("--minimum-deep-read-ratio must be between 0 and 1")
        sources.append((math.ceil(total * args.minimum_deep_read_ratio), "--minimum-deep-read-ratio"))
    if len(sources) > 1:
        raise SystemExit("deep-reading target must have exactly one source")
    if not sources:
        return None, "not_set"
    target, source = sources[0]
    if target < 0 or target > total:
        raise SystemExit(f"deep-reading target {target} outside available range 0..{total}")
    return target, source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-root", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--input-manifest", help="JSON manifest; optional quantity gate is read only from expected_counts.core_deep_reads")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--deep-read-count", type=int, help="Explicit per-run gate; never inferred")
    target.add_argument("--minimum-deep-read-ratio", type=float, help="Legacy explicit per-run gate; no default")
    parser.add_argument("--approved-paper-id", action="append", default=[], help="Human-reviewed paper_id approved for deep reading; repeat as needed")
    parser.add_argument("--title-map", help="JSON object mapping exact original titles to reviewed Chinese titles")
    args = parser.parse_args()
    root = Path(args.vault_root).resolve()
    title_map_path = Path(args.title_map).resolve() if args.title_map else root / "10_文献知识/sources" / f"{args.batch_id}_中文题名映射.json"
    title_map = load_title_map(title_map_path)
    legacy_paths = sorted((root / "10_文献知识/profiles").glob(f"{args.batch_id}*_paper_profiles.jsonl"))
    profiles = load_jsonl(legacy_paths)
    audit_path = root / "10_文献知识/evidence" / f"{args.batch_id}_全文覆盖审计.jsonl"
    audits = load_jsonl([audit_path])
    audit_by_id = {row.get("paper_id"): row for row in audits}
    records: list[dict] = []
    for item in profiles:
        audit = audit_by_id.get(item.get("paper_id"))
        if not audit or audit.get("status") != "ready" or not audit.get("source"):
            continue
        markdown_path = Path(audit["source"]["full_md_path"])
        markdown = markdown_path.read_text(encoding="utf-8", errors="replace")
        evidence, headings = extract_evidence(markdown)
        annotate_evidence(item, evidence)
        manifest = manifest_summary(audit["source"].get("manifest_path"))
        scores = score_profile(item, evidence, manifest)
        title_original = str(item.get("title") or "")
        if title_original not in title_map:
            raise SystemExit(f"Missing Chinese title translation: {title_original}")
        records.append({"profile": item, "title_cn": title_map[title_original], "source_batch_id": args.batch_id, "source_path": str(markdown_path), "access_level": "fulltext", "review_level": "auto_extracted", "evidence_status": "partial_text", "review_status": "unverified", "knowledge_status": "candidate", "fulltext_characters": len(markdown), "headings": headings[:120], "fulltext_evidence": evidence, "manifest": manifest, "scores": scores, "roles": role_for(item, scores)})

    requested_target, target_source = requested_deep_read_target(args, root, len(records))
    ordered = sorted(records, key=lambda row: (row["scores"]["total_score"], row["scores"]["theme_relevance_score"], row["scores"]["conflict_score"], int(row["profile"].get("year") or 0)), reverse=True)
    available_ids = {str(row["profile"].get("paper_id")) for row in ordered}
    approved_ids = {str(value) for value in args.approved_paper_id}
    unknown_approved = sorted(approved_ids - available_ids)
    if unknown_approved:
        raise SystemExit(f"approved paper IDs are not in the batch: {unknown_approved}")
    if requested_target is not None and len(approved_ids) != requested_target:
        raise SystemExit(f"human-approved set has {len(approved_ids)} items; current manifest/parameter requires {requested_target}")
    for record in records:
        record["deep_read_status"] = "approved" if str(record["profile"].get("paper_id")) in approved_ids else "deferred"

    machine_path = root / "10_文献知识/evidence" / f"{args.batch_id}_fulltext_records.jsonl"
    machine_path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")

    output_dir = root / "10_文献知识/profiles/机器学习水文预报"
    output_dir.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    note_paths: dict[str, Path] = {}
    for record in records:
        name = safe_name(record["profile"], used)
        path = output_dir / f"{name}.md"
        path.write_text("\n".join(profile_markdown(record)).rstrip() + "\n", encoding="utf-8")
        note_paths[str(record["profile"].get("paper_id"))] = path

    index_path = output_dir / f"{args.batch_id}_轻量画像_Obsidian版.md"
    index_lines = ["---", 'title: "机器学习水文预报全文轻量画像索引"', 'evidence_status: "partial_text"', 'review_status: "unverified"', 'review_level: "auto_extracted"', "---", "", "# 机器学习水文预报全文轻量画像索引", "", f"> 共{len(records)}篇，基于MinerU机器遍历生成；人工明确批准{len(approved_ids)}篇进入精读。数量门槛来源：{target_source}。未设置门槛时不会自动批准。期刊层级不参与评分。", "", "## 已批准精读", ""]
    for record in ordered:
        if record["deep_read_status"] != "approved":
            continue
        item = record["profile"]; path = note_paths[str(item.get("paper_id"))]; zkey = zotero_key(item)
        index_lines.append(f"- [[{path.stem}|{record['title_cn']}]] · [文章页面]({item.get('url') or 'https://doi.org/'+str(item.get('doi'))})" + (f" · [Zotero](zotero://select/library/items/{zkey})" if zkey else "") + f" · {record['scores']['total_score']}/15 · {'；'.join(record['roles'])}")
    index_lines += ["", "## 其余全文画像", ""]
    for record in ordered:
        if record["deep_read_status"] == "approved":
            continue
        item = record["profile"]; path = note_paths[str(item.get("paper_id"))]; zkey = zotero_key(item)
        index_lines.append(f"- [[{path.stem}|{record['title_cn']}]] · [文章页面]({item.get('url') or 'https://doi.org/'+str(item.get('doi'))})" + (f" · [Zotero](zotero://select/library/items/{zkey})" if zkey else "") + f" · {record['scores']['total_score']}/15")
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    core_path = root / "10_文献知识/core" / f"核心文献选择_{args.batch_id}.csv"
    fields = ["canonical_literature_id", "paper_id", "source_batch_id", "title", "authors", "year", "journal", "doi_normalized", "source_path", "selection_status", "question_part", "generalization_relation", "selection_reason", "evidence_roles", "basin", "scale", "data", "model", "baselines", "evaluation", "extrapolation_setting", "evidence_status", "review_status", "fulltext_available", "figures_available", "supplement_available", "downstream_use", "final_treatment", "final_treatment_reason", "decision_maker", "decision_time", "theme_relevance_score", "representative_score", "frontier_score", "conflict_score", "evidence_value_score", "total_score", "journal_tier_context"]
    with core_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for record in ordered:
            item = record["profile"]; scores = record["scores"]
            writer.writerow({"canonical_literature_id": item.get("canonical_literature_id") or item.get("paper_id"), "paper_id": item.get("paper_id"), "source_batch_id": args.batch_id, "title": item.get("title"), "authors": "; ".join(item.get("authors") or []), "year": item.get("year"), "journal": item.get("venue"), "doi_normalized": str(item.get("doi") or "").lower(), "source_path": record.get("source_path"), "selection_status": "included", "question_part": item.get("research_problem") or "待人工填写", "generalization_relation": "待人工填写", "selection_reason": "五维分数仅供排序；具体比较理由待人工复核填写。", "evidence_roles": "; ".join(record["roles"]), "basin": item.get("study_region"), "scale": "; ".join(filter(None, [str(item.get("spatial_scale") or ""), str(item.get("temporal_resolution") or "")])), "data": "; ".join(item.get("datasets") or []), "model": "; ".join(item.get("methods") or []), "baselines": "; ".join(item.get("baselines") or []), "evaluation": "; ".join(item.get("metrics") or []), "extrapolation_setting": "待人工填写", "evidence_status": "partial_text", "review_status": "unverified", "fulltext_available": "机器可访问；人工待核验", "figures_available": "部分；人工待核验", "supplement_available": "待核验", "downstream_use": "仅候补" if record["deep_read_status"] != "approved" else "问题发现;主题校准", "final_treatment": "approved_for_deep_read" if record["deep_read_status"] == "approved" else "deferred", "final_treatment_reason": "人工显式批准" if record["deep_read_status"] == "approved" else "等待人工完成附录A.1并决定", "decision_maker": "external_human_approval" if record["deep_read_status"] == "approved" else "", "decision_time": "", **scores, "journal_tier_context": item.get("journal_tier")})

    core_md = core_path.with_name(f"核心文献选择_{args.batch_id}_Obsidian版.md")
    core_lines = ["---", 'title: "机器学习水文预报核心文献筛选"', 'evidence_status: "partial_text"', 'review_status: "unverified"', 'review_level: "auto_extracted"', "---", "", "# 机器学习水文预报核心文献筛选", "", f"> 全文画像{len(records)}篇；人工明确批准{len(approved_ids)}篇精读；数量门槛来源：{target_source}。五维各0—3分，只用于排序；期刊层级不进入总分，也不是硬门槛。附录A.1未完成的条目保持暂缓。", "", "| 文献 | 主题相关 | 代表性 | 前沿性 | 冲突性 | 证据价值 | 总分 | 角色 | 状态 |", "|---|---:|---:|---:|---:|---:|---:|---|---|"]
    for record in ordered:
        item = record["profile"]; scores = record["scores"]
        core_lines.append(f"| {external_link(item, record['title_cn'])} | {scores['theme_relevance_score']} | {scores['representative_score']} | {scores['frontier_score']} | {scores['conflict_score']} | {scores['evidence_value_score']} | {scores['total_score']} | {'；'.join(record['roles'])} | {'已批准精读' if record['deep_read_status'] == 'approved' else '暂缓精读'} |")
    core_md.write_text("\n".join(core_lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "created", "fulltext_profiles": len(records), "requested_deep_reads": requested_target, "target_source": target_source, "approved_deep_reads": len(approved_ids), "profile_dir": str(output_dir), "machine": str(machine_path), "core": str(core_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
