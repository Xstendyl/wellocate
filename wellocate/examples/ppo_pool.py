#!/usr/bin/env python3
"""Post-hoc: Run A's eight seeds pooled, re-testing shares with cluster intervals,
and end-of-training entropies for every run.

Seeds 0 to 2 (results/b11_test_A.json) and 3 to 7 (results/b11_replication_A.json) were tested on the same episodes.
Their per-episode rows pool into one eight-seed comparison. Each seed is paired with its own initialisation, and every
seed with the same random and scripted rows. The interval is the two-level cluster bootstrap of
ppo_robustness2.Cluster (landscapes, then episodes; 10,000 draws), in its own key range so no earlier interval moves.
The pooled per-seed values must equal those of the two source files.

It also gives the re-testing share of Run A seeds 3 to 7, Run B with entropy_coef 0.05 and the pooled eight seeds,
with cluster intervals. Last, it reads the final logged order- and nominate-head entropy of every seed from the
training logs of four runs: Run A, Run A seeds 3 to 7, Run B, and Run B with the larger entropy bonus.

Usage: python3 wellocate/examples/ppo_pool.py      (writes results/b11_phase2_pooled.json)
"""
import hashlib, importlib.util, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(ROOT, "results")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R2, PC, P2 = _load("ppo_robustness2"), _load("ppo_curves"), _load("ppo_phase2")
with open(os.path.abspath(__file__), "rb") as _f:
    CODE_SHA256 = hashlib.sha256(_f.read()).hexdigest()
SPLITS = ("nk:test", "gb1:test", "phoq:test")
OTHERS = ("initialisation", "random", "guessing", "informed", "model-guided")
KEY0 = 7400
LOGS = {"Run A seeds 0-2 (registered)": [os.path.join(ROOT, "training", "out", "b11", "A_s%d" % s) for s in (0, 1, 2)],
        "Run A seeds 3-7": [os.path.join(ROOT, "training", "out", "b11", "A_s%d" % s) for s in (3, 4, 5, 6, 7)],
        "Run B (registered)": [os.path.join(ROOT, "training", "out", "b11", "B_s%d" % s) for s in (0, 1, 2)],
        "Run B, entropy_coef 0.05": [os.path.join(ROOT, "training", "out", "b11_rb2", "B_s%d" % s) for s in (0, 1, 2)]}


def per_seed_check(c, src, split, name):
    """The pooled per-seed differences must be the source files' own, seed for seed."""
    want = []
    for fn, n in src:
        s = json.load(open(os.path.join(RES, fn)))["splits"][split]
        reg = s["comparisons"].get("vs " + name) or s["versus_scripted"].get(name)
        want += reg["per_seed"]
    got = c["seed"]["per_seed"]
    if len(got) != len(want) or any(abs(a - b) > 1e-9 for a, b in zip(got, want)):
        raise SystemExit("ABORT: pooled per-seed %s %s differs from the source files" % (split, name))


def pooled(key):
    A = json.load(open(os.path.join(RES, "b11_test_A.json")))
    B = json.load(open(os.path.join(RES, "b11_replication_A.json")))
    out = {}
    for split in SPLITS:
        pa, pb = A["splits"][split]["per_episode"], B["splits"][split]["per_episode"]
        if A["splits"][split]["episodes"] != B["splits"][split]["episodes"]:
            raise SystemExit("ABORT: %s was tested on different episodes" % split)
        for n in ("random", "guessing", "informed", "model-guided"):
            if pa[n] != pb[n]:
                raise SystemExit("ABORT: %s %s rows differ between the two tests" % (split, n))
        trained = pa["trained"] + pb["trained"]
        init = pa["initialisation"] + pb["initialisation"]
        inst = [r["instance"] for r in trained[0]]
        key += 1
        cl = R2.Cluster(inst, key)
        comps = {"initialisation": init}
        comps.update({n: [pa[n]] * len(trained) for n in OTHERS[1:]})
        rows = {}
        for n, other in comps.items():
            c = R2.cluster_paired(cl, trained, other, "pick")
            per_seed_check(c, [("b11_test_A.json", 3), ("b11_replication_A.json", 5)], split, n)
            rows["trained minus %s, pick" % n] = c
        rows["trained re-testing share, %"] = R2.cluster_mean(cl, trained, "share")
        out[split] = rows
    return out, key


