"""Apply one approved verse reordering to a *private*, immutable working snapshot.

This module contains no manuscript data. Public CI tests use synthetic examples.
Actual source attestation remains a separate private human/philological process.
"""

from __future__ import annotations

import argparse
import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from .gate import GateError, _require, index_snapshot, validate_reviews, verify_release


def apply_one(snapshot: object, record: object, *, require_full: bool = True) -> dict:
    """Return a new snapshot after exactly one source-attested lexical reordering.

    The caller must use current (not outdated) reader tokens in the review.
    No private file is modified by this function.
    """
    _require(isinstance(record, dict), "one full review object is required")
    reviewed = validate_reviews({"schema_version": 1, "reviews": [record]})
    ref, approved = next(iter(reviewed.items()))
    _require(approved["status"] == "CONFIRMED_REORDER",
             "only CONFIRMED_REORDER can modify reader text")
    order, tokens, counts = index_snapshot(snapshot)
    if require_full:
        _require(counts == {"books": 39, "chapters": 929, "verses": 23145},
                 "snapshot is not the complete Old Testament")
    _require(ref in tokens, "reviewed reference not in current snapshot")
    before = tuple(approved["before_tokens"])
    after = tuple(approved["after_tokens"])
    _require(tokens[ref] != after, "this change was already applied")
    _require(tokens[ref] == before, "review refers to stale or different reader tokens")

    candidate = copy.deepcopy(snapshot)
    found = False
    for book in candidate["books"]:
        for chapter in book["chapters"]:
            for verse in chapter["verses"]:
                key = f"{book['name']} {chapter['number']}:{verse['number']}"
                if key == ref:
                    _require(not found, "duplicate reference found")
                    verse["tokens"] = list(after)
                    found = True
    _require(found, "target reference absent")

    result = verify_release(
        snapshot, candidate, {"schema_version": 1, "reviews": [record]},
        require_full=require_full,
    )
    _require(result["changed_references"] == [ref], "unexpected mutation")
    _require(result["unchanged_verses"] == len(order) - 1,
             "unreviewed verses were modified")
    return candidate


def _decode_input(path: Path) -> tuple[dict, str]:
    """Accept an initial private snapshot or the preceding versioned step."""
    data = path.read_bytes()
    document = json.loads(data)
    if isinstance(document, dict) and "candidate_snapshot" in document:
        document = document["candidate_snapshot"]
    _require(isinstance(document, dict), "snapshot input must be a JSON object")
    index_snapshot(document)
    return document, sha256(data).hexdigest()


def _write_once_private(path: Path, payload: bytes) -> None:
    """Do not overwrite an earlier snapshot, including on concurrent writers.

    Write temporary bytes, sync them, then atomically link an exclusive new name
    in the same directory. Never mutate the canonical input snapshot.
    """
    _require(path.parent.is_dir(), "output directory must exist")
    _require(not path.is_symlink(), "output must not be a symlink")
    fd = None
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(
            prefix=".sincere-private-pending-", dir=path.parent
        )
        with os.fdopen(fd, "wb") as stream:
            fd = None
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Hard link fails if path already exists, so old versions are immutable.
        os.link(temp_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        _require(path.read_bytes() == payload, "readback mismatch")
    except FileExistsError as exc:
        raise GateError("output already exists: refusing to overwrite private history") from exc
    finally:
        if fd is not None:
            os.close(fd)
        if temp_path is not None:
            Path(temp_path).unlink(missing_ok=True)


def make_private_step(input_path: Path, review_path: Path, output_path: Path,
                      *, require_full: bool = True) -> dict:
    """Create one immutable private step bundling the revised reader and its journal."""
    _require(input_path.resolve() != output_path.resolve(),
             "input and output must differ")
    _require(review_path.resolve() != output_path.resolve(),
             "review and output must differ")
    snapshot, parent_sha = _decode_input(input_path)
    raw = json.loads(review_path.read_text(encoding="utf-8"))
    _require(isinstance(raw, dict) and raw.get("schema_version") == 1,
             "review must be a versioned JSON object")
    entries = raw.get("reviews")
    _require(isinstance(entries, list) and len(entries) == 1,
             "exactly one review record per private step is required")
    candidate = apply_one(snapshot, entries[0], require_full=require_full)
    output = {
        "schema_version": 1,
        "previous_file_sha256": parent_sha,
        "applied_review": entries[0],
        "candidate_snapshot": candidate,
        "verification_status": "MECHANICAL_PASS_ONLY",
        "note": "Not a CVOT/CHES source check, grammar certification or published edition.",
    }
    encoded = (json.dumps(output, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode("utf-8")
    _write_once_private(output_path, encoded)
    # Strong local round-trip: ensure persistent candidate contains one correct edit.
    reread = json.loads(output_path.read_text(encoding="utf-8"))
    _require(reread["previous_file_sha256"] == parent_sha,
             "broken parent hash chain")
    _require(reread["candidate_snapshot"] == candidate,
             "stored candidate differs from verified candidate")
    _require(reread["applied_review"] == entries[0],
             "review journal differs from approved review")
    return {"status": "PRIVATE_STEP_WRITTEN", "review_count": 1,
            "mechanical_gate": "PASS", "publication_status": "NOT_PUBLISHED"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True,
                        help="Private tokenized baseline or previous step JSON")
    parser.add_argument("--review", type=Path, required=True,
                        help="Private single-verse review JSON")
    parser.add_argument("--output", type=Path, required=True,
                        help="Unique new private step filename: never overwritten")
    args = parser.parse_args()
    try:
        report = make_private_step(args.input, args.review, args.output)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL: {type(exc).__name__}; no canonical source changed\n")
    # Never print any verse tokens, private paths, Drive IDs or evidence to logs.
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
