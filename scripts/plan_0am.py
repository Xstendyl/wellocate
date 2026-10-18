#!/usr/bin/env python3
"""The other-landscape plan in numbers: reading lines per cell, precision at the planned n, the GB1 follow-up's
chance, and cost. Simulation and arithmetic on result files only; no model calls.

  LINES      per cell, y = the yardstick share (results/yardsticks_0am.json), the "does not generalise" line
             y + 5, and the "generalises" line G = max(2y, y + 10). G is 2y wherever y >= 10, which is every
             NK landscape; it differs only where the guessing policy re-tests almost never (scrambled GB1 and
             PhoQ, y about 1%), where 2y would fall inside the 5-point band.
  PRECISION  the 95% half-width of a cell mean at its planned n, from the per-campaign SD of replication
             share in the grid (failed nominations dropped) for that model and condition.
  FOLLOW-UP  the Opus real-minus-scrambled GB1 difference at n = 30, paired by seed. Its SD is not known
             before the run; with the two arms uncorrelated it is sqrt(2) times the grid SD.
  MONEY      expected spend from the most recent same-day Opus, Gemini and DeepSeek means per campaign
             (the original-prompt control runs) and each panel's ceiling.

Usage: python3 scripts/plan_0am.py      (writes results/plan_0am.json)
"""
import json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_grid as AG                                          # noqa: E402
import analyse_0al as A0                                           # noqa: E402
import launch_0am as LA                                            # noqa: E402
from repdef import envs as E                                       # noqa: E402
from repdef.stats import _t_sf                                     # noqa: E402

OUT = os.path.join(ROOT, "results", "plan_0am.json")
MODELS = {"anthropic/claude-opus-4.7": "Opus", "google/gemini-2.5-flash": "Gemini",
          "deepseek/deepseek-chat-v3.1": "DeepSeek"}
N = {"R": {"Opus": 30, "Gemini": 60, "DeepSeek": 60}, "K": {"Opus": 20, "Gemini": 60, "DeepSeek": 60}}


def t_quantile(df, p=0.975):
    lo, hi = 0.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _t_sf(mid, df) > 1 - p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def lines(y):
    return dict(yardstick=y, does_not_generalise_at_or_below=y + 5.0, generalises_at_or_above=max(2 * y, y + 10.0),
                two_y=2 * y)


