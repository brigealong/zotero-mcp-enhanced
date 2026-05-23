# Zotero MCP Tools 升级设计说明

## 背景

当前 `zotero-mcp-enhanced-service` (端口 `23120`) 只暴露 OCR/PDF 相关 MCP tools。
XHS 采集链路需要直接通过 MCP 调用 Zotero 写入能力，而不是只通过独立脚本操作。

## 设计原则

1. **写入统一走插件队列**：所有写入类 MCP tool 底层继续走 Zotero 插件队列能力（`ZoteroQueueClient` → plugin queue → `storedattachmentpoc.js` action 执行）。不依赖 `23119/api`，不假设 Zotero local REST 可用。
2. **稳定业务接口，非内部协议镜像**：不把插件底层 action 1:1 裸露成 MCP tool，而是设计单一职责、参数清晰、结果可审计的接口。
3. **最小可用集优先**：先开放 XHS 采集最依赖的写入能力，读能力和删除/事务类默认不开放。

## 三档分级

### 第一档：本轮必须开放（已实现）

| MCP Tool | 插件底层 Action | 用途 |
|---|---|---|
| `zotero_create_collection` | `createCollection` | XHS 采集按主题/日期建收藏夹 |
| `zotero_add_item_to_collections` | `addItemToCollections` | 将 Connector 剪藏的 item 归入目标收藏夹 |
| `zotero_update_item_fields` | `updateItemFields` | 补充/修正 item 元数据（标题、URL、标签等） |
| `zotero_create_note` | `createNote` | 为 item 添加采集笔记或评论摘要 |

**为什么选这四个**：
- 这是 XHS 采集链路的最小闭环：剪藏 → 归类 → 补全元数据 → 写笔记
- 旧脚本 `zotero_queue_client.py` 已经封装了这四个方法，插件端已经验证稳定
- 参数简单、语义清晰、结果可审计

### 第二档：本轮顺手补（已实现）

| MCP Tool | 插件底层 Action | 用途 |
|---|---|---|
| `zotero_create_item` | `createItem` | 不经过 Connector，直接程序化创建 item |
| `zotero_update_note` | `updateNote` | 追加/更新已有笔记内容 |

**为什么补这两个**：
- `create_item` 是 `createNote` 的姊妹能力，插件端已完整实现（支持 creators/collections/tags）
- `update_note` 支持 replace/append/prepend 三种模式，对采集后补充笔记很有用
- 成本可控：底层队列路径和 Tier 1 完全一致，无额外架构负担

### 第三档：先盘点，不开放

| 插件 Action | 评估 | 暂不开放原因 |
|---|---|---|
| `moveCollection` | 可用 | 属于目录结构调整，XHS 采集当前不需要 |
| `removeItemFromCollections` | 可用 | 属于逆向操作，误用风险高于收益 |
| `createAnnotation` | 可用 | 需要 attachment + position 等复杂参数，属于 PDF 精读场景，非采集必需 |

### 默认不开放

| 插件 Action | 风险 |
|---|---|
| `trashAttachment` | 删除操作不可逆，审计困难 |
| `trashNote` | 同上 |
| `trashRegularItem` | 同上，且可能连带删除子附件/笔记 |
| `runTransaction` | 多步骤事务，失败回滚复杂，调试困难，不属于 XHS 采集最小必需集 |

## 三层映射

### 1. 插件底层已有 action

全部 14 个 action 在 `storedattachmentpoc.js` 中已实现：

- `importStoredAttachment`
- `createItem`
- `updateItemFields`
- `addItemToCollections`
- `createNote`
- `updateNote`
- `createCollection`
- `moveCollection`
- `removeItemFromCollections`
- `trashAttachment`
- `trashNote`
- `trashRegularItem`
- `createAnnotation`
- `runTransaction`

### 2. 旧脚本已封装能力

