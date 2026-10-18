#!/usr/bin/env python3
"""Where the scripted reference's mean nomination sits in the landscape it is searching.

  python3 scripts/reference_percentile.py

It reports the share of viable candidates, and of the whole 160,000-candidate space, at least as good as the
fair k* policy's mean nomination, on the landscape rebuilt by the same call the reference curve uses.

Writes results/reference_percentile.json.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import fair_reference_curve as FRC                                     # noqa: E402


def main():
    fit, pool = FRC.landscape()
    # Neighbours are drawn over the landscape's own letters.
    curves = json.load(open(FRC.CORRECTED))["curves"]
    out = {}
    for scope in ("fair", "pool"):
        for k in ("0", "1"):
            v = curves[scope][k]["mean"]
            n_pool = sum(1 for s in pool if fit[s] >= v)
            n_all = sum(1 for s in fit if fit[s] >= v)
            out["%s_k%s" % (scope, k)] = dict(
                mean=v,
                top_pct_of_viable=100.0 * n_pool / len(pool),
                top_pct_of_space=100.0 * n_all / len(fit),
                n_viable_at_least=n_pool, n_space_at_least=n_all)
    out["landscape"] = dict(candidates=len(fit), viable=len(pool), best=max(fit.values()))
    dst = os.path.join(ROOT, "results", "reference_percentile.json")
    json.dump(out, open(dst, "w"), indent=1)

    print("=" * 92)
    print("WHERE A NOMINATION SITS IN THE LANDSCAPE   %d candidates, %d viable, best %.4f"
          % (len(fit), len(pool), max(fit.values())))
    print("=" * 92)
    print("  %-34s %9s %16s %16s" % ("policy", "mean", "top % viable", "top % of space"))
    for key in ("pool_k1", "fair_k1", "pool_k0", "fair_k0"):
        r = out[key]
        print("  %-34s %9.4f %15.2f%% %15.3f%%"
              % (key, r["mean"], r["top_pct_of_viable"], r["top_pct_of_space"]))
    print("\n  wrote results/reference_percentile.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
