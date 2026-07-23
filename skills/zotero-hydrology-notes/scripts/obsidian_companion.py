#!/usr/bin/env python3
"""Generate title-first UTF-8 Markdown companions for a Zotero profile batch."""
import argparse, csv, json, re
from pathlib import Path

def csv_rows(path):
    if not path.exists(): return []
    with path.open("r",encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))
def jsonl(paths):
    out=[]
    for path in paths:
        with path.open("r",encoding="utf-8") as f: out += [json.loads(x) for x in f if x.strip()]
    return out
def cell(v):
    if v is None: return "—"
    if isinstance(v,list): v="；".join(str(x) for x in v if x not in (None,""))
    return str(v).replace("\r"," ").replace("\n"," ").replace("|","\\|").strip() or "—"
def human_notes(item):
    """Remove internal Zotero identifiers from prose shown to Obsidian readers."""
    value=cell(item.get("notes"))
    value=re.sub(r"Zotero item key\s*=\s*[A-Z0-9]+[。.]?\s*", "", value, flags=re.IGNORECASE)
    return value or "—"
def key(item):
    if item.get("zotero_item_key") or item.get("item_key"): return str(item.get("zotero_item_key") or item.get("item_key"))
    for p in item.get("provenance",[]):
        loc=str(p.get("locator",""))
        if loc.startswith("zotero://"): return loc.split("/")[-1].split("#")[0]
    return ""
def link(item):
    title=cell(item.get("title_cn") or item.get("title")); u=item.get("url") or (f"https://doi.org/{item['doi']}" if item.get("doi") else ""); k=key(item)
    return (f"[{title}]({u})" if u else title)+(f" · [Zotero](zotero://select/library/items/{k})" if k else "")
def article_url(item):
    return item.get("url") or (f"https://doi.org/{item['doi']}" if item.get("doi") else "")
def safe_note_name(item,used):
    title=str(item.get("title") or "未命名文献")
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", title)
    name=re.sub(r"\s+", " ", name).strip(" .")
    year=str(item.get("year") or "").strip()
    base=(f"{year}_{name}" if year else name)[:150].rstrip(" .") or "未命名文献"
    candidate=base; ordinal=2
    while candidate.casefold() in used:
        candidate=f"{base[:135].rstrip()}（同名文献{ordinal}）"; ordinal+=1
    used.add(candidate.casefold()); return candidate
def checks(item):
    text=" ".join(str(item.get(k,"")) for k in ["title","research_problem","methods","notes"]).lower(); out=[]
    rules=[
      (["ungauged","transfer","regional","无资料","迁移"],"核验空间留出是否以流域为单位、训练属性是否覆盖目标流域，以及所谓泛化是否只是同区域插值。"),
      (["flood","extreme","洪水","洪峰"],"除平均NSE/KGE外，核验洪峰幅度、峰现时间、命中/虚警、极端样本量及阈值定义。"),
      (["hybrid","physics","physical","混合","物理"],"拆分物理信息进入方式，检查消融、守恒、非负约束及增益是否受底层过程模型质量控制。"),
      (["uncert","probabil","bayes","不确定"],"同时检查覆盖率与区间宽度、域外校准、极端覆盖和强概率基线，避免只报告名义置信度。"),
      (["reservoir","operation","调度","水库"],"核验输入在业务时刻是否可得，并把统计技能连接到供水、防洪、成本、迟滞和失效后果。"),
      (["vmd","emd","wavelet","decomposition","分解"],"检查分解、标准化和特征选择是否只在训练折拟合，并与严格滚动预报和简单基线比较。"),
      (["graph","gnn","topology","河网"],"核验拓扑是否真实可得、空间切分是否避免邻接泄漏，以及上下游输出是否一致。"),
      (["climate","cmip","future","气候"],"区分历史拟合与非平稳外推，检查偏差订正独立性和跨气候模式稳健性。"),
      (["explain","interpret","解释"],"将特征归因与因果机制分开，检查解释对随机种子、背景样本和共线变量是否稳健。")]
    for keys,msg in rules:
        if any(k in text for k in keys): out.append(msg)
    return (out or ["核验时间/空间/事件划分、输入可得性、强基线、极端指标和失败流域，不以摘要性能措辞替代全文证据。"] )[:3]
