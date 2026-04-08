import argparse
import copy
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_from_cache(cache_path, source_markdown_path):
    if not Path(cache_path).exists():
        return None
    records = _load_json(cache_path)
    for record in records:
        if record.get("source_markdown_path") == source_markdown_path:
            return record
    return None


def build_search_command(query, limit=5):
    return ["zot", "--json", "search", query, "--limit", str(limit)]


def build_query_candidates(title=None, author=None, raw_query=None):
    candidates = []
    seen = set()
    stopwords = {
        "and",
        "the",
        "with",
        "from",
        "into",
        "interview",
        "chapter",
        "part",
        "section",
        "note",
        "notes",
    }

    def add(value):
        value = (value or "").strip()
        if value and value not in seen:
            candidates.append(value)
            seen.add(value)

    if title and author:
        add(f"{title} {author}")
    add(title)
    add(raw_query)

    if title:
        words = [
            word
            for word in title.replace(":", " ").split()
            if len(word) > 3 and word.lower() not in stopwords
        ]
        if len(words) >= 2:
            add(" ".join(words[-2:]))
        if len(words) >= 3:
            add(" ".join(words[:3]))

    add(author)
    return candidates


def build_command_env(data_dir=None, library_id=None, api_key=None):
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if data_dir:
        env["ZOT_DATA_DIR"] = data_dir
    if library_id:
        env["ZOT_LIBRARY_ID"] = library_id
    if api_key:
        env["ZOT_API_KEY"] = api_key
    return env


def search_candidates(query, limit=5, data_dir=None):
    command = build_search_command(query, limit=limit)
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=build_command_env(data_dir),
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout or "zot search failed")
    return json.loads(completed.stdout)


def pick_first_non_empty_result(queries, search_fn):
    for query in queries:
        items = search_fn(query)
        if items:
            return query, items
    return None, []


def upsert_cache_record(cache_path, record):
    cache_file = Path(cache_path)
    if cache_file.exists():
        records = _load_json(cache_file)
    else:
        records = []

    updated = False
    for idx, existing in enumerate(records):
        if existing.get("source_markdown_path") == record.get("source_markdown_path"):
            merged = {**existing, **record}
            merged["updated_at"] = record.get("updated_at") or datetime.now().astimezone().isoformat(timespec="seconds")
            records[idx] = merged
            updated = True
            break

    if not updated:
        records.append(record)

    _write_json(cache_file, records)


def build_writeback_command(payload_path, parent_item_key, writeback_script):
    return ["python", writeback_script, payload_path, parent_item_key]


def _clean_mapping(values):
    cleaned = {}
    for key, value in (values or {}).items():
        if value in (None, ""):
            continue
        cleaned[key] = value
    return cleaned


def _load_locator_input(locator_json=None, locator_path=None):
    if locator_json and locator_path:
        raise ValueError("use either locator_json or locator_path, not both")
    if locator_json:
        return _clean_mapping(json.loads(locator_json))
    if locator_path:
        loaded = _load_json(locator_path)
        if "locator" in loaded and isinstance(loaded["locator"], dict):
            return _clean_mapping(loaded["locator"])
        return _clean_mapping(loaded)
    return {}


def build_locator_overrides_from_args(args):
    merged = _load_locator_input(
        locator_json=args.locator_json,
        locator_path=args.locator_path,
    )
    merged.update(
        _clean_mapping(
            {
                "attachment_key": args.attachment_key,
                "attachment_type": args.attachment_type,
                "library_scope": args.library_scope,
                "group_id": args.group_id,
                "page": args.page,
                "page_label": args.page_label,
                "page_idx": args.page_idx,
                "chapter_hint": args.chapter_hint,
                "annotation_key": args.annotation_key,
            }
        )
    )
    return merged


def prepare_payload_for_writeback(payload, parent_item_key, source_markdown_path, locator_overrides=None):
    prepared = copy.deepcopy(payload)
    locator = dict(prepared.get("locator") or {})
    locator["source_markdown_path"] = source_markdown_path
    locator["target_item_key"] = parent_item_key
    locator.update(_clean_mapping(locator_overrides))
    prepared["locator"] = locator
    prepared["target_item_key"] = parent_item_key
    return prepared


def update_payload_file(payload_path, parent_item_key, source_markdown_path, locator_overrides=None):
    payload_path = Path(payload_path)
    payload = _load_json(payload_path)
    updated = prepare_payload_for_writeback(
        payload=payload,
        parent_item_key=parent_item_key,
        source_markdown_path=source_markdown_path,
        locator_overrides=locator_overrides,
    )
    _write_json(payload_path, updated)
    return updated


def build_local_save_command(
    payload_path,
    output_path,
    local_save_script,
    parent_item_key=None,
    write_mode="both",
):
    command = ["python", local_save_script, payload_path, output_path]
    if parent_item_key:
        command.extend(["--parent-item-key", parent_item_key])
    if write_mode:
        command.extend(["--write-mode", write_mode])
    return command


def infer_task_root(source_markdown_path):
    parts = Path(str(source_markdown_path).replace("\\", "/")).parts
    for idx in range(len(parts) - 2):
        if parts[idx] == "tasks" and parts[idx + 1] == "active":
            return Path(*parts[: idx + 3])
    return None


