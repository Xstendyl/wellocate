#!/usr/bin/env python3
"""Power calculation for the grid's primary outcome, the selection shortfall.

The shortfall is best true value measured minus true value nominated. Power depends on the paired per-campaign
SD of the shortfall difference between two nomination rules, estimated from a scripted policy on the grid
landscape with a prior fitted to measured readings. An across-seed overdispersion factor of 1.25x on the SD
(1.5625x on the campaign count) is also reported.

  python3 scripts/grid_power.py
"""
import json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import campaign as C, policies as P
from repdef.nk import NKLandscape

CV, FLOOR, GB1_MAX = 0.073, (1 / 557) / (285 / 557), 8.762
K, SEED, PCT = 1, 1, 93.0
OVER_SD = 1.25
N = int(os.environ.get("GP_N", "1500"))


def build():
    nk = NKLandscape(k=K, seed=SEED, threshold_percentile=PCT, dist="uniform")
    f = GB1_MAX / max(nk.fitness.values())
    return {k: v * f for k, v in nk.fitness.items()}, nk.pool


def shortfalls(fit, pool, policy, nomination, n, seed0, prior="empirical"):
    ps = tuple(sorted(pool))
    out = []
    for i in range(n):
        r = C.run(fit, pool, policy, 0.0, seed0 + i, 0.15, pool_sorted=ps,
                  nomination=nomination, prior=prior,
                  noise_model="multiplicative", cv=CV, noise_floor=FLOOR)
        out.append(r.best_true_measured - r.nominated_true)
    return out


def n_for(effect, sd, target_se=2.8, inflate=1.0):
    """Campaigns per arm for a paired difference of `effect` at `target_se` standard errors."""
    return math.ceil(((target_se * sd * inflate) / abs(effect)) ** 2)


def main():
    fit, pool = build()
    vals = [fit[s] for s in pool]
    prior = (st.mean(vals), st.variance(vals))
    pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")

    print("=" * 92)
    print("GRID POWER on the selection shortfall   NK uniform K=%d seed=%d pct=%.1f  n=%d"
          % (K, SEED, PCT, N))
    print("=" * 92)
    rows = {}
    for rule in ("max", "mean", "shrinkage"):
        sf = shortfalls(fit, pool, pol, rule, N, 6_100_000,
                        "empirical" if rule == "shrinkage" else None)
        rows[rule] = sf
        print("  shortfall under %-10s mean %.4f  sample sd %.4f  SE %.4f  zero in %5.1f%% of campaigns"
              % (rule, st.mean(sf), st.stdev(sf), st.stdev(sf) / math.sqrt(len(sf)),
                 100.0 * sum(1 for x in sf if abs(x) < 1e-12) / len(sf)))

    # The paired sd is much smaller than either arm's sd because the same history feeds both rules.
    paired = [a - b for a, b in zip(rows["max"], rows["shrinkage"])]
    sd_paired = st.stdev(paired)
    sd_arm = st.stdev(rows["max"])
    print()
    print("  max-single minus shrinkage, paired   %+.4f  paired sd %.4f  (unpaired arm sd %.4f)"
          % (st.mean(paired), sd_paired, sd_arm))
    print("  pairing reduces the sd by            %.2fx" % (sd_arm / sd_paired))

    print()
    print("=" * 92)
    print("CAMPAIGNS PER CELL, at 2.8 SE which is two-sided 0.005, paired within campaign")
    print("=" * 92)
    # The ordinary normal calculation, with and without the overdispersion factor.
    print("  %-28s %14s %16s %14s" % ("difference to detect", "uninflated", "x1.25 sd",
                                      "count x1.57"))
    plan = []
    for eff in (0.005, 0.010, 0.020, 0.030, 0.050):
        a = n_for(eff, sd_paired, 2.8, 1.0)
        b = n_for(eff, sd_paired, 2.8, OVER_SD)
        print("  shortfall difference %.3f %14s %16s %14s"
              % (eff, "{:,}".format(a), "{:,}".format(b), "%.2fx" % (b / max(1, a))))
        plan.append(dict(effect=eff, n_uninflated=a, n_overdispersed=b))

    # Target effect: the landscape's own max-versus-shrinkage gap.
    target = abs(st.mean(paired))
    n_t = n_for(target, sd_paired, 2.8, OVER_SD)
    print()
    print("  The landscape's own max-minus-shrinkage gap is %.4f, so an intervention that closes the"
          % target)
    print("  shortfall must move at least that far. Sized on it, at 2.8 SE with the 1.25x sd")
    print("  inflation: %s campaigns per cell." % "{:,}".format(n_t))
    cells = 5 * 3
    print()
    print("  GRID SHAPE   5 conditions x 3 models = %d cells" % cells)
    print("  at %s campaigns per cell that is %s campaigns, %s LLM calls at 16 per campaign"
          % ("{:,}".format(n_t), "{:,}".format(n_t * cells), "{:,}".format(n_t * cells * 16)))
    print("  which is far beyond the $600 stage ceiling, so the count must be set by BUDGET and the")
    print("  detectable effect REPORTED, not the reverse. See the spec's sample-size section.")
    for n_cell in (20, 30, 40, 60):
        det = 2.8 * sd_paired * OVER_SD / math.sqrt(n_cell)
        print("    %3d campaigns/cell -> %4d campaigns, %5d calls, detectable shortfall difference %.4f"
              % (n_cell, n_cell * cells, n_cell * cells * 16, det))
    out = dict(n_per_cell_measured=N, sd_paired=sd_paired, sd_arm=sd_arm,
               mean_paired=st.mean(paired), overdispersion_sd=OVER_SD,
               overdispersion_count=OVER_SD ** 2, plan=plan,
               n_for_landscape_gap=n_t,
               detectable=[{"n_per_cell": n, "cells": cells,
                            "detectable_difference": 2.8 * sd_paired * OVER_SD / math.sqrt(n)}
                           for n in (20, 30, 40, 60)],
               shortfall_means={k: st.mean(v) for k, v in rows.items()},
               shortfall_sds={k: st.stdev(v) for k, v in rows.items()})
    json.dump(out, open(os.path.join(ROOT, "results", "step6_grid_power.json"), "w"), indent=1)
    print("\nsaved results/step6_grid_power.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
