import os, sys
from pathlib import Path
from collections import Counter
import re
import yaml
import json
from jsonschema import validate, ValidationError
from pprint import pprint

class Violation:
    def __init__(self, file, check, message, severity="error"):
        self.file = file
        self.check = check
        self.message = message
        self.severity = severity

    def to_dict(self):
        """Convert to a dictionary for JSON export or serialization."""
        return {
            "file": self.file,
            "check": self.check,
            "severity": self.severity,
            "message": self.message
        }

    def __repr__(self):
        """Human-readable format for printing."""
        return f"{self.check}: {self.file} — {self.message}"


def load_rules(config_file):
    with open(config_file) as f:
        return yaml.safe_load(f)

def get_all_files(root_dir):
    filepaths = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            filepaths.append(os.path.join(dirpath, filename))
    return filepaths

# def check_allowed_text_extensions(file_path, rules):
#     violations = []
#     allowed = rules["allowed_text_extensions"]
#     if not file_path.endswith(tuple(allowed)):
#         violations.append(Violation(
#             file=file_path,
#             check="File extension",
#             message=f"Invalid extension. Allowed: {', '.join(allowed)}",
#             severity="error"
#         ))
#     return violations

# def check_allowed_author_extensions(file_path, rules):
#     violations = []
#     allowed = rules["allowed_author_extensions"]
#     if not file_path.endswith(tuple(allowed)):
#         violations.append(Violation(
#             file=file_path,
#             check="File extension",
#             message=f"Invalid extension. Allowed: {', '.join(allowed)}",
#             severity="error"
#         ))
#     return violations

def report_violations(violations):
    violations = [item for sublist in violations for item in sublist]
    if not violations:
        print("✅ All checks passed.")
        return
    print(f"❌ violations found:")
    for v in violations:
        print(str(v))

# def run_all_checks(file_path, rules):
#     violations = []
#     for name, func in globals().items():
#         if name.startswith("check_") and callable(func):
#             rule_name = name.replace("check_", "")
#             if rule_name in rules:
#                 violations.extend(func(file_path, rules))
#     return violations

import os

def check_filenames_multiple_dots(file_list):
    """
    Check if any filename has more than one dot.
    
    Args:
        file_list (list of str): List of file paths or filenames.
    
    Returns:
        list of str: Filenames that have more than one dot.
    """
    violations = []
    for filepath in file_list:
        filename = os.path.basename(filepath)
        # Count dots in filename (excluding leading dot for hidden files)
        # Example: '.env' has one dot but is hidden file, so we consider only dots after first char
        dots_count = filename.count('.')
        if filename.startswith('.'):
            dots_count -= 1  # ignore leading dot for hidden files

        if dots_count > 1:
            violations.append(Violation(
                file=filepath,
                check="Filename multiple dots",
                message=f"Filename '{filename}' contains more than one dot.",
                severity="error"
            ))
    return violations

def check_filename_pattern(file_path, pattern):
    """
    Check if the file name matches a regex pattern.
    Args:
        file_path (str): Full path to the file.
        rules (dict): Contains the rule parameters for this check.
    Returns:
        list[dict]: List of violations (empty if none).
    """
    violations = []

    if not re.match(pattern, os.path.basename(file_path)):
        violations.append(Violation(
            file = file_path,
            check = "Filename pattern",
            severity = "error",
            message = f"Filename does not match pattern: {pattern}"
        ))

    return violations

def check_unique_ids(id_list):
    violations = []
    counts = Counter(id_list)
    non_unique = [item for item, count in counts.items() if count > 1]
    print(f'{non_unique = }')
    return Violation(
            file = "",
            check = "Non-Uniqu ID",
            severity = "error",
            message = f"Repeating IDs found: {non_unique}"
        )


def find_has_foreign_keys(collections: dict):
    for collection_key, docs_dict in collections.items():
        docs_dict["__has_foreign_keys"] = []
        #TODO: check of self reference
        other_collection_keys = [k for k, _ in collections.items() if k != collection_key]
        for ok in other_collection_keys:
            if "properties" in docs_dict["__validation_schema"] and ok in docs_dict["__validation_schema"]["properties"]:
                docs_dict["__has_foreign_keys"].append(ok)
                print(f">>> For {collection_key} foreign key {ok} found!")


def find_is_foreign_keys(collections: dict):
    for collection_key, docs_dict in collections.items():
        docs_dict["__is_foreign_key_in"] = []
    for collection_key, docs_dict in collections.items():
        for fk in docs_dict["__has_foreign_keys"]:
            collections[fk]["__is_foreign_key_in"].append(collection_key)


def find_mentions(collections: dict):
    for collection_key, docs_dict in collections.items():#authors
        docs_dict["__mentioned_in"] = {}
        for primary in docs_dict:#js
            if not primary.startswith("__"):    
                docs_dict[primary]["__mentioned_in"] = dict()
                for other_collection in docs_dict["__is_foreign_key_in"]:#works
                    docs_dict[primary]["__mentioned_in"][other_collection] = []
                    for doc in collections[other_collection]:#iv
                        if not doc.startswith("__") and primary in collections[other_collection][doc][collection_key]:
                            docs_dict[primary]["__mentioned_in"][other_collection].append(doc)


def main(db_root: Path):
    rules = load_rules(db_root / "config.yaml")
    all_violations = []

    collection_name_pattern = "_[a-z]{2,255}"
    collections = dict()
    collection_dirs = [dir for dir in db_root.iterdir() if dir.is_dir() and re.match(collection_name_pattern, str(dir.name))]
    for dir in collection_dirs:

        collections[dir.name] = dict()
        with open(db_root / "schemas" / (dir.name + ".yaml")) as f:
            validation_schema = yaml.safe_load(f)
        collections[dir.name]["__validation_schema"] = validation_schema
        for doc in dir.rglob("*.yaml"):

            with open(doc) as f:
                data = yaml.safe_load(f)
            try:
                validate(instance=data, schema=validation_schema)
                collections[dir.name][doc.stem] = data
                collections[dir.name][doc.stem]["path"] = str(doc.relative_to(db_root))
            except ValidationError as e:
                print(f"❌ Validation error: {doc}", e.message)

    find_has_foreign_keys(collections)
    find_is_foreign_keys(collections)

    find_mentions(collections)

    pprint(collections, sort_dicts=True, indent=4, width=60)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <directory>")
        sys.exit(1)
    main(Path(sys.argv[1]))