from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .runner import OcrRunResult


class OcrmypdfRunner:
    def __init__(self, *, ocrmypdf_path: Path, timeout_seconds: int = 600) -> None:
        self.ocrmypdf_path = Path(ocrmypdf_path)
        self.timeout_seconds = timeout_seconds

    def build_command(
        self,
        *,
        source_pdf_path: Path,
        output_pdf_path: Path,
        report_path: Path,
    ) -> list[str]:
        return [
            self.ocrmypdf_path.as_posix(),
            "--optimize",
            "0",
            "--output-type",
            "pdf",
            "--sidecar",
            str(report_path),
            Path(source_pdf_path).as_posix(),
            str(output_pdf_path),
        ]

    def build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        path_parts = [part for part in env.get("PATH", "").split(os.pathsep) if part]

        if self.ocrmypdf_path.parent != Path("."):
            candidate = str(self.ocrmypdf_path.parent)
            if candidate not in path_parts:
                path_parts.insert(0, candidate)

        common_tesseract = r"C:\Program Files\Tesseract-OCR"
        if Path(common_tesseract).exists() and common_tesseract not in path_parts:
            path_parts.insert(0, common_tesseract)

        env["PATH"] = os.pathsep.join(path_parts)
        return env

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
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                env=self.build_env(),
                timeout=timeout_seconds if timeout_seconds is not None else self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("ocrmypdf command was not found. Install OCRmyPDF and ensure it is on PATH.") from exc
        if completed.stdout:
            report_path.write_text(completed.stdout, encoding="utf-8")
        if completed.stderr:
            report_path.write_text(
                report_path.read_text(encoding="utf-8") + completed.stderr if report_path.exists() else completed.stderr,
                encoding="utf-8",
            )
        if completed.returncode != 0:
            raise RuntimeError(f"ocrmypdf exited with code {completed.returncode}")
        if not output_pdf_path.exists():
            raise RuntimeError("ocrmypdf completed without producing output PDF")
        return OcrRunResult(output_pdf_path=output_pdf_path, report_path=report_path)
