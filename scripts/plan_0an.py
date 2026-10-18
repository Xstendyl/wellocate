#!/usr/bin/env python3
"""Planning numbers for the aid arms: equivalence bands, power, expected spend and a reasoning-model cost estimate.

Arithmetic on committed results only; no model calls.

  SDs        per model, paired by seed against the grid's Blind campaigns, the larger of two same-design reruns,
             for the final pick and the replication share.
  BANDS      the final-pick band delta = half-width + 1.96 SE, rounded up to 0.01, so a cell with no true change
             falls within delta with probability at least 0.95.
  POWER      the smallest true change in final pick detected with 80% power at two-sided 5%.
  MONEY      expected spend from the latest same-design Blind run, and each arm's ceiling.
  R1 COST    the cost of DeepSeek R1 (0528) on the same design, from DeepSeek V3.1 Blind token counts, OpenRouter's
             listed prices and a reasoning length from measured Gemini 2.5 Flash calls, with a low case of 1,000 tokens.

Usage: python3 scripts/plan_0an.py      (writes results/plan_0an.json)
"""
import glob, gzip, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_grid as AG                                          # noqa: E402
import launch_0an as L                                             # noqa: E402
from repdef.stats import _t_sf                                     # noqa: E402

OUT = os.path.join(ROOT, "results", "plan_0an.json")
GRID = ("stage1", "topup_opus", "topup_gemini", "topup_deepseek")
MODELS = {"anthropic/claude-opus-4.7": "Opus", "google/gemini-2.5-flash": "Gemini",
          "deepseek/deepseek-chat-v3.1": "DeepSeek"}
N = {"Opus": 60, "Gemini": 120, "DeepSeek": 120}
ARMS = ("F1 ledger", "F2 menu", "F3 cap")
CEILING_PER_ARM = 25.0
YARD = 23.78           # the guessing yardstick, read below and asserted


def tq(df, p=0.975):
    lo, hi = 0.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if _t_sf(mid, df) > 1 - p else (lo, mid)
    return (lo + hi) / 2


