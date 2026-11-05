# Verification boundaries and release policy

## What public GitHub Actions checks

The public **sincere-required-ci** job uses synthetic text only. It verifies the code's capacity to reject:

- lexical additions, deletions, substitutions, duplicate words and verb-form changes;
- any modifications to a verse without a unique CONFIRMED_REORDER journal entry;
- an AMBIGUOUS, BLOCKED or FALSE_POSITIVE record that changes text;
- missing, reordered, duplicated or non-consecutive verse references;
- a candidate that differs from its approved before/after journal;
- a confirmed review without a minimal manual CVOT/CHES evidence attestation.

**A green check does not mean that any real verse has been checked against Hebrew, CHES, or CVOT.** Evidence booleans are metadata assertions, not a substitute for inspecting private source files. No private sources are downloaded by public CI.

## Private manuscript regression

In a private, controlled execution environment with authorized source access, export *tokenized* baseline, candidate and verse-review journal as JSON matching `sincere_ci.gate`'s schema. Execute:

```bash
python3 -m sincere_ci.gate \
  --baseline /private/baseline.json \
  --candidate /private/candidate.json \
  --reviews /private/reviews.json \
  --require-full
```

The command fails on an unexpected text change or incomplete 39-book / 929-chapter / 23,145-verse structure. It does **not** inspect original source-span alignment, attest that a human reviewed CVOT fetstil, verify PDF bookmarks/chapter links or guarantee the completeness of the actual manuscript. Those are separate private release gates. Never attach the private JSON files to a public GitHub Action or PR.

## Editorial review (private)

1. Read the *current* canonical manifest and checkpoint in the private project workspace; select the latest verified release.
2. Verify CHES and CVOT source bytes against canonical SHA-256 values.
3. Inspect a genuine numbered verse and adjacent context in both sources, including CVOT PDF typeface/bold spans. Decide subject, predicate, object and vocative.
4. Journal each review with full source-span IDs and human rationale privately. Approved reorders preserve source-derived lexical tokens and current verb forms exactly; ambiguous cases remain unchanged.
5. Repeat on verses outside heuristic flags. The existing 991 flags are neither verified errors nor exhaustive.
6. Retain Nehemiah 7:68 as a source-span exception until independently resolved.
7. Run full private text regression, verify 39 volume texts and their PDF parity, preface, 929 chapter links/bookmarks, and SHA-256 after roundtrip upload before updating any canonical manifest or checkpoint.

## Publication

The original CHES ZIP, CVOT PDF, manuscript volumes, large private ledgers, source text excerpts and Drive credentials must **not** be committed or included in public CI logs/artifacts. Only source-independent code, synthetic fixtures and non-sensitive aggregate test reports belong in this public repository.

Until a full real-source verification and publication audit passes, the GT reader must retain `DRAFT_REVIEW_REQUIRED`; do not use terms such as "filologically complete" or "all verses verified." Passing CI here is necessary as a software check, not sufficient to publish a new Bible edition.
