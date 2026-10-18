#!/usr/bin/env python3
"""Regress the crossing round on campaign length to test three timing hypotheses at once.

    absolute clock   predicts slope = 0
    budget fraction  predicts slope = the fraction, 0.41 to 0.62
    rounds-remaining predicts slope = 1
"""
import collections, glob, json, math, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def crossings(tag_glob):
    """Crossing round per campaign, grouped by campaign length, from the per-call logs."""
    out = collections.defaultdict(list)
    for p in sorted(glob.glob(os.path.join(ROOT, "results", tag_glob))):
        rows = [json.loads(l) for l in open(p)]
        R = rows[0].get("total_rounds")
        if R is None:
            continue
        camps = collections.defaultdict(list)
        for r in rows:
            if r["kind"] != "nomination":
                camps[r["campaign_seed"]].append(r)
        for seed, calls in camps.items():
            seen, per = set(), []
            for r in sorted(calls, key=lambda x: (x["round"], x["kind"] != "round")):
                if not r["parsed"]:
                    continue
                per.append((r["round"],
                            sum(1 for s in r["parsed"] if s in seen) / len(r["parsed"])))
                seen.update(r["parsed"])
            f = [rd for rd, v in per if v > 0.5]
            out[R].append(f[0] if f else None)
    return out


def main():
    data = crossings("pilot_len*_calls.jsonl")
    data2 = crossings("pilot_L*n20_calls.jsonl")
    for R, v in data2.items():
        if v:
            data[R] = v                      # prefer the larger n when available
    xs, ys = [], []
    print("  %-8s %4s %9s %s" % ("length", "n", "censored", "crossing rounds"))
    for R in sorted(data):
        got = [c for c in data[R] if c is not None]
        cens = sum(1 for c in data[R] if c is None)
        print("  %-8d %4d %9d %s" % (R, len(data[R]), cens, sorted(got)))
        for c in got:
            xs.append(float(R)); ys.append(float(c))
    n = len(xs)
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    inter = my - slope * mx
    resid = [y - (inter + slope * x) for x, y in zip(xs, ys)]
    # regression residual sd, df = n-2
    sd_reg = math.sqrt(sum(r * r for r in resid) / (n - 2))
    # pooled within-group sd, df = n - number of groups, the conservative choice
    groups = sorted(set(xs))
    ss_w = 0.0
    for g in groups:
        yy = [y for x, y in zip(xs, ys) if x == g]
        m = st.mean(yy)
        ss_w += sum((v - m) ** 2 for v in yy)
    sd_within = math.sqrt(ss_w / (n - len(groups)))
    print("\n  n = %d campaigns across %d lengths.  Sxx = %.1f" % (n, len(groups), sxx))
    print("  mean crossing round = %.3f" % my)
    for lbl, sd, df in (("regression residual", sd_reg, n - 2),
                        ("pooled within-group", sd_within, n - len(groups))):
        se = sd / math.sqrt(sxx)
        lo, hi = slope - 1.96 * se, slope + 1.96 * se
        print("\n  using the %s sd = %.3f (df %d):" % (lbl, sd, df))
        print("    slope = %+.4f  SE %.4f   95%% CI [%+.4f, %+.4f]" % (slope, se, lo, hi))
        for hyp, val in (("absolute clock", 0.0), ("budget fraction, L15 fit", 0.41),
                         ("budget fraction, pooled fit", 0.52),
                         ("budget fraction, L10 fit", 0.62), ("rounds-remaining", 1.0)):
            d = abs(val - slope) / se
            print("    %-30s predicts %+.2f -> %5.1f SE away   %s"
                  % (hyp, val, d, "CONSISTENT" if d < 2 else "REJECTED"))
    print("\n  Reconciling the earlier permutation p: the scaled L15 set {4,6,12,16,24} has 2 of 5")
    print("  at or below 10, so 0.4^5 = 0.01024 exactly; the 0.01046 reported was Monte Carlo over")
    print("  200,000 draws, whose SE is 0.00022, so the two agree within 1 SE. That test is")
    print("  retired anyway: it raised a proportion estimated from five points to the fifth power.")


if __name__ == "__main__":
    main()
