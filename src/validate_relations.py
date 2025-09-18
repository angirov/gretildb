#!/usr/bin/env python3
"""
Validate Relations (SQLite build)
================================

Reads a collections map (produced by src/validate_collections.py), then builds
an in-memory SQLite database to model collections and their relations. It
reports all issues found (naming, missing schemas/IDs, insert/constraint
errors) and continues building to reveal as many problems as possible.

Validations
- Identifier safety: collections and inferred join-table names use only
  lowercase letters, digits, dashes and underscores.
- Schema relations: infers foreign-key relations from each collection's schema
  (looks for properties named after other collections, then their nested
  properties as relation names). Validates that each referenced ID exists in
  the target collection.

SQLite Notes
- Quoting: SQLite allows dashes in identifiers when double-quoted (e.g.,
  "my-table"). This validator enforces a conservative name policy
  ("[a-z0-9_-]") so names are predictable; you should still quote identifiers
  when generating SQL if they contain dashes.
- Case: Identifiers are case-insensitive in SQLite by default; prefer lower-case
  for consistency.
- Reserved words: If you use a reserved word as an identifier, quote it
  consistently when generating SQL.
- SQL injection: Identifiers cannot be parameterized; validate names strictly
  and only parameterize values.
- Join-table naming: Names are built as "<left>__<relation>__<right>" to avoid
  ambiguity.

CLI
- --map-in: path to JSON map from validate_collections (required)
- --dump-sql: optional path to write a SQL dump of the in-memory DB
- --db-out [PATH]: override the output SQLite DB path. By default, the
  script writes the DB to 'db.sqlite' next to the map file.

Exit codes
- 0: all checks passed
- 1: violations found
- 2: setup or input error
"""
import argparse
import json
import re
import sqlite3
from sqlite3 import IntegrityError
import sys
from pathlib import Path
from typing import Dict, List

import yaml


# Conservative identifier policy for SQLite to keep names predictable and to
# reduce accidental SQL-injection risk via identifiers.
SAFE_IDENT_RE = re.compile(r"^[a-z0-9_-]+$")


def load_map(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"Failed to load map JSON: {path}: {e}")


def load_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"Failed to load YAML: {path}: {e}")


def join_table_name(left: str, relation: str, right: str) -> str:
    """Build a clear, unambiguous join-table name for SQLite.

    Uses "<left>__<relation>__<right>" to avoid collisions with simple
    concatenation.
    """
    return f"{left}__{relation}__{right}"


def quote_ident(name: str) -> str:
    """Quote an SQL identifier for SQLite using double quotes.

    Any embedded double quotes are doubled per SQL rules.
    """
    return '"' + str(name).replace('"', '""') + '"'


def join_column_names(left: str, right: str) -> (str, str):
    """Return (left_col, right_col) names for a join table.

    Disambiguates self-referential joins by using src/dst suffixes to avoid
    duplicate column names.
    """
    if left == right:
        return f"{left}_src_id", f"{right}_dst_id"
    return f"{left}_id", f"{right}_id"


def infer_relations_from_schema(schema: dict, collection_names: List[str]) -> Dict[str, List[str]]:
    """Return mapping foreign-collection -> list of relation names.

    A relation is inferred when the schema has a property named after another
    collection (e.g., "_persons"), whose nested "properties" keys define the
    relation names (e.g., "_composed-by").
    """
    rels: Dict[str, List[str]] = {}
    props = schema.get("properties") or {}
    for fk in props.keys():
        if fk in collection_names:
            subprops = props.get(fk, {}).get("properties") or {}
            relation_names = list(subprops.keys())
            if relation_names:
                rels[fk] = relation_names
    return rels


