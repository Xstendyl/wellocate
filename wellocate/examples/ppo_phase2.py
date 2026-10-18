#!/usr/bin/env python3
"""Post-hoc PPO runs: Run B with entropy_coef 0.05, and Run A with five more seeds (3 to 7).

`test` runs ppo.test once per split in its own process, writing training/out/b11/robustness2/test_<name>_<split>.json;
`merge` combines those into one results file per run and adds the training curves.

  test --name B_ent05 --split phoq:test      one split of the Run B ablation (checkpoints training/out/b11_rb2)
  test --name A_rep --split nk:test          one split of the Run A replication (seeds 3 to 7)
  merge                                      results/b11_B_ent05.json and results/b11_replication_A.json

Usage: python3 wellocate/examples/ppo_phase2.py test --name B_ent05 --split phoq:test
"""
import argparse, hashlib, importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location("ppo", os.path.join(HERE, "ppo.py"))
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)
_spec = importlib.util.spec_from_file_location("ppo_curves", os.path.join(HERE, "ppo_curves.py"))
PC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PC)

LABEL = "POST-HOC (spec/B11_ROBUSTNESS_2.md)"
WORK = os.path.join(ROOT, "training", "out", "b11", "robustness2")
RUNS = {"B_ent05": dict(run="B", out=os.path.join(ROOT, "training", "out", "b11_rb2"), seeds=(0, 1, 2),
                        splits=("phoq:test", "gb1:test", "nk:test"), path=os.path.join(ROOT, "results", "b11_B_ent05.json"),
                        change="entropy_coef 0.05 (registered 0.01); every other setting registered"),
        "A_rep": dict(run="A", out=P.OUT, seeds=(3, 4, 5, 6, 7), splits=("nk:test", "gb1:test", "phoq:test"),
                      path=os.path.join(ROOT, "results", "b11_replication_A.json"),
                      change="none: the registered configuration, five more seeds")}
with open(os.path.abspath(__file__), "rb") as _f:
    CODE_SHA256 = hashlib.sha256(_f.read()).hexdigest()


def part_path(name, split):
    return os.path.join(WORK, "test_%s_%s.json" % (name, split.replace(":", "_")))


def test(name, split):
    r = RUNS[name]
    os.makedirs(WORK, exist_ok=True)
    print(P.test(r["run"], out=r["out"], seeds=r["seeds"], path=part_path(name, split), splits=[split]))


def end_of_training(curves):
    """The last logged point of each seed: order- and nominate-head entropy (mean over the last bin of updates) and
    validation re-testing share; and their means over seeds."""
    last = {sd: c["points"][-1] for sd, c in curves.items()}
    mean = lambda f: sum(f(p) for p in last.values()) / len(last)
    return dict(update=[p["update"] for p in last.values()],
                order_entropy=mean(lambda p: p["order_entropy"]), nominate_entropy=mean(lambda p: p["nominate_entropy"]),
                val_share=mean(lambda p: sum(p["val_share"].values()) / len(p["val_share"])))


def merge():
    for name, r in RUNS.items():
        parts = [json.load(open(part_path(name, sp))) for sp in r["splits"] if os.path.exists(part_path(name, sp))]
        if len(parts) != len(r["splits"]):
            print("%s: %d of %d splits tested; not merged" % (name, len(parts), len(r["splits"])))
            continue
        if any(p["checkpoints"] != parts[0]["checkpoints"] for p in parts):
            raise SystemExit("ABORT: %s's splits were tested on different checkpoints" % name)
        res = dict(label=LABEL, spec="spec/B11_ROBUSTNESS_2.md", code_sha256=CODE_SHA256, run=r["run"],
                   seeds=list(r["seeds"]), change=r["change"], checkpoints=parts[0]["checkpoints"],
                   splits={sp: p["splits"][sp] for sp, p in zip(r["splits"], parts)},
                   curves=parts[0]["curves"],
                   training_curves={str(sd): PC.curves(os.path.join(r["out"], "%s_s%d" % (r["run"], sd), "log.jsonl"))
                                    for sd in r["seeds"]})
        if name == "B_ent05":
            # the original Run B's curves, for the entropy comparison
            res["registered_run_b_curves"] = {str(sd): PC.curves(os.path.join(P.OUT, "B_s%d" % sd, "log.jsonl"))
                                              for sd in (0, 1, 2)}
        res["end_of_training"] = {k: end_of_training(res[k]) for k in ("training_curves", "registered_run_b_curves")
                                  if k in res}
        with open(r["path"], "w") as f:
            json.dump(res, f, indent=1)
        print("written %s" % os.path.relpath(r["path"], ROOT))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("test", "merge"))
    ap.add_argument("--name", choices=sorted(RUNS))
    ap.add_argument("--split")
    a = ap.parse_args(argv)
    if a.cmd == "test":
        test(a.name, a.split)
    else:
        merge()


if __name__ == "__main__":
    main()
