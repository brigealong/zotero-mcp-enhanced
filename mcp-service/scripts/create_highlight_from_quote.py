from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path


ANNOTATION_SCRIPT_PATH = Path(__file__).with_name("create_zotero_annotation.py")

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def resolve_pdftotext_path() -> Path:
    configured = os.environ.get("PDFTOTEXT_PATH")
    candidates = [configured] if configured else []
    detected = shutil.which("pdftotext")
    if detected:
        candidates.append(detected)
    candidates.extend(
        [
            r"C:\Program Files\MiKTeX\miktex\bin\x64\pdftotext.exe",
            r"C:\Users\Public\MiKTeX\miktex\bin\x64\pdftotext.exe",
            r"C:\Program Files\poppler\Library\bin\pdftotext.exe",
        ]
    )
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.exists():
            return path
    raise RuntimeError(
        "pdftotext not found. Set PDFTOTEXT_PATH or add pdftotext to PATH before running this script."
    )


def load_annotation_module():
    spec = importlib.util.spec_from_file_location("create_zotero_annotation", ANNOTATION_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load annotation module: {ANNOTATION_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_quote_search_variants(quote: str) -> list[str]:
    variants: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        value = value.strip()
        if value and value not in seen:
            variants.append(value)
            seen.add(value)

    add(quote)
    collapsed = re.sub(r"\s+", " ", quote).strip()
    add(collapsed)
    add(collapsed.replace(" ", ""))
    return variants


def normalize_for_match(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized.translate(
        str.maketrans(
            "",
            "",
            ",，:：;；()（）[]【】{}<>《》\"“”'‘’·、",
        )
    )


def build_quote_fragments(quote: str) -> list[str]:
    fragments = [
        fragment.strip()
        for fragment in re.split(r"[。；!?！？]", quote)
        for fragment in re.split(r"\s+", fragment)
        if fragment.strip()
    ]
    merged: list[str] = []
    current = ""
    for fragment in fragments:
        candidate = f"{current} {fragment}".strip() if current else fragment
        if len(candidate) < 10:
            current = candidate
            continue
        merged.append(candidate)
        current = ""
    if current:
        merged.append(current)
    if not merged:
        merged = [quote.strip()]
    return merged


def locate_quote_on_page(page, quote: str):
    for variant in build_quote_search_variants(quote):
        rects = page.search_for(variant)
        if rects:
            return {
                "strategy": "exact",
                "matched_text": variant,
                "rects": rects,
            }

    fragment_rects = []
    matched_fragments = []
    for fragment in build_quote_fragments(quote):
        found = None
        for variant in build_quote_search_variants(fragment):
            rects = page.search_for(variant)
            if rects:
                found = (variant, rects)
                break
        if not found:
            return None
        matched_fragments.append(found[0])
        fragment_rects.extend(found[1])

    return {
        "strategy": "fragments",
        "matched_text": " / ".join(matched_fragments),
        "rects": fragment_rects,
    }


def estimate_page_from_ft_cache(pdf_path: str | Path, quote: str) -> int | None:
    cache_path = Path(pdf_path).with_name(".zotero-ft-cache")
    if not cache_path.exists():
        return None
    target = normalize_for_match(quote)
    text = cache_path.read_text(encoding="utf-8", errors="replace")
    for page_number, page_text in enumerate(text.split("\f"), start=1):
        if target and target in normalize_for_match(page_text):
            return page_number
    return None


def extract_tsv_rows(
    pdf_path: str | Path,
    *,
    first_page: int | None = None,
    last_page: int | None = None,
) -> list[dict[str, str]]:
    pdftotext_path = resolve_pdftotext_path()
    command = [str(pdftotext_path)]
    if first_page is not None:
        command.extend(["-f", str(first_page)])
    if last_page is not None:
        command.extend(["-l", str(last_page)])
    command.extend(["-tsv", "-enc", "UTF-8", str(pdf_path), "-"])
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout or "pdftotext failed")
    lines = completed.stdout.splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) != len(header):
            continue
        row = dict(zip(header, parts))
        if row.get("level") != "5":
            continue
        text = row.get("text", "")
        if not text or text.startswith("###"):
            continue
        rows.append(row)
    return rows


def merge_rects_for_rows(rows: list[dict[str, str]]) -> list[list[float]]:
    merged: list[list[float]] = []
    current_key = None
    current_rect: list[float] | None = None
    for row in rows:
        key = (row["page_num"], row["par_num"], row["block_num"], row["line_num"])
        left = float(row["left"])
        top = float(row["top"])
        right = left + float(row["width"])
        bottom = top + float(row["height"])
        if key != current_key:
            if current_rect:
                merged.append(current_rect)
            current_key = key
            current_rect = [left, top, right, bottom]
            continue
        current_rect = [
            min(current_rect[0], left),
            min(current_rect[1], top),
            max(current_rect[2], right),
            max(current_rect[3], bottom),
        ]
    if current_rect:
        merged.append(current_rect)
    return [[round(value, 4) for value in rect] for rect in merged]


def load_page_height(pdf_path: str | Path, page_number: int) -> float:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    page = reader.pages[page_number - 1]
    return round(float(page.cropbox.top) - float(page.cropbox.bottom), 4)


def convert_top_origin_rects_to_pdf_rects(
    *,
    page_height: float,
    rects: list[list[float]] | list[tuple[float, float, float, float]],
) -> list[list[float]]:
    converted: list[list[float]] = []
    for left, top, right, bottom in rects:
        converted.append(
            [
                round(float(left), 4),
                round(float(page_height) - float(bottom), 4),
                round(float(right), 4),
                round(float(page_height) - float(top), 4),
            ]
        )
    return converted


def build_match_quality(quote: str, matched_text: str) -> dict[str, object]:
    normalized_quote = normalize_for_match(quote)
    normalized_matched = normalize_for_match(matched_text)
    exact_text = normalized_matched == normalized_quote
    starts_with_quote = normalized_matched.startswith(normalized_quote)
    ends_with_quote = normalized_matched.endswith(normalized_quote)
    extra_chars = max(0, len(normalized_matched) - len(normalized_quote))
    return {
        "normalized_quote": normalized_quote,
        "normalized_matched_text": normalized_matched,
        "exact_text": exact_text,
        "starts_with_quote": starts_with_quote,
        "ends_with_quote": ends_with_quote,
        "has_extra_text": not exact_text,
        "extra_character_count": extra_chars,
    }


def build_quote_locator(
    match: dict[str, object],
    quote: str,
    *,
    attachment_key: str,
    annotation_key: str,
    attachment_type: str = "pdf",
    library_scope: str = "library",
    group_id: str | None = None,
) -> dict[str, object]:
    return {
        "quote": quote,
        "matched_text": match["matched_text"],
        "attachment_key": attachment_key,
        "annotation_key": annotation_key,
        "attachment_type": attachment_type,
        "library_scope": library_scope,
        "group_id": group_id,
        "page": int(match["page_number"]),
        "page_number": int(match["page_number"]),
        "page_index": int(match["page_index"]),
        "page_label": str(match["page_number"]),
        "strategy": match["strategy"],
        "coordinate_space": "pdf-bottom-left",
        "source_coordinate_space": "pdftotext-top-origin",
        "page_height": match["page_height"],
        "rects": match["rects"],
        "raw_rects": match["raw_rects"],
        "match_quality": build_match_quality(quote, str(match["matched_text"])),
    }


def locate_quote_in_word_rows(rows: list[dict[str, str]], quote: str) -> dict[str, object]:
    if not rows:
        raise RuntimeError("No TSV word rows available")

    ordered_rows = sorted(
        rows,
        key=lambda row: (
            int(row["page_num"]),
            int(row["par_num"]),
            int(row["block_num"]),
            int(row["line_num"]),
            int(row["word_num"]),
        ),
    )
    target = normalize_for_match(quote)
    normalized_texts = [normalize_for_match(row["text"]) for row in ordered_rows]

    for start in range(len(ordered_rows)):
        start_text = normalized_texts[start]
        if not start_text or not target.startswith(start_text):
            continue
        combined = ""
        for end in range(start, len(ordered_rows)):
            piece = normalized_texts[end]
            if not piece:
                continue
            candidate = combined + piece
            if target.startswith(candidate):
                combined = candidate
            elif candidate.startswith(target):
                combined = candidate
            else:
                break
            if target != combined and not combined.startswith(target):
                continue
            matched_rows = ordered_rows[start : end + 1]
            return {
                "page_number": int(matched_rows[0]["page_num"]),
                "page_index": int(matched_rows[0]["page_num"]) - 1,
                "strategy": "tsv-window",
                "matched_text": "".join(row["text"] for row in matched_rows),
                "rects": merge_rects_for_rows(matched_rows),
            }
    raise RuntimeError("Quote not found in TSV word rows")


def locate_quote_in_pdf(pdf_path: str | Path, quote: str) -> dict[str, object]:
    estimated_page = estimate_page_from_ft_cache(pdf_path, quote)
    if estimated_page is not None:
        first_page = max(1, estimated_page - 1)
        last_page = estimated_page + 1
        rows = extract_tsv_rows(pdf_path, first_page=first_page, last_page=last_page)
    else:
        rows = extract_tsv_rows(pdf_path)
    match = locate_quote_in_word_rows(rows, quote)
    page_height = load_page_height(pdf_path, int(match["page_number"]))
    match["raw_rects"] = match["rects"]
    match["page_height"] = page_height
    match["rects"] = convert_top_origin_rects_to_pdf_rects(
        page_height=page_height,
        rects=match["raw_rects"],
    )
    match["strategy"] = "ft-cache+tsv" if estimated_page is not None else "tsv"
    return match


def build_highlight_annotation_request(
    *,
    attachment_key: str,
    page_number: int,
    quote: str,
    rects: list[tuple[float, float, float, float]] | list[list[float]],
    comment: str = "",
    color: str = "#ffd400",
    page_label: str | None = None,
    library_id: int = 1,
) -> dict[str, object]:
    annotation_module = load_annotation_module()
    normalized_rects = [[float(v) for v in rect] for rect in rects]
    return annotation_module.build_annotation_request(
        attachment_key=attachment_key,
        page=page_number,
        comment=comment,
        annotation_type="highlight",
        page_label=page_label or str(page_number),
        text=quote,
        color=color,
        position={
            "pageIndex": page_number - 1,
            "rects": normalized_rects,
        },
        library_id=library_id,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Locate a quote in a PDF and create a Zotero highlight annotation."
    )
    parser.add_argument("attachment_key")
    parser.add_argument("pdf_path")
    parser.add_argument("quote")
    parser.add_argument("--comment", default="")
    parser.add_argument("--color", default="#ffd400")
    parser.add_argument("--page-label")
    parser.add_argument("--library-id", type=int, default=1)
    parser.add_argument("--library-scope", default="library")
    parser.add_argument("--group-id")
    parser.add_argument("--result-path")
    parser.add_argument("--working-dir")
    parser.add_argument("--timeout-sec", type=int, default=30)
    parser.add_argument("--poll-interval-ms", type=int, default=500)
    return parser.parse_args()


def main():
    args = parse_args()
    annotation_module = load_annotation_module()
    located = locate_quote_in_pdf(args.pdf_path, args.quote)
    request = build_highlight_annotation_request(
        attachment_key=args.attachment_key,
        page_number=int(located["page_number"]),
        quote=args.quote,
        rects=located["rects"],
        comment=args.comment,
        color=args.color,
        page_label=args.page_label or str(located["page_number"]),
        library_id=args.library_id,
    )

    bridge = annotation_module.load_bridge_module()
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
    result["quote_match"] = located
    result["locator"] = build_quote_locator(
        located,
        args.quote,
        attachment_key=request["item_key"],
        annotation_key=result["annotationKey"],
        attachment_type="pdf",
        library_scope=args.library_scope,
        group_id=args.group_id,
    )

    if args.result_path:
        result_path = Path(args.result_path)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
