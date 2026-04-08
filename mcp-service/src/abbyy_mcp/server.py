from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .pdf_service import PdfBookmarkService
from .service import OcrJobService


def build_server(service: OcrJobService, *, bookmark_service: PdfBookmarkService | None = None) -> FastMCP:
    mcp = FastMCP("abbyy-searchable-pdf")

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

    return mcp
