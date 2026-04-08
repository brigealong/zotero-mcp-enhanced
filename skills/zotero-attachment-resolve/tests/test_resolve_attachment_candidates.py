import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "resolve_attachment_candidates.py"
)
SPEC = importlib.util.spec_from_file_location(
    "resolve_attachment_candidates",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_doi_match_ranks_above_title_only_match(tmp_path):
    strong = tmp_path / "Attention-Is-All-You-Need-10.5555-attention.pdf"
    strong.write_text("pdf", encoding="utf-8")
    weak = tmp_path / "Attention-Is-All-You-Need-notes.pdf"
    weak.write_text("pdf", encoding="utf-8")

    results = MODULE.resolve_candidates(
        title="Attention Is All You Need",
        creators=[],
        doi="10.5555/attention",
        isbn="",
        search_roots=[tmp_path],
        limit=5,
    )

    assert results
    assert results[0]["path"] == str(strong)
    assert any("doi-exact" in evidence for evidence in results[0]["evidence"])


def test_title_and_creator_tokens_drive_filename_matching(tmp_path):
    match = tmp_path / "Carl-Schmitt-The-Crisis-of-Parliamentary-Democracy.epub"
    match.write_text("epub", encoding="utf-8")
    other = tmp_path / "Random-Notes-on-Democracy.pdf"
    other.write_text("pdf", encoding="utf-8")

    results = MODULE.resolve_candidates(
        title="The Crisis of Parliamentary Democracy",
        creators=["Carl Schmitt"],
        doi="",
        isbn="",
        search_roots=[tmp_path],
        limit=5,
    )

    assert results
    assert results[0]["path"] == str(match)
    assert any("title-token-overlap" in evidence for evidence in results[0]["evidence"])
    assert any("creator-token-overlap" in evidence for evidence in results[0]["evidence"])


def test_default_search_root_uses_downloads_folder(monkeypatch, tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    candidate = downloads / "9780262632492-the-crisis.pdf"
    candidate.write_text("pdf", encoding="utf-8")

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    results = MODULE.resolve_candidates(
        title="",
        creators=[],
        doi="",
        isbn="9780262632492",
        search_roots=None,
        limit=5,
    )

    assert results
    assert results[0]["path"] == str(candidate)
    assert any("isbn-exact" in evidence for evidence in results[0]["evidence"])
