#!/usr/bin/env python3
"""Scripted reference curves for a policy that must guess viability, as the agents must. Simulation only, no API calls.

The pool-scope reference only proposes viable sequences, so it is never rejected and never loses a slot. The
fair policy proposes over the whole landscape, so non-viable picks are rejected by the campaign's own rules. It
first checks that the original curves reproduce results/fair_reference_curve.json exactly, then writes both
references with neighbours over the landscape's own alphabet to results/reference_curve_alphabet.json.

Usage: python3 scripts/fair_reference_curve.py
"""
import collections, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import campaign as C, policies as P                        # noqa: E402
from repdef.nk import NKLandscape                                      # noqa: E402
import repdef.rng as R                                                 # noqa: E402

K, SEED, PCT = 1, 1, 93.0
CV, FLOOR, GB1_MAX = 0.073, (1 / 557) / (285 / 557), 8.762
N = int(os.environ.get("FRC_N", "1500"))
SEED0 = 8_200_000                     # same seed base as nk_reference_curve.py, so the two are paired
KS = (0, 1, 2, 3, 4)


class FairGreedy(P.GreedyWithReplication):
    """GreedyWithReplication that must guess viability: it starts from the reference point and its
    neighbours, and its exploration and fallback picks are drawn from the whole landscape."""

    def __init__(self, k, anchor, space, seed=0):
        P.GreedyWithReplication.__init__(self, k, seed=seed, explore_scope="landscape",
                                        fallback="fresh_pool")
        self.anchor = anchor
        self.space = tuple(sorted(space))
        self.name = "fair_greedy_k%d" % k

    def _cold_start_fair(self, view, n_slots, exclude):
        # The reference point first, then its neighbours in a seeded order, matching what the agents are told.
        cand = [self.anchor] + sorted(self._neighbours(self.anchor))
        cand = [c for c in cand if c not in set(exclude)]
        take = R.sample_without_replacement(cand, min(n_slots, len(cand)),
                                           "coldfair", self.seed, view.campaign_seed,
                                           view.current_round)
        return take[:n_slots]

    def _explore(self, view, champ, need, exclude):
        if need <= 0:
            return []
        seen = view.measured() | set(exclude)
        nb = [x for x in self._neighbours(champ) if x not in seen]
        nb.sort()
        take = R.sample_without_replacement(nb, min(need, len(nb)), "exfair", self.seed,
                                            view.campaign_seed, view.current_round, champ)
        if len(take) < need:
            # Fallback drawn from the whole landscape, so it can pick non-viable sequences.
            pool_free = [x for x in self.space if x not in seen and x not in set(take)]
            take += list(R.sample_without_replacement(
                pool_free, need - len(take), "fbfair", self.seed, view.campaign_seed,
                view.current_round, champ))
        return take[:need]

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        champ = self.champion(view)
        if champ is None:
            return self._cold_start_fair(view, n_slots, exclude)
        if kind == "replacement":
            return self._explore(view, champ, n_slots, exclude)
        picks = [champ] * min(self.k, n_slots)
        return picks + self._explore(view, champ, n_slots - len(picks), exclude)


class FairGreedyAlphabet(FairGreedy):
    """`FairGreedy` with neighbours over the letters of the landscape it searches, read from `space`."""

    def __init__(self, k, anchor, space, seed=0):
        FairGreedy.__init__(self, k, anchor, space, seed=seed)
        self.alphabet = P.alphabet_of(space)
        self.name = "fair_greedy_alphabet_k%d" % k


class PoolGreedyAlphabet(P.GreedyWithReplication):
    """The pool-scope reference with neighbours over the letters of the landscape it searches."""

    def __init__(self, k, space, seed=0):
        P.GreedyWithReplication.__init__(self, k, seed, "pool", "fresh_pool")
        self.alphabet = P.alphabet_of(space)
        self.name = "pool_greedy_alphabet_k%d" % k


PUBLISHED = os.path.join(ROOT, "results", "fair_reference_curve.json")
CORRECTED = os.path.join(ROOT, "results", "reference_curve_alphabet.json")


def landscape():
    nk = NKLandscape(k=K, seed=SEED, threshold_percentile=PCT, dist="uniform")
    f = GB1_MAX / max(nk.fitness.values())
    return {k: v * f for k, v in nk.fitness.items()}, nk.pool


