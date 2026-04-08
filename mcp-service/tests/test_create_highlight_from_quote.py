from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "create_highlight_from_quote.py"


def load_module():
    spec = importlib.util.spec_from_file_location("create_highlight_from_quote", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakePage:
    def __init__(self, responses: dict[str, list[tuple[int, int, int, int]]]):
        self.responses = responses
        self.calls: list[str] = []

    def search_for(self, query: str):
        self.calls.append(query)
        return self.responses.get(query, [])


def test_build_quote_search_variants_collapse_whitespace() -> None:
    module = load_module()
    quote = "人们经常听到  一个指责\n说罗马天主教政治不过是彻头彻尾的机会主义。"

    variants = module.build_quote_search_variants(quote)

    assert variants[0] == quote
    assert "人们经常听到 一个指责 说罗马天主教政治不过是彻头彻尾的机会主义。" in variants
    assert "人们经常听到一个指责说罗马天主教政治不过是彻头彻尾的机会主义。" in variants


def test_locate_quote_on_page_prefers_exact_match() -> None:
    module = load_module()
    quote = "19世纪是议会和民主的时代。在这整个时期,人们经常听到 一个指责,说罗马天主教政治不过是彻头彻尾的机会主义。"
    page = FakePage({quote: [(1, 2, 3, 4), (5, 6, 7, 8)]})

    match = module.locate_quote_on_page(page, quote)

    assert match is not None
    assert match["strategy"] == "exact"
    assert match["rects"] == [(1, 2, 3, 4), (5, 6, 7, 8)]


def test_locate_quote_on_page_falls_back_to_fragments() -> None:
    module = load_module()
    quote = "19世纪是议会和民主的时代。在这整个时期,人们经常听到 一个指责,说罗马天主教政治不过是彻头彻尾的机会主义。"
    page = FakePage(
        {
            "19世纪是议会和民主的时代": [(1, 2, 3, 4)],
            "在这整个时期,人们经常听到": [(5, 6, 7, 8)],
            "一个指责,说罗马天主教政治不过是彻头彻尾的机会主义": [(9, 10, 11, 12)],
        }
    )

    match = module.locate_quote_on_page(page, quote)

    assert match is not None
    assert match["strategy"] == "fragments"
    assert match["rects"] == [(1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12)]


def test_build_highlight_annotation_request_uses_quote_text() -> None:
    module = load_module()

    request = module.build_highlight_annotation_request(
        attachment_key="JZ8GNS66",
        page_number=87,
        quote="19世纪是议会和民主的时代。",
        rects=[(1, 2, 3, 4)],
        comment="测试高亮",
    )

    assert request["annotation_type"] == "highlight"
    assert request["page"] == 87
    assert request["text"] == "19世纪是议会和民主的时代。"
    assert request["comment"] == "测试高亮"
    assert request["position"]["pageIndex"] == 86
    assert request["position"]["rects"] == [[1, 2, 3, 4]]


def test_normalize_for_match_unifies_whitespace_and_commas() -> None:
    module = load_module()

    normalized = module.normalize_for_match(
        "在这整个时期, 人们经常听到\n一个指责，说罗马天主教政治不过是彻头彻尾的机会主义。"
    )

    assert normalized == "在这整个时期人们经常听到一个指责说罗马天主教政治不过是彻头彻尾的机会主义。"


def test_locate_quote_in_word_rows_merges_multiline_rects() -> None:
    module = load_module()
    rows = [
        {
            "page_num": "87",
            "par_num": "7",
            "block_num": "0",
            "line_num": "0",
            "word_num": "0",
            "left": "141.50",
            "top": "324.86",
            "width": "16.08",
            "height": "12.70",
            "text": "19",
        },
        {
            "page_num": "87",
            "par_num": "7",
            "block_num": "0",
            "line_num": "0",
            "word_num": "1",
            "left": "157.60",
            "top": "323.36",
            "width": "360.81",
            "height": "14.20",
            "text": "世纪是议会和民主的时代。在这整个时期，人们经常听到",
        },
        {
            "page_num": "87",
            "par_num": "7",
            "block_num": "1",
            "line_num": "0",
            "word_num": "0",
            "left": "111.40",
            "top": "349.57",
            "width": "380.41",
            "height": "13.00",
            "text": "一个指责，说罗马天主教政治不过是彻头彻尾的机会主义。",
        },
    ]

    match = module.locate_quote_in_word_rows(
        rows,
        "19世纪是议会和民主的时代。在这整个时期,人们经常听到 一个指责,说罗马天主教政治不过是彻头彻尾的机会主义。",
    )

    assert match["page_number"] == 87
    assert match["matched_text"] == "19世纪是议会和民主的时代。在这整个时期，人们经常听到一个指责，说罗马天主教政治不过是彻头彻尾的机会主义。"
    assert match["rects"] == [
        [141.5, 323.36, 518.41, 337.56],
        [111.4, 349.57, 491.81, 362.57],
    ]


def test_convert_top_origin_rects_to_pdf_rects_flips_y_axis() -> None:
    module = load_module()

    rects = module.convert_top_origin_rects_to_pdf_rects(
        page_height=886.57,
        rects=[
            [141.5, 323.34, 518.41, 337.56],
            [111.4, 349.57, 491.81, 362.57],
        ],
    )

    assert rects == [
        [141.5, 549.01, 518.41, 563.23],
        [111.4, 524.0, 491.81, 537.0],
    ]


def test_build_match_quality_marks_extra_tail_text() -> None:
    module = load_module()

    quality = module.build_match_quality(
        "自然与恩宠是分裂的，而特伦托信纲对此几乎一无所知。",
        "自然与恩宠是分裂的，而特伦托信纲对此几乎一无所知。同样",
    )

    assert quality["exact_text"] is False
    assert quality["starts_with_quote"] is True
    assert quality["has_extra_text"] is True
    assert quality["extra_character_count"] == 2


def test_build_quote_locator_contains_note_writeback_fields() -> None:
    module = load_module()

    locator = module.build_quote_locator(
        {
            "page_number": 135,
            "page_index": 134,
            "strategy": "tsv",
            "matched_text": "测试句子",
            "rects": [[1, 2, 3, 4]],
            "raw_rects": [[5, 6, 7, 8]],
            "page_height": 886.553,
        },
        "测试句子",
        attachment_key="JZ8GNS66",
        annotation_key="UBG4M4TA",
        library_scope="library",
        group_id=None,
    )

    assert locator["attachment_key"] == "JZ8GNS66"
    assert locator["annotation_key"] == "UBG4M4TA"
    assert locator["attachment_type"] == "pdf"
    assert locator["library_scope"] == "library"
    assert locator["page"] == 135
    assert locator["page_number"] == 135
    assert locator["match_quality"]["exact_text"] is True
