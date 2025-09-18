#!/usr/bin/env python3
"""
Collection Validator
====================

Validates underscore-prefixed collection directories (e.g., ``_works``) under
an input root. Each collection contains item YAML files (``<item>.yaml``)
and optional attachments linked by filename convention: ``<item>_<tag><ext>``.

Validation performed
--------------------
- For each collection directory ``_<name>``, requires a schema file named
  ``_<name>.yaml`` in the schemas directory (default: ``<root>/schemas``).
- Item YAMLs are parsed and validated against the collection schema
  using Draft 2020-12 JSON Schema.
- Attachment rules are read from a config YAML (see ``src/settings_schema.yaml``)
  and may impose per-extension requirements, tag regex patterns, and optional
  external validation hooks to run per-attachment.

CLI
---
- --root: path containing underscore collections (required)
- --schemas: path to schemas dir (defaults to ``<root>/schemas``)
- --config: path to settings/config YAML defining rules (defaults to ``<root>/config.yaml``)
- --hooks: directory containing optional hook scripts referenced by config
- --run-hooks: actually execute hook scripts (disabled by default)
 - --map-out: path to write a JSON map of collections/items/attachments
   (defaults to ``<root>/collections.json``)

Exit codes
----------
- 0: all checks passed
- 1: violations found
- 2: environment/config error
"""
import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


@dataclass
class AllowedAttachment:
    """Allowed attachment rule.

    Attributes
    ----------
    ext: str
        File extension including leading dot (e.g., ``.txt``).
    required: bool
        Whether at least one matching attachment is required per item.
    tag_re: Optional[re.Pattern]
        Compiled regex that ``<tag>`` must match (``None`` allows any tag).
    validators: List[str]
        Optional list of hook script filenames to run for each match.
    """
    ext: str
    required: bool
    tag_re: Optional[re.Pattern]
    validators: List[str]


@dataclass
class CollectionRules:
    """Per-collection validation rules parsed from config."""
    name: str
    id_re: Optional[re.Pattern]
    allowed: List[AllowedAttachment]


