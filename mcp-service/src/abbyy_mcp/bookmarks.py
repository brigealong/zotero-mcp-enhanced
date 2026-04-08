from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader, PdfWriter


TOC_LINE_PATTERN = re.compile(r"^(?P<title>.+?)(?:[.。·•…\-\s]{2,})(?P<page>[A-Za-z0-9]+)\s*$")
SECTION_TITLE_PATTERN = re.compile(
    r"^(?:"
    r"第\s*\d+\s*版序"
    r"|[一二三四五六七八九十]+、"
    r"|引言"
    r"|跋[:：]"
    r"|给读者阅读方向的提示"
    r"|1959年自印文本"
    r"|人名译名对照表"
    r")"
)


@dataclass(frozen=True)
class BookmarkEntry:
    title: str
    printed_page: int
    level: int = 1


def parse_toc_entries(toc_text: str, *, max_depth: int = 2) -> list[BookmarkEntry]:
    entries: list[BookmarkEntry] = []
    pending_title_parts: list[str] = []

    for raw_line in toc_text.splitlines():
        normalized_line = normalize_toc_line(raw_line)
        if not normalized_line or normalized_line == "目录":
            continue

        match = TOC_LINE_PATTERN.match(normalized_line)
        if match is None:
            pending_title_parts.append(normalized_line)
            continue

        title_parts = [part for part in pending_title_parts if part]
        title_parts.append(match.group("title"))
        pending_title_parts.clear()

        title = normalize_title("".join(title_parts))
        page = normalize_printed_page(match.group("page"))
        level = infer_entry_level(title, max_depth=max_depth)
        entries.append(BookmarkEntry(title=title, printed_page=page, level=level))

    return entries


def extract_toc_text(pdf_path: Path, *, max_scan_pages: int = 40) -> str:
    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    collecting = False

    for index, page in enumerate(reader.pages[:max_scan_pages], start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            if collecting:
                break
            continue

        is_toc_page = "目录" in text or count_toc_lines(text) >= 3
        if is_toc_page:
            collecting = True
            pages.append(text)
            continue

        if collecting:
            break

    return "\n\n".join(pages)


def infer_pdf_page_offset(
    entries: list[BookmarkEntry],
    *,
    pdf_path: Path | None = None,
    page_texts: list[str] | None = None,
    max_scan_pages: int = 300,
    min_offset: int = -5,
    max_offset: int = 50,
) -> int:
    if page_texts is None:
        if pdf_path is None:
            raise ValueError("pdf_path or page_texts is required")
        page_texts = extract_page_texts(pdf_path, max_scan_pages=max_scan_pages)

    scores: dict[int, int] = {}
    for entry in entries:
        if entry.level != 1:
            continue
        anchor = make_anchor_title(entry.title)
        if not anchor:
            continue
        match_index = find_anchor_page(anchor, page_texts)
        if match_index is None:
            continue
        offset = (match_index + 1) - entry.printed_page
        if min_offset <= offset <= max_offset:
            scores[offset] = scores.get(offset, 0) + 1

    if not scores:
        return 0
    return max(sorted(scores), key=lambda candidate: (scores[candidate], -abs(candidate), -candidate))


def write_pdf_bookmarks(
    *,
    source_pdf_path: Path,
    output_pdf_path: Path,
    entries: list[BookmarkEntry],
    pdf_page_offset: int,
) -> Path:
    reader = PdfReader(str(source_pdf_path))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    parents: dict[int, object] = {}
    max_index = max(len(reader.pages) - 1, 0)
    for entry in entries:
        target_index = min(max(entry.printed_page + pdf_page_offset - 1, 0), max_index)
        parent = parents.get(entry.level - 1)
        outline_item = writer.add_outline_item(entry.title, page_number=target_index, parent=parent)
        parents[entry.level] = outline_item
        for stale_level in [level for level in parents if level > entry.level]:
            parents.pop(stale_level, None)

    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with output_pdf_path.open("wb") as handle:
        writer.write(handle)
    return output_pdf_path


def count_toc_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if TOC_LINE_PATTERN.match(normalize_toc_line(line)))


def extract_page_texts(pdf_path: Path, *, max_scan_pages: int = 300) -> list[str]:
    reader = PdfReader(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages[:max_scan_pages]]


def find_anchor_page(anchor: str, page_texts: list[str]) -> int | None:
    for page_index, page_text in enumerate(page_texts):
        normalized = normalize_search_text(page_text)
        if not normalized:
            continue
        if normalized.startswith(anchor):
            return page_index

    for page_index, page_text in enumerate(page_texts):
        normalized = normalize_search_text(page_text)
        if anchor and anchor in normalized:
            return page_index

    return None


def infer_entry_level(title: str, *, max_depth: int) -> int:
    if max_depth <= 1:
        return 1
    if SECTION_TITLE_PATTERN.match(title):
        return 2
    return 1


def normalize_toc_line(line: str) -> str:
    return re.sub(r"\s+", "", line.strip())


def normalize_title(title: str) -> str:
    cleaned = title.strip()
    cleaned = re.sub(r"[.。·•…\-\s]+$", "", cleaned)
    cleaned = re.sub(r"\[\s*", "[", cleaned)
    cleaned = re.sub(r"\s*\]", "]", cleaned)
    cleaned = re.sub(r"［\s*", "［", cleaned)
    cleaned = re.sub(r"\s*］", "］", cleaned)
    return cleaned


def make_anchor_title(title: str) -> str:
    anchor = re.sub(r"[\[［(（].*?[\]］)）]", "", title)
    anchor = re.sub(r"[-—–:：·•]", "", anchor)
    return normalize_search_text(anchor)


def normalize_search_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def normalize_printed_page(page_token: str) -> int:
    token = page_token.strip().replace(" ", "")
    if re.fullmatch(r"[Hh]\d+", token):
        token = f"11{token[1:]}"
    else:
        token = token.translate(str.maketrans({"I": "1", "l": "1", "O": "0", "o": "0"}))
    return int(token)
