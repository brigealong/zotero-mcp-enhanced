from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class OcrRunResult:
    output_pdf_path: Path
    report_path: Path


class OcrRunner(Protocol):
    def run(
        self,
        *,
        source_pdf_path: Path,
        output_pdf_path: Path,
        report_path: Path,
        timeout_seconds: int | None = None,
    ) -> OcrRunResult:
        ...


class StubOcrRunner:
    def run(
        self,
        *,
        source_pdf_path: Path,
        output_pdf_path: Path,
        report_path: Path,
        timeout_seconds: int | None = None,
    ) -> OcrRunResult:
        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_pdf_path, output_pdf_path)
        report_path.write_text("stub runner completed\n", encoding="utf-8")
        return OcrRunResult(output_pdf_path=output_pdf_path, report_path=report_path)