def write(path,lines):
    text="\n".join(lines).rstrip()+"\n"; bad=[x for x in ["�","æ–‡çŒ®","ç²¾è¯»","â€“","Ã±"] if x in text]
    if bad: raise ValueError(f"mojibake in {path}: {bad}")
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text,encoding="utf-8")
def profile_card(p):
    findings=p.get("main_findings") or []; innovations=p.get("claimed_innovations") or []; limits=p.get("limitations") or []
    title=str(p.get("title") or "未命名文献").replace('"', "'")
    L=["---",f'title: "{title}"',f'year: "{cell(p.get("year"))}"',f'venue: "{cell(p.get("venue")).replace(chr(34), chr(39))}"',f'evidence_level: "{cell(p.get("access_level"))}"',f'review_level: "{cell(p.get("review_level"))}"',"---","",f"# {link(p)}","","> [!info] 轻量画像","> 用于精读筛选，不替代全文证据；正式引用必须回到全文章节、图表或页码。","",f"- 作者：{cell(p.get('authors'))}",f"- 年份/期刊：{cell(p.get('year'))}｜{cell(p.get('venue'))}",f"- DOI：{('[DOI](' + article_url(p) + ')') if article_url(p) else '未报告'}",f"- 证据/复核：`{cell(p.get('access_level'))}` / `{cell(p.get('review_level'))}`","","## 研究设计画像","",f"- 研究问题：{cell(p.get('research_problem'))}",f"- 预测对象与提前期：{cell(p.get('forecast_target'))}；{cell(p.get('forecast_horizon'))}",f"- 空间/时间尺度：{cell(p.get('spatial_scale'))}；{cell(p.get('temporal_resolution'))}",f"- 研究区域与数据：{cell(p.get('study_region'))}；{cell(p.get('datasets'))}",f"- 方法：{cell(p.get('methods'))}",f"- 基线：{cell(p.get('baselines'))}",f"- 指标：{cell(p.get('metrics'))}","","## 摘要级发现",""]
    L += [f"- {cell(x)}" for x in findings] or ["- 摘要未提供足够结果，需全文核验。"]
    L += ["","## 作者声称创新",""]+([f"- {cell(x)}" for x in innovations] or ["- 摘要未明确报告；不得自行补写创新。"])
    L += ["","## 已知局限与待核验边界",""]+([f"- {cell(x)}" for x in limits] or ["- 摘要不足以支持具体局限判断；需检查全文数据、实验和讨论。"])
    L += ["","## 精读筛选提示",""]+[f"- {x}" for x in checks(p)]+["","## 证据边界","",f"- {human_notes(p)}","- 本画像不可直接作为论文引文；正式引用必须回到全文章节、图表或页码。"]
    return L
def profile_view(root,batch,profiles):
    base=root/"10_文献知识"/"profiles"; folder=base/"机器学习水文预报"; used=set(); entries=[]
    for p in profiles:
        note_name=safe_note_name(p,used); note_path=folder/f"{note_name}.md"; write(note_path,profile_card(p)); entries.append((p,note_path))
    index=folder/f"{batch}_轻量画像_Obsidian版.md"
    L=["---",'title: "机器学习水文预报轻量画像索引"','evidence_status: "abstract"',"---","","# 机器学习水文预报轻量画像索引","",f"> 共{len(entries)}篇；每篇论文对应一个Markdown文件。题名链接文章页面，画像链接进入本地笔记。",""]
    for p,note_path in entries:
        L += [f"- [[{note_path.stem}|{cell(p.get('title'))}]]"+(f" · [文章页面]({article_url(p)})" if article_url(p) else "")+(f" · [Zotero](zotero://select/library/items/{key(p)})" if key(p) else "")]
    write(index,L)
    compatibility=base/f"{batch}_轻量画像_Obsidian版.md"
    write(compatibility,["---",'title: "机器学习水文预报轻量画像入口"',"---","","# 机器学习水文预报轻量画像入口","","> 轻量画像已按“一篇论文一个文件”拆分到主题目录。","",f"[[机器学习水文预报/{index.stem}|打开{len(entries)}篇轻量画像索引]]"])
    return index,entries
def table(path,title,rows,cols,note):
    L=["---",f'title: "{title}"',"---","",f"# {title}","",f"> {note}",""]
    if rows:
        L += ["| "+" | ".join(v for _,v in cols)+" |","|"+"|".join("---" for _ in cols)+"|"]
        L += ["| "+" | ".join(cell(r.get(k)) for k,_ in cols)+" |" for r in rows]
    else: L.append("无记录。")
    write(path,L); return path
def with_titles(rows,profiles):
    idx={p.get("paper_id"):p for p in profiles}; out=[]
    for row in rows: n=dict(row); n["paper"]=link(idx[row["paper_id"]]) if row.get("paper_id") in idx else "未能关联到论文题名"; out.append(n)
    return out
def front(path,name):
    for line in path.read_text(encoding="utf-8").splitlines()[:40]:
        if line.startswith(name+":"): return line.split(":",1)[1].strip().strip('"')
    return ""
