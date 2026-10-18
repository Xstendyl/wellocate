#!/usr/bin/env python3
"""Compare the Mechanism and Decision-rule conditions per model, paired by seed.

Uses the campaign set of the published analysis, excluding campaigns whose nomination did not parse. For each
model it reports how often the agent picked the candidate with the highest average reading, the replication
share, distinct candidates measured, the true value of the best candidate measured, and how many paired campaigns
improved, got worse or tied on the final pick. It writes nothing unless its paired counts match Table 3.

Usage: python3 scripts/decision_rule_detail.py      (writes results/decision_rule_detail.json)
"""
import collections, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")       # the grid is complete; this reads final data
import analyse_grid as AG                                   # noqa: E402
from repdef.stats import _t_sf                              # noqa: E402

TAGS = ("stage1", "topup_opus", "topup_gemini", "topup_deepseek")
OUT = os.path.join(ROOT, "results", "decision_rule_detail.json")
# Table 3, Decision-rule against Mechanism: seeds and the paired mean difference in nominated true fitness.
PUBLISHED = {"claude-opus-4.7": (695, -0.0316), "deepseek-chat-v3.1": (180, +0.0699),
             "gemini-2.5-flash": (139, -0.0044)}
TIE = 1e-12


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value from the discordant counts."""
    n, k = b + c, min(b, c)
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def t_quantile(q, df):
    """The t quantile by bisection on the package's own survival function."""
    lo, hi = 0.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _t_sf(mid, df) > 1 - q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def paired_ci(d, level=0.95):
    """Mean, SE and the paired t interval of the within-seed differences `d`."""
    n = len(d)
    m, se = st.mean(d), st.stdev(d) / math.sqrt(n)
    t = t_quantile(1 - (1 - level) / 2, n - 1)
    return dict(mean=m, se=se, lo=m - t * se, hi=m + t * se, n=n)


def summarise(rows):
    """model -> the paired comparison, Mechanism (a) against Decision-rule (b)."""
    cells = collections.defaultdict(dict)
    for r in rows:
        if r["condition"] in ("Mechanism", "Decision-rule"):
            cells[(r["model"].split("/")[-1], r["condition"])][r["seed"]] = r
    out = {}
    for model in sorted({m for m, _ in cells}):
        a, b = cells[(model, "Mechanism")], cells[(model, "Decision-rule")]
        seeds = sorted(set(a) & set(b))
        A, B = [a[s] for s in seeds], [b[s] for s in seeds]
        d = [y["nominated_true"] - x["nominated_true"] for x, y in zip(A, B)]
        # Paired binary outcome: campaigns that switched away from the highest-mean pick against those that switched to it.
        left = sum(1 for x, y in zip(A, B) if x["agent_chose_mean"] and not y["agent_chose_mean"])
        joined = sum(1 for x, y in zip(A, B) if not x["agent_chose_mean"] and y["agent_chose_mean"])
        out[model] = dict(
            n=len(seeds),
            chose_mean=[st.mean(float(bool(x["agent_chose_mean"])) for x in X) for X in (A, B)],
            replication=[100 * st.mean(x["replication_fraction"] for x in X) for X in (A, B)],
            distinct=[st.mean(x["n_distinct_measured"] for x in X) for X in (A, B)],
            # Paired difference in percentage points, Decision-rule minus Mechanism.
            replication_diff_ci=paired_ci([100 * (y["replication_fraction"] - x["replication_fraction"])
                                           for x, y in zip(A, B)]),
            distinct_diff_ci=paired_ci([y["n_distinct_measured"] - x["n_distinct_measured"]
                                        for x, y in zip(A, B)]),
            best_tested_diff=st.mean(y["best_true_measured"] - x["best_true_measured"] for x, y in zip(A, B)),
            selection_shortfall_diff=st.mean(y["selection_shortfall"] - x["selection_shortfall"]
                                             for x, y in zip(A, B)),
            nominated_diff=st.mean(d),
            chose_mean_switched=[left, joined], chose_mean_mcnemar_p=mcnemar_exact(left, joined),
            improved=sum(v > TIE for v in d), worse=sum(v < -TIE for v in d),
            unchanged=sum(abs(v) <= TIE for v in d))
    return out


def main():
    rows = AG.load("+".join(TAGS))
    kept, dropped = AG.drop_fallbacks(rows, AG.fallback_seeds(list(TAGS)))
    primary, sensitivity = summarise(kept), summarise(rows)
    bad = []
    for model, (n, diff) in PUBLISHED.items():
        p = primary[model]
        if p["n"] != n or round(p["nominated_diff"], 4) != diff:
            bad.append("%s: %d seeds, %+.4f recomputed; Table 3 says %d, %+.4f"
                       % (model, p["n"], p["nominated_diff"], n, diff))
    for model, p in primary.items():
        if p["improved"] + p["worse"] + p["unchanged"] != p["n"]:
            bad.append("%s: improved, worse and unchanged do not sum to the pairs" % model)
    if bad:
        print("REFUSED: this is not the campaign set of Table 3.\n  " + "\n  ".join(bad))
        return 1
    for tag, res in (("primary, 0ag excluded", primary), ("sensitivity, every campaign", sensitivity)):
        print("== %s" % tag)
        for model, p in res.items():
            print("  %-20s n=%3d  chose-highest-mean %.3f -> %.3f  replication %.2f -> %.2f  distinct %.2f -> "
                  "%.2f  best tested %+.4f  selection shortfall %+.4f  final pick %+.4f  improved/worse/"
                  "unchanged %d/%d/%d  pick-rule McNemar p %.3f" % (model, p["n"], *p["chose_mean"], *p["replication"],
                                          *p["distinct"], p["best_tested_diff"],
                                          p["selection_shortfall_diff"], p["nominated_diff"],
                                          p["improved"], p["worse"], p["unchanged"],
                                          p["chose_mean_mcnemar_p"]))
    print("== paired 95% t intervals, Decision-rule minus Mechanism, primary set")
    for model, p in primary.items():
        r, d = p["replication_diff_ci"], p["distinct_diff_ci"]
        print("  %-20s n=%3d  re-testing share %+.2f pp [%+.2f, %+.2f]   distinct %+.2f [%+.2f, %+.2f]"
              % (model, r["n"], r["mean"], r["lo"], r["hi"], d["mean"], d["lo"], d["hi"]))
    json.dump(dict(primary=primary, sensitivity=sensitivity,
                   excluded={"%s|%s" % k: v for k, v in dropped.items()}),
              open(OUT, "w"), indent=1, sort_keys=True)
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
