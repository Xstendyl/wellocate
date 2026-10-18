#!/usr/bin/env python3
"""Simulate whether the replication ranking discriminates, transfers and can be learned. No API calls.

Part 1 runs scripted policies over nine settings (K in {1, 2, 3} crossed with noise at 0.5x, 1x and 2x) under
both exploration scopes. A setting discriminates if k* beats k=0 by at least 0.10 normalised units with
non-overlapping 95% intervals; the ranking transfers if the policy ordering is the same in all nine settings.
Part 2 trains a two-parameter policy (replication share and selection rule) on reward alone; it is learnable at
0.80 normalised on held-out seeds and transfers above 0.50 on held-out settings.

The normalised score is `(nominated - k0) / (kstar - k0)`, with both endpoints from the same setting and scope.
The policies are k=0 and k=k* with the highest single reading, k=k* with shrinkage, and k=0 with shrinkage to
complete the 2x2. k* is found per setting by sweeping k = 0..4 on training seeds and carries its gap to the
runner-up with a standard error. Each seed builds its own landscape, training and held-out seed ranges are
disjoint, and every cell reports how many campaigns were kept.

Usage:
  python3 scripts/learnability_sim.py --smoke      # small, to exercise the code
  python3 scripts/learnability_sim.py              # the pre-registered run, n = 200
  python3 scripts/learnability_sim.py --n 1500     # the power follow-up
"""
import argparse, collections, json, math, os, random, statistics as st, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import campaign as C, policies as P                        # noqa: E402
from repdef.nk import NKLandscape                                      # noqa: E402

PCT, GB1_MAX = 93.0, 8.762
CV_BASE, FLOOR_BASE = 0.073, (1 / 557) / (285 / 557)
KS = (0, 1, 2, 3, 4)
SELECTORS = ("max", "mean", "shrinkage")
# An NK landscape over N = 4 positions admits K in [0, N-1], so the largest setting is K = 3.
LAND_K = (1, 2, 3)
CV_MULT = (0.5, 1.0, 2.0)
# Held-out settings are every setting outside the training block, fixed here before any run.
TRAIN_SETTINGS = [(k, m) for k in (1, 2) for m in (0.5, 1.0)]
SEED_TRAIN, SEED_HELDOUT = 9_100_000, 9_300_000
BOOT = 2000


# The fair and pool-scope policies are imported from the reference script, so there is one definition of each.
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fair_reference_curve import FairGreedyAlphabet, PoolGreedyAlphabet  # noqa: E402


def landscape(k, seed):
    """One generated landscape, rescaled so its maximum equals GB1's, with the noise floor scaled with it."""
    nk = NKLandscape(k=k, seed=seed, threshold_percentile=PCT, dist="uniform")
    f = GB1_MAX / max(nk.fitness.values())
    return {s: v * f for s, v in nk.fitness.items()}, nk.pool


def anchor_of(fit, pool):
    vals = sorted(fit[s] for s in pool)
    med = vals[len(vals) // 2]
    return sorted(s for s in pool if fit[s] == med)[0]


def run_one(L, k, selector, seed, cv, fair):
    """One campaign on an already-built landscape. Returns the nominated true fitness, or None if the
    campaign collapsed; the caller counts collapses."""
    fit, pool, ps, space, anchor = L
    # Neighbours are drawn over the landscape's own letters, A to T.
    pol = (FairGreedyAlphabet(k, anchor, space, seed=0) if fair else PoolGreedyAlphabet(k, space))
    try:
        r = C.run(fit, pool, pol, 0.0, seed, 0.15, pool_sorted=ps,
                  nomination=selector, prior="empirical",
                  noise_model="multiplicative", cv=cv, noise_floor=FLOOR_BASE)
    except C.UnusableSigma:
        return None
    return r.nominated_true


def build(K, seed):
    """One fresh landscape, with everything a campaign needs, built once per (K, seed)."""
    fit, pool = landscape(K, seed)
    ps = tuple(sorted(pool))
    return (fit, pool, ps, tuple(sorted(fit)), anchor_of(fit, pool))


def boot_ci(vals, reps=BOOT, seed=7):
    rnd = random.Random(seed)
    n = len(vals)
    means = sorted(st.mean(rnd.choices(vals, k=n)) for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps)]


