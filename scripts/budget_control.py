#!/usr/bin/env python3
"""Test whether the screen-precision effect is more than an effect of effective budget.

Condition "slots" is the real environment (15 rounds x 4 slots; a measured dead variant costs a slot).
Condition "useful" runs until a fixed number of viable readings, equalising information across screen
strengths. A third test checks whether the q curves collapse onto one function of the realised replication
fraction k / (k + (4-k)p), in which case q acts only through that identity.
"""
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import landscape as L, metrics as M, policies as P, sweep as S
from repdef import rng as R

N = int(os.environ.get("REPDEF_N", "3000"))
N_END = int(os.environ.get("REPDEF_N_END", "1200"))
QS = (0.0, 0.25, 0.5, 0.75, 1.0)
KS = (0, 1, 2, 3)
THRESH_VERBATIM = {           # thresh.py as written, sequential RNG, N=1200
    "phoq": {1.0: (28.109, 27.835, 23.815, 20.462), 2.0: (21.040, 23.320, 22.001, 19.073),
             4.0: (12.443, 15.574, 14.911, 15.076)},
    "gb1": {1.0: (5.141, 4.836, 4.247, 3.483), 2.0: (4.186, 4.292, 3.939, 3.224),
            4.0: (2.684, 3.097, 2.972, 2.648)},
}
POOL_RESTRICTED = {           # restricted pool, N=5000
    "phoq": {1.0: (37.833, 36.006, 31.642, 25.979), 2.0: (33.058, 33.298, 29.699, 24.476),
             4.0: (24.392, 26.223, 23.966, 21.294)},
    "gb1": {1.0: (5.916, 5.626, 5.091, 4.195), 2.0: (5.281, 5.326, 4.804, 4.005),
            4.0: (3.895, 4.362, 4.101, 3.517)},
}


def bootstrap_argmax(per_k, iters=2000, seed=7):
    """P(argmax = k), resampling campaigns jointly across k so pairing is preserved.

    Uses a plain seeded RNG: a bootstrap needs only reproducibility, not the counter-based scheme."""
    import random
    ks = sorted(per_k)
    n = len(per_k[ks[0]])
    cols = [per_k[k] for k in ks]
    counts = [0] * len(ks)
    rnd = random.Random(seed)
    rr = rnd.randrange
    for _ in range(iters):
        idx = [rr(n) for _ in range(n)]
        best_i, best_v = 0, None
        for ci, col in enumerate(cols):
            t = 0.0
            for j in idx:
                t += col[j]
            if best_v is None or t > best_v:
                best_i, best_v = ci, t
        counts[best_i] += 1
    return {ks[i]: counts[i] / iters for i in range(len(ks))}


def cell(ls, ps, k, sigma, q, mode, target_useful, n=None):
    pol = P.GreedyWithReplication(k, 0, "landscape", "fresh_pool")
    return S.run_cell(ls, pol, sigma, n or N, pool_sorted=ps, screen_q=q,
                      budget_mode=mode, target_useful=target_useful)


def main():
    for name in ("phoq", "gb1"):
        ls = L.load(name)
        ps = tuple(sorted(ls.pool))
        unit = S.SIGMA_UNIT[name]

        print("\n" + "=" * 108)
        print("ENDPOINT CHECK  %s   (targets: q=1 -> pool-restricted, q=0 -> verbatim thresh.py)"
              % name.upper())
        print("=" * 108)
        for ratio in (1.0, 2.0, 4.0):
            for q, tgt, lbl in ((1.0, POOL_RESTRICTED[name][ratio], "pool-restricted"),
                                (0.0, THRESH_VERBATIM[name][ratio], "verbatim thresh.py")):
                row, se = [], []
                for k in KS:
                    c = cell(ls, ps, k, unit * ratio, q, "slots", None, n=N_END)
                    m, e, _ = c.summary["true_of_nominated"]
                    row.append(m); se.append(e)
                dev = [abs(row[i] - tgt[i]) / se[i] for i in range(4)]
                am_mine = max(range(4), key=lambda i: row[i])
                am_tgt = max(range(4), key=lambda i: tgt[i])
                print("  r%.1f q=%.0f vs %-19s %s | dev/SE %s | argmax mine k=%d target k=%d %s"
                      % (ratio, q, lbl,
                         " ".join("%6.2f" % x for x in row),
                         " ".join("%4.1f" % d for d in dev), am_mine, am_tgt,
                         "MATCH" if am_mine == am_tgt else "DIFFER"))

        print("\n" + "=" * 108)
        print("BUDGET CONTROL  %s" % name.upper())
        print("=" * 108)
        for ratio in (2.0, 4.0):
            sigma = unit * ratio
            print("\n  --- ratio %.1f ---" % ratio)
            for mode, tu in (("slots", None), ("useful", 51)):
                print("   mode=%-7s %s" % (mode,
                      "(15 rounds x 4 slots)" if mode == "slots"
                      else "(run until %d viable readings)" % tu))
                for q in QS:
                    per_k, prec, rf, ru, nu = {}, [], [], [], []
                    row, se = [], []
                    for k in KS:
                        c = cell(ls, ps, k, sigma, q, mode, tu)
                        per_k[k] = [r.nominated_true for r in c.results]
                        m, e, _ = c.summary["true_of_nominated"]
                        row.append(m); se.append(e)
                        prec.append(st.mean([r.realized_precision for r in c.results]))
                        rf.append(st.mean([r.replication_fraction_of_useful
                                           for r in c.results]))
                        ru.append(st.mean([r.rounds_used for r in c.results]))
                        nu.append(st.mean([r.n_useful for r in c.results]))
                    bs = bootstrap_argmax(per_k)
                    am = max(bs, key=bs.get)
                    pd = M.paired_diff(per_k[am], per_k[0])
                    print("     q=%.2f %s | argmax k=%d P=%.2f%s | gain %+6.2f%%+-%.2f | "
                          "prec %.3f | rep.frac %s | rounds %.0f | useful %.0f"
                          % (q, " ".join("%6.2f" % x for x in row), am, bs[am],
                             "" if bs[am] > 0.95 else " NOT IDENTIFIED",
                             100 * pd["diff"] / row[0] if row[0] else 0,
                             100 * (pd["se"] or 0) / row[0] if row[0] else 0,
                             prec[0], " ".join("%.2f" % x for x in rf), ru[1], nu[1]))


if __name__ == "__main__":
    main()
