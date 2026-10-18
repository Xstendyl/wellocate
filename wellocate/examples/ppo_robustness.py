#!/usr/bin/env python3
"""Post-hoc robustness of the PPO policies: Run A's three networks and the scripted policies at three noise levels on
nk:test, and on the LLM campaigns' own episodes. Simulation only; no model is called. Never writes
results/b11_test_*.json.

  contamination      checks each LLM arm's landscape against the PPO training and validation splits
                     (writes results/b11_robustness_contamination.json)
  noise --cv X       one noise level on nk:test, every policy, per episode (one file in WORK)
  llm --arm A        one LLM arm's episodes, every policy, per episode (one file in WORK)
  report-noise       check against results/b11_test_A.json, then results/b11_robustness_noise.json
  report-llm         checks against the published cells, then results/b11_robustness_llm.json

Usage: python3 wellocate/examples/ppo_robustness.py contamination
       python3 wellocate/examples/ppo_robustness.py noise --cv 0.073
       python3 wellocate/examples/ppo_robustness.py llm --arm gb1_real
       python3 wellocate/examples/ppo_robustness.py report-noise
       python3 wellocate/examples/ppo_robustness.py report-llm
"""
import argparse, hashlib, importlib.util, json, os, sys, time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
_spec = importlib.util.spec_from_file_location("ppo", os.path.join(HERE, "ppo.py"))
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)
from repdef import envs as EV                                                       # noqa: E402
from wellocate import baselines as B, env as W, landscapes as LS, scorecard as SC   # noqa: E402
from wellocate import splits as SP                                                  # noqa: E402

LABEL = "POST-HOC (spec/B11_ROBUSTNESS.md)"
with open(os.path.abspath(__file__), "rb") as _f:
    CODE_SHA256 = hashlib.sha256(_f.read()).hexdigest()
RES = os.path.join(ROOT, "results")
TEST_A = os.path.join(RES, "b11_test_A.json")
WORK = os.path.join(ROOT, "training", "out", "b11", "robustness")
NOISE = (("low", 0.0365), ("assay", 0.073), ("high", 0.146))
NOISE_SPLIT = "nk:test"
SCRIPTED = ["random"] + ["guessing k=%d" % k for k in range(5)] + ["informed k=%d" % k for k in range(5)] + \
           ["model-guided"]
NON_RANDOM = SCRIPTED[1:]
TRAIN_VAL = ("nk:train", "nk:validation", "gb1:train", "gb1:validation", "phoq:train", "phoq:validation")
# arm: (Wellocate instance, harness builder, split whose validation chose k, action key for the networks)
ARMS = {"grid": ("nk/K1/seed1", lambda: EV.nk(1, 1), "nk:test", 6001),
        "gb1_scrambled": ("gb1/scramble:20261003", EV.gb1_scrambled, "gb1:test", 6002),
        "gb1_real": ("gb1/real", EV.gb1_real, "gb1:test", 6003),
        "phoq_scrambled": ("phoq/scramble:20261004", EV.phoq_scrambled, "phoq:test", 6004)}
ARM_ORDER = ("grid", "gb1_scrambled", "gb1_real", "phoq_scrambled")
FIELDS = ("pick", "norm", "share", "exploration", "selection", "distinct", "lost")


def make(name):
    if name == "random":
        return B.random()
    if name == "model-guided":
        return B.model_guided(1, True)
    rule, k = name.split(" k=")
    return (B.guessing if rule == "guessing" else B.informed)(int(k))


# -- the networks -------------------------------------------------------------------------------------------------------
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def networks():
    """Run A's three selected networks, each hash-checked against results/b11_test_A.json."""
    out = []
    for c in json.load(open(TEST_A))["checkpoints"]:
        path = os.path.join(ROOT, c["best_path"])
        if sha256(path) != c["best_sha256"]:
            raise SystemExit("ABORT: %s does not match the sha256 in results/b11_test_A.json" % c["best_path"])
        out.append((c["best_path"], c["best_sha256"], P.load_net(path)))
    return out


