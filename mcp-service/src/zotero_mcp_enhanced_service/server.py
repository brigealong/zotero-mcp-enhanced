from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .pdf_service import PdfBookmarkService
from .service import OcrJobService
from .zotero_queue import ZoteroPluginUnavailableError, ZoteroWriteService

# ---------------------------------------------------------------------------
# SQLite read-only helpers (immutable mode — no API key, no DB lock conflict)
# ---------------------------------------------------------------------------

_ZOTERO_DB_PATH = os.path.expanduser("~/Zotero/zotero.sqlite")


def _zotero_readonly_connection() -> sqlite3.Connection:
    """Open Zotero SQLite DB in immutable mode (safe with Zotero running)."""
    uri = f"file:{_ZOTERO_DB_PATH}?immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def build_server(
    service: OcrJobService,
    *,
    bookmark_service: PdfBookmarkService | None = None,
    zotero_write_service: ZoteroWriteService | None = None,
    port: int = 23120,
) -> FastMCP:
    mcp = FastMCP("zotero-mcp-enhanced-service", port=port)

    # -- Existing OCR / PDF tools ------------------------------------------------

    @mcp.tool()
    def submit_pdf_ocr(
        source_pdf_path: str,
        target_item_key: str,
        source_attachment_key: str,
        timeout_seconds: int | None = None,
        job_label: str | None = None,
    ) -> dict[str, str]:
        return service.submit_pdf_ocr(
            source_pdf_path=source_pdf_path,
            target_item_key=target_item_key,
            source_attachment_key=source_attachment_key,
            timeout_seconds=timeout_seconds,
            job_label=job_label,
        )

    @mcp.tool()
    def get_ocr_job_status(job_id: str) -> dict[str, object]:
        return service.get_ocr_job_status(job_id)

    @mcp.tool()
    def get_ocr_job_result(job_id: str) -> dict[str, object]:
        return service.get_ocr_job_result(job_id)

    @mcp.tool()
    def cleanup_ocr_job(job_id: str, keep_logs: bool = False) -> dict[str, object]:
        return service.cleanup_ocr_job(job_id, keep_logs=keep_logs)

    if bookmark_service is not None:

        @mcp.tool()
        def create_bookmarked_pdf(
            source_pdf_path: str,
            output_pdf_path: str,
            toc_text: str | None = None,
            pdf_page_offset: int | None = None,
            max_depth: int = 2,
        ) -> dict[str, object]:
            return bookmark_service.create_bookmarked_pdf(
                source_pdf_path=source_pdf_path,
                output_pdf_path=output_pdf_path,
                toc_text=toc_text,
                pdf_page_offset=pdf_page_offset,
                max_depth=max_depth,
            )

    # -- Zotero write tools (via plugin queue) -----------------------------------

    zws = zotero_write_service or ZoteroWriteService()

    # Tier 1: Must-have for XHS collection pipeline

    @mcp.tool()
    def zotero_create_collection(
        name: str,
        parent_key: str | None = None,
        library_id: int = 1,
    ) -> dict[str, object]:
        """Create a new collection in Zotero.

        Args:
            name: Name of the collection to create.
            parent_key: Optional parent collection key for nested collections.
            library_id: Zotero library ID (default 1 = user library).

        Returns:
            Dict with success, request_id, collection_key, collection_name, etc.
        """
        try:
            return zws.create_collection(name, parent_key, library_id=library_id)
        except ZoteroPluginUnavailableError as exc:
            return {"success": False, "error": f"Zotero plugin not available: {exc}"}

    @mcp.tool()
    def zotero_add_item_to_collections(
        item_key: str,
        collection_keys: list[str],
        library_id: int = 1,
    ) -> dict[str, object]:
        """Add an existing Zotero item to one or more collections.

        Args:
            item_key: The item key to add.
            collection_keys: List of collection keys to add the item to.
            library_id: Zotero library ID (default 1 = user library).

        Returns:
            Dict with success, request_id, item_key, collections, etc.
        """
        try:
            return zws.add_item_to_collections(item_key, collection_keys, library_id=library_id)
        except ZoteroPluginUnavailableError as exc:
            return {"success": False, "error": f"Zotero plugin not available: {exc}"}

    @mcp.tool()
    def zotero_update_item_fields(
        item_key: str,
        fields: dict[str, str],
        library_id: int = 1,
    ) -> dict[str, object]:
        """Update fields of an existing Zotero item.

        Args:
            item_key: The item key to update.
            fields: Dict of field names to new values (e.g. {"title": "New Title"}).
            library_id: Zotero library ID (default 1 = user library).

        Returns:
            Dict with success, request_id, item_key, updated_fields, etc.
        """
        try:
            return zws.update_item_fields(item_key, fields, library_id=library_id)
        except ZoteroPluginUnavailableError as exc:
            return {"success": False, "error": f"Zotero plugin not available: {exc}"}

    @mcp.tool()
    def zotero_create_note(
        content: str,
        parent_key: str | None = None,
        collection_keys: list[str] | None = None,
        library_id: int = 1,
    ) -> dict[str, object]:
        """Create a new note in Zotero.

        Args:
            content: Note content (HTML or plain text).
            parent_key: Optional parent item key for a child note.
            collection_keys: Optional list of collection keys for a standalone note.
                Cannot be used together with parent_key.
            library_id: Zotero library ID (default 1 = user library).

        Returns:
            Dict with success, request_id, item_key, note_length, etc.
        """
        try:
            return zws.create_note(content, parent_key, collection_keys, library_id=library_id)
        except ZoteroPluginUnavailableError as exc:
            return {"success": False, "error": f"Zotero plugin not available: {exc}"}

    # Tier 2: Nice-to-have, same queue path

    @mcp.tool()
    def zotero_create_item(
        item_type: str,
        fields: dict[str, str],
        creators: list[dict[str, object]] | None = None,
        collection_keys: list[str] | None = None,
        tags: list[str] | None = None,
        library_id: int = 1,
    ) -> dict[str, object]:
        """Create a new regular item in Zotero (book, journalArticle, webpage, etc.).

        Args:
            item_type: Item type. Supported: book, journalArticle, bookSection, webpage, document.
            fields: Required fields. Must include at least "title".
            creators: Optional list of creator dicts with keys:
                creatorType (author/editor/translator/bookAuthor),
                firstName, lastName, fieldMode.
            collection_keys: Optional list of collection keys to add the item to.
            tags: Optional list of tag strings.
            library_id: Zotero library ID (default 1 = user library).

        Returns:
            Dict with success, request_id, item_key, item_type, fields, etc.
        """
        try:
            return zws.create_item(
                item_type=item_type,
                fields=fields,
                creators=creators,
                collection_keys=collection_keys,
                tags=tags,
                library_id=library_id,
            )
        except ZoteroPluginUnavailableError as exc:
            return {"success": False, "error": f"Zotero plugin not available: {exc}"}

    @mcp.tool()
    def zotero_update_note(
        item_key: str,
        content: str,
        mode: str = "replace",
        library_id: int = 1,
    ) -> dict[str, object]:
        """Update an existing note's content.

        Args:
            item_key: The note item key to update.
            content: New note content.
            mode: Update mode: "replace" (default), "append", or "prepend".
            library_id: Zotero library ID (default 1 = user library).

        Returns:
            Dict with success, request_id, item_key, mode, note_length, etc.
        """
        try:
            return zws.update_note(item_key, content, mode=mode, library_id=library_id)
        except ZoteroPluginUnavailableError as exc:
            return {"success": False, "error": f"Zotero plugin not available: {exc}"}

    # -- Zotero read tools (SQLite immutable mode, no API key needed) ---------

    @mcp.tool()
    def zotero_search_items(
        query: str,
        limit: int = 20,
        collection_key: str | None = None,
    ) -> dict[str, object]:
        """Search Zotero items by title/URL/extra text. Reads directly from
        the local Zotero SQLite database — no API key or Web API needed.

        Args:
            query: Substring to search in title, URL, and extra fields.
            limit: Max results (default 20).
            collection_key: Optional collection key to scope the search.
        """
        try:
            conn = _zotero_readonly_connection()
            params: list = [f"%{query}%"]
            sql = """
                SELECT DISTINCT i.key, i.itemID
                FROM items i
                JOIN itemData id_t ON i.itemID = id_t.itemID
                JOIN itemDataValues idv_t ON id_t.valueID = idv_t.valueID
            """
            if collection_key:
                sql += " JOIN collectionItems ci ON i.itemID = ci.itemID "
            sql += """
                WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems)
                AND id_t.fieldID IN (1, 13, 16)
                AND idv_t.value LIKE ?
            """
            if collection_key:
                sql += " AND ci.collectionID = (SELECT collectionID FROM collections WHERE key = ?)"
                params.append(collection_key)
            sql += " ORDER BY i.itemID DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            conn.close()

            if not rows:
                return {"success": True, "count": 0, "items": []}

            conn2 = _zotero_readonly_connection()
            items = []
            for row in rows:
                field_rows = conn2.execute(
                    "SELECT fd.fieldName, idv.value FROM itemData id "
                    "JOIN fields fd ON id.fieldID = fd.fieldID "
                    "JOIN itemDataValues idv ON id.valueID = idv.valueID "
                    "WHERE id.itemID = ? AND fd.fieldName IN ('title','url','dateAdded')",
                    (row["itemID"],)
                ).fetchall()
                fields = {r["fieldName"]: (r["value"] or "") for r in field_rows}
                # Get itemType from items + itemTypes join
                type_row = conn2.execute(
                    "SELECT it.typeName FROM items i "
                    "JOIN itemTypes it ON i.itemTypeID = it.itemTypeID "
                    "WHERE i.itemID = ?", (row["itemID"],)
                ).fetchone()
                items.append({
                    "key": row["key"],
                    "title": fields.get("title", ""),
                    "url": fields.get("url", ""),
                    "dateAdded": fields.get("dateAdded", ""),
                    "itemType": type_row["typeName"] if type_row else "",
                })
            conn2.close()
            return {"success": True, "count": len(items), "items": items}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @mcp.tool()
    def zotero_search_collections(query: str) -> dict[str, object]:
        """Search Zotero collections by name. Reads directly from the local
        Zotero SQLite database — no API key needed.

        Args:
            query: Substring to match against collection names.
        """
        try:
            conn = _zotero_readonly_connection()
            rows = conn.execute(
                "SELECT c.key, c.collectionName, c.collectionID, pc.key as parentKey "
                "FROM collections c "
                "LEFT JOIN collections pc ON c.parentCollectionID = pc.collectionID "
                "WHERE c.collectionName LIKE ? "
                "ORDER BY c.collectionName",
                (f"%{query}%",)
            ).fetchall()
            conn.close()
            return {
                "success": True,
                "count": len(rows),
                "collections": [
                    {"key": r["key"], "name": r["collectionName"],
                     "collectionID": r["collectionID"], "parentKey": r["parentKey"]}
                    for r in rows
                ]
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @mcp.tool()
    def zotero_get_recent(limit: int = 20, collection_key: str | None = None) -> dict[str, object]:
        """Get recently added Zotero items. Reads directly from the local
        Zotero SQLite database — no API key needed.

        Args:
            limit: Max results (default 20).
            collection_key: Optional collection key to scope results.
        """
        try:
            conn = _zotero_readonly_connection()
            sql = """
                SELECT DISTINCT i.key, i.itemID
                FROM items i
            """
            params: list = []
            if collection_key:
                sql += " JOIN collectionItems ci ON i.itemID = ci.itemID "
            sql += """
                WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems)
            """
            if collection_key:
                sql += " AND ci.collectionID = (SELECT collectionID FROM collections WHERE key = ?)"
                params.append(collection_key)
            sql += " ORDER BY i.itemID DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            conn.close()

            if not rows:
                return {"success": True, "count": 0, "items": []}

            conn2 = _zotero_readonly_connection()
            items = []
            for row in rows:
                field_rows = conn2.execute(
                    "SELECT fd.fieldName, idv.value FROM itemData id "
                    "JOIN fields fd ON id.fieldID = fd.fieldID "
                    "JOIN itemDataValues idv ON id.valueID = idv.valueID "
                    "WHERE id.itemID = ? AND fd.fieldName IN ('title','url','dateAdded')",
                    (row["itemID"],)
                ).fetchall()
                fields = {r["fieldName"]: (r["value"] or "") for r in field_rows}
                type_row = conn2.execute(
                    "SELECT it.typeName FROM items i "
                    "JOIN itemTypes it ON i.itemTypeID = it.itemTypeID "
                    "WHERE i.itemID = ?", (row["itemID"],)
                ).fetchone()
                items.append({
                    "key": row["key"],
                    "title": fields.get("title", ""),
                    "url": fields.get("url", ""),
                    "dateAdded": fields.get("dateAdded", ""),
                    "itemType": type_row["typeName"] if type_row else "",
                })
            conn2.close()
            return {"success": True, "count": len(items), "items": items}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    return mcp
