from pathlib import Path

from pypdf import PdfReader, PdfWriter

from zotero_mcp_enhanced_service.bookmarks import (
    BookmarkEntry,
    infer_pdf_page_offset,
    parse_toc_entries,
    write_pdf_bookmarks,
)


SAMPLE_TOC_TEXT = """
目录
编者说明（刘小枫）.......................................1
教会的可见性——经院学思考［ 1918］ （刘锋译）.......... 5
政治的神学——主权学说四论［1922 ］（刘宗坤等译）……19
第 2 版序［ 1933 ］ ......................................................... 21
一、主权的定义..........................................24
二、主权问题作为法律形式和决断问题.....................33
三、政治的神学..........................................49
四、论反对革命的国家哲学（德・迈斯特、波纳德、柯特）……63
罗马天主教与政治形式［1923 〕（刘锋译）...............75

政治的神学续篇一关于终结所有政治神学的传说[1970 ]
（吴增定译）..............................................H9
给读者阅读方向的提示 ................................. 121
引言....................................................124
一、关于彻底终结神学的传说.............................127
二、已成传说的文献.....................................152
三、传说的结论命题.....................................192
跋：问题的当前状况一一现代的正当性......................204
价值的僭政------ -个法学家对价值哲学的思考[1959— 1975 ]
（朱雁冰译）...........................................................................................221
引言....................................................223
1959年自印文本.........................................240
人名译名对照表 ........................................ 254
"""


def test_parse_toc_entries_extracts_hierarchy_from_sample_text() -> None:
    entries = parse_toc_entries(SAMPLE_TOC_TEXT, max_depth=2)

    assert entries[0] == BookmarkEntry(title="编者说明（刘小枫）", printed_page=1, level=1)
    assert entries[2] == BookmarkEntry(
        title="政治的神学——主权学说四论［1922］（刘宗坤等译）",
        printed_page=19,
        level=1,
    )
    assert entries[3] == BookmarkEntry(title="第2版序［1933］", printed_page=21, level=2)
    assert entries[4] == BookmarkEntry(title="一、主权的定义", printed_page=24, level=2)
    assert entries[9] == BookmarkEntry(
        title="政治的神学续篇一关于终结所有政治神学的传说[1970]（吴增定译）",
        printed_page=119,
        level=1,
    )
    assert entries[-1] == BookmarkEntry(title="人名译名对照表", printed_page=254, level=2)


def test_write_pdf_bookmarks_creates_two_level_outline(tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    output_pdf = tmp_path / "output.pdf"

    writer = PdfWriter()
    for _ in range(260):
        writer.add_blank_page(width=72, height=72)
    with source_pdf.open("wb") as handle:
        writer.write(handle)

    entries = [
        BookmarkEntry(title="编者说明（刘小枫）", printed_page=1, level=1),
        BookmarkEntry(title="政治的神学——主权学说四论", printed_page=19, level=1),
        BookmarkEntry(title="第2版序", printed_page=21, level=2),
        BookmarkEntry(title="一、主权的定义", printed_page=24, level=2),
        BookmarkEntry(title="罗马天主教与政治形式", printed_page=75, level=1),
    ]

    write_pdf_bookmarks(
        source_pdf_path=source_pdf,
        output_pdf_path=output_pdf,
        entries=entries,
        pdf_page_offset=8,
    )

    titles = flatten_outline_titles(PdfReader(str(output_pdf)).outline)

    assert titles == [
        "编者说明（刘小枫）",
        "政治的神学——主权学说四论",
        "第2版序",
        "一、主权的定义",
        "罗马天主教与政治形式",
    ]


def test_infer_pdf_page_offset_uses_anchor_titles() -> None:
    entries = [
        BookmarkEntry(title="编者说明（刘小枫）", printed_page=1, level=1),
        BookmarkEntry(title="政治的神学——主权学说四论", printed_page=19, level=1),
        BookmarkEntry(title="罗马天主教与政治形式", printed_page=75, level=1),
    ]
    page_texts = ["封面", "版权页"] + [""] * 6 + ["编者说明正文开始", "内容"] + [""] * 9 + ["政治的神学正文开始"]

    assert infer_pdf_page_offset(entries, page_texts=page_texts) == 8


def test_infer_pdf_page_offset_prefers_page_header_match_over_body_mentions() -> None:
    entries = [BookmarkEntry(title="罗马天主教与政治形式［1923］（刘锋译）", printed_page=75, level=1)]
    page_texts = [
        "编者说明中讨论《罗马天主教与政治形式》这篇文章的意义",
        "",
        "罗马天主教与政治形式\n[1923]\n刘锋译",
    ]

    assert infer_pdf_page_offset(entries, page_texts=page_texts, min_offset=-100, max_offset=100) == -72


def flatten_outline_titles(outline: list[object]) -> list[str]:
    titles: list[str] = []
    for item in outline:
        if isinstance(item, list):
            titles.extend(flatten_outline_titles(item))
            continue
        title = getattr(item, "title", None)
        if title:
            titles.append(title)
    return titles
