#!/usr/bin/env python3
"""Yardsticks: the guessing scripted policy on every landscape. Simulation only.

For each landscape, the guessing policy (k = 0 to 4 re-tests of its best candidate per round, exploration from
the reference point's neighbours, viability guessed and paid for under the grid's rule) runs on the 1,500 seeds
of `fair_reference_curve.py`. The yardstick is the replication share (replication_count / slots_used) at k*, the
k with the best mean nominated true value. Real-name GB1 gets none, since the policy lacks the prior knowledge an
agent may have.

Neighbours are drawn from the landscape's own alphabet (`FairGreedyAlphabet`), not the hard-coded amino acids of
`policies.neighbours`; the grid is run both ways to record the difference.

Usage: python3 scripts/yardsticks_0am.py [--workers 12]      (writes results/yardsticks_0am.json)
"""
import argparse, json, os, statistics as st, sys, time
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from repdef import campaign as C, envs as E                      # noqa: E402
import repdef.rng as R                                            # noqa: E402
import fair_reference_curve as FRC                                # noqa: E402

OUT = os.path.join(ROOT, "results", "yardsticks_0am.json")
CHECK_N = 20                     # per-seed results kept for the first 20 seeds, which the tests recompute


class FairGreedyAlphabet(FRC.FairGreedy):
    """`FairGreedy` with neighbours over the landscape's alphabet. Every other line is the parent's."""

    def __init__(self, k, anchor, space, alphabet, seed=0):
        FRC.FairGreedy.__init__(self, k, anchor, space, seed=seed)
        self.alphabet = alphabet
        self.name = "fair_greedy_alphabet_k%d" % k

    def neighbours(self, q):
        return tuple(q[:i] + a + q[i + 1:] for i in range(len(q)) for a in self.alphabet if a != q[i])

    def _cold_start_fair(self, view, n_slots, exclude):
        cand = [self.anchor] + sorted(self.neighbours(self.anchor))
        cand = [c for c in cand if c not in set(exclude)]
        take = R.sample_without_replacement(cand, min(n_slots, len(cand)), "coldfair", self.seed,
                                           view.campaign_seed, view.current_round)
        return take[:n_slots]

    def _explore(self, view, champ, need, exclude):
        if need <= 0:
            return []
        seen = view.measured() | set(exclude)
        nb = sorted(x for x in self.neighbours(champ) if x not in seen)
        take = R.sample_without_replacement(nb, min(need, len(nb)), "exfair", self.seed,
                                            view.campaign_seed, view.current_round, champ)
        if len(take) < need:
            free = [x for x in self.space if x not in seen and x not in set(take)]
            take += list(R.sample_without_replacement(free, need - len(take), "fbfair", self.seed,
                                                      view.campaign_seed, view.current_round, champ))
        return take[:need]


def grid_env():
    fit, pool = FRC.landscape()
    return fit, pool, FRC.anchor_of(fit, pool)


def env_by_label(label):
    if label == "grid":
        fit, pool, anchor = grid_env()
        return dict(fit=fit, pool=pool, anchor=anchor, alphabet=E.ABSTRACT, rng_key=None)
    if label.startswith("nk:"):
        _n, k, s = label.split(":")
        e = E.nk(int(k), int(s))
    else:
        e = E.env_for(label)
    return dict(fit=e.fit, pool=e.pool, anchor=e.anchor, alphabet=e.alphabet, rng_key=e.rng_key)


_CACHE = {}


