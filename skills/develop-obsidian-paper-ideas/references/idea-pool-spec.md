# Cross-theme Idea pool specification

`40_选题池/` is the mentor-facing control layer. It compares directions across themes and projects; it does not replace detailed Appendix A.3 documents under `任务/<项目>/03_选题管理/`.

## Required Markdown frontmatter

```yaml
---
类型: 跨主题候选选题比较
pool_id: POOL-<YYYYMMDD>-<NN>
source_batch_id: <batch or mixed>
status: V0临时判断
knowledge_status: candidate
decision_status: waiting_for_mentor_decision
generated_at: <timestamp with timezone>
---
```

`mentor_confirmed` is forbidden unless a separate dated mentor decision is supplied.

## Required sections

1. 本轮边界与状态
2. 跨主题排序总表
3. 否决检查
4. 逐方向比较
5. 共同依赖、重叠与互斥
6. 导师快速决策入口
7. 本次实际使用的来源

Every ranked row must show:

- rank or `accepted/reserve/rejected`;
- complete Idea title and usable Obsidian link;
- theme/project;
- recommendation and score;
- fatal-gate status;
- decisive evidence;
- decisive unknown;
- minimum validation;
- next action.

Pool scores are provisional and cannot override a fatal gate. A direction without a complete task-level Idea may appear only as `reserve` or `rejected`, with the missing contract named.

## Machine record

Write one JSON object conforming to `idea-pool.schema.json`. Its `accepted_idea_ids` must equal the candidate JSONL IDs, and every accepted entry must contain `detail_path`.