def build_local_note_filename(title):
    value = (title or "").strip().lstrip("#").strip()
    value = re.sub(r'[<>:"/\\\\|?*]+', "-", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    value = value.strip("-. ")
    return f"{value or 'zotero-note'}.md"


def resolve_local_output_path(source_markdown_path, payload_path, local_output_path=None):
    if local_output_path:
        return Path(local_output_path)

    if not payload_path:
        raise SystemExit("could not infer local output path without payload_path")

    task_root = infer_task_root(source_markdown_path)
    if not task_root:
        raise SystemExit("could not infer local output path from source_markdown_path")

    payload = _load_json(payload_path)
    filename = build_local_note_filename(payload.get("title", ""))
    return task_root / "01-研究产出" / filename


def should_auto_select(candidates, auto_first):
    return auto_first and len(candidates) == 1


def run_writeback_command(command, data_dir=None, library_id=None, api_key=None):
    return subprocess.run(
        command,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=build_command_env(data_dir, library_id=library_id, api_key=api_key),
    )


def _require_local_save_args(args):
    missing = []
    if not args.payload_path:
        missing.append("payload_path")
    if not args.local_save_script:
        missing.append("local_save_script")
    if missing:
        raise SystemExit(f"missing local save arguments: {', '.join(missing)}")


def execute_write_actions(output, parent_item_key, args):
    output["write_mode"] = args.save_mode
    if args.payload_path:
        updated_payload = update_payload_file(
            payload_path=args.payload_path,
            parent_item_key=parent_item_key,
            source_markdown_path=args.source_markdown_path,
            locator_overrides=build_locator_overrides_from_args(args),
        )
        output["payload_updated"] = True
        output["target_item_key"] = updated_payload.get("target_item_key")
        output["payload_locator"] = updated_payload.get("locator", {})

    if args.save_mode in {"both", "local_only"}:
        _require_local_save_args(args)
        resolved_local_output_path = resolve_local_output_path(
            source_markdown_path=args.source_markdown_path,
            payload_path=args.payload_path,
            local_output_path=args.local_output_path,
        )
        output["local_output_path"] = str(resolved_local_output_path).replace("\\", "/")
        output["local_output_status"] = "pending"
        output["local_saved"] = False
        local_command = build_local_save_command(
            payload_path=args.payload_path,
            output_path=str(resolved_local_output_path).replace("\\", "/"),
            local_save_script=args.local_save_script,
            parent_item_key=parent_item_key,
            write_mode=args.save_mode,
        )
        output["local_save_command"] = local_command

        if args.run_writeback:
            completed = run_writeback_command(
                local_command,
                data_dir=args.data_dir,
                library_id=args.library_id,
                api_key=args.api_key,
            )
            output["local_save_stdout"] = completed.stdout
            output["local_save_stderr"] = completed.stderr
            output["local_save_returncode"] = completed.returncode
            if completed.returncode != 0:
                output["local_output_status"] = "failed"
                print(json.dumps(output, ensure_ascii=False, indent=2))
                raise SystemExit(completed.returncode)

            output["local_output_status"] = "saved"
            output["local_saved"] = True

    if args.save_mode == "local_only":
        return True

    if args.payload_path and args.writeback_script:
        command = build_writeback_command(args.payload_path, parent_item_key, args.writeback_script)
        output["writeback_command"] = command
        if args.run_writeback:
            completed = run_writeback_command(
                command,
                data_dir=args.data_dir,
                library_id=args.library_id,
                api_key=args.api_key,
            )
            output["writeback_stdout"] = completed.stdout
            output["writeback_stderr"] = completed.stderr
            output["writeback_returncode"] = completed.returncode
            if completed.returncode != 0:
                print(json.dumps(output, ensure_ascii=False, indent=2))
                raise SystemExit(completed.returncode)

    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_markdown_path")
    parser.add_argument("query")
    parser.add_argument("--cache-path", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--data-dir")
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument("--payload-path")
    parser.add_argument("--writeback-script")
    parser.add_argument("--auto-first", action="store_true")
    parser.add_argument("--run-writeback", action="store_true")
    parser.add_argument("--library-id")
    parser.add_argument("--api-key")
    parser.add_argument("--save-mode", choices=["zotero_only", "local_only", "both"], default="zotero_only")
    parser.add_argument("--local-output-path")
    parser.add_argument("--local-save-script")
    parser.add_argument("--attachment-key")
    parser.add_argument("--attachment-type")
    parser.add_argument("--library-scope")
    parser.add_argument("--group-id")
    parser.add_argument("--page", type=int)
    parser.add_argument("--page-label")
    parser.add_argument("--page-idx", type=int)
    parser.add_argument("--chapter-hint")
    parser.add_argument("--annotation-key")
    parser.add_argument("--locator-json")
    parser.add_argument("--locator-path")
    args = parser.parse_args()

    hit = resolve_from_cache(args.cache_path, args.source_markdown_path)
    if hit:
        output = {"mode": "cache", "record": hit}
        if args.payload_path and (args.writeback_script or args.save_mode in {"both", "local_only"}):
            execute_write_actions(output, hit["resolved_parent_item_key"], args)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    queries = build_query_candidates(title=args.title, author=args.author, raw_query=args.query)
    matched_query, candidates = pick_first_non_empty_result(
        queries,
        lambda q: search_candidates(q, limit=args.limit, data_dir=args.data_dir),
    )
    output = {"mode": "search", "matched_query": matched_query, "candidates": candidates, "tried_queries": queries}

    if should_auto_select(candidates, args.auto_first):
        chosen = candidates[0]
        cache_record = {
            "source_markdown_path": args.source_markdown_path,
            "resolved_parent_item_key": chosen["key"],
            "title_hint": chosen.get("title", ""),
            "matched_query": matched_query,
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        output["selected"] = cache_record

        if args.payload_path and (args.writeback_script or args.save_mode in {"both", "local_only"}):
            execute_write_actions(output, chosen["key"], args)
            upsert_cache_record(args.cache_path, cache_record)
        else:
            upsert_cache_record(args.cache_path, cache_record)
    elif args.auto_first and len(candidates) > 1:
        output["selection_skipped"] = "multiple-candidates"

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
