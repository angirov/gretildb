import subprocess
import sys
from pathlib import Path
import tempfile
import unittest


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def make_min_collection_tree(root: Path):
    # schemas
    write(root / "schemas" / "_works.yaml", "type: object\nadditionalProperties: true\n")
    # collection dir
    (root / "_works").mkdir(parents=True, exist_ok=True)
    # item yaml
    write(root / "_works" / "mybook.yaml", "title: Test\n")
    # attachments
    write(root / "_works" / "mybook_ver1.txt", "ok")
    write(root / "_works" / "mybook_final.pdf", "ok")


def make_config(path: Path):
    cfg = """
collections:
  works:
    id_pattern: "^[a-z0-9-]{2,64}$"
    allowed_attachments:
      - extension: txt
        required: true
        tag_pattern: "^ver[0-9]+$"
      - extension: pdf
        tag_pattern: "^(draft|final)$"
"""
    write(path, cfg)


class TestValidateCollections(unittest.TestCase):
    def test_validate_collections_ok(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            make_min_collection_tree(base)
            cfg_path = base / "config.yaml"
            make_config(cfg_path)
            res = run([sys.executable, "src/validate_collections.py", "--root", str(base), "--schemas", str(base / "schemas"), "--config", str(cfg_path)])
            self.assertEqual(res.returncode, 0, msg=res.stdout + "\n" + res.stderr)
            self.assertIn("Collections OK", res.stdout)


    def test_validate_collections_stray_attachment(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            make_min_collection_tree(base)
            # Add a stray file that lacks the '<item>_' boundary
            write(base / "_works" / "lonely.txt", "oops")
            cfg_path = base / "config.yaml"
            make_config(cfg_path)
            res = run([sys.executable, "src/validate_collections.py", "--root", str(base), "--schemas", str(base / "schemas"), "--config", str(cfg_path)])
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("stray attachment name", res.stdout)


if __name__ == "__main__":
    unittest.main()
