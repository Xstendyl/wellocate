#!/usr/bin/env python3
"""Post-hoc robustness analyses of the PPO policies under assay stress, by simulation. Never writes
results/b11_test_*.json.

  stress --split S --cond C   every policy on all 1,500 episodes of S (nk:test or gb1:test) in condition C
  report-stress               consistency checks, then results/b11_stress.json
  cluster                     the cluster-bootstrap table, results/b11_cluster_bootstrap.json

Usage: python3 wellocate/examples/ppo_robustness2.py stress --split nk:test --cond batch5
"""
import argparse, collections, hashlib, importlib.util, json, os, sys, time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
_spec = importlib.util.spec_from_file_location("ppo_robustness", os.path.join(HERE, "ppo_robustness.py"))
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)
P = R.P
from wellocate import env as W, scorecard as SC, splits as SP                       # noqa: E402

LABEL = "POST-HOC (spec/B11_ROBUSTNESS_2.md)"
with open(os.path.abspath(__file__), "rb") as _f:
    CODE_SHA256 = hashlib.sha256(_f.read()).hexdigest()
RES = os.path.join(ROOT, "results")
WORK = os.path.join(ROOT, "training", "out", "b11", "robustness2")
CV = 0.073
CONDITIONS = collections.OrderedDict([
    ("none", {}), ("batch5", dict(batch_sd=0.05)), ("batch10", dict(batch_sd=0.10)), ("floor", dict(noise_floor=0.17524)),
    ("zeros", dict(outlier_rate=0.02, outlier_kind="zero")), ("spikes", dict(outlier_rate=0.02, outlier_kind="spike"))])
STRESS_SPLITS = ("nk:test", "gb1:test")
SCRIPTED = R.SCRIPTED
NON_RANDOM = R.NON_RANDOM
REPS = 10000
T_975_DF2 = 4.302652729911275
# two-sided 95% t quantiles by degrees of freedom (seeds minus one)
T_975 = {1: 12.706204736174698, 2: T_975_DF2, 3: 3.182446305284263, 4: 2.7764451051977987, 5: 2.5705818366147395,
         6: 2.4469118511449692, 7: 2.3646242515927844, 8: 2.3060041350333704, 9: 2.2621571627409915}


# -- episodes -----------------------------------------------------------------------------------------------------------
def net_rows(net, episodes, lands, key, **env_kw):
    """ppo.evaluate with environment options: the same policy, keyed generators and row fields."""
    pol, rows = P.Policy(net), []
    for inst, cs in sorted(episodes, key=lambda e: e[0]):
        env = W.Wellocate(lands.get(inst), seed=cs, noise_cv=CV, **env_kw)
        info = P.play(env, pol, P.episode_rng(key, cs))
        rows.append(R.row(inst, cs, info["scorecard"], info["nomination_fallback"]))
    return rows


def scripted_rows(name, episodes, lands, **env_kw):
    pol, rows = R.make(name), []
    for inst, cs in sorted(episodes, key=lambda e: e[0]):
        sc = SC.run_episode(pol, lands.get(inst), cs, CV, **env_kw)
        rows.append(None if sc is None else R.row(inst, cs, sc))
    return rows


def registered_rows(split):
    """{policy: rows} of the main test for a split, keyed by (instance, campaign seed)."""
    reg = json.load(open(R.TEST_A))["splits"][split]
    out = {"guessing k=%d" % reg["validation_k"]["guessing"]: reg["per_episode"]["guessing"],
           "informed k=%d" % reg["validation_k"]["informed"]: reg["per_episode"]["informed"],
           "random": reg["per_episode"]["random"], "model-guided": reg["per_episode"]["model-guided"]}
    out.update({"Run A s%d" % i: reg["per_episode"]["trained"][i] for i in range(3)})
    return {n: {(r["instance"], r["campaign_seed"]): r for r in rows if r is not None} for n, rows in out.items()}


