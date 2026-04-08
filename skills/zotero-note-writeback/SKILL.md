---
name: zotero-note-writeback
description: Use when the user wants to write current discussion, reading notes, quotes, questions, or AI summaries back into an existing Zotero item, including cases where the target item must first be resolved from title, author, quote, attachment, or source Markdown hints, and including optional requests to keep a local Markdown copy of the same note at the same time.
---

# Zotero Note Writeback

## Overview

把 Agent Workspace 里的讨论结果整理成结构化 Zotero note，并尽量安全地写回到正确的 Zotero 条目下面。

核心策略是 `search-first, cache-later`：
- 先根据标题、作者、原始 query 或源 Markdown 线索解析目标条目
- 命中后再缓存 `source_markdown_path -> parent_item_key`
- 目标不明确时宁可停下来确认，也不要误写

这版支持：
- 只写回 Zotero
- Zotero + 本地 Markdown 双写
- 在 note 中附带 Zotero deep link

## When To Use

- 用户明确要把当前讨论、阅读笔记、摘录、问题或 AI 回应写回 Zotero
- 用户希望把 Markdown / 对话内容整理成 Zotero note
- 目标 bibliographic item 已存在，但需要先靠标题、作者、引文或源文件线索解析
- 用户希望写回后的笔记带有可点击的 Zotero 条目链接或 PDF 跳页链接

不要在这些情况下用：
- 用户只想保留本地 Markdown，不想写回 Zotero
- 没有可辨认的目标条目，且标题、作者、引文线索都很弱
- 同一个请求里还要求“先新建条目”或“先建 collection”

## Required Setup

- `zotero-cli-cc` 可用
- 本地 Zotero 数据目录可读
- 写回时按需提供：
  - `ZOT_DATA_DIR`
  - `ZOT_LIBRARY_ID`
  - `ZOT_API_KEY`

脚本路径：
- `scripts/writeback_tool.py`
- `scripts/writeback_from_search.py`
- `scripts/save_local_copy.py`
- `scripts/replay_runner.py`

## Payload Shape

优先整理成结构化 JSON，再执行搜索与写回。推荐字段：
- `title`
- `focus`
- `summary`
- `tags`
- `source_quote`
- `user_points`
- `ai_response`
- `collaboration`
- `locator`
- `note_granularity`
- `point_count_hint`

默认粒度规则：
- 默认使用 `atomic`
- 一条笔记只讲一个点
- 如果明显包含多个点，先拆成多条 note 候选，再逐条写回

## Locator Contract

`locator` 不再只是自由文本备注，默认按结构化字段处理。

最小可用形状：

```json
{
  "locator": {
    "attachment_key": "ATTFAK01",
    "library_scope": "library",
    "group_id": null,
    "page": 24,
    "page_label": "24",
    "annotation_key": null,
    "attachment_type": "pdf",
    "source_markdown_path": "C:/path/to/source.md"
  }
}
```

字段含义：
- `attachment_key`: PDF 附件 key。生成 PDF deep link 的必需字段
- `library_scope`: `library` 或 `groups`
- `group_id`: 仅群组库需要
- `page`: 页码级跳转的页码
- `page_label`: 可选，控制链接展示文本
- `annotation_key`: 若已有 Zotero annotation，则升级为 annotation 级跳转
- `attachment_type`: 展示用，建议对 PDF 写 `pdf`
- `source_markdown_path`: 溯源用

## Deep Link Policy

默认使用 Zotero deep link，不使用本地文件绝对路径。

个人库：
- 条目链接：`zotero://select/library/items/<ITEM_KEY>`
- PDF 页码链接：`zotero://open-pdf/library/items/<ATTACHMENT_KEY>?page=<PAGE>`
- PDF annotation 链接：`zotero://open-pdf/library/items/<ATTACHMENT_KEY>?page=<PAGE>&annotation=<ANNOTATION_KEY>`

群组库：
- 条目链接：`zotero://select/groups/<GROUP_ID>/items/<ITEM_KEY>`
- PDF 页码链接：`zotero://open-pdf/groups/<GROUP_ID>/items/<ATTACHMENT_KEY>?page=<PAGE>`
- PDF annotation 链接：`zotero://open-pdf/groups/<GROUP_ID>/items/<ATTACHMENT_KEY>?page=<PAGE>&annotation=<ANNOTATION_KEY>`

降级规则：
- 有 `annotation_key`：写 annotation 级 PDF 链接
- 没有 `annotation_key` 但有 `attachment_key + page`：写页码级 PDF 链接
- 没有 `page`：只写条目链接
- 没有 `attachment_key`：只写条目链接