def paired_ci(a, b, reps=BOOT, seed=11):
    """Bootstrap interval for mean(a) - mean(b) over the same seeds, resampling seeds.

    Every policy in a setting runs on the same landscapes and seeds, so the per-seed difference removes the
    landscape draw. It is reported beside the pre-registered overlap test.
    """
    rnd = random.Random(seed)
    idx = range(len(a))
    d = [a[i] - b[i] for i in idx]
    means = sorted(st.mean(rnd.choices(d, k=len(d))) for _ in range(reps))
    return st.mean(d), means[int(0.025 * reps)], means[int(0.975 * reps)]


def normalise(vals, k0, kstar):
    span = kstar - k0
    if span <= 0:
        return None
    return [(v - k0) / span for v in vals]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--n", type=int, default=int(os.environ.get("LSIM_N", "200")))
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "learnability_sim_fresh.json"))
    a = ap.parse_args()
    n = 6 if a.smoke else a.n
    land_ks = [1] if a.smoke else list(LAND_K)
    mults = [1.0] if a.smoke else list(CV_MULT)
    scopes = ["pool"] if a.smoke else ["pool", "fair"]
    settings = [(k, m) for k in land_ks for m in mults]

    # Disjoint seed ranges: the seed is the landscape, so a held-out seed is a held-out problem.
    train = list(range(SEED_TRAIN, SEED_TRAIN + n))
    held = list(range(SEED_HELDOUT, SEED_HELDOUT + n))
    assert not (set(train) & set(held)), "training and held-out landscapes must be disjoint"

    print("=" * 112)
    print("LEARNABILITY SIMULATION, FRESH LANDSCAPE PER SEED   %d settings x %d scopes x %d landscapes"
          % (len(settings), len(scopes), n))
    print("landscape seed = campaign seed; train %d..%d, held out %d..%d (disjoint)"
          % (train[0], train[-1], held[0], held[-1]))
    print("=" * 112)

    # ---- Pass 1: the training landscapes. Every (cv, scope, k, selector) on each, built once. ----
    tr_vals = collections.defaultdict(list)      # (K, mult, scope, k, sel) -> nominated values
    tr_dead = collections.Counter()
    t0 = time.time()
    for K in land_ks:
        for i, sd in enumerate(train):
            L = build(K, sd)
            for mult in mults:
                for scope in scopes:
                    for k in KS:
                        for sel in SELECTORS:
                            v = run_one(L, k, sel, sd, CV_BASE * mult, scope == "fair")
                            if v is None:
                                tr_dead[(K, mult, scope, k, sel)] += 1
                            else:
                                tr_vals[(K, mult, scope, k, sel)].append(v)
            if (i + 1) % 50 == 0 or i + 1 == len(train):
                print("  train K=%d %4d/%d landscapes  %.0fs" % (K, i + 1, len(train), time.time() - t0))

    # k* per (setting, scope), from the training landscapes, with the gap to the runner-up.
    cells = {}
    for (K, mult) in settings:
        for scope in scopes:
            means, kept = {}, {}
            for k in KS:
                v = tr_vals[(K, mult, scope, k, "shrinkage")]
                means[k] = st.mean(v) if v else float("nan")
                kept[k] = len(v)
            order = sorted(KS, key=lambda k: -means[k])
            kstar, runner = order[0], order[1]
            # The gap's SE is paired: both policies ran on the same landscapes and seeds.
            va, vb = (tr_vals[(K, mult, scope, kstar, "shrinkage")],
                      tr_vals[(K, mult, scope, runner, "shrinkage")])
            m = min(len(va), len(vb))
            d = [va[j] - vb[j] for j in range(m)]
            gap = st.mean(d) if d else float("nan")
            gap_se = (st.stdev(d) / math.sqrt(len(d))) if len(d) > 1 else float("nan")
            cells[(K, mult, scope)] = dict(
                kstar=kstar, runner_up=runner, gap=gap, gap_se=gap_se,
                gap_is_a_tie=bool(gap_se == gap_se and abs(gap) < 2 * gap_se),
                k0_mean=means[0], kstar_mean=means[kstar], span=means[kstar] - means[0],
                # The standard error per k, because many k* gaps here are ties.
                sweep={str(k): dict(
                    mean=means[k], kept=kept[k],
                    se=(st.stdev(tr_vals[(K, mult, scope, k, "shrinkage")])
                        / math.sqrt(len(tr_vals[(K, mult, scope, k, "shrinkage")]))
                        if len(tr_vals[(K, mult, scope, k, "shrinkage")]) > 1 else float("nan")),
                    collapsed=tr_dead[(K, mult, scope, k, "shrinkage")])
                    for k in KS})

    # ---- Pass 2: the held-out landscapes. The four corners plus the learned policy. ----
    tr_settings = [x for x in settings if x in TRAIN_SETTINGS] or settings[:1]
    ho_settings = [x for x in settings if x not in tr_settings]
    learned = {}
    for scope in scopes:
        tot = {}
        for k in KS:
            for sel in SELECTORS:
                vs = [v for (K, mult) in tr_settings for v in tr_vals[(K, mult, scope, k, sel)]]
                tot[(k, sel)] = st.mean(vs) if vs else float("-inf")
        learned[scope] = max(tot, key=lambda kp: tot[kp])
        print("  learned on reward alone, scope=%s: k=%d selector=%s"
              % (scope, learned[scope][0], learned[scope][1]))

    ho_vals = collections.defaultdict(list)      # (K, mult, scope, label) -> values
    ho_dead = collections.Counter()
    for K in land_ks:
        for i, sd in enumerate(held):
            L = build(K, sd)
            for mult in mults:
                for scope in scopes:
                    c = cells[(K, mult, scope)]
                    ks = c["kstar"]
                    plan = [("A k=0 max", 0, "max"), ("B k* max", ks, "max"),
                            ("C k* shrinkage", ks, "shrinkage"), ("D k=0 shrinkage", 0, "shrinkage"),
                            ("LEARNED", learned[scope][0], learned[scope][1])]
                    for label, k, sel in plan:
                        v = run_one(L, k, sel, sd, CV_BASE * mult, scope == "fair")
                        if v is None:
                            ho_dead[(K, mult, scope, label)] += 1
                        else:
                            ho_vals[(K, mult, scope, label)].append(v)
            if (i + 1) % 50 == 0 or i + 1 == len(held):
                print("  held  K=%d %4d/%d landscapes  %.0fs" % (K, i + 1, len(held), time.time() - t0))

    report = dict(n_per_cell=n, fresh_landscape_per_seed=True,
                  train_seeds=[train[0], train[-1]], held_seeds=[held[0], held[-1]],
                  settings=[], part2={}, criteria=dict(
                      discriminates="kstar > k0, 95% intervals disjoint, gap >= 0.10 normalised",
                      transfers_ranking="the ordering of the three policies is identical in every setting",
                      learnable=">= 0.80 normalised on held-out landscapes of the training settings",
                      transfers_learned="> 0.50 normalised on held-out settings"))

    print("\n  %-3s %-7s %-5s %-3s %-9s %-20s %9s %8s" %
          ("K", "cv", "scope", "k*", "runner-up", "gap to runner-up (SE)", "span", "kept k*"))
    for (K, mult) in settings:
        for scope in scopes:
            c = cells[(K, mult, scope)]
            row = dict(K=K, cv_mult=mult, cv=CV_BASE * mult, scope=scope, policies={}, **c)
            per = {}
            for label in ("A k=0 max", "B k* max", "C k* shrinkage", "D k=0 shrinkage", "LEARNED"):
                v = ho_vals[(K, mult, scope, label)]
                nv = normalise(v, c["k0_mean"], c["kstar_mean"]) if c["span"] > 0 else None
                per[label] = nv
                lo, hi = (boot_ci(nv) if nv and len(nv) > 1 else (float("nan"),) * 2)
                row["policies"][label] = dict(
                    raw_mean=(st.mean(v) if v else float("nan")),
                    norm_mean=(st.mean(nv) if nv else float("nan")), lo=lo, hi=hi,
                    kept=len(v), collapsed=ho_dead[(K, mult, scope, label)])
            row["paired"] = {}
            for hi_l, lo_l in (("B k* max", "A k=0 max"), ("C k* shrinkage", "B k* max"),
                               ("C k* shrinkage", "A k=0 max")):
                x, y = per[hi_l], per[lo_l]
                if x and y:
                    m2 = min(len(x), len(y))
                    dd, dlo, dhi = paired_ci(x[:m2], y[:m2])
                    row["paired"]["%s - %s" % (hi_l, lo_l)] = dict(diff=dd, lo=dlo, hi=dhi, n=m2)
            report["settings"].append(row)
            print("  %-3d %-7.3f %-5s %-3d %-9d %+9.4f (%.4f)%s %9.4f %8d"
                  % (K, CV_BASE * mult, scope, c["kstar"], c["runner_up"], c["gap"], c["gap_se"],
                     " TIE" if c["gap_is_a_tie"] else "    ", c["span"],
                     c["sweep"][str(c["kstar"])]["kept"]))

    print("\n  COLLAPSES: campaigns lost to UnusableSigma, so every mean above is over SURVIVORS")
    for (K, mult) in settings:
        for scope in scopes:
            c = cells[(K, mult, scope)]
            lost = {k: c["sweep"][str(k)]["collapsed"] for k in KS if c["sweep"][str(k)]["collapsed"]}
            if lost:
                print("    K=%d cv=%.3f %-5s  %s" % (K, CV_BASE * mult, scope,
                      ", ".join("k=%d lost %d of %d" % (k, v, n) for k, v in sorted(lost.items()))))

    for scope in scopes:
        seed_sc = [st.mean(normalise(ho_vals[(K, m, scope, "LEARNED")],
                                     cells[(K, m, scope)]["k0_mean"],
                                     cells[(K, m, scope)]["kstar_mean"]))
                   for (K, m) in tr_settings if cells[(K, m, scope)]["span"] > 0]
        set_sc = [st.mean(normalise(ho_vals[(K, m, scope, "LEARNED")],
                                    cells[(K, m, scope)]["k0_mean"],
                                    cells[(K, m, scope)]["kstar_mean"]))
                  for (K, m) in ho_settings if cells[(K, m, scope)]["span"] > 0]
        lrn = st.mean(seed_sc) if seed_sc else float("nan")
        trn = st.mean(set_sc) if set_sc else float("nan")
        report["part2"][scope] = dict(trained_k=learned[scope][0], trained_selector=learned[scope][1],
                                      heldout_seed_score=lrn, heldout_setting_score=trn,
                                      heldout_settings_usable=len(set_sc),
                                      learnable=bool(lrn >= 0.80), transfers=bool(trn > 0.50))
        print("\n  scope=%s  learned k=%d, %s" % (scope, learned[scope][0], learned[scope][1]))
        print("    held-out LANDSCAPES, training settings: %.3f   (LEARNABLE needs >= 0.80: %s)"
              % (lrn, "PASS" if lrn >= 0.80 else "FAIL"))
        print("    held-out SETTINGS:                      %.3f   (TRANSFERS needs > 0.50: %s)"
              % (trn, "PASS" if trn > 0.50 else "FAIL"))

    disc, orders = [], set()
    for row in report["settings"]:
        tag = "K=%d cv=%.3f %s" % (row["K"], row["cv"], row["scope"])
        if row["span"] <= 0:
            disc.append((tag, False, "no span: the sweep put k* at 0"))
            continue
        A, B = row["policies"]["A k=0 max"], row["policies"]["B k* max"]
        gap = B["norm_mean"] - A["norm_mean"]
        disjoint = B["lo"] > A["hi"]
        disc.append((tag, (gap >= 0.10) and disjoint,
                     "gap %+.3f, intervals %s" % (gap, "disjoint" if disjoint else "OVERLAP")))
        orders.add(tuple(l for _v, l in sorted(
            ((row["policies"][l]["norm_mean"], l)
             for l in ("A k=0 max", "B k* max", "C k* shrinkage")), reverse=True)))
    npass = sum(1 for _t, ok, _w in disc if ok)
    ppass = sum(1 for row in report["settings"]
                if row.get("paired", {}).get("B k* max - A k=0 max", {}).get("lo", -9) > 0
                and row["paired"]["B k* max - A k=0 max"]["diff"] >= 0.10)
    print("\n  DISCRIMINATES as pre-registered: %d of %d;  paired: %d" % (npass, len(disc), ppass))
    for tag, ok, why in disc:
        print("    %-22s %-4s %s" % (tag, "PASS" if ok else "FAIL", why))
    print("\n  TRANSFERS (one ordering everywhere): %s"
          % ("PASS" if len(orders) == 1 else "FAIL, %d orderings" % len(orders)))
    for o in sorted(orders):
        print("    %s" % " > ".join(o))
    report["criteria_result"] = dict(discriminates_pass=npass, discriminates_total=len(disc),
                                     discriminates_paired_pass=ppass, distinct_orderings=len(orders),
                                     orderings=[list(o) for o in sorted(orders)])
    json.dump(report, open(a.out, "w"), indent=1)
    print("\n  wrote %s   (%.0f s)" % (os.path.relpath(a.out, ROOT), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
