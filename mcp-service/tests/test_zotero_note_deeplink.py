from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "skills" / "zotero-note-writeback" / "scripts" / "writeback_tool.py"


def load_module():
    spec = importlib.util.spec_from_file_location("writeback_tool", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_payload(locator: dict[str, object]) -> dict[str, object]:
    return {
        "title": "测试笔记",
        "summary": "测试摘要",
        "focus": "测试焦点",
        "tags": ["test"],
        "source_quote": "原文",
        "user_points": {"questions": ["问题1"], "judgments": [], "associations": []},
        "ai_response": {"translation": "", "explanation": "解释", "expansion": "", "reply_to_user": ""},
        "collaboration": {"current_conclusion": "结论", "open_questions": [], "next_questions": []},
        "locator": locator,
    }


def test_render_note_includes_library_pdf_page_link() -> None:
    module = load_module()
    payload = build_payload(
        {
            "source_markdown_path": "C:/tmp/note.md",
            "attachment_type": "pdf",
            "attachment_key": "JZ8GNS66",
            "library_scope": "library",
            "page": 24,
        }
    )

    note = module.render_note(payload, parent_item_key="PL6M34V3")

    assert 'href="zotero://select/library/items/PL6M34V3"' in note
    assert 'href="zotero://open-pdf/library/items/JZ8GNS66?page=24"' in note
    assert ">PDF p.24<" in note


def test_render_note_upgrades_to_annotation_link_when_key_exists() -> None:
    module = load_module()
    payload = build_payload(
        {
            "source_markdown_path": "C:/tmp/note.md",
            "attachment_type": "pdf",
            "attachment_key": "JZ8GNS66",
            "library_scope": "library",
            "page": 24,
            "annotation_key": "ABCD1234",
        }
    )

    note = module.render_note(payload, parent_item_key="PL6M34V3")

    assert "annotation=ABCD1234" in note
    assert 'href="zotero://open-pdf/library/items/JZ8GNS66?page=24&amp;annotation=ABCD1234"' in note


def test_render_note_supports_group_library_links() -> None:
    module = load_module()
    payload = build_payload(
        {
            "source_markdown_path": "C:/tmp/note.md",
            "attachment_type": "pdf",
            "attachment_key": "JZ8GNS66",
            "library_scope": "groups",
            "group_id": "12345",
            "page": 8,
        }
    )

    note = module.render_note(payload, parent_item_key="PL6M34V3")

    assert 'href="zotero://select/groups/12345/items/PL6M34V3"' in note
    assert 'href="zotero://open-pdf/groups/12345/items/JZ8GNS66?page=8"' in note


def test_render_note_falls_back_to_item_link_without_page() -> None:
    module = load_module()
    payload = build_payload(
        {
            "source_markdown_path": "C:/tmp/note.md",
            "attachment_type": "pdf",
            "attachment_key": "JZ8GNS66",
            "library_scope": "library",
        }
    )

    note = module.render_note(payload, parent_item_key="PL6M34V3")

    assert 'href="zotero://select/library/items/PL6M34V3"' in note
    assert "zotero://open-pdf/" not in note