def load_yaml(path: Path):
    """Load a YAML file and return the parsed Python object."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def compile_re(pat: Optional[str]) -> Optional[re.Pattern]:
    """Compile a regex string or return ``None`` if not provided."""
    if not pat:
        return None
    return re.compile(pat)


def parse_settings(settings_path: Path) -> List[CollectionRules]:
    """Parse settings config into a list of per-collection rules.

    Expected shape:
    - Mapping: ``collections: { works: {...}, persons: {...} }``
    """
    cfg = load_yaml(settings_path) or {}
    cols_raw = cfg.get("collections", {})
    rules: List[CollectionRules] = []

    def build_rules(name: str, obj: dict):
        # Normalize collection dir name to underscore form
        col_name = name
        if col_name != "*" and not col_name.startswith("_"):
            col_name = f"_{col_name}"
        id_pat = obj.get("id_pattern") or obj.get("id_patter")
        allowed_raw = obj.get("allowed_attachments", []) or []
        allowed: List[AllowedAttachment] = []
        for a in allowed_raw:
            if isinstance(a, str):
                a = {"extension": a}
            ext = (a.get("extension") or "").strip()
            if ext and not ext.startswith("."):
                ext = "." + ext
            required = bool(a.get("required", False))
            tag_re = compile_re(a.get("tag_pattern"))
            validators = list(a.get("validation_scripts", []) or [])
            allowed.append(AllowedAttachment(ext=ext.lower(), required=required, tag_re=tag_re, validators=validators))
        rules.append(CollectionRules(name=col_name, id_re=compile_re(id_pat), allowed=allowed))

    # Only dict mapping {collection_name: rules}
    if not isinstance(cols_raw, dict):
        raise ValueError("Invalid config: 'collections' must be a mapping of name -> rules")
    for key, obj in cols_raw.items():
        if not isinstance(obj, dict):
            obj = {}
        build_rules(str(key), obj)
    return rules


def find_col_rules(col_name: str, all_rules: List[CollectionRules]) -> Optional[CollectionRules]:
    """Return matching rules for a collection dir name.

    Prefers exact match (e.g., ``_works``), otherwise returns the wildcard
    rule with name ``*`` when present.
    """
    for r in all_rules:
        if r.name == col_name:
            return r
    for r in all_rules:
        if r.name == "*":
            return r
    return None


def load_item_schema(schemas_dir: Path, collection_dir_name: str) -> Optional[dict]:
    """Load the schema dict for a given collection directory if present."""
    schema_path = schemas_dir / f"{collection_dir_name}.yaml"
    if not schema_path.exists():
        return None
    return load_yaml(schema_path)


def validate_instance_with_schema(instance: dict, schema: dict, src_path: Path) -> List[str]:
    """Validate a YAML instance against a JSON Schema.

    Returns a list of human-readable error messages rather than raising.
    """
    errors: List[str] = []
    try:
        v = Draft202012Validator(schema)
        for err in v.iter_errors(instance):
            loc = ".".join(str(p) for p in err.path) or "<root>"
            errors.append(f"{src_path}: schema violation at {loc}: {err.message}")
    except Exception as e:
        errors.append(f"{src_path}: schema validation error: {e}")
    return errors


def group_items_and_attachments(col_path: Path) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Path]]:
    """Partition a collection subtree into items and attachments (recursive).

    Returns
    -------
    tuple(list, list, list)
        - items: list of {"id": <base>, "item_path": Path}
        - attachments: list of {"id": <base>, "path": Path, "tag": str, "ext": str}
        - stray: list of files that cannot be associated (no "_" in name)
    """
    items_list: List[Dict[str, object]] = []
    attachments: List[Dict[str, object]] = []
    stray: List[Path] = []
    # Walk recursively; subfolders are for user convenience only
    for p in col_path.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() == ".yaml":
            # Item identified by basename; subdir has no semantic meaning
            # Do not collapse by stem; keep duplicates for validation to catch
            items_list.append({"id": p.stem, "item_path": p})
        else:
            stem = p.stem
            if "_" not in stem:
                stray.append(p)
                continue
            base, tag = stem.split("_", 1)
            attachments.append({
                "id": base,
                "path": p,
                "tag": tag,
                "ext": p.suffix.lower(),
            })
    # Ensure a stable order for predictable downstream processing
    items_list.sort(key=lambda it: (str(it.get("id") or ""), str(it.get("item_path") or "")))
    return items_list, attachments, stray


def build_collection_map(col_path: Path, root: Path) -> List[Dict[str, object]]:
    """Return a list of item descriptors for a collection directory.

    The list items have the shape:
    {"id": "<item>", "item_path": "...", "item_data": {...}, "attachments": ["..."]}
    Paths are relative to ``root``.
    """
    items, attachments, _ = group_items_and_attachments(col_path)
    out_list: List[Dict[str, object]] = []
    for entry in items:
        base = entry.get("id")
        item_path = entry.get("item_path")
        # collect attachments for this item id (sorted by filename)
        atts_paths = [att.get("path") for att in attachments if att.get("id") == base]
        atts_paths = [p for p in atts_paths if isinstance(p, Path)]
        atts = [str(p.relative_to(root)) for p in sorted(atts_paths, key=lambda pp: pp.name)]
        try:
            data = load_yaml(item_path) if isinstance(item_path, Path) else load_yaml(Path(str(item_path)))
        except Exception as e:
            data = {"_error": f"YAML load failed: {e}"}
        out_list.append(
            {
                "id": base,
                "item_path": str((item_path if isinstance(item_path, Path) else Path(str(item_path))).relative_to(root)),
                "item_data": data,
                "attachments": atts,
            }
        )
    return out_list


def rules_to_dict(rules: Optional[CollectionRules]) -> Optional[Dict[str, object]]:
    """Convert CollectionRules to a JSON-serializable dict."""
    if rules is None:
        return None
    return {
        "name": rules.name,
        "id_pattern": (rules.id_re.pattern if rules.id_re is not None else None),
        "allowed_attachments": [
            {
                "extension": a.ext,
                "required": a.required,
                "tag_pattern": (a.tag_re.pattern if a.tag_re is not None else None),
                "validation_scripts": list(a.validators) if a.validators else [],
            }
            for a in rules.allowed
        ],
    }


def run_hook(hooks_dir: Path, script_name: str, target_path: Path) -> Tuple[bool, str]:
    """Run a validation hook script on an attachment.

    Scripts are executed as subprocesses; return (ok, message).
    """
    script_path = hooks_dir / script_name
    if not script_path.exists():
        return False, f"hook not found: {script_path}"
    try:
        res = subprocess.run([str(script_path), str(target_path)], capture_output=True, text=True, check=False)
        ok = res.returncode == 0
        out = res.stdout.strip()
        err = res.stderr.strip()
        msg = out or err
        return ok, (msg if msg else ("ok" if ok else "failed"))
    except Exception as e:
        return False, f"hook error: {e}"


def validate_collection(col_path: Path, schemas_dir: Path, rules: Optional[CollectionRules], hooks_dir: Optional[Path], run_hooks: bool) -> List[str]:
    """Validate a single collection directory.

    Applies schema validation to item YAMLs, verifies attachment linkage and
    enforcement of allowed extensions, tag patterns, and required files.
    Returns a list of error messages.
    """
    errors: List[str] = []
    schema = load_item_schema(schemas_dir, col_path.name)
    if schema is None:
        errors.append(f"{col_path}: missing schema file {schemas_dir / (col_path.name + '.yaml')}")
    items, attachments, stray = group_items_and_attachments(col_path)

    # Stray files (no underscore to bind to an item)
    for p in stray:
        errors.append(f"{p}: stray attachment name (expected <item>_<tag><ext>)")

    # If no explicit rules, allow everything but still verify pairing and schema
    allowed_by_ext: Dict[str, List[AllowedAttachment]] = {}
    id_re = None
    if rules is not None:
        id_re = rules.id_re
        for a in rules.allowed:
            allowed_by_ext.setdefault(a.ext, []).append(a)

    # Validate each item
    for entry in items:
        if not isinstance(entry, dict):
            continue
        base = entry.get("id")
        item_path = entry.get("item_path")
        # id pattern on base name
        if isinstance(base, str) and id_re and not id_re.match(base):
            errors.append(f"{item_path}: item name '{base}' does not match id pattern {id_re.pattern}")

        # schema validation if available
        if schema is not None:
            try:
                # item_path is a Path from group_items_and_attachments
                data = load_yaml(item_path if isinstance(item_path, Path) else Path(str(item_path)))
            except Exception as e:
                errors.append(f"{item_path}: cannot parse YAML: {e}")
                data = None
            if isinstance(data, dict):
                errors.extend(validate_instance_with_schema(data, schema, item_path))
            elif data is not None:
                errors.append(f"{item_path}: expected YAML object at root")

        # attachments
        att_list = [att for att in attachments if isinstance(base, str) and att.get("id") == base]
        # Index by extension and tags
        got: Dict[str, List[Tuple[str, Path]]] = {}
        for att in att_list:
            tag = att.get("tag") or ""
            p = att.get("path")
            ext = att.get("ext") or (p.suffix.lower() if isinstance(p, Path) else "")
            if not isinstance(p, Path):
                continue
            got.setdefault(str(ext), []).append((str(tag), p))

        if rules is None:
            # With no rules, only check that attachments bind to existing items (already done)
            continue

        # Check required and allowed/tag patterns
        for ext, alist in allowed_by_ext.items():
            for rule in alist:
                matches = [pp for (tag, pp) in got.get(ext, []) if (rule.tag_re.match(tag) if rule.tag_re else True)]
                if rule.required and not matches:
                    errors.append(f"{item_path}: missing required attachment ext={ext} tag_pattern={rule.tag_re.pattern if rule.tag_re else '<any>'}")
                # Validate each match with hooks if requested
                if run_hooks and hooks_dir is not None and rule.validators:
                    for _tag, pth in [(t, p) for (t, p) in got.get(ext, []) if (rule.tag_re.match(t) if rule.tag_re else True)]:
                        for script in rule.validators:
                            ok, msg = run_hook(hooks_dir, script, pth)
                            if not ok:
                                errors.append(f"{pth}: hook '{script}' failed: {msg}")

        # Disallow attachments not matching any rule
        all_allowed_exts = set(allowed_by_ext.keys())
        for ext, pairs in got.items():
            if ext not in all_allowed_exts:
                for tag, pth in pairs:
                    errors.append(f"{pth}: disallowed attachment extension '{ext}'")
                continue
            # ext is allowed, but ensure tag matches at least one rule for this ext
            tag_rules = [r for r in allowed_by_ext[ext]]
            for tag, pth in pairs:
                if not any((tr.tag_re.match(tag) if tr.tag_re else True) for tr in tag_rules):
                    errors.append(f"{pth}: tag '{tag}' does not match allowed patterns for ext '{ext}'")

    # Orphan attachments: base has no item
    item_ids = {it.get("id") for it in items if isinstance(it, dict)}
    for att in attachments:
        base = att.get("id")
        p = att.get("path")
        if base not in item_ids and isinstance(p, Path):
            errors.append(f"{p}: attachment refers to missing item '{base}'")

    return errors


def main(argv: List[str]) -> int:
    """Program entry point for collection validation CLI.

    Returns a POSIX-style exit code described in the module docstring.
    """
    ap = argparse.ArgumentParser(description="Validate underscore collections, items, and attachments")
    ap.add_argument("--root", required=True, help="Root directory that contains collections (e.g., db_sample)")
    ap.add_argument("--schemas", required=False, help="Path to schemas directory (default: <root>/schemas)")
    ap.add_argument("--config", required=False, help="Path to settings config YAML (default: <root>/config.yaml; see src/settings_schema.yaml)")
    ap.add_argument("--hooks", required=False, help="Directory with validation scripts referenced in config")
    ap.add_argument("--run-hooks", action="store_true", help="Run external validation scripts for attachments")
    ap.add_argument("--map-out", required=False, help="Path to write JSON map (default: <root>/collections.json)")
    args = ap.parse_args(argv[1:])

    root = Path(args.root).resolve()
    schemas_dir = Path(args.schemas).resolve() if args.schemas else (root / "schemas").resolve()
    hooks_dir = Path(args.hooks).resolve() if args.hooks else None

    if not root.exists() or not root.is_dir():
        print(f"Root directory not found: {root}")
        return 2
    if not schemas_dir.exists() or not schemas_dir.is_dir():
        print(f"Schemas directory not found: {schemas_dir}")
        return 2

    # Determine config path (default to <root>/config.yaml)
    cfg_path = Path(args.config).resolve() if args.config else (root / "config.yaml").resolve()
    if not cfg_path.exists():
        print(f"Config file not found: {cfg_path}")
        return 2
    rules_all = parse_settings(cfg_path)

    # Discover collections as underscore-prefixed directories
    collections = [p for p in root.iterdir() if p.is_dir() and p.name.startswith("_")]
    errors: List[str] = []

    # Build JSON map scaffold
    db_map: Dict[str, object] = {
        "root": str(root),
        "collections": {},
    }
    for col in sorted(collections, key=lambda p: p.name):
        crules = find_col_rules(col.name, rules_all)
        errors.extend(
            validate_collection(col, schemas_dir, crules, hooks_dir, bool(args.run_hooks))
        )
        # Always add to the map, regardless of validation outcome
        db_map["collections"][col.name] = {
            "collection_path": str(col.relative_to(root)),
            "rules": rules_to_dict(crules),
            "schema_path": str((schemas_dir / f"{col.name}.yaml").resolve()),
            "items": build_collection_map(col, root),
        }

    # Write JSON map
    out_path = Path(args.map_out).resolve() if args.map_out else (root / "collections.json")
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(db_map, fh, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Warning: failed to write map JSON to {out_path}: {e}")

    if errors:
        print("Collection validation failed:")
        for e in errors:
            print(f" - {e}")
        return 1
    print("Collections OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