def main():
    y = json.load(open(os.path.join(ROOT, "results", "yardsticks_0am.json")))["grid"]["alphabet_policy"]
    if round(y["share_at_kstar"], 2) != YARD:
        raise SystemExit("REFUSED: the corrected yardstick is no longer 23.78%")
    g, _n = AG.drop_fallbacks(AG.load("+".join(GRID)), AG.fallback_seeds(list(GRID)))
    gb = {(r["model"], r["seed"]): r for r in g if r["condition"] == "Blind"}
    sd = {}
    for tag in ("panelA_wording", "panelA0_original"):
        rows, _x = AG.drop_fallbacks(AG.load(tag), AG.fallback_seeds([tag]))
        for m, short in MODELS.items():
            pr = [(r, gb[(m, r["seed"])]) for r in rows if r["model"] == m and r["condition"] == "Blind"
                  and (m, r["seed"]) in gb]
            sd.setdefault(short, {})[tag] = dict(
                n=len(pr), pick=st.stdev([a["nominated_true"] - b["nominated_true"] for a, b in pr]),
                share=st.stdev([100 * (a["replication_fraction"] - b["replication_fraction"]) for a, b in pr]))
    plan = {}
    for short in N:
        n = N[short]
        s_pick = max(v["pick"] for v in sd[short].values())
        s_share = max(v["share"] for v in sd[short].values())
        se, t = s_pick / math.sqrt(n), tq(n - 1)
        hw = t * se
        delta = math.ceil((hw + 1.96 * se) * 100) / 100
        mde = (t + 0.8416) * se
        hw_share = t * s_share / math.sqrt(n)
        plan[short] = dict(n=n, sd_pick=s_pick, sd_share=s_share, pick_half_width=hw, pick_delta=delta,
                           p_meet_no_change=_p_meet(delta, hw, se), pick_mde_80=mde,
                           share_half_width=hw_share, share_mde_80=(t + 0.8416) * s_share / math.sqrt(n))
    # The same rule at each arm's own n (Opus runs 30 in some arms).
    plan_n = {}
    for short in N:
        s_pick = max(v["pick"] for v in sd[short].values())
        s_share = max(v["share"] for v in sd[short].values())
        for n in sorted({sizes[m] for sizes in L.N_BY_ARM.values() for m in sizes if MODELS[m] == short}):
            se, t = s_pick / math.sqrt(n), tq(n - 1)
            hw = t * se
            delta = math.ceil((hw + 1.96 * se) * 100) / 100
            plan_n.setdefault(short, {})[str(n)] = dict(
                n=n, pick_half_width=hw, pick_delta=delta, p_meet_no_change=_p_meet(delta, hw, se),
                pick_mde_80=(t + 0.8416) * se, share_half_width=t * s_share / math.sqrt(n))
    a0 = [json.loads(l) for l in open(os.path.join(ROOT, "results", "grid_panelA0_original_campaigns.jsonl"))
          if l.strip()]
    cost = {MODELS[m]: st.mean(r["spend"] for r in a0 if r["model"] == m and r["condition"] == "Blind")
            for m in MODELS}
    per_arm = sum(N[s] * cost[s] for s in N)
    control = sum(N[s] * cost[s] for s in ("Gemini", "DeepSeek"))      # Opus's control was run earlier
    # Cost of DeepSeek R1 (0528) on the same design.
    calls = []
    for f in glob.glob(os.path.join(ROOT, "results", "grid_topup_deepseek_calls", "blind__*.jsonl.gz")):
        calls += [json.loads(l) for l in gzip.open(f, "rt") if l.strip()]
    per_c = {}
    for c in calls:
        per_c[c["campaign_seed"]] = per_c.get(c["campaign_seed"], 0) + 1
    cpc = st.mean(per_c.values())
    ptok = st.mean(c.get("prompt_tokens") or 0 for c in calls)
    ctok = st.mean(c.get("completion_tokens") or 0 for c in calls)
    rsn = []
    for f in glob.glob(os.path.join(ROOT, "results", "grid_panelc_calls", "*gemini*.jsonl.gz")):
        rsn += [json.loads(l).get("reasoning_tokens") or 0 for l in gzip.open(f, "rt") if l.strip()]
    r_med = st.mean(rsn)
    pr = json.load(open(os.path.join(ROOT, "results", "openrouter_prices_0an.json")))["models"]
    p = pr["deepseek/deepseek-r1-0528"]["pricing"]
    pin, pout = float(p["prompt"]), float(p["completion"])
    f4 = {}
    for label, r in (("low, 1,000 reasoning tokens per call", 1000.0), ("central, measured %d" % round(r_med), r_med)):
        per = cpc * (ptok * pin + (ctok + r) * pout)
        f4[label] = dict(per_campaign=per, n120=120 * per)
    out = dict(yardstick=YARD, two_x_yardstick=2 * YARD, sd=sd, plan=plan, plan_n=plan_n, cost_per_campaign=cost,
               per_arm_expected=per_arm, control_expected=control, control_ceiling=4.0,
               total_expected=len(ARMS) * per_arm + control, ceiling_per_arm=CEILING_PER_ARM,
               total_ceiling=len(ARMS) * CEILING_PER_ARM + 4.0,
               f4=dict(model="deepseek/deepseek-r1-0528", price_in_per_m=pin * 1e6, price_out_per_m=pout * 1e6,
                       calls_per_campaign=cpc, prompt_tokens_per_call=ptok, answer_tokens_per_call=ctok,
                       measured_reasoning_tokens_per_call=r_med, estimates=f4))
    json.dump(out, open(OUT, "w"), indent=1)
    print("paired SDs vs the grid's Blind campaigns (pick, share):")
    for s, v in sd.items():
        print("   %-8s %s" % (s, {k: (round(x["pick"], 3), round(x["share"], 2)) for k, x in v.items()}))
    print("\n%-8s %4s %8s %10s %8s %10s %9s %10s" % ("model", "n", "SD pick", "half-width", "delta", "P(meet|0)",
                                                    "MDE 80%", "share hw"))
    for s, v in plan.items():
        print("%-8s %4d %8.3f %10.3f %8.2f %10.3f %9.3f %10.2f" % (s, v["n"], v["sd_pick"], v["pick_half_width"],
                                                                v["pick_delta"], v["p_meet_no_change"],
                                                                v["pick_mde_80"], v["share_half_width"]))
    print("\n0an.1, each arm's own n:")
    for s_, v in plan_n.items():
        for n_, x in v.items():
            print("   %-8s n=%3s delta %.2f P(meet|0) %.3f MDE %.3f share hw %.2f"
                  % (s_, n_, x["pick_delta"], x["p_meet_no_change"], x["pick_mde_80"], x["share_half_width"]))
    print("\nmoney: per campaign %s; per arm $%.2f, three arms $%.2f, control $%.2f, total $%.2f; ceilings $%.0f per "
          "arm and $4 for the control, $%.0f in all" % ({k: round(v, 4) for k, v in cost.items()}, per_arm, 3 * per_arm,
                                                      control, 3 * per_arm + control, CEILING_PER_ARM,
                                                      3 * CEILING_PER_ARM + 4))
    print("F4 deepseek-r1-0528: %.1f calls/campaign, %.0f prompt tokens/call; %s"
          % (cpc, ptok, {k: "$%.3f/campaign, $%.2f for 120" % (v["per_campaign"], v["n120"]) for k, v in f4.items()}))
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


def _p_meet(delta, hw, se):
    """P(the interval lies within +-delta | true change 0): the mean must fall within delta - hw of zero."""
    room = delta - hw
    if room <= 0:
        return 0.0
    return math.erf(room / se / math.sqrt(2))


if __name__ == "__main__":
    sys.exit(main())
