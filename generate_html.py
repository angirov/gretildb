import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import sys

def get_target_folder_and_link(parent_table, child_table):
    """
    Determine the target folder for a link based on the parent table.

    Rules:
    - child_table always has 3 parts: _left_relation_right
    - left and right are primary tables
    - middle is the relationship descriptor
    """
    parts = child_table.split("_")
    # Filter out empty strings caused by leading underscores
    parts = [p for p in parts if p]

    left_table = f"_{parts[0]}"
    right_table = f"_{parts[2]}"
    link = f"_{parts[1]}"

    if parent_table == left_table:
        target = right_table
    elif parent_table == right_table:
        target = left_table
    else:
        # Safety fallback: just return left_table
        target = left_table
    return target, link


def generate_html_jinja(result, base_dir):
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader("html_templates"))  # assumes templates in current dir
    entity_template = env.get_template("entity_template.html")
    # index_template = env.get_template("html_templates/index.html")

    # Step 1: generate entity pages
    for table, rows in result.items():
        table_dir = base_dir / table
        table_dir.mkdir(exist_ok=True)
        for row_id, relations in rows.items():
            page_dict = {}
            page_dict["title"] = row_id
            page_dict["relations"] = []
            for relection, target_items in relations.items():
                relation_dict = {}
                relation_dict["target_table"], relation_dict["relation_nature"] = get_target_folder_and_link(table, relection)
                relation_dict["target_items"] = target_items
                page_dict["relations"].append(relation_dict)
            html_output = entity_template.render(entity=page_dict)

            # Save HTML
            with open(f"{table_dir}/{row_id}.html", "w", encoding="utf-8") as f:
                f.write(html_output)

            # Save JSON
            with open(f"{table_dir}/{row_id}.json", "w", encoding="utf-8") as f:
                json.dump(page_dict, f, ensure_ascii=False, indent=4)


    # Step 2: generate index page
    index_dict = {}
    for table, rows in result.items():
        index_dict[table] = []
        for row_id in rows:
            index_dict[table].append(row_id)
    print(json.dumps(index_dict, indent=2))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_html_jinja.py <mapping.json> <output_folder>")
        sys.exit(1)

    json_file = sys.argv[1]
    output_dir = sys.argv[2]

    with open(json_file, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    generate_html_jinja(mapping, output_dir)
    print(f"HTML generation completed in folder: {output_dir}")
