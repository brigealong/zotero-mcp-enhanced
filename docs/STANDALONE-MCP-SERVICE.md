# Standalone MCP Service

This document explains the simpler packaging path for `mcp-service`.
It does not replace the original Python startup method.

Goal:

- build one Windows executable file: `zotero-mcp-enhanced-service.exe`
- point Codex to that file
- avoid asking every user to manually type Python startup commands

## What this improves

The old setup asks the user to:

- install Python
- create a virtual environment
- install dependencies with `pip`
- remember the startup command

The standalone path changes that to:

- download or build `zotero-mcp-enhanced-service.exe`
- put one command path into Codex config

If you are using a prebuilt `zotero-mcp-enhanced-service.exe`, you do not need to install Python first.
This is only an optional convenience path. The original Python-based MCP service configuration remains supported.
This executable packaging does not bundle `OCRmyPDF`, `Tesseract`, or `pdftotext`.

## Build the executable

From the `mcp-service/` folder, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\build-standalone.ps1
```

What the script does:

1. checks whether `PyInstaller` is available
2. creates an isolated build virtual environment
3. installs build dependencies into that isolated environment
4. builds a single-file Windows executable
5. writes the result to:

```text
mcp-service\dist\zotero-mcp-enhanced-service.exe
```

Using an isolated build environment is intentional. It avoids failures caused by unrelated packages in your global Python installation.

## Configure Codex

Copy the example file:

- [codex-mcp-config.example.json](codex-mcp-config.example.json)

If you prefer to keep the original Python command style, use:

- [codex-mcp-config-python.example.json](codex-mcp-config-python.example.json)

The most important part is this:

```json
{
  "mcpServers": {
    "zotero-mcp-enhanced": {
      "command": "C:\\path\\to\\zotero-mcp-enhanced\\mcp-service\\dist\\zotero-mcp-enhanced-service.exe",
      "args": [
        "--base-dir",
        "C:\\path\\to\\zotero-mcp-enhanced\\mcp-service-data",
        "--runner",
        "stub"
      ]
    }
  }
}
```

## Which runner should you use

For first startup, use:

- `stub`

This avoids proprietary dependency problems and lets you verify that Codex can start the MCP service process correctly.

This repository's public documentation only covers the `stub` startup path.
If you later connect `OCRmyPDF` or another local PDF-processing runner, treat that as an optional extension layer on top of this base packaging flow.
In that case, install those OCR tools separately on the local machine first.

## Why this is closer to the original Zotero MCP experience

The original easy path works because the user only needs:

- one runnable server command
- one small MCP config snippet

This standalone packaging restores that model.

Instead of asking the user to remember:

```powershell
python -m zotero_mcp_enhanced_service --base-dir . --runner stub
```

Codex can point directly to:

```text
zotero-mcp-enhanced-service.exe
```

That is the main simplification.

## Current limitation

This makes the service much easier to run, but it still does not make the Zotero plugin automatically install the MCP service.
It also should be treated as an optional packaging path until you confirm it works in your real Codex environment.

To reach that final experience, the next layer would be:

1. release the prebuilt `zotero-mcp-enhanced-service.exe`
2. ship a one-click installer or bootstrap script
3. optionally generate the Codex config snippet automatically
