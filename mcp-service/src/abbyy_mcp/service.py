from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import AppConfig
from .job_store import JobStore
from .models import JobStatus
from .runner import OcrRunner


class OcrJobService:
    def __init__(self, *, config: AppConfig, store: JobStore, runner: OcrRunner) -> None:
        self.config = config
        self.store = store
        self.runner = runner
        self.executor = ThreadPoolExecutor(max_workers=config.max_workers, thread_name_prefix="abbyy-ocr")

    def submit_pdf_ocr(
        self,
        *,
        source_pdf_path: Path,
        target_item_key: str,
        source_attachment_key: str,
        timeout_seconds: int | None = None,
        job_label: str | None = None,
    ) -> dict[str, str]:
        source_pdf_path = Path(source_pdf_path)
        if not source_pdf_path.exists():
            raise FileNotFoundError(source_pdf_path)
        record = self.store.create_job(
            source_pdf_path=source_pdf_path,
            target_item_key=target_item_key,
            source_attachment_key=source_attachment_key,
            timeout_seconds=timeout_seconds if timeout_seconds is not None else self.config.command_timeout_seconds,
            job_label=job_label,
        )
        self.executor.submit(self._run_job, record.job_id)
        return {
            "job_id": record.job_id,
            "status": record.status.value,
            "workspace_dir": str(record.workspace_dir),
            "planned_output_pdf_path": str(record.output_pdf_path),
            "target_item_key": record.target_item_key,
            "source_attachment_key": record.source_attachment_key,
            "source_pdf_path": str(record.source_pdf_path),
            "timeout_seconds": str(record.timeout_seconds),
        }

    def get_ocr_job_status(self, job_id: str) -> dict[str, object]:
        record = self.store.get_job(job_id)
        return {
            "job_id": record.job_id,
            "status": record.status.value,
            "progress_message": record.progress_message,
            "source_pdf_path": str(record.source_pdf_path),
            "output_pdf_path": str(record.output_pdf_path),
            "target_item_key": record.target_item_key,
            "source_attachment_key": record.source_attachment_key,
            "error_message": record.error_message,
            "timeout_seconds": record.timeout_seconds,
        }

    def get_ocr_job_result(self, job_id: str) -> dict[str, object]:
        record = self.store.get_job(job_id)
        return {
            "job_id": record.job_id,
            "status": record.status.value,
            "output_pdf_path": str(record.output_pdf_path),
            "target_item_key": record.target_item_key,
            "source_attachment_key": record.source_attachment_key,
            "source_pdf_path": str(record.source_pdf_path),
            "suggested_replacement_filename": record.source_pdf_path.name,
            "cleanup_ready": record.status == JobStatus.SUCCEEDED,
            "timeout_seconds": record.timeout_seconds,
        }

    def cleanup_ocr_job(self, job_id: str, *, keep_logs: bool = False) -> dict[str, object]:
        cleaned_paths = self.store.cleanup_job_files(job_id, keep_logs=keep_logs)
        record = self.store.mark_cleaned(job_id)
        return {
            "job_id": record.job_id,
            "status": record.status.value,
            "cleaned_paths": cleaned_paths,
        }

    def _run_job(self, job_id: str) -> None:
        record = self.store.update_status(job_id, JobStatus.RUNNING, progress_message="OCR running")
        try:
            self.runner.run(
                source_pdf_path=record.source_pdf_path,
                output_pdf_path=record.output_pdf_path,
                report_path=record.report_path,
                timeout_seconds=record.timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            self.store.mark_failed(job_id, error_message=str(exc))
            return
        self.store.mark_succeeded(job_id)
