"""Zotero plugin queue integration for MCP server.

Wraps the existing ZoteroQueueClient to expose stable, auditable MCP tools.
All write operations go through the plugin queue (file-based command/result protocol),
never through Zotero local REST API (23119/api).
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


class QueueError(RuntimeError):
    """Raised when a queue operation fails or times out."""


class ZoteroPluginUnavailableError(RuntimeError):
    """Raised when the Zotero plugin queue directory is not available."""


@dataclass(frozen=True)
class QueueResult:
    """Structured result from a queue command execution."""

    status: str  # "success" or "error"
    request_id: str
    request_signature: str | None
    action: str
    occurred_at: str | None
    data: dict[str, Any]
    error: str | None
    stack: str | None

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> dict[str, Any]:
        """Convert to a flat dict suitable for MCP tool return."""
        result: dict[str, Any] = {
            "status": self.status,
            "request_id": self.request_id,
            "action": self.action,
            "success": self.is_success,
        }
        if self.request_signature:
            result["request_signature"] = self.request_signature
        if self.occurred_at:
            result["occurred_at"] = self.occurred_at
        if self.error:
            result["error"] = self.error
        if self.stack:
            result["stack"] = self.stack
        # Merge data fields for convenience
        result.update(self.data)
        return result


class ZoteroQueueClient:
    """Low-level client for the zotero-mcp-enhanced plugin queue.

    Protocol: write ``<TMPDIR>/zotero-mcp-enhanced/commands/command-*.json``,
    poll ``<TMPDIR>/zotero-mcp-enhanced/results/result-<requestID>.json``.
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        poll_interval: float = 0.5,
        timeout: float = 30.0,
    ) -> None:
        if base_dir is None:
            configured = os.environ.get("ZOTERO_MCP_QUEUE_DIR") or os.environ.get("ZOTERO_PLUGIN_QUEUE_DIR")
            if configured:
                base_dir = Path(configured).expanduser()
            else:
                tmp = os.environ.get("TMPDIR") or tempfile.gettempdir()
                base_dir = Path(tmp) / "zotero-mcp-enhanced"
        self.base = Path(base_dir)
        self.commands = self.base / "commands"
        self.results = self.base / "results"
        self.poll_interval = poll_interval
        self.timeout = timeout
        if not self.base.exists():
            raise ZoteroPluginUnavailableError(
                f"queue base dir missing: {self.base} (plugin not running?)"
            )
        self.commands.mkdir(exist_ok=True)
        self.results.mkdir(exist_ok=True)

    def _submit(
        self, action: str, payload: dict[str, Any], *, library_id: int = 1, retries: int = 3
    ) -> QueueResult:
        """Submit a command to the plugin queue and wait for result."""
        last_timeout: Path | None = None
        for attempt in range(1, retries + 1):
            request_id = str(uuid.uuid4())
            result_path = self.results / f"result-{request_id}.json"
            command = {
                "action": action,
                "requestID": request_id,
                "libraryID": library_id,
                "resultPath": str(result_path),
                "alertOnSuccess": False,
                "alertOnError": False,
                **payload,
            }
            ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
            cmd_path = self.commands / f"command-{ts}-{request_id}.json"
            cmd_path.write_text(json.dumps(command, ensure_ascii=False), encoding="utf-8")

            deadline = time.time() + self.timeout
            while time.time() < deadline:
                if result_path.exists():
                    data = json.loads(result_path.read_text(encoding="utf-8"))
                    return self._parse_result(data, action, request_id)
                time.sleep(self.poll_interval)
            last_timeout = result_path

        raise QueueError(
            f"timeout after {retries} attempts waiting for {last_timeout}"
        )

    @staticmethod
    def _parse_result(data: dict[str, Any], action: str, request_id: str) -> QueueResult:
        """Parse raw result JSON into a structured QueueResult."""
        status = data.get("status", "error")
        return QueueResult(
            status=status,
            request_id=data.get("requestID") or request_id,
            request_signature=data.get("requestSignature"),
            action=data.get("action", action),
            occurred_at=data.get("occurredAt"),
            data={k: v for k, v in data.items() if k not in {
                "status", "requestID", "requestSignature", "action", "occurredAt",
                "error", "stack", "failedStepIndex", "stepResults", "configPath", "trigger"
            }},
            error=data.get("error"),
            stack=data.get("stack"),
        )

    # ------------------------------------------------------------------
    # Tier 1: Must-have for XHS collection pipeline
    # ------------------------------------------------------------------

    def create_collection(
        self, name: str, parent_key: str | None = None, *, library_id: int = 1
    ) -> QueueResult:
        """Create a new collection in Zotero."""
        payload: dict[str, Any] = {"name": name}
        if parent_key:
            payload["parentCollectionKey"] = parent_key
        return self._submit("createCollection", payload, library_id=library_id)

    def add_item_to_collections(
        self, item_key: str, collection_keys: list[str], *, library_id: int = 1
    ) -> QueueResult:
        """Add an existing item to one or more collections."""
        return self._submit(
            "addItemToCollections",
            {"itemKey": item_key, "collectionKeys": collection_keys},
            library_id=library_id,
        )

    def update_item_fields(
        self, item_key: str, fields: dict[str, str], *, library_id: int = 1
    ) -> QueueResult:
        """Update fields of an existing item."""
        return self._submit(
            "updateItemFields",
            {"itemKey": item_key, "fields": fields},
            library_id=library_id,
        )

    def create_note(
        self,
        content: str,
        parent_key: str | None = None,
        collection_keys: list[str] | None = None,
        *,
        library_id: int = 1,
    ) -> QueueResult:
        """Create a new note item, either standalone or child of a parent item."""
        if parent_key and collection_keys:
            raise QueueError(
                "createNote child notes must use parentKey without collectionKeys"
            )
        payload: dict[str, Any] = {"content": content}
        if parent_key:
            payload["parentKey"] = parent_key
        if collection_keys:
            payload["collectionKeys"] = collection_keys
        return self._submit("createNote", payload, library_id=library_id)

    # ------------------------------------------------------------------
    # Tier 2: Nice-to-have, same queue path
    # ------------------------------------------------------------------

    def create_item(
        self,
        item_type: str,
        fields: dict[str, str],
        *,
        creators: list[dict[str, Any]] | None = None,
        collection_keys: list[str] | None = None,
        tags: list[str] | None = None,
        library_id: int = 1,
    ) -> QueueResult:
        """Create a new regular item (book, journalArticle, webpage, etc.)."""
        payload: dict[str, Any] = {
            "itemType": item_type,
            "fields": fields,
        }
        if creators:
            payload["creators"] = creators
        if collection_keys:
            payload["collectionKeys"] = collection_keys
        if tags:
            payload["tags"] = tags
        return self._submit("createItem", payload, library_id=library_id)

    def update_note(
        self,
        item_key: str,
        content: str,
        *,
        mode: str = "replace",
        library_id: int = 1,
    ) -> QueueResult:
        """Update an existing note's content."""
        return self._submit(
            "updateNote",
            {"itemKey": item_key, "content": content, "mode": mode},
            library_id=library_id,
        )


