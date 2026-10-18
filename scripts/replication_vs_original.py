#!/usr/bin/env python3
"""Compare the replication run with the original grid run, arm by arm (not pre-registered).

The replication reran the same landscape with the same settings on disjoint seeds, so each arm-to-arm
difference is unpaired, with a Welch standard error. Only DeepSeek V3.1's Mechanism and Decision-rule arms
enter, each without its fallback campaign (seed 300084 in the original, 6100047 in the replication).
No pooled estimate is computed, since pooling was not pre-registered.

Usage: python3 scripts/replication_vs_original.py     (writes results/replication_vs_original.json)
"""
import json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_grid as AG                                   # noqa: E402

MODEL = "deepseek/deepseek-chat-v3.1"
RUNS = {"original": ("stage1", "topup_opus", "topup_gemini", "topup_deepseek"),
        "replication": ("replication_dsdr",)}
EXPECTED_FALLBACKS = {"original": {300084}, "replication": {6100047}}
OUT = os.path.join(ROOT, "results", "replication_vs_original.json")


def main():
    arms, out = {}, {}
    for run, tags in RUNS.items():
        rows = AG.load("+".join(tags))
        fb = AG.fallback_seeds(list(tags))
        dropped = {k[2] for k in fb if k[1] == MODEL and k[0] in ("instructed", "decision_rule")}
        if dropped != EXPECTED_FALLBACKS[run]:
            raise SystemExit("REFUSED: %s drops %s, expected %s" % (run, sorted(dropped), sorted(EXPECTED_FALLBACKS[run])))
        for cond in ("Mechanism", "Decision-rule"):
            rung = AG.RUNG_OF[cond]
            v = [r["nominated_true"] for r in rows if r["model"] == MODEL and r["condition"] == cond
                 and (rung, r["model"], r["seed"]) not in fb]
            arms[(run, cond)] = v
            out["%s|%s" % (run, cond)] = dict(n=len(v), mean=st.mean(v), sd=st.stdev(v))
    for cond in ("Mechanism", "Decision-rule"):
        a, b = arms[("original", cond)], arms[("replication", cond)]
        out["shift|%s" % cond] = dict(diff=st.mean(b) - st.mean(a),
                                      se=math.sqrt(st.variance(a) / len(a) + st.variance(b) / len(b)))
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True)
    for k, v in sorted(out.items()):
        print("  %-28s %s" % (k, "  ".join("%s %.6f" % (x, y) if isinstance(y, float) else "%s %d" % (x, y)
                                            for x, y in sorted(v.items()))))
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
