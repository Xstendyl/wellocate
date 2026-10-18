#!/usr/bin/env python3
"""Check that the design is paired by seed, and how treating it as unpaired changes the answer.

repdef/oracle.py keys measurement noise, instrument failures and screen admission on the seed, so at a fixed
seed every condition sees the same random numbers and the cells are dependent. Computed from the pilot:

(1) Alignment: every cell within a model must hold each seed exactly once.
(2) The cost of ignoring pairing: Welch drops the -2*cov/n term, so its standard error is too large or too
    small depending on the sign of the covariance.
(3) A numerical check that a wild cluster bootstrap with one Rademacher weight per seed equals a wild bootstrap
    on the centred paired differences:
      mean_B* - mean_A* = (1/n) sum_s w_s (r_Bs - r_As) = (1/n) sum_s w_s (d_s - mean(d)).
"""
import collections, json, math, os, statistics as st, sys
from statistics import NormalDist

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import repdef.rng as R

MEI, ALPHA, POWER, FAMILY = 0.06, 0.05, 0.80, 6
CONTRASTS = [("Aggregated", "Mechanism"), ("Decision-rule", "Mechanism")]
Z = NormalDist().inv_cdf(1 - ALPHA / FAMILY / 2) + NormalDist().inv_cdf(POWER)


def load(tag):
    p = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
    return [json.loads(l) for l in open(p) if l.strip()]


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "stage0"
    rows = load(tag)
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        by[(r["condition"], r["model"])][r["seed"]].append(r["nominated_true"])
    models = sorted({m for _c, m in by})
    conds = ["Blind", "Quantitative", "Mechanism", "Aggregated", "Decision-rule"]

    print("=" * 102)
    print("(1) ALIGNMENT  --  every seed exactly once per cell is what makes pairing available   tag=%s" % tag)
    print("=" * 102)
    ok = True
    for m in models:
        sets, dupes = [], 0
        for c in conds:
            cell = by.get((c, m), {})
            dupes += sum(1 for s in cell if len(cell[s]) != 1)
            sets.append(set(cell))
        same = all(s == sets[0] for s in sets)
        ok = ok and same and dupes == 0
        print("  %-30s seeds/cell %3d  identical sets %-5s  seeds appearing twice %d"
              % (m.split("/")[-1], len(sets[0]), same, dupes))
    print("  ALIGNED: %s" % ok)

    print()
    print("=" * 102)
    print("(2) WHAT IGNORING THE PAIRING COSTS")
    print("=" * 102)
    print("  %-22s %-26s %4s %8s %8s %7s %6s %9s" % ("model", "contrast", "n", "sd pair",
                                                     "sd unpr", "corr", "z(r)", "Welch is"))
    out = []
    for m in models:
        for i_, b_ in CONTRASTS:
            A, B = by[(b_, m)], by[(i_, m)]
            ks = sorted(set(A) & set(B))
            a = [A[k][0] for k in ks]
            b = [B[k][0] for k in ks]
            d = [y - x for x, y in zip(a, b)]
            n = len(ks)
            sd_p = st.stdev(d)
            sd_u = math.sqrt(st.variance(a) + st.variance(b))
            ma, mb = st.mean(a), st.mean(b)
            cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (n - 1)
            r = cov / (st.stdev(a) * st.stdev(b))
            zr = r * math.sqrt(n - 3)          # crude: r / (1/sqrt(n-3))
            verdict = "too SMALL" if sd_u < sd_p else "conservative"
            print("  %-22s %-26s %4d %8.4f %8.4f %+7.3f %+6.2f %9s"
                  % (m.split("/")[-1], "%s vs %s" % (i_, b_), n, sd_p, sd_u, r, zr, verdict))
            out.append(dict(model=m, contrast="%s vs %s" % (i_, b_), n=n, sd_paired=sd_p,
                            sd_unpaired=sd_u, corr=r, z_corr=zr, cov=cov))
    print("  z(r) uses 1/sqrt(n-3) as the null SE of r, so |z| < 1.96 means the pilot cannot establish")
    print("  the SIGN of the correlation. The paired estimator is correct whatever that sign turns out")
    print("  to be, because the covariance term belongs in the variance either way.")

    print()
    print("=" * 102)
    print("(3) SIZING CONSEQUENCE   n per cell = (z/MEI)^2 * variance,  z = %.4f, MEI = %.2f" % (Z, MEI))
    print("=" * 102)
    print("  %-22s %-26s %10s %10s %8s" % ("model", "contrast", "n unpaired", "n paired", "ratio"))
    for o in out:
        nu = math.ceil((Z / MEI) ** 2 * o["sd_unpaired"] ** 2)
        npd = math.ceil((Z / MEI) ** 2 * o["sd_paired"] ** 2)
        o["n_unpaired"], o["n_paired"] = nu, npd
        print("  %-22s %-26s %10d %10d %8.3fx"
              % (o["model"].split("/")[-1], o["contrast"], nu, npd, npd / nu))
    print("  Pairing is not automatically cheaper. It is correct; the cost moves per cell.")

    print()
    print("=" * 102)
    print("(4) IDENTITY CHECK  --  one weight per seed on the two-sample statistic")
    print("=" * 102)
    worst = 0.0
    for m in models:
        for i_, b_ in CONTRASTS:
            A, B = by[(b_, m)], by[(i_, m)]
            ks = sorted(set(A) & set(B))
            a = [A[k][0] for k in ks]
            b = [B[k][0] for k in ks]
            d = [y - x for x, y in zip(a, b)]
            n = len(ks)
            ma, mb, md = st.mean(a), st.mean(b), st.mean(d)
            ra = [x - ma for x in a]
            rb = [x - mb for x in b]
            rd = [x - md for x in d]
            for rep in range(200):
                w = [1 if R._u64("id", rep, j) % 2 else -1 for j in range(n)]
                two = st.mean([w[j] * rb[j] for j in range(n)]) - \
                      st.mean([w[j] * ra[j] for j in range(n)])
                one = st.mean([w[j] * rd[j] for j in range(n)])
                worst = max(worst, abs(two - one))
    print("  max |two-sample clustered draw - paired-difference draw| over %d draws: %.3e" % (200 * 6, worst))
    print("  IDENTICAL to floating point, so the paired-difference bootstrap IS the seed-clustered one.")

    dst = os.path.join(ROOT, "results", "seed_pairing_%s.json" % tag)
    with open(dst, "w") as f:
        json.dump(dict(tag=tag, aligned=ok, z=Z, mei=MEI, contrasts=out,
                       identity_max_abs_diff=worst), f, indent=1)
    print()
    print("  wrote %s" % os.path.relpath(dst, ROOT))


if __name__ == "__main__":
    main()
