"""wellocate.evaluate(policy, split, n): a policy's scorecard on a split, with 95% bootstrap intervals.

Per episode the scorecard reads the environment's own numbers (Wellocate.scorecard). Over episodes it reports
the mean and a 95% interval (episodes resampled with a keyed bootstrap) of:
  pick                  the nominee's true value
  regret vs informed    the informed rule's pick minus this pick, paired by episode (informed at its best k)
  share_budget          re-testing share: orders of an already-measured candidate over slots used, in %
  share_nonlost         the same over slots not lost
  exploration_shortfall the best true value in the landscape minus the best this campaign measured
  selection_shortfall   the best this campaign measured minus the nominee's true value
  distinct, lost_slots  candidates measured, and slots lost (round forfeited or replacements exhausted)
and the best scripted share: the re-testing share of the reference policy with the highest mean pick on the same
episodes, among the guessing and informed rules at k = 0 to 4 and the model-guided policy, with that policy
named. The right share depends on the landscape and the noise; on GB1 at assay noise the best scripted
policies barely re-test. The paper's pre-registered band (guessing share at k* to the model-guided policy's
share) is defined only on the paper's grid at assay noise, and only there is a position against it reported.
A split names one family ("gb1:test") or a whole track ("bio:test", every family of the track, scored per
family).

A policy is either an object with propose(view, n_slots, exclude, kind) and, optionally, nominate(view), or a
factory that takes the landscape (repdef.envs.Env) and returns one. Without nominate the registered shrinkage
rule nominates. An episode where that rule is undefined (fewer than two measured candidates) is counted as
collapsed and left out, the paper's convention for its references.
"""
import functools
import collections
import statistics as st

from repdef import campaign as C
from repdef import rng as R
from wellocate import baselines as B
from wellocate import env as W
from wellocate import landscapes as LS
from wellocate import splits as SP

METRICS = ("pick", "regret_vs_informed", "share_budget", "share_nonlost", "exploration_shortfall",
           "selection_shortfall", "distinct", "lost_slots")
KS = (0, 1, 2, 3, 4)


def _family_splits(split):
    track, _, name = split.partition(":")
    if track in LS.TRACKS:
        return ["%s:%s" % (f, name) for f in LS.TRACKS[track]]
    return [split]


def run_episode(policy, instance, cseed, noise="assay", **kw):
    """One episode through the step API. Returns the scorecard dict, or None when the nomination collapsed."""
    env = W.Wellocate(instance, seed=cseed, noise_cv=noise, **kw)
    pol = policy(env.env) if not hasattr(policy, "propose") else policy
    obs = env.observation
    while obs.phase in ("round", "replacement"):
        obs, _r, _d, _i = env.step(pol.propose(obs.view, obs.n_slots, obs.exclude, obs.phase))
    if hasattr(pol, "nominate"):
        nom = pol.nominate(obs.view)
        nom = nom[0] if isinstance(nom, tuple) else nom
    else:
        try:
            nom = W.shrinkage_nominee(obs.view, env.noise_cv, env.noise_floor)
        except C.UnusableSigma:
            return None
    _o, _r, _d, info = env.nominate(nom)
    return info["scorecard"]


def run(policy, split, n=None, noise="assay", **kw):
    """Scorecards for the first n episodes of a family split, in episode order; None marks a collapse."""
    eps = SP.episodes(split, n)
    order = sorted(range(len(eps)), key=lambda i: (eps[i][0], i))      # group by landscape for the build cache
    out = [None] * len(eps)
    for i in order:
        out[i] = run_episode(policy, eps[i][0], eps[i][1], noise, **kw)
    return out


def _boot(cols, reps, tag):
    """Mean and 95% interval of each column, one keyed resample of episodes shared by all columns."""
    n = len(next(iter(cols.values())))
    draws = {k: [] for k in cols}
    for b in range(reps):
        idx = [R._u64("wellocate_boot", tag, b, j) % n for j in range(n)]
        for k, v in cols.items():
            draws[k].append(sum(v[j] for j in idx) / n)
    out = {}
    for k, v in cols.items():
        d = sorted(draws[k])
        out[k] = dict(mean=st.mean(v), ci=[d[int(0.025 * reps)], d[min(reps - 1, int(0.975 * reps))]])
    return out