class ZoteroWriteService:
    """High-level service wrapping ZoteroQueueClient for MCP integration.

    Provides clean, auditable methods that return flat dicts suitable for
    direct MCP tool responses.
    """

    def __init__(self, client: ZoteroQueueClient | None = None) -> None:
        self._client = client or ZoteroQueueClient()

    # ------------------------------------------------------------------
    # Tier 1
    # ------------------------------------------------------------------

    def create_collection(
        self,
        name: str,
        parent_key: str | None = None,
        *,
        library_id: int = 1,
    ) -> dict[str, Any]:
        result = self._client.create_collection(name, parent_key, library_id=library_id)
        if not result.is_success:
            return {
                "success": False,
                "error": result.error or "Unknown error",
                "request_id": result.request_id,
                "action": result.action,
            }
        return {
            "success": True,
            "request_id": result.request_id,
            "collection_key": result.data.get("collectionKey"),
            "collection_id": result.data.get("collectionID"),
            "collection_name": result.data.get("collectionName"),
            "parent_collection_key": result.data.get("parentCollectionKey"),
            "library_id": result.data.get("libraryID"),
        }

    def add_item_to_collections(
        self,
        item_key: str,
        collection_keys: list[str],
        *,
        library_id: int = 1,
    ) -> dict[str, Any]:
        result = self._client.add_item_to_collections(item_key, collection_keys, library_id=library_id)
        if not result.is_success:
            return {
                "success": False,
                "error": result.error or "Unknown error",
                "request_id": result.request_id,
                "action": result.action,
            }
        return {
            "success": True,
            "request_id": result.request_id,
            "item_key": result.data.get("itemKey"),
            "item_id": result.data.get("itemID"),
            "collections": result.data.get("collections", []),
            "collection_count_after_update": result.data.get("collectionCountAfterUpdate"),
            "library_id": result.data.get("libraryID"),
        }

    def update_item_fields(
        self,
        item_key: str,
        fields: dict[str, str],
        *,
        library_id: int = 1,
    ) -> dict[str, Any]:
        result = self._client.update_item_fields(item_key, fields, library_id=library_id)
        if not result.is_success:
            return {
                "success": False,
                "error": result.error or "Unknown error",
                "request_id": result.request_id,
                "action": result.action,
            }
        return {
            "success": True,
            "request_id": result.request_id,
            "item_key": result.data.get("itemKey"),
            "item_id": result.data.get("itemID"),
            "updated_fields": result.data.get("updatedFields", {}),
            "library_id": result.data.get("libraryID"),
        }

    def create_note(
        self,
        content: str,
        parent_key: str | None = None,
        collection_keys: list[str] | None = None,
        *,
        library_id: int = 1,
    ) -> dict[str, Any]:
        result = self._client.create_note(content, parent_key, collection_keys, library_id=library_id)
        if not result.is_success:
            return {
                "success": False,
                "error": result.error or "Unknown error",
                "request_id": result.request_id,
                "action": result.action,
            }
        return {
            "success": True,
            "request_id": result.request_id,
            "item_key": result.data.get("itemKey"),
            "item_id": result.data.get("itemID"),
            "parent_key": result.data.get("parentKey"),
            "note_length": result.data.get("noteLength"),
            "collections": result.data.get("collections", []),
            "library_id": result.data.get("libraryID"),
        }

    # ------------------------------------------------------------------
    # Tier 2
    # ------------------------------------------------------------------

    def create_item(
        self,
        item_type: str,
        fields: dict[str, str],
        *,
        creators: list[dict[str, Any]] | None = None,
        collection_keys: list[str] | None = None,
        tags: list[str] | None = None,
        library_id: int = 1,
    ) -> dict[str, Any]:
        result = self._client.create_item(
            item_type=item_type,
            fields=fields,
            creators=creators,
            collection_keys=collection_keys,
            tags=tags,
            library_id=library_id,
        )
        if not result.is_success:
            return {
                "success": False,
                "error": result.error or "Unknown error",
                "request_id": result.request_id,
                "action": result.action,
            }
        return {
            "success": True,
            "request_id": result.request_id,
            "item_key": result.data.get("itemKey"),
            "item_id": result.data.get("itemID"),
            "item_type": result.data.get("itemType"),
            "fields": result.data.get("fields", {}),
            "creators": result.data.get("creators", []),
            "collections": result.data.get("collections", []),
            "library_id": result.data.get("libraryID"),
        }

    def update_note(
        self,
        item_key: str,
        content: str,
        *,
        mode: str = "replace",
        library_id: int = 1,
    ) -> dict[str, Any]:
        result = self._client.update_note(item_key, content, mode=mode, library_id=library_id)
        if not result.is_success:
            return {
                "success": False,
                "error": result.error or "Unknown error",
                "request_id": result.request_id,
                "action": result.action,
            }
        return {
            "success": True,
            "request_id": result.request_id,
            "item_key": result.data.get("itemKey"),
            "item_id": result.data.get("itemID"),
            "mode": result.data.get("mode", mode),
            "note_length": result.data.get("noteLength"),
            "library_id": result.data.get("libraryID"),
        }
