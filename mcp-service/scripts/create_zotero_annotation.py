from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BRIDGE_PATH = REPO_ROOT / "skills" / "zotero-workflow-orchestrator" / "scripts" / "local_writer_bridge.py"
DEFAULT_NOTE_RECT = [16, 740, 36, 760]


def resolve_bridge_path() -> Path:
    configured = os.environ.get("ZOTERO_BRIDGE_PATH")
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_BRIDGE_PATH


def load_bridge_module():
    bridge_path = resolve_bridge_path()
    spec = importlib.util.spec_from_file_location("local_writer_bridge", bridge_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load bridge module: {bridge_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_note_anchor_position(page: int, rect: list[float] | None = None) -> dict[str, object]:
    if page < 1:
        raise ValueError("page must be >= 1")
    return {
        "pageIndex": page - 1,
        "rects": [rect or list(DEFAULT_NOTE_RECT)],
    }


def build_annotation_request(
    *,
    attachment_key: str,
    page: int,
    comment: str,
    annotation_type: str = "note",
    page_label: str | None = None,
    text: str | None = None,
    color: str | None = None,
    position: dict[str, object] | None = None,
    annotation_key: str | None = None,
    sort_index: str | None = None,
    library_id: int = 1,
    is_external: bool = False,
) -> dict[str, object]:
    if not attachment_key:
        raise ValueError("attachment_key is required")
    if page < 1:
        raise ValueError("page must be >= 1")

    return {
        "action": "createAnnotation",
        "library_id": library_id,
        "item_key": attachment_key,
        "annotation_key": annotation_key,
        "annotation_type": annotation_type,
        "page": page,
        "page_label": page_label or str(page),
        "comment": comment,
        "text": text,
        "color": color,
        "sort_index": sort_index,
        "position": position or build_note_anchor_position(page),
        "is_external": is_external,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Create a Zotero annotation through the local writer bridge.")
    parser.add_argument("attachment_key")
    parser.add_argument("page", type=int)
    parser.add_argument("--comment", default="")
    parser.add_argument("--annotation-type", default="note")
    parser.add_argument("--page-label")
    parser.add_argument("--text")
    parser.add_argument("--color")
    parser.add_argument("--annotation-key")
    parser.add_argument("--sort-index")
    parser.add_argument("--position-json")
    parser.add_argument("--result-path")
    parser.add_argument("--library-id", type=int, default=1)
    parser.add_argument("--working-dir")
    parser.add_argument("--timeout-sec", type=int, default=30)
    parser.add_argument("--poll-interval-ms", type=int, default=500)
    parser.add_argument("--is-external", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    bridge = load_bridge_module()
    position = json.loads(args.position_json) if args.position_json else None
    request = build_annotation_request(
        attachment_key=args.attachment_key,
        page=args.page,
        comment=args.comment,
        annotation_type=args.annotation_type,
        page_label=args.page_label,
        text=args.text,
        color=args.color,
        position=position,
        annotation_key=args.annotation_key,
        sort_index=args.sort_index,
        library_id=args.library_id,
        is_external=args.is_external,
    )

    result = bridge.run_bridge(
        action=request["action"],
        working_dir=args.working_dir or bridge.DEFAULT_WORKING_DIR,
        timeout_sec=args.timeout_sec,
        poll_interval_ms=args.poll_interval_ms,
        library_id=request["library_id"],
        item_key=request["item_key"],
        annotation_key=request["annotation_key"],
        annotation_type=request["annotation_type"],
        page=request["page"],
        page_label=request["page_label"],
        comment=request["comment"],
        text=request["text"],
        color=request["color"],
        sort_index=request["sort_index"],
        position=request["position"],
        is_external=request["is_external"],
    )

    if args.result_path:
        result_path = Path(args.result_path)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
