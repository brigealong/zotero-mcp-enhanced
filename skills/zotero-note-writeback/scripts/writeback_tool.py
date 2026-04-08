import argparse
import html
import json
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode


DEFAULT_NOTE_GRANULARITY = "atomic"


def _escape(value):
    return html.escape(str(value), quote=True)


def _paragraph(label, content):
    return f"<p><strong>{_escape(label)}:</strong> {_escape(content)}</p>"


def _list(items):
    filtered = [item for item in items if item]
    if not filtered:
        filtered = [""]
    lis = "".join(f"<li>{_escape(item)}</li>" for item in filtered)
    return f"<ul>{lis}</ul>"


def _raw_list(items):
    filtered = [item for item in items if item]
    if not filtered:
        return ""
    lis = "".join(f"<li>{item}</li>" for item in filtered)
    return f"<ul>{lis}</ul>"


def _link(href, text):
    return f'<a href="{_escape(href)}">{_escape(text)}</a>'


def resolve_note_policy(payload):
    granularity = payload.get("note_granularity") or DEFAULT_NOTE_GRANULARITY
    focus = (payload.get("focus") or payload.get("summary") or "").strip()
    point_count_hint = payload.get("point_count_hint", 1)
    allow_multi_point = payload.get("allow_multi_point", False)
    return {
        "note_granularity": granularity,
        "focus": focus,
        "point_count_hint": point_count_hint,
        "allow_multi_point": allow_multi_point,
    }


def validate_note_payload(payload):
    policy = resolve_note_policy(payload)
    if policy["note_granularity"] == "atomic" and not policy["allow_multi_point"]:
        if policy["point_count_hint"] and int(policy["point_count_hint"]) > 1:
            raise ValueError("atomic note expected a single point, but payload declares multiple points")
    return policy


def build_item_uri(parent_item_key, locator):
    scope = locator.get("library_scope") or "library"
    if scope == "groups":
        group_id = locator.get("group_id")
        if not group_id:
            raise ValueError("group_id is required when library_scope=groups")
        return f"zotero://select/groups/{group_id}/items/{parent_item_key}"
    return f"zotero://select/library/items/{parent_item_key}"


def build_pdf_uri(locator):
    attachment_key = locator.get("attachment_key")
    page = locator.get("page", locator.get("page_number", locator.get("page_idx")))
    if not attachment_key or page in (None, ""):
        return None

    scope = locator.get("library_scope") or "library"
    if scope == "groups":
        group_id = locator.get("group_id")
        if not group_id:
            raise ValueError("group_id is required when library_scope=groups")
        base = f"zotero://open-pdf/groups/{group_id}/items/{attachment_key}"
    else:
        base = f"zotero://open-pdf/library/items/{attachment_key}"

    query = {"page": page}
    annotation_key = locator.get("annotation_key")
    if annotation_key:
        query["annotation"] = annotation_key
    return f"{base}?{urlencode(query)}"


def build_locator_links(parent_item_key, locator):
    item_link = _link(build_item_uri(parent_item_key, locator), "条目")
    pdf_uri = build_pdf_uri(locator)
    if not pdf_uri:
        return item_link, ""
    page_label = locator.get("page_label") or locator.get("page", locator.get("page_idx"))
    return item_link, _link(pdf_uri, f"PDF p.{page_label}")


def render_note(payload, *, parent_item_key=None):
    policy = validate_note_payload(payload)
    title = payload["title"]
    summary = payload["summary"]
    tags = payload.get("tags", [])
    source_quote = payload.get("source_quote", "")
    user_points = payload.get("user_points", {})
    ai_response = payload.get("ai_response", {})
    collaboration = payload.get("collaboration", {})
    locator = payload.get("locator", {})
    resolved_parent_item_key = parent_item_key or payload.get("target_item_key") or locator.get("target_item_key")

    page = locator.get("page", locator.get("page_idx"))
    locator_items = [
        f"来源文件：{locator.get('source_markdown_path', '')}",
        f"附件类型：{str(locator.get('attachment_type', '')).upper()}",
    ]
    if page is not None:
        locator_items.append(f"页码：{page}")
    if locator.get("chapter_hint"):
        locator_items.append(f"章节：{locator['chapter_hint']}")

    locator_links = []
    if resolved_parent_item_key:
        item_link, pdf_link = build_locator_links(resolved_parent_item_key, locator)
        locator_links.append(item_link)
        if pdf_link:
            locator_links.append(pdf_link)

    writeback_items = [
        f"写回时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"笔记粒度：{policy['note_granularity']}",
        "生成方式：Agent Workspace + zotero-cli-cc",
    ]

    parts = [
        f"<h1>{_escape(title)}</h1>",
        _paragraph("核心点", policy["focus"]),
        _paragraph("摘要", summary),
        _paragraph("标签", " ".join(f"#{tag}" for tag in tags) if tags else ""),
        _paragraph("原文摘录", f"“{source_quote}”" if source_quote else ""),
        "<h2>我的问题 / 想法</h2>",
        _list(
            user_points.get("questions", [])
            + user_points.get("judgments", [])
            + user_points.get("associations", [])
        ),
        "<h2>AI 回应</h2>",
        _list(
            [
                ai_response.get("translation", ""),
                ai_response.get("explanation", ""),
                ai_response.get("expansion", ""),
                ai_response.get("reply_to_user", ""),
            ]
        ),
        "<h2>协作结论</h2>",
        _list(
            [collaboration.get("current_conclusion", "")]
            + collaboration.get("open_questions", [])
            + collaboration.get("next_questions", [])
        ),
        "<h2>来源定位</h2>",
        _list(locator_items),
        _raw_list(locator_links),
        "<h2>写回信息</h2>",
        _list(writeback_items),
    ]
    return "\n".join(part for part in parts if part) + "\n"


def build_zot_command(parent_item_key, content):
    return ["zot", "note", parent_item_key, "--add", content]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("payload_path")
    parser.add_argument("parent_item_key")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = json.loads(Path(args.payload_path).read_text(encoding="utf-8-sig"))
    note = render_note(payload, parent_item_key=args.parent_item_key)

    if args.dry_run:
        print(note)
        return

    command = build_zot_command(args.parent_item_key, note)
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    if completed.stdout:
        print(completed.stdout)
    if completed.stderr:
        print(completed.stderr)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