def main():
    a=argparse.ArgumentParser(); a.add_argument("--vault-root",required=True); a.add_argument("--batch-id",required=True); x=a.parse_args(); root=Path(x.vault_root).resolve(); batch=x.batch_id
    pfiles=sorted((root/"10_文献知识"/"profiles").glob(f"{batch}*_paper_profiles.jsonl")); profiles=jsonl(pfiles)
    fulltext_machine=root/"10_文献知识"/"evidence"/f"{batch}_fulltext_records.jsonl"
    profile_index=root/"10_文献知识"/"profiles"/"机器学习水文预报"/f"{batch}_轻量画像_Obsidian版.md"
    if not fulltext_machine.exists() or not profile_index.exists():
        raise RuntimeError("Completed Obsidian profiles require the full-text audit and fulltext_profile_batch.py; abstract-only companion generation is disabled.")
    fulltext_records=jsonl([fulltext_machine]); profiles=[{**row["profile"], "title_cn": row.get("title_cn")} for row in fulltext_records]; profile_entries=[None]*len(profiles); made=[profile_index]
    profiles_by_doi={str(p.get("doi") or "").casefold():p for p in profiles if p.get("doi")}
    inv=root/"10_文献知识"/"sources"/f"{batch}_120篇样本文献清单.csv"; ir=[]
    for row in csv_rows(inv):
        n=dict(row); matched=profiles_by_doi.get(str(row.get("doi") or "").casefold()); n["paper"]=link(matched or row); ir.append(n)
    made.append(table(inv.with_name(f"{batch}_120篇文献清单_Obsidian版.md"),"120篇文献清单（Obsidian版）",ir,[("paper","文献"),("year","年份"),("venue","期刊"),("profile_selected","已画像")],"只含元数据，不代表全文已读；题名链接文章页面。"))
    core=root/"10_文献知识"/"core"/f"核心文献选择_{batch}.csv"; made.append(table(core.with_name(f"核心文献选择_{batch}_Obsidian版.md"),"核心文献选择（Obsidian版）",with_titles(csv_rows(core),profiles),[("paper","文献"),("theme_relevance_score","主题相关"),("representative_score","代表性"),("frontier_score","前沿性"),("conflict_score","冲突性"),("evidence_value_score","证据价值"),("total_score","总分"),("roles","作用"),("deep_read_status","精读状态")],"五维评分只用于排序和角色覆盖；期刊层级不计分、不否决。人读视图以论文题名和链接识别文献。"))
    qc=root/"10_文献知识"/"quality"/f"{batch}_质量抽检.csv"; made.append(table(qc.with_name(f"{batch}_质量抽检_Obsidian版.md"),"质量抽检（Obsidian版）",with_titles(csv_rows(qc),profiles),[("paper","文献"),("checker","检查人"),("issue","问题"),("severity","严重度"),("action","处理")],"机器结构抽检不得冒充独立人工复核。"))
    err=root/"10_文献知识"/"errors"/f"{batch}_失败记录.csv"; made.append(table(err.with_name(f"{batch}_失败记录_Obsidian版.md"),"失败记录（Obsidian版）",csv_rows(err),[("stage","阶段"),("reason","原因"),("action","处理"),("status","状态")],"无法解析为论文题名的技术标识只保留在机器CSV。"))
    nav=root/"10_文献知识"/f"{batch}_Obsidian导航.md"; notes=sorted((root/"文献"/"机器学习深度学习流域水文预报"/"文献笔记").glob("*_精读笔记.md")); L=["---",f'title: "{batch} 文献批次导航"',"---","",f"# {batch} 文献批次导航","","## 人读入口",""]+[f"- [[{p.stem}]]" for p in made]+[f"- [[{batch}_全文覆盖审计]]",f"- [[{batch}_核心文献证据索引]]",f"- [[{batch}_全文画像与精读验收]]",f"- [[00_核心精读索引_{batch}]]",f"- [[{batch}_批次交付说明]]","","## 精读笔记",""]
    for p in notes:
        title=front(p,"title") or p.stem; doi=front(p,"doi"); article=f"[{title}](https://doi.org/{doi})" if doi else title; L.append(f"- {article} · [[{p.stem}|精读笔记]]")
    L += ["","## 机器文件","> 以下只供脚本和追溯使用；日常阅读使用上方Markdown。",""]+[f"- `{p.relative_to(root).as_posix()}`" for p in pfiles+[inv,core,qc,err] if p.exists()]; write(nav,L); made.append(nav)
    print(json.dumps({"status":"created","profiles":len(profiles),"profile_files":len(profile_entries),"files":[str(p) for p in made]},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
