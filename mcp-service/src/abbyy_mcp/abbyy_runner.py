from __future__ import annotations

import subprocess
from pathlib import Path

from .runner import OcrRunResult


class FineCmdRunner:
    def __init__(self, *, finecmd_path: Path, timeout_seconds: int = 600) -> None:
        self.finecmd_path = Path(finecmd_path)
        self.timeout_seconds = timeout_seconds

    def build_command(
        self,
        *,
        source_pdf_path: Path,
        output_pdf_path: Path,
        report_path: Path,
    ) -> list[str]:
        return [
            self.finecmd_path.as_posix(),
            Path(source_pdf_path).as_posix(),
            "/out",
            str(output_pdf_path),
            "/report",
            str(report_path),
        ]

    def run(
        self,
        *,
        source_pdf_path: Path,
        output_pdf_path: Path,
        report_path: Path,
        timeout_seconds: int | None = None,
    ) -> OcrRunResult:
        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        command = self.build_command(
            source_pdf_path=source_pdf_path,
            output_pdf_path=output_pdf_path,
            report_path=report_path,
        )
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds if timeout_seconds is not None else self.timeout_seconds,
            check=False,
        )
        if completed.stdout:
            report_path.write_text(completed.stdout, encoding="utf-8")
        if completed.stderr:
            report_path.write_text(
                report_path.read_text(encoding="utf-8") + completed.stderr if report_path.exists() else completed.stderr,
                encoding="utf-8",
            )
        if completed.returncode != 0:
            raise RuntimeError(f"FineCmd exited with code {completed.returncode}")
        if not output_pdf_path.exists():
            raise RuntimeError("FineCmd completed without producing output PDF")
        return OcrRunResult(output_pdf_path=output_pdf_path, report_path=report_path)