@functools.lru_cache(maxsize=None)
def references(split, n=None, noise="assay"):
    """The guessing curve (k = 0 to 4), informed curve and model-guided policy on the same episodes. Computed once
    per (split, n, noise) in a session, since every evaluate() call on that split reuses them. All eleven rules play
    one landscape before the next is built, so each landscape is built once."""
    pols = [("guessing", k, B.guessing(k)) for k in KS] + [("informed", k, B.informed(k)) for k in KS]
    pols.append(("model_guided", None, B.model_guided(1, True)))
    eps = SP.episodes(split, n)
    rows = {(kind, k): [None] * len(eps) for kind, k, _p in pols}
    for i in sorted(range(len(eps)), key=lambda i: (eps[i][0], i)):
        for kind, k, pol in pols:
            rows[(kind, k)][i] = run_episode(pol, eps[i][0], eps[i][1], noise)
    return refs_from({k: rows[("guessing", k)] for k in KS}, {k: rows[("informed", k)] for k in KS},
                     rows[("model_guided", None)])


def refs_from(guessing, informed, model_guided):
    """The references from their per-episode rows: each rule's best k, and the band between the guessing rule's
    share at its best k and the model-guided policy's share."""
    ref = dict(guessing=dict(guessing), informed=dict(informed), model_guided=model_guided)
    mean = lambda rows, f: st.mean(r[f] for r in rows if r is not None)
    ref["guessing_kstar"] = max(KS, key=lambda k: mean(ref["guessing"][k], "pick"))
    ref["informed_kstar"] = max(KS, key=lambda k: mean(ref["informed"][k], "pick"))
    cands = [("guessing k=%d" % k, ref["guessing"][k]) for k in KS] + [("informed k=%d" % k, ref["informed"][k]) for k in KS]
    cands.append(("model-guided k=1 with confirmation", model_guided))
    name, rows = max(cands, key=lambda c: mean(c[1], "pick"))
    ref["best_scripted"] = dict(policy=name, pick=mean(rows, "pick"), share_budget=mean(rows, "share_budget"))
    return ref


def registered_band(split, noise):
    """The paper's pre-registered band, defined only on the grid at assay noise; None elsewhere."""
    if split != "nk:paper" or noise != "assay":
        return None
    import json, os
    b = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results",
                                    "analysis_0an7.json")))["band_grid"]
    return dict(lower=b["lower"]["share_budget"], upper=b["upper"]["share_budget"],
                source="paper, 0an.4: %s to %s" % (b["lower"]["policy"], b["upper"]["policy"]))


def evaluate(policy, split, n=None, noise="assay", refs=None, boot=1000, rows=None):
    """The scorecard of `policy` on `split` (a family split or a track split). Returns a dict per family."""
    out = collections.OrderedDict()
    for fs in _family_splits(split):
        ref = (refs or {}).get(fs) or references(fs, n, noise)
        mine = rows[fs] if rows else run(policy, fs, n, noise)
        inf = ref["informed"][ref["informed_kstar"]]
        keep = [i for i, r in enumerate(mine) if r is not None and inf[i] is not None]
        cols = {m: [mine[i][m] for i in keep] for m in METRICS if m != "regret_vs_informed"}
        cols["regret_vs_informed"] = [inf[i]["pick"] - mine[i]["pick"] for i in keep]
        sc = _boot(cols, boot, fs)
        s = sc["share_budget"]["mean"]
        sc["best_scripted"] = ref["best_scripted"]
        band = registered_band(fs, noise)
        if band:
            lo, hi = band["lower"], band["upper"]
            band.update(position=(s - lo) / (hi - lo), label="below" if s < lo else ("above" if s > hi else "inside"))
            sc["band"] = band
        sc.update(episodes=len(mine), collapsed=sum(r is None for r in mine), guessing_kstar=ref["guessing_kstar"],
                  informed_kstar=ref["informed_kstar"], track=LS.FAMILY_TRACK[fs.split(":")[0]], noise=noise)
        out[fs] = sc
    return out
