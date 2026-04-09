---
name: zotero-workflow-orchestrator
description: Use this skill whenever the user asks for two or more Zotero actions in one request, especially resolve-then-write chains such as metadata lookup, local attachment discovery, note updates, collection placement, attachment import, attachment replacement, or trash.
---

# Zotero Workflow Orchestrator

## Overview

This skill coordinates multi-step Zotero work in the current MCP-first setup.

Its job is to decide:
- which atomic skill should run first
- what structured output should be passed to the next step
- whether the final write should go through native Zotero MCP or the legacy local bridge fallback

It should not duplicate the logic of atomic skills.

It also owns the quote-to-annotation locator branch for already-imported PDFs when a sentence from Markdown or note text must be turned into a real Zotero highlight annotation.

Public scope boundary:
- this published skill does not assume any bundled OCR or PDF-bookmark MCP service
- if a machine has a private local PDF enhancement chain, treat that as a separate pre-processing step before this skill starts
- this skill only orchestrates the Zotero-side workflow that this repository publicly ships

## Building Blocks

Route to these building blocks first when they fit:
- `zotero-metadata`
- `zotero-attachment-resolve`

Use the local quote-to-annotation script when the workflow already has the final imported attachment and needs a real highlight from selected text:
- `mcp-service/scripts/create_highlight_from_quote.py`

Then choose the final write path:
- native Zotero MCP for item, metadata, note, tag, collection, attachment import, and trash writes
- `scripts/local_writer_bridge.py` only as a fallback for environments that still lack the upgraded MCP plugin, or when native attachment import hits a path-handling edge case that is not yet resolved

## When To Use

Use this skill when the request contains two or more Zotero actions in one request, for example:
- resolve metadata, then find the local PDF, then write into Zotero
- attach a local PDF to an existing item, then update a note or collection
- replace an existing PDF attachment with a better local file
- turn one selected quote into a real Zotero highlight annotation on an already-imported attachment

Do not use this skill when:
- the user is asking for one atomic step only
- the correct file path is already known and the work is a single direct write

## Routing Rules

### Metadata First

Choose `zotero-metadata` first when the write target is not yet stable.

### Attachment First

Choose `zotero-attachment-resolve` first when the item already exists or metadata is already stable, but the local file path is unknown.

### Metadata Then Attachment

Use this chain when local file search needs title, creator, DOI, or ISBN produced by metadata resolution.

### Default Quote-To-Annotation Chain

Use this branch only after the final PDF has already been written back to Zotero and confirmed as the canonical attachment.

Run these steps in order:
1. identify the final attachment key on the Zotero item
2. call `scripts/create_highlight_from_quote.py`
3. read the returned `locator` object instead of recomputing page or rects elsewhere
4. if `locator.match_quality.exact_text=true`, treat the annotation as auto-approved
5. if `locator.match_quality.exact_text=false`, keep the result JSON and mark it as review-needed before using the annotation key in downstream note writeback

Stable implementation rules:
- always run against the final imported PDF, not an outdated local draft
- page estimation should come from `.zotero-ft-cache` first
- text boxes should come from `pdftotext -tsv`
- `pdftotext` coordinates must be converted from top-origin page space into PDF bottom-left coordinates before calling Zotero `createAnnotation`
- downstream steps should consume `locator.rects` only; `locator.raw_rects` is diagnostic data, not writeback input
- keep the result JSON because it carries `annotationKey`, `locator`, and match-quality evidence for later note deep links

Default timeout guidance:
- for very long scanned books, allow up to 7200 seconds

## Validated Write Map

### Use Zotero MCP Directly

Current validated MCP write actions in this environment:
- `write_item`
- `write_metadata`
- `write_note`
- `write_tag`
- `create_collection`
- `update_collection`
- `delete_collection`
- `add_items_to_collection`
- `remove_items_from_collection`
- `write_attachment`
- `trash_item`

These actions were verified against the live local MCP endpoint, not only inferred from tool metadata.

