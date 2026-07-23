#!/usr/bin/env python3
"""Create 16-section full-text deep-reading notes for the approved core set."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def values(value: object) -> list[str]:
    return [str(item).strip() for item in value] if isinstance(value, list) else []


def compact(value: object, empty: str = "未报告") -> str:
    if isinstance(value, list):
        clean = [str(item).strip() for item in value if str(item).strip()]
        return "；".join(clean) if clean else empty
    text = str(value or "").strip()
    return text or empty


def human_compact(value: object, fallback: str = "未报告") -> str:
    text = compact(value, fallback)
    if re.search(r"[\u4e00-\u9fff]", text):
        return text
    words = re.findall(r"[A-Za-z][A-Za-z-]+", text)
    return text if len(words) <= 8 else fallback


def esc(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def yaml_quote(value: object) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def zotero_key(item: dict) -> str:
    for source in item.get("provenance") or []:
        match = re.search(r"zotero://select/library/items/([A-Z0-9]+)", str(source.get("locator") or ""), re.I)
        if match:
            return match.group(1).upper()
    match = re.search(r"Zotero item key\s*=\s*([A-Z0-9]+)", str(item.get("notes") or ""), re.I)
    return match.group(1).upper() if match else ""


def safe_profile_name(item: dict, used: set[str]) -> str:
    title = str(item.get("title") or "未命名文献")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", title)
    name = re.sub(r"\s+", " ", name).strip(" .")
    year = str(item.get("year") or "").strip()
    base = (f"{year}_{name}" if year else name)[:150].rstrip(" .") or "未命名文献"
    candidate = base; ordinal = 2
    while candidate.casefold() in used:
        candidate = f"{base[:135].rstrip()}（同名文献{ordinal}）"; ordinal += 1
    used.add(candidate.casefold()); return candidate


def safe_note_name(item: dict) -> str:
    author = (values(item.get("authors")) or ["作者"])[0]
    author = re.sub(r"[^\w\u4e00-\u9fff -]+", "", author).strip().split()[-1] if author.strip() else "作者"
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(item.get("title") or "未命名文献"))
    title = re.sub(r"\s+", " ", title).strip(" .")[:82].rstrip(" .")
    return f"{author}等_{item.get('year') or '年份待核验'}_{title}_全文精读.md"


def evidence(record: dict, group: str, count: int = 3) -> list[dict]:
    rows = record.get("fulltext_evidence", {}).get(group) or []
    return rows[:count]


def anchor(row: dict) -> str:
    return f"§{row.get('heading_cn') or '全文相关章节'}，L{row.get('line') or '待核验'}"


def snippet(row: dict) -> str:
    return esc(row.get("cn_summary") or "中文释义未生成；请按锚点回查机器记录中的原文片段。")


def result_rows(record: dict) -> list[dict]:
    rows = evidence(record, "result", 4)
    item = record["profile"]
    for finding in values(item.get("main_findings")):
        if len(rows) >= 3:
            break
        rows.append({"heading_cn": "摘要结论（需与结果段复核）", "line": "—", "cn_summary": finding})
    while len(rows) < 3:
        rows.append({"heading_cn": "结果章节", "line": "待人工定位", "cn_summary": "全文自动抽取未形成独立结果卡，需人工回到结果与图表补齐。"})
    return rows[:3]


def figure_rows(record: dict) -> list[dict]:
    figures = (record.get("manifest") or {}).get("figures") or []
    tables = (record.get("manifest") or {}).get("tables") or []
    rows = [("Figure", item) for item in figures[:2]] + [("Table", item) for item in tables[:2]]
    if len(rows) < 2:
        rows += [("Figure/Table", {"label": "待人工选择", "page": "待核验", "caption": "MinerU未提供足够可判定图表块。"})] * (2 - len(rows))
    return [{"kind": kind, **item} for kind, item in rows[:2]]


def build_note(record: dict, profile_stem: str, core_note: str) -> str:
    item = record["profile"]
    title_original = str(item.get("title") or "未命名文献")
    title = str(record.get("title_cn") or "中文题名待补")
    url = item.get("url") or (f"https://doi.org/{item['doi']}" if item.get("doi") else "")
    zkey = zotero_key(item)
    methods = human_compact(item.get("methods"), "论文方法链待学生复核")
    datasets = human_compact(item.get("datasets"), "论文数据与样本待学生复核")
    baselines = human_compact(item.get("baselines"), "对照方法待学生复核")
    metrics = human_compact(item.get("metrics"), "水文评价指标待学生复核")
    results = result_rows(record)
    figures = figure_rows(record)
    limitations = evidence(record, "limitation", 3)
    data_evidence = evidence(record, "data", 3)
    method_evidence = evidence(record, "method", 3)
    validation = evidence(record, "validation", 3)
    uncertainty = evidence(record, "uncertainty", 3)
    availability = evidence(record, "availability", 2)
    problem = evidence(record, "problem", 3)
    scores = record.get("scores") or {}
    roles = "；".join(record.get("roles") or [])
    authors = values(item.get("authors"))
    lines = [
        "---",
        f"title: {yaml_quote(title)}",
        f"canonical_literature_id: {yaml_quote(item.get('canonical_literature_id') or item.get('paper_id'))}",
        f"source_batch_id: {yaml_quote(record.get('source_batch_id'))}",
        f"title_cn: {yaml_quote(title)}",
        f"title_original: {yaml_quote(title_original)}",
        "authors:",
        *[f"  - {yaml_quote(author)}" for author in authors],
        f"year: {yaml_quote(item.get('year'))}",
        f"journal: {yaml_quote(item.get('venue'))}",
        f"doi: {yaml_quote(item.get('doi'))}",
        f"doi_normalized: {yaml_quote(str(item.get('doi') or '').lower().replace('https://doi.org/', '').replace('http://doi.org/', '').replace('doi:', '').strip())}",
        'source_file: "本地MinerU全文；技术路径见机器证据记录"',
        f"source_path: {yaml_quote(record.get('source_path'))}",
        f"source_url: {yaml_quote(url)}",
        'reading_status: "AI结构化全文初读（关键上下文、PDF原图与数值待学生复核）"',
        'selection_status: "included"',
        'evidence_status: "partial_text"',
        'review_status: "unverified"',
        'knowledge_status: "candidate"',
        'access_level: "fulltext"',
        'review_level: "auto_extracted"',
        f"profile_link: {yaml_quote('[[10_文献知识/profiles/机器学习水文预报/' + profile_stem + '|' + title + ']]')}",
        f"core_selection: {yaml_quote(core_note)}",
        'importance: "A"',
        'related_project: "机器学习与深度学习流域水文预报"',
        "tags:",
        "  - literature",
        "  - intensive-reading",
        "  - hydrology",
        "  - machine-learning",
        "  - fulltext",
        "---",
        "",
        f"# [{title}]({url})" if url else f"# {title}",
        "",
        (f"[在Zotero中打开](zotero://select/library/items/{zkey})" if zkey else "Zotero链接未解析"),
        "",
        "> [!important] 证据边界",
        f"> 本笔记已由机器遍历MinerU文本{record.get('fulltext_characters')}字符并读取章节、结果片段和图表清单。规范状态为`partial_text + unverified`：关键上下文、数值、公式、PDF原图、补充材料和代码仍需学生回查后才能用于正式引用。",
        "",
        "## 0. 阅读状态与证据标记",
        "",
        "- [x] 元数据、摘要、引言、数据方法、结果、讨论/结论与可用性章节已机器通读",
        "- [x] 已建立不少于8个章节/行号/图表证据锚点",
        "- [x] 已完成五维核心筛选与角色记录",
        "- [ ] 学生复核关键定量结果、PDF原图、公式与补充材料",
        "- [ ] 导师确认论文角色和可用于选题的判断",
        "",
        "# 一、文献信息与快速定位",
        "",
        "## 1.1 标准书目信息",
        "",
        "| 字段 | 内容 | 核验状态 |",
        "|---|---|---|",
        f"| 中文题目 | {esc(title)} | AI译题，学生待核定术语 |",
        f"| 作者 | {esc('；'.join(authors))} | Zotero元数据 |",
        f"| 期刊/年份 | {esc(item.get('venue'))}，{esc(item.get('year'))} | Zotero元数据 |",
        f"| DOI/文章页面 | [{esc(item.get('doi'))}]({url}) | 待独立书目核验 |" if url else f"| DOI | {esc(item.get('doi'))} | 待独立书目核验 |",
        f"| 全文覆盖 | {record.get('fulltext_characters')}字符；{len(record.get('headings') or [])}个标题；MinerU约{(record.get('manifest') or {}).get('total_pages') or '页数待核验'}页 | 已遍历 |",
        "",
        "## 1.2 30秒判断",
        "",
        f"**一句话概括：** 本文围绕“{human_compact(item.get('research_problem'), '论文研究问题待学生定稿')}”，采用{methods}处理{human_compact(item.get('forecast_target'), '径流或相关水文预测')}，并以{baselines}和{metrics}评价；其结论的主要边界来自数据划分、泛化、极端事件和工程信息可得性。",
        "",
        f"**为什么值得精读：** 五维总分{scores.get('total_score')}/15；角色为{roles}；入选不依赖期刊等级。",
        "",
        "# 二、术语、符号与尺度账本",
        "",
        "## 2.1 术语表",
        "",
        "| 规范术语 | 本笔记采用形式 | 定义/证据入口 |",
        "|---|---|---|",
        f"| 预测对象 | {esc(item.get('forecast_target') or '流量/径流')} | 全文方法与结果章节 |",
        f"| 方法体系 | {esc(methods)} | {anchor(method_evidence[0]) if method_evidence else '方法章节待人工定位'} |",
        f"| 评价指标 | {esc(metrics)} | 评价/结果章节 |",
        "",
        "## 2.2 尺度信息",
        "",
        "| 维度 | 本文设置 | 潜在尺度效应 |",
        "|---|---|---|",
        f"| 时间分辨率 | {esc(human_compact(item.get('temporal_resolution'), '未报告'))} | 与洪峰/低流量过程的匹配需复核 |",
        f"| 预报提前期 | {esc(human_compact(item.get('forecast_horizon'), '未报告'))} | 决定能否用于业务预警或调度 |",
        f"| 空间尺度 | {esc(human_compact(item.get('spatial_scale'), '未报告'))} | 单流域结果不能直接外推到无资料流域 |",
        f"| 研究区域 | {esc(human_compact(item.get('study_region'), '未报告'))} | 气候、地形、人类活动共同限制迁移 |",
        "",
        "# 三、论文论证骨架",
        "",
        "## 3.1 背景—缺口—贡献",
        "",
        "| 环节 | 全文证据 | 位置 | 科研判断 |",
        "|---|---|---|---|",
    ]
    labels = ["研究背景/问题", "作者目标", "贡献入口"]
    for index, row in enumerate((problem + method_evidence)[:3]):
        lines.append(f"| {labels[index]} | {snippet(row)} | {anchor(row)} | 需与结果和局限形成闭环 |")
    lines += ["", "## 3.2 主张—证据链", "", "| 主张编号 | 关键主张/结果 | 实际证据 | 强度 | 缺口 |", "|---|---|---|---|---|"]
    for index, row in enumerate(results, 1):
        lines.append(f"| CL{index:02d} | {snippet(row)} | {anchor(row)} | 中 | 关键数值与图表原图待学生复核 |")
    lines += ["", "## 3.3 作者自称创新与实际增量", "", f"- 作者声称创新：{human_compact(item.get('claimed_innovations'), '作者创新表述待从引言和结论定稿')}", f"- 当前可确认的实际增量：在{methods}、{datasets}、验证场景或工程任务上的组合增量。", "- 尚不能仅由算法名称或期刊层级断言科学创新；需与同类核心文献全文比较。", "", "# 四、研究对象与工程背景", "", "## 4.1 研究区或工程对象", "", "| 项目 | 内容 | 对结果的影响 |", "|---|---|---|", f"| 区域/流域 | {esc(human_compact(item.get('study_region'), '未报告'))} | 控制外部有效性 |", f"| 数据与样本 | {esc(datasets)} | 决定模型能学习到的水文状态范围 |", f"| 预测任务 | {esc(human_compact(item.get('forecast_target'), '待核验'))}；{esc(human_compact(item.get('forecast_horizon'), '未报告'))} | 决定评价指标和工程价值 |", f"| 边界/初始条件 | 全文自动定位未形成统一记录 | 需人工回查方法章节 |", "", "## 4.2 可迁移性", "", "- 案例特有因素包括气候区、流域属性、资料密度、输入产品和训练期。", "- 可能可迁移的是方法链、验证协议和指标体系，而非原论文性能数值。", "- 换到无资料流域、极端事件或业务预报时，需重新做时间/空间/事件独立验证。", "", "# 五、数据与预处理", "", "## 5.1 数据清单", "", "| 数据/证据 | 来源位置 | 用途与待核验点 |", "|---|---|---|"]
    for row in data_evidence:
        lines.append(f"| {snippet(row)} | {anchor(row)} | 核验时段、分辨率、样本量、缺测与质量控制 |")
    if not data_evidence:
        lines.append("| 未自动定位到明确数据段 | 数据章节待人工核验 | 不得用摘要替代 |")
    lines += ["", "## 5.2 预处理与信息泄漏检查", "", "- 标准化、分解、特征选择和超参数搜索是否只使用训练集：待学生回查。", "- 相邻站点、同一洪水事件或同一时期是否跨训练/测试：待学生回查。", "- 未来信息是否通过再分析、滚动统计或事后观测进入输入：待学生回查。"]
    for row in validation:
        lines.append(f"- **验证证据 {anchor(row)}：** {snippet(row)}")
    lines += ["", "# 六、方法与模型拆解", "", "## 6.1 方法总流程", "", f"{datasets} → 预处理/特征构造 → {methods} → 训练/率定 → {baselines}比较 → {metrics}评价 → 水文与工程解释。", "", "## 6.2 输入、输出、基线与物理一致性", "", f"- 输入：{datasets}及全文方法章节列出的动态/静态变量。", f"- 输出：{human_compact(item.get('forecast_target'), '径流或相关水文变量')}。", f"- 基线：{baselines}。", f"- 评价：{metrics}。", "- 物理一致性需检查质量守恒、非负流量、河网上下游一致性以及后处理是否改变水量平衡。"]
    for row in method_evidence:
        lines.append(f"- **方法证据 {anchor(row)}：** {snippet(row)}")
    lines += ["", "# 七、率定、验证与评价指标", "", "## 7.1 实验设计", "", "| 项目 | 全文自动定位 | 评价 |", "|---|---|---|", f"| 训练/测试 | {snippet(validation[0]) if validation else '未自动定位'} | 必须确认时间/空间独立性 |", f"| 强基线 | {esc(baselines)} | 若只比较弱基线，增益不稳健 |", f"| 指标 | {esc(metrics)} | 平均指标需配合洪峰、峰现时间、偏差与概率可靠性 |", "", "## 7.2 验证强度", "", "- 检查是否存在真正独立测试、空间留出、留事件或非平稳时期验证。", "- 统计显著不等于工程显著；需要把性能差异转成预警提前量、洪峰误差或调度后果。", "", "# 八、不确定性、敏感性与鲁棒性", "", "## 8.1 不确定性与鲁棒性证据"]
    for row in uncertainty:
        lines.append(f"- **{anchor(row)}：** {snippet(row)}")
    if not uncertainty:
        lines.append("- 全文自动定位未发现系统不确定性分析；需人工检查讨论和补充材料。")
    lines += ["- 需分别检查观测误差、输入预报误差、模型结构、随机种子、参数、极端事件和分布外流域。", "", "# 九、结果、图表与证据定位", "", "## 9.1 关键结果卡"]
    for index, row in enumerate(results, 1):
        lines += ["", f"### 结果卡 R{index:02d}", f"- **中文释义（AI概括）：** {snippet(row)}", f"- **来源锚点：** {anchor(row)}", f"- **比较基准：** {baselines}", "- **是否支撑主结论：** 部分；需回查完整上下文与原图。", "- **待核验：** 单位、样本量、统计区间、是否为独立测试。"]
    lines += ["", "## 9.2 图表精读"]
    for index, row in enumerate(figures, 1):
        lines += ["", f"### 图表{index}：{esc(row.get('label'))}", "- **图注/表注中文说明：** 原始图注保留在机器证据记录；当前不做未经核定的逐字翻译。", f"- **来源锚点：** MinerU页索引{esc(row.get('page'))}，全文相关章节", "- **当前检查范围：** 已读图注及正文上下文；未复核PDF原图，不评价颜色、线型或视觉显著性。", "- **人工任务：** 核验坐标、单位、样本量、误差线、面板和图注限定条件。"]
    lines += ["", "## 9.3 原文证据块", ""]
    all_anchors = (problem + data_evidence + method_evidence + validation + results + limitations + availability)[:14]
    for index, row in enumerate(all_anchors, 1):
        lines += [f"<a id=\"S{index:03d}\"></a>", f"- **S{index:03d}｜{anchor(row)}：** {snippet(row)}"]
    lines += ["", "# 十、讨论、局限与适用边界", "", "## 10.1 作者讨论和局限证据"]
    for row in limitations:
        lines.append(f"- **{anchor(row)}：** {snippet(row)}")
    if not limitations:
        lines.append("- 自动定位未找到明确局限段；需回查讨论/结论。")
    lines += ["", "## 10.2 未充分讨论的风险", "", "- 数据代表性、因果识别、模型结构误差、非平稳性、极端外推、物理一致性和工程执行约束需分别判断。", "", "## 10.3 结论边界句", "", f"本文结论只适用于{human_compact(item.get('study_region'), '原研究区域')}、{human_compact(item.get('spatial_scale'), '原空间尺度')}、{human_compact(item.get('temporal_resolution'), '原时间尺度')}及其数据/模型条件；当气候、资料密度、工程规则或输入可得性变化时，原性能不可直接迁移。", "", "# 十一、水利工程可实施性检查", "", "| 检查项 | 论文当前证据 | 工程差距 |", "|---|---|---|", f"| 数据实时可得性 | {datasets} | 核验业务时刻是否可获得 |", f"| 提前期/更新频率 | {human_compact(item.get('forecast_horizon'), '未报告')}/{human_compact(item.get('temporal_resolution'), '未报告')} | 与预警和调度时效匹配 |", "| 极端和失效后果 | 见结果与鲁棒性证据 | 平均指标不能替代洪峰与失效评估 |", "| 物理/工程约束 | 自动画像未形成完整约束清单 | 需补质量守恒、河网与运行约束 |", "| 可解释与人工接管 | 未报告或待核验 | 实际部署必须提供 |", "", "**工程适用等级：** 需工程化改造或仅概念验证；学生复核前不判定为可直接应用。", "", "# 十二、批判性评价", "", "## 12.1 五类有效性", "", "| 维度 | 初判 | 证据与待核验点 |", "|---|---|---|", f"| 内部有效性 | 中 | 方法与结果有全文锚点；需复核数据划分、消融和随机性 |", f"| 构念有效性 | 中 | 指标为{esc(metrics)}；需判断是否匹配洪水/水资源目标 |", "| 统计有效性 | 中 | 需复核样本量、区间和多重比较 |", f"| 外部有效性 | 中—弱 | 区域/尺度为{esc(human_compact(item.get('study_region'), '未报告'))}/{esc(human_compact(item.get('spatial_scale'), '未报告'))} |", "| 工程有效性 | 待核验 | 输入时效、约束、计算成本和失效后果尚未闭环 |", "", "## 12.2 最强与最弱", "", f"- **最强之处：** {snippet(results[0])}", f"- **最弱之处：** {snippet(limitations[0]) if limitations else '全文未明确量化主要失效条件，需人工补查。'}", "- **总体可信度：** 中（AI全文通读初判，待学生复核）。", "", "# 十三、与当前研究和其他文献的关系", "", "## 13.1 对机器学习流域水文预报的作用", "", f"- 五维筛选：主题相关{scores.get('theme_relevance_score')}/3，代表性{scores.get('representative_score')}/3，前沿性{scores.get('frontier_score')}/3，冲突性{scores.get('conflict_score')}/3，证据价值{scores.get('evidence_value_score')}/3。", f"- 角色：{roles}。", "- 可用于比较方法、验证协议、失败边界和工程适用性；不得以期刊层级替代证据。", "", "## 13.2 关系候选（待双文全文核验）", "", "- 与同方法家族论文比较：数据范围、基线强度、时间/空间留出和极端指标。", "- 与冲突论文比较：性能差异是否来自数据、尺度、信息泄漏、任务定义或底层物理模型。", "", "# 十四、可引用证据与写作出口", "", "| 引文编号 | 拟支持的论断 | 原文位置 | 核验状态 |", "|---|---|---|---|"]
    for index, row in enumerate(results, 1):
        lines.append(f"| CIT{index:02d} | {snippet(row)} | {anchor(row)} | 学生待核验 |")
    lines += ["", "- 可进入引言：研究问题和方法背景，需回查问题锚点。", "- 可进入方法/讨论：验证设计、强基线、失败流域和适用边界。", "- 不应直接引用：AI综合判断、未复核数值、仅来自摘要的结论。", "", "# 十五、复现与最小验证", "", "## 15.1 数据与代码可得性"]
    for row in availability:
        lines.append(f"- **{anchor(row)}：** {snippet(row)}")
    if not availability:
        lines.append("- 未自动定位明确数据/代码声明；需人工检查全文末尾和补充材料。")
    lines += ["", "## 15.2 最小复现实验", "", f"- **要验证的命题：** {snippet(results[0])}", f"- **最小数据：** {datasets}", f"- **最小模型：** {methods}", f"- **对照组：** {baselines}", f"- **输出：** {metrics}、洪峰/峰现时间、偏差和跨流域/跨时期泛化。", "- **成功条件：** 在严格独立测试中保持优势，并且极端与物理一致性不退化。", "- **失败条件：** 优势在强基线、空间留出、事件留出或非平稳时期消失。", "- **预计工作量：** 数据可得时约1—3周完成最小复现；具体由数据规模和代码可用性修正。", "- **数据/代码位置：** 待项目负责人指定，不在本笔记中复制版权全文。", "", "# 十六、精读结论与行动", "", "## 16.1 五句话总结", "", f"1. 本文研究：{human_compact(item.get('research_problem'), '论文研究问题待学生定稿')}。", f"2. 作者使用：{methods}，数据为{datasets}。", f"3. 主要发现：{snippet(results[0])}", f"4. 最大价值：{roles}，并提供{scores.get('evidence_value_score')}/3的全文证据价值。", f"5. 关键边界：{snippet(limitations[0]) if limitations else '数据划分、外推、极端和工程约束仍需人工核验。'}", "", "## 16.2 最终判断", "", f"- **科学价值：** {'高' if scores.get('total_score', 0) >= 13 else '中—高'}", "- **方法可靠性：** 中（待学生复核）", "- **工程适用性：** 需工程化改造/仅概念验证", "- **与当前课题相关性：** 直接", "- **是否进入深度拆解库：** 是（五维核心筛选批准）", "- **是否建议复现：** 是，优先复现可决定冲突或泛化判断的实验", "- **是否需要导师讨论：** 是", "", "## 16.3 下一步任务", "", "- [ ] 学生复核3个关键结果卡的完整上下文、数值和单位", "- [ ] 查看至少2幅PDF原图/表并记录坐标、误差和样本量", "- [ ] 核验训练/验证/测试划分与潜在信息泄漏", "- [ ] 核验数据代码可得性并设计最小复现", "- [ ] 与另一篇支持或冲突核心文献做双全文比较", "", "## 16.4 复核记录", "", "| 日期 | 复核人 | 新证据或判断变化 |", "|---|---|---|", "| 待填写 | 待填写 | AI全文初读，等待学生复核 |"]
    return "\n".join(lines).rstrip() + "\n"


def existing_notes_by_doi(notes_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in notes_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="replace")[:5000]
        match = re.search(r"(?m)^doi:\s*\"?([^\"\n]+)\"?\s*$", text)
        if match and "旧版" not in path.name:
            index[match.group(1).strip().casefold()] = path
    return index


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
    parser.add_argument("--notes-dir", help="Vault-relative or absolute note directory; defaults to the established legacy path")
    parser.add_argument("--overwrite-existing", action="store_true", help="Explicitly allow backup and replacement of an existing generated note")
    args = parser.parse_args()
    root = Path(args.vault_root).resolve()
    records = load_jsonl(root / "10_文献知识/evidence" / f"{args.batch_id}_fulltext_records.jsonl")
    approved = [record for record in records if record.get("deep_read_status") == "approved"]
    requested_target, target_source = requested_deep_read_target(args, root, len(records))
    if requested_target is not None and len(approved) != requested_target:
        raise SystemExit(f"Approved deep reads {len(approved)} do not match current manifest/parameter target {requested_target}")
    notes_dir = Path(args.notes_dir) if args.notes_dir else Path("文献/机器学习深度学习流域水文预报/文献笔记")
    if not notes_dir.is_absolute():
        notes_dir = (root / notes_dir).resolve()
    else:
        notes_dir = notes_dir.resolve()
    if notes_dir != root and root not in notes_dir.parents:
        raise SystemExit("--notes-dir must stay inside --vault-root")
    notes_dir.mkdir(parents=True, exist_ok=True)
    existing = existing_notes_by_doi(notes_dir)
    backup_dir = root / "10_文献知识/runs" / f"{args.batch_id}_旧版精读备份"
    if args.overwrite_existing:
        backup_dir.mkdir(parents=True, exist_ok=True)
    used: set[str] = set(); profile_stems: dict[str, str] = {}
    for record in records:
        profile_stems[str(record["profile"].get("paper_id"))] = safe_profile_name(record["profile"], used)
    outputs: list[tuple[dict, Path]] = []
    skipped_existing: list[Path] = []
    for record in approved:
        item = record["profile"]
        doi = str(item.get("doi") or "").casefold()
        path = existing.get(doi) or (notes_dir / safe_note_name(item))
        if path.exists():
            if not args.overwrite_existing:
                skipped_existing.append(path)
                outputs.append((record, path))
                continue
            backup = backup_dir / path.name
            if not backup.exists():
                shutil.copy2(path, backup)
        content = build_note(record, profile_stems[str(item.get("paper_id"))], f"[[10_文献知识/core/核心文献选择_{args.batch_id}_Obsidian版|五维核心文献筛选]]")
        path.write_text(content, encoding="utf-8")
        outputs.append((record, path))

    index_path = notes_dir / f"00_核心精读索引_{args.batch_id}.md"
    index_lines = ["---", 'title: "机器学习水文预报核心精读索引"', 'evidence_status: "partial_text"', 'review_status: "unverified"', 'review_level: "auto_extracted"', "---", "", "# 机器学习水文预报核心精读索引", "", f"> 全文画像{len(records)}篇；人工批准集合{len(approved)}篇；数量门槛来源：{target_source}。本次新写或纳入索引{len(outputs)}篇，保留未覆盖既有笔记{len(skipped_existing)}篇。期刊层级不参与评分。", ""]
    for record, path in sorted(outputs, key=lambda pair: pair[0]["scores"]["total_score"], reverse=True):
        item = record["profile"]; url = item.get("url") or f"https://doi.org/{item.get('doi')}"
        index_lines.append(f"- [[{path.stem}|{record.get('title_cn') or '中文题名待补'}]] · [文章页面]({url}) · {record['scores']['total_score']}/15 · {'；'.join(record.get('roles') or [])}")
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    evidence_path = root / "10_文献知识/evidence" / f"{args.batch_id}_核心文献证据索引.md"
    evidence_lines = ["---", 'title: "机器学习水文预报核心文献证据索引"', 'evidence_status: "partial_text"', 'review_status: "unverified"', 'review_level: "auto_extracted"', "---", "", "# 机器学习水文预报核心文献证据索引", "", f"> 当前核心笔记{len(outputs)}篇；机器文本遍历与结构化笔记不等于人工全文核验。正式引用仍需学生复核关键上下文、图表与补充材料。", "", "| 文献 | 五维角色 | 精读笔记 | 关键结果锚点 |", "|---|---|---|---|"]
    for record, path in sorted(outputs, key=lambda pair: pair[0]["scores"]["total_score"], reverse=True):
        item = record["profile"]; url = item.get("url") or f"https://doi.org/{item.get('doi')}"; first = result_rows(record)[0]
        evidence_lines.append(f"| [{esc(record.get('title_cn') or '中文题名待补')}]({url}) | {esc('；'.join(record.get('roles') or []))} | [[{path.stem}|精读笔记]] | {esc(anchor(first))} |")
    evidence_path.write_text("\n".join(evidence_lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "created", "fulltext_profiles": len(records), "requested_deep_reads": requested_target, "target_source": target_source, "approved_deep_reads": len(approved), "deep_notes_indexed": len(outputs), "skipped_existing": [str(path) for path in skipped_existing], "index": str(index_path), "evidence_index": str(evidence_path), "backup_dir": str(backup_dir) if args.overwrite_existing else None}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
