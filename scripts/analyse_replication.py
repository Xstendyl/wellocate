#!/usr/bin/env python3
"""Read the out-of-sample replication of the Decision-rule effect by its pre-registered rule.

The primary outcome is the seed-paired difference in nominated_true, Decision-rule minus Mechanism, for
DeepSeek V3.1, excluding campaigns whose nomination did not parse. The interval is a percentile bootstrap over
seeds (20,000 resamples). The label is "replicates" if the paired mean is above 0 and the 95% interval excludes
zero, "direction holds, not significant" if the mean is above 0 and the interval includes zero, and "does not
replicate" otherwise.

Usage: python3 scripts/analyse_replication.py      (writes results/replication_decision_rule.json)
"""
import collections, glob, gzip, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_grid as AG                                   # noqa: E402
import replicate_decision_rule as RD                        # noqa: E402

OUT = os.path.join(ROOT, "results", "replication_decision_rule.json")
TIE = 1e-12


def label(mean, lo, hi):
    if mean <= 0:
        return "does not replicate"
    return "replicates" if lo > 0 or hi < 0 else "direction holds, not significant"


def calls(tag):
    p = os.path.join(ROOT, "results", "grid_%s_calls.jsonl" % tag)
    srcs = [open(p)] if os.path.exists(p) else [gzip.open(g, "rt") for g in sorted(glob.glob(
        os.path.join(ROOT, "results", "grid_%s_calls" % tag, "*.jsonl.gz")))]
    for fh in srcs:
        with fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)


def main():
    rows = AG.load(RD.TAG)
    planned = set(range(RD.SEED0, RD.SEED0 + RD.N))
    stray = [r["seed"] for r in rows if r["seed"] not in planned]
    if stray or any(r["model"] != RD.MODEL or r["condition"] not in RD.CONDITIONS for r in rows):
        raise SystemExit("REFUSED: the file holds a campaign outside the registered design: %s" % stray[:5])
    fb = AG.fallback_seeds([RD.TAG])
    kept, dropped = AG.drop_fallbacks(rows, fb)
    by = collections.defaultdict(dict)
    for r in kept:
        by[r["condition"]][r["seed"]] = r
    a, b = by["Mechanism"], by["Decision-rule"]
    seeds = sorted(set(a) & set(b))
    d = [b[s]["nominated_true"] - a[s]["nominated_true"] for s in seeds]
    mean = st.mean(d)
    lo, hi = AG.boot_ci(d, tag="0ak")
    se = st.stdev(d) / math.sqrt(len(d))
    prov = collections.defaultdict(collections.Counter)
    for c in calls(RD.TAG):
        prov[c.get("rung")][c.get("provider") or "unrecorded"] += 1
    arm = {"instructed": "Mechanism", "decision_rule": "Decision-rule"}
    out = dict(
        tag=RD.TAG, model=RD.MODEL, planned_per_arm=RD.N,
        campaigns={c: sum(1 for r in rows if r["condition"] == c) for c in RD.CONDITIONS},
        fallbacks_excluded={c: dropped.get((c, RD.MODEL), 0) for c in RD.CONDITIONS},
        pairs=len(seeds), mean=mean, ci95_boot=[lo, hi], label=label(mean, lo, hi),
        improved=sum(v > TIE for v in d), worse=sum(v < -TIE for v in d),
        unchanged=sum(abs(v) <= TIE for v in d),
        wild_p=AG.paired_wild_p(d, tag="0ak"), se=se, ci95_normal=[mean - 1.96 * se, mean + 1.96 * se],
        arm_means={c: st.mean(x[s]["nominated_true"] for s in seeds) for c, x in
                   (("Mechanism", a), ("Decision-rule", b))},
        provider_calls={arm[k]: dict(v.most_common()) for k, v in prov.items() if k in arm},
        spend_usd=sum(r.get("spend") or 0 for r in rows))
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))
    print("LABEL: %s" % out["label"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
