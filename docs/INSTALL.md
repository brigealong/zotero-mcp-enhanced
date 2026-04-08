# Installation Notes

This guide separates setup into three independent parts:

1. Zotero plugin
2. Python MCP service
3. Agent skills

You can install only the parts you need.

## 1. Install the Zotero Plugin

The plugin in `plugin/` is a manual-install source package.

### Package the add-on

Option A: use the ready-made package if the repository already includes:

- `plugin/dist/zotero-mcp-enhanced.xpi`

Option B: build the package yourself from source:

```powershell
powershell -ExecutionPolicy Bypass -File plugin\build-plugin.ps1
```

After the script finishes, the installable file will be:

- `plugin/dist/zotero-mcp-enhanced.xpi`

### Install into Zotero

1. Open Zotero.
2. Go to `Tools -> Plugins`.
3. Choose `Install Add-on From File...`.
4. Select the `.xpi` file.
5. Restart Zotero.

### Queue directory

The plugin writes queue files to the system temp directory by default:

- Windows example: `%TEMP%\\zotero-mcp-enhanced`

If you want a stable custom path, set one of:

- `ZOTERO_MCP_QUEUE_DIR`
- `ZOTERO_PLUGIN_QUEUE_DIR`

## 2. Install the MCP Service

From `mcp-service/`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[test]
```

If editable extras are not supported in your environment:

```powershell
pip install -e .
pip install pytest
```

### Start the service

For a dependency-light local boot test:

```powershell
python -m abbyy_mcp --base-dir . --runner stub
```

For a real OCR setup, replace the stub runner with your actual service configuration after verifying the basic service starts correctly.

If you want an ultra-detailed Windows guide, read:

- [MCP-SERVICE-STEP-BY-STEP.md](MCP-SERVICE-STEP-BY-STEP.md)

### Verify the test suite

```powershell
pytest tests
```

## 3. Optional OCR and Layout Dependencies

These are not required for the base bridge or most writeback workflows.

### ABBYY FineReader 15

Default Windows path expected by the prototype service:

- `C:\Program Files (x86)\ABBYY FineReader 15\FineCmd.exe`

If ABBYY is not installed, continue using `--runner stub`.

### pdftotext

`mcp-service/scripts/create_highlight_from_quote.py` resolves `pdftotext` in this order:

1. `PDFTOTEXT_PATH`
2. `PATH`
3. common Windows install paths

Use this dependency only if you want quote-to-annotation layout extraction.

## 4. Install the Skills

Copy or symlink the folders under `skills/` into your agent skill directory, or reference them directly from this repository.

Included skills:

- `zotero-metadata`
- `zotero-attachment-resolve`
- `zotero-workflow-orchestrator`
- `zotero-note-writeback`

## 5. Environment Variables for Writeback

If you want to write notes back into Zotero, prepare:

- `ZOT_DATA_DIR`
- `ZOT_LIBRARY_ID`
- `ZOT_API_KEY`

These are not required for every repository feature. They are mainly needed for writeback flows and direct Zotero API interactions.

## 6. Recommended Setup Profiles

### Minimal

- install the plugin
- use the default local queue directory

### Bridge + service

- install the plugin
- install the MCP service
- run the service with `--runner stub` first

### Full enhanced workflow

- install the plugin
- install the MCP service
- install the four bundled skills
- add writeback environment variables
- optionally add ABBYY or `pdftotext` only if you need those specific flows
