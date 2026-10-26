"""The zip for claude.ai has the same layout as court-skill.zip."""
import os
import subprocess
import sys
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Build(unittest.TestCase):
    def test_zip_layout(self):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "build.py")], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        with zipfile.ZipFile(os.path.join(ROOT, "dist", "pitch-skill.zip")) as z:
            names = set(z.namelist())
        self.assertEqual(names, {"pitch/", "pitch/SKILL.md", "pitch/ideacourt.py",
                                 "pitch/jurors.json", "pitch/LICENSE"})
        self.assertFalse(any("\\" in n for n in names))


if __name__ == "__main__":
    unittest.main()
