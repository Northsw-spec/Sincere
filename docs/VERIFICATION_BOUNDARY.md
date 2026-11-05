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

## One verse at a time — private working revisions

New source-independent helper: `sincere_ci.incremental`. It accepts a **private, already tokenized** latest reader snapshot and **one manually verified review** at a time. Its output is an immutable, private JSON bundle containing the revised snapshot, corresponding review journal, and the exact SHA-256 of the preceding input file. It refuses stale, duplicate, uncertain or lexically changed verses and changes no other verse.

In a trusted private runtime **only**, after independently verifying real source syntax and using a new private output filename:

```bash
python3 -m sincere_ci.incremental \
  --input /private/working-snapshot.json \
  --review /private/next-reviewed-verse.json \
  --output /private/revisions/step-00001.json
```

Then repeat with the preceding step as the next input and a new review/output path. Each step creates a new file with restricted permissions, checks the write by rereading it and never replaces the original. The private storage system must itself be durable, versioned and secured, with backups; an upload to Drive must be independently read back before it can be counted as persisted progress. The helper performs NO Google Drive upload and NO PDF regeneration. A valid private snapshot has exactly 39 books, 929 chapters and 23,145 verses (fail closed). The synthetic test function can be run without that requirement but the CLI cannot.

The `CONFIRMED_REORDER` status and evidence fields are author assertions. **The helper does not independently establish the historical Hebrew syntax, inspect CVOT PDF font attributes, verify every CHES span, or approve a final edition.** An unverified suggestion must never be passed as approved. Keep step files, review contents, source-derived snapshots and any logs containing them private, outside the public repository and Actions artifacts.

## Current preferred private editorial format (2026-11-05)

The user-approved division of responsibility is:

- **Markdown**: primary editable source of the GT, one private working `.md` volume per book.
- **JSON**: machine-readable, private per-verse source review journals and Markdown SHA-256 chains.
- **PDF**: generated reader / publication artifact after full private GT regression, never the line-by-line edit target.

The complete v3.1 ZIP already contains 39 Markdown volumes with 929 chapter headings
and 23,145 numbered verses. The private `CHES_CVOT_GT` Drive project holds an
**unmodified v3.1 working copy** (39 Markdown volumes plus a JSON working-state manifest
and empty review journal). Do not store that private copy, the Drive identifier or any
of its actual verse contents in GitHub.

The preferred private CLI for one properly CHES/CVOT-attested, *necessary for
reader comprehension*, same-verse word reordering is:

```sh
python3 -m sincere_ci.markdown \
  --original-md /private/current/001_book.md \
  --review-json /private/approved_single_verse_review.json \
  --revised-md /private/next/001_book_revision_0001.md \
  --revision-json /private/next/revision_0001.json
```

The command is **local only**: it rejects prior-applied or stale proposals, changes
exactly one numbered verse, preserves verb/word tokens exactly, writes a new
Markdown book and separate JSON evidence+before/after-hash journal without
overwriting originals, and rereads them. It does not upload or certify anything.

After generating, upload the **new immutable private Markdown revision and JSON
journal** to the protected Drive folder and **download both back, byte-for-byte**.
Treat the revised book as current only if both round trips match their SHA-256
fingerprints. Prefer new revision filenames and an append-only active-version
manifest rather than overwriting existing files. Do not count a correction merely
because local write or public CI succeeds. No actual verse corrections were made
by the initial v3.1 working-copy migration.

**Reader comprehension is the edit criterion:** unusual or non-idiomatic
word order is acceptable when a reader acquainted with the preface and chapter
context can genuinely understand the text. Never reorder solely to force
subject-before-verb, or because CVOT offers a different natural-sounding order.

The earlier `sincere_ci.incremental` JSON-snapshot helper is retained for
backward compatibility and synthetically tested but **not** the preferred manuscript
authoring format.
