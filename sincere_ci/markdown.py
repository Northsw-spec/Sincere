"""Edit exactly one attested verse in a PRIVATE Markdown book, never its PDF.

Public source code only. This tool never accesses CHES, CVOT or Google Drive.
Review attestations are assertions requiring independent private source checks.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile

from .gate import GateError, _require, validate_reviews


_CHAPTER = re.compile(r"^### Chapter ([1-9][0-9]*)\n$")
_VERSE = re.compile(r"^\*\*([1-9][0-9]*)\.\*\* (.+?)(\n?)$")
_BOOK = re.compile(r"^## ([1-3] )?[A-Za-z][A-Za-z ]*\n$", re.M)


def _md_index(markdown: str) -> tuple[str, dict[str, tuple[int, str]]]:
    """Parse a complete Markdown book, enforcing chapter/verse order and integrity."""
    _require(isinstance(markdown, str) and markdown.startswith("# Sincere Translation\n"),
             "expected a Sincere Translation Markdown volume")
    _require("\r" not in markdown, "unexpected line endings")
    books = list(_BOOK.finditer(markdown))
    _require(len(books) == 1, "exactly one Markdown book heading required")
    book = books[0].group(0)[3:].strip()
    chapter = 0
    current_verse = 0
    verses: dict[str, tuple[int, str]] = {}
    lines = markdown.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        chapter_match = _CHAPTER.fullmatch(line)
        if chapter_match:
            number = int(chapter_match.group(1))
            _require(number == chapter + 1, "missing or duplicate chapter")
            if chapter:
                _require(current_verse > 0, "chapter without verses")
            chapter = number
            current_verse = 0
            continue
        verse_match = _VERSE.fullmatch(line)
        if verse_match:
            _require(chapter > 0, "verse outside chapter")
            number = int(verse_match.group(1))
            _require(number == current_verse + 1, "missing or duplicate verse")
            current_verse = number
            ref = f"{book} {chapter}:{number}"
            _require(ref not in verses, "duplicate verse reference")
            verses[ref] = (idx, verse_match.group(2))
    _require(chapter > 0 and current_verse > 0, "book lacks verses")
    return book, verses


def apply_markdown_one(markdown: str, record: dict) -> tuple[str, str]:
    """Return Markdown with ONE unchanged-vocabulary, attested reordering."""
    reviewed = validate_reviews({"schema_version": 1, "reviews": [record]})
    ref, item = next(iter(reviewed.items()))
    _require(item["status"] == "CONFIRMED_REORDER",
             "only CONFIRMED_REORDER can change a verse")
    book, verses = _md_index(markdown)
    _require(ref.startswith(book + " "), "review belongs to a different book")
    _require(ref in verses, "review reference does not exist in the Markdown book")
    idx, actual = verses[ref]
    before = " ".join(item["before_tokens"])
    after = " ".join(item["after_tokens"])
    _require(actual != after, "verse already updated; refusing duplicate edit")
    _require(actual == before, "stale review: actual Markdown text differs")
    _require(before != after, "no word reorder found")
    lines = markdown.splitlines(keepends=True)
    old_line = lines[idx]
    ending = "\n" if old_line.endswith("\n") else ""
    lines[idx] = f"**{ref.split(':')[-1]}.** {after}{ending}"
    changed = "".join(lines)
    _, candidate = _md_index(changed)
    _require(set(verses) == set(candidate), "chapter or verse layout changed")
    mutated = [key for key in verses if verses[key][1] != candidate[key][1]]
    _require(mutated == [ref], "an unrelated verse changed")
    _require(candidate[ref][1] == after, "revised verse does not match review")
    return changed, ref


def _write_new(path: Path, payload: bytes) -> None:
    """Create a new private, synced immutable file; never overwrite history."""
    _require(path.parent.is_dir(), "destination parent folder missing")
    _require(not path.is_symlink(), "destination symlink forbidden")
    fd = None
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".sincere-private-", dir=path.parent)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            os.fchmod(handle.fileno(), 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(tmp, path)  # O_EXCL-style create, never replace older revisions.
        dfd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
        _require(path.read_bytes() == payload, "local read-back mismatch")
    except FileExistsError as exc:
        raise GateError("revision output exists; immutable history cannot be overwritten") from exc
    finally:
        if fd is not None:
            os.close(fd)
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)


def create_markdown_revision(original_path: Path, review_path: Path,
                             revised_path: Path, journal_path: Path) -> dict:
    """Write one independent private Markdown revision plus its JSON audit record.

    This does not upload to Google Drive, nor certify a verse's source grammar.
    Actual durable remote persistence must be independently read-back verified.
    """
    paths = [original_path, review_path, revised_path, journal_path]
    _require(len({str(path.resolve()) for path in paths}) == 4,
             "input/output files must all be distinct")
    _require(not revised_path.exists() and not journal_path.exists(),
             "revision output exists")
    original_bytes = original_path.read_bytes()
    original = original_bytes.decode("utf-8")
    input_doc = json.loads(review_path.read_text(encoding="utf-8"))
    _require(isinstance(input_doc, dict) and input_doc.get("schema_version") == 1,
             "review document schema missing")
    entries = input_doc.get("reviews")
    _require(isinstance(entries, list) and len(entries) == 1,
             "exactly one reviewed verse per operation")
    changed, ref = apply_markdown_one(original, entries[0])
    revised_bytes = changed.encode("utf-8")
    journal = {
        "schema_version": 1,
        "reference": ref,
        "before_file_sha256": sha256(original_bytes).hexdigest(),
        "after_file_sha256": sha256(revised_bytes).hexdigest(),
        "review": entries[0],
        "status": "MECHANICAL_PASS_ONLY",
        "publication": "NOT_PUBLISHED",
        "caveat": "No source/CVOT-bold verification or remote Drive round-trip was performed.",
    }
    journal_bytes = (json.dumps(journal, ensure_ascii=False, sort_keys=True,
                                indent=2) + "\n").encode("utf-8")
    md_written = False
    try:
        _write_new(revised_path, revised_bytes)
        md_written = True
        _write_new(journal_path, journal_bytes)
    except Exception:
        if md_written:
            revised_path.unlink(missing_ok=True)  # Roll back incomplete pair.
        raise
    _require(revised_path.read_bytes() == revised_bytes, "Markdown read-back mismatch")
    _require(journal_path.read_bytes() == journal_bytes, "journal read-back mismatch")
    return {
        "status": "LOCAL_PRIVATE_REVISION_WRITTEN",
        "changed_verses": 1,
        "mechanical_gate": "PASS",
        "publication": "NOT_PUBLISHED",
        "remote_drive_readback": "NOT_TESTED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-md", required=True, type=Path)
    parser.add_argument("--review-json", required=True, type=Path)
    parser.add_argument("--revised-md", required=True, type=Path)
    parser.add_argument("--revision-json", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = create_markdown_revision(
            args.original_md, args.review_json, args.revised_md, args.revision_json
        )
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL: {type(exc).__name__}; no canonical file changed\n")
    # Never print verses, file paths, evidence, source excerpts or private IDs.
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
