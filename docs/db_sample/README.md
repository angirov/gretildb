Database Sample Layout and Validation
====================================

This folder illustrates the expected on‑disk layout for a database instance and how to validate it using the repository’s filesystem spec and validator.

Overview
--------
- The validator enforces structure and naming rules defined in `docs/fs_spec.yaml`.
- Collections (folders starting with `_`) are ignored by validation to keep the sample simple.
- The `schemas/` and `scripts/` folders are constrained; `docs/` is open for any content.   

Expected Layout (top level)
---------------------------
- README.md: this file (required)
- config.yaml: optional config file for your instance
- docs/: exists; unconstrained content (free‑form)
- schemas/: required; only YAML files matching `^_[a-z0-9][a-z0-9-]*\.yaml$`; no subfolders
- scripts/: required; may contain only Python (`.py`) and Bash (`.sh`) files plus a README in every directory
- _… (collections): zero or more folders whose names begin with `_` (ignored by validator)

What “unnecessary files” means
------------------------------
- At the root, only `README.md` and `config.yaml` are allowed. Anything else (e.g., stray files) is flagged.
- Under `schemas/`, only files matching the regex above are allowed; subdirectories are not allowed.
- Under `scripts/`, only `.py`, `.sh`, and README files are allowed; any other files are flagged. Every directory in `scripts/` must have a README (`README.md` or `readme.md`).

How Validation Works
--------------------
1. Rules live in `docs/fs_spec.yaml` and are completely declarative. Key parts:
   - ignore.dir_name_regex: directories to skip globally (e.g., `^_.*$` to ignore collections).
   - required.files / required.dirs: items that must exist at the root.
   - directories[]: per‑path rules (allow/deny lists, regex, recursion, README requirement, etc.).
   - only_allow_matching: when true, files not matching any allow‑rule are reported as “disallowed”.
2. The validator script `scripts/validate_fs.py` reads the spec and checks a target root.
3. Exit codes: 0 = OK, 1 = violations found, 2 = setup/spec error.

Run the Validator
-----------------
- From the repository root, validate this sample:
  
  python scripts/validate_fs.py --root db_sample

- Use a non‑default spec (optional):
  
  python scripts/validate_fs.py --root db_sample --spec docs/fs_spec.yaml

Customizing Rules
-----------------
- Edit `docs/fs_spec.yaml` to adjust constraints without changing code. Common changes:
  - Allow additional root files: add names under `directories: - path: "." -> rules.allowed_names`.
  - Relax scripts constraints: add extensions to `allowed_extensions` or files to `allowed_names`.
  - Remove the “README required” rule in scripts: delete `require_readme_per_dir`.
  - Change which directories are ignored globally: update `ignore.dir_name_regex`.

Notes
-----
- The validator uses PyYAML (listed in `requirements.txt`).
- Collections (underscore‑prefixed folders) are ignored by default; if you want to validate them, remove the corresponding ignore rule and add directory rules for those paths.
