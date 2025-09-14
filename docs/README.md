# 文档总索引 (Authority Index)

本文件为 HomeSystem 唯一权威文档索引。所有知识类 Markdown 文档新增 / 更新 / 废弃，均需在此登记或调整。严禁出现“文档已存在但未被索引”情况。

> 维护流程简述：
> 1. 新建文档：按命名规范创建 + 填写 Front Matter 草稿字段。
> 2. 在下方表格新增行（ID 初稿可留 `TBD`，合并前需补齐）。
> 3. 更新/修订：刷新 `updated` 字段。
> 4. 废弃：`status=deprecated` + 填写 `废弃原因` 与 `替代`（如有）。
> 5. 自动/人工校验：确保无“孤立文件”。

## 索引表
| ID | 路径 | 类型 | 摘要 | 上游依赖 | 下游引用 | 模块 | Owner | 状态 | 创建 | 更新 | 替代 | 废弃原因 |
|----|------|------|------|----------|----------|------|-------|------|------|------|------|----------|
| DOC-001 | (示例占位，提交前删除) | architecture/project-structure-v2025-09-14.md | 目录与模块划分说明 | - | - | graph,workflow | core-team | draft | 2025-09-14 | 2025-09-14 | - | - |

（在此表格末尾顺序追加，不修改历史行；ID 递增且不复用）

## 命名规范回顾
`<类型>-<主题>-v<YYYY-MM-DD>[(-r<修订号>)] .md`
示例：`integration-llm-config-v2025-09-14.md` ；修订：`integration-llm-config-v2025-09-14-r1.md`

允许的 `类型`（扩展需在此处声明）：
`integration | api | architecture | deployment | workflow | troubleshooting | analysis | testing | glossary | other`

## Front Matter 模板
```yaml
---
title: <标题>
id: DOC-xxx
type: <见类型列表>
created: 2025-09-14
updated: 2025-09-14
owner: <维护人/团队>
modules: [graph]
upstream: []
status: draft
superseded_by: null
deprecated_reason: null
---
```

## 任务绑定提醒
- 任务开始前：引用上游文档 ID（若无 → 说明原因）
- 任务结束：保证产出文档已登记并有正确 ID

## 校验建议（可脚本化）
- 列出 `docs/**/*.md` 与表格路径差集 → 为空
- 检查表格 ID 是否严格递增 & 无重复
- 检查所有 `deprecated` 行均填写废弃原因
- 检查仍被引用的文档其 `status` 不能为 `draft` 超过 7 天

## 变更历史（手工或自动记录）
| 时间 | 操作 | 影响 ID | 说明 | 执行人 |
|------|------|---------|------|--------|
| 2025-09-14 | init | - | 创建初始索引文件 | system |

（后续追加）
