#!/usr/bin/env python3
"""Add named sources and bounded evidence cards to profile/deep-note Markdown."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


START = "<!-- EVIDENCE_ENRICHMENT_START -->"
END = "<!-- EVIDENCE_ENRICHMENT_END -->"
ID_RE = re.compile(
    r"(?m)^(?:paper_id|canonical_literature_id):\s*[\"']?([A-Za-z0-9._-]+)[\"']?\s*$"
)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9.+-]*|\d+(?:\.\d+)?%?")
STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "were", "was",
    "are", "has", "have", "into", "using", "used", "their", "which", "our",
    "its", "can", "based", "study", "results", "model", "models", "to", "of",
    "in", "a", "an", "we", "be", "by", "as", "on", "or", "et", "al",
}
GROUP_LABELS = {
    "problem": "研究问题",
    "data": "数据与研究区",
    "method": "方法链",
    "validation": "验证设计",
    "result": "结果",
    "limitation": "局限与适用边界",
    "uncertainty": "不确定性与稳健性",
    "availability": "数据或代码可得性",
}
GROUP_PRIORITY = (
    "result", "method", "validation", "limitation",
    "data", "uncertainty", "problem", "availability",
)
GROUP_KEYWORDS = {
    "problem": ("challenge", "problem", "aim", "objective", "need", "important"),
    "data": ("dataset", "data", "period", "basin", "watershed", "river", "station", "years"),
    "method": ("proposed", "developed", "framework", "integrated", "hybrid", "architecture", "algorithm"),
    "validation": ("training", "validation", "testing", "test", "split", "cross-validation", "forecast horizon"),
    "result": ("outperformed", "best performance", "improved", "higher", "lower", "nse", "rmse", "kge", "r2"),
    "limitation": ("limitation", "however", "challenge", "boundary", "generalization", "future work", "uncertain"),
    "uncertainty": ("uncertainty", "confidence", "coverage", "robust", "sensitivity", "ensemble"),
    "availability": ("available", "availability", "repository", "code", "data", "license"),
}
GROUP_HINTS = {
    "availability": ("可得", "代码", "材料", "开放获取", "许可证"),
    "uncertainty": ("不确定", "敏感", "鲁棒", "可靠性", "置信"),
    "limitation": ("局限", "限制", "边界", "外推", "适用", "威胁"),
    "result": ("结果", "结论", "发现", "性能", "比较", "cl0", "结果卡"),
    "validation": ("验证", "训练", "测试", "评价", "基线", "划分", "检验"),
    "method": ("方法", "模型", "框架", "网络", "技术路线", "算法"),
    "data": ("数据", "研究区", "样本", "尺度", "观测", "流域", "站点"),
    "problem": ("问题", "背景", "目标", "需求", "动机"),
}
GENERIC_PHRASES = (
    "全文相关章节",
    "原文证据卡（见",
    "该段用于界定",
    "该段交代",
    "该段描述模型",
    "该段涉及训练",
    "该段报告模型",
    "该段包含局限",
    "该段涉及不确定性",
    "该段涉及数据、代码",
    "原文可核验线索",
)
VISIBLE_LOCATOR_PATTERNS = (
    re.compile(r"§[^|\n]{0,100}?[,，]\s*L\d+\b", re.I),
    re.compile(r"(?:抽取行|提取行|原文行号|段落编号)\s*[:：]?\s*\d+", re.I),
    re.compile(r"来源锚点\s*[:：][^|\n]{0,100}?\bL\d+\b", re.I),
)

# These two records are the acceptance samples for content-based evidence writing.
# Each entry states what the paper says, what it supports, and the inference boundary.
CUSTOM_ANALYSIS = {
    "P-2025-0016": {
        "problem": (
            "论文以土耳其流域的降雨—径流关系为对象，比较机器学习方法识别气候与径流响应关系的能力。",
            "可支持研究对象是降雨—径流建模及多方法比较。",
            "题名指向底格里斯河流域，但已抽取正文同时出现幼发拉底河流域及 Konya、Rize；研究区身份需回到论文首页和研究区图人工核对。",
        ),
        "data": (
            "正文说明研究使用月尺度降雨与径流观测，并涉及九个径流观测站以及相应气象观测资料。",
            "可支持模型输入来自站点降雨观测、预测目标为月径流，且研究具有多站点结构。",
            "当前片段不足以确认各站完整时段、缺测处理、训练测试划分和所有站点是否同属题名所称流域。",
        ),
        "method": (
            "方法部分描述了基于 Takagi–Sugeno 模糊系统和网格划分的 ANFIS，并将其与 LSTM 等机器学习方法放在同一降雨—径流比较框架中。",
            "可支持论文确实比较了神经模糊方法、循环神经网络及其他统计或机器学习方法。",
            "仅凭方法描述不能判断哪一种模型最优，也不能证明模型满足水量平衡或跨流域泛化要求。",
        ),
        "validation": (
            "论文使用相关系数、NSE、RMSE、标准差比和 PBIAS 等指标评价模拟；PBIAS 的正负分别用于辨识总体高估或低估。",
            "可支持评价体系同时关注拟合、误差幅度和系统偏差。",
            "尚需核对训练测试划分、各站点是否采用相同评价期，以及指标是否在独立测试集上计算。",
        ),
        "result": (
            "正文报告 LSTM 的 RMSE 低于所比较的其他方法，并强调仍需结合过程线或图形检查评价模型表现。",
            "可支持作者报告 LSTM 在误差指标上的相对优势，而非所有指标和所有站点上的全面最优。",
            "具体优势幅度、显著性、比较基线和适用站点必须依据结果表与图重新核验。",
        ),
        "limitation": (
            "论文承认降雨—径流关系受多种因素共同影响，属于高度复杂且具有不确定性的建模问题。",
            "可支持解释模型结果时需要考虑输入因素不完整与系统非线性。",
            "这段一般性陈述不能替代对数据缺失、时间外推、空间迁移和极端事件误差的专门检验。",
        ),
        "uncertainty": (
            "现有正文片段把模糊规则与神经网络学习用于处理复杂和不确定关系，但未显示概率预报、置信区间或系统敏感性实验。",
            "可支持论文在方法动机层面关注不确定性。",
            "不能据此声称论文已经完成概率不确定性量化或可靠性校准。",
        ),
        "availability": (
            "当前证据记录未给出可直接复现的数据仓库、代码版本或软件环境。",
            "只能支持复现入口尚未在已读片段中确认。",
            "不能据此断言作者没有公开材料，仍需检查论文的数据与代码可得性声明。",
        ),
    },
    "P-2024-0012": {
        "problem": (
            "论文针对内蒙古察尔森流域资料稀缺条件下的洪水与径流预测，关注极端气候和观测不足对预报精度的约束。",
            "可支持研究问题是资料稀缺流域的径流预报，而非一般性的时间序列预测。",
            "尚不能据此判断方法在其他气候区、无资料流域或非汛期同样有效。",
        ),
        "data": (
            "研究同时使用 CAMELS 多流域数据和察尔森流域资料：前者提供迁移学习的源流域模式，后者用于目标流域的径流预测与检验。",
            "可支持实验采用跨流域知识迁移，并将察尔森作为资料稀缺目标流域。",
            "当前片段未完整给出源流域筛选、样本时段、变量清单、缺测处理和源—目标尺度一致性。",
        ),
        "method": (
            "方法将 Informer 深度学习模型与 WRF-Hydro 水文模拟结合形成 Hydro-Informer，并通过迁移学习把 CAMELS 源流域中学习到的模式用于察尔森流域。",
            "可支持该方法是一条“数据驱动预测＋水文模拟信息＋跨流域迁移”的混合链路。",
            "尚需核对两类模型的具体耦合位置、输入输出、损失函数、参数冻结策略及是否使用预测时不可得的信息。",
        ),
        "validation": (
            "研究按数据收集、模型训练和验证组织迁移实验，并在 2015—2016 年汛期使用 NSE、IOA 等指标比较不同模型及混合比例。",
            "可支持验证包含跨年度汛期比较和多个模型配置。",
            "现有片段不足以确认是否存在完全独立的测试集、调参是否与测试期隔离，以及基线是否经过同等优化。",
        ),
        "result": (
            "作者报告 Hydro-Informer 和 Informer 在多数情形下优于 WRF-Hydro；2016 年两者的 NSE 均为 0.76，并更接近两次显著洪峰。",
            "可支持深度学习与混合模型在所列汛期指标和洪峰过程线上优于该 WRF-Hydro 配置。",
            "这一结论受年份、流域、模型校准和指标选择限制，不能外推为混合模型在所有资料稀缺流域均占优。",
        ),
        "limitation": (
            "论文的模拟仅覆盖夏季月份，作者据此提示结论的季节代表性和泛化范围可能受限。",
            "可支持当前结果主要适用于所研究的夏季或汛期条件。",
            "不能据此评价枯水期、全年连续模拟、长期气候变化或其他流域上的表现。",
        ),
        "uncertainty": (
            "研究比较了不同模型组合比例在 2015 和 2016 汛期的 NSE 与 IOA，但现有证据未显示概率区间、覆盖率或预测分布校准。",
            "可支持论文做了配置敏感性或稳健性比较。",
            "不能把模型比例比较等同于完整的不确定性量化。",
        ),
        "availability": (
            "当前证据可以确认 CAMELS 是源数据之一，但尚未确认察尔森数据、训练代码、模型权重和配置文件的公开入口。",
            "可支持复现至少需要 CAMELS 与目标流域观测两类资料。",
            "链接、版本、许可证及目标流域资料权限仍需人工核查。",
        ),
    },
}

CUSTOM_LINE_ANALYSIS = {
    "P-2024-0012": {
        ("problem", 9): (
            "引言把气候变化相关极端天气、洪水预报需求与察尔森流域观测稀缺并列为研究动机。",
            "可支持论文聚焦资料稀缺条件下的洪水预报。",
            "这只是问题陈述，不能证明后续模型已经解决数据稀缺。",
        ),
        ("problem", 23): (
            "论文明确提出在察尔森流域组合 Informer 与 WRF-Hydro，以改善缺少观测资料地区的径流预测。",
            "可支持研究目标和混合模型的基本构成。",
            "不能据此判断耦合方式、性能优势或跨流域通用性。",
        ),
        ("data", 9): (
            "引言确认察尔森流域的数据稀缺是实验设计必须面对的条件。",
            "可支持目标流域属于资料稀缺应用场景。",
            "未给出数据量、缺测比例、时段和变量，不能量化“稀缺”程度。",
        ),
        ("data", 31): (
            "研究区图同时标出美国 CAMELS 流域集合和内蒙古察尔森流域，说明实验包含源流域与目标流域两个空间层次。",
            "可支持跨区域迁移实验的空间对象。",
            "地图说明不能替代源流域筛选规则、面积和气候相似性核验。",
        ),
        ("data", 37): (
            "CAMELS 被作为包含气象与水文信息的美国大样本数据集，用于迁移学习阶段获取源流域模式。",
            "可支持 CAMELS 是迁移学习的源域数据。",
            "当前片段未列出具体变量、源流域数量、时间范围和预处理。",
        ),
        ("method", 57): (
            "Informer 采用编码器—解码器结构处理序列预测任务，是数据驱动分支的主体模型。",
            "可支持方法包含面向长序列预测的 Informer 架构。",
            "尚未说明输入窗口、预测步长、注意力配置和与 WRF-Hydro 的连接位置。",
        ),
        ("method", 61): (
            "Informer 训练时以均方误差 MSE 作为预测误差损失并进行最小化。",
            "可支持训练目标是点预测误差优化。",
            "MSE 不直接约束洪峰、低流量、概率可靠性或水量平衡。",
        ),
        ("method", 63): (
            "论文报告 Informer 的学习率为 0.001、批量大小为 32、训练 20 个 epoch，并采用早停；这些设置在实验中保持一致。",
            "可支持复现数据驱动分支的部分训练配置。",
            "仍缺随机种子、优化器、早停耐心值、搜索范围和最终模型选择规则。",
        ),
        ("validation", 15): (
            "该段说明传统径流预测依赖模拟流域内水运动与分布的水文模型，属于基线背景而非验证协议。",
            "可支持设置 WRF-Hydro 类过程模型作为比较对象的理由。",
            "不能据此确认基线如何校准或测试集如何划分。",
        ),
        ("validation", 21): (
            "该段把深度学习与传统水文模型的整合描述为可结合双方优势的协同思路。",
            "可支持混合比较的设计动机。",
            "这是方法主张，不是独立测试结果，也不能替代消融实验。",
        ),
        ("validation", 43): (
            "迁移建模流程被组织为数据收集、模型训练和验证三个连续步骤，详细设置指向实验部分。",
            "可支持论文具有显式训练与验证流程。",
            "仍需核对时间切分、测试集隔离、调参规则和源—目标数据泄漏。",
        ),
        ("result", 143): (
            "2016 年 WRF-Hydro 的 NSE 在三种模型中最低，而 Informer 与 Hydro-Informer 的 NSE 均为 0.76。",
            "可支持两种学习模型在该年度 NSE 上优于文中的 WRF-Hydro 配置。",
            "单年度单指标不能证明总体显著优势，且需回查表格中的 WRF-Hydro 数值和评价期。",
        ),
        ("result", 145): (
            "作者概括 Hydro-Informer 和 Informer 在多数比较情形下优于 WRF-Hydro；即便混合模型表现最弱时，其结果仍位于两者之间。",
            "可支持作者报告的总体排序趋势。",
            "“多数情形”需要按年份、指标和配置逐项核表，不能表述为无条件最优。",
        ),
        ("result", 149): (
            "2016 年两次显著洪峰期间，Informer 与 Hydro-Informer 的过程线更接近观测，WRF-Hydro 出现较大偏离。",
            "可支持学习模型在这两个洪峰案例中的过程线拟合更好。",
            "图形接近不等于洪峰时刻、峰值误差和提前量均更优，需读取图表数值。",
        ),
        ("result", 163): (
            "讨论部分把径流事件预测精度改善列为 Informer 与 WRF-Hydro 整合后的主要收益之一。",
            "可支持作者对混合模型收益的解释。",
            "讨论性总结必须由前述结果表和消融比较支撑，不能单独作为强证据。",
        ),
        ("limitation", 17): (
            "引言指出传统水文模型往往需要含多参数的复杂校准，带来时间和计算成本。",
            "可支持混合方法试图缓解过程模型校准负担的动机。",
            "这是领域层面挑战，未量化本文 WRF-Hydro 的实际校准成本。",
        ),
        ("limitation", 163): (
            "该段报告混合模型的精度收益，本身没有给出限制或失败条件。",
            "不能用作论文局限的直接证据。",
            "局限判断应优先依据夏季限定、样本范围和作者明确讨论的约束。",
        ),
        ("limitation", 169): (
            "作者明确说明模拟只在夏季月份开展；尽管夏季通常是察尔森流域降雨与径流最高的季节，这会限制结论的时间代表性。",
            "可支持论文结果主要适用于夏季或汛期。",
            "不能外推到枯水期、全年连续运行或其他季节水文过程。",
        ),
        ("uncertainty", 9): (
            "该段把极端天气与数据稀缺列为预报挑战，但没有给出预测分布、置信区间或可靠性指标。",
            "可支持不确定性来源包括气候极端和观测不足。",
            "不能据此声称论文完成了概率不确定性量化。",
        ),
        ("uncertainty", 163): (
            "讨论中的精度改善属于确定性性能结论，没有展示概率可靠性或敏感性结果。",
            "可支持混合模型的作者解释。",
            "不能作为不确定性分析的直接证据。",
        ),
        ("uncertainty", 165): (
            "图 7 比较不同模型组合比例在 2015、2016 汛期的 NSE 和 IOA，反映配置比例变化下的性能差异。",
            "可支持存在一项模型配比敏感性比较。",
            "这不是概率不确定性量化；还需查看原图、配比取值和误差波动。",
        ),
    },
    "P-2025-0016": {
        ("problem", 22): (
            "正文片段称研究涵盖土耳其 Konya 与 Rize 两个气候差异明显的流域，并以 R、NSE、RMSE、SDR 等指标评价。",
            "可支持论文涉及气候差异流域上的多指标降雨—径流比较。",
            "这一研究区描述与题名中的底格里斯河流域不一致，必须核对论文首页、摘要和研究区图。",
        ),
        ("problem", 23): (
            "另一正文片段称使用土耳其幼发拉底河流域站点降雨资料，并以 ANN、GEP 和 MLR 估算径流。",
            "可支持已抽取文本包含站点降雨驱动的多模型径流估算。",
            "幼发拉底、底格里斯以及 Konya/Rize 的并存提示文献身份或正文解析可能混杂，暂不能合并成同一研究设计。",
        ),
        ("data", 37): (
            "研究尝试从九个径流观测站确定月径流值，用于流域管理相关的降雨—径流分析。",
            "可支持观测目标包含多站点月径流。",
            "站名、观测年份、气象变量和缺测处理尚未在该片段中完整出现。",
        ),
        ("data", 168): (
            "研究将流域多边形与相应径流观测站匹配，并评价径流站与气象站的多年平均月值。",
            "可支持数据组织包含空间流域单元、径流站和气象站之间的匹配。",
            "仍需核对配对规则、期望年份的含义以及空间平均方法。",
        ),
        ("data", 321): (
            "该段转述其他研究中 EEMD 相对 LSTM 的表现，属于文献讨论，不是本文数据说明。",
            "不能用来确认本文使用了 EEMD 或相应数据。",
            "本文数据范围应依据研究区、站点和数据章节重新提取。",
        ),
        ("method", 3): (
            "摘要把降雨与径流建模界定为可由概念模型到人工智能方法共同处理的水文问题。",
            "可支持论文采用多类方法比较的总体框架。",
            "摘要层面的宽泛分类不能确认具体模型结构和训练流程。",
        ),
        ("method", 105): (
            "ANFIS 分支采用 Takagi–Sugeno 模糊推理，并用网格划分构建网络层之间的连接。",
            "可支持神经模糊模型的推理形式和结构生成方式。",
            "未给出隶属函数数量、规则数、优化器和防止规则爆炸的处理。",
        ),
        ("method", 352): (
            "该片段位于参考文献表，列举他人的降雨—径流模拟研究，并非本文方法描述。",
            "不能作为本文采用某项方法的证据。",
            "方法判断必须回到正文方法章节和参数表。",
        ),
        ("validation", 164): (
            "论文把 PBIAS=0 视为无总体偏差的理想值，并用正负号区分总体高估与低估。",
            "可支持 PBIAS 在评价体系中的解释方式。",
            "PBIAS 单独不能反映洪峰时刻、过程相关性或局部极端误差。",
        ),
        ("validation", 307): (
            "正文报告 LSTM 的 RMSE 低于其他方法，同时强调水文模型验证仍需结合过程线的视觉检查。",
            "可支持评价不只依赖单一数值指标，并报告了 LSTM 的 RMSE 优势。",
            "仍需核对各站点、测试期和比较方法是否一致，以及差异是否经过统计检验。",
        ),
        ("validation", 346): (
            "该片段是参考文献条目，讨论其他地区的回归与神经网络研究，不是本文验证方案。",
            "不能用于确认本文基线、数据划分或评价结果。",
            "验证证据应来自实验设计、指标定义和结果表。",
        ),
        ("result", 3): (
            "摘要只陈述降雨—径流建模的重要性和可选方法范围，没有报告可核验的实验结果。",
            "可支持研究背景。",
            "不能作为模型优越性或定量结果证据。",
        ),
        ("result", 17): (
            "该段以概括性措辞评价人工智能方法的适应性，主要引用既有研究而非报告本文实验。",
            "可支持作者采用人工智能方法的动机。",
            "不能据此声称本文模型最优。",
        ),
        ("result", 113): (
            "论文说明使用常见性能指标评价所开发方法，但该段未给出模型排序或具体数值。",
            "可支持存在规范的指标评价步骤。",
            "不能作为任何模型改善幅度的结果证据。",
        ),
        ("result", 198): (
            "正文报告 GPR 的一组指标范围：一项指标为 3.48—48.49，RMSE 为 6.60—74.88，R² 为 0.50—0.74，NSE 为 0.45—0.74。",
            "可支持 GPR 在不同评价对象上的性能存在明显区间。",
            "首项指标名称、单位、站点对应关系和测试期需回到结果表确认后才能解释。",
        ),
        ("limitation", 3): (
            "摘要承认降雨—径流建模本身具有挑战性，但没有列出本文特有的失败条件。",
            "可支持研究问题复杂。",
            "不能替代数据、模型和外推层面的具体局限分析。",
        ),
        ("limitation", 16): (
            "正文指出径流量受多种因素共同影响，因此仅从降雨准确确定径流具有内在困难。",
            "可支持输入不完备和过程复杂性是模型边界。",
            "该一般性局限尚未量化本文各因素遗漏造成的误差。",
        ),
        ("limitation", 58): (
            "该段强调神经模糊系统结合模糊规则灵活性和神经网络学习能力，属于预期优势而非实证局限。",
            "可支持选择 ANFIS 的方法动机。",
            "不能用来证明 ANFIS 已成功处理不确定性，也不是失败情形证据。",
        ),
        ("uncertainty", 16): (
            "多因素共同影响径流说明降雨—径流映射存在结构和输入不确定性。",
            "可支持不确定性来源不止降雨观测。",
            "没有概率指标或敏感性实验，不能声称完成了量化。",
        ),
        ("uncertainty", 17): (
            "该段对人工智能适应性的评价主要依赖既有文献，未报告本文的不确定性结果。",
            "只能支持方法选择背景。",
            "不能作为可靠性、置信区间或稳健性证据。",
        ),
        ("uncertainty", 351): (
            "该片段是参考文献条目而非本文正文分析。",
            "不能支持本文开展了不确定性评估。",
            "需要在正文中寻找概率指标、敏感性或稳健性实验。",
        ),
    },
}


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no}: record must be an object")
        value["_record_file"] = path
        rows.append(value)
    return rows


def vault_link(path: Path, vault: Path, label: str) -> str:
    try:
        relative = path.resolve().relative_to(vault.resolve()).as_posix()
        if relative.lower().endswith(".md"):
            relative = relative[:-3]
        return f"[[{relative}|{label}]]"
    except ValueError:
        return f"`{path}`"


def article_link(profile: dict, title: str) -> str:
    url = str(profile.get("url") or "").strip()
    doi = str(profile.get("doi_normalized") or profile.get("doi") or "").strip()
    if not url and doi:
        url = f"https://doi.org/{doi}"
    return f"[{title}]({url})" if url else title


def short_excerpt(snippet: str, maximum_words: int, group: str) -> str:
    compact = snippet.replace("\n", " ")
    words = compact.split()
    lowered = compact.lower()
    anchor_index = 0
    for keyword in GROUP_KEYWORDS.get(group, ()):
        position = lowered.find(keyword)
        if position >= 0:
            anchor_index = len(compact[:position].split())
            break
    start = max(0, min(anchor_index - 2, max(0, len(words) - maximum_words)))
    return " ".join(words[start : start + maximum_words]).strip(" ,;:")


def signals(snippet: str) -> str:
    values: list[str] = []
    for token in WORD_RE.findall(snippet):
        normalized = token.lower()
        if normalized in STOPWORDS or len(token) < 2:
            continue
        if token not in values:
            values.append(token)
        if len(values) == 8:
            break
    return "、".join(values) if values else "研究对象、比较条件和证据边界"


def analysis_for(
    group: str,
    snippet: str,
    paper_id: str = "",
    line_number: int | None = None,
) -> tuple[str, str, str]:
    line_specific = CUSTOM_LINE_ANALYSIS.get(paper_id, {}).get((group, line_number))
    if line_specific:
        return line_specific
    custom = CUSTOM_ANALYSIS.get(paper_id, {}).get(group)
    if custom:
        return custom
    raise ValueError(
        f"{paper_id}: missing reviewed paper-specific analysis for group {group!r}. "
        "Keyword-derived fallback prose is prohibited; create a curated analysis record "
        "and render it with rebuild_substantive_notes.py."
    )
    clues = signals(snippet)
    if group == "problem":
        return (
            f"原文把与“{clues}”相关的现象或需求作为研究问题入口。",
            "可支持论文确实提出了这一问题。",
            "不能据此证明所提方法有效或可推广。",
        )
    if group == "data":
        return (
            f"原文提供了数据、研究区或样本设计线索，当前可核验关键词为：{clues}。",
            "可支持后续回查数据范围和样本条件。",
            "未核对数据表、单位和缺测前，不作为完整数据说明。",
        )
    if group == "method":
        return (
            f"原文描述的方法链或组件涉及：{clues}；该信息用于重建输入—处理—输出关系。",
            "可支持论文使用或组合了这些方法要素。",
            "方法存在不等于性能提升，也不证明物理一致性。",
        )
    if group == "validation":
        return (
            f"原文涉及训练、测试、对照或评价设计，识别到的线索包括：{clues}。",
            "可支持定位验证协议和评价对象。",
            "仍需核查划分时点、强基线和预处理是否使用未来信息。",
        )
    if group == "result":
        return (
            f"原文报告了与“{clues}”有关的比较或结果；当前仅把它作为作者报告的结果线索。",
            "可支持论文报告了相应比较方向。",
            "具体数值、单位、基线和样本条件必须回到图表或上下文复核。",
        )
    if group == "limitation":
        return (
            f"原文暴露了与“{clues}”相关的限制、失败情形或适用边界。",
            "可用于约束论文结论的外推范围。",
            "不能把单个局限片段扩大为对整篇论文的否定。",
        )
    if group == "uncertainty":
        return (
            f"原文出现与不确定性、敏感性或稳健性有关的线索：{clues}。",
            "可支持定位论文是否讨论可靠性。",
            "若未见概率指标或敏感性实验，不能声称已完成不确定性量化。",
        )
    return (
        f"原文给出与数据、代码或材料可得性有关的线索：{clues}。",
        "可支持定位复现入口。",
        "链接、版本、权限和许可证仍需人工确认。",
    )


def evidence_score(group: str, item: dict) -> int:
    snippet = str(item.get("snippet") or "")
    lowered = snippet.lower()
    heading = str(item.get("heading") or "").lower()
    score = min(len(snippet), 500) // 80
    for keyword in GROUP_KEYWORDS.get(group, ()):
        if keyword in lowered:
            score += 5
    if "front matter" not in heading:
        score += 2
    if any(marker in lowered for marker in (" et al.", "j. hydrol", "references", "doi.org/")):
        score -= 12
    if re.match(r"^\s*\d+\.\s+[A-Z][A-Za-z-]+,", snippet):
        score -= 15
    if group == "result" and any(metric in lowered for metric in ("nse", "rmse", "kge", "mape", "r²", "r2")):
        score += 6
    return score


def choose_evidence(record: dict, maximum_cards: int) -> list[tuple[str, dict]]:
    evidence = record.get("fulltext_evidence") or {}
    chosen: list[tuple[str, dict]] = []
    for group in GROUP_PRIORITY:
        items = evidence.get(group) or []
        candidates = [
            candidate for candidate in items
            if isinstance(candidate, dict) and str(candidate.get("snippet") or "").strip()
        ]
        item = max(candidates, key=lambda candidate: evidence_score(group, candidate), default=None)
        if item:
            chosen.append((group, item))
        if len(chosen) >= maximum_cards:
            break
    return chosen


def infer_group(text: str) -> str | None:
    section_match = re.search(r"§\s*([^,，|\n]+)", text)
    if section_match:
        section = section_match.group(1)
        section_map = (
            ("问题", "problem"),
            ("背景", "problem"),
            ("数据", "data"),
            ("观测", "data"),
            ("方法", "method"),
            ("验证", "validation"),
            ("训练", "validation"),
            ("结果", "result"),
            ("局限", "limitation"),
            ("限制", "limitation"),
            ("不确定", "uncertainty"),
            ("可得", "availability"),
        )
        for token, group in section_map:
            if token in section:
                return group
    lowered = text.lower()
    for group, hints in GROUP_HINTS.items():
        if any(hint in lowered for hint in hints):
            return group
    return None


def visible_line_number(text: str) -> int | None:
    match = re.search(r"(?:§[^|\n]{0,100}?[,，]\s*|来源锚点\s*[:：][^|\n]{0,100}?)L(\d+)\b", text, re.I)
    if match:
        return int(match.group(1))
    return None


def needs_content_rewrite(text: str) -> bool:
    return (
        any(phrase in text for phrase in GENERIC_PHRASES)
        or any(pattern.search(text) for pattern in VISIBLE_LOCATOR_PATTERNS)
    )


def evidence_item_for(
    record: dict,
    preferred_group: str | None,
    line_number: int | None,
) -> tuple[str, dict] | tuple[None, None]:
    evidence = record.get("fulltext_evidence") or {}
    groups = [preferred_group] if preferred_group else []
    groups.extend(group for group in GROUP_PRIORITY if group not in groups)
    if line_number is not None:
        for group in groups:
            for item in evidence.get(group, []) or []:
                if not isinstance(item, dict):
                    continue
                try:
                    item_line = int(item.get("line"))
                except (TypeError, ValueError):
                    continue
                if item_line == line_number and str(item.get("snippet") or "").strip():
                    return group, item
    if preferred_group:
        candidates = [
            item for item in evidence.get(preferred_group, []) or []
            if isinstance(item, dict) and str(item.get("snippet") or "").strip()
        ]
        if candidates:
            return preferred_group, max(
                candidates,
                key=lambda candidate: evidence_score(preferred_group, candidate),
            )
    chosen = choose_evidence(record, 1)
    return chosen[0] if chosen else (None, None)


def content_package(record: dict, source_line: str) -> tuple[str, str]:
    profile = record.get("profile") or {}
    paper_id = str(profile.get("paper_id") or profile.get("canonical_literature_id") or "")
    preferred_group = infer_group(source_line)
    line_number = visible_line_number(source_line)
    group, item = evidence_item_for(record, preferred_group, line_number)
    if group is None or item is None:
        group = preferred_group or "problem"
        snippet = ""
    else:
        snippet = str(item.get("snippet") or "")
    analysis, support, boundary = analysis_for(group, snippet, paper_id, line_number)
    package = f"{analysis} 支持：{support} 边界：{boundary}"
    return group, package


def rewrite_table_line(line: str, record: dict) -> str:
    cells = line.split("|")
    group, package = content_package(record, line)
    locator_indexes = [
        index for index, cell in enumerate(cells)
        if any(pattern.search(cell) for pattern in VISIBLE_LOCATOR_PATTERNS)
        or "原文证据卡（见" in cell
        or "全文相关章节" in cell
    ]
    generic_indexes = [
        index for index, cell in enumerate(cells)
        if any(phrase in cell for phrase in GENERIC_PHRASES)
        and index not in locator_indexes
    ]
    if generic_indexes:
        cells[generic_indexes[0]] = f" {package} "
        for index in generic_indexes[1:]:
            cells[index] = " 同上文原文内容分析 "
        for index in locator_indexes:
            cells[index] = " 原文内容分析 "
    elif locator_indexes:
        cells[locator_indexes[0]] = f" {package} "
        for index in locator_indexes[1:]:
            cells[index] = " 同上文原文内容分析 "
    else:
        label = GROUP_LABELS.get(group, group)
        return f"| 原文内容分析（{label}） | {package} |"
    return "|".join(cells)


def rewrite_human_evidence(text: str, record: dict) -> str:
    rewritten: list[str] = []
    for line in text.splitlines():
        if not needs_content_rewrite(line):
            rewritten.append(line)
            continue
        if line.lstrip().startswith("|") and line.rstrip().endswith("|"):
            new_line = rewrite_table_line(line, record)
        else:
            group, package = content_package(record, line)
            indent = line[: len(line) - len(line.lstrip())]
            new_line = (
                f"{indent}- **原文内容分析（{GROUP_LABELS.get(group, group)}）：** "
                f"{package}"
            )
        if not rewritten or rewritten[-1] != new_line:
            rewritten.append(new_line)
    return "\n".join(rewritten)


def index_markdown(directory: Path | None) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if directory is None or not directory.exists():
        return index
    for path in directory.glob("*.md"):
        text = path.read_text(encoding="utf-8-sig")
        match = ID_RE.search(text[:5000])
        if match:
            index[match.group(1)] = path
    return index


def render_section(
    record: dict,
    markdown_path: Path,
    vault: Path,
    manifest: Path,
    paired_path: Path | None,
    maximum_cards: int,
    maximum_words: int,
) -> str:
    profile = record.get("profile") or {}
    paper_id = str(profile.get("paper_id") or profile.get("canonical_literature_id") or "")
    title = str(record.get("title_cn") or profile.get("title") or paper_id)
    original_title = str(profile.get("title") or title)
    source_path = str(record.get("source_path") or profile.get("source_path") or "")
    record_file = Path(record["_record_file"])
    evidence_status = str(record.get("evidence_status") or profile.get("evidence_status") or "unknown")
    review_status = str(record.get("review_status") or profile.get("review_status") or "unknown")
    lines = [
        START,
        "## 原文证据与分析",
        "",
        f"- 文献：{article_link(profile, title)}",
        f"- 原文题名：{original_title}",
        f"- 证据/复核状态：`{evidence_status}` / `{review_status}`",
        "- 说明：可见内容直接说明原文讲了什么、支持什么以及不能推出什么；抽取行号和段落编号仅保存在机器证据记录中。",
        "",
    ]
    chosen = choose_evidence(record, maximum_cards)
    if not chosen:
        lines.extend(
            [
                "### 当前可用证据",
                "",
                "- 原文短摘：未获得可安全展示的原文片段。",
                "- 中文分析（AI概括）：当前记录只能确认文献身份与证据状态，不能支持具体科学结论。",
                "- 支持：文献存在及其书目信息。",
                "- 边界：方法、结果和局限均待人工回查。",
                "",
            ]
        )
    for number, (group, item) in enumerate(chosen, 1):
        snippet = str(item.get("snippet") or "")
        excerpt = short_excerpt(snippet, maximum_words, group)
        try:
            source_line = int(item.get("line"))
        except (TypeError, ValueError):
            source_line = None
        analysis, support, boundary = analysis_for(
            group,
            snippet,
            paper_id,
            source_line,
        )
        heading = str(item.get("heading") or "章节待核验")
        card_lines = [
            f"### 证据卡 {number}：{GROUP_LABELS.get(group, group)}",
            "",
            f"- 原文短摘（不超过 {maximum_words} 词）：“{excerpt}”",
            f"- 中文分析（AI概括）：{analysis}",
            f"- 支持：{support}",
            f"- 边界：{boundary}",
        ]
        if heading.strip().lower() not in {"front matter", "章节待核验"}:
            card_lines.append(f"- 来源章节：{heading}")
        card_lines.append("")
        lines.extend(card_lines)
    lines.extend(
        [
            "## 本文件实际使用的来源",
            "",
            "| 类型 | 完整名称 | 链接或文件 | 本文件中的用途 |",
            "|---|---|---|---|",
            f"| 原始文献 | {title} | {article_link(profile, 'DOI/出版社页面')} | 书目信息与原文证据 |",
        ]
    )
    if source_path.startswith("zotero://"):
        lines.append(f"| Zotero | {title} 的本地 Zotero 条目 | [{source_path}]({source_path}) | 本地书目与全文定位 |")
    lines.append(
        f"| 机器证据记录 | {record_file.name} | {vault_link(record_file, vault, record_file.name)} | 原文片段、证据状态与抽取定位 |"
    )
    lines.append(
        f"| 输入清单 | {manifest.name} | {vault_link(manifest, vault, manifest.name)} | 批次身份与纳入范围 |"
    )
    if paired_path is not None:
        role = "对应精读笔记" if "profiles" in markdown_path.parts else "对应轻量画像"
        lines.append(f"| {role} | {paired_path.name} | {vault_link(paired_path, vault, paired_path.stem)} | 交叉阅读与证据复核 |")
    lines.extend(["", END, ""])
    return "\n".join(lines)


def replace_section(text: str, section: str, record: dict) -> str:
    text = rewrite_human_evidence(text, record)
    if START in text and END in text:
        pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
        return pattern.sub(lambda _: section.strip(), text).rstrip() + "\n"
    return text.rstrip() + "\n\n" + section


def validate_file(path: Path, title: str) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    errors: list[str] = []
    for required in (START, END, "## 原文证据与分析", "## 本文件实际使用的来源", title):
        if required not in text:
            errors.append(f"{path}: missing {required}")
    if "全文相关章节" in text:
        errors.append(f"{path}: contains bare 全文相关章节")
    for pattern in VISIBLE_LOCATOR_PATTERNS:
        if pattern.search(text):
            errors.append(f"{path}: contains visible extraction locator: {pattern.pattern}")
    for phrase in GENERIC_PHRASES:
        if phrase in text:
            errors.append(f"{path}: contains generic evidence placeholder: {phrase}")
    if "中文分析（AI概括）" not in text:
        errors.append(f"{path}: missing Chinese evidence analysis")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-root", required=True)
    parser.add_argument("--records", action="append", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--profile-dir", required=True)
    parser.add_argument("--note-dir")
    parser.add_argument("--mode", choices=("apply", "check"), default="apply")
    parser.add_argument(
        "--target-kind",
        choices=("all", "profile", "note"),
        default="all",
        help="Rewrite all mapped files, only profiles, or only existing deep notes.",
    )
    parser.add_argument("--max-excerpts", type=int, default=3)
    parser.add_argument("--max-words", type=int, default=8)
    parser.add_argument(
        "--paper-id",
        action="append",
        help="Limit the run to one or more paper IDs; repeat for multiple samples.",
    )
    args = parser.parse_args()

    vault = Path(args.vault_root).resolve()
    manifest = Path(args.manifest).resolve()
    profile_dir = Path(args.profile_dir).resolve()
    note_dir = Path(args.note_dir).resolve() if args.note_dir else None
    records: dict[str, dict] = {}
    for record_path in args.records:
        for record in load_jsonl(Path(record_path).resolve()):
            profile = record.get("profile") or {}
            paper_id = str(profile.get("paper_id") or profile.get("canonical_literature_id") or "")
            if paper_id:
                records[paper_id] = record
    if args.paper_id:
        requested = set(args.paper_id)
        records = {paper_id: record for paper_id, record in records.items() if paper_id in requested}
        missing_requested = sorted(requested - set(records))
        if missing_requested:
            print(json.dumps(
                {"status": "FAIL", "missing_requested_paper_ids": missing_requested},
                ensure_ascii=False,
                indent=2,
            ))
            return 1

    profiles = index_markdown(profile_dir)
    notes = index_markdown(note_dir)
    written: list[str] = []
    errors: list[str] = []
    for paper_id, record in records.items():
        profile = record.get("profile") or {}
        title = str(record.get("title_cn") or profile.get("title") or paper_id)
        targets = []
        if args.target_kind in {"all", "profile"} and paper_id in profiles:
            targets.append((profiles[paper_id], notes.get(paper_id)))
        if args.target_kind in {"all", "note"} and paper_id in notes:
            targets.append((notes[paper_id], profiles.get(paper_id)))
        for target, paired in targets:
            if args.mode == "apply":
                text = target.read_text(encoding="utf-8-sig")
                section = render_section(
                    record, target, vault, manifest, paired,
                    args.max_excerpts, args.max_words,
                )
                target.write_text(replace_section(text, section, record), encoding="utf-8")
                written.append(str(target))
            errors.extend(validate_file(target, title))

    missing_profiles = (
        sorted(set(records) - set(profiles))
        if args.target_kind in {"all", "profile"}
        else []
    )
    result = {
        "status": "PASS" if not errors and not missing_profiles else "FAIL",
        "mode": args.mode,
        "records": len(records),
        "profiles_enriched": len(set(profiles) & set(records)),
        "notes_enriched": len(set(notes) & set(records)),
        "files_written": len(written),
        "missing_profiles": missing_profiles,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
