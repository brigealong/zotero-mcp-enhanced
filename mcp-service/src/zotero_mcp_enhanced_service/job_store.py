from __future__ import annotations

import json
import shutil
import threading
import uuid
from pathlib import Path

from .config import AppConfig
from .models import JobRecord, JobStatus, now_iso


class JobStore:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._lock = threading.RLock()
        self.config.jobs_dir.mkdir(parents=True, exist_ok=True)

    def create_job(
        self,
        *,
        source_pdf_path: Path,
        target_item_key: str,
        source_attachment_key: str,
        timeout_seconds: int | None = None,
        job_label: str | None = None,
    ) -> JobRecord:
        job_id = uuid.uuid4().hex
        workspace_dir = self.config.jobs_dir / job_id
        workspace_dir.mkdir(parents=True, exist_ok=True)
        record = JobRecord(
            job_id=job_id,
            status=JobStatus.QUEUED,
            source_pdf_path=Path(source_pdf_path),
            workspace_dir=workspace_dir,
            output_pdf_path=workspace_dir / "output-searchable.pdf",
            report_path=workspace_dir / "report.txt",
            target_item_key=target_item_key,
            source_attachment_key=source_attachment_key,
            timeout_seconds=timeout_seconds if timeout_seconds is not None else self.config.command_timeout_seconds,
            job_label=job_label,
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        self.save_job(record)
        return record

    def get_job(self, job_id: str) -> JobRecord:
        with self._lock:
            job_file = self._job_file(job_id)
            payload = json.loads(job_file.read_text(encoding="utf-8"))
            return JobRecord.from_dict(payload)

    def save_job(self, record: JobRecord) -> JobRecord:
        with self._lock:
            record.updated_at = now_iso()
            self._write_atomic(
                self._job_file(record.job_id),
                json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
            )
            return record

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        progress_message: str | None = None,
        error_message: str | None = None,
    ) -> JobRecord:
        record = self.get_job(job_id)
        record.status = status
        if progress_message is not None:
            record.progress_message = progress_message
        if error_message is not None:
            record.error_message = error_message
        return self.save_job(record)

    def mark_succeeded(self, job_id: str, *, progress_message: str = "OCR completed") -> JobRecord:
        return self.update_status(job_id, JobStatus.SUCCEEDED, progress_message=progress_message)

    def mark_failed(self, job_id: str, *, error_message: str) -> JobRecord:
        return self.update_status(job_id, JobStatus.FAILED, error_message=error_message)

    def mark_cleanup_pending(self, job_id: str) -> JobRecord:
        return self.update_status(job_id, JobStatus.CLEANUP_PENDING)

    def mark_cleaned(self, job_id: str) -> JobRecord:
        return self.update_status(job_id, JobStatus.CLEANED)

    def cleanup_job_files(self, job_id: str, *, keep_logs: bool = False) -> list[str]:
        record = self.get_job(job_id)
        cleaned_paths: list[str] = []
        for child in record.workspace_dir.iterdir():
            if child.name == "job.json":
                continue
            if keep_logs and child.name == "report.txt":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)
            cleaned_paths.append(str(child))
        return cleaned_paths

    def _job_file(self, job_id: str) -> Path:
        return self.config.jobs_dir / job_id / "job.json"

    def _write_atomic(self, path: Path, payload: str) -> None:
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(path)
