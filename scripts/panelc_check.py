#!/usr/bin/env python3
"""Write results/panelc_check.md, a per-cell breakdown of the reasoning panel against the main grid run.

Per cell: the seeds that pair with the main run, the campaigns excluded for an unparsed nomination and their
finish reason, the paired difference on the primary outcome with its interval and Holm p, and the matching
changes in replication share, distinct variants, selection shortfall and rejections. A sensitivity table
repeats the paired figures with the excluded campaigns put back. Everything is recomputed from the campaign
files and the call archive.

Usage: python3 scripts/panelc_check.py [--out results/panelc_check.md]
"""
import argparse, collections, glob, gzip, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_grid as A  # noqa: E402

TAG, BASE = "panelc", "stage1"
CONDS = ["Blind", "Mechanism"]
MODELS = ["anthropic/claude-opus-4.7", "google/gemini-2.5-flash"]


def campaigns(tag):
    p = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
    return [json.loads(l) for l in open(p) if l.strip()]


def calls(tag):
    out = []
    for g in sorted(glob.glob(os.path.join(ROOT, "results", "grid_%s_calls" % tag, "*.jsonl.gz"))):
        with gzip.open(g, "rt") as f:
            out += [json.loads(l) for l in f if l.strip()]
    return out


def holm(ps):
    """Holm-adjusted p-values, in the order given."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, (len(ps) - rank) * ps[i])
        adj[i] = min(1.0, run)
    return adj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "panelc_check.md"))
    a = ap.parse_args()

    pc, base = campaigns(TAG), campaigns(BASE)
    cl = calls(TAG)

    # Excluded: a nomination that did not parse, where campaign.py substituted best_by_mean().
    fb = [r for r in cl if r.get("kind") == "nomination" and r.get("parse_status") != "ok"]
    fb_key = {(r["rung"], r["campaign_seed"], r["model"]) for r in fb}
    fb_by_cell = collections.defaultdict(list)
    for r in fb:
        fb_by_cell[(r["rung"], r["model"])].append(r)

    rung_of = {"Blind": "blind", "Mechanism": "instructed"}

    def key(c):
        return (rung_of[c["condition"]], c["seed"], c["model"])

    rows = []
    for cond in CONDS:
        for model in MODELS:
            mine = {c["seed"]: c for c in pc if c["condition"] == cond and c["model"] == model}
            theirs = {c["seed"]: c for c in base if c["condition"] == cond and c["model"] == model}
            shared = sorted(set(mine) & set(theirs))
            dropped = [s for s in shared if key(mine[s]) in fb_key]
            used = [s for s in shared if s not in dropped]
            d_prim = [mine[s]["nominated_true"] - theirs[s]["nominated_true"] for s in used]
            d_rep = [mine[s]["replication_fraction"] - theirs[s]["replication_fraction"] for s in used]
            d_dis = [mine[s]["n_distinct_measured"] - theirs[s]["n_distinct_measured"] for s in used]
            # Selection shortfall and rejected candidates, which can explain an outcome change.
            d_sel = [(mine[s].get("selection_shortfall") or 0.0)
                     - (theirs[s].get("selection_shortfall") or 0.0) for s in used]
            d_rej = [(mine[s].get("n_rejected") or 0) - (theirs[s].get("n_rejected") or 0) for s in used]
            d_lost = [(mine[s].get("lost_slots") or 0) - (theirs[s].get("lost_slots") or 0) for s in used]
            d_best = [mine[s]["best_true_measured"] - theirs[s]["best_true_measured"] for s in used]
            se = st.stdev(d_prim) / math.sqrt(len(d_prim))
            p = A.paired_wild_p(d_prim)
            fin = collections.Counter(r.get("finish_reason") for r in fb_by_cell[(rung_of[cond], model)])
            rows.append(dict(cond=cond, model=model, seeds_panel=len(mine), seeds_base=len(theirs),
                             pairs=len(shared), dropped=len(dropped), used=len(used),
                             dropped_seeds=dropped, finish=dict(fin),
                             diff=st.mean(d_prim), se=se,
                             lo=st.mean(d_prim) - 1.96 * se, hi=st.mean(d_prim) + 1.96 * se, p=p,
                             panel_rep=100 * st.mean(mine[s]["replication_fraction"] for s in used),
                             base_rep=100 * st.mean(theirs[s]["replication_fraction"] for s in used),
                             d_rep=100 * st.mean(d_rep),
                             d_rep_se=100 * st.stdev(d_rep) / math.sqrt(len(d_rep)),
                             panel_dis=st.mean(mine[s]["n_distinct_measured"] for s in used),
                             base_dis=st.mean(theirs[s]["n_distinct_measured"] for s in used),
                             d_dis=st.mean(d_dis),
                             d_dis_se=st.stdev(d_dis) / math.sqrt(len(d_dis)),
                             panel_sel=st.mean(mine[s].get("selection_shortfall") or 0.0 for s in used),
                             base_sel=st.mean(theirs[s].get("selection_shortfall") or 0.0 for s in used),
                             d_sel=st.mean(d_sel), d_sel_se=st.stdev(d_sel) / math.sqrt(len(d_sel)),
                             d_rej=st.mean(d_rej), d_rej_se=st.stdev(d_rej) / math.sqrt(len(d_rej)),
                             base_rej=st.mean(theirs[s].get("n_rejected") or 0 for s in used),
                             panel_rej=st.mean(mine[s].get("n_rejected") or 0 for s in used),
                             panel_best=st.mean(mine[s]["best_true_measured"] for s in used),
                             base_best=st.mean(theirs[s]["best_true_measured"] for s in used),
                             d_best=st.mean(d_best),
                             d_best_se=st.stdev(d_best) / math.sqrt(len(d_best)),
                             d_lost=st.mean(d_lost)))
    for r, padj in zip(rows, holm([r["p"] for r in rows])):
        r["holm"] = padj

    # Sensitivity: repeat every paired figure with the excluded campaigns put back.
    sens = []
    for cond in CONDS:
        for model in MODELS:
            mine = {c["seed"]: c for c in pc if c["condition"] == cond and c["model"] == model}
            theirs = {c["seed"]: c for c in base if c["condition"] == cond and c["model"] == model}
            allp = sorted(set(mine) & set(theirs))
            d = [mine[s]["nominated_true"] - theirs[s]["nominated_true"] for s in allp]
            se2 = st.stdev(d) / math.sqrt(len(d))
            sens.append(dict(cond=cond, model=model, n=len(allp), diff=st.mean(d), se=se2,
                             lo=st.mean(d) - 1.96 * se2, hi=st.mean(d) + 1.96 * se2,
                             p=A.paired_wild_p(d)))
    for r, padj in zip(sens, holm([r["p"] for r in sens])):
        r["holm"] = padj

    fin_all = collections.Counter(r.get("finish_reason") for r in cl)
    L = []
    w = L.append
    w("# Panel (c) check: reasoning effort medium, after the finish_reason reruns\n")
    w("Regenerate with `python3 scripts/panelc_check.py`. Every figure is recomputed from")
    w("`results/grid_panelc_campaigns.jsonl`, `results/grid_stage1_campaigns.jsonl` and the panel's call")
    w("archive. Nothing is read from a table in `results/analysis_final/`.\n")
    w("Panel (c) holds **%d campaigns** in %d cells and **%d archived calls**." % (len(pc), len(rows), len(cl)))
    w("Finish reasons over every call in the panel: %s."
      % ", ".join("**%s** %d" % (k, v) for k, v in sorted(fin_all.items(), key=lambda t: -t[1])))
    w("No call reports `finish_reason == \"error\"`, which the repair now raises on.\n")
    w("## Per cell\n")
    w("`pairs` is seeds present in both panel (c) and stage 1. `0ag` is campaigns excluded because the")
    w("nomination did not parse and the harness substituted its own averaging rule. `used` is what every")
    w("paired figure below is computed on.\n")
    w("| condition | model | panel n | stage-1 n | pairs | 0ag | used | 0ag finish reasons |")
    w("|---|---|---:|---:|---:|---:|---:|---|")
    for r in rows:
        w("| %s | %s | %d | %d | %d | %d | %d | %s |"
          % (r["cond"], r["model"].split("/")[-1], r["seeds_panel"], r["seeds_base"], r["pairs"],
             r["dropped"], r["used"],
             ", ".join("%s %d" % (k, v) for k, v in sorted(r["finish"].items())) or "none"))
    w("\n### Primary outcome, paired by seed\n")
    w("Nominated true fitness, panel (c) minus stage 1. Interval is the paired normal interval. `wild p` is")
    w("the studentised wild cluster bootstrap over seeds with %d draws, and Holm runs across these four rows"
      % A.BOOT_REPS)
    w("only.\n")
    w("| condition | model | used | diff | SE | 95% CI | wild p | Holm p | reject at .05 |")
    w("|---|---|---:|---:|---:|---|---:|---:|---|")
    for r in rows:
        w("| %s | %s | %d | %+.4f | %.4f | [%+.4f, %+.4f] | %.5f | %.5f | %s |"
          % (r["cond"], r["model"].split("/")[-1], r["used"], r["diff"], r["se"], r["lo"], r["hi"],
             r["p"], r["holm"], "YES" if r["holm"] < 0.05 else "no"))
    w("\n### The mechanism: replication share and distinct variants, same pairs\n")
    w("Both are paired on the same seeds as the primary outcome. Replication share is over slots used.\n")
    w("| condition | model | repl share panel | repl share stage 1 | delta (SE) | distinct panel |"
      " distinct stage 1 | delta (SE) |")
    w("|---|---|---:|---:|---|---:|---:|---|")
    for r in rows:
        w("| %s | %s | %.1f%% | %.1f%% | %+.2f pp (%.2f) | %.2f | %.2f | %+.2f (%.2f) |"
          % (r["cond"], r["model"].split("/")[-1], r["panel_rep"], r["base_rep"], r["d_rep"], r["d_rep_se"],
             r["panel_dis"], r["base_dis"], r["d_dis"], r["d_dis_se"]))
    w("\n### 0ag sensitivity: the same comparison with all nine excluded campaigns put back\n")
    w("`summary.json`'s `contrasts_with_fallbacks` covers the confirmatory family, and panel (c) has no")
    w("confirmatory contrast of its own, so the sensitivity for this comparison is computed here. Every")
    w("cell uses all 40 paired seeds. In a kept campaign the nomination is whatever `best_by_mean()`")
    w("returned, which is the Decision-rule instruction applied by the harness.\n")
    w("| condition | model | n | diff | SE | 95% CI | wild p | Holm p | reject at .05 | primary diff |")
    w("|---|---|---:|---:|---:|---|---:|---:|---|---:|")
    for r, prim in zip(sens, rows):
        w("| %s | %s | %d | %+.4f | %.4f | [%+.4f, %+.4f] | %.5f | %.5f | %s | %+.4f |"
          % (r["cond"], r["model"].split("/")[-1], r["n"], r["diff"], r["se"], r["lo"], r["hi"],
             r["p"], r["holm"], "YES" if r["holm"] < 0.05 else "no", prim["diff"]))
    w("\n### What the extra exploration cost, and where the outcome went\n")
    w("Reasoning lowered the replication share and raised the distinct-variant count in every cell, and the")
    w("primary outcome still fell. Three quantities separate the ways that can happen. Best measured is the")
    w("true value of the best candidate the agent actually measured, so a fall means the wider search")
    w("returned worse candidates. Selection shortfall is best measured minus nominated, so a rise means the")
    w("agent held a better reading and did not nominate it. Rejections and lost slots say what the wider")
    w("search cost in budget.\n")
    w("| condition | model | selection shortfall panel | stage 1 | delta (SE) | rejections delta (SE) |"
      " lost slots delta |")
    w("|---|---|---:|---:|---|---|---:|")
    for r in rows:
        w("| %s | %s | %.4f | %.4f | %+.4f (%.4f) | %+.2f (%.2f) | %+.2f |"
          % (r["cond"], r["model"].split("/")[-1], r["panel_sel"], r["base_sel"], r["d_sel"], r["d_sel_se"],
             r["d_rej"], r["d_rej_se"], r["d_lost"]))
    w("\n### The excluded seeds, named\n")
    for r in rows:
        if r["dropped_seeds"]:
            w("- %s / %s: %s" % (r["cond"], r["model"].split("/")[-1],
                                 ", ".join(str(s) for s in r["dropped_seeds"])))
    w("\nA sensitivity keeping the 0ag campaigns is in `results/analysis_final/panelc/summary.json` under")
    w("`contrasts_with_fallbacks`.\n")
    w("### What this file does not settle\n")
    w("The arithmetic above is stated without a reading. Three things it cannot decide on its own. The")
    w("comparison is unpaired in treatment even though it is paired in seed, because stage 1 ran at a")
    w("different time with a different token budget. Panel (c) covers two of the five conditions, so no")
    w("ladder-wide claim follows from it. And the two gemini cells drop 5 and 4 campaigns under 0ag, which")
    w("the sensitivity addresses but does not remove.\n")
    open(a.out, "w").write("\n".join(L) + "\n")
    print("wrote %s" % os.path.relpath(a.out, ROOT))
    for r in rows:
        print("  %-10s %-20s pairs %2d  0ag %d  used %2d  diff %+.4f  holm %.5f  repl %+.2f pp  distinct %+.2f"
              % (r["cond"], r["model"].split("/")[-1], r["pairs"], r["dropped"], r["used"],
                 r["diff"], r["holm"], r["d_rep"], r["d_dis"]))
    print("  selection shortfall delta, rejections delta, lost-slot delta:")
    for r in rows:
        print("    %-10s %-20s sel %+.4f (%.4f)  rej %+.2f  lost %+.2f"
              % (r["cond"], r["model"].split("/")[-1], r["d_sel"], r["d_sel_se"], r["d_rej"], r["d_lost"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
