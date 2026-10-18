#!/usr/bin/env python3
"""Scripted reference curve on the grid landscape: nominated fitness against replication k. No API calls.

Noise at the pool mean, over the viable pool's own standard deviation, is 0.065 on GB1 but 1.253 on NK uniform,
so the best k can differ between them. For k = 0 to 3 under the grid's noise model, it reports the nominated
sequence's fitness with standard errors and a bootstrapped argmax for each nomination rule. The comparator uses
an empirical-Bayes prior, not the pool's true distribution.
"""
import collections, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import campaign as C, landscape as L, policies as P, rng as R
from repdef.nk import NKLandscape

CV, FLOOR, GB1_MAX = 0.073, (1 / 557) / (285 / 557), 8.762
K, SEED, PCT = 1, 1, 93.0
N = int(os.environ.get("NRC_N", "1500"))
BOOT = 2000


def sig(f):
    return math.sqrt(FLOOR ** 2 + (abs(f) * CV) ** 2)


def nk():
    g = NKLandscape(k=K, seed=SEED, threshold_percentile=PCT, dist="uniform")
    f = GB1_MAX / max(g.fitness.values())
    return {k: v * f for k, v in g.fitness.items()}, g.pool


def noise_to_spread(fit, pool, label):
    vals = [fit[s] for s in pool]
    m, sd = st.mean(vals), st.stdev(vals)
    print("  %-16s pool mean %7.4f  pool sd %7.4f  sigma(mean) %7.4f  ratio %6.3f"
          % (label, m, sd, sig(m), sig(m) / sd))
    return sig(m) / sd


def policy(k, fit):
    """The pool-scope reference, with neighbours over the landscape's own letters."""
    pol = P.GreedyWithReplication(k, 0, "pool", "fresh_pool")
    pol.alphabet = P.alphabet_of(fit)
    return pol


def curve(fit, pool, rule, n, seed0):
    ps = tuple(sorted(pool))
    per_k = {}
    for k in (0, 1, 2, 3):
        vals = []
        for i in range(n):
            r = C.run(fit, pool, policy(k, fit), 0.0,
                      seed0 + i, 0.15, pool_sorted=ps, nomination=rule,
                      prior=("empirical" if rule == "shrinkage" else None),
                      noise_model="multiplicative", cv=CV, noise_floor=FLOOR)
            vals.append(r.nominated_true)
        per_k[k] = vals
    return per_k


def boot_argmax(per_k, boot=BOOT):
    """Resample campaigns with replacement, keeping the pairing across k, and record the argmax."""
    n = len(per_k[0])
    counts = collections.Counter()
    for b in range(boot):
        idx = [R._u64("boot", b, j) % n for j in range(n)]
        means = {k: sum(per_k[k][i] for i in idx) / n for k in per_k}
        counts[max(means, key=means.get)] += 1
    return counts


def main():
    fit, pool = nk()
    gb1 = L.load("gb1")
    print("=" * 96)
    print("WHERE THE NOISE SITS RELATIVE TO THE SIGNAL")
    print("=" * 96)
    r_nk = noise_to_spread(fit, pool, "NK uniform")
    r_gb1 = noise_to_spread(gb1.fitness, gb1.pool, "GB1")
    print("  NK carries %.0fx more noise per unit of spread than GB1." % (r_nk / r_gb1))

    out = {"noise_over_spread": {"nk": r_nk, "gb1": r_gb1}, "n": N, "curves": {}}
    for rule in ("mean", "max", "shrinkage"):
        print("\n" + "=" * 96)
        print("NOMINATED TRUE FITNESS vs REPLICATION BUDGET k   rule=%s   n=%d" % (rule, N))
        print("=" * 96)
        per_k = curve(fit, pool, rule, N, 8_200_000)
        print("  %3s %12s %10s %14s %12s" % ("k", "mean", "SE", "vs k=0", "paired SE"))
        base = per_k[0]
        rows = {}
        for k in (0, 1, 2, 3):
            v = per_k[k]
            m = st.mean(v)
            se = st.stdev(v) / math.sqrt(len(v))
            d = [a - b for a, b in zip(v, base)]
            dm = st.mean(d)
            dse = (st.stdev(d) / math.sqrt(len(d))) if k else 0.0
            print("  %3d %12.4f %10.4f %+14.4f %12.4f%s"
                  % (k, m, se, dm, dse, "" if k == 0 else
                     ("   %.1f SE" % (abs(dm / dse)) if dse else "")))
            rows[k] = dict(mean=m, se=se, diff_vs_k0=dm, paired_se=dse,
                           se_units=(abs(dm / dse) if dse else 0.0))
        counts = boot_argmax(per_k)
        kstar = max(rows, key=lambda k: rows[k]["mean"])
        tot = sum(counts.values())
        print("  bootstrapped argmax over %d resamples: %s"
              % (tot, {k: "%.1f%%" % (100.0 * counts[k] / tot) for k in sorted(counts)}))
        print("  k* = %d   (bootstrap support %.1f%%)" % (kstar, 100.0 * counts[kstar] / tot))
        out["curves"][rule] = dict(rows=rows, kstar=kstar,
                                   bootstrap={str(k): counts[k] / tot for k in counts})

    print("\n" + "=" * 96)
    print("WHAT THIS DOES TO THE CLAIM")
    print("=" * 96)
    ks = {r: out["curves"][r]["kstar"] for r in out["curves"]}
    print("  k* by nomination rule: %s" % ks)
    if any(v > 0 for v in ks.values()):
        print("  REPLICATION PAYS ON THE PRIMARY LANDSCAPE under at least one rule. So \"replication")
        print("  never pays in the real assay\" is a GB1 statement and must be restricted to the GB1")
        print("  panel. On NK the correct replication rate is k*, and every grid replication rate is")
        print("  read against THAT, not against zero.")
    else:
        print("  k* is zero under every rule here too, so the GB1 finding survives on a landscape")
        print("  where noise exceeds the spread, which makes it considerably stronger.")
    # The original step7_nk_reference_curve.json stays as the grid's record; this curve is written beside it.
    dest = os.path.join(ROOT, "results", "step7_nk_reference_curve_alphabet.json")
    json.dump(out, open(dest, "w"), indent=1)
    print("\nsaved %s" % os.path.relpath(dest, ROOT))         # relative: the run log is tracked
    return 0


if __name__ == "__main__":
    sys.exit(main())
