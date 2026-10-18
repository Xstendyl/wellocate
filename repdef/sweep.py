"""Run cells of the design (sigma ratio x k) and report them with standard errors.

Campaign i uses seed i for every policy, so all arms share one noise field and contrasts
against k=0 are reported paired, with the arm-to-arm correlation.
"""

import collections

from repdef import campaign as C
from repdef import metrics as M
from repdef import policies as P

# Older sigma units, calibrated under a greedy policy. Kept only to reproduce the reference tables.
SIGMA_UNIT_INHERITED = {"phoq": 4.24, "gb1": 0.42}

# Sigma unit in use: the median top1-top2 gap among a campaign's measured set, calibrated under
# random exploration, which uses no fitness information.
SIGMA_UNIT = {"phoq": 5.807, "gb1": 0.557}
THRESHOLD = {"phoq": 1.0, "gb1": 0.1}
REFERENCE_RATIOS = (1.0, 2.0, 4.0)

Cell = collections.namedtuple("Cell", "label results summary")


def make_policy(family, k, seed=0, explore_scope="pool", fallback="fresh_pool"):
    if family == "greedy":
        return P.GreedyWithReplication(k, seed, explore_scope, fallback)
    if family == "randrep":
        return P.GreedyRandomReplication(k, seed, explore_scope, fallback)
    if family == "random":
        return P.RandomPolicy(seed)
    raise ValueError("unknown policy family %r" % (family,))


def run_cell(ls, policy, sigma, n_campaigns, failure_rate=0.15, nomination="mean",
             prior=None, pool_sorted=None, seed0=0, measurable=None,
             screen_q=None, budget_mode="slots", target_useful=None):
    pool_sorted = pool_sorted or tuple(sorted(ls.pool))
    gmax = max(ls.fitness[s] for s in ls.pool)
    res = [C.run(ls.fitness, ls.pool, policy, sigma, seed0 + i, failure_rate,
                 nomination=nomination, prior=prior, pool_sorted=pool_sorted,
                 measurable=measurable, screen_q=screen_q, budget_mode=budget_mode,
                 target_useful=target_useful, global_best=gmax)
           for i in range(n_campaigns)]
    return Cell(policy.name, res,
                M.summarise(res, ls.fitness, ls.pool, global_max=gmax))


def k_sweep(ls, ratios, ks=(0, 1, 2, 3), n_campaigns=2000, failure_rate=0.15,
            family="greedy", explore_scope="pool", fallback="fresh_pool",
            nomination="mean", sigma_unit=None, use_prior=False, seed0=0,
            measurable=None):
    """The full ratio x k grid for one landscape. Returns {ratio: {k: Cell}}."""
    unit = sigma_unit if sigma_unit is not None else SIGMA_UNIT[ls.name]
    pool_sorted = tuple(sorted(ls.pool))
    prior = None
    if use_prior:
        import statistics as st
        vals = [ls.fitness[s] for s in ls.pool]
        prior = (st.mean(vals), st.variance(vals))
    grid = {}
    for ratio in ratios:
        sigma = unit * ratio
        grid[ratio] = {}
        for k in ks:
            pol = make_policy(family, k, seed=0, explore_scope=explore_scope,
                              fallback=fallback)
            grid[ratio][k] = run_cell(ls, pol, sigma, n_campaigns, failure_rate,
                                      nomination, prior, pool_sorted, seed0,
                                      measurable=measurable)
    return grid


def table(grid, ks=(0, 1, 2, 3), field="true_of_nominated", ref=None, title=""):
    """Render one grid as text: value +/- SE per cell, best k, and the paired gain."""
    lines = []
    if title:
        lines.append(title)
    head = "  ratio |" + "".join("%18s" % ("k=%d" % k) for k in ks) + " | best |  gain vs k=0 (paired)"
    lines.append(head)
    lines.append("  " + "-" * (len(head) - 2))
    for ratio in sorted(grid):
        row = grid[ratio]
        cells = []
        means = {}
        for k in ks:
            m, se, _ = row[k].summary[field]
            means[k] = m
            cells.append("%11.3f+-%-5.3f" % (m, se if se else 0.0))
        bk = max(means, key=means.get)
        base = [r.nominated_true for r in row[ks[0]].results]
        bestv = [r.nominated_true for r in row[bk].results]
        pd = M.paired_diff(bestv, base)
        gain = 100.0 * pd["diff"] / means[ks[0]] if means[ks[0]] else 0.0
        gse = 100.0 * (pd["se"] or 0.0) / means[ks[0]] if means[ks[0]] else 0.0
        lines.append("   %4.2f |%s |  k=%d | %+6.2f%% +- %.2f  (rho=%.3f)"
                     % (ratio, "".join(cells), bk, gain, gse,
                        pd["correlation"] if pd["correlation"] is not None else float("nan")))
        if ref and ratio in ref:
            devs = []
            for k in ks:
                m, se, _ = row[k].summary[field]
                want = ref[ratio][k]
                d = abs(m - want) / se if se else float("inf")
                devs.append("%.1f" % d)
            lines.append("        | reference deviation in SE: " + "  ".join(
                "k=%d:%s" % (k, d) for k, d in zip(ks, devs)))
    return "\n".join(lines)


# Reference table: mean true fitness of the nominated sequence.
REFERENCE = {
    "phoq": {1.0: {0: 28.109, 1: 27.835, 2: 23.815, 3: 20.462},
             2.0: {0: 21.040, 1: 23.320, 2: 22.001, 3: 19.073},
             4.0: {0: 12.443, 1: 15.574, 2: 14.911, 3: 15.076}},
    "gb1":  {1.0: {0: 5.141, 1: 4.836, 2: 4.247, 3: 3.483},
             2.0: {0: 4.186, 1: 4.292, 2: 3.939, 3: 3.224},
             4.0: {0: 2.684, 1: 3.097, 2: 2.972, 3: 2.648}},
}
