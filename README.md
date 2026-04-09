# zotero-mcp-enhanced

`zotero-mcp-enhanced` packages the parts we changed around the Zotero MCP workflow into one repository:

- a Zotero bridge plugin that writes local queue jobs from the Zotero UI
- a Python MCP service startup path and packaging layer for local workflows
- reusable agent skills for metadata lookup, attachment resolution, workflow orchestration, and note writeback

This repository is a downstream enhancement project built on top of the Zotero MCP ecosystem. It is not a full mirror of the upstream Zotero MCP server.

## What Is Included

```text
plugin/         Manual-install Zotero add-on source
mcp-service/    Python MCP service, scripts, and tests
skills/         Reusable skills plus helper scripts
docs/           Installation and publishing notes
```

Current publishable scope:

- bridge-style Zotero plugin changes
- MCP service startup and packaging
- note writeback and attachment workflow skills

## What Is Optional

The local PDF text-location path is intentionally optional.

You can use the plugin bridge, note writeback flow, and most skill-based workflows without any proprietary OCR software.

Optional components only needed for specific flows:

- `pdftotext` for quote-to-annotation layout extraction
- `OCRmyPDF` plus `Tesseract` if you want an open-source OCR runner
- your own private local PDF enhancement chain, if you choose to build one separately

If `pdftotext` is not on `PATH`, set `PDFTOTEXT_PATH` before running `mcp-service/scripts/create_highlight_from_quote.py`.

This repository does not bundle or redistribute any proprietary OCR engine.

## Prerequisites

- Zotero 7-compatible desktop environment
- Python 3.10 or newer
- an MCP-capable client if you want to run the service from an agent
- a Codex/agent skill directory if you want to install the bundled skills

Optional:

- `pdftotext`
- `OCRmyPDF`
- `Tesseract`

## Quick Start

### 1. Install the Zotero plugin

You can install the plugin in either of these ways:

- Direct install: use `plugin/dist/zotero-mcp-enhanced.xpi` if it is already included in the repository.
- Build it yourself: run `powershell -ExecutionPolicy Bypass -File plugin/build-plugin.ps1` to regenerate the `.xpi` from the open-source `plugin/` directory.

Then install it in Zotero:

1. Open Zotero.
2. Go to `Tools -> Plugins`.
3. Choose `Install Add-on From File...`.
4. Select `plugin/dist/zotero-mcp-enhanced.xpi`.
5. Restart Zotero.

By default, the plugin writes queue files to:

- Windows: `%TEMP%\\zotero-mcp-enhanced`

Override with either of these environment variables:

- `ZOTERO_MCP_QUEUE_DIR`
- `ZOTERO_PLUGIN_QUEUE_DIR`

### 2. Start the MCP service

The original Python-based MCP service setup is still supported and will be kept.
The standalone `.exe` path is an optional convenience layer, not a replacement.

From `mcp-service/`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[test]
python -m zotero_mcp_enhanced_service --base-dir . --runner stub
```

Use `--runner stub` for the public smoke test path. Proprietary OCR runner setup is intentionally out of scope for this repository's public install guide.

If you want an open-source OCR path later, install `OCRmyPDF` and `Tesseract`, then switch to:

```powershell
python -m zotero_mcp_enhanced_service --base-dir . --runner ocrmypdf
```

For a click-by-click Windows walkthrough, see [docs/MCP-SERVICE-STEP-BY-STEP.md](docs/MCP-SERVICE-STEP-BY-STEP.md).

If you want the original-style config path, use [docs/codex-mcp-config-python.example.json](docs/codex-mcp-config-python.example.json).

If you want a simpler deployment path closer to the original Zotero MCP experience, see [docs/STANDALONE-MCP-SERVICE.md](docs/STANDALONE-MCP-SERVICE.md). That flow packages the service as a standalone `zotero-mcp-enhanced-service.exe` so your client config can point to a single executable instead of a Python command.

### 3. Install the bundled skills

Copy or symlink the folders under `skills/` into your agent skill directory:

- `zotero-metadata`
- `zotero-attachment-resolve`
- `zotero-workflow-orchestrator`
- `zotero-note-writeback`

### 4. Enable writeback when needed

The note-writeback flow typically needs:

- `ZOT_DATA_DIR`
- `ZOT_LIBRARY_ID`
- `ZOT_API_KEY`

These are only required for writeback or direct Zotero API operations, not for every workflow in this repository.

## Typical Usage Paths

### Plugin bridge only

Install the Zotero plugin and point your local tooling at the queue directory. This is the lightest setup.

### Plugin + MCP service

Install the plugin, then run the Python service for the queue-driven local workflow you want to test.

### Full workflow with agent skills

Install the plugin, service, and skills together when you want higher-level agent workflows such as:

- metadata resolution
- attachment discovery
- orchestrated Zotero workflows
- note writeback with Zotero deep links

## Installation Guide

For step-by-step setup instructions, see [docs/INSTALL.md](docs/INSTALL.md).

## Upstream and License

This repository is intended to stay compatible with the Zotero MCP ecosystem.

Referenced upstream project:

- [54yyyu/zotero-mcp](https://github.com/54yyyu/zotero-mcp)

License:

- MIT, see [LICENSE](LICENSE)
