#!/usr/bin/env python3
"""Robustness checks: sigma calibration, exploration confound, nomination rule, denominator, and power."""
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import landscape as L, sweep as S, metrics as M, policies as P, campaign as C

N = int(os.environ.get("REPDEF_N", "2000"))
RATIOS = (1.0, 2.0, 4.0)


def hdr(t):
    print("\n" + "=" * 100)
    print(t)
    print("=" * 100)


# ---------------------------------------------------------------- sigma calibration first: it is an input
def f6_sigma_units(ls, n=400):
    """Sigma unit = median(top1 - top2) of true values among a 60-measurement campaign, per policy.

    The gap depends on which sequences got measured, so it is compared across policies."""
    ps = tuple(sorted(ls.pool))
    out = {}
    configs = [
        ("random from pool",       P.RandomPolicy(0),                               None),
        ("greedy k=0, pool",       P.GreedyWithReplication(0, 0, "pool", "fresh_pool"), None),
        ("greedy k=1, pool",       P.GreedyWithReplication(1, 0, "pool", "fresh_pool"), None),
        ("greedy k=0, unrestricted", P.GreedyWithReplication(0, 0, "landscape", "any_pool"),
                                   frozenset(ls.fitness)),
    ]
    for label, pol, measurable in configs:
        gaps = []
        for i in range(n):
            # sigma=0 and no failures, so the unit depends only on the landscape and the policy's reach.
            r = C.run(ls.fitness, ls.pool, pol, 0.0, 10_000 + i, 0.0,
                      pool_sorted=ps, measurable=measurable)
            tv = sorted((ls.fitness[s] for s in {h.seq for h in r.history
                                                 if h.outcome == "ok"}), reverse=True)
            if len(tv) >= 2:
                gaps.append(tv[0] - tv[1])
        out[label] = (st.median(gaps), st.mean(gaps), len(gaps))
    return out