def shares(key):
    out = {}
    for fn in ("b11_replication_A.json", "b11_B_ent05.json"):
        d = json.load(open(os.path.join(RES, fn)))
        out[fn] = {}
        for split, s in d["splits"].items():
            trained = s["per_episode"]["trained"]
            key += 1
            c = R2.cluster_mean(R2.Cluster([r["instance"] for r in trained[0]], key), trained, "share")
            if abs(c["mean"] - s["table"]["trained"]["share"]["mean"]) > 1e-9:
                raise SystemExit("ABORT: %s %s share %.9f, results file %.9f" % (fn, split, c["mean"],
                                                                                  s["table"]["trained"]["share"]["mean"]))
            c["per_seed"] = [p["mean"] for p in s["table"]["trained"]["share"]["per_seed"]]
            out[fn][split] = c
    return out, key


def entropies():
    out = {}
    for run, dirs in LOGS.items():
        curves = {os.path.basename(d): PC.curves(os.path.join(d, "log.jsonl")) for d in dirs}
        last = {sd: c["points"][-1] for sd, c in curves.items()}
        out[run] = dict(P2.end_of_training(curves),
                        per_seed={sd: dict(update=p["update"], order_entropy=p["order_entropy"],
                                           nominate_entropy=p["nominate_entropy"]) for sd, p in last.items()})
    # the merged results files hold the same means; they must agree
    for run, fn, k in (("Run A seeds 3-7", "b11_replication_A.json", "training_curves"),
                       ("Run B, entropy_coef 0.05", "b11_B_ent05.json", "training_curves"),
                       ("Run B (registered)", "b11_B_ent05.json", "registered_run_b_curves")):
        ref = json.load(open(os.path.join(RES, fn)))["end_of_training"][k]
        for f in ("order_entropy", "nominate_entropy", "val_share"):
            if abs(ref[f] - out[run][f]) > 1e-9:
                raise SystemExit("ABORT: %s %s %.9f, %s %.9f" % (run, f, out[run][f], fn, ref[f]))
    return out


def main():
    pool, key = pooled(KEY0)
    sh, key = shares(key)
    res = dict(label=R2.LABEL, spec="spec/B11_ROBUSTNESS_2.md", code_sha256=CODE_SHA256, draws=R2.REPS,
               method=("Run A seeds 0 to 7 pooled: mean over seeds of per-seed paired differences on the shared test "
                       "episodes; two-level bootstrap, landscapes then episodes; seed level: t-interval at 7 degrees of "
                       "freedom"),
               pooled_seeds_0_7=pool, shares=sh, end_of_training=entropies())
    path = os.path.join(RES, "b11_phase2_pooled.json")
    with open(path, "w") as f:
        json.dump(res, f, indent=1)
    for split, rows in pool.items():
        for name, c in rows.items():
            print("seeds 0-7 %-9s %-34s %+.3f [%+.3f, %+.3f]%s" % (
                split, name, c["mean"], c["ci"][0], c["ci"][1],
                "  seeds %s t [%+.3f, %+.3f]" % ("/".join("%+.3f" % x for x in c["seed"]["per_seed"]),
                                                  *c["seed"]["t_interval"]) if "seed" in c else ""))
    for fn, rows in sh.items():
        for split, c in rows.items():
            print("share %-24s %-9s %.2f [%.2f, %.2f]  seeds %s" % (
                fn, split, c["mean"], c["ci"][0], c["ci"][1], "/".join("%.2f" % x for x in c["per_seed"])))
    for run, e in res["end_of_training"].items():
        print("%-28s order H %.3f  nominate H %.3f  val share %.2f  %s" % (
            run, e["order_entropy"], e["nominate_entropy"], e["val_share"],
            " ".join("%s:%.2f/%.3f" % (sd, p["order_entropy"], p["nominate_entropy"]) for sd, p in e["per_seed"].items())))
    print("written %s" % os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
