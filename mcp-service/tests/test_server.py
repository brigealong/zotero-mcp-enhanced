import asyncio
from pathlib import Path

from abbyy_mcp.config import AppConfig
from abbyy_mcp.job_store import JobStore
from abbyy_mcp.pdf_service import PdfBookmarkService
from abbyy_mcp.runner import StubOcrRunner
from abbyy_mcp.server import build_server
from abbyy_mcp.service import OcrJobService


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
    }