# -- episodes -----------------------------------------------------------------------------------------------------------
def row(inst, cs, sc, fallback=None):
    r = dict(instance=inst, campaign_seed=cs, pick=sc["pick"], norm=sc["pick"] / sc["global_best"],
             share=sc["share_budget"], exploration=sc["exploration_shortfall"], selection=sc["selection_shortfall"],
             distinct=sc["distinct"], lost=sc["lost_slots"], global_best=sc["global_best"])
    if fallback is not None:
        r["fallback"] = fallback
    return r


def net_rows(net, episodes, lands, key, noise_cv):
    """ppo.evaluate with the noise CV as a parameter: the same policy, keyed generators and row fields."""
    pol, rows = P.Policy(net), []
    for inst, cs in sorted(episodes, key=lambda e: e[0]):
        env = W.Wellocate(lands.get(inst), seed=cs, noise_cv=noise_cv)
        info = P.play(env, pol, P.episode_rng(key, cs))
        rows.append(row(inst, cs, info["scorecard"], info["nomination_fallback"]))
    return rows


def scripted_rows(name, episodes, lands, noise_cv):
    pol, rows = make(name), []
    for inst, cs in sorted(episodes, key=lambda e: e[0]):
        sc = SC.run_episode(pol, lands.get(inst), cs, noise_cv)
        rows.append(None if sc is None else row(inst, cs, sc))
    return rows


def keyed(rows, episodes):
    """Rows in the order of `episodes`; None stays None (a collapsed scripted episode)."""
    by = {}
    for (inst, cs), r in zip(sorted(episodes, key=lambda e: e[0]), rows):
        by[(inst, cs)] = r
    return [by[e] for e in episodes]


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


# -- statistics ---------------------------------------------------------------------------------------------------------
class Keys(object):
    """One fixed bootstrap key per comparison, in the order they are asked for, written to the output."""

    def __init__(self, base):
        self.base, self.used = base, {}

    def __call__(self, name):
        if name not in self.used:
            self.used[name] = self.base + len(self.used)
        return self.used[name]


def paired_runA(trained, other, key, field):
    """ppo.beats for any field: per seed the mean paired difference over episodes where no comparator collapsed,
    the mean over seeds, a 95% interval from one resample of episodes shared by all seeds."""
    keep = [j for j in range(len(other[0])) if all(o[j] is not None for o in other)]
    diffs = np.asarray([[t[j][field] - o[j][field] for j in keep] for t, o in zip(trained, other)])
    draws = np.sort(diffs[:, P.boot_index(key, len(keep))].mean(axis=2).mean(axis=0))
    per_seed = [float(d.mean()) for d in diffs]
    return dict(mean=float(diffs.mean()), ci=[P.quantile(draws, 0.025), P.quantile(draws, 0.975)],
                per_seed=per_seed, episodes=len(keep), dropped_collapsed=len(other[0]) - len(keep), key=key)


def paired_scripted(a, b, key, field):
    keep = [j for j in range(len(a)) if a[j] is not None and b[j] is not None]
    d = np.asarray([a[j][field] - b[j][field] for j in keep])
    draws = np.sort(d[P.boot_index(key, len(keep))].mean(axis=1))
    return dict(mean=float(d.mean()), ci=[P.quantile(draws, 0.025), P.quantile(draws, 0.975)], episodes=len(keep),
                dropped_collapsed=len(a) - len(keep), key=key)


def mean_ci(rows, key, field):
    """Mean of one policy (or one LLM) with a 95% episode-bootstrap interval."""
    v = np.asarray([r[field] for r in rows if r is not None])
    draws = np.sort(v[P.boot_index(key, len(v))].mean(axis=1))
    return dict(mean=float(v.mean()), ci=[P.quantile(draws, 0.025), P.quantile(draws, 0.975)], n=len(v), key=key)


def mean_ci_runA(per_seed, key, field):
    """Run A over its three seeds, the interval from one resample of episodes shared by all seeds."""
    m = np.asarray([[r[field] for r in rows] for rows in per_seed])
    draws = np.sort(m[:, P.boot_index(key, m.shape[1])].mean(axis=2).mean(axis=0))
    return dict(mean=float(m.mean()), ci=[P.quantile(draws, 0.025), P.quantile(draws, 0.975)],
                per_seed=[float(x) for x in m.mean(axis=1)], n=m.shape[1], key=key)