def canary_first(split, nets, lands, n=20):
    """Check that the first n episodes in condition none equal the main test's rows."""
    want = registered_rows(split)
    eps = sorted(SP.episodes(split), key=lambda e: e[0])[:n]
    got = {"Run A s0": net_rows(nets[0][2], eps, lands, P.TEST_KEY[split]),
           "random": scripted_rows("random", eps, lands)}
    for name, rows in got.items():
        for r in rows:
            w = want[name][(r["instance"], r["campaign_seed"])]
            if abs(r["pick"] - w["pick"]) > 1e-12 or abs(r["share"] - w["share"]) > 1e-12:
                raise SystemExit("ABORT: %s at %s/%d differs from the registered test" % (name, r["instance"],
                                                                                       r["campaign_seed"]))
    return n


def stress(split, cond):
    torch.set_num_threads(1)
    t0 = time.time()
    nets = R.networks()
    lands = P.Landscapes(24)
    print("canary: %d episodes equal the registered test" % canary_first(split, nets, lands), flush=True)
    kw = CONDITIONS[cond]
    eps = SP.episodes(split)
    out = dict(label=LABEL, code_sha256=CODE_SHA256, split=split, condition=cond, options=kw, noise_cv=CV,
               action_key=P.TEST_KEY[split], episodes=[list(e) for e in eps],
               networks=[dict(path=p, sha256=h) for p, h, _n in nets], rows={})
    for i, (_p, _h, net) in enumerate(nets):
        out["rows"]["Run A s%d" % i] = R.keyed(net_rows(net, eps, lands, P.TEST_KEY[split], **kw), eps)
        print("%s %s: Run A s%d done  %.0f s" % (split, cond, i, time.time() - t0), flush=True)
    for name in SCRIPTED:
        out["rows"][name] = R.keyed(scripted_rows(name, eps, lands, **kw), eps)
        print("%s %s: %s done  %.0f s" % (split, cond, name, time.time() - t0), flush=True)
    out["wall_s"] = time.time() - t0
    R.dump(os.path.join(WORK, "stress_%s_%s.json" % (split.replace(":", "_"), cond)), out)


# -- the cluster bootstrap ------------------------------------------------------------------------------------------------
class Cluster(object):
    """One two-level resample of a split's episodes: landscapes with replacement, then each chosen landscape's
    episodes with replacement. Episodes are sorted by instance (stable)."""

    def __init__(self, instances, key, reps=REPS):
        self.instances = list(instances)
        groups = collections.OrderedDict()
        for j, inst in enumerate(self.instances):
            groups.setdefault(inst, []).append(j)
        self.groups = [np.asarray(v) for v in groups.values()]
        if any(np.any(np.diff(g) != 1) for g in self.groups):
            raise ValueError("a landscape's episodes are not contiguous; put them in the registered order first")
        self.key, self.reps = key, reps
        rng = np.random.default_rng([4113, key])
        L = len(self.groups)
        if L == 1:
            g = self.groups[0]
            self.idx = g[rng.integers(0, len(g), size=(reps, len(g)))]
        else:
            pick = rng.integers(0, L, size=(reps, L))
            parts = []
            for c in range(L):
                sizes = np.asarray([len(self.groups[x]) for x in pick[:, c]])
                width = sizes.max()
                u = rng.random((reps, width))
                local = np.minimum((u * sizes[:, None]).astype(np.int64), sizes[:, None] - 1)
                starts = np.asarray([self.groups[x][0] for x in pick[:, c]])
                # groups are contiguous once sorted by instance
                col = starts[:, None] + local
                mask = np.arange(width)[None, :] < sizes[:, None]
                parts.append(np.where(mask, col, -1))
            self.idx = np.concatenate(parts, axis=1)
        self.levels = "landscapes, then episodes" if L > 1 else "episodes (one landscape)"

    def draws(self, v):
        """Bootstrap means of per-episode values v (NaN = missing, left out)."""
        v = np.append(np.asarray(v, dtype=float), np.nan)              # index -1 reads NaN
        return np.nanmean(v[self.idx], axis=1)


def seed_level(per_seed):
    m = np.asarray(per_seed, dtype=float)
    mean, sd = float(m.mean()), float(m.std(ddof=1)) if len(m) > 1 else 0.0
    half = T_975[len(m) - 1] * sd / np.sqrt(len(m)) if len(m) - 1 in T_975 else float("nan")
    return dict(per_seed=[float(x) for x in m], mean=mean, range=[float(m.min()), float(m.max())],
                t_interval=[mean - half, mean + half])


