#!/usr/bin/env python3
"""The model-guided policy, a third scripted reference. Simulation only; no model is called.

The policy learns the landscape from its own readings only (the view holds no true value):
  rounds 1-4   one single-letter change of the reference per position per round, letters by keyed draw, no repeats;
               a replacement uses another untried letter at the rejected candidate's position;
  round 5 on   the Menu's additive model ranks single changes of the current best by mean and two-position changes
               built from each position's two best letters; candidates carrying a rejected letter rank last; ties
               by keyed draw. 4 - k new candidates and k re-tests per round; the re-tests go to the top k + 1 by
               mean in order, skipping the top candidate if it already has two or more readings;
  rounds 13-15 the confirm variant re-tests the top 4 by mean; the no-confirm variant follows the round-5 rule.
Nomination: the references' empirical-Bayes shrinkage rule (campaign.run, prior "empirical"), with the highest mean
(campaign.Result.ref_mean) beside it. Settings, seeds and rules are those of fair_reference_curve.py.

Usage: python3 scripts/model_guided_0an4.py [--n N] [--panel-k-seeds M]      (writes results/model_guided_0an4.json)
"""
import argparse, collections, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from repdef import campaign as C, envs as EV, policies as P, rng as R          # noqa: E402
import fair_reference_curve as FRC                                             # noqa: E402

OUT = os.path.join(ROOT, "results", "model_guided_0an4.json")
GUESSING, INFORMED = 7.8659, 7.9993        # the two references at k*, results/reference_curve_alphabet.json


class ModelGuided(P.Policy):

    def __init__(self, anchor, alphabet, k=1, confirm=True):
        self.anchor, self.alphabet, self.k, self.confirm = anchor, alphabet, int(k), bool(confirm)
        self.name = "model_guided_k%d_%s" % (self.k, "confirm" if confirm else "noconfirm")

    # -- what the view says ---------------------------------------------------------------------------
    @staticmethod
    def _state(view):
        reads = view.readings()
        ordered = {o.seq for o in view.history}                 # ok, failed and rejected: never proposed again
        rejected = [o.seq for o in view.history if o.outcome == "rejected"]
        return reads, ordered, rejected

    @staticmethod
    def _by_mean(reads):
        return sorted(reads, key=lambda s: (-sum(reads[s]) / len(reads[s]), s))

    def _model(self, reads):
        allv = [x for v in reads.values() for x in v]
        overall = sum(allv) / len(allv) if allv else 0.0
        acc = collections.defaultdict(list)
        for s, v in reads.items():
            for i, a in enumerate(s):
                acc[(i, a)].extend(v)
        m = {key: sum(v) / len(v) for key, v in acc.items()}
        return (lambda c: sum(m.get((i, a), overall) for i, a in enumerate(c))), m

    def _rejected_letters(self, reads, rejected):
        seen = {(i, a) for s in reads for i, a in enumerate(s)}
        return {(i, a) for s in rejected for i, a in enumerate(s) if (i, a) not in seen}

    def _ranked_new(self, view, reads, ordered, rejected, exclude):
        score, m = self._model(reads)
        bad = self._rejected_letters(reads, rejected)
        top = self._by_mean(reads)
        cands = set()
        for base in top[:3]:                                   # the best first; the next two only as a fallback
            singles = {base[:i] + a + base[i + 1:] for i in range(4) for a in self.alphabet if a != base[i]}
            best2 = {i: [a for a, _v in sorted(((a, v) for (j, a), v in m.items() if j == i),
                                               key=lambda t: -t[1])[:2] if a != base[i]] for i in range(4)}
            doubles = {base[:i] + a + base[i + 1:j] + b + base[j + 1:]
                       for i in range(4) for j in range(i + 1, 4) for a in best2[i] for b in best2[j]}
            cands |= {c for c in singles | doubles if c not in ordered and c not in exclude}
            if cands:
                break
        key = lambda c: (any((i, a) in bad for i, a in enumerate(c)), -score(c),
                         R._u64("model_guided", view.campaign_seed, view.current_round, c))
        return sorted(cands, key=key)

    def _early(self, view, ordered, exclude, positions):
        out = []
        for i in positions:
            tried = {s[i] for s in ordered | set(exclude) | set(out)
                     if sum(1 for j in range(4) if s[j] != self.anchor[j]) == 1 and s[i] != self.anchor[i]}
            free = sorted((a for a in self.alphabet if a != self.anchor[i] and a not in tried),
                          key=lambda a: R._u64("model_guided_early", view.campaign_seed, i, a))
            if free:
                out.append(self.anchor[:i] + free[0] + self.anchor[i + 1:])
        return out

    def _retests(self, reads, k):
        top = self._by_mean(reads)[:k + 1]
        if top and len(reads[top[0]]) >= 2:
            top = top[1:]
        return top[:k]

    # -- the policy -----------------------------------------------------------------------------------
    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        reads, ordered, rejected = self._state(view)
        rnd = view.current_round
        if rnd <= 4:
            if kind == "replacement":
                last = [s for s in rejected if s in exclude]
                pos = [next(i for i in range(4) if last[-1][i] != self.anchor[i])] if last else list(range(4))
                return self._early(view, ordered, exclude, pos)[:1]
            return self._early(view, ordered, exclude, range(4))[:n_slots]
        new = self._ranked_new(view, reads, ordered, rejected, exclude)
        if kind == "replacement":
            return new[:1]
        if self.confirm and rnd >= 13:
            re = self._by_mean(reads)[:n_slots]
        else:
            re = self._retests(reads, min(self.k, n_slots))
        picks = list(re) + [c for c in new if c not in re][:n_slots - len(re)]
        return picks[:n_slots]

    def replication_slots(self, view):
        return self.k