### Bridge Fallback Only

Legacy bridge actions still available through `scripts/local_writer_bridge.py`:
- `importStoredAttachment`
- `trashAttachment`
- `trashRegularItem`

Default working directory:
- environment variable `ZOTERO_MCP_QUEUE_DIR`, otherwise the system temp directory under `zotero-mcp-enhanced`

Use the bridge only when:
- the machine still runs an older MCP plugin build without `write_attachment` and `trash_item`
- native `write_attachment` fails on a non-ASCII local file path and a fast workaround is needed

## Current Capability Boundary

Use native Zotero MCP first whenever it already supports the write.

Current confirmed native Zotero MCP capabilities:
- import a local file path into Zotero storage under an existing parent item via `write_attachment`
- trash a regular item, attachment, or note by key via `trash_item`

Current confirmed quote-to-annotation script capabilities:
- estimate the target page from `.zotero-ft-cache`
- derive line-level highlight boxes from `pdftotext -tsv`
- convert top-origin TSV boxes into PDF-standard coordinates before writeback
- create a real Zotero `highlight` annotation through the local bridge
- return a structured `locator` object with `rects`, `raw_rects`, `page_number`, `strategy`, and `match_quality`

Current residual caveat:
- native `write_attachment` was fully verified on an ASCII local file path
- one smoke attempt using a Chinese path returned `Source file not found`
- this is not yet isolated as a plugin bug versus a caller-side encoding issue

Because of that caveat, keep the bridge available as a fallback until non-ASCII path import is verified end to end.

## Performance Guidance

Observed timings in this environment:
- `zotero-metadata` local single-file extraction: about `0.54s`
- `zotero-attachment-resolve` with explicit small `search_root`: about `0.14s`
- `zotero-attachment-resolve` with default multi-root scan: about `5.39s`
- MCP `search_library(title contains)`: about `1.13s`
- MCP `create_collection`: about `1.46s`
- MCP `write_item(create)`: about `2.95s`
- MCP `write_metadata`: about `0.41s`
- MCP `write_note(create)`: about `0.54s`
- MCP `write_tag(add)`: about `0.65s`
- native MCP `write_attachment`: about `0.38s`
- native MCP `trash_item` on attachment: about `0.16s`
- native MCP `trash_item` on regular item: about `0.18s`

Fast-path guidance:
- always pass an explicit `search_root` to `zotero-attachment-resolve` when possible
- prefer native Zotero MCP over the bridge for attachment import and trash, because it removes queue polling and extra process hops

## Handoff Contract

Keep the handoff between steps structured. Prefer passing:
- `title`
- `creators`
- `publisher`
- `date`
- `place`
- `isbn`
- `doi`
- `attachment_path`
- `collection_key` or `collection_name`
- `target_item_key`
- `source_attachment_key`
- `annotation_key`
- `locator`
- `match_quality`
- `confidence`
- `evidence`

## Safety Rules

- do not escalate a single-step request into an orchestrated chain
- do not hide ambiguity between same-name collections or close attachment matches
- if metadata or attachment evidence is weak, stop before the write step
- keep read and write responsibilities separated: local scripts for read, MCP for writes, bridge only for fallback
- if native `write_attachment` fails on a non-ASCII path, do not silently retry forever; either normalize the path to an ASCII temp location or explicitly fall back to the bridge
- if bookmark extraction confidence is low, prefer using trusted bibliographic or publisher-side sources to refine the table of contents before the final import
- do not recompute quote highlight rects in downstream skills once `create_highlight_from_quote.py` has returned a `locator`
- if `locator.match_quality.has_extra_text=true`, do not silently present the annotation as exact; either flag it for review or use a shorter quote span

## Output Expectations

The response should make clear:
- which Zotero actions were detected
- which atomic skill or local script runs first
- what evidence gates the final write
- whether the final write path is native MCP or bridge fallback
- for quote-based annotation flows, whether the returned locator was exact-match or review-needed
- whether the workflow executed fully or stopped for confirmation
