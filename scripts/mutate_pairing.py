#!/usr/bin/env python3
"""Mutation test for tests/test_the_contrast_is_paired_by_seed.py: each mutation should make the test fail.

Five mutations:
  1. report the Welch standard error while calling the analysis paired
  2. pair by row order instead of by seed
  3. drop the seed-alignment reporting, so a missing seed vanishes
  4. drop the degeneracy guard, so a nan can reach Holm
  5. intersect differing seed sets without counting the dropped seeds
A mutation the test misses is reported as a hole in the test.
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import mutate

TARGET = os.path.join(ROOT, "scripts", "analyse_grid.py")
# mutate.baseline/check prepend `python -B -m unittest`, so this is the unittest ARGUMENT list only.
TEST = ["discover", "-s", "tests", "-p", "test_the_contrast_is_paired_by_seed.py"]
CANARY_IMPORTS = "import sys, os; sys.path.insert(0, %r); import analyse_grid" % os.path.join(ROOT, "scripts")

MUTANTS = [
    ("reports the Welch SE while calling itself paired",
     "            diff, se, pt = paired_t_p(d)",
     "            diff, se, pt = paired_t_p(d)\n            _du0, se, _p0 = welch_p(ya, yb)"),
    ("pairs by row order, the predecessor's bug",
     "            ya = [A[k] for k in ks]\n            yb = [B[k] for k in ks]",
     "            ya = [A[k] for k in ks]\n            yb = list(A.values()) and [B[k] for k in sorted(B)][::-1]"),
    ("stops reporting dropped seeds",
     "            dropped = len(set(A) ^ set(B))",
     "            dropped = 0"),
    ("lets a degenerate cell through to Holm",
     "                if st.stdev(v) == 0:",
     "                if False:"),
    ("uses the unpaired difference as the point estimate",
     "            du, seu, pw = welch_p(ya, yb)",
     "            du, seu, pw = welch_p(ya, yb)\n            diff = du + 0.5"),
]


def main():
    print("BASELINE (must be clean before any verdict means anything)")
    green, log = mutate.baseline(TEST)
    print("  green=%s  %s" % (green, log.strip().splitlines()[-1] if log.strip() else ""))
    if not green:
        print(log)
        sys.exit("baseline is not green; no mutation verdict would be trustworthy")
    rows = []
    for label, old, new in MUTANTS:
        v = mutate.check(TARGET, old, new, TEST, imports=CANARY_IMPORTS, label=label, timeout=300)
        rows.append((label, v))
        print("  %-52s %s" % (label[:52], v))
    print()
    missed = [l for l, v in rows if v != "CAUGHT"]
    print("CAUGHT %d/%d" % (len(rows) - len(missed), len(rows)))
    for l in missed:
        print("  MISSED: %s" % l)
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
