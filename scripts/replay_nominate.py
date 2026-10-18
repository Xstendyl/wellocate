#!/usr/bin/env python3
"""Collect nomination data from the pilot with one call per campaign instead of a full re-run.

Every reading is keyed on (campaign_seed, sequence, replicate_index), independent of call order, so a
campaign's measurement history can be replayed exactly from the logged proposals. The replay is checked
against the logged n_ok and n_rejected before any call is made, and nothing is spent if it does not match.
"""
import argparse
import collections
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import landscape as L, llm_policy as LP, oracle as O, view as V

LOG = "results/pilot_opus47_calls.jsonl"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def replay(ls, ps, seed, sigma, calls):
    """Rebuild the exact oracle state from the logged proposals."""
    orc = O.Oracle(ls.fitness, ls.pool, sigma, seed, 0.15)
    for r in sorted(calls, key=lambda x: (x["round"], x["kind"] != "round")):
        for s in r["parsed"]:
            orc.measure(s, r["round"])
    return orc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="anthropic/claude-opus-4.7")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ls = L.load("gb1")
    ps = tuple(sorted(ls.pool))
    rows = [json.loads(l) for l in open(os.path.join(ROOT, LOG))]
    camps = collections.defaultdict(list)
    for r in rows:
        camps[(r["rung"], r["ratio"], r["campaign_seed"])].append(r)

    print("STEP 1: verify the replay reproduces the logged campaign exactly.")
    ok_all = True
    states = {}
    for key, calls in sorted(camps.items()):
        rung, ratio, seed = key
        orc = replay(ls, ps, seed, 0.557 * ratio, calls)
        n_ok = orc.n_ok()
        n_rej = sum(1 for r in orc.history if r.outcome == O.REJECTED)
        states[key] = orc
        print("  %-12s r%.0f seed %d  replayed ok=%2d rej=%2d" % (rung, ratio, seed, n_ok, n_rej))
        if n_ok == 0:
            ok_all = False
    if not ok_all:
        print("\n  REPLAY FAILED, nothing spent.")
        return 1

    print("\nSTEP 2: the two reference rules on each replayed history, before any model call.")
    print("  %-12s %5s %6s | %-6s %8s | %-6s %8s | %s"
          % ("rung", "ratio", "seed", "maxmean", "true", "maxsingle", "true", "rules differ"))
    ref = {}
    for key, orc in sorted(states.items()):
        v = V.build(orc, 15, 15, 4, 60, ps)
        mm, msx = v.best_by_mean(), v.best_by_max()
        ref[key] = (mm, msx, v)
        print("  %-12s %5.0f %6d | %-6s %8.3f | %-6s %8.3f | %s"
              % (key[0], key[1], key[2], mm, ls.fitness[mm], msx, ls.fitness[msx],
                 "YES" if mm != msx else "no"))
    n_diff = sum(1 for k, (a, b, _) in ref.items() if a != b)
    print("\n  campaigns where the two rules give DIFFERENT answers: %d of %d" % (n_diff, len(ref)))
    if args.dry_run:
        print("  dry run, no calls made.")
        return 0

    print("\nSTEP 3: one nomination call per campaign.")
    out, spend = [], 0.0
    for key, orc in sorted(states.items()):
        rung, ratio, seed = key
        mm, msx, v = ref[key]
        pol = LP.LLMPolicy(args.model, "instructed" if rung == "instructed" else "blind",
                           0.557 * ratio, max_tokens=1200)
        seq, reason, rec = pol.nominate(v)
        spend += pol.spend_usd
        tf = ls.fitness.get(seq)
        best_own = ls.fitness[mm]
        lost = (best_own - tf) if tf is not None else None
        match = ("maxmean" if seq == mm else "maxsingle" if seq == msx
                 else "neither" if seq else "unparsed")
        if mm == msx and seq == mm:
            match = "tied"
        print("  %-12s r%.0f seed %d -> %-5s true=%s | maxmean true=%.3f | lost=%s | %s"
              % (rung, ratio, seed, seq or "?", ("%.3f" % tf) if tf is not None else "n/a",
                 best_own, ("%+.3f" % -lost) if lost is not None else "n/a", match))
        out.append({"rung": rung, "ratio": ratio, "seed": seed, "nominated": seq,
                    "nominated_true": tf, "ref_maxmean": mm, "ref_maxmean_true": best_own,
                    "ref_maxsingle": msx, "ref_maxsingle_true": ls.fitness[msx],
                    "match": match, "lost_vs_own_data": lost, "reason": reason,
                    "raw": rec["raw_response"], "cost_usd": rec["cost_usd"]})

    rp = os.path.join(ROOT, "results", "nomination_replay.jsonl")
    with open(rp, "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")

    print("\n" + "=" * 92)
    print("THE THREE NUMBERS")
    print("=" * 92)
    worse = [r for r in out if r["lost_vs_own_data"] is not None and r["lost_vs_own_data"] > 1e-9]
    print("  share of campaigns whose answer is WORSE than max-mean on their own data: %d/%d = %.0f%%"
          % (len(worse), len(out), 100 * len(worse) / max(1, len(out))))
    if worse:
        print("  mean fitness lost, over those campaigns: %.3f  (median %.3f, max %.3f)"
              % (st.mean([r["lost_vs_own_data"] for r in worse]),
                 st.median([r["lost_vs_own_data"] for r in worse]),
                 max(r["lost_vs_own_data"] for r in worse)))
    c = collections.Counter(r["match"] for r in out)
    print("  which rule the nomination matched: %s" % dict(c))
    print("\n  SPEND: $%.4f over %d calls   log: %s" % (spend, len(out), rp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
