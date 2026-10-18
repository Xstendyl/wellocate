#!/usr/bin/env python3
"""Print the diff between the grid's Blind prompt and the biology-framing variants, for all four prompt types.

Each variant replaces the opening sentence with a biology role (and, in one cell, adds a sentence saying
readings are noisy); nothing else changes. The SHA256 of each rendered variant is printed for checking.
"""
import difflib, hashlib, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_prompt_contract import rendered  # noqa: E402

GRID_FIRST_SENTENCE = ("You are running a numerical optimization campaign on four positions of an "
                       "abstract four-position system.")
# The role text is imported from the harness so the diff matches what is actually sent.
from repdef.prompts import OPENINGS  # noqa: E402

ROLE = OPENINGS["bio_role"]
NOISE_SENTENCE = OPENINGS["bio_role_noisy"][len(ROLE) + 1:]
KINDS = ["round", "replacement", "reask", "nomination"]


def bio_role(text):
    """The grid's Blind prompt with only the first sentence replaced."""
    if text.count(GRID_FIRST_SENTENCE) != 1:
        raise SystemExit("the anchor sentence does not appear exactly once; the prompt has drifted")
    return text.replace(GRID_FIRST_SENTENCE, ROLE, 1)


def bio_role_noisy(text):
    """bio_role plus one qualitative noise sentence appended to the role paragraph."""
    t = bio_role(text)
    return t.replace(ROLE, ROLE + " " + NOISE_SENTENCE, 1)


CELLS = [("bio_role", bio_role, "sigma > 0, no noise statement"),
         ("bio_role_noisy", bio_role_noisy, "sigma > 0, one qualitative noise sentence"),
         ("bio_role_exact", bio_role, "sigma = 0, failures kept at 15%, prompt identical to bio_role")]


class Tee(object):
    """Write to the terminal and to results/bio_framing_diff.txt in the same call."""

    def __init__(self, path):
        self.f = open(path, "w")
        self.out = sys.stdout

    def write(self, s):
        self.out.write(s)
        self.f.write(s)

    def flush(self):
        self.out.flush()
        self.f.flush()

    def close(self):
        self.f.close()


def main():
    tee = Tee(os.path.join(ROOT, "results", "bio_framing_diff.txt"))
    real_stdout, sys.stdout = sys.stdout, tee
    try:
        return _main()
    finally:
        sys.stdout = real_stdout
        tee.close()


def _main():
    R = rendered()
    out = {}
    for cell, fn, note in CELLS:
        print("=" * 104)
        print("CELL %s   (%s)" % (cell, note))
        print("=" * 104)
        for kind in KINDS:
            base = R[("blind", "multiplicative", kind)]
            new = fn(base)
            d = list(difflib.unified_diff(base.splitlines(), new.splitlines(),
                                          fromfile="grid Blind / %s" % kind,
                                          tofile="%s / %s" % (cell, kind), lineterm="", n=1))
            print("\n--- %s ---" % kind)
            for line in d:
                print("  " + line)
            changed = sum(1 for l in d if l.startswith(("+", "-")) and not l.startswith(("+++", "---")))
            out["%s|%s" % (cell, kind)] = dict(sha256=hashlib.sha256(new.encode()).hexdigest(),
                                               diff_lines=changed,
                                               base_sha256=hashlib.sha256(base.encode()).hexdigest())
            print("  (%d changed lines; rendered SHA256 %s)"
                  % (changed, out["%s|%s" % (cell, kind)]["sha256"][:16]))
    print("\n" + "=" * 104)
    print("EVERY OTHER BYTE IS IDENTICAL, checked rather than asserted")
    print("=" * 104)
    bad = 0
    for cell, fn, _n in CELLS:
        for kind in KINDS:
            base = R[("blind", "multiplicative", kind)]
            new = fn(base)
            # Remove the intended change from both sides; what remains must match exactly.
            a = base.replace(GRID_FIRST_SENTENCE, "@@ROLE@@", 1)
            b = new.replace(ROLE + " " + NOISE_SENTENCE, "@@ROLE@@", 1).replace(ROLE, "@@ROLE@@", 1)
            same = (a == b)
            bad += int(not same)
            print("  %-16s %-12s identical outside the substitution: %s" % (cell, kind, same))
    dst = os.path.join(ROOT, "results", "bio_framing_prompts.json")
    json.dump(dict(anchor=GRID_FIRST_SENTENCE, role=ROLE, noise_sentence=NOISE_SENTENCE,
                   rendered=out), open(dst, "w"), indent=1)
    print("\n  wrote %s" % os.path.relpath(dst, ROOT))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
