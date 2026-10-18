#!/usr/bin/env python3
"""Post-hoc: recompute every PPO comparison from its per-episode rows with a two-level cluster bootstrap
(landscapes, then episodes within landscape; 10,000 draws), next to the original interval and the seed-level
mean, range and t-interval. Flags any interval that now crosses zero.

Usage: python3 wellocate/examples/ppo_cluster.py      (writes results/b11_cluster_bootstrap.json)
"""
import hashlib, importlib.util, json, os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location("ppo_robustness2", os.path.join(HERE, "ppo_robustness2.py"))
R2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R2)
RES = os.path.join(ROOT, "results")
with open(os.path.abspath(__file__), "rb") as _f:
    CODE_SHA256 = hashlib.sha256(_f.read()).hexdigest()


def crosses(old, new):
    """True when the old interval excluded zero and the new one does not."""
    return bool((old[0] > 0 or old[1] < 0) and new[0] <= 0 <= new[1])


def row(source, name, old, c):
    return dict(source=source, comparison=name, mean=c["mean"], old_interval=list(old), cluster_interval=c["ci"],
                levels=c["levels"], seed=c["seed"], now_crosses_zero=crosses(old, c["ci"]),
                old_excludes_zero=bool(old[0] > 0 or old[1] < 0), new_excludes_zero=bool(c["ci"][0] > 0 or c["ci"][1] < 0))


def test_file(fname, key0):
    d = json.load(open(os.path.join(RES, fname)))
    out, key = [], key0
    for split, s in d["splits"].items():
        pe = s["per_episode"]
        inst = [r["instance"] for r in pe["trained"][0]]
        for other in [pe["random"]] + [pe[n] for n in ("guessing", "informed", "model-guided")] + pe["initialisation"]:
            if [r["instance"] for r in other if r is not None] != [i for i, r in zip(inst, other) if r is not None]:
                raise SystemExit("ABORT: %s %s rows are not in one episode order" % (fname, split))
        key += 1
        cl = R2.Cluster(inst, key)
        n = len(pe["trained"])
        comps = {"vs initialisation": pe["initialisation"], "vs random": [pe["random"]] * n}
        comps.update({"vs %s" % k: [pe[k]] * n for k in ("guessing", "informed", "model-guided")})
        for name, other in comps.items():
            c = R2.cluster_paired(cl, pe["trained"], other, "pick")
            reg = s["comparisons"].get(name) or s["versus_scripted"].get(name[3:])
            if abs(c["mean"] - reg["mean"]) > 1e-9:
                raise SystemExit("ABORT: %s %s %s mean %.9f, registered %.9f" % (fname, split, name, c["mean"],
                                                                                  reg["mean"]))
            out.append(row(fname, "%s, trained minus %s, pick" % (split, name[3:]), reg["ci"], c))
    return out, key


def noise_file(key0):
    fname = "b11_robustness_noise.json"
    d = json.load(open(os.path.join(RES, fname)))
    inst = [e[0] for e in d["episode_list"]]
    out, key = [], key0
    pr = lambda pe, n: [None if p is None else dict(pick=p, share=s) for p, s in zip(pe[n]["pick"], pe[n]["share"])]
    for lv, L in d["levels"].items():
        key += 1
        cl = R2.Cluster(inst, key)
        pe = L["per_episode"]
        runA = [pr(pe, "Run A s%d" % i) for i in range(3)]
        for name, c0 in L["comparisons"].items():
            other = "random" if name.endswith("random") else name.split("(")[1].rstrip(")")
            for f in ("pick", "share"):
                c = R2.cluster_paired(cl, runA, [pr(pe, other)] * 3, f)
                if abs(c["mean"] - c0[f]["mean"]) > 1e-6:
                    raise SystemExit("ABORT: %s %s %s %s mean differs" % (fname, lv, name, f))
                out.append(row(fname, "%s, %s, %s" % (lv, name, f), c0[f]["ci"], c))
        for rule, b in L["best_k"].items():
            for name, c0 in b["others"].items():
                a, bb = name.split(" minus ")
                c = R2.cluster_paired(cl, [pr(pe, a)], [pr(pe, bb)], "pick")
                out.append(row(fname, "%s, %s, pick" % (lv, name), c0["pick"]["ci"], c))
    key += 1
    cl = R2.Cluster(inst, key)
    for name, c0 in d["share_change_vs_assay"].items():
        who, rest = name.split(", ")
        lv = rest.split(" ")[0]
        a = d["levels"][lv]["per_episode"]
        b = d["levels"]["assay"]["per_episode"]
        if who == "Run A":
            c = R2.cluster_paired(cl, [pr(a, "Run A s%d" % i) for i in range(3)], [pr(b, "Run A s%d" % i) for i in range(3)],
                                  "share")
        else:
            c = R2.cluster_paired(cl, [pr(a, who)], [pr(b, who)], "share")
        out.append(row(fname, "share change, %s" % name, c0["ci"], c))
    return out, key


