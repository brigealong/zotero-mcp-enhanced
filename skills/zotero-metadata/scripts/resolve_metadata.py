"""Resolve Zotero metadata from a local PDF/EPUB or remote bibliographic hints."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from pypdf import PdfReader


ISBN_RE = re.compile(r"\b(?:97[89][\-\s]?)?\d[\d\-\s]{8,16}\d\b")
YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})\b")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    lowered = ascii_only.casefold()
    collapsed = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", collapsed).strip()


def clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    return value.strip(" -_|:,;")


def split_people(value: str) -> list[str]:
    parts = re.split(r"\s*(?:,|;|/| and | & )\s*", value or "")
    return [clean_text(part) for part in parts if clean_text(part)]


def extract_year(value: str) -> str:
    match = YEAR_RE.search(value or "")
    return match.group(1) if match else ""


def extract_isbn(value: str) -> str:
    match = ISBN_RE.search(value or "")
    if not match:
        return ""
    return re.sub(r"[^0-9Xx]", "", match.group(0))


def clean_filename_stem(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"\b(pdf|epub|mobi|azw3|djvu)\b", " ", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[_\-.]+", " ", stem)
    return clean_text(stem)


def parse_title_author_from_filename(path: Path) -> tuple[str, list[str], list[str]]:
    raw_stem = path.stem
    evidence: list[str] = ["filename:stem"]
    if " - " in raw_stem:
        left, right = [clean_text(part) for part in raw_stem.split(" - ", 1)]
        if len(left.split()) <= 4:
            return right, split_people(left), evidence + ["filename:author-title"]
        if len(right.split()) <= 4:
            return left, split_people(right), evidence + ["filename:title-author"]
    cleaned = clean_filename_stem(path)
    return cleaned, [], evidence


def infer_confidence(title: str, authors: list[str], evidence: list[str]) -> str:
    unique_evidence = {item.split(":", 1)[0] for item in evidence}
    if title and authors and len(unique_evidence) >= 2:
        return "high"
    if title and (authors or len(evidence) >= 2):
        return "medium"
    return "low"


def make_candidate(
    *,
    item_type: str,
    title: str = "",
    authors: list[str] | None = None,
    year: str = "",
    publisher: str = "",
    place: str = "",
    isbn: str = "",
    doi: str = "",
    url: str = "",
    language: str = "",
    evidence: list[str] | None = None,
    source: str = "",
    source_id: str = "",
) -> dict:
    authors = authors or []
    evidence = evidence or []
    title = clean_text(title)
    return {
        "item_type": item_type,
        "title": title,
        "authors": [clean_text(name) for name in authors if clean_text(name)],
        "year": clean_text(year),
        "publisher": clean_text(publisher),
        "place": clean_text(place),
        "isbn": clean_text(isbn),
        "doi": clean_text(doi),
        "url": clean_text(url),
        "language": clean_text(language),
        "confidence": infer_confidence(title, authors, evidence),
        "evidence": evidence,
        "source": source,
        "source_id": source_id,
    }


def choose_title_from_lines(lines: list[str]) -> tuple[str, list[str]]:
    for index, line in enumerate(lines[:12], start=1):
        cleaned = clean_text(line)
        lowered = cleaned.casefold()
        if len(cleaned) < 8:
            continue
        if any(token in lowered for token in ["copyright", "isbn", "doi", "www.", "http://", "https://"]):
            continue
        return cleaned, [f"page_{index}:title_line"]
    return "", []


def choose_authors_from_lines(lines: list[str]) -> tuple[list[str], list[str]]:
    for index, line in enumerate(lines[:18], start=1):
        cleaned = clean_text(line)
        lowered = cleaned.casefold()
        if lowered.startswith("by "):
            return split_people(cleaned[3:]), [f"page_{index}:author_line"]
        if lowered.startswith("author "):
            value = re.sub(r"(?i)^author[s]?:?\s*", "", cleaned)
            return split_people(value), [f"page_{index}:author_line"]
    return [], []


def extract_pdf_metadata(path: Path) -> dict | None:
    reader = PdfReader(str(path))
    metadata = reader.metadata or {}
    evidence: list[str] = []
    title = clean_text(str(metadata.get("/Title", "") or ""))
    authors = split_people(str(metadata.get("/Author", "") or ""))
    if title:
        evidence.append("pdf_metadata:title")
    if authors:
        evidence.append("pdf_metadata:author")

    text_lines: list[str] = []
    for page in reader.pages[:2]:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text_lines.extend(line.strip() for line in text.splitlines() if clean_text(line))

    if not title:
        guessed_title, guessed_evidence = choose_title_from_lines(text_lines)
        title = guessed_title or title
        evidence.extend(guessed_evidence)
    if not authors:
        guessed_authors, guessed_evidence = choose_authors_from_lines(text_lines)
        authors = guessed_authors or authors
        evidence.extend(guessed_evidence)

    joined_text = "\n".join(text_lines[:80])
    isbn = extract_isbn(joined_text) or extract_isbn(clean_filename_stem(path))
    if isbn:
        evidence.append("page_or_filename:isbn")
    year = extract_year(str(metadata.get("/CreationDate", "") or "")) or extract_year(joined_text)
    if year:
        evidence.append("pdf_or_page:year")

    if not title:
        title, filename_authors, filename_evidence = parse_title_author_from_filename(path)
        if filename_authors and not authors:
            authors = filename_authors
        evidence.extend(filename_evidence)

    if not title:
        return None

    return make_candidate(
        item_type="document",
        title=title,
        authors=authors,
        year=year,
        isbn=isbn,
        evidence=evidence,
        source="local-pdf",
        source_id=str(path),
    )


def extract_epub_metadata(path: Path) -> dict | None:
    with zipfile.ZipFile(path) as epub_zip:
        container_root = ET.fromstring(epub_zip.read("META-INF/container.xml"))
        rootfile = container_root.find(".//{*}rootfile")
        if rootfile is None:
            return None
        opf_path = rootfile.attrib.get("full-path", "")
        if not opf_path:
            return None
        opf_root = ET.fromstring(epub_zip.read(opf_path))

    ns = {"dc": "http://purl.org/dc/elements/1.1/"}

    def first_text(xpath: str) -> str:
        node = opf_root.find(xpath, ns)
        return clean_text(node.text if node is not None and node.text else "")

    title = first_text(".//dc:title")
    authors = [clean_text(node.text or "") for node in opf_root.findall(".//dc:creator", ns) if clean_text(node.text or "")]
    publisher = first_text(".//dc:publisher")
    year = extract_year(first_text(".//dc:date"))
    language = first_text(".//dc:language")
    evidence: list[str] = []
    if title:
        evidence.append("opf:title")
    if authors:
        evidence.append("opf:creator")
    if publisher:
        evidence.append("opf:publisher")
    if year:
        evidence.append("opf:date")

    isbn = ""
    for node in opf_root.findall(".//dc:identifier", ns):
        isbn = extract_isbn(node.text or "")
        if isbn:
            evidence.append("opf:identifier:isbn")
            break

    if not title:
        title, filename_authors, filename_evidence = parse_title_author_from_filename(path)
        if filename_authors and not authors:
            authors = filename_authors
        evidence.extend(filename_evidence)

    if not title:
        return None

    return make_candidate(
        item_type="book",
        title=title,
        authors=authors,
        year=year,
        publisher=publisher,
        isbn=isbn,
        language=language,
        evidence=evidence,
        source="local-epub",
        source_id=str(path),
    )


def extract_local_candidates(path: Path) -> list[dict]:
    suffix = path.suffix.casefold()
    if suffix == ".pdf":
        candidate = extract_pdf_metadata(path)
    elif suffix == ".epub":
        candidate = extract_epub_metadata(path)
    else:
        raise RuntimeError(f"Unsupported local metadata suffix: {path.suffix}")
    return [candidate] if candidate else []


def fetch_json(url: str, *, params: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def build_crossref_candidate(message: dict) -> dict:
    authors: list[str] = []
    for author in message.get("author", []) or []:
        name = " ".join(part for part in [author.get("given", ""), author.get("family", "")] if part).strip()
        if name:
            authors.append(name)
    year = ""
    for key in ["published-print", "published-online", "issued"]:
        parts = (((message.get(key) or {}).get("date-parts")) or [[]])[0]
        if parts:
            year = str(parts[0])
            break
    return make_candidate(
        item_type="journalArticle",
        title=((message.get("title") or [""])[0]),
        authors=authors,
        year=year,
        publisher=((message.get("container-title") or [""])[0]),
        doi=message.get("DOI", "") or "",
        url=message.get("URL", "") or "",
        language=message.get("language", "") or "",
        evidence=["crossref:message"],
        source="crossref",
        source_id=message.get("DOI", "") or "",
    )


def resolve_doi_candidates(doi: str) -> list[dict]:
    data = fetch_json(
        f"https://api.crossref.org/works/{urllib.parse.quote(doi)}",
        headers={"User-Agent": "zotero-metadata/1.0 (mailto:none@example.com)"},
    )
    message = (data.get("message") or {})
    candidate = build_crossref_candidate(message)
    candidate["confidence"] = "high"
    candidate["evidence"].append("query:doi-exact")
    return [candidate] if candidate.get("title") else []


def resolve_title_candidates(title: str, author: str | None, limit: int) -> list[dict]:
    results: list[dict] = []
    book_data = fetch_json(
        "https://openlibrary.org/search.json",
        params={"title": title, "author": author or "", "limit": str(limit)},
    )
    for doc in book_data.get("docs", [])[:limit]:
        if not doc.get("title"):
            continue
        results.append(
            make_candidate(
                item_type="book",
                title=doc.get("title", ""),
                authors=doc.get("author_name", []) or [],
                year=str(doc.get("first_publish_year", "") or ""),
                publisher=(doc.get("publisher") or [""])[0],
                place=(doc.get("publish_place") or [""])[0] if doc.get("publish_place") else "",
                isbn=(doc.get("isbn") or [""])[0] if doc.get("isbn") else "",
                language=(doc.get("language") or [""])[0] if doc.get("language") else "",
                evidence=["openlibrary:search"],
                source="openlibrary",
                source_id=doc.get("key", "") or "",
            )
        )
    article_data = fetch_json(
        "https://api.crossref.org/works",
        params={"query.title": title, "query.author": author or "", "rows": str(limit)},
        headers={"User-Agent": "zotero-metadata/1.0 (mailto:none@example.com)"},
    )
    for message in (((article_data.get("message") or {}).get("items")) or [])[:limit]:
        if message.get("title"):
            results.append(build_crossref_candidate(message))
    return dedupe_candidates(results)[:limit]


def resolve_isbn_candidates(isbn: str, limit: int) -> list[dict]:
    data = fetch_json(
        "https://openlibrary.org/search.json",
        params={"isbn": isbn, "limit": str(limit)},
    )
    candidates = []
    for doc in data.get("docs", [])[:limit]:
        if not doc.get("title"):
            continue
        candidate = make_candidate(
            item_type="book",
            title=doc.get("title", ""),
            authors=doc.get("author_name", []) or [],
            year=str(doc.get("first_publish_year", "") or ""),
            publisher=(doc.get("publisher") or [""])[0],
            place=(doc.get("publish_place") or [""])[0] if doc.get("publish_place") else "",
            isbn=(doc.get("isbn") or [""])[0] if doc.get("isbn") else isbn,
            language=(doc.get("language") or [""])[0] if doc.get("language") else "",
            evidence=["openlibrary:isbn-search", "query:isbn"],
            source="openlibrary",
            source_id=doc.get("key", "") or "",
        )
        candidate["confidence"] = "high"
        candidates.append(candidate)
    return candidates


def dedupe_candidates(candidates: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    output: list[dict] = []
    for candidate in candidates:
        key = (
            normalize_text(candidate.get("title", "")),
            normalize_text(" ".join(candidate.get("authors", []))),
            normalize_text(candidate.get("doi", "") or candidate.get("isbn", "") or candidate.get("source_id", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(candidate)
    return output


def resolve_remote_candidates(*, title: str | None, author: str | None, doi: str | None, isbn: str | None, limit: int) -> list[dict]:
    if doi:
        return resolve_doi_candidates(doi)
    if isbn:
        return resolve_isbn_candidates(isbn, limit)
    if title:
        return resolve_title_candidates(title, author, limit)
    raise RuntimeError("Remote metadata resolution requires one of: --doi, --isbn, --title")


def print_json_output(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attachment-path")
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument("--doi")
    parser.add_argument("--isbn")
    parser.add_argument("--item-type-hint", choices=["book", "journalArticle", "document"])
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if args.attachment_path:
        path = Path(args.attachment_path)
        if not path.exists():
            raise RuntimeError(f"Attachment not found: {path}")
        candidates = extract_local_candidates(path)
        payload = {"mode": "local-file", "query": None, "attachment_path": str(path), "item_type_hint": args.item_type_hint, "candidates": candidates}
    else:
        candidates = resolve_remote_candidates(title=args.title, author=args.author, doi=args.doi, isbn=args.isbn, limit=args.limit)
        payload = {
            "mode": "remote-query",
            "query": {"title": args.title, "author": args.author, "doi": args.doi, "isbn": args.isbn},
            "attachment_path": None,
            "item_type_hint": args.item_type_hint,
            "candidates": candidates,
        }
    print_json_output(payload)


if __name__ == "__main__":
    main()
