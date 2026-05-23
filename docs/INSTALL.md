# Installation Notes

This guide separates setup into three independent parts:

1. Zotero plugin
2. Python MCP service
3. Agent skills

You can install only the parts you need.

## What You Get From This Repository

Directly provided here:

- plugin source
- ready-made `.xpi` package when included in the repo or release
- MCP service source
- optional standalone `.exe` packaging flow
- bundled skills
- setup documentation

Installed separately only when needed:

- `OCRmyPDF`
- `Tesseract`
- `pdftotext`

This means the base project can be installed from this repository, but OCR-related dependencies are separate local installs.

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

Important:

- the original Python launch method is still supported
- the standalone `.exe` method is optional
- we are not deleting the old MCP service startup path
- neither startup path auto-installs OCR dependencies

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
python -m zotero_mcp_enhanced_service --base-dir . --runner stub
```

For the public repository, `stub` is the documented startup mode. If you later wire in your own private local PDF-processing runner, treat that as a custom extension after the basic service boot path is verified.

### Optional open-source OCR runner

If you want OCR without proprietary software, install `OCRmyPDF` and `Tesseract` separately, then start:

```powershell
python -m zotero_mcp_enhanced_service --base-dir . --runner ocrmypdf
```

You can also run the helper probe:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\probe_ocrmypdf.ps1
```

If you want an ultra-detailed Windows guide, read:

- [MCP-SERVICE-STEP-BY-STEP.md](MCP-SERVICE-STEP-BY-STEP.md)

If you are on macOS and want the HTTP MCP endpoint to be kept alive automatically, read:

- [MACOS-LAUNCHD-MCP-SERVICE.md](MACOS-LAUNCHD-MCP-SERVICE.md)

If you want the original Codex config style, use:

- [codex-mcp-config-python.example.json](codex-mcp-config-python.example.json)

If you want a simpler executable-based deployment model, read:

- [STANDALONE-MCP-SERVICE.md](STANDALONE-MCP-SERVICE.md)

### Verify the test suite

```powershell
pytest tests
```

## 3. Optional Local PDF and Layout Dependencies

These are not required for the base bridge or most writeback workflows.

### pdftotext

`mcp-service/scripts/create_highlight_from_quote.py` resolves `pdftotext` in this order:

1. `PDFTOTEXT_PATH`
2. `PATH`
3. common Windows install paths

Use this dependency only if you want quote-to-annotation layout extraction.

### OCRmyPDF and Tesseract

These are optional add-ons, not bundled parts of the repository.

Use them only if you want the open-source OCR runner:

- install `OCRmyPDF`
- install `Tesseract`
- confirm both commands are available in PowerShell
- then start the service with `--runner ocrmypdf`

### Private PDF enhancement chain

If you maintain your own local OCR or bookmark-generation toolchain, keep it outside this repository's documented public setup.
This repository does not ship a proprietary OCR engine.

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
- optionally add `pdftotext` only if you need quote-to-annotation layout extraction
