from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "create_zotero_annotation.py"


def load_module():
    spec = importlib.util.spec_from_file_location("create_zotero_annotation", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_note_anchor_position_uses_page_number() -> None:
    module = load_module()

    position = module.build_note_anchor_position(page=24)

    assert position["pageIndex"] == 23
    assert position["rects"] == [[16, 740, 36, 760]]


def test_build_annotation_request_defaults_to_note_anchor() -> None:
    module = load_module()

    request = module.build_annotation_request(
        attachment_key="ATTFAK01",
        page=24,
        comment="自动创建的 annotation 锚点",
    )

    assert request["action"] == "createAnnotation"
    assert request["item_key"] == "ATTFAK01"
    assert request["annotation_type"] == "note"
    assert request["page"] == 24
    assert request["page_label"] == "24"
    assert request["comment"] == "自动创建的 annotation 锚点"
    assert request["position"]["pageIndex"] == 23