def compact(rows):
    """Per-episode pick and share, aligned with the episode list; None for a collapsed episode."""
    return dict(pick=[None if r is None else round(r["pick"], 9) for r in rows],
                share=[None if r is None else round(r["share"], 9) for r in rows])


# -- contamination --------------------------------------------------------------------------------------------------------
def fitness_table_sha256(env):
    """The sorted fitness values to 9 decimals: a relabelling of the same landscape cannot change it."""
    return hashlib.sha256("\n".join("%.9f" % v for v in sorted(env.fit.values())).encode()).hexdigest()


def seed_range(split):
    e = SP.load()["splits"][split]
    return e["campaign_seed_start"], e["campaign_seed_start"] + e["episodes"]


def llm_rows_by_arm():
    """{arm: [(label, model, tags, rows)]}: the published Blind rows, transport fallbacks dropped."""
    import analyse_0an7 as A7
    import analyse_0am as AM
    import basins as BS
    import landscapes_0an8 as LA
    arms = LA.arms()
    names = {m: lab for lab, m, _t in BS.ARMS["grid Blind"]}
    out = {"grid": [], "gb1_scrambled": [], "gb1_real": [], "phoq_scrambled": []}
    for arm, land in (("grid", "grid"), ("gb1_scrambled", "GB1"), ("phoq_scrambled", "PhoQ")):
        for label, (model, tags) in arms[land].items():
            out[arm].append((label, model, list(tags), LA.rows_for(model, tags)))
    for model in AM.MODELS:
        tags = list(AM.R_TAGS["gb1_real"])
        out["gb1_real"].append((names[model], model, tags, LA.rows_for(model, tags)))
    return out


def manifest(tag):
    return json.load(open(os.path.join(RES, "grid_%s_manifest.json" % tag)))


def ran(tags):
    """The tags that wrote campaigns: a continuation tag listed in an arm may never have run."""
    return [t for t in tags if os.path.exists(os.path.join(RES, "grid_%s_campaigns.jsonl" % t))]


