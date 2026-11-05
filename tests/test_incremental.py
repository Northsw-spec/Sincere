"""Synthetic-only tests for sequential private, immutable one-verse updates."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from sincere_ci.gate import GateError
from sincere_ci.incremental import apply_one, make_private_step
from test_gate import review, snapshot


class IncrementalTests(unittest.TestCase):
    def test_apply_one_approved_and_preserve_untouched_verse(self):
        old = snapshot()
        changed = apply_one(old, review()["reviews"][0], require_full=False)
        self.assertEqual(old["books"][0]["chapters"][0]["verses"][0]["tokens"],
                         ["and", "person", "saw", "thing"])
        self.assertEqual(changed["books"][0]["chapters"][0]["verses"][0]["tokens"],
                         ["and", "person", "thing", "saw"])
        self.assertEqual(changed["books"][0]["chapters"][0]["verses"][1],
                         old["books"][0]["chapters"][0]["verses"][1])

    def test_replaying_same_verse_fails(self):
        changed = apply_one(snapshot(), review()["reviews"][0], require_full=False)
        with self.assertRaisesRegex(GateError, "already applied"):
            apply_one(changed, review()["reviews"][0], require_full=False)

    def test_stale_baseline_fails(self):
        r = review()["reviews"][0]
        r["before_tokens"] = ["wrong", "person", "saw", "thing"]
        r["after_tokens"] = ["wrong", "person", "thing", "saw"]
        with self.assertRaisesRegex(GateError, "stale"):
            apply_one(snapshot(), r, require_full=False)

    def test_unapproved_review_cannot_patch(self):
        r = review(status="AMBIGUOUS")["reviews"][0]
        r["after_tokens"] = copy.deepcopy(r["before_tokens"])
        with self.assertRaisesRegex(GateError, "only CONFIRMED_REORDER"):
            apply_one(snapshot(), r, require_full=False)

    def test_required_full_scope_is_enforced(self):
        with self.assertRaisesRegex(GateError, "not the complete"):
            apply_one(snapshot(), review()["reviews"][0])

    def test_one_private_immutable_step_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "snapshot.json"
            rev = root / "review.json"
            out = root / "step-00001.json"
            base.write_text(json.dumps(snapshot()), encoding="utf-8")
            rev.write_text(json.dumps(review()), encoding="utf-8")
            old = base.read_bytes()
            result = make_private_step(base, rev, out, require_full=False)
            self.assertEqual(result["status"], "PRIVATE_STEP_WRITTEN")
            self.assertEqual(old, base.read_bytes())
            saved = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(saved["candidate_snapshot"]["books"][0]["chapters"][0]
                             ["verses"][0]["tokens"],
                             ["and", "person", "thing", "saw"])
            self.assertEqual(saved["applied_review"]["reference"], "Sample 1:1")
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)
            with self.assertRaisesRegex(GateError, "already exists"):
                make_private_step(base, rev, out, require_full=False)
            self.assertEqual(saved, json.loads(out.read_text(encoding="utf-8")))

    def test_second_step_reads_previous_bundle_and_preserves_first(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "step-00001.json"
            second = root / "step-00002.json"
            base = root / "base.json"
            r1 = root / "r1.json"
            r2 = root / "r2.json"
            base.write_text(json.dumps(snapshot()), encoding="utf-8")
            r1.write_text(json.dumps(review()), encoding="utf-8")
            make_private_step(base, r1, first, require_full=False)
            second_review = review()
            record = second_review["reviews"][0]
            record["reference"] = "Sample 1:2"
            record["before_tokens"] = ["and", "they", "rested"]
            record["after_tokens"] = ["and", "rested", "they"]
            record["evidence"]["cvot_verse_anchor"] = "Sample 1:2"
            record["evidence"]["ches_source_span_ids"] = [105, 106, 107]
            r2.write_text(json.dumps(second_review), encoding="utf-8")
            make_private_step(first, r2, second, require_full=False)
            updated = json.loads(second.read_text(encoding="utf-8"))["candidate_snapshot"]
            self.assertEqual(updated["books"][0]["chapters"][0]["verses"][0]
                             ["tokens"], ["and", "person", "thing", "saw"])
            self.assertEqual(updated["books"][0]["chapters"][0]["verses"][1]
                             ["tokens"], ["and", "rested", "they"])

    def test_invalid_review_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base, rev, out = (root / x for x in ["base.json", "review.json", "out.json"])
            base.write_text(json.dumps(snapshot()), encoding="utf-8")
            bad = review()
            bad["reviews"][0]["after_tokens"] = ["and", "person", "no", "saw"]
            rev.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(GateError):
                make_private_step(base, rev, out, require_full=False)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
