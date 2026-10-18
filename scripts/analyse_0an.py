#!/usr/bin/env python3
"""Analyse the ledger, menu and structure tool arms against paired controls and label each cell.

Each arm campaign is paired by model and seed with a concurrent Blind control, and pairs where either nomination
failed to parse are dropped. Replication share gets a label for the ledger and menu arms ("removes re-testing",
"reduces", "no effect"), and the paired change in final pick gets a label against the detectable change from
scripts/plan_0an.py; intervals are 95% percentile bootstraps over pairs.

Usage: python3 scripts/analyse_0an.py      (writes results/analysis_0an.json)
"""
import collections, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_grid as AG                                   # noqa: E402
import launch_0an as L                                      # noqa: E402

OUT = os.path.join(ROOT, "results", "analysis_0an.json")
GRID = ("stage1", "topup_opus", "topup_gemini", "topup_deepseek")
ARMS = {"F1 ledger": ("gen_0an_f1_ledger", "ledger"), "F2 menu": ("gen_0an_f2_menu", "menu"),
        "F5 structure": ("gen_0an_f5_structure", "structure")}
ARM_KEY = {"F1 ledger": "f1_ledger", "F2 menu": "f2_menu", "F5 structure": "f5_structure"}
TOOL_OPTIONS = ("ledger", "menu", "repeat_cap", "structure")
MODELS = {"anthropic/claude-opus-4.7": "Opus", "google/gemini-2.5-flash": "Gemini",
          "deepseek/deepseek-chat-v3.1": "DeepSeek"}
LOST_GUARD = 10.0
SHARE_LABELLED = ("F1 ledger", "F2 menu", "F5 structure")
SHARE_CEILING_F3 = 50.0
CONTROL_TAG = "gen_0an_f0_control"
A0_TAG = "panelA0_original"
NOT_INTERPRETABLE = "not interpretable: slot loss"
MIN_EFFECT = 0.10


def share(r):
    return 100.0 * r["replication_count"] / r["slots_used"] if r["slots_used"] else 0.0


def share_non_lost(r):
    used = r["slots_used"] - r["lost_slots"]
    return 100.0 * r["replication_count"] / used if used > 0 else 0.0


def share_label(mean_share, d_share, ci_share, ci_d, lost, yard):
    removes, reduces = 2.0 * yard, -10.0
    if mean_share <= removes:
        out, crosses = "removes re-testing", ci_share[0] < removes < ci_share[1]
    elif d_share < reduces:
        out, crosses = "reduces", ci_d[0] < reduces < ci_d[1]
    else:
        out = "no effect"
        crosses = ci_d[0] < reduces < ci_d[1] or ci_share[0] < removes < ci_share[1]
    if out != "no effect" and lost > LOST_GUARD:
        return NOT_INTERPRETABLE
    return out + (" (interval crosses a line)" if crosses else "")


def pick_label(ci, delta):
    if ci[0] > 0:
        return "pick rises"
    if ci[1] < 0:
        return "pick falls"
    if -delta <= ci[0] and ci[1] <= delta:
        return "no change beyond delta"
    return "unresolved"


def labels(arm, d, yard):
    """The labels of one cell: a share label for the ledger and menu arms only, and a final-pick label for all."""
    out = {"pick_label": pick_label(d["d_pick_ci"], d["delta"]) + ("" if d["pick_powered"] else " (descriptive)")}
    if arm in SHARE_LABELLED:
        out["share_label"] = share_label(d["share"], d["d_share"], d["share_ci"], d["d_share_ci"], d["lost_slots"], yard)
    return out


def load_arm(tag, option):
    p = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
    if not os.path.exists(p):
        return [], 0
    rows = AG.load(tag)
    for r in rows:
        o = r.get("prompt_options") or {}
        want = {k: (option is not None and k == option) for k in TOOL_OPTIONS}
        if not o.get("truthful_reask") or any(bool(o.get(k)) != v for k, v in want.items()) \
                or o.get("goal_true_value") or o.get("fix_replacement_budget") or o.get("riskfree_rejection"):
            raise SystemExit("REFUSED: %s seed %s ran with options %s" % (tag, r["seed"], o))
        if r["condition"] != "Blind":
            raise SystemExit("REFUSED: %s holds a %s campaign" % (tag, r["condition"]))
    kept, n = AG.drop_fallbacks(rows, AG.fallback_seeds([tag]))
    return kept, sum(n.values())


def ci(v, tag):
    return list(AG.boot_ci(v, tag=tag))


