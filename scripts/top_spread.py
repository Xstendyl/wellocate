#!/usr/bin/env python3
"""How tightly each landscape's best candidates are bunched, in units of assay noise (descriptive).

For the grid (nk/K1/seed1), scrambled GB1 (gb1/scramble:20261003) and scrambled PhoQ (phoq/scramble:20261004), the
landscapes the paper runs, read through wellocate.landscapes:
  ten best    (best value minus the 10th best value) / SD
  top tenth   (best value minus the 90th percentile of the viable values) / SD
where SD is the reading noise at the top at assay noise, CV x best value (wellocate.env.NOISE_PRESETS["assay"]). The
oracle's noise floor is added in quadrature as a check and changes neither ratio at two decimals. A small ratio
means one noisy reading cannot tell the leaders apart, which is when re-testing them pays.

The script aborts unless gb1/real and phoq/real hold the same multiset of values, and the same multiset of viable values,
as the scrambles the paper runs, so the scrambled and real landscapes give the same numbers.

Usage: python3 scripts/top_spread.py     (writes results/top_spread.json)
"""
import json, math, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from wellocate import env as W                                   # noqa: E402
from wellocate import landscapes as LS                           # noqa: E402

OUT = os.path.join(ROOT, "results", "top_spread.json")
LANDS = (("grid", "nk/K1/seed1", None), ("GB1", "gb1/scramble:20261003", "gb1/real"),
         ("PhoQ", "phoq/scramble:20261004", "phoq/real"))
TOP_N, PCT = 10, 90


def spread(env):
    cv = W.NOISE_PRESETS["assay"]
    viable = sorted((env.fit[s] for s in env.pool), reverse=True)
    best, tenth = viable[0], viable[TOP_N - 1]
    pct = float(np.percentile(viable, PCT))
    sd = cv * best
    sd_floor = math.sqrt(W.NOISE_FLOOR ** 2 + sd ** 2)
    return dict(best=best, tenth_best=tenth, viable_p90=pct, noise_cv=cv, sd_at_top=sd, sd_at_top_with_floor=sd_floor,
                ten_best_in_sd=(best - tenth) / sd, top_tenth_in_sd=(best - pct) / sd,
                ten_best_in_sd_with_floor=(best - tenth) / sd_floor, top_tenth_in_sd_with_floor=(best - pct) / sd_floor)


def main():
    out = {}
    for name, inst, real in LANDS:
        env = LS.instance(inst)
        row = dict(instance=inst, **spread(env))
        if real:
            renv = LS.instance(real)
            if sorted(renv.fit.values()) != sorted(env.fit.values()):
                raise SystemExit("ABORT: %s and %s do not hold the same values" % (inst, real))
            if sorted(renv.fit[s] for s in renv.pool) != sorted(env.fit[s] for s in env.pool):
                raise SystemExit("ABORT: %s and %s do not hold the same viable values" % (inst, real))
            row["same_values_as"] = real
        for f in ("ten_best_in_sd", "top_tenth_in_sd"):
            if round(row[f], 2) != round(row[f + "_with_floor"], 2):
                raise SystemExit("ABORT: %s %s moves with the noise floor" % (name, f))
        out[name] = row
        print("%-5s %-24s best %.4f, 10th best %.4f, viable p90 %.4f, SD at top %.4f | ten best %.2f SD, top tenth "
              "%.1f SD%s" % (name, inst, row["best"], row["tenth_best"], row["viable_p90"], row["sd_at_top"],
                             row["ten_best_in_sd"], row["top_tenth_in_sd"],
                             " | same values as %s" % real if real else ""))
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print("written %s" % os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