def interval(draws):
    d = np.sort(draws[~np.isnan(draws)])
    return [P.quantile(d, 0.025), P.quantile(d, 0.975)]


def vec(rows, field):
    return np.asarray([np.nan if r is None else r[field] for r in rows], dtype=float)


def cluster_paired(cl, a_per_seed, b_per_seed, field):
    """Mean over seeds of per-seed paired differences, with the cluster-bootstrap interval; an episode is used only
    where no comparator collapsed, as in the main test."""
    A = [vec(r, field) for r in a_per_seed]
    Bv = [vec(r, field) for r in b_per_seed]
    keep = np.all([~np.isnan(b) for b in Bv] + [~np.isnan(a) for a in A], axis=0)
    diffs = [np.where(keep, a - b, np.nan) for a, b in zip(A, Bv)]
    per_seed = [float(np.nanmean(d)) for d in diffs]
    draws = np.mean([cl.draws(d) for d in diffs], axis=0)
    return dict(mean=float(np.mean(per_seed)), ci=interval(draws), episodes=int(keep.sum()), seed=seed_level(per_seed),
                key=cl.key, levels=cl.levels)


def cluster_mean(cl, per_seed, field):
    vs = [vec(r, field) for r in per_seed]
    draws = np.mean([cl.draws(v) for v in vs], axis=0)
    return dict(mean=float(np.mean([np.nanmean(v) for v in vs])), ci=interval(draws), key=cl.key)


# -- report: stress -------------------------------------------------------------------------------------------------------
def load_stress(split, cond):
    p = os.path.join(WORK, "stress_%s_%s.json" % (split.replace(":", "_"), cond))
    return json.load(open(p)) if os.path.exists(p) else None


def ordered(part):
    """Episodes and rows sorted by instance (stable)."""
    eps = [tuple(e) for e in part["episodes"]]
    order = sorted(range(len(eps)), key=lambda j: eps[j][0])
    return [eps[j] for j in order], {n: [rs[j] for j in order] for n, rs in part["rows"].items()}


def stress_block(split, cond, part, key):
    eps, rows = ordered(part)
    cl = Cluster([e[0] for e in eps], key)
    runA = [rows["Run A s%d" % i] for i in range(3)]
    out = dict(condition=cond, options=part["options"], episodes=len(eps), policies={}, best_k={}, heavy_vs_moderate={})
    out["policies"]["Run A"] = {f: cluster_mean(cl, runA, f) for f in ("pick", "share")}
    for n in SCRIPTED:
        out["policies"][n] = {f: cluster_mean(cl, [rows[n]], f) for f in ("pick", "share")}
        out["policies"][n]["collapsed"] = sum(1 for r in rows[n] if r is None)
    best = max(NON_RANDOM, key=lambda n: out["policies"][n]["pick"]["mean"])
    out["best_scripted"] = best
    out["run_a_minus_random"] = {f: cluster_paired(cl, runA, [rows["random"]] * 3, f) for f in ("pick", "share")}
    out["run_a_minus_best"] = {f: cluster_paired(cl, runA, [rows[best]] * 3, f) for f in ("pick", "share")}
    for rule in ("guessing", "informed"):
        ks = ["%s k=%d" % (rule, k) for k in range(5)]
        kb = max(ks, key=lambda n: out["policies"][n]["pick"]["mean"])
        b = dict(best=kb, share=out["policies"][kb]["share"]["mean"], pick=out["policies"][kb]["pick"]["mean"],
                 cost={})
        for k in (3, 4):
            n = "%s k=%d" % (rule, k)
            b["cost"]["k=%d minus best" % k] = cluster_paired(cl, [rows[n]], [rows[kb]], "pick")
        out["best_k"][rule] = b
        mod = max(ks[:3], key=lambda n: out["policies"][n]["pick"]["mean"])
        heavy = max(ks[3:], key=lambda n: out["policies"][n]["pick"]["mean"])
        c = cluster_paired(cl, [rows[heavy]], [rows[mod]], "pick")
        out["heavy_vs_moderate"][rule] = dict(best_moderate=mod, best_heavy=heavy, heavy_minus_moderate=c,
                                              heavy_matches_or_beats=bool(c["ci"][1] >= 0))
    out["per_episode"] = dict({"Run A s%d" % i: R.compact(runA[i]) for i in range(3)},
                              **{n: R.compact(rows[n]) for n in SCRIPTED})
    out["episode_list"] = [list(e) for e in eps]
    return out


