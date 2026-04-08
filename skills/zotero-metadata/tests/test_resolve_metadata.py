import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "resolve_metadata.py"
SPEC = importlib.util.spec_from_file_location("resolve_metadata", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_remote_doi_resolution_prefers_exact_lookup(monkeypatch):
    monkeypatch.setattr(
        MODULE,
        "resolve_doi_candidates",
        lambda doi: [{"title": "Attention Is All You Need", "doi": doi, "source": "crossref"}],
    )
    result = MODULE.resolve_remote_candidates(title=None, author=None, doi="10.5555/attention", isbn=None, limit=5)
    assert result == [{"title": "Attention Is All You Need", "doi": "10.5555/attention", "source": "crossref"}]


def test_local_attachment_resolution_routes_to_local_extractor(monkeypatch, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(
        MODULE,
        "extract_local_candidates",
        lambda path: [{"title": "Local Candidate", "source_id": str(path)}],
    )
    result = MODULE.extract_local_candidates(pdf_path)
    assert result == [{"title": "Local Candidate", "source_id": str(pdf_path)}]


def test_parse_title_author_from_filename():
    title, authors, evidence = MODULE.parse_title_author_from_filename(Path("Vaswani - Attention Is All You Need.pdf"))
    assert title == "Attention Is All You Need"
    assert authors == ["Vaswani"]
    assert "filename:author-title" in evidence
