import threading
from pathlib import Path

from zotero_mcp_enhanced_service.config import AppConfig
from zotero_mcp_enhanced_service.job_store import JobStore
from zotero_mcp_enhanced_service.models import JobStatus


def test_job_store_creates_and_reads_job(tmp_path: Path) -> None:
    config = AppConfig.from_base_dir(tmp_path)
    store = JobStore(config)

    record = store.create_job(
        source_pdf_path=tmp_path / "source.pdf",
        target_item_key="ITEM123",
        source_attachment_key="ATTACH123",
        job_label="smoke",
    )

    saved = store.get_job(record.job_id)

    assert saved.job_id == record.job_id
    assert saved.status is JobStatus.QUEUED
    assert saved.workspace_dir == config.jobs_dir / record.job_id
    assert (saved.workspace_dir / "job.json").exists()


def test_job_store_marks_cleanup(tmp_path: Path) -> None:
    config = AppConfig.from_base_dir(tmp_path)
    store = JobStore(config)
    record = store.create_job(
        source_pdf_path=tmp_path / "source.pdf",
        target_item_key="ITEM123",
        source_attachment_key="ATTACH123",
    )
    record = store.update_status(record.job_id, JobStatus.CLEANUP_PENDING)

    cleaned = store.mark_cleaned(record.job_id)

    assert cleaned.status is JobStatus.CLEANED


def test_job_store_reads_valid_json_during_concurrent_updates(tmp_path: Path) -> None:
    config = AppConfig.from_base_dir(tmp_path)
    store = JobStore(config)
    record = store.create_job(
        source_pdf_path=tmp_path / "source.pdf",
        target_item_key="ITEM123",
        source_attachment_key="ATTACH123",
    )
    errors: list[Exception] = []
    stop = False

    def writer() -> None:
        for index in range(1000):
            store.update_status(
                record.job_id,
                JobStatus.RUNNING,
                progress_message=("x" * 10000) + str(index),
            )

    def reader() -> None:
        while not stop:
            try:
                store.get_job(record.job_id)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
                break

    reader_thread = threading.Thread(target=reader)
    writer_thread = threading.Thread(target=writer)
    reader_thread.start()
    writer_thread.start()
    writer_thread.join()
    stop = True
    reader_thread.join()

    assert errors == []
