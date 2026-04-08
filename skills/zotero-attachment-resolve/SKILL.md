---
name: zotero-attachment-resolve
description: Use this skill whenever a Zotero workflow needs to find an already-downloaded local PDF or EPUB by title, creator, DOI, or ISBN before attaching it, especially if the user says the file should already exist in Downloads or another local folder but the exact path is still unknown. Use it for file discovery only, not for metadata extraction or any Zotero write.
---

# Zotero Attachment Resolve

## Overview

This skill finds likely local attachment files that already exist on disk.

It is for file discovery only:
- Search one or more local roots such as `Downloads`
- Rank PDF and EPUB candidates by DOI, ISBN, title tokens, and creator tokens
- Return candidate paths with evidence

It does not read Zotero's database, create items, or attach files by itself.

## When To Use

Use this skill when:
- The user says a related PDF or EPUB should already exist locally
- The next step is "find the file first, then attach it"
- The workflow already has title, author, DOI, or ISBN and needs candidate file paths

Do not use this skill when:
- The task is to extract metadata from the file itself
- The path is already known exactly
- The task is only about Zotero item writes or collection updates

## Inputs

Preferred inputs:
- `--title <title>`
- `--creator <name>` and repeat if needed
- `--doi <doi>`
- `--isbn <isbn>`
- Optional `--search-root <dir>` and repeat if needed
- Optional `--limit <n>`

If no search root is provided, the script searches the user's default local folders, starting with `Downloads`.

## Performance Notes

- On this machine, searching an explicit small root with one candidate file is about sub-second.
- Default root search can take several seconds because it scans `Downloads`, `Desktop`, and `Documents`.
- Prefer an explicit `--search-root` whenever the likely file location is already known.

## Output Contract

Always return structured JSON with:
- `query`
- `search_roots`
- `candidates`

Each candidate contains:
- `path`
- `extension`
- `score`
- `evidence`
- `size_bytes`
- `modified_ts`

## Script

Script path:
- `scripts/resolve_attachment_candidates.py`

Example:

```powershell
python skills/zotero-attachment-resolve/scripts/resolve_attachment_candidates.py `
  --title "The Crisis of Parliamentary Democracy" `
  --creator "Carl Schmitt" `
  --search-root "./Downloads"
```

## Handoff

After candidates are returned:
- If the top candidate is unambiguous, hand the chosen path to `zotero-workflow-orchestrator`
- If there are several similar candidates, ask the user to choose before any write step

## Safety Rules

- Do not assume the top-ranked path is correct when several results are close
- Do not attach, import, or link files from this skill alone
- Prefer DOI and ISBN evidence over fuzzy title overlap
