#!/usr/bin/env python3
"""Scripted references on the paper's scrambled PhoQ at assay noise. Simulation only; no model is called.

Every policy plays the agents' rules through Wellocate: 15 rounds of 4, 15% failures, three replacement asks,
multiplicative noise at CV 0.073 with the read-depth floor, and the pre-registered shrinkage nomination. The
policies are the guessing and informed rules at k = 0 to 4 and the model-guided policy (k = 1 with
confirmation). Each rule's k* has the highest mean pick on the 1,500 reference seeds, and the best scripted
share is the re-testing share of the policy with the highest mean pick among all eleven.

Seeds: the 1,500 reference seeds (8,200,000 onward) and the agents' 30 seeds (17,000,000 to 17,000,029), so each
agent campaign has a scripted twin on its own seed. Per policy and seed set: mean pick, re-testing share over
the budget and over slots not lost, exploration and selection shortfalls, distinct candidates, lost slots, the
share of nominees with one reading, and the most frequent nominee with its count. Collapsed episodes (fewer than
two measured candidates) are left out. Intervals on the 1,500 seeds are mean +/- 1.96 standard errors.

Before writing, it checks that the Wellocate landscape equals the harness's, that its sha256 matches the frozen
split, and that the guessing rule reproduces the earlier PhoQ yardstick (k* = 0, mean 2.0500, share 1.03%).

Usage: python3 scripts/references_0an8.py      (writes results/references_0an8.json)
"""
import collections, json, math, os, statistics as st, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import envs as EV                                                   # noqa: E402
from wellocate import baselines as B, env as W, landscapes as LS, scorecard as SC, splits as SP   # noqa: E402

INSTANCE = "phoq/scramble:20261004"
SPLIT = "phoq:paper"
AGENT_SEEDS = [17_000_000 + i for i in range(30)]
KS = (0, 1, 2, 3, 4)
OUT = os.path.join(ROOT, "results", "references_0an8.json")
FIELDS = ("pick", "share_budget", "share_nonlost", "exploration_shortfall", "selection_shortfall", "distinct",
          "lost_slots")


def canary_landscape():
    w = W.Wellocate(INSTANCE, seed=AGENT_SEEDS[0]).env
    h = EV.phoq_scrambled()
    same = dict(table=w.fit == h.fit, pool=w.pool == h.pool, start=w.anchor == h.anchor,
                source_keys=w.rng_key == h.rng_key, label=w.label == h.label)
    if not all(same.values()):
        raise SystemExit("ABORT: Wellocate's %s differs from the harness's phoq_scrambled: %s" % (INSTANCE, same))
    split = SP.load()["splits"][SPLIT]
    if split["instances"] != [INSTANCE]:
        raise SystemExit("ABORT: %s holds %s, not %s" % (SPLIT, split["instances"], INSTANCE))
    return dict(same_as_harness=same, label=h.label, start=h.anchor, start_value=h.fit[h.anchor],
                scramble_seed=h.meta["scramble_seed"], letter_maps=h.meta["letter_maps"],
                frozen_sha256=split["instance_sha256"][INSTANCE])


def episodes(seeds):
    return [(INSTANCE, s) for s in seeds]


def run(make, eps):
    rows = [SC.run_episode(make, inst, s, "assay") for inst, s in eps]
    return rows


def summarise(rows, ci):
    ok = [r for r in rows if r is not None]
    d = dict(n=len(ok), collapsed=len(rows) - len(ok))
    for f in FIELDS:
        v = [r[f] for r in ok]
        d[f] = st.mean(v)
        if ci and len(v) > 1:
            se = st.stdev(v) / math.sqrt(len(v))
            d[f + "_se"] = se
            d[f + "_ci"] = [d[f] - 1.96 * se, d[f] + 1.96 * se]
    d["nominee_one_reading"] = 100.0 * st.mean(1.0 if r["nominee_readings"] == 1 else 0.0 for r in ok)
    noms = collections.Counter(r["shrinkage_nominee"] for r in ok)
    d["top_nominee"], d["top_nominee_count"] = noms.most_common(1)[0]
    d["distinct_nominees"] = len(noms)
    return d


