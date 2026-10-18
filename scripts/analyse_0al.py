#!/usr/bin/env python3
"""Analyse the prompt-wording and risk-free follow-up runs against the original grid campaigns.

For the wording run, each campaign is paired by condition, model and seed with the original campaign, and the
paired change in replication share and nominated true fitness is reported per cell with bootstrap intervals.
The risk-free run is compared with the guessing scripted policy under the same rule, and an all-options-off
control run, when present, separates the wording effect from service drift.
Usage: python3 scripts/analyse_0al.py      (writes results/analysis_0al.json)
"""
import collections, glob, gzip, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_grid as AG                                   # noqa: E402

ORIGINAL = ("stage1", "topup_opus", "topup_gemini", "topup_deepseek")
PANELS = {"A": "panelA_wording", "B": "panelB_riskfree"}
A0_TAG = "panelA0_original"
OPTIONS = {"A0": dict(goal_true_value=False, fix_replacement_budget=False, riskfree_rejection=False),
           "A": dict(goal_true_value=True, fix_replacement_budget=True, riskfree_rejection=False),
           "B": dict(goal_true_value=True, fix_replacement_budget=True, riskfree_rejection=True)}
CONDITIONS = ("Blind", "Mechanism")
MODELS = ("anthropic/claude-opus-4.7", "google/gemini-2.5-flash", "deepseek/deepseek-chat-v3.1")
SEEDS = range(300000, 300060)
OUT = os.path.join(ROOT, "results", "analysis_0al.json")


def share(r):
    return 100.0 * r["replication_count"] / r["slots_used"] if r["slots_used"] else 0.0


def ci(d, tag):
    lo, hi = AG.boot_ci(d, tag=tag)
    return [lo, hi]


def calls(tag):
    p = os.path.join(ROOT, "results", "grid_%s_calls.jsonl" % tag)
    srcs = [open(p)] if os.path.exists(p) else [gzip.open(g, "rt") for g in sorted(glob.glob(
        os.path.join(ROOT, "results", "grid_%s_calls" % tag, "*.jsonl.gz")))]
    for fh in srcs:
        with fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)


def within_bands(cells):
    return all(-5 <= c["d_share_ci"][0] and c["d_share_ci"][1] <= 5
               and -0.06 <= c["d_fit_ci"][0] and c["d_fit_ci"][1] <= 0.06 for c in cells.values())


def paired(a, b, tag):
    """Per cell, b minus a on the seeds both hold: the change in replication share and in final pick."""
    cells = {}
    for cond in CONDITIONS:
        for m in MODELS:
            ks = sorted(k for k in b if k[0] == cond and k[1] == m and k in a)
            dr = [share(b[k]) - share(a[k]) for k in ks]
            df = [b[k]["nominated_true"] - a[k]["nominated_true"] for k in ks]
            t = "%s|%s|%s" % (tag, cond, m.split("/")[-1])
            cells["%s|%s" % (cond, m.split("/")[-1])] = dict(
                pairs=len(ks), d_share=st.mean(dr) if dr else None, d_share_ci=ci(dr, t + "|drep"),
                d_fit=st.mean(df) if df else None, d_fit_ci=ci(df, t + "|dfit"))
    return cells


def load_panel(p, tag):
    rows = AG.load(tag)
    stray = [r for r in rows if r["condition"] not in CONDITIONS or r["model"] not in MODELS
             or r["seed"] not in SEEDS or r.get("prompt_options") != OPTIONS[p]]
    if stray:
        raise SystemExit("REFUSED: panel %s holds a campaign outside its registered design" % p)
    fb = AG.fallback_seeds([tag])
    keep = {(r["condition"], r["model"], r["seed"]): r for r in rows
            if (AG.RUNG_OF[r["condition"]], r["model"], r["seed"]) not in fb}
    return rows, fb, keep