def main():
    for name in ("phoq", "gb1"):
        ls = L.load(name)
        gmax = max(ls.fitness[s] for s in ls.pool)
        ps = tuple(sorted(ls.pool))
        unit = S.SIGMA_UNIT[name]

        hdr("F6  SIGMA CALIBRATION CIRCULARITY  --  %s   (inherited unit = %.2f)"
            % (name.upper(), unit))
        u = f6_sigma_units(ls)
        for label, (med, mean, k) in u.items():
            print("  %-26s median gap %8.4f   mean %8.4f   (n=%d)   ratio to inherited: %.2fx"
                  % (label, med, mean, k, med / unit))
        rand_unit = u["random from pool"][0]
        print("  VERDICT: inherited %.2f vs random-calibrated %.4f -> %s"
              % (unit, rand_unit,
                 "CIRCULAR, and the unit moves %.2fx" % (rand_unit / unit)))

        hdr("F1  EXPLORATION CONFOUND  --  %s   champion-replication vs random-replication"
            % name.upper())
        print("  Both arms spend k slots re-measuring and 4-k exploring the CHAMPION's")
        print("  neighbourhood. They differ only in WHICH sequence gets re-measured.")
        for ratio in RATIOS:
            sigma = unit * ratio
            base = S.run_cell(ls, P.GreedyWithReplication(0, 0), sigma, N, pool_sorted=ps)
            champ = S.run_cell(ls, P.GreedyWithReplication(1, 0), sigma, N, pool_sorted=ps)
            randr = S.run_cell(ls, P.GreedyRandomReplication(1, 0), sigma, N, pool_sorted=ps)
            b = [r.nominated_true for r in base.results]
            pc = M.paired_diff([r.nominated_true for r in champ.results], b)
            pr = M.paired_diff([r.nominated_true for r in randr.results], b)
            m0 = st.mean(b)
            share = (100 * pr["diff"] / pc["diff"]) if pc["diff"] else float("nan")
            print("   ratio %.1f  k=0 %7.3f | champion-rep %+7.3f+-%.3f (%+5.1f%%) | "
                  "random-rep %+7.3f+-%.3f (%+5.1f%%) | control captures %5.1f%% of the gain"
                  % (ratio, m0, pc["diff"], pc["se"], 100 * pc["diff"] / m0,
                     pr["diff"], pr["se"], 100 * pr["diff"] / m0, share))

        hdr("F3  NOMINATION-RULE SENSITIVITY  --  %s" % name.upper())
        vals = [ls.fitness[s] for s in ls.pool]
        prior = (st.mean(vals), st.variance(vals))
        for rule in ("mean", "max", "shrinkage"):
            line = []
            for ratio in RATIOS:
                sigma = unit * ratio
                cells = {}
                for k in (0, 1, 2, 3):
                    cells[k] = S.run_cell(ls, P.GreedyWithReplication(k, 0), sigma, N,
                                          nomination=rule,
                                          prior=prior if rule == "shrinkage" else None,
                                          pool_sorted=ps)
                means = {k: st.mean([r.nominated_true for r in cells[k].results])
                         for k in cells}
                bk = max(means, key=means.get)
                pd = M.paired_diff([r.nominated_true for r in cells[bk].results],
                                   [r.nominated_true for r in cells[0].results])
                sig = "SIG" if pd["se"] and abs(pd["diff"]) > 2 * pd["se"] else "n.s."
                line.append("r%.0f: best k=%d %+6.2f%%+-%.2f %s"
                            % (ratio, bk, 100 * pd["diff"] / means[0],
                               100 * (pd["se"] or 0) / means[0], sig))
            print("  %-10s  %s" % (rule, "  |  ".join(line)))

        hdr("F4  DENOMINATOR SENSITIVITY  --  %s   (global pool max = %.3f)"
            % (name.upper(), gmax))
        for ratio in RATIOS:
            sigma = unit * ratio
            row_m, row_g = [], []
            for k in (0, 1, 2, 3):
                c = S.run_cell(ls, P.GreedyWithReplication(k, 0), sigma, N, pool_sorted=ps)
                row_m.append(c.summary["regression_loss"][0])
                row_g.append(c.summary["regression_loss_global"][0])
            print("   ratio %.1f  vs MAX MEASURED : %s   (spread %.3f)"
                  % (ratio, " ".join("%8.3f" % x for x in row_m), max(row_m) - min(row_m)))
            print("             vs GLOBAL POOL MAX: %s   (spread %.3f)"
                  % (" ".join("%8.3f" % x for x in row_g), max(row_g) - min(row_g)))

        hdr("F5  POWER  --  %s" % name.upper())
        for ratio in RATIOS:
            sigma = unit * ratio
            c0 = S.run_cell(ls, P.GreedyWithReplication(0, 0), sigma, N, pool_sorted=ps)
            c1 = S.run_cell(ls, P.GreedyWithReplication(1, 0), sigma, N, pool_sorted=ps)
            a = [r.nominated_true for r in c1.results]
            b = [r.nominated_true for r in c0.results]
            pd = M.paired_diff(a, b)
            sd_pair = pd["sd_of_diff"]
            sd_unp = (st.stdev(a) ** 2 + st.stdev(b) ** 2) ** 0.5
            claimed = {1.0: 0.0, 2.0: 0.108, 4.0: 0.252}[ratio] * st.mean(b) \
                if name == "phoq" else {1.0: 0.0, 2.0: 0.025, 4.0: 0.154}[ratio] * st.mean(b)
            obs = pd["diff"]
            print("   ratio %.1f  observed diff %+7.4f+-%.4f  rho=%.3f | sd_paired %7.3f "
                  "sd_unpaired %7.3f" % (ratio, obs, pd["se"], pd["correlation"] or 0,
                                         sd_pair, sd_unp))
            for lbl, eff in (("CLAIMED effect", claimed), ("OBSERVED effect", obs)):
                if eff and abs(eff) > 1e-9:
                    npair = M.power_n(sd_pair, eff)
                    nunp = M.power_n(sd_unp, eff)
                    print("             n for %-15s (%+7.4f): paired %8s  unpaired %8s"
                          % (lbl, eff, "{:,}".format(npair), "{:,}".format(nunp)))


if __name__ == "__main__":
    main()
