import argparse
import importlib.util
import json
from datetime import datetime
from pathlib import Path


_WRITEBACK_SEARCH_PATH = Path(__file__).resolve().parent / "writeback_from_search.py"
_SPEC = importlib.util.spec_from_file_location("writeback_from_search", _WRITEBACK_SEARCH_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)

build_query_candidates = _MODULE.build_query_candidates
pick_first_non_empty_result = _MODULE.pick_first_non_empty_result
search_candidates = _MODULE.search_candidates


def load_fixtures(fixtures_path):
    return json.loads(Path(fixtures_path).read_text(encoding="utf-8"))


def infer_search_mode(fixture, matched_query, candidates):
    if not candidates:
        return "conservative-failure"
    title_hint = fixture.get("title_hint")
    raw_query = fixture.get("raw_query")
    if matched_query and raw_query and matched_query == raw_query:
        return "exact"
    if matched_query and title_hint and matched_query == title_hint:
        if raw_query and raw_query != title_hint:
            return "cascade"
        return "exact"
    return "cascade"


def evaluate_fixture(fixture, resolver):
    queries = build_query_candidates(
        title=fixture.get("title_hint"),
        author=fixture.get("author_hint"),
        raw_query=fixture.get("raw_query"),
    )
    matched_query, candidates = resolver(queries)
    resolved_parent_item_key = candidates[0]["key"] if candidates else None
    should_writeback = bool(candidates)
    expected_key = fixture.get("expected_parent_item_key")
    expected_should_writeback = fixture.get("expected_should_writeback")
    expected_matched_query = fixture.get("expected_matched_query")
    expected_search_mode = fixture.get("expected_search_mode")
    observed_search_mode = infer_search_mode(fixture, matched_query, candidates)

    passed = (
        resolved_parent_item_key == expected_key
        and should_writeback == expected_should_writeback
        and (expected_matched_query is None or matched_query == expected_matched_query)
        and (expected_search_mode is None or observed_search_mode == expected_search_mode)
    )

    return {
        "fixture_id": fixture.get("fixture_id"),
        "source_markdown_path": fixture.get("source_markdown_path"),
        "title_hint": fixture.get("title_hint"),
        "author_hint": fixture.get("author_hint"),
        "raw_query": fixture.get("raw_query"),
        "tried_queries": queries,
        "matched_query": matched_query,
        "resolved_parent_item_key": resolved_parent_item_key,
        "should_writeback": should_writeback,
        "expected_parent_item_key": expected_key,
        "expected_should_writeback": expected_should_writeback,
        "expected_matched_query": expected_matched_query,
        "expected_search_mode": expected_search_mode,
        "observed_search_mode": observed_search_mode,
        "status": "pass" if passed else "fail",
    }


def run_fixtures(fixtures, resolver):
    return [evaluate_fixture(fixture, resolver) for fixture in fixtures]


def build_summary(results):
    passed = sum(1 for result in results if result["status"] == "pass")
    failed = len(results) - passed
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
    }


def save_report(report_path, results, summary=None):
    data = results
    if summary is not None:
        data = {
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "summary": summary,
            "results": results,
        }
    Path(report_path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def resolve_live_queries(queries, data_dir=None, limit=5):
    return pick_first_non_empty_result(
        queries,
        lambda query: search_candidates(query, limit=limit, data_dir=data_dir),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fixtures_path")
    parser.add_argument("report_path")
    parser.add_argument("--data-dir")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    fixtures = load_fixtures(args.fixtures_path)
    results = run_fixtures(
        fixtures,
        lambda queries: resolve_live_queries(queries, data_dir=args.data_dir, limit=args.limit),
    )
    save_report(args.report_path, results, summary=build_summary(results))


if __name__ == "__main__":
    main()