def validate_relations(map_data: dict) -> List[str]:
    """Validate via actual in-memory SQLite build.

    - Creates primary tables for each collection (id TEXT PRIMARY KEY)
    - Infers relations from schemas and creates join tables
    - Inserts items and join rows, reporting but not halting on errors
    """
    errors: List[str] = []
    coll_entries = map_data.get("collections") or []
    # Normalize and extract collection names as a list
    coll_names = [
        c.get("name")
        for c in coll_entries
        if isinstance(c, dict) and isinstance(c.get("name"), str)
    ]

    # Build quick lookup: ids per collection and item paths
    ids_by_coll: Dict[str, set] = {}
    path_by_coll_id: Dict[str, Dict[str, str]] = {}
    for cent in coll_entries:
        if not isinstance(cent, dict):
            continue
        cname = cent.get("name")
        if not isinstance(cname, str) or not cname:
            continue
        items = cent.get("items") or []
        # items is a list of objects with an 'id' field
        ids_by_coll[cname] = set(
            it.get("id") for it in items if isinstance(it, dict) and isinstance(it.get("id"), str)
        )
        path_by_coll_id[cname] = {
            it.get("id"): it.get("item_path", "")
            for it in items
            if isinstance(it, dict) and isinstance(it.get("id"), str)
        }

    # Connect to in-memory SQLite and enable FK enforcement
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception as e:
        return [f"Failed to initialize SQLite in-memory DB: {e}"]

    # Identifier checks and relation inference per collection
    rel_spec_by_coll: Dict[str, Dict[str, List[str]]] = {}
    for cent in coll_entries:
        if not isinstance(cent, dict):
            continue
        cname = cent.get("name")
        if not isinstance(cname, str) or not cname:
            continue
        if not SAFE_IDENT_RE.match(cname):
            errors.append(f"Collection name not RDBMS-safe: {cname} (allowed: [a-z0-9_-])")

        schema_path = cent.get("schema_path")
        if not schema_path:
            errors.append(f"{cname}: missing schema_path in map")
            continue
        schema = load_yaml(Path(schema_path))
        rel_spec = infer_relations_from_schema(schema, coll_names)
        rel_spec_by_coll[cname] = rel_spec

        # Validate join-table identifier constraints (character policy)
        for fk, rnames in rel_spec.items():
            for rname in rnames:
                jn = join_table_name(cname, rname, fk)
                if not SAFE_IDENT_RE.match(jn):
                    errors.append(f"Join table name not SQLite-safe: {jn}")

    # Create primary tables
    for cname in coll_names:
        try:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {quote_ident(cname)} ("
                f"{quote_ident('id')} TEXT PRIMARY KEY)"
            )
        except Exception as e:
            errors.append(f"CREATE TABLE failed for {cname}: {e}")

    # Create join tables
    created_join = set()
    for left, rel_spec in rel_spec_by_coll.items():
        for right, rnames in rel_spec.items():
            for rname in rnames:
                jn = join_table_name(left, rname, right)
                if jn in created_join:
                    continue
                left_col, right_col = join_column_names(left, right)
                sql = (
                    f"CREATE TABLE IF NOT EXISTS {quote_ident(jn)} ("
                    f"{quote_ident(left_col)} TEXT,"
                    f"{quote_ident(right_col)} TEXT,"
                    f"PRIMARY KEY ({quote_ident(left_col)}, {quote_ident(right_col)}),"
                    f"FOREIGN KEY ({quote_ident(left_col)}) REFERENCES {quote_ident(left)}({quote_ident('id')}),"
                    f"FOREIGN KEY ({quote_ident(right_col)}) REFERENCES {quote_ident(right)}({quote_ident('id')})"
                    f")"
                )
                try:
                    conn.execute(sql)
                    created_join.add(jn)
                except Exception as e:
                    errors.append(f"CREATE JOIN TABLE failed for {jn}: {e}")

    # Commit DDL before inserts to ensure a consistent snapshot
    try:
        conn.commit()
    except Exception:
        pass

    # Insert items
    for cent in coll_entries:
        if not isinstance(cent, dict):
            continue
        cname = cent.get("name")
        if not isinstance(cname, str) or not cname:
            continue
        items = cent.get("items") or []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            item_id = entry.get("id")
            if not isinstance(item_id, str) or not item_id:
                errors.append(f"{cname}: item missing string 'id' in map")
                continue
            try:
                conn.execute(
                    f"INSERT INTO {quote_ident(cname)} ({quote_ident('id')}) VALUES (?)",
                    (item_id,),
                )
            except IntegrityError as e:
                # Duplicate item id within the same collection
                errors.append(f"{cname}/{item_id}: duplicate item id (PRIMARY KEY violation): {e}")
            except Exception as e:
                errors.append(f"INSERT item failed for {cname}/{item_id}: {e}")

    # Insert relations
    for cent in coll_entries:
        if not isinstance(cent, dict):
            continue
        left = cent.get("name")
        if not isinstance(left, str) or not left:
            continue
        rel_spec = rel_spec_by_coll.get(left, {})
        items = cent.get("items") or []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            item_id = entry.get("id")
            if not isinstance(item_id, str) or not item_id:
                # Already reported above during insert loop; skip
                continue
            item_data = entry.get("item_data") or {}
            item_path = entry.get("item_path") or f"{left}/{item_id}.yaml"
            for right, rnames in rel_spec.items():
                block = item_data.get(right)
                if not isinstance(block, dict):
                    # optional block missing is acceptable
                    continue
                for rname in rnames:
                    links = block.get(rname)
                    if links is None:
                        continue
                    if not isinstance(links, list):
                        errors.append(f"{item_path}: relation '{right}.{rname}' must be a list of links")
                        continue
                    jn = join_table_name(left, rname, right)
                    left_col, right_col = join_column_names(left, right)
                    # Ensure join table exists even if schema inference missed it
                    if jn not in created_join:
                        try:
                            sql = (
                                f"CREATE TABLE IF NOT EXISTS {quote_ident(jn)} ("
                                f"{quote_ident(left_col)} TEXT,"
                                f"{quote_ident(right_col)} TEXT,"
                                f"PRIMARY KEY ({quote_ident(left_col)}, {quote_ident(right_col)}),"
                                f"FOREIGN KEY ({quote_ident(left_col)}) REFERENCES {quote_ident(left)}({quote_ident('id')}),"
                                f"FOREIGN KEY ({quote_ident(right_col)}) REFERENCES {quote_ident(right)}({quote_ident('id')})"
                                f")"
                            )
                            conn.execute(sql)
                            created_join.add(jn)
                        except Exception as e:
                            errors.append(f"CREATE JOIN TABLE (on demand) failed for {jn}: {e}")
                            # If we can't create the join table, skip inserts for this relation
                            continue
                    for idx, link in enumerate(links):
                        if not isinstance(link, dict):
                            errors.append(f"{item_path}: relation '{right}.{rname}' entry #{idx+1} must be an object")
                            continue
                        ref_id = link.get("id")
                        if not isinstance(ref_id, str) or not ref_id:
                            errors.append(f"{item_path}: relation '{right}.{rname}' entry #{idx+1} missing string id")
                            continue
                        # Pre-check reference existence to avoid FK errors; still attempt insert if configured
                        if ref_id not in ids_by_coll.get(right, set()):
                            errors.append(
                                f"{item_path}: relation '{right}.{rname}' references missing id '{ref_id}' in {right}"
                            )
                            # Skip insert to avoid FK error
                            continue
                        try:
                            conn.execute(
                                f"INSERT INTO {quote_ident(jn)} ("
                                f"{quote_ident(left_col)}, {quote_ident(right_col)}) VALUES (?, ?)",
                                (item_id, ref_id),
                            )
                        except IntegrityError as e:
                            # Duplicate edge between the same two items for this relation
                            errors.append(
                                f"{item_path}: duplicate relation in {jn} ({item_id}, {ref_id}) — {e}"
                            )
                        except Exception as e:
                            errors.append(
                                f"{item_path}: SQL error inserting relation into {jn} ({item_id}, {ref_id}): {e}"
                            )

    # Commit all inserts before any dump/backup so external snapshots include data
    try:
        conn.commit()
    except Exception:
        pass

    # To allow dumping/exporting later, store connection on a hidden attribute.
    validate_relations._last_conn = conn  # type: ignore[attr-defined]

    return errors


