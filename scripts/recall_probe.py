#!/usr/bin/env python3
"""Cold recall probe: does the model recall a landscape's optimum, or only have good priors?

One call per model per landscape, with no campaign or history, asking for the best variant. Naming the exact
global optimum suggests recall; naming plausible but non-optimal variants suggests priors. The rank correlation
with the true top 10 matters more than a single hit, since priors should get the direction right but not the order.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import landscape as L, llm

TASKS = {
    "gb1": {
        "positions": "V39, D40, G41 and V54",
        "study": "Wu, Dai, Olson, Lloyd-Smith and Sun (2016), eLife, the combinatorially "
                 "complete four-site fitness landscape of protein G domain B1 (GB1) measured "
                 "by mRNA display",
        "metric": "fitness relative to wild type",
        "parent": "VDGV",
    },
    "phoq": {
        "positions": "A284, V285, S288 and T289",
        "study": "Podgornaia and Laub (2015), Science, the complete four-residue sequence space "
                 "of the E. coli PhoQ kinase interface with PhoP",
        "metric": "functional score",
        "parent": "AVST",
    },
}

PROMPT = """In {study}, all 20^4 = 160,000 variants at positions {positions} were characterised.
The wild-type sequence at those four positions is "{parent}".

From your knowledge of that published dataset, name the variant with the HIGHEST {metric}.
Then list your best guess at the top 10 variants in descending order.

Reply in exactly this format and nothing else:
BEST: XXXX
TOP10: XXXX, XXXX, XXXX, XXXX, XXXX, XXXX, XXXX, XXXX, XXXX, XXXX
CONFIDENCE: one short sentence on whether you are recalling the dataset or inferring from
biochemistry."""


def spearman(a, b):
    """Rank correlation over the shared members, re-ranked within that subset."""
    shared = [x for x in a if x in b]
    if len(shared) < 3:
        return None, len(shared)
    # order the shared items as each list orders them, then rank within the subset
    sa = [x for x in a if x in shared]
    sb = [x for x in b if x in shared]
    ra = {x: i for i, x in enumerate(sa)}
    rb = {x: i for i, x in enumerate(sb)}
    n = len(shared)
    d2 = sum((ra[x] - rb[x]) ** 2 for x in shared)
    return 1.0 - 6.0 * d2 / (n * (n * n - 1)), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=("anthropic/claude-opus-4.7,openai/gpt-5.5,"
                                        "google/gemini-3.1-pro-preview,"
                                        "deepseek/deepseek-v4-flash,mistralai/mistral-nemo"))
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    out, spend = [], 0.0

    for name, t in TASKS.items():
        ls = L.load(name)
        truth = sorted(ls.pool, key=lambda s: -ls.fitness[s])[:10]
        print("=" * 100)
        print("%s   true best %s (%.3f)   true top10 %s"
              % (name.upper(), truth[0], ls.fitness[truth[0]], " ".join(truth)))
        print("=" * 100)
        for m in models:
            c = llm.complete(PROMPT.format(**t), m, max_tokens=1200, temperature=0.0)
            spend += c.cost_usd
            if not c.ok:
                print("  %-34s ERROR %s" % (m, (c.error or "")[:60]))
                continue
            txt = c.text
            best = ""
            top = []
            for line in txt.splitlines():
                u = line.strip().upper()
                if u.startswith("BEST:"):
                    best = u.split(":", 1)[1].strip().split()[0][:4] if ":" in u else ""
                if u.startswith("TOP10:"):
                    top = [x.strip()[:4] for x in u.split(":", 1)[1].split(",") if x.strip()]
            rho, shared = spearman(top, truth)
            hit = "EXACT HIT" if best == truth[0] else ""
            n_in_top10 = sum(1 for s in top if s in truth)
            conf = ""
            for line in txt.splitlines():
                if line.strip().upper().startswith("CONFIDENCE:"):
                    conf = line.split(":", 1)[1].strip()[:80]
            print("  %-34s BEST=%-5s %-9s | %d/10 of its list in the true top10 | rho=%s"
                  % (m, best or "?", hit, n_in_top10,
                     ("%.2f (n=%d)" % (rho, shared)) if rho is not None else "n/a"))
            if conf:
                print("      self-report: %s" % conf)
            out.append({"landscape": name, "model": m, "best": best, "top10": top,
                        "exact_hit": best == truth[0], "n_in_true_top10": n_in_top10,
                        "rho": rho, "raw": txt, "cost_usd": c.cost_usd})
        print()

    rp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "results", "recall_probe.jsonl")
    with open(rp, "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    print("TOTAL SPEND: $%.4f over %d calls   log: %s" % (spend, len(out), rp))


if __name__ == "__main__":
    main()