def main():
    orig = AG.load("+".join(ORIGINAL))
    fb_orig = AG.fallback_seeds(list(ORIGINAL))
    old = {(r["condition"], r["model"], r["seed"]): r for r in orig
           if (AG.RUNG_OF[r["condition"]], r["model"], r["seed"]) not in fb_orig}
    yard = json.load(open(os.path.join(ROOT, "results", "riskfree_reference.json")))["riskfree"]
    yk = yard["kstar"]
    ys = yard["curve"][str(yk)]["replication_share"] if str(yk) in yard["curve"] else yard["curve"][yk]["replication_share"]
    out = dict(yardstick=dict(kstar=yk, share=ys, twice=2 * ys,
                              mean=(yard["curve"].get(str(yk)) or yard["curve"][yk])["mean"]))
    kept = {}
    for p, tag in PANELS.items():
        rows, fb, new = load_panel(p, tag)
        kept[p] = new
        prov = collections.defaultdict(collections.Counter)
        transport = 0
        for c in calls(tag):
            prov[(c.get("cell") or c.get("rung"), c.get("model"))][c.get("provider") or "unrecorded"] += 1
            transport += int(bool(c.get("error")))
        cells = {}
        for cond in CONDITIONS:
            for m in MODELS:
                keys = sorted(k for k in new if k[0] == cond and k[1] == m)
                pairs = [k for k in keys if k in old]
                d_rep = [share(new[k]) - share(old[k]) for k in pairs]
                d_fit = [new[k]["nominated_true"] - old[k]["nominated_true"] for k in pairs]
                sh = [share(new[k]) for k in keys]
                tagc = "0al-%s|%s|%s" % (p, cond, m.split("/")[-1])
                cell = dict(campaigns=sum(1 for r in rows if r["condition"] == cond and r["model"] == m),
                            fallbacks=sum(1 for k in fb if k[0] == AG.RUNG_OF[cond] and k[1] == m),
                            pairs=len(pairs),
                            share_new=st.mean(sh) if sh else None, share_new_ci=ci(sh, tagc + "|share"),
                            share_old_paired=st.mean(share(old[k]) for k in pairs) if pairs else None,
                            d_share=st.mean(d_rep) if d_rep else None, d_share_ci=ci(d_rep, tagc + "|drep"),
                            fit_new=st.mean(new[k]["nominated_true"] for k in keys) if keys else None,
                            fit_old_paired=st.mean(old[k]["nominated_true"] for k in pairs) if pairs else None,
                            d_fit=st.mean(d_fit) if d_fit else None, d_fit_ci=ci(d_fit, tagc + "|dfit"),
                            distinct=st.mean(new[k]["n_distinct_measured"] for k in keys) if keys else None,
                            rejections=st.mean(new[k]["n_rejected"] for k in keys) if keys else None,
                            lost_slots=st.mean(new[k]["lost_slots"] for k in keys) if keys else None,
                            cap_hits=sum(new[k].get("rejection_cap_hits", 0) for k in keys),
                            # Sensitivity: the same cell without campaigns that reached the cap.
                            share_new_nocap=(st.mean(nc) if (nc := [share(new[k]) for k in keys
                                                                   if not new[k].get("rejection_cap_hits")])
                                             else None),
                            n_nocap=sum(1 for k in keys if not new[k].get("rejection_cap_hits")),
                            campaigns_hitting_cap=sum(1 for k in keys if new[k].get("rejection_cap_hits")),
                            spend=sum(r.get("spend") or 0 for r in rows
                                      if r["condition"] == cond and r["model"] == m),
                            providers=dict(prov[(cond, m)].most_common()))
                cells["%s|%s" % (cond, m.split("/")[-1])] = cell
        if p == "A":
            label = ("the wording does not move the results" if within_bands(cells)
                     else "the wording moves the results")
        else:
            def rule_b(shares):
                if any(v <= ys + 5 for v in shares):
                    return "rejection risk explains it"
                if all(v >= 2 * ys for v in shares):
                    return "rejection risk does not produce the habit"
                return "partial"
            label = rule_b([c["share_new"] for c in cells.values()])
            sens_label = rule_b([c["share_new_nocap"] for c in cells.values() if c["share_new_nocap"] is not None])
        out["panel_" + p] = dict(tag=tag, label=label, cells=cells, transport_errors=transport,
                                 spend=sum(r.get("spend") or 0 for r in rows))
        if p == "B":
            out["panel_B"]["label_without_capped_campaigns"] = sens_label
        print("\n== PANEL %s (%s): %s" % (p, tag, label))
        for name, c in cells.items():
            print("  %-26s n=%3d pairs=%3d fb=%d | share %.1f%% (old %.1f) d %+.2f [%+.2f, %+.2f] | fit %.4f "
                  "d %+.4f [%+.4f, %+.4f] | distinct %.2f rej %.2f lost %.2f caps %d/%d"
                  % (name, c["campaigns"], c["pairs"], c["fallbacks"], c["share_new"], c["share_old_paired"],
                     c["d_share"], c["d_share_ci"][0], c["d_share_ci"][1], c["fit_new"], c["d_fit"],
                     c["d_fit_ci"][0], c["d_fit_ci"][1], c["distinct"], c["rejections"], c["lost_slots"],
                     c["campaigns_hitting_cap"], c["cap_hits"]))
    a0_file = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % A0_TAG)
    if os.path.exists(a0_file):
        rows0, fb0, a0 = load_panel("A0", A0_TAG)
        wording, drift = paired(a0, kept["A"], "0al-A-vs-A0"), paired(old, a0, "0al-A0-vs-grid")
        out["panel_A0"] = dict(
            tag=A0_TAG, campaigns=len(rows0), fallbacks=len(fb0),
            spend=sum(r.get("spend") or 0 for r in rows0),
            wording_vs_A0=dict(label=("the wording does not move the results, against a same-day control"
                                      if within_bands(wording) else "the wording moves the results, "
                                      "against a same-day control"), cells=wording),
            drift_vs_grid=dict(label=("no drift beyond the bands" if within_bands(drift)
                                      else "drift beyond the bands"), cells=drift))
        for name, block in (("A against A0", wording), ("A0 against the grid", drift)):
            print("\n== %s" % name)
            for cell, c in block.items():
                print("  %-26s pairs=%3d d share %+.2f [%+.2f, %+.2f] | d fit %+.4f [%+.4f, %+.4f]"
                      % (cell, c["pairs"], c["d_share"], c["d_share_ci"][0], c["d_share_ci"][1],
                         c["d_fit"], c["d_fit_ci"][0], c["d_fit_ci"][1]))
    else:
        out["panel_A0"] = "not run"
    print("\n  yardstick (guessing policy, risk-free): k*=%d, mean %.4f, share %.2f%%, twice %.2f%%"
          % (yk, out["yardstick"]["mean"], ys, 2 * ys))
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True)
    print("  wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
