#!/usr/bin/env python3
"""
Map Foreign Keys (rows view only)
=================================

Introspects a SQLite database and emits JSON:
parent_table -> parent_value -> child_table -> [other_fk_values]

Use this to see, for each specific parent id, which other ids co-occur with it
in child rows (e.g., in join tables with two FKs).

CLI
- --db PATH: input SQLite database (required)
- --out PATH: output JSON file (default: <db_dir>/fk_rows.json)
- --minify: write compact JSON
"""
import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict


def quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def map_row_references(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]

    result = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for table in tables:
        cur.execute(f"PRAGMA foreign_key_list({quote_ident(table)})")
        fks = cur.fetchall()
        if not fks:
            continue

        fk_cols = [(from_col, parent_table) for _, _, parent_table, from_col, _, *_ in fks]
        cols = ", ".join(quote_ident(col) for col, _ in fk_cols)
        cur.execute(f"SELECT {cols} FROM {quote_ident(table)}")
        for row in cur.fetchall():
            row_map = dict(zip([c for c, _ in fk_cols], row))
            for col, parent_table in fk_cols:
                parent_value = row_map[col]
                if parent_value is None:
                    continue
                for other_col, _ in fk_cols:
                    if other_col == col:
                        continue
                    other_value = row_map[other_col]
                    if other_value is not None:
                        result[parent_table][parent_value][table].append(other_value)

    return result


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Emit row-level FK co-occurrence map from a SQLite DB")
    ap.add_argument("--db", required=True, help="Path to SQLite database file")
    ap.add_argument("--out", help="Output JSON path (default: <db_dir>/fk_rows.json)")
    ap.add_argument("--minify", action="store_true", help="Write compact JSON")
    return ap.parse_args(argv)


def main(argv) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 2
    out_path = Path(args.out) if args.out else (db_path.parent / "fk_rows.json")

    conn = sqlite3.connect(str(db_path))
    try:
        data = map_row_references(conn)
    finally:
        conn.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        if args.minify:
            json.dump(data, f, separators=(",", ":"))
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote row-level FK map to {out_path}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))