def main():
    t0 = time.time()
    land = canary_landscape()
    print("landscape: %s, start %s (%.4f), scramble seed %d; identical to the harness's: %s"
          % (land["label"], land["start"], land["start_value"], land["scramble_seed"], land["same_as_harness"]), flush=True)
    ref_eps = SP.episodes(SPLIT, 1500)
    if any(inst != INSTANCE for inst, _s in ref_eps) or ref_eps[0][1] != 8_200_000:
        raise SystemExit("ABORT: the reference episodes are not %s from seed 8,200,000" % INSTANCE)
    policies = [("guessing k=%d" % k, B.guessing(k)) for k in KS] + [("informed k=%d" % k, B.informed(k)) for k in KS]
    policies.append(("model-guided k=1 with confirmation", B.model_guided(1, True)))
    out = dict(instance=INSTANCE, split=SPLIT, noise="assay, CV 0.073", landscape=land,
               reference_seeds="8,200,000 to 8,201,499", agent_seeds="%d to %d" % (AGENT_SEEDS[0], AGENT_SEEDS[-1]),
               reference={}, agent_seeds_rows={})
    for name, make in policies:
        rr = run(make, ref_eps)
        out["reference"][name] = summarise(rr, ci=True)
        ar = run(make, episodes(AGENT_SEEDS))
        out["agent_seeds_rows"][name] = [None if r is None else {f: r[f] for f in FIELDS + ("nominee_readings", "shrinkage_nominee")}
                                         for r in ar]
        a = out["reference"][name]
        print("%-36s pick %.4f (SE %.4f)  share %6.2f%% (nonlost %6.2f%%)  explore %.3f  select %.3f  distinct %5.1f  "
              "lost %5.2f  collapsed %d" % (name, a["pick"], a["pick_se"], a["share_budget"], a["share_nonlost"],
                                            a["exploration_shortfall"], a["selection_shortfall"], a["distinct"],
                                            a["lost_slots"], a["collapsed"]), flush=True)
    # Check: the guessing rule reproduces the earlier PhoQ yardstick at every k (same seeds, rules and oracle keys).
    y = json.load(open(os.path.join(ROOT, "results", "yardsticks_0am.json")))["landscapes"][land["label"]]
    for k in KS:
        a, b = out["reference"]["guessing k=%d" % k], y["curve"][str(k)]
        if a["n"] != b["n"] or abs(a["pick"] - b["mean"]) > 1e-9 or abs(a["share_budget"] - b["replication_share"]) > 1e-9:
            raise SystemExit("ABORT: guessing k=%d gives %d / %.6f / %.4f%%, 0am's yardstick %d / %.6f / %.4f%%"
                             % (k, a["n"], a["pick"], a["share_budget"], b["n"], b["mean"], b["replication_share"]))
    print("canary: the guessing rule reproduces 0am's PhoQ yardstick at k = 0 to 4", flush=True)
    for rule in ("guessing", "informed"):
        ks = max(KS, key=lambda k: out["reference"]["%s k=%d" % (rule, k)]["pick"])
        out["%s_kstar" % rule] = ks
    best = max(out["reference"], key=lambda n: out["reference"][n]["pick"])
    b = out["reference"][best]
    out["best_scripted"] = dict(policy=best, pick=b["pick"], pick_se=b["pick_se"], share_budget=b["share_budget"],
                                share_budget_ci=b["share_budget_ci"], share_nonlost=b["share_nonlost"])
    out["seconds"] = round(time.time() - t0, 1)
    print("guessing k* = %d, informed k* = %d; BEST SCRIPTED: %s, pick %.4f, share %.2f%% [%.2f, %.2f]"
          % (out["guessing_kstar"], out["informed_kstar"], best, b["pick"], b["share_budget"], *b["share_budget_ci"]))
    json.dump(out, open(OUT, "w"), indent=1)
    print("wrote %s in %.0f s" % (os.path.relpath(OUT, ROOT), out["seconds"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
