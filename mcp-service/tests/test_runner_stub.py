from pathlib import Path

from abbyy_mcp.runner import StubOcrRunner


def test_stub_runner_copies_input_to_output(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "output-searchable.pdf"
    report = tmp_path / "report.txt"
    source.write_bytes(b"%PDF-1.4\nstub")

    result = StubOcrRunner().run(
        source_pdf_path=source,
        output_pdf_path=output,
        report_path=report,
    )

    assert output.read_bytes() == source.read_bytes()
    assert report.exists()
    assert result.output_pdf_path == output
    assert result.report_path == report
