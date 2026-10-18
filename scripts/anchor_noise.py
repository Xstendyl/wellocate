#!/usr/bin/env python3
"""Estimate whether a signal-to-noise ratio of 4.0 occurs in real deep mutational scanning assays.

Noise is estimated from published GB1 data (Wu et al. 2016, eLife 5:e16965) by Poisson read sampling and from
the published replicate correlation, taking the larger defensible noise wherever an assumption could go
either way. PhoQ (Podgornaia and Laub 2015, Science 347:673) is used for the share of functional variants.
"""
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import landscape as L

# Published GB1 depth
N_IN_TOT, N_SEL_TOT, N_VARIANTS = 89_075_246, 45_587_128, 160_000
READS_IN, READS_SEL = N_IN_TOT / N_VARIANTS, N_SEL_TOT / N_VARIANTS
R_REPLICATE = 0.97
FILTER_MIN_IN = 10

UNITS = {            # sigma unit = median campaign top1-top2 gap
    "phoq": {"inherited": 4.24, "random": 5.807},
    "gb1": {"inherited": 0.42, "random": 0.557},
}


def line(c="-"):
    print(c * 100)


def main():
    gb1 = L.load("gb1")
    pool_vals = [gb1.fitness[s] for s in gb1.pool]
    sd_pool = st.pstdev(pool_vals)
    mean_pool = st.mean(pool_vals)
    top = sorted(pool_vals, reverse=True)
    champ_level = st.median(top[:200])       # where a campaign's champion actually sits

    line("=")
    print("GB1: measurement noise, estimated two independent ways")
    line("=")
    print("  the viable pool: n=%d  mean %.3f  sd %.3f" % (len(pool_vals), mean_pool, sd_pool))
    print("  a campaign's champion sits near fitness %.3f (median of the pool's top 200)"
          % champ_level)
    print()

    # ---- Method 1: Poisson read sampling, a lower bound on total noise -------------------
    print("  METHOD 1. Poisson read-sampling noise, from the published depth.")
    print("  Var(log w) = 1/n_sel + 1/n_in (+ WT terms, negligible: WT is abundant).")
    var_log = 1.0 / READS_SEL + 1.0 / READS_IN
    cv_log = math.sqrt(var_log)
    print("    average depth: %.0f input, %.0f selected reads per variant"
          % (READS_IN, READS_SEL))
    print("    Var(log w) = 1/%.0f + 1/%.0f = %.6f   ->  CV = %.1f%%"
          % (READS_SEL, READS_IN, var_log, 100 * cv_log))
    print("    noise is MULTIPLICATIVE: sigma_linear(f) = f x CV, which is the")
    print("    heteroscedasticity FLIGHTED reports. At the champion level f=%.2f:" % champ_level)
    sig_poisson = champ_level * cv_log
    print("      sigma = %.3f fitness units" % sig_poisson)
    # the worst-sampled variant that survives the filter
    var_log_worst = 1.0 / FILTER_MIN_IN + 1.0 / FILTER_MIN_IN
    sig_worst = champ_level * math.sqrt(var_log_worst)
    print("    ADVERSARIAL BOUND: a variant at the read-count filter (n_in = n_sel = %d)"
          % FILTER_MIN_IN)
    print("      CV = %.1f%%  ->  sigma = %.3f at the champion level"
          % (100 * math.sqrt(var_log_worst), sig_worst))
    print("      but such variants are the WORST-sampled 6.6%% that barely passed the filter,")
    print("      and an enriched high-fitness variant is by definition well sampled after")
    print("      selection, so this is an upper extreme and not the champion's regime.")
    print()

    # ---- METHOD 2: from the published replicate correlation ------------------------------
    print("  METHOD 2. From the published replicate agreement, Pearson r = %.2f." % R_REPLICATE)
    print("  For X1 = T + e1 and X2 = T + e2 with equal error variance,")
    print("  r = var(T)/(var(T)+var(e)), so sd(e) = sd(T) x sqrt((1-r)/r).")
    frac = math.sqrt((1 - R_REPLICATE) / R_REPLICATE)
    sig_repl = sd_pool * frac
    print("    sd(e) = %.3f x sd(T) = %.3f x %.3f = %.3f fitness units"
          % (frac, frac, sd_pool, sig_repl))
    print("    NOTE THIS IS GENEROUS TO THE PAPER: r=0.97 was reported for SINGLE AND DOUBLE")
    print("    mutants, which are the best-sampled variants, so the true landscape-wide")
    print("    correlation is LOWER and the implied noise HIGHER. Using the pool's sd as sd(T)")
    print("    rather than the subset's also inflates the estimate.")
    print()

    line()
    print("  WHERE REAL GB1 SITS ON THE RATIO AXIS")
    line()
    for unit_name, unit in UNITS["gb1"].items():
        print("   in the %s-calibrated unit (sigma_unit = %.3f):" % (unit_name, unit))
        for lbl, s in (("Poisson, average depth", sig_poisson),
                       ("replicate correlation r=0.97", sig_repl),
                       ("Poisson, worst variant at the filter", sig_worst)):
            print("     %-38s sigma %6.3f  ->  ratio %5.2f" % (lbl, s, s / unit))
    print()
    print("   HOW MUCH WOULD HAVE TO BE WRONG for real GB1 to reach ratio 4.0?")
    need = 4.0 * UNITS["gb1"]["random"]
    print("     ratio 4.0 in the random-calibrated unit needs sigma = %.3f" % need)
    print("     that is %.1fx the Poisson estimate and %.1fx the replicate estimate."
          % (need / sig_poisson, need / sig_repl))
    print("     By Method 1 it needs CV = %.0f%%, i.e. effective depth of about %.0f reads"
          % (100 * need / champ_level, 2.0 / (need / champ_level) ** 2))
    print("     per variant against the published ~285-557.")
    print("     By Method 2 it needs replicate r = %.3f against the published 0.97."
          % (1.0 / (1.0 + (need / sd_pool) ** 2)))
    print()

    # ---- PhoQ ----------------------------------------------------------------------------
    phoq = L.load("phoq")
    pv = sorted((phoq.fitness[s] for s in phoq.pool), reverse=True)
    allv = sorted(phoq.fitness.values(), reverse=True)
    line("=")
    print("PhoQ: no replicate data located, and a separate problem")
    line("=")
    print("  Podgornaia & Laub report 1,659 FUNCTIONAL variants of 160,000 (1.04%).")
    print("  Our viable pool, threshold > 1.0, holds %d (%.2f%%), which is %.1fx more."
          % (len(pv), 100 * len(pv) / 160000, len(pv) / 1659.0))
    print("  The 1,659th highest value in our file is %.3f, so the published functional call"
          % allv[1658])
    print("  corresponds to a threshold near %.1f in these units, not 1.0." % allv[1658])
    print("  CONSEQUENCE: the design space the whole experiment restricts to is NOT the")
    print("  published functional set. That is a methods problem independent of the noise")
    print("  question, and it changes pool size, sigma unit and every ratio.")
    print()
    print("  Their assay was a TWO-STEP selection with a binary functional call, so it")
    print("  publishes no per-variant noise to anchor against. No PhoQ anchor is available")
    print("  from this source, and I am not going to manufacture one.")


if __name__ == "__main__":
    main()
