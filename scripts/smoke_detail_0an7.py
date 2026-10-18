#!/usr/bin/env python3
"""Pilot runs in detail: calls, tokens and slot-loss channels per model and arm, from the campaign and call logs.

Usage: python3 scripts/smoke_detail_0an7.py      (writes results/smoke_detail_0an7.json)
"""
import collections, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_0al as A0                                                 # noqa: E402

ARMS = ("grid_blind", "gb1_blind", "gb1_menu")


def main():
    out = {}
    for arm in ARMS:
        tag = "smoke0an7_" + arm
        rows = [json.loads(l) for l in open(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)) if l.strip()]
        calls = collections.defaultdict(list)
        for c in A0.calls(tag):
            calls[c["model"]].append(c)
        for m, cs in calls.items():
            v = [r for r in rows if r["model"] == m]
            rt = sorted(c.get("reasoning_tokens") or 0 for c in cs)
            out["%s|%s" % (m.split("/")[1], arm)] = dict(
                campaigns=len(v), calls_per_campaign=len(cs) / len(v), prompt_tokens=st.mean(c.get("prompt_tokens") or 0 for c in cs),
                reasoning_median=st.median(rt), reasoning_p90=rt[int(0.9 * (len(rt) - 1))], reasoning_max=rt[-1],
                calls_with_reasoning=sum(1 for x in rt if x > 0),
                visible_median=st.median((c.get("completion_tokens") or 0) - (c.get("reasoning_tokens") or 0) for c in cs),
                rejections=[r["n_rejected"] for r in v], lost_rejection=[r["slots_abandoned"] for r in v],
                lost_rounds=[r["rounds_lost_slots"] for r in v], share=[round(100 * r["replication_fraction"], 1) for r in v],
                distinct=[r["n_distinct_measured"] for r in v], pick=[round(r["nominated_true"], 3) for r in v],
                cost_per_campaign=st.mean(r["spend"] for r in v))
    json.dump(out, open(os.path.join(ROOT, "results", "smoke_detail_0an7.json"), "w"), indent=1)
    for k, d in out.items():
        print("%-36s %4.1f calls/campaign, %4.0f prompt tok | reasoning median %5.1f p90 %4d max %4d (%d calls >0) | visible %4.1f | "
              "rejections %s lost: rejection %s rounds %s | share %s distinct %s pick %s | $%.3f"
              % (k, d["calls_per_campaign"], d["prompt_tokens"], d["reasoning_median"], d["reasoning_p90"], d["reasoning_max"],
                 d["calls_with_reasoning"], d["visible_median"], d["rejections"], d["lost_rejection"], d["lost_rounds"],
                 d["share"], d["distinct"], d["pick"], d["cost_per_campaign"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