| Action | `zotero_queue_client.py` 封装状态 |
|---|---|
| `createCollection` | ✅ 已封装 |
| `addItemToCollections` | ✅ 已封装 |
| `updateItemFields` | ✅ 已封装 |
| `createNote` | ✅ 已封装 |
| `createItem` | ❌ 未封装（本轮 MCP 层直接补） |
| `updateNote` | ❌ 未封装（本轮 MCP 层直接补） |
| `importStoredAttachment` | ❌ 未封装 |
| `moveCollection` | ❌ 未封装 |
| `removeItemFromCollections` | ❌ 未封装 |
| `trashAttachment` | ❌ 未封装 |
| `trashNote` | ❌ 未封装 |
| `trashRegularItem` | ❌ 未封装 |
| `createAnnotation` | ❌ 未封装 |
| `runTransaction` | ❌ 未封装 |

**旧脚本假设了 MCP 读能力但当前 server 没实现**：
- `zotero-item-resolver.py` 中引用了 `get_recent` MCP tool，但当前 server 并未注册该 tool
- 该脚本目前只能作为独立 CLI 使用，无法通过 MCP 调用

### 3. 新 MCP tool 暴露结果

| MCP Tool | 状态 | 说明 |
|---|---|---|
| `zotero_create_collection` | ✅ 已开放 | Tier 1 |
| `zotero_add_item_to_collections` | ✅ 已开放 | Tier 1 |
| `zotero_update_item_fields` | ✅ 已开放 | Tier 1 |
| `zotero_create_note` | ✅ 已开放 | Tier 1 |
| `zotero_create_item` | ✅ 已开放 | Tier 2 |
| `zotero_update_note` | ✅ 已开放 | Tier 2 |
| `zotero_move_collection` | ⏸️ 暂缓 | Tier 3，非采集必需 |
| `zotero_remove_item_from_collections` | ⏸️ 暂缓 | Tier 3，误用风险 |
| `zotero_create_annotation` | ⏸️ 暂缓 | Tier 3，参数复杂 |
| `zotero_trash_attachment` | 🚫 明确不开放 | 删除类，风险高 |
| `zotero_trash_note` | 🚫 明确不开放 | 删除类，风险高 |
| `zotero_trash_regular_item` | 🚫 明确不开放 | 删除类，风险高 |
| `zotero_run_transaction` | 🚫 明确不开放 | 事务类，调试困难 |

## 读能力规划

当前 **不** 在 `23120` 开放读能力，原因：
- 稳定的读链路尚未验证（`23119/api` 不稳定，`zotero-item-resolver.py` 的 `get_recent` 只是假设）
- XHS 采集链路的读需求（按 URL + 时间窗反查 item key）目前由独立脚本 `zotero-item-resolver.py` 满足

**下一批读能力建议**：
- 如果 `23119/api` 稳定性改善，可以考虑在 `23120` 代理少量读接口（如 `get_recent`, `search_items`）
- 或者，在插件队列中增加读 action（如 `getItemByKey`, `searchItems`），统一走队列路径
- 决策前需要先验证底层链路稳定性

## 文件改动

| 文件 | 仓库 | 说明 |
|---|---|---|
| `mcp-service/src/zotero_mcp_enhanced_service/zotero_queue.py` | `zotero-xhs-integration` | 新增：ZoteroQueueClient + ZoteroWriteService |
| `mcp-service/src/zotero_mcp_enhanced_service/server.py` | `zotero-xhs-integration` | 修改：注册 6 个新 MCP tools |
| `mcp-service/src/zotero_mcp_enhanced_service/__init__.py` | `zotero-xhs-integration` | 修改：导出新模块 |
| `docs/ZOTERO-MCP-TOOLS-DESIGN.md` | `zotero-xhs-integration` | 新增：本设计文档 |

## 验证方式

1. MCP server 能正常启动
2. 新 tools 已注册（可通过 MCP inspector 或客户端列出 tools）
3. 每个 Tier 1 tool 至少有一次调用验证（真实或 mock）
4. 验证结果中包含 `request_id` 和 `action` 字段，证明走的是插件队列路径

## 后续建议

1. **第二批**：验证读链路稳定性后，开放 `zotero_get_recent`、`zotero_search_items` 等读 tool
2. **第三批**：如需目录结构调整能力，开放 `zotero_move_collection`
3. **删除/事务类**：需要用户明确批准 + 增加二次确认机制后才考虑开放
