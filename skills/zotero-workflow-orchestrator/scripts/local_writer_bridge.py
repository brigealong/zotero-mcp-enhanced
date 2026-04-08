import argparse
import json
import os
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path


def resolve_default_working_dir() -> Path:
    configured = os.environ.get("ZOTERO_MCP_QUEUE_DIR") or os.environ.get("ZOTERO_PLUGIN_QUEUE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path(tempfile.gettempdir()) / "zotero-mcp-enhanced"


DEFAULT_WORKING_DIR = resolve_default_working_dir()
SUPPORTED_ACTIONS = {
    "importStoredAttachment",
    "trashAttachment",
    "trashRegularItem",
    "createAnnotation",
}


def build_payload(
    *,
    action,
    result_path,
    library_id=1,
    alert_on_success=False,
    alert_on_error=False,
    parent_key=None,
    file_path=None,
    file_base_name=None,
    item_key=None,
    annotation_key=None,
    annotation_type=None,
    page=None,
    page_label=None,
    comment=None,
    text=None,
    color=None,
    sort_index=None,
    position=None,
    is_external=False,
):
    if action not in SUPPORTED_ACTIONS:
        raise ValueError(f"Unsupported action: {action}")

    payload = {
        "action": action,
        "requestID": str(uuid.uuid4()),
        "libraryID": library_id,
        "resultPath": str(Path(result_path)),
        "alertOnSuccess": bool(alert_on_success),
        "alertOnError": bool(alert_on_error),
    }

    if action == "importStoredAttachment":
        if not parent_key:
            raise ValueError("parent_key is required for importStoredAttachment")
        if not file_path:
            raise ValueError("file_path is required for importStoredAttachment")
        if not file_base_name:
            raise ValueError("file_base_name is required for importStoredAttachment")
        payload["parentKey"] = parent_key
        payload["filePath"] = str(Path(file_path))
        payload["fileBaseName"] = file_base_name
        return payload

    if action == "createAnnotation":
        if not item_key:
            raise ValueError("item_key is required for createAnnotation")
        if not annotation_type:
            raise ValueError("annotation_type is required for createAnnotation")
        if not position:
            raise ValueError("position is required for createAnnotation")
        payload["itemKey"] = item_key
        payload["annotationType"] = annotation_type
        payload["position"] = position
        payload["isExternal"] = bool(is_external)
        if annotation_key:
            payload["annotationKey"] = annotation_key
        if page is not None:
            payload["page"] = int(page)
        if page_label:
            payload["pageLabel"] = page_label
        if comment is not None:
            payload["comment"] = comment
        if text is not None:
            payload["text"] = text
        if color is not None:
            payload["color"] = color
        if sort_index is not None:
            payload["sortIndex"] = sort_index
        return payload

    if not item_key:
        raise ValueError(f"item_key is required for {action}")
    payload["itemKey"] = item_key
    return payload


def write_command(command_path, payload):
    command_path = Path(command_path)
    command_path.parent.mkdir(parents=True, exist_ok=True)
    command_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return command_path


def wait_for_result(result_path, timeout_sec=30, poll_interval_ms=500):
    result_path = Path(result_path)
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            status = result.get("status")
            if status in {"success", "error"}:
                return result
        time.sleep(poll_interval_ms / 1000)
    raise TimeoutError(
        f"Timed out waiting for stored attachment result. resultPath={result_path}"
    )


def run_bridge(
    *,
    action,
    working_dir=DEFAULT_WORKING_DIR,
    timeout_sec=30,
    poll_interval_ms=500,
    library_id=1,
    alert_on_success=False,
    alert_on_error=False,
    parent_key=None,
    file_path=None,
    file_base_name=None,
    item_key=None,
    annotation_key=None,
    annotation_type=None,
    page=None,
    page_label=None,
    comment=None,
    text=None,
    color=None,
    sort_index=None,
    position=None,
    is_external=False,
):
    working_dir = Path(working_dir)
    commands_dir = working_dir / "commands"
    results_dir = working_dir / "results"
    commands_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    request_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    result_path = results_dir / f"result-{request_id}.json"
    payload = build_payload(
        action=action,
        result_path=result_path,
        library_id=library_id,
        alert_on_success=alert_on_success,
        alert_on_error=alert_on_error,
        parent_key=parent_key,
        file_path=file_path,
        file_base_name=file_base_name,
        item_key=item_key,
        annotation_key=annotation_key,
        annotation_type=annotation_type,
        page=page,
        page_label=page_label,
        comment=comment,
        text=text,
        color=color,
        sort_index=sort_index,
        position=position,
        is_external=is_external,
    )
    payload["requestID"] = request_id

    command_path = commands_dir / f"command-{timestamp}-{request_id}.json"
    write_command(command_path, payload)
    result = wait_for_result(
        result_path=result_path,
        timeout_sec=timeout_sec,
        poll_interval_ms=poll_interval_ms,
    )
    if result.get("status") == "error":
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Bridge validated local Zotero write actions through the installed plugin queue."
    )
    parser.add_argument("action", choices=sorted(SUPPORTED_ACTIONS))
    parser.add_argument("--working-dir", default=str(DEFAULT_WORKING_DIR))
    parser.add_argument("--timeout-sec", type=int, default=30)
    parser.add_argument("--poll-interval-ms", type=int, default=500)
    parser.add_argument("--library-id", type=int, default=1)
    parser.add_argument("--alert-on-success", action="store_true")
    parser.add_argument("--alert-on-error", action="store_true")
    parser.add_argument("--parent-key")
    parser.add_argument("--file-path")
    parser.add_argument("--file-base-name")
    parser.add_argument("--item-key")
    parser.add_argument("--annotation-key")
    parser.add_argument("--annotation-type")
    parser.add_argument("--page", type=int)
    parser.add_argument("--page-label")
    parser.add_argument("--comment")
    parser.add_argument("--text")
    parser.add_argument("--color")
    parser.add_argument("--sort-index")
    parser.add_argument("--position-json")
    parser.add_argument("--is-external", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    result = run_bridge(
        action=args.action,
        working_dir=args.working_dir,
        timeout_sec=args.timeout_sec,
        poll_interval_ms=args.poll_interval_ms,
        library_id=args.library_id,
        alert_on_success=args.alert_on_success,
        alert_on_error=args.alert_on_error,
        parent_key=args.parent_key,
        file_path=args.file_path,
        file_base_name=args.file_base_name,
        item_key=args.item_key,
        annotation_key=args.annotation_key,
        annotation_type=args.annotation_type,
        page=args.page,
        page_label=args.page_label,
        comment=args.comment,
        text=args.text,
        color=args.color,
        sort_index=args.sort_index,
        position=json.loads(args.position_json) if args.position_json else None,
        is_external=args.is_external,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
