#!/usr/bin/env python3
"""Mutation test for tests/test_the_manifest_cannot_lie_about_its_code.py, with six mutations of grid.py."""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import mutate

TARGET = os.path.join(ROOT, "scripts", "grid.py")
TEST = ["discover", "-s", "tests", "-p", "test_the_manifest_cannot_lie_about_its_code.py"]
IMPORTS = ("import sys, os; sys.path.insert(0, %r); sys.path.insert(0, %r); import grid"
           % (os.path.join(ROOT, "scripts"), ROOT))

MUTANTS = [
    ("records HEAD and calls it provenance, the original bug",
     "        git_commit_describes_the_code=not dirty)",
     "        git_commit_describes_the_code=True)"),
    ("never refuses, only warns",
     "    if not allow_dirty:\n        raise UncommittedCode(",
     "    if False:\n        raise UncommittedCode("),
    ("misses untracked files, so a new module launches unnoticed",
     "    dirty = [l for l in _git(\"status\", \"--porcelain\").splitlines()",
     "    dirty = [l for l in _git(\"status\", \"--porcelain\").splitlines() if not l.startswith('??')"),
    ("blocks on a spec edit too, which teaches --allow-dirty by reflex",
     "             if l[3:].strip().strip('\"').startswith(CODE_DIRS)",
     "             if True"),
    ("lets an earlier manifest key shadow the provenance",
     "    manifest.update(prov)",
     "    manifest = dict(prov, **manifest)"),
    ("saves the diff but not the untracked file contents",
     '            f.write("\\n--- UNTRACKED FILE, in no commit and in no diff: %s ---\\n" % rel)',
     '            continue'),
]


def main():
    green, log = mutate.baseline(TEST)
    print("BASELINE green=%s" % green)
    if not green:
        print(log)
        sys.exit("baseline is not green")
    rows = []
    for label, old, new in MUTANTS:
        v = mutate.check(TARGET, old, new, TEST, imports=IMPORTS, label=label, timeout=300)
        rows.append((label, v))
        print("  %-56s %s" % (label[:56], v))
    missed = [l for l, v in rows if v != "CAUGHT"]
    print("\nCAUGHT %d/%d" % (len(rows) - len(missed), len(rows)))
    for l in missed:
        print("  MISSED: %s" % l)
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