def anchor_of(fit, pool):
    """The grid's own reference point: the pool median, lexicographically first among ties."""
    vals = sorted(fit[s] for s in pool)
    med = vals[len(vals) // 2]
    return sorted(s for s in pool if fit[s] == med)[0]


def run_curve(fit, pool, ps, space, anchor, fair, alphabet=True):
    out = {}
    for k in KS:
        nom, dis, rej, lost, dead = [], [], [], [], 0
        for i in range(N):
            if alphabet:
                pol = FairGreedyAlphabet(k, anchor, space, seed=0) if fair else PoolGreedyAlphabet(k, space)
            else:
                pol = (FairGreedy(k, anchor, space, seed=0) if fair
                       else P.GreedyWithReplication(k, 0, "pool", "fresh_pool"))
            try:
                r = C.run(fit, pool, pol, 0.0, SEED0 + i, 0.15, pool_sorted=ps,
                          nomination="shrinkage", prior="empirical",
                          noise_model="multiplicative", cv=CV, noise_floor=FLOOR)
            except C.UnusableSigma:
                # A campaign that measures fewer than two variants is counted as collapsed.
                dead += 1
                continue
            nom.append(r.nominated_true)
            ok = [h for h in r.history if h.outcome == "ok"]
            dis.append(len({h.seq for h in ok}))
            rej.append(sum(1 for h in r.history if h.outcome == "rejected"))
            lost.append(sum(1 for h in r.history if h.outcome == "abandoned"))
        out[k] = dict(mean=(st.mean(nom) if len(nom) > 1 else float("nan")),
                      se=(st.stdev(nom) / (len(nom) ** 0.5) if len(nom) > 1 else float("nan")),
                      distinct=(st.mean(dis) if dis else float("nan")),
                      rejections=(st.mean(rej) if rej else float("nan")),
                      lost=(st.mean(lost) if lost else float("nan")),
                      collapsed=dead, n=len(nom))
    return out


def main():
    fit, pool = landscape()
    ps = tuple(sorted(pool))
    space = tuple(sorted(fit))
    anchor = anchor_of(fit, pool)
    print("=" * 104)
    print("FAIR vs POOL-SCOPE SCRIPTED REFERENCE (0ai), neighbours over the landscape's alphabet   n=%d per k   "
          "anchor=%s   seeds %d..%d" % (N, anchor, SEED0, SEED0 + N - 1))
    print("=" * 104)
    # The original curves must reproduce first, so the new ones differ only in the alphabet.
    pub = json.load(open(PUBLISHED))["curves"]
    for scope in ("fair", "pool"):
        old = run_curve(fit, pool, ps, space, anchor, scope == "fair", alphabet=False)
        bad = [k for k in KS if old[k]["n"] != pub[scope][str(k)]["n"]
               or abs(old[k]["mean"] - pub[scope][str(k)]["mean"]) > 1e-12]
        if bad:
            raise SystemExit("REFUSED: the published %s curve does not reproduce at k=%s" % (scope, bad))
        print("  published %s curve reproduced exactly at every k" % scope)
    res = {}
    for fair in (False, True):
        scope = "fair" if fair else "pool"
        label = "FAIR (guesses viability)" if fair else "POOL-SCOPE (told viability)"
        res[scope] = run_curve(fit, pool, ps, space, anchor, fair, alphabet=True)
        print("\n  %s" % label)
        print("  %3s %10s %9s %11s %12s %10s %8s %9s"
              % ("k", "mean", "SE", "distinct", "rejections", "lost", "n", "collapsed"))
        for k in KS:
            d = res[scope][k]
            print("  %3d %10.4f %9.4f %11.2f %12.2f %10.2f %8d %9d"
                  % (k, d["mean"], d["se"], d["distinct"], d["rejections"], d["lost"], d["n"], d["collapsed"]))
        usable = [k for k in KS if res[scope][k]["n"] > 1]
        if not usable:
            print("  EVERY k COLLAPSED: this policy is not a usable reference.")
            res[scope + "_kstar"] = None
            continue
        best = max(usable, key=lambda k: res[scope][k]["mean"])
        print("  k* = %d   k*=%.4f  k=0=%.4f  span=%.4f  distinct at k*=%.2f"
              % (best, res[scope][best]["mean"], res[scope][0]["mean"],
                 res[scope][best]["mean"] - res[scope][0]["mean"], res[scope][best]["distinct"]))
        res[scope + "_kstar"] = best
    json.dump(dict(n=N, seed0=SEED0, anchor=anchor, ks=list(KS), alphabet=P.alphabet_of(space),
                   published_record=os.path.relpath(PUBLISHED, ROOT), curves=res),
              open(CORRECTED, "w"), indent=1)
    print("\n  wrote %s; %s is left as published" % (os.path.relpath(CORRECTED, ROOT),
                                                       os.path.relpath(PUBLISHED, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
