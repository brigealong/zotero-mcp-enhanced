from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CLEANUP_PENDING = "cleanup_pending"
    CLEANED = "cleaned"


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    source_pdf_path: Path
    workspace_dir: Path
    output_pdf_path: Path
    report_path: Path
    target_item_key: str
    source_attachment_key: str
    timeout_seconds: int
    job_label: str | None = None
    progress_message: str | None = None
    error_message: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("source_pdf_path", "workspace_dir", "output_pdf_path", "report_path"):
            data[key] = str(data[key])
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JobRecord":
        return cls(
            job_id=payload["job_id"],
            status=JobStatus(payload["status"]),
            source_pdf_path=Path(payload["source_pdf_path"]),
            workspace_dir=Path(payload["workspace_dir"]),
            output_pdf_path=Path(payload["output_pdf_path"]),
            report_path=Path(payload["report_path"]),
            target_item_key=payload["target_item_key"],
            source_attachment_key=payload["source_attachment_key"],
            timeout_seconds=payload["timeout_seconds"],
            job_label=payload.get("job_label"),
            progress_message=payload.get("progress_message"),
            error_message=payload.get("error_message"),
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
        )

    def public_dict(self) -> dict[str, Any]:
        data = self.to_dict()
        data["cleanup_ready"] = self.status == JobStatus.SUCCEEDED
        data["suggested_replacement_filename"] = self.source_pdf_path.name
        return data
