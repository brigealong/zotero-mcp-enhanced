# GitHub Release Notes

## Summary

This release publishes the open-source parts of our downstream Zotero MCP enhancement work:

- Zotero bridge plugin
- MCP service startup and packaging layer
- reusable agent skills for metadata, attachment, workflow, and note writeback

## What Is Included

- installable Zotero add-on package: `plugin/dist/zotero-mcp-enhanced.xpi`
- open-source plugin source under `plugin/`
- Python MCP service under `mcp-service/`
- optional standalone executable packaging flow for the MCP service
- bundled skills under `skills/`
- step-by-step installation documentation

## What Is Optional

OCR is optional.

The base repository does not bundle or auto-install OCR dependencies.
If you want OCR support, install these separately on your own machine:

- `OCRmyPDF`
- `Tesseract`

If you want quote-to-annotation layout extraction, install:

- `pdftotext`

## Installation Guidance

- For the lightest setup, install the `.xpi` plugin and use the base queue workflow.
- For MCP service startup, use either the original Python path or the optional standalone `.exe` path.
- For OCR, follow the separate installation steps in the repository docs.

## Important Note

This release does not redistribute any proprietary OCR engine.
Only the open-source plugin, MCP service layer, and skills are published here.
