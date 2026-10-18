#!/usr/bin/env python3
"""Training curves of the PPO runs, read from each run's log.jsonl.

For each run and seed, one line per validation point (every 50 updates):
  train reward   mean training reward (nominee's true value over the landscape's best) over the updates since the
                 previous validation point
  val score      the validation score at that update (mean pick over the landscape's best)
  val share      validation re-testing share, % of slots used (Wellocate's share_budget), per validation split
  order H        mean entropy of the order head over the same updates (nats)
  nominate H     mean entropy of the nominate head over the same updates (nats)

With --every N the training columns are averaged over bins of N updates instead, and the validation columns are
filled only on the bins that end at a validation point.

Usage: python3 wellocate/examples/ppo_curves.py [--every N] [--json PATH]
       (reads training/out/b11/<run>_s<seed>/log.jsonl)
"""
import argparse, glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "training", "out", "b11")


def curves(path, every=None):
    """Points at each validation update, or every `every` updates. Training columns average the updates
    [previous point, this point); update u's PPO step comes after the validation at u."""
    rows = [json.loads(l) for l in open(path)]
    upd = [r for r in rows if r["kind"] == "update"]
    val = {r["update"]: r for r in rows if r["kind"] == "validation"}
    ends = sorted(val) if not every else sorted(set(range(0, (upd[-1]["update"] + 1 if upd else 0) + 1, every)))
    out, prev = [], -1
    for end in ends:
        window = [u for u in upd if prev <= u["update"] < end]
        mean = lambda k: sum(u[k] for u in window) / len(window) if window else None
        v = val.get(end)
        out.append(dict(update=end, episodes=window[-1]["episodes"] if window else 0, train_reward=mean("reward"),
                        val_score=v["score"] if v else None,
                        val_share={k[:-len("_share")]: v[k] for k in sorted(v) if k.endswith("_share")} if v else None,
                        order_entropy=mean("order_entropy"), nominate_entropy=mean("nominate_entropy"),
                        best_update=v["best_update"] if v else None,
                        wall_h=(v["wall_s"] if v else window[-1]["wall_s"] if window else 0.0) / 3600))
        prev = end
    return dict(updates_logged=len(upd), points=out)


def fmt(x, f="%.3f"):
    return "-" if x is None else f % x


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=None, help="bin training columns every N updates")
    ap.add_argument("--json", default=None, help="also write the curves to this file")
    a = ap.parse_args(argv)
    allc = {}
    for d in sorted(glob.glob(os.path.join(OUT, "*_s*"))):
        log = os.path.join(d, "log.jsonl")
        if not os.path.exists(log):
            continue
        name = os.path.basename(d)
        c = allc[name] = curves(log, a.every)
        print("\n%s (%d updates logged)" % (name, c["updates_logged"]))
        splits = sorted(next(p["val_share"] for p in c["points"] if p["val_share"])) if c["points"] else []
        print("  update  episodes  train reward  val score  %s  order H  nominate H  best so far  wall h" % "  ".join(
            "val share %s" % s.split(":")[0] for s in splits))
        for p in c["points"]:
            print("  %6d  %8d  %12s  %9s  %s  %7s  %10s  %11s  %6.2f" % (
                p["update"], p["episodes"], fmt(p["train_reward"]), fmt(p["val_score"]),
                "  ".join("%13s" % fmt(p["val_share"][s] if p["val_share"] else None, "%.1f%%") for s in splits),
                fmt(p["order_entropy"], "%.2f"), fmt(p["nominate_entropy"], "%.3f"),
                fmt(p["best_update"], "%d"), p["wall_h"]))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(allc, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
