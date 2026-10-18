#!/usr/bin/env python3
"""Post-hoc check of how the scripted results change with the starting candidate.

On the grid, scrambled GB1 and scrambled PhoQ, 50 random viable starts plus the paper's own start each run the
three scripted rules over their usual re-test settings (guessing and informed k = 0 to 4, model-guided with
confirmation k = 0 to 3), on the same campaign seeds so starts are compared on paired episodes. Each start is
passed as a copy of the landscape with a new anchor; nothing else changes. Per start and rule, k* is the setting
with the best mean true pick, kept with its margin over the runner-up and that margin's paired SE.
The script aborts unless the paper's start reproduces the existing scorecards and the informed rule, which takes
no start, gives identical results from every start.

No LLM calls and no paid API. Usage: python3 scripts/start_robustness.py [--n 1500] [--workers 10]
Writes results/start_robustness.json; per-episode arrays go to training/out/start_robustness/ (not in git).
"""
import argparse, hashlib, json, math, multiprocessing as mp, os, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import envs as EV                                # noqa: E402
from wellocate import baselines as B                         # noqa: E402
from wellocate import landscapes as LS                       # noqa: E402
from wellocate import scorecard as S                         # noqa: E402
from wellocate import splits as SP                           # noqa: E402

LANDS = (("grid", "nk:paper"), ("gb1_scrambled", "gb1:paper"), ("phoq_scrambled", "phoq:paper"))
N_STARTS, START_SEED = 50, 20261010
RULES = ([("guessing", k, B.guessing(k)) for k in range(5)] + [("informed", k, B.informed(k)) for k in range(5)]
         + [("model-guided", k, B.model_guided(k, True)) for k in range(4)])
FIELDS = ("pick", "share_budget", "share_nonlost", "distinct", "lost_slots", "exploration_shortfall",
          "selection_shortfall")
OUT = os.path.join(ROOT, "results", "start_robustness.json")
WORK = os.path.join(ROOT, "training", "out", "start_robustness")
with open(os.path.abspath(__file__), "rb") as _f:
    CODE_SHA256 = hashlib.sha256(_f.read()).hexdigest()


def with_start(env, start):
    """The landscape with `start` as its reference point, built as the original is; the example is chosen by
    repdef.envs.reference_point's rule (the first one-letter neighbour in sorted order)."""
    example = sorted(start[:i] + c + start[i + 1:] for i in range(len(start)) for c in env.alphabet if c != start[i])[0]
    copy = EV.Env(env.name, env.label, env.prompt_landscape, env.alphabet, env.fit, env.pool, env.threshold, start,
                  example, rng_key=env.rng_key, source_of=env.source_of, meta=env.meta)
    # The design space depends only on the strings, so the copy shares the original's (and its cached alphabet).
    space, alpha = B._space(env)
    B._SPACES[copy.label] = (copy, space, alpha)
    return copy


def starts(env):
    others = sorted(s for s in env.pool if s != env.anchor)
    rng = np.random.default_rng(START_SEED)
    return [env.anchor] + [others[i] for i in rng.choice(len(others), size=N_STARTS, replace=False)]


def run_start(job):
    """All rules from one start over the shared seeds: per rule, an array per field (NaN for a collapse)."""
    land, split, start, n = job
    env = LS.instance(SP.episodes(split, 1)[0][0])
    copy = with_start(env, start)
    seeds = [c for _i, c in SP.episodes(split, n)]
    out = {}
    for rule, k, pol in RULES:
        rows = [S.run_episode(pol, copy, cs) for cs in seeds]
        out["%s|%d" % (rule, k)] = {f: np.array([np.nan if r is None else r[f] for r in rows], dtype=float)
                                    for f in FIELDS}
    return land, start, out


def summary(arrs, rule, ks):
    """Means per setting, k* by mean pick, and k*'s margin over the runner-up with its paired SE."""
    per = {}
    for k in ks:
        a = arrs["%s|%d" % (rule, k)]
        ok = ~np.isnan(a["pick"])
        per[str(k)] = dict(n=int(ok.sum()), collapsed=int((~ok).sum()),
                           pick_se=float(np.std(a["pick"][ok], ddof=1) / math.sqrt(ok.sum())),
                           **{f: float(np.nanmean(a[f])) for f in FIELDS})
    order = sorted(ks, key=lambda k: -per[str(k)]["pick"])
    best, second = order[0], order[1]
    d = arrs["%s|%d" % (rule, best)]["pick"] - arrs["%s|%d" % (rule, second)]["pick"]
    d = d[~np.isnan(d)]
    return dict(settings=per, kstar=best, runner_up=second, margin=float(d.mean()),
                margin_se=float(np.std(d, ddof=1) / math.sqrt(len(d))))


