# Installation Notes

## 1. Plugin

The Zotero plugin in `plugin/` is a manual-install source package.

Recommended install path:

1. Zip the contents of `plugin/` into an `.xpi`
2. In Zotero, install the add-on from file
3. Restart Zotero

The plugin queue directory defaults to the system temp directory under `zotero-mcp-enhanced`.

Optional override:

- `ZOTERO_MCP_QUEUE_DIR`
- `ZOTERO_PLUGIN_QUEUE_DIR`

## 2. MCP Service

From `mcp-service/`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[test]
```

If your environment does not support extras for editable install, use:

```powershell
pip install -e .
pip install pytest
```

Run the server:

```powershell
python -m abbyy_mcp --base-dir .
```

Use `--runner stub` if ABBYY is not installed.

## 3. Optional OCR Dependencies

### ABBYY

Default Windows path used by the service:

- `C:\Program Files (x86)\ABBYY FineReader 15\FineCmd.exe`

If ABBYY is not installed, run with the stub runner or adjust the service config in your own wrapper.

### pdftotext

`create_highlight_from_quote.py` resolves `pdftotext` in this order:

1. `PDFTOTEXT_PATH`
2. `PATH`
3. common Windows install paths

## 4. Skills

Copy the folders under `skills/` into your agent skill directory, or reference them directly from this repo.

Included skills:

- `zotero-metadata`
- `zotero-attachment-resolve`
- `zotero-workflow-orchestrator`
- `zotero-note-writeback`
