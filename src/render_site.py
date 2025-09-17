#!/usr/bin/env python3
"""
Render Full Site
================

Builds a combined HTML site that includes:
- Metadata pages for YAML/TXT under the DB root (via render_static)
- Relation pages per entity from the relations SQLite DB (via map_foreign_keys + render_relations)

CLI
- --root: DB root (required)
- --db: SQLite relations database (required)
- --out: output directory (default: <root>/site)
- --title: title for the metadata homepage (default: "Table of Contents")
"""
import argparse
import yaml
from pathlib import Path

import os
import json
import shutil
from jinja2 import Environment, FileSystemLoader


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Render combined metadata + relations site")
    ap.add_argument("--root", required=True, help="DB root path")
    ap.add_argument("--fkmap", required=True, help="Path to fk_rows.json produced by map_foreign_keys.py")
    ap.add_argument("--collections", required=True, help="Path to collections.json produced by validate_collections.py")
    ap.add_argument("--out", help="Output directory (default: <root>/site)")
    ap.add_argument("--title", default="Table of Contents", help="Metadata homepage title")
    return ap.parse_args(argv)


# --------------------
# Helpers (self-contained)
# --------------------

# Stylesheet is maintained in src/templates/site.css and copied to <site>/site.css

def get_target_folder_and_link(parent_table: str, child_table: str):
    parts = [p for p in child_table.split("_") if p]
    if len(parts) < 3:
        return child_table, "related"
    left_table = f"_{parts[0]}"
    relation = parts[1]
    right_table = f"_{parts[2]}"
    if parent_table == left_table:
        target = right_table
    elif parent_table == right_table:
        target = left_table
    else:
        target = left_table
    return target, relation


def build_tree(base_dir: Path) -> dict:
    tree: dict = {}
    for folder, dirs, files in os.walk(base_dir):
        rel_path = Path(folder).relative_to(base_dir)
        if not str(rel_path) or not str(rel_path).split(os.sep)[0].startswith("_"):
            continue
        current = tree
        for part in rel_path.parts:
            current = current.setdefault(part, {"yaml_files": [], "txt_files": [], "subfolders": {}})[
                "subfolders"
            ]
        yaml_files = [Path(folder) / f for f in files if f.endswith(".yaml")]
        txt_files = [Path(folder) / f for f in files if f.endswith(".txt")]
        if rel_path.parts:
            parent = tree
            for part in rel_path.parts[:-1]:
                parent = parent[part]["subfolders"]
            parent[rel_path.parts[-1]] = {"yaml_files": yaml_files, "txt_files": txt_files, "subfolders": {}}
        else:
            for f in yaml_files:
                tree.setdefault(base_dir.name, {"yaml_files": [], "txt_files": [], "subfolders": {}})["yaml_files"].append(f)
            for f in txt_files:
                tree.setdefault(base_dir.name, {"yaml_files": [], "txt_files": [], "subfolders": {}})["txt_files"].append(f)
    return tree


def main(argv=None) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Root not found: {root}")
        return 2
    fk_path = Path(args.fkmap).resolve()
    if not fk_path.exists():
        print(f"FK map not found: {fk_path}")
        return 2
    coll_path = Path(args.collections).resolve()
    if not coll_path.exists():
        print(f"Collections map not found: {coll_path}")
        return 2
    out_dir = Path(args.out).resolve() if args.out else (root / "site")

    # Tables will be direct subdirs of site root
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Obtain row-level FK map from provided JSON file
    try:
        rows_map = json.loads(fk_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to read FK map JSON: {fk_path}: {e}")
        return 2
    # Do not write fk_rows.json into the site; keep rows_map in memory only

    # 2) Build combined entity pages (metadata + relations) using collections.json
    try:
        collections_map = json.loads(coll_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to read collections JSON: {coll_path}: {e}")
        return 2

    entities: dict = {}
    for coll_name, coll_info in (collections_map.get("collections") or {}).items():
        items = coll_info.get("items") or {}
        mapped = {}
        for item_id, info in items.items():
            data = info.get("item_data")
            if data is None:
                # Keep structure predictable
                data = {}
            attachments = info.get("attachments") or []
            mapped[item_id] = {"data": data, "attachments": attachments}
        entities[coll_name] = mapped

    # Render combined pages using a simple Jinja template
    from jinja2 import Environment, FileSystemLoader
    tpl_dir = (Path(__file__).parent / "templates").resolve()
    env = Environment(loader=FileSystemLoader(str(tpl_dir)))
    combined_tmpl = env.get_template("entity.html")
    txt_template = env.get_template("txt_template.html")

    # Ensure dirs for per-table pages will be created below
    # Copy site.css from templates into the site root
    css_src = tpl_dir / "site.css"
    css_path = out_dir / "site.css"
    try:
        if css_src.exists():
            shutil.copyfile(css_src, css_path)
    except Exception:
        pass
    # Build a sidebar menu (TOC) that links to combined entity pages
    def build_entities_toc(entities_map: dict, link_prefix: str) -> str:
        parts = ["<ul class='folder-tree'>"]
        for table, items in entities_map.items():
            table_disp = table.lstrip('_')
            parts.append("<li><details><summary>" + table_disp + "</summary><ul>")
            for item_id in sorted(items.keys()):
                href = f"{link_prefix}{table_disp}/{item_id}.html"
                parts.append(f"<li><a href='{href}'>{item_id}</a></li>")
            parts.append("</ul></details></li>")
        parts.append("</ul>")
        return "\n".join(parts)

    toc_for_index = build_entities_toc(entities, "")
    toc_for_entries = build_entities_toc(entities, "../")

    for table, items in entities.items():
        table_disp = table.lstrip('_')
        tdir = out_dir / table_disp
        tdir.mkdir(parents=True, exist_ok=True)
        rels_for_table = rows_map.get(table, {})
        for item_id, info in items.items():
            metadata = info["data"]
            attachments = info["attachments"]
            relations = []
            for rel_table, target_items in rels_for_table.get(item_id, {}).items():
                target_table, relation = get_target_folder_and_link(table, rel_table)
                target_table = target_table.lstrip('_')
                relations.append({
                    "target_table": target_table,
                    "relation_nature": relation,
                    "target_items": target_items,
                })
            content_html = combined_tmpl.render(
                table=table_disp,
                item_id=item_id,
                metadata=metadata,
                attachments=attachments,
                relations=relations,
            )
            # From <site>/<table>/<id>.html back to <site>/index.html
            page_html = txt_template.render(content=content_html, toc_html=toc_for_entries, homepage=False, home_href='../index.html', css_href='../site.css')
            (tdir / f"{item_id}.html").write_text(page_html, encoding="utf-8")
    # Index page using the same menu/sidebar layout
    index_content = "<h1>Entities</h1>"
    index_html = txt_template.render(content=index_content, toc_html=toc_for_index, homepage=False, home_href='index.html', css_href='site.css')
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")

    print(f"Entity pages written under {out_dir}; index at {out_dir/'index.html'}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
