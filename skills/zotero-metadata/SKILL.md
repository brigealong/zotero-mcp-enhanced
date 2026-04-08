---
name: zotero-metadata
description: Use this skill whenever the immediate job is to identify, rank, or normalize Zotero metadata candidates before any create, update, attach, note, or collection write. Trigger even if the user mentions Zotero, as long as they only have a title, DOI, ISBN, or one local PDF/EPUB and need metadata resolved first rather than written now.
---

# Zotero Metadata

## Overview

This skill resolves metadata candidates before any Zotero write step.

It combines two paths:
- Local file metadata extraction from one PDF or EPUB
- Remote bibliographic lookup from DOI, ISBN, title, and optional author

It does not create items, attach files, move collections, or write notes.

## When To Use

Use this skill when the immediate task is one of these:
- "先解析 metadata，再决定要不要写入 Zotero"
- "我只有 DOI / ISBN / 题名，先查候选"
- "先从本地 PDF 或 EPUB 里读书名、作者、出版社、年份"
- A larger Zotero workflow needs metadata as its first step

Do not use this skill when:
- The user already wants to create or update Zotero data now
- The task is only about collections, notes, trash, or attachments
- The user already has stable metadata and does not need candidate resolution

## Inputs

Prefer one of these entry shapes:
- `--attachment-path <file>`
- `--doi <doi>`
- `--isbn <isbn>`
- `--title <title>` with optional `--author <name>`
- Optional `--item-type-hint book|journalArticle|document`

## Output Contract

Always return structured JSON with:
- `mode`
- `query`
- `attachment_path`
- `item_type_hint`
- `candidates`

Each candidate should contain as many of these fields as available:
- `item_type`
- `title`
- `authors`
- `year`
- `publisher`
- `place`
- `isbn`
- `doi`
- `url`
- `language`
- `confidence`
- `evidence`
- `source`
- `source_id`

## Script

Script path:
- `scripts/resolve_metadata.py`

Examples:

```powershell
python skills/zotero-metadata/scripts/resolve_metadata.py `
  --doi "10.5555/attention"
```

```powershell
python skills/zotero-metadata/scripts/resolve_metadata.py `
  --attachment-path "./sample.epub"
```

## Handoff

After metadata is resolved:
- Send local file matching to `zotero-attachment-resolve`
- Send actual write actions to `zotero-workflow-orchestrator` or directly to the local Zotero MCP route

## Safety Rules

- Show candidates before any write step
- Keep weak local guesses at low confidence
- DOI and ISBN exact hits may be high confidence, but must still keep evidence
- Do not pretend this skill writes anything into Zotero
