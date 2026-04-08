# zotero-mcp-enhanced

Enhanced Zotero MCP workflow assets collected into one repo:

- a Zotero bridge plugin for local write queues
- an MCP service for ABBYY OCR jobs and PDF bookmark generation
- reusable skills for metadata resolution, attachment discovery, workflow orchestration, and note writeback

## Repository Layout

```text
plugin/         Zotero plugin source
mcp-service/    Python MCP service and related scripts/tests
skills/         Reusable Codex/agent skills and helper scripts
docs/           Setup notes and publishing context
```

## Scope

This repository is a companion project for Zotero MCP based workflows. It is not a full mirror of the upstream Zotero MCP server. The current publishable scope is:

- bridge-style Zotero plugin changes
- ABBYY-based OCR and bookmark MCP service
- note-writeback and attachment workflow skills

## Optional Dependencies

The OCR and layout-recognition branch is intentionally optional.

Core Zotero workflow and note-writeback usage does not require ABBYY or `pdftotext`.

Optional components:

- ABBYY FineReader 15 with `FineCmd.exe`
- `pdftotext` for quote-to-annotation page layout extraction

If `pdftotext` is not on `PATH`, set `PDFTOTEXT_PATH` before running `mcp-service/scripts/create_highlight_from_quote.py`.

## Queue Directory

The local plugin queue defaults to the system temp directory:

- Windows example: `%TEMP%\\zotero-mcp-enhanced`

You can override it with:

- `ZOTERO_MCP_QUEUE_DIR`
- `ZOTERO_PLUGIN_QUEUE_DIR`

## Upstream and License

This repo is intended to be compatible with the Zotero MCP ecosystem and was prepared with upstream-license compatibility in mind.

The upstream repository referenced during packaging is:

- [54yyyu/zotero-mcp](https://github.com/54yyyu/zotero-mcp)

The repository license is MIT. See [LICENSE](LICENSE).

## Quick Start

1. Install the Zotero plugin from `plugin/`.
2. Configure the local queue directory if you do not want the temp-directory default.
3. Set up the Python environment in `mcp-service/`.
4. Use the skills in `skills/` from your agent environment.

More detail is in [docs/INSTALL.md](docs/INSTALL.md).
