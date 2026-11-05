"""Synthetic book only; NO real biblical material may enter public CI."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from sincere_ci.gate import GateError
from sincere_ci.markdown import apply_markdown_one, create_markdown_revision
from test_gate import review


SAMPLE = (
    "# Sincere Translation\n\n"
    "## Sample\n\n"
    "### Chapter 1\n\n"
    "**1.** and person saw thing\n\n"
    "**2.** and they rested\n\n"
    "### Chapter 2\n\n"
    "**1.** the rain fell slowly\n"
)


class PrivateMarkdownTests(unittest.TestCase):
    def test_single_verse_and_all_other_bytes_preserved(self):
        changed, ref = apply_markdown_one(SAMPLE, review()["reviews"][0])
        self.assertEqual(ref, "Sample 1:1")
        self.assertEqual(
            changed,
            SAMPLE.replace("**1.** and person saw thing",
                           "**1.** and person thing saw", 1),
        )

    def test_replay_of_already_applied_review_is_blocked(self):
        changed, _ = apply_markdown_one(SAMPLE, review()["reviews"][0])
        with self.assertRaisesRegex(GateError, "already updated"):
            apply_markdown_one(changed, review()["reviews"][0])

    def test_stale_review_cannot_modify_markdown(self):
        doc = review()
        doc["reviews"][0]["before_tokens"] = ["and", "person", "saw", "another"]
        doc["reviews"][0]["after_tokens"] = ["and", "person", "another", "saw"]
        with self.assertRaisesRegex(GateError, "stale review"):
            apply_markdown_one(SAMPLE, doc["reviews"][0])

    def test_ambiguous_case_cannot_modify_markdown(self):
        record = review(status="AMBIGUOUS")["reviews"][0]
        record["after_tokens"] = copy.deepcopy(record["before_tokens"])
        with self.assertRaisesRegex(GateError, "only CONFIRMED_REORDER"):
            apply_markdown_one(SAMPLE, record)

    def test_wrong_book_is_blocked(self):
        record = review()["reviews"][0]
        record["reference"] = "Other 1:1"
        record["evidence"]["cvot_verse_anchor"] = "Other 1:1"
        with self.assertRaisesRegex(GateError, "different book"):
            apply_markdown_one(SAMPLE, record)

    def test_duplicate_chapter_fails_closed(self):
        changed = SAMPLE.replace("### Chapter 2", "### Chapter 1")
        with self.assertRaisesRegex(GateError, "duplicate chapter"):
            apply_markdown_one(changed, review()["reviews"][0])

    def test_duplicate_verse_fails_closed(self):
        changed = SAMPLE.replace("**2.** and they rested", "**1.** and they rested")
        with self.assertRaisesRegex(GateError, "duplicate verse"):
            apply_markdown_one(changed, review()["reviews"][0])

    def test_missing_bold_attestation_fails_closed(self):
        record = review()["reviews"][0]
        record["evidence"]["pdf_bold_checked"] = False
        with self.assertRaisesRegex(GateError, "not attested"):
            apply_markdown_one(SAMPLE, record)

    def test_create_outputs_are_private_and_journal_has_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, rev, md, log = (root / name for name in
                                 ("source.md", "review.json", "revision.md", "revision.json"))
            src.write_text(SAMPLE, encoding="utf-8")
            rev.write_text(json.dumps(review()), encoding="utf-8")
            result = create_markdown_revision(src, rev, md, log)
            self.assertEqual(result["changed_verses"], 1)
            self.assertEqual(result["remote_drive_readback"], "NOT_TESTED")
            obj = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(obj["before_file_sha256"],
                             hashlib.sha256(src.read_bytes()).hexdigest())
            self.assertEqual(obj["after_file_sha256"],
                             hashlib.sha256(md.read_bytes()).hexdigest())
            self.assertEqual(obj["status"], "MECHANICAL_PASS_ONLY")
            self.assertEqual(md.stat().st_mode & 0o777, 0o600)
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)
            self.assertEqual(SAMPLE, src.read_text(encoding="utf-8"))
            with self.assertRaisesRegex(GateError, "output exists"):
                create_markdown_revision(src, rev, md, log)

    def test_bad_review_does_not_write_any_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src, rev, md, log = (root / name for name in
                                 ("source.md", "review.json", "revision.md", "revision.json"))
            src.write_text(SAMPLE, encoding="utf-8")
            invalid = review()
            invalid["reviews"][0]["after_tokens"] = ["and", "another", "thing", "saw"]
            rev.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaises(GateError):
                create_markdown_revision(src, rev, md, log)
            self.assertFalse(md.exists())
            self.assertFalse(log.exists())


if __name__ == "__main__":
    unittest.main()
