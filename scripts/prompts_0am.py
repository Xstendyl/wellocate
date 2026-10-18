#!/usr/bin/env python3
"""Capture the round-1 prompts of the real-protein panel arms beside the grid's, from the campaign path itself.

No model is called. `grid.one_campaign` runs with a stand-in model that records the first prompt it is sent
and replies in format, so what is written here is exactly what a campaign sends in round 1, for the Blind and
Mechanism conditions on the grid and on each arm. A line-by-line comparison against the grid's prompt
lists every line that differs.

Usage: python3 scripts/prompts_0am.py      (writes results/prompts_0am_panel_r.txt)
"""
import difflib, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from repdef import envs as E, llm                                       # noqa: E402
import grid                                                             # noqa: E402

OUT = os.path.join(ROOT, "results", "prompts_0am_panel_r.txt")


def first_prompt(env, rung):
    seen = []

    def model(prompt, model, **kw):
        seen.append(prompt)
        if "ANSWER: XXXX" in prompt:
            ref = re.search(r'The reference point is "([A-Z]{4})"', prompt).group(1)
            return llm.Call(text="ANSWER: %s\nREASON: x" % ref, model=model)
        n = int(re.search(r"Reply with exactly (\d+) lines", prompt).group(1))
        ref = re.search(r'The reference point is "([A-Z]{4})"', prompt).group(1)
        return llm.Call(text="\n".join("%s | x" % ref for _ in range(n)), model=model)
    real = llm.complete
    llm.complete = model
    try:
        if env is None:
            fit, pool = grid.landscape()
            ps = tuple(sorted(pool))
            vals = [fit[s] for s in pool]
            grid.one_campaign(fit, pool, ps, (sum(vals) / len(vals), 1.0), "vendor/stub", rung, 1, [],
                              6000, 3)
        else:
            grid.one_campaign(env.fit, env.pool, env.ps, env.prior, "vendor/stub", rung, 1, [], 6000, 3,
                              env=env)
    finally:
        llm.complete = real
    return seen[0]


def main():
    arms = [("grid (NK K=1 seed 1)", None), ("gb1_scrambled", E.gb1_scrambled()),
            ("gb1_real", E.gb1_real()), ("phoq_scrambled", E.phoq_scrambled())]
    out = []
    for cond, rung in (("Blind", "blind"), ("Mechanism", "instructed")):
        base = first_prompt(None, rung).splitlines()
        for name, env in arms:
            p = first_prompt(env, rung)
            out.append("=" * 100)
            out.append("%s, %s, round 1" % (name, cond))
            out.append("=" * 100)
            out.append(p)
            if env is not None:
                d = [l for l in difflib.unified_diff(base, p.splitlines(), "grid", name, n=0, lineterm="")
                     if not l.startswith(("---", "+++", "@@"))]
                out.append("-" * 100)
                out.append("LINES THAT DIFFER FROM THE GRID'S %s PROMPT (%d removed, %d added):"
                           % (cond, sum(1 for l in d if l.startswith("-")),
                              sum(1 for l in d if l.startswith("+"))))
                out.extend(d)
            out.append("")
    open(OUT, "w").write("\n".join(out) + "\n")
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
