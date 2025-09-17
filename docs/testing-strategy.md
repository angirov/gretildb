Testing Strategy
================

This project relies on two lightweight validators and a small static site generator:
- `src/validate_fs.py`: checks repository/DB folder structure against a YAML spec.
- `src/validate_collections.py`: validates underscore collections, item YAMLs, and their attachments.
- `static/static.py`: renders HTML (not covered by tests yet).

Goals
-----
- Validate expected success paths with minimal fixtures.
- Catch common error modes (missing required files, disallowed files, schema/tag violations).
- Keep tests hermetic: build temporary directories; no network; no global state.

Scope & Approach
----------------
- Black‑box CLI tests for both validators using standard library `unittest` and `tempfile`.
- Each test constructs a temporary filesystem:
  - For `validate_fs.py`: creates a minimal tree that conforms to `src/fs_spec.yaml`, and a negative variant with “extra” files.
  - For `validate_collections.py`: creates a minimal collection (`_<name>`), a matching schema file, an item YAML, and attachments; plus negative variants (stray/disallowed/mismatched tag).
- Tests assert only on exit codes and key substrings in stdout to remain robust to message formatting changes.

How to Run
----------
- Using the standard library runner:

  python3 -m unittest discover -s tests -p "test_*.py"

What’s Covered
--------------
- `validate_fs.py`:
  - Success case: valid root, `docs/`, `schemas/` with allowed names, `scripts/` with README and allowed script types.
  - Failure case: unexpected/disallowed files at root and under constrained directories.
- `validate_collections.py`:
  - Success case: required schema present, item YAML parses and (minimally) conforms, attachments match config (extension + tag pattern, required attachments present).
  - Failure case: stray attachment without `<item>_` boundary.

Out of Scope (for now)
----------------------
- Static rendering tests for `static/static.py`.
- Hook execution tests for attachment validators (use `--run-hooks`).

Extending Tests
---------------
- Add per‑collection rules in your config and replicate scenarios in temp fixtures.
- Validate more negative cases (orphan attachments, tag mismatches) by adding small files in the temp trees and asserting on the error substrings.
