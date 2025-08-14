import os
import sys
import yaml
from pathlib import Path
from jinja2 import Template, Environment, FileSystemLoader
from pprint import pprint

def build_tree(base_dir):
    tree = {}
    for folder, dirs, files in os.walk(base_dir):
        rel_path = Path(folder).relative_to(base_dir)
        if not str(rel_path).startswith("_"):
            continue
        current = tree
        # Walk into nested dicts based on path parts
        for part in rel_path.parts:
            current = current.setdefault(part, {"yaml_files": [], "txt_files": [], "subfolders": {}})["subfolders"]
        yaml_files = [Path(folder) / f for f in files if f.endswith(".yaml")]
        txt_files = [Path(folder) / f for f in files if f.endswith(".txt")]
        if rel_path.parts:
            parent = tree
            for part in rel_path.parts[:-1]:
                parent = parent[part]["subfolders"]
            parent[rel_path.parts[-1]] = {
                "yaml_files": yaml_files,
                "txt_files": txt_files,
                "subfolders": {}
            }
        else:
            for f in yaml_files:
                tree.setdefault(base_dir.name, {"yaml_files": [], "txt_files": [], "subfolders": {}})["yaml_files"].append(f)
            for f in txt_files:
                tree.setdefault(base_dir.name, {"yaml_files": [], "txt_files": [], "subfolders": {}})["txt_files"].append(f)
    return tree

def load_template(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return Template(f.read())

def main(directory):
    directory = Path(directory)
    if not directory.is_dir():
        print(f"Error: {directory} is not a directory")
        sys.exit(1)

    # Load templates from files in the same directory as script
    template_dir = Path(__file__).parent
    template_env = Environment(loader=FileSystemLoader("static"))
    toc_template = template_env.get_template("toc_template.html")
    txt_template = template_env.get_template("txt_template.html")
    yaml_template = template_env.get_template("yaml_template.html")


    txt_files = sorted(f for f in directory.rglob("*.txt"))
    if not txt_files:
        print("No .txt files found in directory")
        sys.exit(1)

    yaml_files = sorted(f for f in directory.rglob("*.yaml"))
    if not yaml_files:
        print("No .yaml files found in directory")
        sys.exit(1)

    output_directory = Path(directory).parent / "output"
    output_directory.mkdir(exist_ok=True)
    # title = output_directory.name
    tree = build_tree(directory)
    toc_html = toc_template.render(tree=tree)

    # Create HTML for each TXT file
    for file in txt_files:
        with open(file, "r", encoding="utf-8") as f:
            text_content = f.read()
        file_html = txt_template.render(content=f"<h1>{file.stem}</h1><pre>{text_content}</pre>", toc_html=toc_html, homepage=False)
        with open(output_directory / f"{file.stem}.html", "w", encoding="utf-8") as f:
            f.write(file_html)

    # Create HTML for each YAML file
    for file in yaml_files:
        attachments = [txt.stem for txt in txt_files if (txt.stem).startswith(file.stem)] #TODO: not robust for ids with overlapping beginnings
        with open(file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        yaml_html = yaml_template.render(title="Metadata", data=data, attachments=attachments)
        file_html = txt_template.render(content=f"<h1>{file.stem}</h1><pre>{yaml_html}</pre>", toc_html=toc_html, homepage=False)
        
        with open(output_directory / f"{file.stem}.html", "w", encoding="utf-8") as f:
            f.write(file_html)

    # Create index.html
    index_html = txt_template.render(content="<h1>Table of Contents</h1>"+toc_html, toc_html=toc_html, title="GRETIL", homepage=True)
    with open(output_directory / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <directory>")
        sys.exit(1)
    main(sys.argv[1])