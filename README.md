# Zotero & Obsidian Research Skills

[中文](#中文) · [English](#english)

Four reusable Codex skills for academic literature discovery, Zotero management, hydrology paper reading, evidence-traceable Obsidian research synthesis, and publishable paper Idea development.

## 中文

本仓库包含四个面向科研工作流的 Codex Skill。公开版本不包含作者的学校、真实姓名、私人用户名、本机目录、Zotero 文库数据、Obsidian 仓库正文、API Key、Cookie 或登录信息。

### Skill 概览

| Skill | 功能 | 主要输入 | 主要输出 |
| --- | --- | --- | --- |
| `zotero-literature-import` | 多源检索高质量论文，候选内部查重与 Zotero 库内查重，复用已有条目，并抓取合法可访问的 PDF | 研究主题、筛选条件、目标 Zotero collection | Zotero 条目、PDF 附件、查重与导入报告 |
| `zotero-hydrology-notes` | 读取 Zotero 与 llm-for-zotero/MinerU 生成的 Markdown，按水文水资源与水利工程模板生成证据标注精读笔记 | 题名、作者、年份、DOI 或 Zotero item key | 单篇/多篇 Markdown 精读笔记 |
| `analyze-obsidian-research` | 综合 Obsidian 中的文献、数据、项目和任务，路由到研究问题簇并生成可追溯分析 | 科研问题、建议或判断、Obsidian vault | 问题簇分析 Markdown 与证据账本 |
| `develop-obsidian-paper-ideas` | 读取问题簇、文献、数据、项目和任务，筛选可证伪的论文 Idea，完成价值、创新、可行性、方法、风险与投稿贡献分析 | 研究主题/问题、Idea 数量、Obsidian vault | 每个 Idea 一份完整分析、候选索引、证据账本与最小验证方案 |

### 安装

克隆仓库后，将需要的 Skill 文件夹复制到 Codex 用户级 Skill 目录：

```powershell
git clone https://github.com/<github-username>/zotero-obsidian-research-skills.git
Copy-Item -Recurse .\zotero-obsidian-research-skills\skills\zotero-literature-import "$HOME\.codex\skills\"
Copy-Item -Recurse .\zotero-obsidian-research-skills\skills\zotero-hydrology-notes "$HOME\.codex\skills\"
Copy-Item -Recurse .\zotero-obsidian-research-skills\skills\analyze-obsidian-research "$HOME\.codex\skills\"
Copy-Item -Recurse .\zotero-obsidian-research-skills\skills\develop-obsidian-paper-ideas "$HOME\.codex\skills\"
```

重启 Codex，然后使用 `$zotero-literature-import`、`$zotero-hydrology-notes`、`$analyze-obsidian-research` 或 `$develop-obsidian-paper-ideas` 调用。

只安装新 Skill 时，也可以下载 [develop-obsidian-paper-ideas.zip](packages/develop-obsidian-paper-ideas.zip)，解压后把同名文件夹复制到 Codex 用户级 Skill 目录。

### 配置

`zotero-literature-import`：

- 需要运行中的 Zotero Desktop，并开启本地 API/Connector（通常为 `127.0.0.1:23119`）。
- 若要把已同步的现有条目自动加入 collection，设置 `ZOTERO_USER_ID` 和具有写权限的 `ZOTERO_API_KEY`。
- 机构访问必须由用户显式提供 `ZOTERO_INSTITUTION_NAME` 或在当前提示词中说明；Skill 不预设任何学校。

`zotero-hydrology-notes`：

- 需要 Zotero、llm-for-zotero/MinerU 的本地 Markdown 缓存以及笔记模板。
- 设置 `HYDROLOGY_NOTE_TEMPLATE` 为模板绝对路径。
- 设置 `HYDROLOGY_NOTE_OUTPUT` 为笔记输出目录。

`analyze-obsidian-research`：

- 在提示词中提供 vault 根目录，或从当前工作区/仓库根目录解析。
- 写入前遵循 vault 中适用的 `AGENTS.md` 和目录规则。

`develop-obsidian-paper-ideas`：

- 优先读取 `文献/*/文献问题簇/`、`数据/`、`项目/` 和 `任务/`；材料不足时保留 `待核验`，不会把“当前未检出”直接写成文献空白。
- 汛限水位主题默认路由到 `任务/汛限水位动态控制试点/03_选题管理`；其他主题按 vault 中匹配的任务项目解析。
- 每个 Idea 使用完整 16 节分析模板，并附实际使用的文献、数据、项目、任务和用户输入证据账本；多 Idea 额外生成候选索引。
- `scripts/idea_vault_inventory.py` 默认只读；只有显式使用 `resolve-target --create` 时才创建已解析的目标目录，不修改文献、原始数据或现有 Idea。
- 可配合 `nature-academic-search`、`nature-reader`、`nature-ref-verifier`、`nature-writing`、`nature-statistics` 等学术 Skill；外部检索只使用抽象的公开研究概念，不上传私人 vault 内容。

### 安全边界

- 不直接修改 `zotero.sqlite`。
- 不上传私人论文、未公开材料或 Obsidian 仓库正文到公共服务。
- 不绕过付费墙、验证码、许可或机构访问限制。
- 密码、MFA、Cookie、API Key 和浏览器令牌必须由用户保管。
- Zotero 写入操作默认 dry-run，并要求显式确认。
- 论文 Idea 生成不会把未公开论文、内部项目资料或私人数据发送到公共服务。

## English

This repository contains four portable Codex skills for research workflows. The public release contains no personal institution, real name, private username, local vault path, Zotero library data, private Obsidian content, API key, cookie, or login credential.

### Included skills

- `zotero-literature-import`: discover and rank papers, deduplicate candidates and a Zotero library, reuse existing records, and capture lawfully accessible PDFs.
- `zotero-hydrology-notes`: turn local Zotero and llm-for-zotero/MinerU Markdown into evidence-labeled hydrology and water-engineering reading notes.
- `analyze-obsidian-research`: synthesize literature, data, projects, and tasks from an Obsidian vault into source-traceable research-cluster analyses.
- `develop-obsidian-paper-ideas`: turn vault evidence and a research prompt into falsifiable, source-traceable paper Idea analyses, candidate rankings, risk gates, and minimum-validation plans.

Install one or more folders from `skills/` into `~/.codex/skills/`, restart Codex, and invoke the skill with its `$skill-name` mention. See the Chinese configuration section above for environment variables and safety boundaries.

## Requirements

- Codex with local Skill support
- Python 3.10+ for bundled Python utilities
- PowerShell 7+ for the Obsidian inventory helper
- Zotero Desktop for the two Zotero workflows
- Optional: llm-for-zotero/MinerU cache for hydrology notes

All bundled scripts use the Python standard library. Companion skills referenced by these workflows, such as academic search, reference verification, or web access, are optional but improve coverage when installed.

## Validation

```powershell
python scripts/validate_repo.py
```

## License

MIT. See [LICENSE](LICENSE).
