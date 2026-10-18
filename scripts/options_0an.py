#!/usr/bin/env python3
"""Cost and precision of each tool arm at the planned and at a reduced Opus n.

Costs are the measured spend per campaign from the pilot runs. A model not run in an arm is projected from its
menu-to-control spend ratio times its control spend, and flagged. Precision uses the plan's paired SD
(results/plan_0an.json) at the new n.

Usage: python3 scripts/options_0an.py      (writes results/options_0an.json)
"""
import json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import plan_0an as P                                                  # noqa: E402

M = {"anthropic/claude-opus-4.7": "Opus", "google/gemini-2.5-flash": "Gemini", "deepseek/deepseek-chat-v3.1": "DeepSeek"}
ARMS = {"F1 ledger": "smoke0an_f1_ledger", "F2 menu": "smoke0an_f2_menu", "F3 cap": "smoke0an_f3_cap",
        "F0 control": "smoke0an_f0_control"}


def spend():
    out = {}
    for arm, tag in ARMS.items():
        rows = [json.loads(l) for l in open(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)) if l.strip()]
        out[arm] = {M[m]: st.mean(r["spend"] for r in rows if r["model"] == m) for m in M
                    if any(r["model"] == m for r in rows)}
    ds = out["F2 menu"]["DeepSeek"] / out["F0 control"]["DeepSeek"]
    out["F3 cap"].setdefault("DeepSeek", out["F0 control"]["DeepSeek"] * ds *
                             (out["F3 cap"]["Gemini"] / out["F2 menu"]["Gemini"]))
    return out


def precision(sd_pick, sd_share, n):
    t = P.tq(n - 1)
    se = sd_pick / math.sqrt(n)
    return dict(n=n, pick_half_width=t * se, pick_mde_80=(t + 0.8416) * se,
                share_half_width=t * sd_share / math.sqrt(n))


def main():
    plan = json.load(open(os.path.join(ROOT, "results", "plan_0an.json")))
    s = spend()
    prec = {short: {n: precision(v["sd_pick"], v["sd_share"], n) for n in (60, 30, 20)}
            for short, v in plan["plan"].items() if short == "Opus"}
    cost = {}
    for arm in ("F1 ledger", "F2 menu", "F3 cap"):
        for n_opus in (60, 30):
            cost["%s|opus %d" % (arm, n_opus)] = n_opus * s[arm]["Opus"] + 120 * (s[arm]["Gemini"] + s[arm]["DeepSeek"])
    cost["F0 control"] = 120 * (s["F0 control"]["Gemini"] + s["F0 control"]["DeepSeek"])
    out = dict(spend_per_campaign=s, deepseek_f3_projected=True, opus_precision=prec, arm_cost=cost)
    json.dump(out, open(os.path.join(ROOT, "results", "options_0an.json"), "w"), indent=1)
    for arm, v in s.items():
        print("%-11s $/campaign %s" % (arm, {k: round(x, 4) for k, x in v.items()}))
    print("DeepSeek in F3 never ran in the smoke; its cost is projected")
    for k, v in prec["Opus"].items():
        print("Opus n=%d: pick half-width %.3f, pick MDE %.3f, share half-width %.2f"
              % (k, v["pick_half_width"], v["pick_mde_80"], v["share_half_width"]))
    for k, v in cost.items():
        print("%-20s $%.2f" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
