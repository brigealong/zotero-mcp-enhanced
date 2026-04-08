from __future__ import annotations

import argparse
from pathlib import Path

from .abbyy_runner import FineCmdRunner
from .config import AppConfig
from .job_store import JobStore
from .pdf_service import PdfBookmarkService
from .runner import StubOcrRunner
from .server import build_server
from .service import OcrJobService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ABBYY searchable PDF MCP server")
    parser.add_argument("--base-dir", type=Path, default=Path.cwd())
    parser.add_argument("--runner", choices=["abbyy", "stub"], default="abbyy")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = AppConfig.from_base_dir(args.base_dir)
    runner = (
        FineCmdRunner(finecmd_path=config.finecmd_path, timeout_seconds=config.command_timeout_seconds)
        if args.runner == "abbyy"
        else StubOcrRunner()
    )
    service = OcrJobService(config=config, store=JobStore(config), runner=runner)
    build_server(service, bookmark_service=PdfBookmarkService()).run(args.transport)


if __name__ == "__main__":
    main()
