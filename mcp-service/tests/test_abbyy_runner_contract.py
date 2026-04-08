from pathlib import Path

from abbyy_mcp.abbyy_runner import FineCmdRunner


def test_finecmd_runner_builds_expected_command(tmp_path: Path) -> None:
    runner = FineCmdRunner(finecmd_path=Path("C:/ABBYY/FineCmd.exe"))

    command = runner.build_command(
        source_pdf_path=Path("C:/input/sample.pdf"),
        output_pdf_path=tmp_path / "out.pdf",
        report_path=tmp_path / "report.txt",
    )

    assert command == [
        "C:/ABBYY/FineCmd.exe",
        "C:/input/sample.pdf",
        "/out",
        str(tmp_path / "out.pdf"),
        "/report",
        str(tmp_path / "report.txt"),
    ]
