#!/usr/bin/env python3
"""The aid arms' prompts beside the grid's Blind prompt, captured from the campaign path itself. No model is called.

A stand-in model orders the same candidates in every arm: the reference point and three of its neighbours each
round, so the reference is ordered again every round and the repeat cap engages from round 3. Each arm's round-4
prompt is captured, with the repeat-cap arm's first replacement ask and its nomination prompt, and every
line that differs from the grid's Blind round-4 prompt is listed.

Usage: python3 scripts/prompts_0an.py      (writes results/prompts_0an.txt)
"""
import difflib, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from repdef import llm, tools                                          # noqa: E402
import grid                                                            # noqa: E402

OUT = os.path.join(ROOT, "results", "prompts_0an.txt")


def capture(opts):
    seen = []

    def model(prompt, model, **kw):
        seen.append(prompt)
        ref = re.search(r'The reference point is "([A-Z]{4})"', prompt).group(1)
        if "ANSWER: XXXX" in prompt:
            return llm.Call(text="ANSWER: %s\nREASON: x" % ref, model=model)
        n = int(re.search(r"Reply with exactly (\d+) lines", prompt).group(1))
        rnd = int(re.search(r"ROUND (\d+) OF", prompt).group(1))
        nb = sorted(tools._neighbours(ref, grid.ALPHABET))
        picks = [ref] + nb[3 * rnd: 3 * rnd + 3]
        if n == 1:
            excl = set(re.findall(r"\b([A-Z]{4})\b", prompt.split("HISTORY")[-1].split("Choose")[-1]))
            picks = [x for x in nb[60:] if x not in excl][:1]
        return llm.Call(text="\n".join("%s | x" % p for p in picks[:n]), model=model)
    real = llm.complete
    llm.complete = model
    try:
        fit, pool = grid.landscape()
        grid.one_campaign(fit, pool, tuple(sorted(pool)), (7.0, 0.1), "vendor/stub", "blind", 300000, [], 6000, 3,
                          prompt_options=opts)
    finally:
        llm.complete = real
    return seen


def round4(prompts):
    return next(p for p in prompts if "ROUND 4 OF" in p and "Reply with exactly 4 lines" in p)


def main():
    base = round4(capture({}))
    out = ["=" * 100, "GRID, Blind, round 4 (no 0an option)", "=" * 100, base, ""]
    for name, opts in (("F1 ledger", dict(truthful_reask=True, ledger=True)),
                       ("F2 menu", dict(truthful_reask=True, menu=True)),
                       ("F3 cap", dict(truthful_reask=True, repeat_cap=True)),
                       ("F5 structure", dict(truthful_reask=True, structure=True))):
        ps = capture(opts)
        p = round4(ps)
        d = [l for l in difflib.unified_diff(base.splitlines(), p.splitlines(), "grid", name, n=0, lineterm="")
             if not l.startswith(("---", "+++", "@@"))]
        out += ["=" * 100, "%s, round 4: lines that differ from the grid's (%d removed, %d added)"
                % (name, sum(1 for l in d if l.startswith("-")), sum(1 for l in d if l.startswith("+"))), "=" * 100]
        out += d + [""]
        if name == "F3 cap":
            # The refusal notice says "have already been ordered"; the at-limit block says "have been".
            rep = next(x for x in ps if "have already been ordered the maximum number of times" in x)
            out += ["F3 cap, the first replacement ask after a refused order, its last lines:"]
            out += rep.splitlines()[-9:] + [""]
            nom = next(x for x in ps if "ANSWER: XXXX" in x)
            out += ["F3 cap, the nomination prompt states the rule:",
                    next(l for l in nom.splitlines() if "ordered at most" in l), ""]
        if name == "F5 structure":
            rep = next(x for x in ps if "Reply with exactly 1 lines" in x)
            nom = next(x for x in ps if "ANSWER: XXXX" in x)
            out += ["F5 structure: the paragraph is also in the replacement asks (%s) and the nomination prompt (%s)."
                    % ("STRUCTURE\n" in rep, "STRUCTURE\n" in nom), ""]
    open(OUT, "w").write("\n".join(out) + "\n")
    print("\n".join(out[5:]))
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
