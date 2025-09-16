import sqlite3
from collections import defaultdict
import json
import sys


def quote_ident(name: str) -> str:
    """Quote an SQL identifier for SQLite (double quotes, escape embedded quotes)."""
    return '"' + str(name).replace('"', '""') + '"'

def map_foreign_keys(conn):
    """
    Build a dictionary mapping (referenced_table, referenced_column)
    -> list of (referencing_table, referencing_column).
    """
    cursor = conn.cursor()

    # get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    fk_map = {}

    for table in tables:
        cursor.execute(f"PRAGMA foreign_key_list({quote_ident(table)})")
        for fk in cursor.fetchall():
            # fk format: (id, seq, table, from, to, on_update, on_delete, match)
            _, _, ref_table, from_col, to_col, *_ = fk
            key = (ref_table, to_col)
            if key not in fk_map:
                fk_map[key] = []
            fk_map[key].append((table, from_col))

    return fk_map

def map_row_references(conn):
    """
    Build mapping:
    parent_table -> parent_value -> child_table -> [other_fk_values]
    
    Assumes:
      - foreign key columns are named <table>_id
      - every table has at least one FK (linking tables may have several)
    """
    cursor = conn.cursor()

    # get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    result = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for table in tables:
        cursor.execute(f"PRAGMA foreign_key_list({quote_ident(table)})")
        fks = cursor.fetchall()
        if not fks:
            continue

        fk_cols = [(from_col, parent_table) for _, _, parent_table, from_col, _, *_ in fks]

        # dynamically build SELECT with all fk cols
        cols = ", ".join(quote_ident(col) for col, _ in fk_cols)
        cursor.execute(f"SELECT {cols} FROM {quote_ident(table)}")
        for row in cursor.fetchall():
            row = dict(zip([c for c, _ in fk_cols], row))

            # for each parent fk in this row
            for col, parent_table in fk_cols:
                parent_value = row[col]
                if parent_value is None:
                    continue

                # collect all the *other* fk values from this row
                for other_col, other_parent_table in fk_cols:
                    if other_col == col:
                        continue
                    other_value = row[other_col]
                    if other_value is not None:
                        result[parent_table][parent_value][table].append(other_value)

    return result

if __name__ == "__main__":
    # check for -m flag
    minify = False
    args = sys.argv[1:]
    if "-m" in args:
        minify = True
        args.remove("-m")

    if len(args) != 2:
        print("Usage: python script.py [-m] <database_file> <output_json_file>")
        sys.exit(1)

    db_file = args[0]
    out_file = args[1]

    conn = sqlite3.connect(db_file)
    result = map_row_references(conn)
    conn.close()

    # write JSON
    with open(out_file, "w", encoding="utf-8") as f:
        if minify:
            json.dump(result, f, separators=(',', ':'))
        else:
            json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"JSON written to {out_file} (minified={minify})")
