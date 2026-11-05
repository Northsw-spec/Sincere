# Sincere Translation — verification tooling

This repository holds **source-independent code and automated tests only** for the Sincere Translation Old Testament project.

## What this repository provides

- `sincere_ci/gate.py`: fail-closed mechanical checks for verse-by-verse before/after journals and full-manuscript comparisons.
- `sincere_ci/markdown.py`: one-verse source-attested **private Markdown** update with a separate immutable JSON revision journal.
- `sincere_ci/incremental.py`: earlier JSON-snapshot proof of concept, maintained for compatibility; Markdown is now the editable manuscript format.
- `tests/test_gate.py`, `tests/test_markdown.py`: synthetic tests, including rejected vocabulary/verb-form edits, stale reviews, cross-verse changes, immutable Markdown snapshots and numbering drift.
- `.github/workflows/sincere-ci.yml`: Ubuntu GitHub Actions job named `sincere-required-ci`.
- [Verification boundary and private release process](docs/VERIFICATION_BOUNDARY.md).

Run the publicly safe regression unit tests locally with `python3 -m unittest discover -s tests -v`. No third-party Python dependencies are required.

## Canonical content and current status

- The canonical manuscript, CHES source material, CVOT comparison source, source-span ledger and publishing checkpoints remain in a **private Google Drive project workspace**.
- This public repository is **not** a Bible text repository, authoritative manuscript or a source for its publication.
- Verified working reader at bootstrap: **v3.1**, covering 39 books, 929 chapters and 23,145 verses. Status: **DRAFT_REVIEW_REQUIRED**. These are technical coverage figures, **not** a claim of completed linguistic review.
- Nehemiah 7:68 is an unresolved CHES source-span exception.

## Security and editorial rules

Do not commit, attach to issues/PRs, print in CI logs, or upload as public Actions artifacts: original CHES/CVOT data, private manuscript/volume contents, full private verse ledgers, source excerpts or access credentials.

**A successful GitHub Action checks the verifier's behavior on synthetic fixtures only.** Real-source grammar and complete manuscript/PDF verification must be performed separately before publication. Never modify unrelated projects or repositories.
