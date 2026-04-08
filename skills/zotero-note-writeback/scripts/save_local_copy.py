import argparse
import json
from datetime import datetime
from pathlib import Path


DEFAULT_NOTE_GRANULARITY = "atomic"


def _string_list(items):
    return [str(item).strip() for item in items if str(item).strip()]


def _section(title, items):
    lines = [f"## {title}", ""]
    values = _string_list(items)
    if not values:
        lines.append("-")
    else:
        lines.extend(f"- {item}" for item in values)
    lines.append("")
    return lines


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


def render_local_note(
    payload,
    parent_item_key="",
    local_output_path="",
    write_mode="both",
    written_at=None,
):
    policy = resolve_note_policy(payload)
    written_at = written_at or datetime.now().astimezone().isoformat(timespec="seconds")
    title = payload["title"].strip()
    summary = payload["summary"].strip()
    tags = " ".join(f"#{tag}" for tag in payload.get("tags", []) if str(tag).strip())

    user_points = payload.get("user_points", {})
    ai_response = payload.get("ai_response", {})
    collaboration = payload.get("collaboration", {})
    locator = payload.get("locator", {})

    lines = [
        f"# {title}",
        "",
        f"核心点：{policy['focus']}",
        f"摘要：{summary}",
        f"标签：{tags}".rstrip(),
        "",
        "## 原文摘录",
        "",
        payload.get("source_quote", "").strip() or "-",
        "",
    ]

    lines.extend(
        _section(
            "我的问题 / 想法",
            user_points.get("questions", [])
            + user_points.get("judgments", [])
            + user_points.get("associations", []),
        )
    )
    lines.extend(
        _section(
            "AI 回应",
            [
                ai_response.get("translation", ""),
                ai_response.get("explanation", ""),
                ai_response.get("expansion", ""),
                ai_response.get("reply_to_user", ""),
            ],
        )
    )
    lines.extend(
        _section(
            "协作结论",
            [collaboration.get("current_conclusion", "")]
            + collaboration.get("open_questions", [])
            + collaboration.get("next_questions", []),
        )
    )
    lines.extend(
        _section(
            "来源定位",
            [
                f"source_markdown_path: {locator.get('source_markdown_path', '')}",
                f"attachment_type: {str(locator.get('attachment_type', '')).upper()}",
                f"page_idx: {locator['page_idx']}" if locator.get("page_idx") is not None else "",
                f"chapter_hint: {locator.get('chapter_hint', '')}",
                f"zotero_parent_item_key: {parent_item_key}" if parent_item_key else "",
            ],
        )
    )
    lines.extend(
        _section(
            "写回信息",
            [
                f"write_mode: {write_mode}",
                f"note_granularity: {policy['note_granularity']}",
                f"local_output_path: {local_output_path}" if local_output_path else "",
                f"written_at: {written_at}",
                "generated_by: Agent Workspace + zotero-cli-cc",
            ],
        )
    )

    return "\n".join(lines).rstrip() + "\n"


def save_local_copy(
    payload_path,
    output_path,
    parent_item_key="",
    write_mode="both",
    written_at=None,
):
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8-sig"))
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    content = render_local_note(
        payload,
        parent_item_key=parent_item_key,
        local_output_path=str(output_file),
        write_mode=write_mode,
        written_at=written_at,
    )
    output_file.write_text(content, encoding="utf-8")
    return output_file


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("payload_path")
    parser.add_argument("output_path")
    parser.add_argument("--parent-item-key", default="")
    parser.add_argument("--write-mode", default="both")
    args = parser.parse_args()

    output_file = save_local_copy(
        payload_path=args.payload_path,
        output_path=args.output_path,
        parent_item_key=args.parent_item_key,
        write_mode=args.write_mode,
    )
    print(str(output_file))


if __name__ == "__main__":
    main()
