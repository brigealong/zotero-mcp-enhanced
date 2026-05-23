import asyncio
from pathlib import Path

from zotero_mcp_enhanced_service.config import AppConfig
from zotero_mcp_enhanced_service.job_store import JobStore
from zotero_mcp_enhanced_service.pdf_service import PdfBookmarkService
from zotero_mcp_enhanced_service.runner import StubOcrRunner
from zotero_mcp_enhanced_service.server import build_server
from zotero_mcp_enhanced_service.service import OcrJobService


def test_server_exposes_expected_tools(tmp_path: Path) -> None:
    config = AppConfig.from_base_dir(Path(tmp_path))
    service = OcrJobService(config=config, store=JobStore(config), runner=StubOcrRunner())
    bookmark_service = PdfBookmarkService()
    server = build_server(service, bookmark_service=bookmark_service)

    tools = asyncio.run(server.list_tools())
    tool_names = {tool.name for tool in tools}

    assert tool_names == {
        "create_bookmarked_pdf",
        "submit_pdf_ocr",
        "get_ocr_job_status",
        "get_ocr_job_result",
        "cleanup_ocr_job",
        "zotero_create_collection",
        "zotero_add_item_to_collections",
        "zotero_update_item_fields",
        "zotero_create_note",
        "zotero_create_item",
        "zotero_update_note",
    }