第一阶段不要做：
- 不自动创建新 annotation
- 不仅凭引文文本反推 PDF 精确高亮框

## Dual-Write Policy

保存模式：
- `zotero_only`
- `both`
- `local_only`

默认：
- 用户没提本地副本时，用 `zotero_only`
- 用户明确要求本地也保存时，用 `both`

`both` 模式下：
- 先保存本地 Markdown 副本
- 再写回 Zotero
- 本地保存失败时，不继续写回 Zotero

## Workflow

1. 整理 payload
2. 校验单点笔记粒度
3. 用 `writeback_from_search.py` 搜索目标条目
4. 只有在单一高置信候选或用户已确认时，才正式写回
5. `writeback_tool.py` 负责把 payload 渲染成 HTML note
6. 若 `locator` 提供了页码或 annotation 信息，则在 note 中写入 Zotero deep link
7. 若是 `both` 模式，先保存本地副本，再写回 Zotero

## Commands

搜索与预览：

```powershell
python scripts/writeback_from_search.py `
  "<source_markdown_path>" `
  "<raw_query>" `
  --cache-path "<cache.json>" `
  --data-dir "C:\Zotero" `
  --title "<title_hint>" `
  --author "<author_hint>" `
  --payload-path "<payload.json>" `
  --writeback-script "scripts/writeback_tool.py"
```

正式写回：

```powershell
python scripts/writeback_from_search.py `
  "<source_markdown_path>" `
  "<raw_query>" `
  --cache-path "<cache.json>" `
  --data-dir "C:\Zotero" `
  --title "<title_hint>" `
  --author "<author_hint>" `
  --payload-path "<payload.json>" `
  --writeback-script "scripts/writeback_tool.py" `
  --auto-first `
  --run-writeback `
  --library-id "<library_id>" `
  --api-key "<api_key>"
```

## Safety Rules

- `--auto-first` 只在恰好 1 个候选时使用
- 多候选时先展示候选，不要自动写回
- 默认按原子笔记处理；若 `point_count_hint > 1`，先拆分
- deep link 必须使用最终写回所对应的附件 key，不要复用已被替换的旧 attachment key
- 若 `library_scope=groups`，必须显式提供 `group_id`
- 不要伪造 annotation 级链接

## Locator Integration Update

当前与新的 quote-to-annotation 流程协调时，默认直接使用上游返回的完整 `locator`，不再由 note-writeback 阶段重新推算坐标，也不只拆单个字段。

推荐的 `locator` 形状：

```json
{
  "locator": {
    "attachment_key": "ATTFAK01",
    "annotation_key": "ANNFAK01",
    "attachment_type": "pdf",
    "library_scope": "library",
    "group_id": null,
    "page": 135,
    "page_number": 135,
    "page_index": 134,
    "page_label": "135",
    "strategy": "ft-cache+tsv",
    "coordinate_space": "pdf-bottom-left",
    "source_coordinate_space": "pdftotext-top-origin",
    "rects": [[216.7, 240.283, 524.89, 253.253]],
    "raw_rects": [[216.7, 633.3, 524.89, 646.27]],
    "match_quality": {
      "exact_text": true,
      "has_extra_text": false,
      "extra_character_count": 0
    },
    "source_markdown_path": "C:/path/to/source.md"
  }
}
```

协调规则：
- `attachment_key`、`page`、`annotation_key` 以 `locator` 为准
- `rects` / `raw_rects` 是上游证据，note-writeback 不重算 rects
- `match_quality.exact_text=false` 时，应标记为待审，而不是默认视为精确命中
- 若已经拿到完整 annotation 结果 JSON，优先使用 `--locator-path <result.json>`
- 也可直接使用 `--locator-json <json>` 注入
- 除非明确人工修订，不要在下游覆盖 `locator.page` 或 `locator.annotation_key`

示例：

```powershell
python scripts/writeback_from_search.py `
  "<source_markdown_path>" `
  "<raw_query>" `
  --cache-path "<cache.json>" `
  --payload-path "<payload.json>" `
  --writeback-script "scripts/writeback_tool.py" `
  --locator-path "C:\path\to\annotation-result.json" `
  --auto-first `
  --run-writeback `
  --library-id "<library_id>" `
  --api-key "<api_key>"
```

## Output Expectations

回复里至少说明：
- 写回目标条目
- 使用的是 `search` 还是 `cache`
- 是否真的执行了 Zotero 写回
- 是否生成了本地副本
- 是否写入了 Zotero item link
- 是否写入了 PDF 页码级或 annotation 级 deep link