def one(job):
    """One scripted campaign. Returns per-campaign outcomes; None for a collapsed comparator."""
    label, policy, k, i = job
    if label not in _CACHE:
        # Keep one landscape per worker at a time; holding all 83 would take about 1.6 GB per worker.
        _CACHE.clear()
        for f in (E.nk, E.gb1_scrambled, E.phoq_scrambled, E.gb1_real):
            f.cache_clear()
        d = env_by_label(label)
        d["ps"], d["space"] = tuple(sorted(d["pool"])), tuple(sorted(d["fit"]))
        _CACHE[label] = d
    d = _CACHE[label]
    pol = (FRC.FairGreedy(k, d["anchor"], d["space"], seed=0) if policy == "committed"
           else FairGreedyAlphabet(k, d["anchor"], d["space"], d["alphabet"], seed=0))
    try:
        r = C.run(d["fit"], d["pool"], pol, 0.0, FRC.SEED0 + i, 0.15, pool_sorted=d["ps"],
                  nomination="shrinkage", prior="empirical", noise_model="multiplicative",
                  cv=FRC.CV, noise_floor=FRC.FLOOR, rng_key=d["rng_key"])
    except C.UnusableSigma:
        return (label, policy, k, i, None)
    proposed = {h.seq for h in r.history if h.seq != "----"}
    return (label, policy, k, i, dict(
        nom=r.nominated_true, share=100.0 * r.replication_count / r.slots_used if r.slots_used else 0.0,
        rej=sum(1 for h in r.history if h.outcome == "rejected"),
        lost=sum(1 for h in r.history if h.outcome == "abandoned"),
        outside=sum(1 for s in proposed if s not in d["fit"])))


