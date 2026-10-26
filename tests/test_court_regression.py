"""Scenario F: the original /court skill keeps working and is left untouched.

Runs the court.py from court-skill.zip through a full trial with fixture files, and checks that the
installed copy (if any) still has the same code. court-skill.zip is not part of this repo: point
COURT_SKILL_ZIP at it, or put it in the repo root. Without it, these tests are skipped.

    COURT_SKILL_ZIP=../court-original/court-skill.zip py -3 -m unittest discover -s tests -v
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP = os.environ.get("COURT_SKILL_ZIP") or os.path.join(ROOT, "court-skill.zip")
INSTALLED = glob.glob(os.path.join(os.path.expanduser("~"), ".claude", "skills", "**", "court", "court.py"),
                      recursive=True)


@unittest.skipUnless(os.path.exists(ZIP), "court-skill.zip not found")
class CourtStillWorks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(ZIP) as z:
            z.extractall(os.path.join(self.tmp, "skill"))
        self.court = os.path.join(self.tmp, "skill", "court", "court.py")
        self.work = os.path.join(self.tmp, "work")
        os.makedirs(os.path.join(self.work, ".court"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def court_cmd(self, *args):
        p = subprocess.run([sys.executable, self.court] + list(args), cwd=self.work,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def put(self, rel, text):
        with open(os.path.join(self.work, rel), "w") as f:
            f.write(text)

    def test_full_trial(self):
        self.put(".court/case.md", "Quit my job to sell candles on Etsy full time\n")
        self.assertIn("17 sub-agent calls", self.court_cmd("plan"))
        self.assertIn("jury of 12", self.court_cmd("init", "--case-file", ".court/case.md", "--seed", "1"))
        with open(os.path.join(self.work, ".court", "LATEST")) as f:
            rd = f.read().strip()
        self.assertIn("prompts opening", self.court_cmd("next"))
        self.court_cmd("prompts", "opening")
        for phase in ("opening", "rebuttal"):
            for side in ("prosecution", "defense"):
                self.put(os.path.join(rd, phase, side + ".md"), "1. point\n")
        for i in range(12):
            vote = "GUILTY" if i < 7 else "NOT GUILTY"
            self.put(os.path.join(rd, "jury", "juror-%02d.md" % (i + 1)),
                     "VOTE: %s\nREASON: r\nDECIDING FACT: f\nWOULD FLIP IF: w\n" % vote)
        self.assertIn("the jury voted GUILTY, 7 to 5", self.court_cmd("next"))
        self.put(os.path.join(rd, "judge", "judge.md"), "## The sentence\nDo it.\n")
        self.assertIn("trial is over", self.court_cmd("next"))
        verdict = self.court_cmd("render")
        self.assertIn("# The verdict: GUILTY, 7 to 5", verdict)

    @unittest.skipUnless(INSTALLED, "court skill is not installed")
    def test_installed_court_is_unchanged(self):
        with zipfile.ZipFile(ZIP) as z:
            for name in ("court.py", "jurors.json"):
                packed = z.read("court/" + name).replace(b"\r\n", b"\n")
                for path in INSTALLED:
                    with open(os.path.join(os.path.dirname(path), name), "rb") as f:
                        self.assertEqual(f.read().replace(b"\r\n", b"\n"), packed, path)


if __name__ == "__main__":
    unittest.main()
