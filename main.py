import os
from pathlib import Path
from collections import Counter
import re
import yaml
import json
from jsonschema import validate, ValidationError

all_violations = []

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

def main():
    rules = load_rules("config.yaml")
    violations = []

    text_dir_files = get_all_files(rules["texts_dir"])
    work_meta_files = [file for file in text_dir_files if Path(file).suffix == "." + rules["work_meta_extensions"]]

    work_cont_files = [file for file in text_dir_files if Path(file).suffix != "." + rules["work_meta_extensions"]]

    auth_dir_files = get_all_files(rules["auth_dir"])
    auth_meta_files = [file for file in auth_dir_files if Path(file).suffix == "." + rules["auth_meta_extensions"]]

    print(text_dir_files, work_meta_files, auth_meta_files)

    for filelist in text_dir_files, auth_dir_files:
        all_violations.append(check_filenames_multiple_dots(filelist))

    for work_meta in work_meta_files:
        all_violations.append(check_filename_pattern(work_meta, rules["work_meta"]["filename_pattern"]))

    for auth_meta in auth_meta_files:
        all_violations.append(check_filename_pattern(auth_meta, rules["auth_meta"]["filename_pattern"]))

    work_ids = [Path(w).stem for w in work_meta_files]
    auth_ids = [Path(w).stem for w in auth_meta_files]
    all_violations.append([check_unique_ids(work_ids)])
    all_violations.append([check_unique_ids(auth_ids)])

    with open("schemas/author.yaml") as f:
        auth_schema = yaml.safe_load(f)

    for file in auth_meta_files:
        author_id = Path(file).stem
        with open(file) as f:
            author_data = yaml.safe_load(f)
        try:
            validate(instance=author_data, schema=auth_schema)
        except ValidationError as e:
            print(f"❌ Validation error: {file}", e.message)

    with open("schemas/work.yaml") as f:
        work_schema = yaml.safe_load(f)
    for file in work_meta_files:
        work_id = Path(file).stem
        with open(file) as f:
            work_data = yaml.safe_load(f)
        try:
            validate(instance=work_data, schema=work_schema)
        except ValidationError as e:
            print(f"❌ Validation error: {file}", e.message)

    for work_cont in work_cont_files:
        all_violations.append(check_filename_pattern(work_cont, rules["work_cont"]["filename_pattern"]))

    report_violations(all_violations)

if __name__ == "__main__":
    main()