def run(fit, pool, anchor, seeds, k, confirm):
    ps, alphabet = tuple(sorted(pool)), P.alphabet_of(tuple(sorted(fit)))
    rows, collapsed = [], 0
    for seed in seeds:
        try:
            r = C.run(fit, pool, ModelGuided(anchor, alphabet, k, confirm), 0.0, seed, 0.15, pool_sorted=ps,
                      nomination="shrinkage", prior="empirical", noise_model="multiplicative", cv=FRC.CV,
                      noise_floor=FRC.FLOOR)
        except C.UnusableSigma:
            # Fewer than two measured candidates: no empirical prior. Counted and left out of the means, the
            # references' own convention (fair_reference_curve.run_curve's "collapsed").
            collapsed += 1
            continue
        lost = sum(1 for h in r.history if h.outcome in ("abandoned", "round_lost", "cap_lost"))
        rows.append(dict(shrinkage=r.nominated_true, highest_mean=fit[r.ref_mean],
                         share=100.0 * r.replication_count / r.slots_used if r.slots_used else 0.0,
                         # the same share over slots not lost, the robustness convention
                         share_nonlost=(100.0 * r.replication_count / (r.slots_used - lost)
                                        if r.slots_used - lost > 0 else 0.0),
                         distinct=r.n_distinct, rejections=r.n_rejected, lost=r.n_abandoned))
    se = lambda v: st.stdev(v) / math.sqrt(len(v))
    return dict(n=len(rows), collapsed=collapsed, **{k2: st.mean(r[k2] for r in rows) for k2 in rows[0]},
                shrinkage_se=se([r["shrinkage"] for r in rows]), highest_mean_se=se([r["highest_mean"] for r in rows]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=FRC.N)
    ap.add_argument("--panel-k-seeds", type=int, default=75)
    a = ap.parse_args()
    fit, pool = FRC.landscape()
    anchor = FRC.anchor_of(fit, pool)
    seeds = [FRC.SEED0 + i for i in range(a.n)]
    out = dict(seeds="%d to %d" % (seeds[0], seeds[-1]), guessing=GUESSING, informed=INFORMED, grid={}, panel_k={})
    for confirm in (True, False):
        for k in range(4):
            key = "%s|k=%d" % ("confirm" if confirm else "no-confirm", k)
            out["grid"][key] = run(fit, pool, anchor, seeds, k, confirm)
            g = out["grid"][key]
            print("grid %-14s pick %.4f (SE %.4f) | highest mean %.4f (SE %.4f) | share %5.1f%% distinct %5.1f "
                  "rejections %5.1f lost %4.2f" % (key, g["shrinkage"], g["shrinkage_se"], g["highest_mean"],
                                                   g["highest_mean_se"], g["share"], g["distinct"],
                                                   g["rejections"], g["lost"]), flush=True)
    y = json.load(open(os.path.join(ROOT, "results", "yardsticks_0am.json")))["panel_k"]
    for K in range(4):
        cells = []
        for j in range(EV.PANEL_K_N):
            env = EV.panel_k_env(K, j)
            cells.append(run(env.fit, env.pool, env.anchor, seeds[:a.panel_k_seeds], 1, True))
        n = sum(c["n"] for c in cells)
        out["panel_k"][str(K)] = dict(landscapes=len(cells), campaigns=n, collapsed=sum(c["collapsed"] for c in cells),
                                      shrinkage=sum(c["shrinkage"] * c["n"] for c in cells) / n,
                                      highest_mean=sum(c["highest_mean"] * c["n"] for c in cells) / n,
                                      share=sum(c["share"] * c["n"] for c in cells) / n,
                                      guessing_yardstick_mean=y[str(K)]["yardstick_mean"],
                                      guessing_yardstick_share=y[str(K)]["yardstick_share"])
        p = out["panel_k"][str(K)]
        print("Panel K=%d: pick %.4f, highest mean %.4f, share %.1f%%, collapsed %d of %d | guessing yardstick %.4f, "
              "share %.1f%%" % (K, p["shrinkage"], p["highest_mean"], p["share"], p["collapsed"],
                                p["campaigns"] + p["collapsed"], p["guessing_yardstick_mean"],
                                p["guessing_yardstick_share"]), flush=True)
    best = max(out["grid"], key=lambda k: out["grid"][k]["shrinkage"])
    out["peak"] = dict(variant=best, pick=out["grid"][best]["shrinkage"])
    json.dump(out, open(OUT, "w"), indent=1)
    print("peak: %s at %.4f; wrote %s" % (best, out["peak"]["pick"], os.path.relpath(OUT, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
