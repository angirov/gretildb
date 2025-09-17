import subprocess
import sys
from pathlib import Path
import tempfile
import unittest


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def make_min_fs(root: Path):
    (root / "README.md").write_text("sample", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "schemas").mkdir()
    # minimal allowed schema filename
    (root / "schemas" / "_works.yaml").write_text("type: object\nadditionalProperties: true\n", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts" / "README.md").write_text("scripts", encoding="utf-8")
    (root / "scripts" / "tool.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    # underscore collections are globally ignored by the FS validator
    (root / "_works").mkdir()


class TestValidateFS(unittest.TestCase):
    def test_validate_fs_ok(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            make_min_fs(base)
            res = run([sys.executable, "src/validate_fs.py", "--root", str(base), "--spec", "src/fs_spec.yaml"])
            self.assertEqual(res.returncode, 0, msg=res.stdout + "\n" + res.stderr)
            self.assertIn("FS structure OK", res.stdout)


    def test_validate_fs_disallowed_root_file(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            make_min_fs(base)
            (base / "whateverrrr").write_text("x", encoding="utf-8")
            res = run([sys.executable, "src/validate_fs.py", "--root", str(base), "--spec", "src/fs_spec.yaml"])
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("disallowed file", res.stdout)


if __name__ == "__main__":
    unittest.main()
