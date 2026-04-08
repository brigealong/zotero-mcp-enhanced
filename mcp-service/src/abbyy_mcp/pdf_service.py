from __future__ import annotations

from pathlib import Path

from .bookmarks import extract_toc_text, infer_pdf_page_offset, parse_toc_entries, write_pdf_bookmarks


class PdfBookmarkService:
    def create_bookmarked_pdf(
        self,
        *,
        source_pdf_path: str | Path,
        output_pdf_path: str | Path,
        toc_text: str | None = None,
        pdf_page_offset: int | None = None,
        max_depth: int = 2,
    ) -> dict[str, object]:
        source_path = Path(source_pdf_path)
        output_path = Path(output_pdf_path)
        if not source_path.exists():
            raise FileNotFoundError(source_path)

        effective_toc_text = toc_text or extract_toc_text(source_path)
        entries = parse_toc_entries(effective_toc_text, max_depth=max_depth)
        if not entries:
            raise ValueError("No TOC entries were detected")

        effective_offset = (
            pdf_page_offset
            if pdf_page_offset is not None
            else infer_pdf_page_offset(entries, pdf_path=source_path)
        )

        written_path = write_pdf_bookmarks(
            source_pdf_path=source_path,
            output_pdf_path=output_path,
            entries=entries,
            pdf_page_offset=effective_offset,
        )

        return {
            "source_pdf_path": str(source_path),
            "output_pdf_path": str(written_path),
            "toc_entry_count": len(entries),
            "pdf_page_offset": effective_offset,
            "max_depth": max_depth,
        }
