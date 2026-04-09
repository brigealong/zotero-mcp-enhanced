from pathlib import Path

import os

from zotero_mcp_enhanced_service.ocrmypdf_runner import OcrmypdfRunner


def test_ocrmypdf_runner_builds_expected_command(tmp_path: Path) -> None:
    runner = OcrmypdfRunner(ocrmypdf_path=Path("C:/example-tools/ocrmypdf.exe"))

    command = runner.build_command(
        source_pdf_path=Path("C:/example-input/sample.pdf"),
        output_pdf_path=tmp_path / "out.pdf",
        report_path=tmp_path / "report.txt",
    )

    assert command == [
        "C:/example-tools/ocrmypdf.exe",
        "--optimize",
        "0",
        "--output-type",
        "pdf",
        "--sidecar",
        str(tmp_path / "report.txt"),
        "C:/example-input/sample.pdf",
        str(tmp_path / "out.pdf"),
    ]


def test_ocrmypdf_runner_builds_env_with_tool_directories(monkeypatch) -> None:
    monkeypatch.setenv("PATH", r"C:\Windows\System32")
    runner = OcrmypdfRunner(ocrmypdf_path=Path(r"C:\Tools\OCRmyPDF\ocrmypdf.exe"))

    env = runner.build_env()

    assert r"C:\Tools\OCRmyPDF" in env["PATH"]
    assert r"C:\Program Files\Tesseract-OCR" in env["PATH"]
