#!/usr/bin/env python3
"""Package and install the pitch skill.

    py -3 build.py              # dist/pitch-skill.zip, for upload to claude.ai
    py -3 build.py --install    # also copy the skill to ~/.claude/skills/pitch (Claude Code)

The zip has the same layout as court-skill.zip: one top-level folder named after the skill, with
forward-slash paths (Compress-Archive on Windows PowerShell 5.1 writes backslashes, which break it).
"""
import argparse
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "pitch"
SRC = os.path.join(ROOT, NAME)
FILES = ["SKILL.md", "ideacourt.py", "jurors.json", "LICENSE"]


def build():
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    out = os.path.join(ROOT, "dist", "%s-skill.zip" % NAME)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(NAME + "/", "")
        for f in FILES:
            z.write(os.path.join(SRC, f), "%s/%s" % (NAME, f))
    print("built %s" % out)


def install():
    dest = os.path.join(os.path.expanduser("~"), ".claude", "skills", NAME)
    os.makedirs(dest, exist_ok=True)
    for f in FILES:
        shutil.copy2(os.path.join(SRC, f), os.path.join(dest, f))
    print("installed to %s (restart Claude Code, then type /%s)" % (dest, NAME))


def main():
    p = argparse.ArgumentParser(prog="build.py")
    p.add_argument("--install", action="store_true", help="also install for Claude Code")
    args = p.parse_args()
    missing = [f for f in FILES if not os.path.exists(os.path.join(SRC, f))]
    if missing:
        sys.exit("build: missing %s" % ", ".join(missing))
    build()
    if args.install:
        install()


if __name__ == "__main__":
    main()