def main():
    y = json.load(open(os.path.join(ROOT, "results", "yardsticks_0am.json")))
    tags = list(A0.ORIGINAL)
    rows, _n = AG.drop_fallbacks(AG.load("+".join(tags)), AG.fallback_seeds(tags))
    sd = {}
    for m, short in MODELS.items():
        for c in ("Blind", "Mechanism"):
            v = [100.0 * r["replication_count"] / r["slots_used"] for r in rows
                 if r["model"] == m and r["condition"] == c and r["slots_used"]]
            sd[(short, c)] = dict(n=len(v), sd=st.stdev(v), min=min(v), mean=st.mean(v))

    cells = {}
    for arm in ("gb1_scrambled", "phoq_scrambled", "gb1_real"):
        lab = (E.gb1_real() if arm == "gb1_real" else E.env_for(arm)).label
        for c in ("Blind", "Mechanism"):
            for short in ("Opus", "Gemini", "DeepSeek"):
                n = N["R"][short]
                hw = t_quantile(n - 1) * sd[(short, c)]["sd"] / math.sqrt(n)
                d = dict(panel="R", arm=arm, condition=c, model=short, n=n, half_width_95=hw)
                if arm != "gb1_real":
                    d.update(lines(y["landscapes"][lab]["share_at_kstar"]), kstar=y["landscapes"][lab]["kstar"])
                cells["R|%s|%s|%s" % (arm, c, short)] = d
    for k in E.PANEL_K:
        for short in ("Opus", "Gemini", "DeepSeek"):
            n = N["K"][short]
            hw = t_quantile(n - 1) * sd[(short, "Blind")]["sd"] / math.sqrt(n)
            d = dict(panel="K", K=k, condition="Blind", model=short, n=n, half_width_95=hw)
            d.update(lines(y["panel_k"][str(k)]["yardstick_share"]))
            cells["K|%d|Blind|%s" % (k, short)] = d
    # Pooled k* per K, as a sensitivity: the k with the best mean averaged over the 20 landscapes.
    pooled = {}
    for k in E.PANEL_K:
        ls = [y["landscapes"][lab] for lab in y["panel_k"][str(k)]["landscapes"]]
        means = {kk: st.mean(x["curve"][kk]["mean"] for x in ls) for kk in ("0", "1", "2", "3", "4")}
        ks = max(means, key=means.get)
        pooled[k] = dict(kstar=int(ks), share=st.mean(x["curve"][ks]["replication_share"] for x in ls))

    # The follow-up trigger at n = 30, paired: half-width with uncorrelated arms.
    topup = {}
    for c in ("Blind", "Mechanism"):
        s = sd[("Opus", c)]["sd"] * math.sqrt(2)
        topup[c] = dict(sd_diff_if_uncorrelated=s, half_width_n30=t_quantile(29) * s / math.sqrt(30),
                        half_width_n60=t_quantile(59) * s / math.sqrt(60),
                        correlation_needed_for_3=1 - (3 / (t_quantile(29) / math.sqrt(30))) ** 2
                        / (2 * sd[("Opus", c)]["sd"] ** 2))

    # Money, from the original-prompt control runs' same-day means per campaign.
    a0 = [json.loads(l) for l in open(os.path.join(ROOT, "results", "grid_panelA0_original_campaigns.jsonl"))
          if l.strip()]
    cost = {(MODELS[m], c): st.mean(r["spend"] for r in a0 if r["model"] == m and r["condition"] == c)
            for m in MODELS for c in ("Blind", "Mechanism")}
    per_arm_r = sum(N["R"][s] * (cost[(s, "Blind")] + cost[(s, "Mechanism")]) for s in N["R"])
    per_k = sum(N["K"][s] * cost[(s, "Blind")] for s in N["K"])
    smoke = 4 * sum(cost[(s, "Blind")] + cost[(s, "Mechanism")] for s in N["R"])
    topup_cost = 2 * 30 * (cost[("Opus", "Blind")] + cost[("Opus", "Mechanism")])
    money = dict(cost_per_campaign={"%s|%s" % k: v for k, v in cost.items()},
                 panel_R_expected=3 * per_arm_r, panel_R_per_arm=per_arm_r,
                 panel_R_ceiling=3 * LA.CEILING["R"], panel_K_expected=4 * per_k, panel_K_per_K=per_k,
                 panel_K_ceiling=4 * LA.CEILING["K"], smoke_expected=smoke, smoke_ceiling=4 * LA.CEILING["smoke"],
                 topup_expected=topup_cost, topup_ceiling=2 * LA.CEILING["topup"],
                 total_expected_before_topup=3 * per_arm_r + 4 * per_k + smoke,
                 total_ceilings_before_topup=3 * LA.CEILING["R"] + 4 * LA.CEILING["K"] + 4 * LA.CEILING["smoke"])
    # Adaptation precision: the slope on the yardstick is informed by the spread of the 80 yardsticks.
    nk_y = [(x["kstar"], x["share_at_kstar"]) for x in y["landscapes"].values() if x.get("name") == "nk"]
    def sxx(vals):
        m = st.mean(vals)
        return sum((v - m) ** 2 for v in vals)
    all_y, k1_y = [v for _k, v in nk_y], [v for k, v in nk_y if k == 1]
    t78, t75 = t_quantile(len(all_y) - 2), t_quantile(len(k1_y) - 2)
    slope = {}
    for short in ("Opus", "Gemini", "DeepSeek"):
        per = N["K"][short] // E.PANEL_K_N
        s_ = sd[(short, "Blind")]["sd"]
        slope[short] = dict(per_landscape=per,
                            half_width_all=t78 * s_ / math.sqrt(per * sxx(all_y)),
                            half_width_kstar1_only=t75 * s_ / math.sqrt(per * sxx(k1_y)))
    unpaired = {}
    for short in ("Opus", "Gemini", "DeepSeek"):
        for c in ("Blind", "Mechanism"):
            s_, ng = sd[(short, c)]["sd"], sd[(short, c)]["n"]
            unpaired["%s|%s" % (short, c)] = 1.96 * s_ * math.sqrt(1.0 / N["R"][short] + 1.0 / ng)
    y_grid = y["grid"]["alphabet_policy"]["share_at_kstar"]
    adaptation = dict(nk_yardstick_min=min(all_y), nk_yardstick_max=max(all_y),
                      nk_kstar1_min=min(k1_y), nk_kstar1_max=max(k1_y), nk_not_kstar1=len(all_y) - len(k1_y),
                      slope_half_width=slope, unpaired_half_width=unpaired, grid_yardstick=y_grid,
                      yardstick_change={a: y["landscapes"][E.env_for(a).label]["share_at_kstar"] - y_grid
                                        for a in ("gb1_scrambled", "phoq_scrambled")})
    out = dict(sd={"%s|%s" % k: v for k, v in sd.items()}, cells=cells, panel_k_pooled_kstar=pooled,
               adaptation=adaptation,
               topup=topup, money=money,
               grid_alphabet_check=dict(committed=y["grid"]["committed_policy"]["share_at_kstar"],
                                        alphabet=y["grid"]["alphabet_policy"]["share_at_kstar"],
                                        paired_change=y["grid"]["paired_change_at_committed_kstar"]))
    json.dump(out, open(OUT, "w"), indent=1)
    print("per-campaign SD of replication share in the grid (points):")
    for k, v in sorted(sd.items()):
        print("   %-9s %-10s n=%4d sd %.2f min %.2f" % (k[0], k[1], v["n"], v["sd"], v["min"]))
    print("\n%-38s %4s %6s %8s %8s %8s %4s" % ("cell", "n", "+-95%", "y", "y+5", "G", "k*"))
    for key, d in cells.items():
        print("%-38s %4d %6.2f %8s %8s %8s %4s" % (
            key, d["n"], d["half_width_95"], "%.2f" % d["yardstick"] if "yardstick" in d else "-",
            "%.2f" % d["does_not_generalise_at_or_below"] if "yardstick" in d else "-",
            "%.2f" % d["generalises_at_or_above"] if "yardstick" in d else "-", d.get("kstar", "")))
    print("\nPanel K pooled-k* sensitivity: %s" % {k: (v["kstar"], round(v["share"], 2)) for k, v in pooled.items()})
    print("Top-up at n=30 (uncorrelated arms): %s" % {c: round(v["half_width_n30"], 2) for c, v in topup.items()})
    print("   correlation the arms would need for +-3 at n=30: %s"
          % {c: round(v["correlation_needed_for_3"], 2) for c, v in topup.items()})
    print("\nMoney: R expected $%.2f (ceiling $%.2f), K expected $%.2f (ceiling $%.2f), smoke $%.2f (ceiling $%.2f)"
          % (money["panel_R_expected"], money["panel_R_ceiling"], money["panel_K_expected"], money["panel_K_ceiling"],
             money["smoke_expected"], money["smoke_ceiling"]))
    print("   total before any top-up: expected $%.2f, ceilings $%.2f; top-up expected $%.2f (ceiling $%.2f)"
          % (money["total_expected_before_topup"], money["total_ceilings_before_topup"], money["topup_expected"],
             money["topup_ceiling"]))
    a_ = adaptation
    print("\nAdaptation: grid yardstick %.2f%%, change to GB1 %+.2f, to PhoQ %+.2f"
          % (a_["grid_yardstick"], a_["yardstick_change"]["gb1_scrambled"], a_["yardstick_change"]["phoq_scrambled"]))
    print("   NK yardsticks %.2f to %.2f; k*=1 only %.2f to %.2f; %d landscapes with k* other than 1"
          % (a_["nk_yardstick_min"], a_["nk_yardstick_max"], a_["nk_kstar1_min"], a_["nk_kstar1_max"],
             a_["nk_not_kstar1"]))
    print("   expected slope half-width, all 80: %s; k*=1 only: %s"
          % ({k: round(v["half_width_all"], 2) for k, v in slope.items()},
             {k: round(v["half_width_kstar1_only"], 2) for k, v in slope.items()}))
    print("   expected unpaired half-width vs the grid: %s" % {k: round(v, 2) for k, v in unpaired.items()})
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
