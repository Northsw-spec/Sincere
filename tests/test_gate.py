"""Synthetic fixtures only. Never put CHES/CVOT or private reader text here."""
import copy
import unittest

from sincere_ci.gate import GateError, index_snapshot, validate_reviews, verify_release


def snapshot(first=("and", "person", "saw", "thing"), second=("and", "they", "rested")):
    return {
        "schema_version": 1,
        "books": [{"name": "Sample", "chapters": [{"number": 1, "verses": [
            {"number": 1, "tokens": list(first)},
            {"number": 2, "tokens": list(second)},
        ]}]}],
    }


def review(status="CONFIRMED_REORDER", before=None, after=None):
    before = before or ["and", "person", "saw", "thing"]
    after = after or ["and", "person", "thing", "saw"]
    return {
        "schema_version": 1,
        "reviews": [{
            "reference": "Sample 1:1",
            "status": status,
            "before_tokens": before,
            "after_tokens": after,
            "evidence": {
                "ches_sha256": "a" * 64,
                "cvot_sha256": "b" * 64,
                "cvot_pdf_page": 42,
                "cvot_verse_anchor": "Sample 1:1",
                "pdf_bold_checked": True,
                "manual_syntax_review": True,
                "ches_source_span_ids": [101, 102, 103, 104],
                "syntax_reason": "Synthetic fixture: subject and predicate were separately identified.",
            },
        }],
    }


class MechanicalSafetyTests(unittest.TestCase):
    def test_approved_reordering_preserves_all_wordforms(self):
        base = snapshot()
        new = snapshot(first=("and", "person", "thing", "saw"))
        result = verify_release(base, new, review())
        self.assertEqual(result["status"], "MECHANICAL_PASS_ONLY")
        self.assertEqual(result["changed_references"], ["Sample 1:1"])
        self.assertEqual(result["unchanged_verses"], 1)

    def test_same_words_including_duplicates_are_required(self):
        bad = review(after=["and", "person", "thing", "thing"])
        with self.assertRaisesRegex(GateError, "multiset"):
            validate_reviews(bad)

    def test_verb_form_changes_fail(self):
        bad = review(after=["and", "person", "thing", "seeing"])
        with self.assertRaisesRegex(GateError, "multiset"):
            validate_reviews(bad)

    def test_missing_approval_fails(self):
        with self.assertRaisesRegex(GateError, "without confirmed review"):
            verify_release(snapshot(), snapshot(first=("and", "person", "thing", "saw")),
                           {"schema_version": 1, "reviews": []})

    def test_ambiguous_and_false_positive_must_not_change(self):
        for status in ("AMBIGUOUS", "FALSE_POSITIVE", "BLOCKED"):
            with self.subTest(status=status):
                with self.assertRaisesRegex(GateError, "remain untouched"):
                    validate_reviews(review(status=status))

    def test_false_positive_unchanged_passes(self):
        r = review(status="FALSE_POSITIVE")
        r["reviews"][0]["after_tokens"] = r["reviews"][0]["before_tokens"].copy()
        result = verify_release(snapshot(), snapshot(), r)
        self.assertEqual(result["changed_references"], [])

    def test_wrong_verse_anchor_fails(self):
        r = review()
        r["reviews"][0]["evidence"]["cvot_verse_anchor"] = "Sample 1:2"
        with self.assertRaisesRegex(GateError, "anchor mismatch"):
            validate_reviews(r)

    def test_no_manual_bold_font_attestation_fails(self):
        r = review()
        r["reviews"][0]["evidence"]["pdf_bold_checked"] = False
        with self.assertRaisesRegex(GateError, "not attested"):
            validate_reviews(r)

    def test_duplicate_review_fails(self):
        r = review()
        r["reviews"].append(copy.deepcopy(r["reviews"][0]))
        with self.assertRaisesRegex(GateError, "duplicate review"):
            validate_reviews(r)

    def test_changing_another_verse_fails(self):
        base = snapshot()
        candidate = snapshot(first=("and", "person", "thing", "saw"),
                             second=("and", "rested", "they"))
        with self.assertRaisesRegex(GateError, "without confirmed review"):
            verify_release(base, candidate, review())

    def test_removed_verse_fails(self):
        candidate = snapshot()
        candidate["books"][0]["chapters"][0]["verses"].pop()
        with self.assertRaises(GateError):
            verify_release(snapshot(), candidate, review())

    def test_missing_book_and_chapter_coverage_fails_full_gate(self):
        with self.assertRaisesRegex(GateError, "not a full"):
            verify_release(snapshot(), snapshot(),
                           {"schema_version": 1, "reviews": []}, require_full=True)

    def test_confirmed_but_unapplied_is_not_silent_pass(self):
        with self.assertRaisesRegex(GateError, "not applied"):
            verify_release(snapshot(), snapshot(), review())

    def test_nonconsecutive_verse_numbers_fail(self):
        x = snapshot()
        x["books"][0]["chapters"][0]["verses"][1]["number"] = 3
        with self.assertRaisesRegex(GateError, "verse numbering gap"):
            index_snapshot(x)

    def test_concurrent_wordform_identity_is_case_sensitive(self):
        r = review(after=["and", "Person", "thing", "saw"])
        with self.assertRaisesRegex(GateError, "multiset"):
            validate_reviews(r)


if __name__ == "__main__":
    unittest.main()