def parse_args(argv: List[str]):
    ap = argparse.ArgumentParser(description="Build an in-memory SQLite DB from a collections map and report issues")
    ap.add_argument("--map-in", required=True, help="Path to JSON map generated by validate_collections")
    ap.add_argument("--dump-sql", help="Optional path to write SQL dump of the in-memory DB")
    ap.add_argument("--db-out", nargs="?", const="db.sqlite", help="Write SQLite DB file; if omitted, writes to 'db.sqlite' next to the map")
    return ap.parse_args(argv[1:])


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    map_path = Path(args.map_in)
    if not map_path.exists():
        print(f"Map file not found: {map_path}")
        return 2
    data = load_map(map_path)

    errors = validate_relations(data)
    if errors:
        print("Relation validation failed:")
        for e in errors:
            print(f" - {e}")
        # continue to dump/export even on errors
    else:
        print("Relations OK")

    # Dump SQL if requested
    if args.dump_sql:
        conn = getattr(validate_relations, "_last_conn", None)
        if conn is None:
            print("Warning: internal connection not available for dump")
        else:
            try:
                out_path = Path(args.dump_sql)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    for line in conn.iterdump():
                        f.write(f"{line}\n")
                print(f"Wrote SQLite dump to {out_path}")
            except Exception as e:
                print(f"Warning: failed to write dump: {e}")

    # Always write DB file (even if there were errors)
    conn = getattr(validate_relations, "_last_conn", None)
    if conn is None:
        print("Warning: internal connection not available for DB export")
    else:
        try:
            # Use provided path or default to 'db.sqlite' next to the map
            db_path = Path(args.db_out) if args.db_out else (map_path.parent / "db.sqlite")
            if args.db_out and not db_path.is_absolute():
                # If user passed just a filename, anchor it next to the map.
                # If a relative path with directories was provided, respect it as-is.
                if db_path.parent == Path('.'):
                    db_path = map_path.parent / db_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(db_path)) as disk:
                conn.backup(disk)
            print(f"Wrote SQLite database to {db_path}")
        except Exception as e:
            print(f"Warning: failed to write SQLite DB: {e}")

    # Close connection if open
    conn = getattr(validate_relations, "_last_conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