def contamination():
    t0 = time.time()
    by_arm = llm_rows_by_arm()
    split_insts = {s: SP.load()["splits"][s]["instances"] for s in TRAIN_VAL}
    content, table = {}, {}
    for s in TRAIN_VAL:
        for inst in split_insts[s]:
            env = LS.instance(inst)
            content.setdefault(LS.content_sha256(env), []).append((s, inst))
            if s.startswith("nk:"):
                table.setdefault(fitness_table_sha256(env), []).append((s, inst))
        print("built %-16s %3d instances  %.0f s" % (s, len(split_insts[s]), time.time() - t0), flush=True)
    out = dict(label=LABEL, code_sha256=CODE_SHA256, splits_checked=list(TRAIN_VAL), arms={})
    for arm in ARM_ORDER:
        inst = ARMS[arm][0]
        env = LS.instance(inst)
        labels = sorted({manifest(t)["landscape"] for _l, _m, tags, _r in by_arm[arm] for t in ran(tags)})
        seeds = sorted({r["seed"] for _l, _m, _t, rows in by_arm[arm] for r in rows})
        by_name = [s for s in TRAIN_VAL if inst in split_insts[s]]
        by_content = content.get(LS.content_sha256(env), [])
        by_table = table.get(fitness_table_sha256(env), []) if inst.startswith("nk/") else None
        overlap = [s for s in TRAIN_VAL if any(seed_range(s)[0] <= x < seed_range(s)[1] for x in seeds)]
        a = dict(instance=inst, manifest_landscapes=labels, campaign_seeds=[seeds[0], seeds[-1]], n_seeds=len(seeds),
                 in_split_by_name=by_name, same_content_as=[list(x) for x in by_content],
                 same_fitness_table_as=None if by_table is None else [list(x) for x in by_table],
                 campaign_seeds_in_split_range=overlap)
        hit = bool(by_name or by_content or by_table)
        a["in_train_or_validation"] = hit
        a["in_runA_train_or_validation"] = bool(
            any(s in ("nk:train", "nk:validation") for s in by_name) or
            any(s in ("nk:train", "nk:validation") for s, _i in by_content) or
            any(s in ("nk:train", "nk:validation") for s, _i in (by_table or [])))
        out["arms"][arm] = a
        print("%-15s %-24s by name %s, by content %s, by fitness table %s, campaign seeds in a split range %s"
              % (arm, inst, by_name or "none", [x[1] for x in by_content] or "none",
                 "n/a" if by_table is None else ([x[1] for x in by_table] or "none"), overlap or "none"))
    out["grid_contaminated"] = out["arms"]["grid"]["in_runA_train_or_validation"]
    out["verdict"] = "CONTAMINATED" if out["grid_contaminated"] else "clean"
    out["wall_s"] = time.time() - t0
    path = os.path.join(RES, "b11_robustness_contamination.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print("grid: %s; written %s" % (out["verdict"], os.path.relpath(path, ROOT)))
    return path


# -- noise ----------------------------------------------------------------------------------------------------------------
def noise_canary_first(nets, lands):
    """Check that the first 20 nk:test episodes at assay noise equal the main test's rows."""
    reg = json.load(open(TEST_A))["splits"][NOISE_SPLIT]["per_episode"]
    eps = sorted(SP.episodes(NOISE_SPLIT), key=lambda e: e[0])[:20]
    got = net_rows(nets[0][2], eps, lands, P.TEST_KEY[NOISE_SPLIT], 0.073)
    want = {(r["instance"], r["campaign_seed"]): r for r in reg["trained"][0]}
    for r in got:
        w = want[(r["instance"], r["campaign_seed"])]
        if abs(r["pick"] - w["pick"]) > 1e-12 or abs(r["share"] - w["share"]) > 1e-12:
            raise SystemExit("ABORT: network 0 at %s/%d differs from results/b11_test_A.json" % (r["instance"],
                                                                                             r["campaign_seed"]))
    return len(got)


def noise(level):
    torch.set_num_threads(1)
    cv = dict(NOISE)[level]
    t0 = time.time()
    nets = networks()
    lands = P.Landscapes(24)
    print("canary: %d episodes equal the registered test" % noise_canary_first(nets, lands), flush=True)
    eps = SP.episodes(NOISE_SPLIT)
    out = dict(label=LABEL, code_sha256=CODE_SHA256, split=NOISE_SPLIT, noise=level, noise_cv=cv, action_key=P.TEST_KEY[NOISE_SPLIT],
               episodes=[list(e) for e in eps], networks=[dict(path=p, sha256=h) for p, h, _n in nets], rows={})
    for i, (_p, _h, net) in enumerate(nets):
        out["rows"]["Run A s%d" % i] = keyed(net_rows(net, eps, lands, P.TEST_KEY[NOISE_SPLIT], cv), eps)
        print("%s: Run A s%d done  %.0f s" % (level, i, time.time() - t0), flush=True)
    for name in SCRIPTED:
        out["rows"][name] = keyed(scripted_rows(name, eps, lands, cv), eps)
        print("%s: %s done  %.0f s" % (level, name, time.time() - t0), flush=True)
    out["wall_s"] = time.time() - t0
    dump(os.path.join(WORK, "noise_%s.json" % level), out)


def report_noise():
    reg = json.load(open(TEST_A))["splits"][NOISE_SPLIT]
    parts = {lv: json.load(open(os.path.join(WORK, "noise_%s.json" % lv))) for lv, _cv in NOISE}
    eps = [tuple(e) for e in parts["assay"]["episodes"]]
    if any([tuple(e) for e in parts[lv]["episodes"]] != eps for lv in parts):
        raise SystemExit("ABORT: the noise levels ran different episodes")
    # The main test's episode order (sorted by instance, stable): a bootstrap resamples positions, so the order
    # is part of the interval's definition.
    order = sorted(range(len(eps)), key=lambda j: eps[j][0])
    eps = [eps[j] for j in order]
    for lv in parts:
        parts[lv]["rows"] = {n: [rs[j] for j in order] for n, rs in parts[lv]["rows"].items()}
    # check: at 0.073 every row of the main test is reproduced, episode by episode
    a = parts["assay"]["rows"]
    regmap = {"guessing k=%d" % reg["validation_k"]["guessing"]: reg["per_episode"]["guessing"],
              "informed k=%d" % reg["validation_k"]["informed"]: reg["per_episode"]["informed"],
              "random": reg["per_episode"]["random"], "model-guided": reg["per_episode"]["model-guided"]}
    regmap.update({"Run A s%d" % i: reg["per_episode"]["trained"][i] for i in range(3)})
    checked = 0
    for name, rrows in regmap.items():
        want = {(r["instance"], r["campaign_seed"]): r for r in rrows if r is not None}
        got = {(r["instance"], r["campaign_seed"]): r for r in a[name] if r is not None}
        if set(want) != set(got):
            raise SystemExit("ABORT: %s collapses on different episodes from the registered test" % name)
        for k, w in want.items():
            if abs(got[k]["pick"] - w["pick"]) > 1e-12 or abs(got[k]["share"] - w["share"]) > 1e-12:
                raise SystemExit("ABORT: %s at %s differs from results/b11_test_A.json" % (name, k))
            checked += 1
    keys = Keys(7000)
    runA = lambda rows: [rows["Run A s%d" % i] for i in range(3)]
    # the main test's "vs random" must come out of the paired code unchanged
    vr = paired_runA(runA(a), [a["random"]] * 3, P.TEST_KEY[NOISE_SPLIT] + 10, "pick")
    rv = reg["comparisons"]["vs random"]
    if abs(vr["mean"] - rv["mean"]) > 1e-12 or any(abs(x - y) > 1e-12 for x, y in zip(vr["ci"], rv["ci"])):
        raise SystemExit("ABORT: the paired code does not reproduce the registered vs-random comparison")
    out = dict(label=LABEL, spec="spec/B11_ROBUSTNESS.md", code_sha256=CODE_SHA256, split=NOISE_SPLIT, episodes=len(eps),
               networks=parts["assay"]["networks"], action_key=parts["assay"]["action_key"],
               canary=dict(rows_equal_registered=checked, vs_random_equal_registered=True), levels={})
    assay_best = None
    for lv, cv in NOISE:
        rows = parts[lv]["rows"]
        L = dict(noise_cv=cv, policies={}, comparisons={}, best_k={})
        L["policies"]["Run A"] = {f: mean_ci_runA(runA(rows), keys("%s|Run A|%s" % (lv, f)), f)
                                  for f in ("pick", "share")}
        for name in SCRIPTED:
            L["policies"][name] = {f: mean_ci(rows[name], keys("%s|%s|%s" % (lv, name, f)), f)
                                   for f in ("pick", "share")}
            L["policies"][name]["collapsed"] = sum(1 for r in rows[name] if r is None)
        best = max(NON_RANDOM, key=lambda n: L["policies"][n]["pick"]["mean"])
        L["best_scripted"] = best
        if lv == "assay":
            assay_best = best
        for other in ("random", best):
            nm = "Run A minus %s" % ("random" if other == "random" else "best scripted (%s)" % other)
            L["comparisons"][nm] = {f: paired_runA(runA(rows), [rows[other]] * 3, keys("%s|%s|%s" % (lv, nm, f)), f)
                                    for f in ("pick", "share")}
        for rule in ("guessing", "informed"):
            ks = ["%s k=%d" % (rule, k) for k in range(5)]
            kb = max(ks, key=lambda n: L["policies"][n]["pick"]["mean"])
            L["best_k"][rule] = dict(best=kb, share_at_best=L["policies"][kb]["share"]["mean"], others={})
            for n in ks:
                if n != kb:
                    L["best_k"][rule]["others"]["%s minus %s" % (n, kb)] = {
                        f: paired_scripted(rows[n], rows[kb], keys("%s|%s-%s|%s" % (lv, n, kb, f)), f)
                        for f in ("pick", "share")}
        L["per_episode"] = dict({"Run A s%d" % i: compact(rows["Run A s%d" % i]) for i in range(3)},
                                **{n: compact(rows[n]) for n in SCRIPTED})
        out["levels"][lv] = L
    out["share_change_vs_assay"] = {}
    for lv in ("low", "high"):
        out["share_change_vs_assay"]["Run A, %s minus assay" % lv] = paired_runA(
            runA(parts[lv]["rows"]), runA(parts["assay"]["rows"]), keys("share %s-assay|Run A" % lv), "share")
        out["share_change_vs_assay"]["%s, %s minus assay" % (assay_best, lv)] = paired_scripted(
            parts[lv]["rows"][assay_best], parts["assay"]["rows"][assay_best],
            keys("share %s-assay|%s" % (lv, assay_best)), "share")
    out["episode_list"] = [list(e) for e in eps]
    out["bootstrap_keys"] = keys.used
    path = os.path.join(RES, "b11_robustness_noise.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print_noise(out)
    print("written %s" % os.path.relpath(path, ROOT))
    return path


def fmt(d, pct=False):
    s = "%.1f%%" if pct else "%.3f"
    return (s + " [" + s + ", " + s + "]") % (d["mean"], d["ci"][0], d["ci"][1])


def print_noise(out):
    print("NOISE ROBUSTNESS ANALYSIS, %s, %s, %d episodes" % (out["label"], out["split"], out["episodes"]))
    for lv, L in out["levels"].items():
        print("\n%s (CV %.4f); best scripted %s" % (lv, L["noise_cv"], L["best_scripted"]))
        for n, p in L["policies"].items():
            print("  %-15s pick %s   share %s" % (n, fmt(p["pick"]), fmt(p["share"], True)))
        for n, c in L["comparisons"].items():
            print("  %-40s pick %s   share %s" % (n, fmt(c["pick"]), fmt(c["share"], True)))
        for rule, b in L["best_k"].items():
            print("  best %s: %s (share %.1f%%)" % (rule, b["best"], b["share_at_best"]))
            for n, c in b["others"].items():
                print("    %-32s pick %s" % (n, fmt(c["pick"])))
    for n, c in out["share_change_vs_assay"].items():
        print("share change, %-34s %s" % (n, fmt(c, True)))


# -- the LLM campaigns ------------------------------------------------------------------------------------------------------
def validation_k(arm):
    v = json.load(open(TEST_A))["splits"][ARMS[arm][2]]["validation_k"]
    return v["guessing"], v["informed"]


def llm_policies(arm):
    g, i = validation_k(arm)
    return ["random", "guessing k=%d" % g, "informed k=%d" % i, "model-guided"]


def llm_canary_settings(arm, by_arm):
    w = W.Wellocate(ARMS[arm][0], seed=0)
    for _l, _m, tags, _r in by_arm[arm]:
        for t in ran(tags):
            m = manifest(t)
            want = dict(cv=w.noise_cv, rounds=w.rounds, slots=w.slots, fail_pct=round(100 * w.failure_rate),
                        noise="multiplicative", max_reasks=w.max_reasks,
                        riskfree=w.riskfree, landscape=w.env.label)
            got = dict(cv=m["cv"], rounds=m["rounds"], slots=m["slots"], fail_pct=m["fail_pct"], noise=m["noise"],
                       max_reasks=m["max_reasks"], riskfree=bool(m["prompt_options"]["riskfree_rejection"]),
                       landscape=m["landscape"])
            if got != want:
                raise SystemExit("ABORT: %s's manifest %s differs from Wellocate's %s" % (t, got, want))


def llm_canary_landscape(arm):
    inst, build = ARMS[arm][0], ARMS[arm][1]
    w, h = W.Wellocate(inst, seed=0).env, build()
    same = (w.fit == h.fit, w.pool == h.pool, w.anchor == h.anchor, w.rng_key == h.rng_key, w.label == h.label)
    if not all(same):
        raise SystemExit("ABORT: Wellocate's %s is not the harness's landscape: %s" % (inst, same))


def llm_canary_yardsticks(arm):
    """Check that the guessing rule through Wellocate reproduces the published first-seed rows where they exist."""
    y = json.load(open(os.path.join(RES, "yardsticks_0am.json")))
    label = W.Wellocate(ARMS[arm][0], seed=0).env.label
    if arm == "grid":
        chk = y["grid"]["alphabet_policy"]["check_first_seeds"]
    elif label in y["landscapes"]:
        chk = y["landscapes"][label]["check_first_seeds"]
    else:
        return 0
    n = 0
    for k, rows in chk.items():
        for i, r in enumerate(rows):
            sc = SC.run_episode(B.guessing(int(k)), ARMS[arm][0], y["seed0"] + i, "assay")
            if r is None or sc is None:
                if (r is None) != (sc is None):
                    raise SystemExit("ABORT: %s guessing k=%s at seed %d: one of Wellocate and 0am collapsed"
                                     % (arm, k, y["seed0"] + i))
                n += 1
                continue
            pick, share = r
            if abs(sc["pick"] - pick) > 1e-9 or abs(sc["share_budget"] - share) > 1e-9:
                raise SystemExit("ABORT: %s guessing k=%s at seed %d gives %.6f / %.4f, 0am %.6f / %.4f"
                                 % (arm, k, y["seed0"] + i, sc["pick"], sc["share_budget"], pick, share))
            n += 1
    return n


def llm(arm):
    torch.set_num_threads(1)
    t0 = time.time()
    by_arm = llm_rows_by_arm()
    llm_canary_settings(arm, by_arm)
    llm_canary_landscape(arm)
    ny = llm_canary_yardsticks(arm)
    print("%s: settings, landscape and %d yardstick rows check" % (arm, ny), flush=True)
    inst, _b, _s, key = ARMS[arm]
    seeds = sorted({r["seed"] for _l, _m, _t, rows in by_arm[arm] for r in rows})
    eps = [(inst, s) for s in seeds]
    nets = networks()
    lands = P.Landscapes(4)
    out = dict(label=LABEL, code_sha256=CODE_SHA256, arm=arm, instance=inst, action_key=key, validation_k=dict(zip(("guessing", "informed"),
               validation_k(arm))), yardstick_rows_checked=ny, episodes=[list(e) for e in eps],
               networks=[dict(path=p, sha256=h) for p, h, _n in nets], rows={})
    for i, (_p, _h, net) in enumerate(nets):
        out["rows"]["Run A s%d" % i] = keyed(net_rows(net, eps, lands, key, 0.073), eps)
    for name in llm_policies(arm):
        out["rows"][name] = keyed(scripted_rows(name, eps, lands, 0.073), eps)
    out["wall_s"] = time.time() - t0
    dump(os.path.join(WORK, "llm_%s.json" % arm), out)
    print("%s: %d episodes, %.0f s" % (arm, len(eps), out["wall_s"]), flush=True)


def published_cell(arm, label, model):
    if arm == "gb1_real":
        c = json.load(open(os.path.join(RES, "analysis_0am.json")))["panel_R"]["gb1_real|Blind|%s" % model.split("/")[-1]]
        return c["fitness"], c["share"]
    land = {"grid": "grid", "gb1_scrambled": "GB1", "phoq_scrambled": "PhoQ"}[arm]
    c = json.load(open(os.path.join(RES, "landscapes_0an8.json")))["cells"][land][label]
    return c["pick"], c["share"]


def report_llm():
    import analyse_0an7 as A7
    con = json.load(open(os.path.join(RES, "b11_robustness_contamination.json")))
    by_arm = llm_rows_by_arm()
    keys = Keys(8000)
    out = dict(label=LABEL, spec="spec/B11_ROBUSTNESS.md", code_sha256=CODE_SHA256, contamination=dict(grid=con["verdict"]), arms={})
    for arm in ARM_ORDER:
        part = json.load(open(os.path.join(WORK, "llm_%s.json" % arm)))
        rows = {n: {(r["instance"], r["campaign_seed"]): r for r in rs if r is not None}
                for n, rs in part["rows"].items()}
        pols = llm_policies(arm)
        A = dict(instance=part["instance"], validation_k=part["validation_k"], action_key=part["action_key"],
                 policies=pols, models={})
        if arm == "grid":
            A["contamination"] = con["verdict"]
        for label, model, tags, lrows in by_arm[arm]:
            # checks: the published cell, and each campaign's global best is the landscape's
            lr = [dict(pick=r["nominated_true"], share=A7.share_b(r), seed=r["seed"], global_best=r["global_best"])
                  for r in lrows]
            pub = published_cell(arm, label, model)
            mine = (float(np.mean([r["pick"] for r in lr])), float(np.mean([r["share"] for r in lr])))
            if abs(mine[0] - pub[0]) > 1e-9 or abs(mine[1] - pub[1]) > 1e-9:
                raise SystemExit("ABORT: %s %s gives %.6f / %.4f, published %.6f / %.4f" % (arm, label, mine[0],
                                                                                          mine[1], pub[0], pub[1]))
            eps = [(part["instance"], r["seed"]) for r in lr]
            for r, e in zip(lr, eps):
                gb = rows["Run A s0"][e]["global_best"]
                if abs(r["global_best"] - gb) > 1e-3:
                    raise SystemExit("ABORT: %s %s seed %d records global best %.4f, the landscape's is %.4f"
                                     % (arm, label, e[1], r["global_best"], gb))
            runA = [[rows["Run A s%d" % i][e] for e in eps] for i in range(3)]
            M = dict(tags=tags, campaigns=len(lr), seeds=[min(r["seed"] for r in lr), max(r["seed"] for r in lr)],
                     llm={f: mean_ci(lr, keys("%s|%s|LLM|%s" % (arm, label, f)), f) for f in ("pick", "share")},
                     policies={}, run_a_minus_llm={})
            M["policies"]["Run A"] = {f: mean_ci_runA(runA, keys("%s|%s|Run A|%s" % (arm, label, f)), f)
                                      for f in ("pick", "share")}
            for n in pols:
                pr = [rows[n].get(e) for e in eps]
                M["policies"][n] = {f: mean_ci(pr, keys("%s|%s|%s|%s" % (arm, label, n, f)), f)
                                    for f in ("pick", "share")}
                M["policies"][n]["collapsed"] = sum(1 for r in pr if r is None)
            M["run_a_minus_llm"] = {f: paired_runA(runA, [lr] * 3, keys("%s|%s|A-LLM|%s" % (arm, label, f)), f)
                                    for f in ("pick", "share")}
            M["per_episode"] = dict(seeds=[r["seed"] for r in lr], llm=compact(lr),
                                    **{"Run A s%d" % i: compact(runA[i]) for i in range(3)},
                                    **{n: compact([rows[n].get(e) for e in eps]) for n in pols})
            A["models"][label] = M
        out["arms"][arm] = A
    out["bootstrap_keys"] = keys.used
    path = os.path.join(RES, "b11_robustness_llm.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print_llm(out)
    print("written %s" % os.path.relpath(path, ROOT))
    return path


def print_llm(out):
    print("THE LLM CAMPAIGNS REPLAYED, %s" % out["label"])
    for arm, A in out["arms"].items():
        flag = "   [%s]" % A["contamination"] if arm == "grid" else ""
        print("\n%s (%s)%s; validation k: %s" % (arm, A["instance"], flag, A["validation_k"]))
        for label, M in A["models"].items():
            print("  %s, %d campaigns, seeds %d to %d" % (label, M["campaigns"], M["seeds"][0], M["seeds"][1]))
            print("    %-15s pick %s   share %s" % (label, fmt(M["llm"]["pick"]), fmt(M["llm"]["share"], True)))
            for n, p in M["policies"].items():
                print("    %-15s pick %s   share %s" % (n, fmt(p["pick"]), fmt(p["share"], True)))
            d = M["run_a_minus_llm"]
            print("    %-15s pick %s   share %s" % ("Run A minus LLM", fmt(d["pick"]), fmt(d["share"], True)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("contamination", "noise", "llm", "report-noise", "report-llm"))
    ap.add_argument("--cv", choices=[lv for lv, _c in NOISE])
    ap.add_argument("--arm", choices=ARM_ORDER)
    a = ap.parse_args(argv)
    if a.cmd == "contamination":
        contamination()
    elif a.cmd == "noise":
        noise(a.cv)
    elif a.cmd == "llm":
        llm(a.arm)
    elif a.cmd == "report-noise":
        report_noise()
    else:
        report_llm()


if __name__ == "__main__":
    main()
