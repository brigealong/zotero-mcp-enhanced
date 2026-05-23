#!/usr/bin/env python3
"""
Zotero MCP 端到端最小验证脚本
测试：获取 collections → 创建 test collection → 添加测试 item → 验证
"""

import json
import requests
import time
import os

MCP_URL = "http://localhost:23120/mcp"

def mcp_call(method: str, params: dict = None) -> dict:
    """调用 MCP 工具"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "id": int(time.time() * 1000),
        "params": params or {}
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    try:
        # MCP HTTP 使用 SSE 流式响应
        response = requests.post(
            MCP_URL, 
            json=payload, 
            headers=headers,
            stream=True,
            timeout=30
        )
        response.raise_for_status()
        
        # 读取 SSE 响应
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    return data
        return {"error": "No data received"}
    except Exception as e:
        return {"error": str(e)}

def test_get_collections():
    """测试获取 collections"""
    print("🧪 测试 1: 获取 collections...")
    
    # 先初始化
    init_result = mcp_call("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    })
    print(f"  初始化结果: {init_result.get('result', {}).get('serverInfo', {})}")
    
    # 调用 get_collections
    result = mcp_call("tools/call", {
        "name": "get_collections",
        "arguments": {}
    })
    
    if "error" in result:
        print(f"  ❌ 失败: {result['error']}")
        return False
    
    collections = result.get("result", {}).get("content", [])
    print(f"  ✅ 成功! 找到 {len(collections)} 个 collections")
    for c in collections[:3]:
        print(f"     - {c.get('name', 'N/A')} (key: {c.get('key', 'N/A')})")
    
    return True

def test_create_collection():
    """测试创建 collection"""
    print("\n🧪 测试 2: 创建测试 collection...")
    
    collection_name = f"test-xhs-integration-{int(time.time())}"
    result = mcp_call("tools/call", {
        "name": "create_collection",
        "arguments": {
            "name": collection_name,
            "parent_collection": None
        }
    })
    
    if "error" in result:
        print(f"  ❌ 失败: {result['error']}")
        return False
    
    collection_key = result.get("result", {}).get("content", [{}])[0].get("key")
    print(f"  ✅ 成功! 创建 collection: {collection_name}")
    print(f"     key: {collection_key}")
    
    return collection_key

def main():
    print("=" * 60)
    print("Zotero MCP 端到端最小验证")
    print("=" * 60)
    
    # 检查 MCP server 是否运行
    print("\n📡 检查 MCP server 状态...")
    try:
        response = requests.get(MCP_URL, timeout=5)
        print(f"  Server 响应: {response.status_code}")
    except:
        print("  ⚠️  Server 可能未运行，尝试继续...")
    
    # 测试 1: 获取 collections
    if not test_get_collections():
        print("\n❌ 测试失败: 无法获取 collections")
        return 1
    
    # 测试 2: 创建 collection
    collection_key = test_create_collection()
    if not collection_key:
        print("\n❌ 测试失败: 无法创建 collection")
        return 1
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过!")
    print("=" * 60)
    print(f"\n下一步可以:")
    print(f"  1. 手动在 Zotero 中检查 collection 是否创建")
    print(f"  2. 进行小红书剪藏测试")
    print(f"  3. 验证 item 写入和 note 创建")
    
    return 0

if __name__ == "__main__":
    exit(main())
