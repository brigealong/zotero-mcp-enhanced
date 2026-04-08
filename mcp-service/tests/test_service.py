import time
from pathlib import Path

from abbyy_mcp.config import AppConfig
from abbyy_mcp.job_store import JobStore
from abbyy_mcp.runner import StubOcrRunner
from abbyy_mcp.service import OcrJobService


class CapturingRunner(StubOcrRunner):
    def __init__(self) -> None:
        self.timeout_seconds: int | None = None

    def run(
        self,
        *,
        source_pdf_path: Path,
        output_pdf_path: Path,
        report_path: Path,
        timeout_seconds: int | None = None,
    ):
        self.timeout_seconds = timeout_seconds
        return super().run(
            source_pdf_path=source_pdf_path,
            output_pdf_path=output_pdf_path,
            report_path=report_path,
            timeout_seconds=timeout_seconds,
        )


def test_service_submits_job_and_returns_result(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-1.4\nhello")
    config = AppConfig.from_base_dir(tmp_path)
    store = JobStore(config)
    service = OcrJobService(config=config, store=store, runner=StubOcrRunner())

    submitted = service.submit_pdf_ocr(
        source_pdf_path=source,
        target_item_key="ITEM123",
        source_attachment_key="ATTACH123",
        job_label="round-1",
    )

    deadline = time.time() + 5
    status = service.get_ocr_job_status(submitted["job_id"])
    while status["status"] in {"queued", "running"} and time.time() < deadline:
        time.sleep(0.05)
        status = service.get_ocr_job_status(submitted["job_id"])

    result = service.get_ocr_job_result(submitted["job_id"])

    assert result["status"] == "succeeded"
    assert Path(result["output_pdf_path"]).exists()
    assert result["target_item_key"] == "ITEM123"
    assert result["source_attachment_key"] == "ATTACH123"


def test_service_passes_per_job_timeout_to_runner(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-1.4\nhello")
    config = AppConfig.from_base_dir(tmp_path)
    store = JobStore(config)
    runner = CapturingRunner()
    service = OcrJobService(config=config, store=store, runner=runner)

    submitted = service.submit_pdf_ocr(
        source_pdf_path=source,
        target_item_key="ITEM123",
        source_attachment_key="ATTACH123",
        timeout_seconds=5400,
    )

    deadline = time.time() + 5
    result = service.get_ocr_job_result(submitted["job_id"])
    while result["status"] in {"queued", "running"} and time.time() < deadline:
        time.sleep(0.05)
        result = service.get_ocr_job_result(submitted["job_id"])

    status = service.get_ocr_job_status(submitted["job_id"])

    assert runner.timeout_seconds == 5400
    assert status["timeout_seconds"] == 5400


def test_service_cleanup_removes_workspace(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-1.4\nhello")
    config = AppConfig.from_base_dir(tmp_path)
    store = JobStore(config)
    service = OcrJobService(config=config, store=store, runner=StubOcrRunner())
    submitted = service.submit_pdf_ocr(
        source_pdf_path=source,
        target_item_key="ITEM123",
        source_attachment_key="ATTACH123",
    )

    deadline = time.time() + 5
    result = service.get_ocr_job_result(submitted["job_id"])
    while result["status"] in {"queued", "running"} and time.time() < deadline:
        time.sleep(0.05)
        result = service.get_ocr_job_result(submitted["job_id"])

    cleaned = service.cleanup_ocr_job(submitted["job_id"])

    assert cleaned["status"] == "cleaned"
    assert cleaned["cleaned_paths"]
