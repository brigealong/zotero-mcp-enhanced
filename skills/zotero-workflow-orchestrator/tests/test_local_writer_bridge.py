import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "local_writer_bridge.py"
)
SPEC = importlib.util.spec_from_file_location("local_writer_bridge", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_build_import_payload_includes_required_fields(tmp_path):
    result_path = tmp_path / "result.json"

    payload = MODULE.build_payload(
        action="importStoredAttachment",
        result_path=result_path,
        parent_key="PARENT123",
        file_path=Path(r"C:\tmp\paper.pdf"),
        file_base_name="paper",
    )

    assert payload["action"] == "importStoredAttachment"
    assert payload["parentKey"] == "PARENT123"
    assert payload["filePath"] == str(Path(r"C:\tmp\paper.pdf"))
    assert payload["fileBaseName"] == "paper"
    assert payload["resultPath"] == str(result_path)


def test_build_trash_attachment_payload_requires_item_key(tmp_path):
    result_path = tmp_path / "result.json"

    payload = MODULE.build_payload(
        action="trashAttachment",
        result_path=result_path,
        item_key="ATTACH123",
    )

    assert payload["action"] == "trashAttachment"
    assert payload["itemKey"] == "ATTACH123"


def test_bridge_roundtrip_writes_command_and_reads_result(tmp_path, monkeypatch):
    working_dir = tmp_path / "bridge"
    request_id = "req-123"
    command_files = []

    monkeypatch.setattr(MODULE.uuid, "uuid4", lambda: request_id)

    def fake_wait_for_result(result_path, timeout_sec, poll_interval_ms):
        command_files.extend((working_dir / "commands").glob("command-*.json"))
        result_payload = {
            "requestID": request_id,
            "status": "success",
            "action": "trashAttachment",
            "itemKey": "ATTACH123",
        }
        result_path.write_text(json.dumps(result_payload), encoding="utf-8")
        return result_payload

    monkeypatch.setattr(MODULE, "wait_for_result", fake_wait_for_result)

    result = MODULE.run_bridge(
        action="trashAttachment",
        working_dir=working_dir,
        item_key="ATTACH123",
    )

    assert result["status"] == "success"
    assert result["itemKey"] == "ATTACH123"
    assert len(command_files) == 1
    command_payload = json.loads(command_files[0].read_text(encoding="utf-8"))
    assert command_payload["action"] == "trashAttachment"
    assert command_payload["itemKey"] == "ATTACH123"


def test_build_payload_rejects_missing_import_fields(tmp_path):
    result_path = tmp_path / "result.json"

    with pytest.raises(ValueError, match="parent_key"):
        MODULE.build_payload(
            action="importStoredAttachment",
            result_path=result_path,
            file_path=Path(r"C:\tmp\paper.pdf"),
            file_base_name="paper",
        )


def test_build_create_annotation_payload_includes_minimal_fields(tmp_path):
    result_path = tmp_path / "result.json"

    payload = MODULE.build_payload(
        action="createAnnotation",
        result_path=result_path,
        item_key="ATTACH123",
        annotation_type="note",
        page=24,
        comment="自动创建的锚点 annotation",
        position={
            "pageIndex": 23,
            "rects": [[16, 760, 36, 780]],
        },
    )

    assert payload["action"] == "createAnnotation"
    assert payload["itemKey"] == "ATTACH123"
    assert payload["annotationType"] == "note"
    assert payload["page"] == 24
    assert payload["comment"] == "自动创建的锚点 annotation"
    assert payload["position"]["pageIndex"] == 23


def test_build_create_annotation_payload_requires_annotation_type(tmp_path):
    result_path = tmp_path / "result.json"

    with pytest.raises(ValueError, match="annotation_type"):
        MODULE.build_payload(
            action="createAnnotation",
            result_path=result_path,
            item_key="ATTACH123",
            page=24,
            position={
                "pageIndex": 23,
                "rects": [[16, 760, 36, 780]],
            },
        )