def summarise(rows):
    """rows: {k: {i: outcome or None}} -> curve, k*, and the margin of k* over the runner-up."""
    curve = {}
    for k in FRC.KS:
        ok = [v for v in rows[k].values() if v is not None]
        nom = [v["nom"] for v in ok]
        curve[k] = dict(n=len(ok), collapsed=len(rows[k]) - len(ok), mean=st.mean(nom),
                        se=st.stdev(nom) / len(nom) ** 0.5, replication_share=st.mean(v["share"] for v in ok),
                        rejections=st.mean(v["rej"] for v in ok), lost=st.mean(v["lost"] for v in ok),
                        proposed_outside_landscape=sum(v["outside"] for v in ok))
    order = sorted((k for k in FRC.KS if curve[k]["n"] > 1), key=lambda k: -curve[k]["mean"])
    kstar, runner = order[0], order[1]
    # Paired by seed: the same 1,500 seeds run at every k, so the margin's standard error is the paired one.
    d = [rows[kstar][i]["nom"] - rows[runner][i]["nom"] for i in rows[kstar]
         if rows[kstar][i] is not None and rows[runner].get(i) is not None]
    se = st.stdev(d) / len(d) ** 0.5
    check = {k: [None if rows[k].get(i) is None else [rows[k][i]["nom"], rows[k][i]["share"]]
                 for i in range(CHECK_N)] for k in FRC.KS}
    return dict(curve=curve, kstar=kstar, runner_up=runner, margin=curve[kstar]["mean"] - curve[runner]["mean"],
                margin_paired_se=se, margin_in_se=(st.mean(d) / se if se else float("inf")),
                share_at_kstar=curve[kstar]["replication_share"], mean_at_kstar=curve[kstar]["mean"],
                check_first_seeds=check)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    t0 = time.time()
    labels = ["gb1_scrambled", "phoq_scrambled"] + ["nk:%d:%d" % (k, s) for k in E.PANEL_K
                                                   for s in E.PANEL_K_SEEDS[k]]
    jobs = [("grid", p, k, i) for p in ("committed", "alphabet") for k in FRC.KS for i in range(FRC.N)]
    jobs += [(lab, "alphabet", k, i) for lab in labels for k in FRC.KS for i in range(FRC.N)]
    # Grouped by landscape so each worker builds few landscapes.
    with Pool(a.workers) as p:
        res = p.map(one, jobs, chunksize=250)
    rows = {}
    for lab, pol, k, i, v in res:
        rows.setdefault((lab, pol), {k_: {} for k_ in FRC.KS})[k][i] = v
    grid_old, grid_new = summarise(rows[("grid", "committed")]), summarise(rows[("grid", "alphabet")])
    committed = json.load(open(os.path.join(ROOT, "results", "fair_reference_curve.json")))["curves"]["fair"]
    bad = [k for k in FRC.KS if abs(grid_old["curve"][k]["mean"] - committed[str(k)]["mean"]) > 1e-12
           or grid_old["curve"][k]["n"] != committed[str(k)]["n"]]
    if bad:
        raise SystemExit("REFUSED: the committed policy does not reproduce fair_reference_curve.json at k=%s" % bad)
    # The paired change the alphabet makes on the grid's own landscape, at the committed k*.
    ks = grid_old["kstar"]
    dd = [rows[("grid", "alphabet")][ks][i]["nom"] - rows[("grid", "committed")][ks][i]["nom"]
          for i in range(FRC.N) if rows[("grid", "alphabet")][ks][i] is not None
          and rows[("grid", "committed")][ks][i] is not None]
    lands = {}
    for lab in labels:
        e = env_by_label(lab)
        s = summarise(rows[(lab, "alphabet")])
        meta = (dict(name="nk", nk_k=int(lab.split(":")[1]), nk_seed=int(lab.split(":")[2]))
                if lab.startswith("nk:") else dict(name=lab))
        s.update(meta, anchor=e["anchor"], label=(E.nk(meta["nk_k"], meta["nk_seed"]).label
                                                  if meta["name"] == "nk" else E.env_for(lab).label))
        lands[s["label"]] = s
    panel_k = {}
    for k in E.PANEL_K:
        ls = [lands["nk_uniform_k%d_s%d_p%.1f" % (k, s, E.PCT)] for s in E.PANEL_K_SEEDS[k]]
        panel_k[k] = dict(landscapes=[x["label"] for x in ls],
                          yardstick_share=st.mean(x["share_at_kstar"] for x in ls),
                          yardstick_mean=st.mean(x["mean_at_kstar"] for x in ls),
                          kstar_counts={str(kk): sum(1 for x in ls if x["kstar"] == kk) for kk in FRC.KS},
                          landscapes_with_kstar_margin_under_2se=sum(1 for x in ls if x["margin_in_se"] < 2))
    out = dict(n=FRC.N, seed0=FRC.SEED0, policy="FairGreedyAlphabet (scripts/yardsticks_0am.py)",
               settings="fair_reference_curve.py: grid noise, 15% failures, 15 x 4, 3 replacement asks, "
                        "shrinkage nomination",
               grid=dict(committed_policy=grid_old, alphabet_policy=grid_new, reproduces_committed=True,
                         paired_change_at_committed_kstar=dict(k=ks, n=len(dd), mean=st.mean(dd),
                                                               se=st.stdev(dd) / len(dd) ** 0.5)),
               landscapes=lands, panel_k=panel_k, seconds=round(time.time() - t0, 1))
    json.dump(out, open(OUT, "w"), indent=1)
    print("grid landscape, committed policy (reproduces the committed curve): k* %d, mean %.4f, share %.2f%%, "
          "%d proposals outside the landscape at k*"
          % (ks, grid_old["mean_at_kstar"], grid_old["share_at_kstar"],
             grid_old["curve"][ks]["proposed_outside_landscape"]))
    print("grid landscape, alphabet policy:                                  k* %d, mean %.4f, share %.2f%%, "
          "%d outside" % (grid_new["kstar"], grid_new["mean_at_kstar"], grid_new["share_at_kstar"],
                          grid_new["curve"][grid_new["kstar"]]["proposed_outside_landscape"]))
    print("  paired change in mean at k=%d: %+.4f (SE %.4f, n %d)"
          % (ks, st.mean(dd), st.stdev(dd) / len(dd) ** 0.5, len(dd)))
    print("\n%-34s %3s %8s %8s %9s %6s %10s" % ("landscape", "k*", "mean", "share%", "runner-up", "SEs", "share k=0..4"))
    for lab in sorted(lands, key=lambda x: (x[:2] != "gb", x)):
        s = lands[lab]
        print("%-34s %3d %8.4f %8.2f %9d %6.1f   %s" % (
            lab, s["kstar"], s["mean_at_kstar"], s["share_at_kstar"], s["runner_up"], s["margin_in_se"],
            " ".join("%.1f" % s["curve"][k]["replication_share"] for k in FRC.KS)))
    for k in E.PANEL_K:
        p = panel_k[k]
        print("Panel K, K=%d: yardstick share %.2f%% (mean over 20), mean %.4f, k* counts %s, margins under 2 SE: %d"
              % (k, p["yardstick_share"], p["yardstick_mean"], p["kstar_counts"],
                 p["landscapes_with_kstar_margin_under_2se"]))
    print("wrote %s in %.0fs" % (os.path.relpath(OUT, ROOT), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
