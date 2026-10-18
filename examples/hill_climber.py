#!/usr/bin/env python3
"""A hill climber written against the Wellocate step API, scored on the bio track. No model is called.

Each round it re-tests its current best once (when the best has a single reading) and tries untried single-letter
changes of the best with the other slots. It nominates by the paper's shrinkage rule.

Usage: python3 examples/hill_climber.py [--split bio:test] [--n 100]
"""
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wellocate import evaluate  # noqa: E402


class HillClimber(object):
    def __init__(self, env):
        self.anchor, self.alphabet = env.anchor, env.alphabet

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        reads = view.readings()
        best = max(reads, key=lambda s: sum(reads[s]) / len(reads[s])) if reads else self.anchor
        tried = {h.seq for h in view.history} | set(exclude)
        new = [best[:i] + a + best[i + 1:] for i in range(4) for a in self.alphabet]
        new = [c for c in new if c not in tried]
        retest = [best] if kind == "round" and best in reads and len(reads[best]) == 1 else []
        return (retest + new)[:n_slots]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="bio:test")
    ap.add_argument("--n", type=int, default=100)
    a = ap.parse_args()
    for split, sc in evaluate(lambda env: HillClimber(env), a.split, n=a.n).items():
        b = sc["best_scripted"]
        print("%-12s pick %.3f [%.3f, %.3f]  re-testing share %.1f%%  regret vs informed %+.3f  "
              "(best scripted: %s, share %.1f%%)" % (split, sc["pick"]["mean"], sc["pick"]["ci"][0], sc["pick"]["ci"][1],
                                                     sc["share_budget"]["mean"], sc["regret_vs_informed"]["mean"],
                                                     b["policy"], b["share_budget"]))


if __name__ == "__main__":
    main()
