#!/usr/bin/env python3
"""Pilot: does an LLM agent ever re-measure its own best result?

Cells: rung x noise ratio, GB1, N campaigns each. One call per round plus at most `max_reasks`
per rejected slot. Everything is logged per proposal to JSONL.

Usage:
  python3 scripts/pilot.py --model deepseek/deepseek-v4-flash --campaigns 2 --rungs blind
  python3 scripts/pilot.py --model anthropic/claude-opus-4.7 --campaigns 5
"""
import argparse
import collections
import json
import os
import statistics as st
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import campaign as C, landscape as L, llm_policy as LP, sweep as S

PARENT = "VDGV"                # GB1 wild type at V39 D40 G41 V54, fitness exactly 1.0000
RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")


def run_cell(ls, ps, model, rung, ratio, n, seed0, unit, temperature, max_reasks, env_file,
             log_rows, budget_usd, spent, max_tokens=3000, reasoning_effort=None, rounds=15, slots=4):
    sigma = unit * ratio
    out = []
    for i in range(n):
        if budget_usd and spent[0] >= budget_usd:
            print("      BUDGET STOP at $%.2f" % spent[0]); break
        pol = LP.LLMPolicy(model, rung, sigma, parent=PARENT, temperature=temperature,
                           env_file=env_file, max_tokens=max_tokens,
                           reasoning_effort=reasoning_effort)
        t0 = time.time()
        r = C.run(ls.fitness, ls.pool, pol, sigma, seed0 + i, 0.15, pool_sorted=ps,
                  global_best=max(ls.fitness[s] for s in ls.pool), max_reasks=max_reasks,
                  nomination="agent", rounds=rounds, slots_per_round=slots)
        spent[0] += pol.spend_usd
        for c in pol.calls:
            c["campaign_seed"] = seed0 + i
            c["ratio"] = ratio
            c["landscape"] = ls.name
            c["total_rounds"] = rounds
            c["slots_per_round"] = slots
            log_rows.append(c)
        rep = r.replication_count
        out.append({
            "seed": seed0 + i, "nominated": r.nominated, "nominated_true": r.nominated_true,
            "best_true_measured": r.best_true_measured, "slots_used": r.slots_used,
            "n_ok": r.n_ok, "n_rejected": r.n_rejected, "n_abandoned": r.n_abandoned,
            "replication_count": rep,
            "ref_mean": r.ref_mean, "ref_max": r.ref_max, "agent_reason": r.agent_reason,
            "agent_chose_mean": r.nominated == r.ref_mean,
            "agent_chose_max": r.nominated == r.ref_max,
            "replication_fraction": rep / r.slots_used if r.slots_used else 0.0,
            "intents": dict(pol.intent_counts()), "statuses": dict(pol.status_counts()),
            "spend": pol.spend_usd, "secs": round(time.time() - t0, 1),
        })
        tag = ("MEAN" if r.nominated == r.ref_mean else
               "MAX" if r.nominated == r.ref_max else "NEITHER")
        if r.ref_mean == r.ref_max:
            tag = "tied"
        print("      seed %-4d slots %2d ok %2d rej %2d | REP %2d (%.0f%%) | nom %s=%.3f "
              "rule=%-7s | $%.4f | %.0fs"
              % (seed0 + i, r.slots_used, r.n_ok, r.n_rejected, rep,
                 100 * out[-1]["replication_fraction"], r.nominated, r.nominated_true,
                 tag, pol.spend_usd, out[-1]["secs"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="deepseek/deepseek-v4-flash")
    ap.add_argument("--campaigns", type=int, default=5)
    ap.add_argument("--ratios", default="2,8")
    ap.add_argument("--rungs", default="blind,instructed")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-reasks", type=int, default=1)
    ap.add_argument("--budget-usd", type=float, default=0.0, help="0 = no stop")
    ap.add_argument("--seed0", type=int, default=90000)
    ap.add_argument("--tag", default="")
    ap.add_argument("--max-tokens", type=int, default=3000)
    ap.add_argument("--slots", type=int, default=4,
                    help="slots per round. Varying this at FIXED length separates a TURN counter "
                         "from a MEASUREMENT counter or a context-length effect, which the current "
                         "design cannot distinguish because rounds, cumulative measurements and "
                         "prompt length all scale together at 4 slots per round.")
    ap.add_argument("--rounds", type=int, default=15,
                    help="campaign length. Varying this separates an ABSOLUTE clock from a "
                         "budget-fraction heuristic, which no observational regression can do.")
    ap.add_argument("--reasoning-effort", default=None,
                    help="low/medium/high; cuts the reasoning budget on reasoning models")
    args = ap.parse_args()

    ls = L.load("gb1")
    ps = tuple(sorted(ls.pool))
    unit = S.SIGMA_UNIT["gb1"]
    ratios = [float(x) for x in args.ratios.split(",")]
    rungs = args.rungs.split(",")
    spent = [0.0]
    log_rows, cells = [], {}

    print("PILOT  model=%s  GB1  unit=%.3f (top1-top2, random-calibrated)  temp=%.1f  N=%d"
          % (args.model, unit, args.temperature, args.campaigns))
    print("  scripted reference: at ratio 2 the optimum is k=0; at ratio 4 it is k=1 (+12%%).")
    for rung in rungs:
        for ratio in ratios:
            print("\n  --- rung=%s  ratio=%.0f  sigma=%.3f ---" % (rung, ratio, unit * ratio))
            cells[(rung, ratio)] = run_cell(
                ls, ps, args.model, rung, ratio, args.campaigns, args.seed0, unit,
                args.temperature, args.max_reasks, None, log_rows, args.budget_usd, spent,
                max_tokens=args.max_tokens, reasoning_effort=args.reasoning_effort,
                rounds=args.rounds, slots=args.slots)

    tag = args.tag or args.model.replace("/", "_")
    os.makedirs(RESULTS, exist_ok=True)
    jp = os.path.join(RESULTS, "pilot_%s_calls.jsonl" % tag)
    with open(jp, "w") as f:
        for row in log_rows:
            f.write(json.dumps(row) + "\n")

    print("\n" + "=" * 96)
    print("PILOT SUMMARY  %s" % args.model)
    print("=" * 96)
    print("  %-11s %6s | %14s | %8s %8s | %s"
          % ("rung", "ratio", "replication frac", "rej/slot", "malform", "intents"))
    for (rung, ratio), rows in sorted(cells.items()):
        if not rows:
            continue
        fr = [r["replication_fraction"] for r in rows]
        rej = st.mean([r["n_rejected"] / max(1, r["slots_used"]) for r in rows])
        bad = collections.Counter()
        for r in rows:
            bad.update(r["statuses"])
        tot = sum(bad.values()) or 1
        mal = 1.0 - bad.get("ok", 0) / tot
        it = collections.Counter()
        for r in rows:
            it.update(r["intents"])
        print("  %-11s %6.0f | %6.1f%% +- %-4.1f | %7.2f  %7.0f%% | %s"
              % (rung, ratio, 100 * st.mean(fr),
                 100 * (st.stdev(fr) / len(fr) ** 0.5) if len(fr) > 1 else 0.0,
                 rej, 100 * mal, dict(it)))
    print("\n  TOTAL SPEND: $%.4f over %d calls" % (spent[0], len(log_rows)))
    print("  per-call log: %s" % jp)


if __name__ == "__main__":
    main()
