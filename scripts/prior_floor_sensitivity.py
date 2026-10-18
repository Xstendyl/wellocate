#!/usr/bin/env python3
"""Is the empirical prior's variance floor doing scientific work? No API calls.

The empirical-Bayes prior sets its variance to `spread - noise`, floored at `rel_floor * noise`, so when a
campaign's measured variants are tightly clustered the floor decides the prior. This measures how often the
floor binds per scripted policy, and whether the margin moves across rel_floor in {0.01, 0.1, 0.5}.
"""
import json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import campaign as C, policies as P
from repdef.nk import NKLandscape

CV, FLOOR, GB1_MAX = 0.073, (1 / 557) / (285 / 557), 8.762
K, SEED, PCT = 1, 1, 93.0
N = int(os.environ.get("PFS_N", "800"))
FLOORS = (0.01, 0.1, 0.5)


def sig(f):
    return math.sqrt(FLOOR ** 2 + (abs(f) * CV) ** 2)


def nk():
    g = NKLandscape(k=K, seed=SEED, threshold_percentile=PCT, dist="uniform")
    f = GB1_MAX / max(g.fitness.values())
    return {k: v * f for k, v in g.fitness.items()}, g.pool


def run_cell(fit, pool, ps, pol, n, seed0, rel_floor, rule="shrinkage"):
    binds, nvar, pv, nom, refmax = 0, [], [], [], []
    holder = {}
    orig = C._shrinkage_nominate

    def spy(view, s_, pm, pvv):
        holder["view"] = view
        return orig(view, s_, pm, pvv)
    C._shrinkage_nominate = spy
    try:
        for i in range(n):
            r = C.run(fit, pool, pol, 0.0, seed0 + i, 0.15, pool_sorted=ps,
                      nomination=rule, prior=("empirical" if rule == "shrinkage" else None),
                      noise_model="multiplicative", cv=CV, noise_floor=FLOOR,
                      prior_rel_floor=rel_floor)
            v = holder.get("view")
            b = C.empirical_prior_floor_binds(v, sig, rel_floor) if v is not None else None
            if b is not None:
                binds += bool(b)
                nvar.append(len(v.readings()))
            if r.empirical_prior_var is not None:
                pv.append(r.empirical_prior_var)
            nom.append(r.nominated_true)
            refmax.append(fit[r.ref_max])
    finally:
        C._shrinkage_nominate = orig
    d = [a - b for a, b in zip(nom, refmax)]
    return dict(binds=binds, n=n, frac=binds / n, mean_nvar=(st.mean(nvar) if nvar else 0),
                mean_prior_var=(st.mean(pv) if pv else float("nan")),
                margin=st.mean(d), se=(st.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else 0.0))


def main():
    fit, pool = nk()
    ps = tuple(sorted(pool))
    pols = [("random", P.RandomPolicy(0)),
            ("greedy k=0", P.GreedyWithReplication(0, 0, "pool", "fresh_pool")),
            ("greedy k=1", P.GreedyWithReplication(1, 0, "pool", "fresh_pool")),
            ("greedy k=2", P.GreedyWithReplication(2, 0, "pool", "fresh_pool")),
            ("greedy k=3", P.GreedyWithReplication(3, 0, "pool", "fresh_pool"))]
    out = {"n": N, "floors": list(FLOORS), "binding": {}, "margins": {}}

    print("=" * 96)
    print("1. HOW OFTEN THE VARIANCE FLOOR BINDS   NK uniform, grid noise model, n=%d" % N)
    print("=" * 96)
    print("  %-12s %12s %12s %12s %14s" % ("policy", "rel_floor", "binds", "mean variants",
                                           "mean prior var"))
    for lbl, pol in pols:
        for rf in FLOORS:
            d = run_cell(fit, pool, ps, pol, N, 9_300_000, rf)
            out["binding"]["%s|%.2f" % (lbl, rf)] = d
            print("  %-12s %12.2f %11.1f%% %12.1f %14.5f"
                  % (lbl, rf, 100 * d["frac"], d["mean_nvar"], d["mean_prior_var"]))

    print("\n" + "=" * 96)
    print("2. DOES THE MARGIN MOVE WITH THE FLOOR?   shrinkage minus max-single, paired, greedy k=1")
    print("=" * 96)
    pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
    print("  %12s %22s %10s %12s" % ("rel_floor", "margin (shrink - max)", "SE", "binds"))
    ms = {}
    for rf in FLOORS:
        d = run_cell(fit, pool, ps, pol, N, 9_400_000, rf)
        ms[rf] = d
        out["margins"]["%.2f" % rf] = d
        print("  %12.2f %+12.4f +- %-7.4f %10.1f %11.1f%%"
              % (rf, d["margin"], d["se"], abs(d["margin"] / d["se"]) if d["se"] else 0.0,
                 100 * d["frac"]))
    lo, hi = ms[min(FLOORS)], ms[max(FLOORS)]
    spread = abs(hi["margin"] - lo["margin"])
    pooled = math.sqrt(lo["se"] ** 2 + hi["se"] ** 2)
    print("\n  margin at %.2f minus margin at %.2f = %+.4f +- %.4f  (%.1f SE)"
          % (max(FLOORS), min(FLOORS), hi["margin"] - lo["margin"], pooled,
             spread / pooled if pooled else float("nan")))
    out["floor_sensitivity_se"] = (spread / pooled) if pooled else None

    # Equal margins could hide offsetting changes, so also count campaigns whose nomination differs
    # between the extreme floors.
    lo_f, hi_f = min(FLOORS), max(FLOORS)
    ch = pv_ch = 0
    for i in range(N):
        a = C.run(fit, pool, pol, 0.0, 9_400_000 + i, 0.15, pool_sorted=ps,
                  nomination="shrinkage", prior="empirical", noise_model="multiplicative",
                  cv=CV, noise_floor=FLOOR, prior_rel_floor=lo_f)
        b = C.run(fit, pool, pol, 0.0, 9_400_000 + i, 0.15, pool_sorted=ps,
                  nomination="shrinkage", prior="empirical", noise_model="multiplicative",
                  cv=CV, noise_floor=FLOOR, prior_rel_floor=hi_f)
        ch += (a.nominated != b.nominated)
        pv_ch += abs((a.empirical_prior_var or 0) - (b.empirical_prior_var or 0)) > 1e-12
    print("  prior variance changed in %d of %d campaigns; NOMINATION changed in %d of %d"
          % (pv_ch, N, ch, N))
    out["campaigns_prior_var_changed"] = pv_ch
    out["campaigns_nomination_changed"] = ch
    print()
    if pooled and spread / pooled > 2.0:
        print("  THE FLOOR IS DRIVING THE RESULT. It must be chosen on a stated principle and the")
        print("  margin reported at each value, because a tuning constant is deciding the comparator.")
    else:
        print("  The floor is INERT across a 50-fold range: the margin moves by less than 2 SE from")
        print("  rel_floor 0.01 to 0.5. It is a guard against a degenerate campaign and not a dial")
        print("  with scientific consequences, and the methods can say so with this number behind it.")
    dest = os.path.join(ROOT, "results", "step7_prior_floor_sensitivity.json")
    json.dump(out, open(dest, "w"), indent=1)
    print("\nsaved %s" % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
