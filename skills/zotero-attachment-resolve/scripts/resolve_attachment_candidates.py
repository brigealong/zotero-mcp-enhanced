"""Find likely local attachment files for a Zotero item candidate."""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from pathlib import Path


SUPPORTED_EXTENSIONS = {".pdf", ".epub"}
STOPWORDS = {
    "a",
    "an",
    "and",
    "book",
    "edition",
    "for",
    "in",
    "of",
    "on",
    "paper",
    "press",
    "the",
    "to",
    "vol",
    "volume",
}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    lowered = ascii_only.casefold()
    collapsed = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", collapsed).strip()


def tokenize(value: str) -> list[str]:
    return [
        token
        for token in normalize_text(value).split()
        if token and token not in STOPWORDS and len(token) > 1
    ]


def normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def default_search_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        home / "Downloads",
        home / "Desktop",
        home / "Documents",
    ]
    return [path for path in candidates if path.exists()]


def iter_candidate_files(search_roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        for current_root, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if not name.startswith(".")]
            for filename in filenames:
                path = Path(current_root) / filename
                if path.suffix.casefold() in SUPPORTED_EXTENSIONS:
                    files.append(path)
    return files


def score_path(
    path: Path,
    *,
    title: str,
    creators: list[str],
    doi: str,
    isbn: str,
) -> dict | None:
    normalized_path = normalize_text(str(path))
    title_tokens = tokenize(title)
    creator_tokens = [token for creator in creators for token in tokenize(creator)]
    doi_key = normalize_identifier(doi)
    isbn_key = normalize_identifier(isbn)

    score = 0
    evidence: list[str] = []

    if doi_key and doi_key in normalize_identifier(str(path)):
        score += 120
        evidence.append("doi-exact:path")
    if isbn_key and isbn_key in normalize_identifier(str(path)):
        score += 100
        evidence.append("isbn-exact:path")

    if title_tokens:
        matched = [token for token in title_tokens if token in normalized_path]
        if matched:
            score += len(matched) * 8
            evidence.append(
                f"title-token-overlap:{len(matched)}/{len(title_tokens)}"
            )
            if len(matched) == len(title_tokens):
                score += 12
                evidence.append("title-all-tokens")

    if creator_tokens:
        matched = [token for token in creator_tokens if token in normalized_path]
        if matched:
            score += len(matched) * 10
            evidence.append(
                f"creator-token-overlap:{len(matched)}/{len(creator_tokens)}"
            )

    if not evidence:
        return None

    try:
        stat = path.stat()
        modified_ts = stat.st_mtime
        size_bytes = stat.st_size
    except OSError:
        modified_ts = 0.0
        size_bytes = 0

    return {
        "path": str(path),
        "extension": path.suffix.casefold(),
        "score": score,
        "evidence": evidence,
        "size_bytes": size_bytes,
        "modified_ts": modified_ts,
    }


def resolve_candidates(
    *,
    title: str,
    creators: list[str],
    doi: str,
    isbn: str,
    search_roots: list[Path] | None,
    limit: int,
) -> list[dict]:
    roots = list(search_roots or default_search_roots())
    scored: list[dict] = []
    for path in iter_candidate_files(roots):
        candidate = score_path(
            path,
            title=title,
            creators=creators,
            doi=doi,
            isbn=isbn,
        )
        if candidate:
            scored.append(candidate)
    scored.sort(
        key=lambda item: (
            -item["score"],
            -item["modified_ts"],
            -item["size_bytes"],
            item["path"],
        )
    )
    return scored[:limit]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="")
    parser.add_argument("--creator", action="append", default=[])
    parser.add_argument("--doi", default="")
    parser.add_argument("--isbn", default="")
    parser.add_argument("--search-root", action="append", default=[])
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    roots = [Path(value) for value in args.search_root] if args.search_root else None
    payload = {
        "query": {
            "title": args.title,
            "creators": args.creator,
            "doi": args.doi,
            "isbn": args.isbn,
        },
        "search_roots": [str(path) for path in (roots or default_search_roots())],
        "candidates": resolve_candidates(
            title=args.title,
            creators=args.creator,
            doi=args.doi,
            isbn=args.isbn,
            search_roots=roots,
            limit=args.limit,
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
