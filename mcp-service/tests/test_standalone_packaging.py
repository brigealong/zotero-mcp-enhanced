from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_DIR = REPO_ROOT / "mcp-service"
DOCS_DIR = REPO_ROOT / "docs"


def test_standalone_build_script_exists() -> None:
    script_path = SERVICE_DIR / "build-standalone.ps1"
    assert script_path.exists()

    script_text = script_path.read_text(encoding="utf-8")
    assert "PyInstaller" in script_text
    assert "zotero-mcp-enhanced-service.exe" in script_text


def test_codex_config_example_targets_standalone_executable() -> None:
    config_path = DOCS_DIR / "codex-mcp-config.example.json"
    assert config_path.exists()

    config = json.loads(config_path.read_text(encoding="utf-8"))
    server = config["mcpServers"]["zotero-mcp-enhanced"]

    assert server["command"].endswith("zotero-mcp-enhanced-service.exe")
    assert "--base-dir" in server["args"]
    assert "--runner" in server["args"]


def test_legacy_python_config_example_is_preserved() -> None:
    config_path = DOCS_DIR / "codex-mcp-config-python.example.json"
    assert config_path.exists()

    config = json.loads(config_path.read_text(encoding="utf-8"))
    server = config["mcpServers"]["zotero-mcp-enhanced"]

    assert server["command"] == "python"
    assert server["args"][:2] == ["-m", "zotero_mcp_enhanced_service"]


def test_standalone_doc_explains_exe_first_setup() -> None:
    doc_path = DOCS_DIR / "STANDALONE-MCP-SERVICE.md"
    assert doc_path.exists()

    text = doc_path.read_text(encoding="utf-8")
    assert "zotero-mcp-enhanced-service.exe" in text
    assert "Codex" in text
    assert "original Python startup method" in text
