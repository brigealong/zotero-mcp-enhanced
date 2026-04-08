from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "skills" / "zotero-note-writeback" / "scripts" / "writeback_from_search.py"


def load_module():
    spec = importlib.util.spec_from_file_location("writeback_from_search", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_payload() -> dict[str, object]:
    return {
        "title": "测试条目",
        "summary": "测试摘要",
        "focus": "测试焦点",
        "tags": ["test"],
        "locator": {
            "source_markdown_path": "C:/tmp/source.md",
            "attachment_type": "pdf",
        },
    }


def test_prepare_payload_for_writeback_merges_locator_context() -> None:
    module = load_module()
    payload = build_payload()

    prepared = module.prepare_payload_for_writeback(
        payload=payload,
        parent_item_key="ITEMFAK1",
        source_markdown_path="C:/tmp/source.md",
        locator_overrides={
            "attachment_key": "ATTFAK01",
            "library_scope": "library",
            "page": 24,
            "page_label": "24",
            "annotation_key": "ANNTEST1",
        },
    )

    assert prepared["target_item_key"] == "ITEMFAK1"
    assert prepared["locator"]["target_item_key"] == "ITEMFAK1"
    assert prepared["locator"]["source_markdown_path"] == "C:/tmp/source.md"
    assert prepared["locator"]["attachment_type"] == "pdf"
    assert prepared["locator"]["attachment_key"] == "ATTFAK01"
    assert prepared["locator"]["page"] == 24
    assert prepared["locator"]["page_label"] == "24"
    assert prepared["locator"]["annotation_key"] == "ANNTEST1"


def test_update_payload_file_persists_selected_item_and_locator(tmp_path: Path) -> None:
    module = load_module()
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(build_payload(), ensure_ascii=False, indent=2), encoding="utf-8")

    module.update_payload_file(
        payload_path=payload_path,
        parent_item_key="ITEMFAK1",
        source_markdown_path="C:/tmp/source.md",
        locator_overrides={
            "attachment_key": "ATTFAK01",
            "library_scope": "library",
            "page": 24,
        },
    )

    updated = json.loads(payload_path.read_text(encoding="utf-8"))
    assert updated["target_item_key"] == "ITEMFAK1"
    assert updated["locator"]["target_item_key"] == "ITEMFAK1"
    assert updated["locator"]["attachment_key"] == "ATTFAK01"
    assert updated["locator"]["page"] == 24


def test_build_locator_overrides_from_locator_json_and_args() -> None:
    module = load_module()
    args = SimpleNamespace(
        locator_json=json.dumps(
            {
                "attachment_key": "ATTJSON1",
                "annotation_key": "ANNJSON1",
                "page": 12,
                "page_label": "12",
            }
        ),
        locator_path=None,
        attachment_key="ARGKEY",
        attachment_type="pdf",
        library_scope="library",
        group_id=None,
        page=None,
        page_label=None,
        page_idx=None,
        chapter_hint=None,
        annotation_key=None,
    )

    locator = module.build_locator_overrides_from_args(args)

    assert locator["attachment_key"] == "ARGKEY"
    assert locator["annotation_key"] == "ANNJSON1"
    assert locator["page"] == 12
    assert locator["page_label"] == "12"
    assert locator["attachment_type"] == "pdf"


def test_build_locator_overrides_from_locator_path_extracts_nested_locator(tmp_path: Path) -> None:
    module = load_module()
    locator_path = tmp_path / "annotation-result.json"
    locator_path.write_text(
        json.dumps(
            {
                "annotationKey": "ANNFAK01",
                "locator": {
                    "attachment_key": "ATTFAK01",
                    "annotation_key": "ANNFAK01",
                    "page": 135,
                    "page_label": "135",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        locator_json=None,
        locator_path=str(locator_path),
        attachment_key=None,
        attachment_type=None,
        library_scope=None,
        group_id=None,
        page=None,
        page_label=None,
        page_idx=None,
        chapter_hint=None,
        annotation_key=None,
    )

    locator = module.build_locator_overrides_from_args(args)

    assert locator["attachment_key"] == "ATTFAK01"
    assert locator["annotation_key"] == "ANNFAK01"
    assert locator["page"] == 135


def test_build_command_env_forces_utf8_subprocess_io() -> None:
    module = load_module()

    env = module.build_command_env(data_dir=r"C:\Zotero")

    assert env["ZOT_DATA_DIR"] == r"C:\Zotero"
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"].lower() == "utf-8"


def test_search_candidates_runs_subprocess_with_utf8_decoding(monkeypatch) -> None:
    module = load_module()
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.search_candidates("公共领域") == []
    assert captured["encoding"].lower() == "utf-8"
    assert captured["errors"] == "replace"


def test_build_query_candidates_prioritizes_title_author_combo() -> None:
    module = load_module()

    queries = module.build_query_candidates(title="公共领域的结构转型", author="Habermas", raw_query=None)

    assert queries[0] == "公共领域的结构转型 Habermas"
    assert "公共领域的结构转型" in queries
    assert "Habermas" in queries
