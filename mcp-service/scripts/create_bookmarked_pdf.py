from __future__ import annotations

import argparse
import json
from pathlib import Path

from abbyy_mcp.pdf_service import PdfBookmarkService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a bookmarked PDF from an OCR PDF")
    parser.add_argument("--source-pdf", type=Path, required=True)
    parser.add_argument("--output-pdf", type=Path, required=True)
    parser.add_argument("--toc-file", type=Path)
    parser.add_argument("--pdf-page-offset", type=int)
    parser.add_argument("--max-depth", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    toc_text = args.toc_file.read_text(encoding="utf-8") if args.toc_file else None
    result = PdfBookmarkService().create_bookmarked_pdf(
        source_pdf_path=args.source_pdf,
        output_pdf_path=args.output_pdf,
        toc_text=toc_text,
        pdf_page_offset=args.pdf_page_offset,
        max_depth=args.max_depth,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