def summary(pr, t, delta, powered):
    """One cell's measures over pairs (arm campaign, partner campaign)."""
    a = [x for x, _y in pr]
    sh, d_sh = [share(x) for x in a], [share(x) - share(y) for x, y in pr]
    d_pick = [x["nominated_true"] - y["nominated_true"] for x, y in pr]
    return dict(pairs=len(pr), share=st.mean(sh), share_ci=ci(sh, t + "|share"),
                partner_share=st.mean(share(y) for _x, y in pr), d_share=st.mean(d_sh), d_share_ci=ci(d_sh, t + "|dshare"),
                share_non_lost=st.mean(share_non_lost(x) for x in a),
                lost_slots=st.mean(x["lost_slots"] for x in a),
                lost_rejection=st.mean(x["slots_abandoned"] - (x.get("repeat_cap_hits") or 0) for x in a),
                lost_cap_bound=st.mean(x.get("repeat_cap_hits") or 0 for x in a),
                lost_rounds=st.mean(x["rounds_lost_slots"] for x in a),
                distinct=st.mean(x["n_distinct_measured"] for x in a),
                partner_distinct=st.mean(y["n_distinct_measured"] for _x, y in pr),
                rejections=st.mean(x["n_rejected"] for x in a), partner_rejections=st.mean(y["n_rejected"] for _x, y in pr),
                capped=st.mean(x.get("n_capped") or 0 for x in a),
                capped_ci=ci([x.get("n_capped") or 0 for x in a], t + "|capped"),
                repeat_cap_hits=sum(x.get("repeat_cap_hits") or 0 for x in a),
                pick=st.mean(x["nominated_true"] for x in a), partner_pick=st.mean(y["nominated_true"] for _x, y in pr),
                d_pick=st.mean(d_pick), d_pick_ci=ci(d_pick, t + "|dpick"), delta=delta, pick_powered=powered)


def main():
    plan = json.load(open(os.path.join(ROOT, "results", "plan_0an.json")))
    yard = plan["yardstick"]
    g, _ = AG.drop_fallbacks(AG.load("+".join(GRID)), AG.fallback_seeds(list(GRID)))
    gb = {(r["model"], r["seed"]): r for r in g if r["condition"] == "Blind"}
    a0, _ = AG.drop_fallbacks(AG.load(A0_TAG), AG.fallback_seeds([A0_TAG]))
    control = {(r["model"], r["seed"]): r for r in a0 if r["condition"] == "Blind" and "opus" in r["model"]}
    f0, nf0 = load_arm(CONTROL_TAG, None)
    control.update({(r["model"], r["seed"]): r for r in f0 if "opus" not in r["model"]})
    out = dict(yardstick=yard, share_ceiling_f3=SHARE_CEILING_F3, cells={}, fallbacks_dropped={"F0 control": nf0},
               spend={"F0 control": sum(r["spend"] for r in f0)}, control_vs_grid={})
    for m, short in MODELS.items():
        pr = [(c, gb[k]) for k, c in control.items() if k[0] == m and k in gb]
        if pr:
            out["control_vs_grid"][short] = summary(pr, "0an|control-vs-grid|" + short, None, None)
    for arm, (tag, option) in ARMS.items():
        rows, nfb = load_arm(tag, option)
        out["fallbacks_dropped"][arm] = nfb
        out["spend"][arm] = sum(r["spend"] for r in rows)
        for m, short in MODELS.items():
            p = plan["plan_n"][short][str(L.N_BY_ARM[ARM_KEY[arm]][m])]
            powered = p["pick_mde_80"] <= MIN_EFFECT
            prc = [(r, control[(m, r["seed"])]) for r in rows if r["model"] == m and (m, r["seed"]) in control]
            prg = [(r, gb[(m, r["seed"])]) for r in rows if r["model"] == m and (m, r["seed"]) in gb]
            if not prc:
                continue
            d = summary(prc, "0an|%s|%s" % (arm, short), p["pick_delta"], powered)
            d.update(labels(arm, d, yard))
            d["sensitivity_vs_grid"] = summary(prg, "0an|grid|%s|%s" % (arm, short), p["pick_delta"], powered)
            d["sensitivity_vs_grid"].update(labels(arm, d["sensitivity_vs_grid"], yard))
            out["cells"]["%s|%s" % (arm, short)] = d
    json.dump(out, open(OUT, "w"), indent=1)
    for k, d in out["cells"].items():
        print("%-18s n=%3d share %5.1f (control %5.1f, change %+5.1f [%+5.1f, %+5.1f], non-lost %5.1f) lost %.1f | "
              "distinct %.1f (control %.1f) rej %.1f capped %.1f | pick %+.3f [%+.3f, %+.3f] | %s | %s"
              % (k, d["pairs"], d["share"], d["partner_share"], d["d_share"], d["d_share_ci"][0], d["d_share_ci"][1],
                 d["share_non_lost"], d["lost_slots"], d["distinct"], d["partner_distinct"], d["rejections"],
                 d["capped"], d["d_pick"], d["d_pick_ci"][0], d["d_pick_ci"][1],
                 d.get("share_label", d.get("share_note", "")), d["pick_label"]))
    print("spend %s; fallbacks dropped %s" % ({k: round(v, 2) for k, v in out["spend"].items()}, out["fallbacks_dropped"]))
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
