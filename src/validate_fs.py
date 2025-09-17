#!/usr/bin/env python3
"""
Filesystem Layout Validator
===========================

Validates a target root directory against a declarative YAML specification.
The spec describes required files/dirs, per-directory constraints (allowed
names, extensions, regex patterns), recursion, and global ignore rules.

CLI
---
- --root: path to the root directory to validate (required)
- --spec: path to the YAML spec (defaults to src/fs_spec.yaml)

Exit codes
----------
- 0: all checks passed
- 1: violations found
- 2: environment/spec error
"""
import sys
import re
import argparse
from pathlib import Path

try:
    import yaml  # PyYAML
except Exception:
    print("PyYAML not installed. Please install with `pip install pyyaml`.")
    sys.exit(2)


def load_spec(spec_path: Path) -> dict:
    """Load and parse the YAML spec file.

    Parameters
    ----------
    spec_path: Path
        Path to a YAML file describing filesystem rules.

    Returns
    -------
    dict
        Parsed YAML mapping.

    Raises
    ------
    ValueError
        If the top-level YAML is not a mapping.
    """
    data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fs_spec.yaml must be a YAML mapping")
    return data


def compile_regexes(patterns):
    """Compile a list of regex pattern strings.

    Returns a list of compiled regex objects. If patterns is falsy,
    returns an empty list.
    """
    comps = []
    for p in patterns or []:
        comps.append(re.compile(p))
    return comps


def is_ignored_dir(path: Path, ignore_dir_res) -> bool:
    """Return True if the directory name matches any global ignore regex."""
    name = path.name
    return any(r.match(name) for r in ignore_dir_res)


def walk_dirs(start: Path, recursive: bool, ignore_dir_res):
    """Yield directories to check according to recursion and ignore rules.

    If ``recursive`` is False, yields only ``start``. Otherwise yields
    ``start`` and all nested directories, skipping those whose names match
    any global ignore regex.
    """
    if not recursive:
        yield start
        return
    for d in [start] + [p for p in start.rglob("*") if p.is_dir()]:
        if is_ignored_dir(d, ignore_dir_res):
            continue
        yield d


def validate_directories(base: Path, spec: dict, errors: list[str], ignore_dir_res):
    """Validate directories defined in the spec.

    For each entry under ``directories`` in the spec, apply the configured
    rules to files found under the corresponding path, optionally recursing.
    Reports forbidden subdirectories, missing READMEs, and disallowed files.
    """
    for entry in spec.get("directories", []) or []:
        dir_path = base / entry["path"]
        rules = entry.get("rules", {})
        require_exists = rules.get("require_exists", False) or entry.get("require_exists", False)
        if require_exists and (not dir_path.exists() or not dir_path.is_dir()):
            errors.append(f"Missing directory: {dir_path}")
            # If required but missing, skip further checks for this dir
            continue
        if not dir_path.exists() or not dir_path.is_dir():
            # Skip optional dirs that don't exist
            continue

        if rules.get("allow_any", False):
            # No further checks
            continue

        recursive = bool(rules.get("recursive", False))
        allow_subdirs = rules.get("allow_subdirs", True)
        file_name_regex = rules.get("file_name_regex")
        only_allow_matching = bool(rules.get("only_allow_matching", False))
        allowed_exts = set(rules.get("allowed_extensions", []) or [])
        allowed_names = set(rules.get("allowed_names", []) or [])
        require_readme_names = set(rules.get("require_readme_per_dir", []) or [])

        name_re = re.compile(file_name_regex) if file_name_regex else None

        if not allow_subdirs:
            # Check immediate subdirs only; ignore dirs matching global ignore
            subdirs = [p for p in dir_path.iterdir() if p.is_dir() and not is_ignored_dir(p, ignore_dir_res)]
            if subdirs:
                for sd in subdirs:
                    errors.append(f"{dir_path}: subdirectories are not allowed (found {sd})")

        for d in walk_dirs(dir_path, recursive, ignore_dir_res):
            files = [f for f in d.iterdir() if f.is_file()]

            # Require a README per dir if configured
            if require_readme_names:
                if not any(f.name in require_readme_names for f in files):
                    errors.append(f"{d}: missing README (one of: {sorted(require_readme_names)})")

            # File allowance checks
            if not (allowed_exts or allowed_names or name_re or only_allow_matching):
                # No constraints, continue
                continue

            for f in files:
                allowed = False
                if f.name in allowed_names:
                    allowed = True
                if not allowed and allowed_exts:
                    if f.suffix in allowed_exts:
                        allowed = True
                if not allowed and name_re is not None:
                    if name_re.match(f.name):
                        allowed = True
                if only_allow_matching and not allowed:
                    desc = []
                    if allowed_names:
                        desc.append(f"names={sorted(allowed_names)}")
                    if allowed_exts:
                        desc.append(f"exts={sorted(allowed_exts)}")
                    if name_re:
                        desc.append(f"regex={name_re.pattern}")
                    details = ", ".join(desc) if desc else "<none>"
                    errors.append(f"{f}: disallowed file. Allowed by: {details}")


def parse_args(argv):
    """Parse command-line arguments for the validator CLI."""
    parser = argparse.ArgumentParser(description="Validate filesystem layout against YAML spec.")
    parser.add_argument("--root", required=True, help="Path to the filesystem root to validate")
    parser.add_argument("--spec", help="Path to the YAML spec. Defaults to <repo>/docs/fs_spec.yaml")
    return parser.parse_args(argv[1:])


def main(argv: list[str]) -> int:
    """Program entry point used by the module and tests.

    Returns a POSIX-style exit code described in the module docstring.
    """
    args = parse_args(argv)
    base = Path(args.root).resolve() 

    # Spec is dealt with
    script_path = Path(__file__).resolve()
    default_spec = script_path.parent / "fs_spec.yaml"
    spec_path = Path(args.spec).resolve() if args.spec else default_spec
    if not spec_path.exists():
        print(f"Spec file not found: {spec_path}")
        return 2
    spec = load_spec(spec_path)
    ignore_dir_res = compile_regexes(spec.get("ignore", {}).get("dir_name_regex"))

    errors: list[str] = []
    # 2. Validate the content of directories defined in the spec
    validate_directories(base, spec, errors, ignore_dir_res)

    if errors:
        print("FS validation failed:")
        for e in errors:
            print(f" - {e}")
        return 1
    print("FS structure OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
