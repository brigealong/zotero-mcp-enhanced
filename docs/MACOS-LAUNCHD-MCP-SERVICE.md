# macOS Launchd MCP Service

这份说明把 `zotero-mcp-enhanced-service` 固化为 macOS `launchd` 常驻服务，解决 `23120/mcp` 只能手工启动、会话退出后失联的问题。

## 目标

- 固定监听 `http://127.0.0.1:23120/mcp`
- 登录后自动启动
- 进程异常退出时自动重启
- 不再依赖临时终端窗口保持存活

## 本仓库提供的文件

- 启动脚本：
  [`scripts/start-zotero-mcp-service.sh`](../scripts/start-zotero-mcp-service.sh)
- 健康检查：
  [`scripts/check-zotero-mcp-service.sh`](../scripts/check-zotero-mcp-service.sh)
- `launchd` 模板：
  [`ops/launchd/com.brigealong.zotero-mcp-enhanced-service.plist`](../ops/launchd/com.brigealong.zotero-mcp-enhanced-service.plist)

## 责任边界

这套常驻方案只负责 **23120 外置 MCP 服务**。

它不负责：
- 启动 Zotero Desktop
- 启动 Zotero 插件内部 watcher
- 修复 `23119/api` 本地 REST 路径

所以完整链路仍需区分：

1. Zotero Desktop 是否在运行
2. 插件队列 watcher 是否 ready
3. `23120/mcp` 是否可握手

## 安装步骤

### 1. 先确认脚本可执行

```bash
chmod +x ../scripts/start-zotero-mcp-service.sh
chmod +x ../scripts/check-zotero-mcp-service.sh
```

### 2. 语法检查 plist

```bash
plutil -lint ../ops/launchd/com.brigealong.zotero-mcp-enhanced-service.plist
```

### 3. 安装到当前用户 LaunchAgents

```bash
mkdir -p "${HOME}/Library/LaunchAgents"
cp ../ops/launchd/com.brigealong.zotero-mcp-enhanced-service.plist \
   "${HOME}/Library/LaunchAgents/com.brigealong.zotero-mcp-enhanced-service.plist"
```

### 4. 加载并立即启动

```bash
launchctl bootout "gui/$(id -u)" "${HOME}/Library/LaunchAgents/com.brigealong.zotero-mcp-enhanced-service.plist" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${HOME}/Library/LaunchAgents/com.brigealong.zotero-mcp-enhanced-service.plist"
launchctl kickstart -k "gui/$(id -u)/com.brigealong.zotero-mcp-enhanced-service"
```

## 验证

### 1. 端口监听

```bash
lsof -nP -iTCP:23120 -sTCP:LISTEN
```

### 2. 握手检查

```bash
../scripts/check-zotero-mcp-service.sh
```

成功标准：
- `lsof` 能看到监听进程
- 检查脚本返回 `PASS: endpoint reachable at http://127.0.0.1:23120/mcp`

### 3. 查看 launchd 状态

```bash
launchctl print "gui/$(id -u)/com.brigealong.zotero-mcp-enhanced-service"
```

## 日志位置

`launchd` 当前写入：

- stdout: `/tmp/zotero-mcp-enhanced-service.stdout.log`
- stderr: `/tmp/zotero-mcp-enhanced-service.stderr.log`

查看方式：

```bash
tail -n 50 /tmp/zotero-mcp-enhanced-service.stdout.log
tail -n 50 /tmp/zotero-mcp-enhanced-service.stderr.log
```

## 启动脚本行为

`start-zotero-mcp-service.sh` 会：

1. 优先使用 `ZOTERO_MCP_PYTHON`
2. 否则依次尝试：
   - `mcp-service/.venv/bin/python`
   - `~/.local/share/mise/installs/python/3.12/bin/python3`
   - `/opt/homebrew/bin/python3`
   - `python3` on PATH
3. 检查解释器是否能导入：
   - `mcp`
   - `pypdf`
   - `zotero_mcp_enhanced_service`
4. 用固定参数启动：
   - `--transport streamable-http`
   - `--port 23120`
   - `--runner stub`

## 常见故障

### 1. `FAIL: no process is listening on TCP 23120`

说明 `launchd` 没起服务，或服务启动后立刻退出。

先看：

```bash
launchctl print "gui/$(id -u)/com.brigealong.zotero-mcp-enhanced-service"
tail -n 50 /tmp/zotero-mcp-enhanced-service.stderr.log
```

### 2. `no usable Python interpreter found`

说明当前机器没有找到能导入 `mcp + pypdf + zotero_mcp_enhanced_service` 的解释器。

修法：

```bash
cd ../mcp-service
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

然后重新 `kickstart`。

### 3. 端口在监听，但握手失败

说明：
- 服务可能不是这套 enhanced service
- 或 Accept / protocol 不匹配

先看 stdout/stderr，再单独跑：

```bash
../scripts/check-zotero-mcp-service.sh
```

### 4. Zotero 插件活着，但 agent 还是报错

要区分：
- 插件 watcher-ready
- `23120/mcp` 可握手

前者不等于后者。这个文档只保证后者。

## 卸载

```bash
launchctl bootout "gui/$(id -u)" "${HOME}/Library/LaunchAgents/com.brigealong.zotero-mcp-enhanced-service.plist"
rm -f "${HOME}/Library/LaunchAgents/com.brigealong.zotero-mcp-enhanced-service.plist"
```
