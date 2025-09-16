#!/usr/bin/env python3
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
    data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fs_spec.yaml must be a YAML mapping")
    return data


def compile_regexes(patterns):
    comps = []
    for p in patterns or []:
        comps.append(re.compile(p))
    return comps


def is_ignored_dir(path: Path, ignore_dir_res) -> bool:
    name = path.name
    return any(r.match(name) for r in ignore_dir_res)


def validate_required(base: Path, req: dict, errors: list[str]):
    for f in req.get("files", []) or []:
        p = base / f
        if not p.exists() or not p.is_file():
            errors.append(f"Missing required file: {p}")
    for d in req.get("dirs", []) or []:
        p = base / d
        if not p.exists() or not p.is_dir():
            errors.append(f"Missing required directory: {p}")


def walk_dirs(start: Path, recursive: bool, ignore_dir_res):
    if not recursive:
        yield start
        return
    for d in [start] + [p for p in start.rglob("*") if p.is_dir()]:
        if is_ignored_dir(d, ignore_dir_res):
            continue
        yield d


def validate_directories(base: Path, spec: dict, errors: list[str], ignore_dir_res):
    for entry in spec.get("directories", []) or []:
        dpath = base / entry["path"]
        rules = entry.get("rules", {})
        require_exists = rules.get("require_exists", False) or entry.get("require_exists", False)
        if require_exists and (not dpath.exists() or not dpath.is_dir()):
            errors.append(f"Missing directory: {dpath}")
            # If required but missing, skip further checks for this dir
            continue
        if not dpath.exists() or not dpath.is_dir():
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
            subdirs = [p for p in dpath.iterdir() if p.is_dir() and not is_ignored_dir(p, ignore_dir_res)]
            if subdirs:
                for sd in subdirs:
                    errors.append(f"{dpath}: subdirectories are not allowed (found {sd})")

        for d in walk_dirs(dpath, recursive, ignore_dir_res):
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
    parser = argparse.ArgumentParser(description="Validate filesystem layout against YAML spec.")
    parser.add_argument("--root", required=True, help="Path to the filesystem root to validate")
    parser.add_argument("--spec", help="Path to the YAML spec. Defaults to <repo>/docs/fs_spec.yaml")
    return parser.parse_args(argv[1:])


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    script_path = Path(__file__).resolve()
    default_spec = script_path.parent / "fs_spec.yaml"
    spec_path = Path(args.spec).resolve() if args.spec else default_spec
    if not spec_path.exists():
        print(f"Spec file not found: {spec_path}")
        return 2

    spec = load_spec(spec_path)
    base = Path(args.root).resolve()

    ignore_dir_res = compile_regexes(spec.get("ignore", {}).get("dir_name_regex"))

    errors: list[str] = []
    validate_required(base, spec.get("required", {}), errors)
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

