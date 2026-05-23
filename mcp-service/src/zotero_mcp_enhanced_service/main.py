from __future__ import annotations

import argparse
from pathlib import Path

from .config import AppConfig
from .job_store import JobStore
from .ocrmypdf_runner import OcrmypdfRunner
from .pdf_service import PdfBookmarkService
from .runner import StubOcrRunner
from .server import build_server
from .service import OcrJobService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="zotero-mcp-enhanced MCP service")
    parser.add_argument("--base-dir", type=Path, default=Path.cwd())
    parser.add_argument("--runner", choices=["ocrmypdf", "stub"], default="stub")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=23120, help="Port for streamable-http transport (default: 23120)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    
    # Set port via environment variable for streamable-http transport
    if args.transport == "streamable-http":
        import os
        os.environ["MCP_HTTP_PORT"] = str(args.port)
    
    config = AppConfig.from_base_dir(args.base_dir)
    runner = (
        OcrmypdfRunner(ocrmypdf_path=config.ocrmypdf_path, timeout_seconds=config.command_timeout_seconds)
        if args.runner == "ocrmypdf"
        else StubOcrRunner()
    )
    service = OcrJobService(config=config, store=JobStore(config), runner=runner)
    build_server(service, bookmark_service=PdfBookmarkService()).run(args.transport)


if __name__ == "__main__":
    main()
