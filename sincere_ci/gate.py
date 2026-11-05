"""Fail-closed, *mechanical* review and snapshot checks for Sincere Translation.

Never use this module to decide Hebrew grammar or to fetch/upload private texts.
The caller must independently attest CHES/CVOT source and syntax evidence.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import argparse
import json
import re


class GateError(ValueError):
    """Input or release candidate does not satisfy mechanical safety rules."""


_STATUSES = {"CONFIRMED_REORDER", "FALSE_POSITIVE", "AMBIGUOUS", "BLOCKED"}
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_REF = re.compile(r"(?:[1-3] )?[A-Za-z][A-Za-z ]* [1-9][0-9]*:[1-9][0-9]*\Z")


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise GateError(message)


def _tokens(value: object, field: str) -> tuple[str, ...]:
    _require(isinstance(value, list) and bool(value), f"{field}: nonempty list required")
    _require(
        all(isinstance(item, str) and bool(item) and item == item.strip()
            and not any(ch.isspace() for ch in item) for item in value),
        f"{field}: tokens must be exact, nonblank, whitespace-free strings",
    )
    return tuple(value)


def _evidence(ev: object, reference: str) -> None:
    _require(isinstance(ev, dict), f"{reference}: evidence object missing")
    for key in ("ches_sha256", "cvot_sha256"):
        _require(isinstance(ev.get(key), str) and bool(_SHA256.fullmatch(ev[key])),
                 f"{reference}: invalid {key}")
    _require(type(ev.get("cvot_pdf_page")) is int and ev["cvot_pdf_page"] > 0,
             f"{reference}: a positive, manually located PDF page is required")
    _require(ev.get("cvot_verse_anchor") == reference,
             f"{reference}: CVOT verse anchor mismatch")
    _require(ev.get("pdf_bold_checked") is True and ev.get("manual_syntax_review") is True,
             f"{reference}: source morphology/typography and syntax not attested")
    ids = ev.get("ches_source_span_ids")
    _require(isinstance(ids, list) and ids and len(ids) == len(set(map(str, ids)))
             and all(isinstance(x, (str, int)) and str(x) for x in ids),
             f"{reference}: unique CHES span IDs required")
    note = ev.get("syntax_reason")
    _require(isinstance(note, str) and len(note.strip()) >= 20,
             f"{reference}: concrete syntax reasoning required")


def validate_reviews(document: object) -> dict[str, dict]:
    """Check review journal format, word conservation and explicitly attested decisions.

    This does not prove evidence is true or inspect CVOT PDF font properties.
    """
    _require(isinstance(document, dict) and document.get("schema_version") == 1,
             "review schema_version must be 1")
    reviews = document.get("reviews")
    _require(isinstance(reviews, list), "reviews must be a list")
    seen: dict[str, dict] = {}
    for record in reviews:
        _require(isinstance(record, dict), "every review must be an object")
        ref = record.get("reference")
        _require(isinstance(ref, str) and bool(_REF.fullmatch(ref)),
                 "invalid book chapter:verse reference")
        _require(ref not in seen, f"duplicate review: {ref}")
        status = record.get("status")
        _require(status in _STATUSES, f"{ref}: invalid decision")
        before = _tokens(record.get("before_tokens"), f"{ref} before")
        after = _tokens(record.get("after_tokens"), f"{ref} after")
        if status == "CONFIRMED_REORDER":
            _require(before != after, f"{ref}: no actual change")
            _require(Counter(before) == Counter(after),
                     f"{ref}: lexical token multiset or verb form changed")
            _evidence(record.get("evidence"), ref)
        else:
            _require(before == after,
                     f"{ref}: unapproved/ambiguous case must remain untouched")
        seen[ref] = record
    return seen


def index_snapshot(document: object) -> tuple[list[str], dict[str, tuple[str, ...]], dict]:
    """Index entire reader text while enforcing unique, consecutive book/chapter/verse IDs."""
    _require(isinstance(document, dict) and document.get("schema_version") == 1,
             "snapshot schema_version must be 1")
    books = document.get("books")
    _require(isinstance(books, list) and books, "books missing")
    order: list[str] = []
    verses: dict[str, tuple[str, ...]] = {}
    book_names: set[str] = set()
    chapters_total = 0
    for book in books:
        _require(isinstance(book, dict), "book must be an object")
        name = book.get("name")
        _require(isinstance(name, str) and bool(re.fullmatch(r"(?:[1-3] )?[A-Za-z][A-Za-z ]*", name)),
                 "invalid book name")
        _require(name not in book_names, f"duplicate book: {name}")
        book_names.add(name)
        chapters = book.get("chapters")
        _require(isinstance(chapters, list) and chapters, f"{name}: chapters missing")
        for chapter_number, chapter in enumerate(chapters, start=1):
            _require(isinstance(chapter, dict) and chapter.get("number") == chapter_number,
                     f"{name}: chapters must be consecutive starting at 1")
            chapters_total += 1
            chapter_verses = chapter.get("verses")
            _require(isinstance(chapter_verses, list) and chapter_verses,
                     f"{name} {chapter_number}: verses missing")
            for verse_number, verse in enumerate(chapter_verses, start=1):
                _require(isinstance(verse, dict) and verse.get("number") == verse_number,
                         f"{name} {chapter_number}: verse numbering gap/duplicate")
                key = f"{name} {chapter_number}:{verse_number}"
                _require(key not in verses, f"duplicate verse: {key}")
                verses[key] = _tokens(verse.get("tokens"), key)
                order.append(key)
    return order, verses, {"books": len(books), "chapters": chapters_total, "verses": len(verses)}


def verify_release(baseline: object, candidate: object, review_doc: object,
                   *, require_full: bool = False) -> dict:
    """Reject any reader change without a matching, source-attested review entry."""
    reviews = validate_reviews(review_doc)
    old_order, old, old_stats = index_snapshot(baseline)
    new_order, new, new_stats = index_snapshot(candidate)
    _require(old_order == new_order, "book, chapter or verse layout changed")
    _require(old_stats == new_stats, "coverage changed")
    if require_full:
        _require(new_stats == {"books": 39, "chapters": 929, "verses": 23145},
                 "not a full 39-book, 929-chapter, 23,145-verse manuscript")
    _require(set(reviews).issubset(old), "review references absent from manuscript")
    changed = []
    for ref in old_order:
        if old[ref] != new[ref]:
            record = reviews.get(ref)
            _require(record is not None and record["status"] == "CONFIRMED_REORDER",
                     f"{ref}: changed without confirmed review")
            _require(tuple(record["before_tokens"]) == old[ref],
                     f"{ref}: review baseline does not match")
            _require(tuple(record["after_tokens"]) == new[ref],
                     f"{ref}: candidate does not match review")
            _require(Counter(old[ref]) == Counter(new[ref]),
                     f"{ref}: changed vocabulary or inflection")
            changed.append(ref)
    for ref, record in reviews.items():
        if record["status"] == "CONFIRMED_REORDER":
            _require(ref in changed, f"{ref}: confirmed review not applied to candidate")
    return {
        "status": "MECHANICAL_PASS_ONLY",
        "coverage": new_stats,
        "changed_references": changed,
        "unchanged_verses": len(old) - len(changed),
        "important_limitation": (
            "Not a source, CVOT-bold-font, PDF/layout, Hebrew grammar or "
            "publication verification. Review evidence must be checked privately."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--reviews", required=True, type=Path)
    parser.add_argument("--require-full", action="store_true")
    args = parser.parse_args()
    try:
        result = verify_release(
            json.loads(args.baseline.read_text(encoding="utf-8")),
            json.loads(args.candidate.read_text(encoding="utf-8")),
            json.loads(args.reviews.read_text(encoding="utf-8")),
            require_full=args.require_full,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, GateError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