def report_stress(conds=None):
    out = dict(label=LABEL, spec="spec/B11_ROBUSTNESS_2.md", code_sha256=CODE_SHA256, noise_cv=CV, splits={},
               canary={})
    key = 7300
    for split in STRESS_SPLITS:
        none = load_stress(split, "none")
        if none is None:
            raise SystemExit("ABORT: %s has no condition-none run, the canary" % split)
        # check: condition none equals the main test's rows, episode by episode
        want, n = registered_rows(split), 0
        for name, w in want.items():
            got = {(r["instance"], r["campaign_seed"]): r for r in none["rows"][name] if r is not None}
            if set(got) != set(w):
                raise SystemExit("ABORT: %s %s collapses on different episodes from the registered test" % (split, name))
            for k, r in w.items():
                if abs(got[k]["pick"] - r["pick"]) > 1e-12 or abs(got[k]["share"] - r["share"]) > 1e-12:
                    raise SystemExit("ABORT: %s %s at %s differs from the registered test" % (split, name, k))
                n += 1
        out["canary"][split] = dict(rows_equal_registered=n)
        out["splits"][split] = {}
        for cond in (conds or CONDITIONS):
            part = load_stress(split, cond)
            if part is None:
                continue
            key += 1
            out["splits"][split][cond] = stress_block(split, cond, part, key)
    path = os.path.join(RES, "b11_stress.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print_stress(out)
    print("written %s" % os.path.relpath(path, ROOT))


def fmt(d, pct=False):
    s = "%.1f%%" if pct else "%+.3f"
    m = "%.1f%%" % d["mean"] if pct else "%.3f" % d["mean"]
    return ("%s [" + s + ", " + s + "]") % (m, d["ci"][0], d["ci"][1])


def fmtd(d):
    return "%+.3f [%+.3f, %+.3f]" % (d["mean"], d["ci"][0], d["ci"][1])


def print_stress(out):
    print("STRESS TESTS, %s, noise CV %.3f" % (out["label"], out["noise_cv"]))
    for split, conds in out["splits"].items():
        for cond, b in conds.items():
            print("\n%s, %s %s" % (split, cond, b["options"] or "(today's environment)"))
            for n in ("Run A", "random") + tuple(SCRIPTED[1:]):
                p = b["policies"][n]
                print("  %-14s pick %-26s share %s" % (n, fmt(p["pick"]), fmt(p["share"], True)))
            print("  best scripted %s" % b["best_scripted"])
            print("  Run A minus random   pick %s" % fmtd(b["run_a_minus_random"]["pick"]))
            print("  Run A minus best     pick %s" % fmtd(b["run_a_minus_best"]["pick"]))
            for rule, k in b["best_k"].items():
                print("  best %s: %s (share %.1f%%); k=3 minus best %s; k=4 minus best %s" % (
                    rule, k["best"], k["share"], fmtd(k["cost"]["k=3 minus best"]), fmtd(k["cost"]["k=4 minus best"])))
            for rule, h in b["heavy_vs_moderate"].items():
                print("  %s: heavy (%s) minus moderate (%s) %s -> heavy matches or beats: %s" % (
                    rule, h["best_heavy"], h["best_moderate"], fmtd(h["heavy_minus_moderate"]),
                    "YES" if h["heavy_matches_or_beats"] else "no"))



# -- behaviour replay ---------------------------------------------------------------------------------------------------
def b_networks():
    """Run B's three selected networks, hash-checked against results/b11_test_B.json."""
    out = []
    for c in json.load(open(os.path.join(RES, "b11_test_B.json")))["checkpoints"]:
        path = os.path.join(ROOT, c["best_path"])
        if R.sha256(path) != c["best_sha256"]:
            raise SystemExit("ABORT: %s does not match the sha256 in results/b11_test_B.json" % c["best_path"])
        out.append((c["best_path"], c["best_sha256"], P.load_net(path)))
    return out


def ham(a, b):
    return sum(x != y for x, y in zip(a, b))


def play_logged(env, policy, rng):
    """ppo.play, then the episode's orders read back from the oracle's history. A re-test is a slot-consuming order
    of a sequence that used a slot before (the scorecard's definition); its rank is by mean reading at the start of
    its round. A new candidate's parent rank is the best rank among sequences read before its round one letter away,
    0 for the start, -1 for neither. Rejected orders used no slot and are not counted."""
    info = P.play(env, policy, rng)
    hist = env._orc.history
    rounds = collections.defaultdict(list)
    for r in hist:
        rounds[r.round].append(r)
    reads = collections.defaultdict(list)
    retest_rank, parent_rank, per_round = [], [], [0] * env.rounds
    anchor = env.env.anchor
    for rnd in sorted(rounds):
        means = {q: sum(v) / len(v) for q, v in reads.items()}
        ranked = sorted(means, key=lambda q: (-means[q], q))
        rk = {q: i + 1 for i, q in enumerate(ranked)}
        read_this_round = set()
        for r in rounds[rnd]:
            if not r.slot_consumed or r.replicate_index is None:
                continue
            if r.replicate_index >= 1:
                per_round[rnd - 1] += 1
                # rank if read before the round; -2 if first read earlier in this round; -1 if only failed before
                retest_rank.append(rk[r.seq] if r.seq in rk else (-2 if r.seq in read_this_round else -1))
            else:
                near = [rk[m] for m in ranked if ham(m, r.seq) == 1]
                parent_rank.append(min(near) if near else (0 if ham(anchor, r.seq) == 1 else -1))
            if r.outcome == "ok":
                read_this_round.add(r.seq)
        for r in rounds[rnd]:
            if r.outcome == "ok":
                reads[r.seq].append(r.observed)
    sc = info["scorecard"]
    if len(retest_rank) != sc["replication_count"]:
        raise SystemExit("ABORT: %d re-tests in the history, the scorecard says %d" % (len(retest_rank),
                                                                                      sc["replication_count"]))
    final_means = {q: sum(v) / len(v) for q, v in reads.items()}
    best_mean = max(sorted(final_means), key=lambda q: final_means[q]) if final_means else None
    return info, dict(retest_rank=retest_rank, parent_rank=parent_rank, retests_by_round=per_round,
                      nominee=info["nominee"], max_mean=best_mean, shrinkage=sc["shrinkage_nominee"],
                      pick=sc["pick"], max_mean_pick=env.fit[best_mean] if best_mean else None,
                      shrinkage_pick=sc["shrinkage_pick"])


def replay(run, split):
    torch.set_num_threads(1)
    t0 = time.time()
    nets = R.networks() if run == "A" else b_networks()
    lands = P.Landscapes(24)
    eps = sorted(SP.episodes(split), key=lambda e: e[0])
    key = P.TEST_KEY[split]
    reg = json.load(open(os.path.join(RES, "b11_test_%s.json" % run)))["splits"].get(split)
    out = dict(label=LABEL, code_sha256=CODE_SHA256, run=run, split=split, action_key=key,
               episodes=[list(e) for e in eps], networks=[dict(path=p, sha256=h) for p, h, _n in nets], seeds={})
    checked = 0
    for i, (_p, _h, net) in enumerate(nets):
        pol, rows, logs = P.Policy(net), [], []
        for inst, cs in eps:
            env = W.Wellocate(lands.get(inst), seed=cs, noise_cv=CV)
            info, lg = play_logged(env, pol, P.episode_rng(key, cs))
            rows.append(R.row(inst, cs, info["scorecard"], info["nomination_fallback"]))
            logs.append(lg)
        if reg is not None:                                   # check: the replay matches the main test
            want = {(r["instance"], r["campaign_seed"]): r for r in reg["per_episode"]["trained"][i]}
            for r in rows:
                w = want[(r["instance"], r["campaign_seed"])]
                if abs(r["pick"] - w["pick"]) > 1e-12 or abs(r["share"] - w["share"]) > 1e-12:
                    raise SystemExit("ABORT: Run %s seed %d replay differs at %s/%d" % (run, i, r["instance"],
                                                                                      r["campaign_seed"]))
                checked += 1
        out["seeds"][i] = dict(rows=rows, logs=logs)
        print("replay %s %s seed %d done  %.0f s" % (run, split, i, time.time() - t0), flush=True)
    out["rows_equal_registered"] = checked
    out["wall_s"] = time.time() - t0
    R.dump(os.path.join(WORK, "replay_%s_%s.json" % (run, split.replace(":", "_"))), out)


# -- other splits and budgets -------------------------------------------------------------------------------------------
EVAL_KEYS = {"gb1:transfer_real": 5011, "phoq:transfer_real": 5012, "nk:test_ood_k2": 5021, "nk:test_ood_k3": 5022}
VAL_SPLIT = {"gb1:transfer_real": "gb1:test", "phoq:transfer_real": "phoq:test", "nk:test_ood_k2": "nk:test",
             "nk:test_ood_k3": "nk:test", "nk:test": "nk:test"}


def scaled(name, slots):
    """A scripted policy at another slots-per-round: k scales with the slots (k * slots / 4)."""
    if slots == 4 or name in ("random", "model-guided"):
        return name, R.make(name)
    rule, k = name.split(" k=")
    k2 = int(k) * slots // 4
    return "%s k=%d" % (rule, k2), (P.B.guessing if rule == "guessing" else P.B.informed)(k2)


def evalset(split, rounds=15, slots=4):
    torch.set_num_threads(1)
    t0 = time.time()
    nets = R.networks()
    lands = P.Landscapes(24)
    key = EVAL_KEYS.get(split, P.TEST_KEY.get(split))
    eps = SP.episodes(split)
    kw = dict(rounds=rounds, slots=slots)
    out = dict(label=LABEL, code_sha256=CODE_SHA256, split=split, rounds=rounds, slots=slots, noise_cv=CV,
               action_key=key, episodes=[list(e) for e in eps], networks=[dict(path=p, sha256=h) for p, h, _n in nets],
               rows={}, scripted_names={})
    for i, (_p, _h, net) in enumerate(nets):
        out["rows"]["Run A s%d" % i] = R.keyed(net_rows(net, eps, lands, key, **kw), eps)
        print("%s %dx%d: Run A s%d done  %.0f s" % (split, rounds, slots, i, time.time() - t0), flush=True)
    for name in SCRIPTED:
        real_name, pol = scaled(name, slots)
        out["scripted_names"][name] = real_name
        rows = []
        for inst, cs in sorted(eps, key=lambda e: e[0]):
            sc = SC.run_episode(pol, lands.get(inst), cs, CV, **kw)
            rows.append(None if sc is None else R.row(inst, cs, sc))
        out["rows"][name] = R.keyed(rows, eps)
        print("%s %dx%d: %s done  %.0f s" % (split, rounds, slots, real_name, time.time() - t0), flush=True)
    out["wall_s"] = time.time() - t0
    R.dump(os.path.join(WORK, "eval_%s_%dx%d.json" % (split.replace(":", "_"), rounds, slots)), out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("stress", "report-stress", "replay", "eval"))
    ap.add_argument("--split")
    ap.add_argument("--cond", choices=list(CONDITIONS))
    ap.add_argument("--conds", default=None)
    ap.add_argument("--run", choices=("A", "B"))
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--slots", type=int, default=4)
    a = ap.parse_args(argv)
    if a.cmd == "stress":
        stress(a.split, a.cond)
    elif a.cmd == "replay":
        replay(a.run, a.split)
    elif a.cmd == "eval":
        evalset(a.split, a.rounds, a.slots)
    else:
        report_stress(a.conds.split(",") if a.conds else None)


if __name__ == "__main__":
    main()