def llm_file(key0):
    fname = "b11_robustness_llm.json"
    d = json.load(open(os.path.join(RES, fname)))
    out, key = [], key0
    for arm, A in d["arms"].items():
        for label, M in A["models"].items():
            pe = M["per_episode"]
            pr = lambda n: [None if p is None else dict(pick=p, share=s) for p, s in zip(pe[n]["pick"], pe[n]["share"])]
            key += 1
            cl = R2.Cluster([A["instance"]] * len(pe["seeds"]), key)
            runA = [pr("Run A s%d" % i) for i in range(3)]
            for f in ("pick", "share"):
                c = R2.cluster_paired(cl, runA, [pr("llm")] * 3, f)
                c0 = M["run_a_minus_llm"][f]
                if abs(c["mean"] - c0["mean"]) > 1e-6:
                    raise SystemExit("ABORT: %s %s %s %s mean differs" % (fname, arm, label, f))
                out.append(row(fname, "%s, %s, Run A minus the LLM, %s" % (arm, label, f), c0["ci"], c))
    return out, key


def main():
    rows, key = [], 7100
    for fn in ("b11_test_A.json", "b11_test_B.json"):
        r, key = test_file(fn, key)
        rows += r
    r, key = noise_file(key)
    rows += r
    r, key = llm_file(key)
    rows += r
    # the extra-seed and entropy runs use their own key range, so no earlier interval moves
    key = 7300
    for fn in ("b11_replication_A.json", "b11_B_ent05.json"):
        if os.path.exists(os.path.join(RES, fn)):
            r, key = test_file(fn, key)
            rows += r
    out = dict(label=R2.LABEL, spec="spec/B11_ROBUSTNESS_2.md", code_sha256=CODE_SHA256, draws=R2.REPS,
               method=("two-level bootstrap: landscapes with replacement, then each chosen landscape's episodes with "
                       "replacement; Run A's seeds kept as registered; seed level: per-seed means, range, t-interval "
                       "(t quantile at seeds minus one degrees of freedom)"),
               rows=rows, now_cross_zero=[r["source"] + ": " + r["comparison"] for r in rows if r["now_crosses_zero"]],
               by_name={r["source"] + " | " + r["comparison"]: r for r in rows})
    path = os.path.join(RES, "b11_cluster_bootstrap.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    w = max(len(r["comparison"]) for r in rows)
    for r in rows:
        s = r["seed"]
        print("%-28s %-*s %+.3f  old [%+.3f, %+.3f]  cluster [%+.3f, %+.3f]  seeds %s t [%+.3f, %+.3f]%s" % (
            r["source"][:28], w, r["comparison"], r["mean"], r["old_interval"][0], r["old_interval"][1],
            r["cluster_interval"][0], r["cluster_interval"][1],
            "/".join("%+.3f" % x for x in s["per_seed"]),
            s["t_interval"][0], s["t_interval"][1],
            "   <-- NOW CROSSES ZERO" if r["now_crosses_zero"] else ""))
    print("%d comparisons; %d now cross zero; written %s" % (len(rows), len(out["now_cross_zero"]),
                                                            os.path.relpath(path, ROOT)))


if __name__ == "__main__":
    main()
