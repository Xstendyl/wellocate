#!/usr/bin/env python3
"""Summary of results/start_robustness.json (post-hoc), per landscape and rule, over the
50 random starts: the distribution of k*, the share of starts whose k* equals the paper start's, how many of those
k* lead their runner-up by more than two paired standard errors, and the re-testing share and final pick at each
start's own k* and at the paper start's k*, against the paper start's own values.

Usage: python3 scripts/start_robustness_report.py     (writes results/start_robustness_summary.json)
"""
import json, os, statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "results", "start_robustness.json")
OUT = os.path.join(ROOT, "results", "start_robustness_summary.json")
RULES = ("guessing", "informed", "model-guided")


def spread(v):
    return dict(median=st.median(v), min=min(v), max=max(v), mean=st.mean(v))


def main():
    d = json.load(open(SRC))
    out = dict(label=d["label"], source="results/start_robustness.json", n_seeds=d["n_seeds"],
               n_random_starts=d["n_random_starts"], start_seed=d["start_seed"], landscapes={})
    for land, L in d["landscapes"].items():
        paper = L["by_start"][L["paper_start"]]
        rand = [L["by_start"][s] for s in L["starts"] if s != L["paper_start"]]
        res = dict(paper_start=L["paper_start"], paper_start_value=paper["start_value"],
                   random_start_values=spread([r["start_value"] for r in rand]), rules={})
        for rule in RULES:
            pk = paper[rule]["kstar"]
            ks = [r[rule]["kstar"] for r in rand]
            clear = [r[rule]["margin"] > 2 * r[rule]["margin_se"] for r in rand]
            at_own = lambda r, f: r[rule]["settings"][str(r[rule]["kstar"])][f]
            at_paper_k = lambda r, f: r[rule]["settings"][str(pk)][f]
            res["rules"][rule] = dict(
                paper_kstar=pk, paper_kstar_clear=paper[rule]["margin"] > 2 * paper[rule]["margin_se"],
                paper_share_at_kstar=paper[rule]["settings"][str(pk)]["share_budget"],
                paper_pick_at_kstar=paper[rule]["settings"][str(pk)]["pick"],
                kstar_counts={str(k): ks.count(k) for k in sorted(set(ks) | {pk})},
                same_kstar_as_paper=sum(k == pk for k in ks), same_kstar_as_paper_pct=100.0 * sum(k == pk for k in ks) / len(ks),
                kstar_clear=sum(clear), kstar_clear_pct=100.0 * sum(clear) / len(clear),
                share_at_own_kstar=spread([at_own(r, "share_budget") for r in rand]),
                pick_at_own_kstar=spread([at_own(r, "pick") for r in rand]),
                share_at_paper_kstar=spread([at_paper_k(r, "share_budget") for r in rand]),
                pick_at_paper_kstar=spread([at_paper_k(r, "pick") for r in rand]),
                pick_lost_at_paper_kstar=spread([at_own(r, "pick") - at_paper_k(r, "pick") for r in rand]))
        out["landscapes"][land] = res
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    for land, res in out["landscapes"].items():
        print("%s (paper start %s, %.3f; random starts %.3f to %.3f)" % (
            land, res["paper_start"], res["paper_start_value"], res["random_start_values"]["min"],
            res["random_start_values"]["max"]))
        for rule, r in res["rules"].items():
            print("  %-13s paper k*=%d | random k* %s | same as paper %d/%d (%.0f%%), clear %d | share at own k* median "
                  "%.1f%% [%.1f, %.1f] (paper %.1f%%) | pick at own k* median %.3f [%.3f, %.3f] (paper %.3f)" % (
                      rule, r["paper_kstar"], r["kstar_counts"], r["same_kstar_as_paper"], out["n_random_starts"],
                      r["same_kstar_as_paper_pct"], r["kstar_clear"], r["share_at_own_kstar"]["median"],
                      r["share_at_own_kstar"]["min"], r["share_at_own_kstar"]["max"], r["paper_share_at_kstar"],
                      r["pick_at_own_kstar"]["median"], r["pick_at_own_kstar"]["min"], r["pick_at_own_kstar"]["max"],
                      r["paper_pick_at_kstar"]))
    print("written %s" % os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