def check_copy_is_original(n=5):
    """The paper's start through a copy must give the original landscape's scorecards, rule for rule."""
    for land, split in LANDS:
        inst = SP.episodes(split, 1)[0][0]
        env = LS.instance(inst)
        copy = with_start(env, env.anchor)
        for rule, k, pol in RULES:
            for _i, cs in SP.episodes(split, n):
                if S.run_episode(pol, inst, cs) != S.run_episode(pol, copy, cs):
                    raise SystemExit("ABORT: %s %s k=%d: the copy with the paper's start differs from the original"
                                     % (land, rule, k))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args(argv)
    t0 = time.time()
    check_copy_is_original()
    jobs, draws = [], {}
    for land, split in LANDS:
        env = LS.instance(SP.episodes(split, 1)[0][0])
        draws[land] = starts(env)
        jobs += [(land, split, s, a.n) for s in draws[land]]
    os.makedirs(WORK, exist_ok=True)
    res = {land: {} for land, _s in LANDS}
    with mp.Pool(a.workers) as pool:
        for land, start, arrs in pool.imap_unordered(run_start, jobs):
            res[land][start] = arrs
            np.savez_compressed(os.path.join(WORK, "%s_%s.npz" % (land, start)),
                                **{"%s__%s" % (key, f): v for key, d in arrs.items() for f, v in d.items()})
    out = dict(label="POST-HOC (review handover 3, task 2)", code_sha256=CODE_SHA256, n_seeds=a.n,
               start_seed=START_SEED, n_random_starts=N_STARTS, workers=a.workers,
               rules=dict(guessing=list(range(5)), informed=list(range(5)), model_guided_with_confirmation=list(range(4))),
               landscapes={})
    for land, split in LANDS:
        paper = draws[land][0]
        rows = {}
        for s in draws[land]:
            arrs = res[land][s]
            rows[s] = dict(start_value=float(LS.instance(SP.episodes(split, 1)[0][0]).fit[s]), paper_start=s == paper,
                           **{rule: summary(arrs, rule, ks) for rule, ks in
                              (("guessing", range(5)), ("informed", range(5)), ("model-guided", range(4)))})
        # The informed rule takes no start: its per-episode results must match across starts exactly.
        ref = res[land][paper]
        for s in draws[land][1:]:
            for k in range(5):
                key = "informed|%d" % k
                if not all(np.array_equal(ref[key][f], res[land][s][key][f], equal_nan=True) for f in FIELDS):
                    raise SystemExit("ABORT: %s informed k=%d differs between starts %s and %s" % (land, k, paper, s))
        out["landscapes"][land] = dict(split=split, paper_start=paper, starts=draws[land], by_start=rows)
    if a.n == 1500:
        sc = json.load(open(os.path.join(ROOT, "results", "wellocate_scorecard.json")))["splits"]
        for land, split in LANDS:
            if split not in sc:
                continue
            base, row = sc[split]["baselines"], out["landscapes"][land]["by_start"][out["landscapes"][land]["paper_start"]]
            for name, rule, k in (("guessing at k*", "guessing", row["guessing"]["kstar"]),
                                  ("informed at k*", "informed", row["informed"]["kstar"]),
                                  ("model-guided", "model-guided", 1)):
                for f in ("pick", "share_budget"):
                    got, want = row[rule]["settings"][str(k)][f], base[name][f]["mean"]
                    if abs(got - want) > 1e-9:
                        raise SystemExit("ABORT: %s %s %s: %.9f here, %.9f in wellocate_scorecard.json"
                                         % (land, name, f, got, want))
        out["reproduces_scorecard"] = [s for _l, s in LANDS if s in sc]
    out["runtime_s"] = time.time() - t0
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print("written %s in %.0f s" % (os.path.relpath(OUT, ROOT), out["runtime_s"]))


if __name__ == "__main__":
    main()
