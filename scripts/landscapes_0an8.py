#!/usr/bin/env python3
"""Compare three landscapes side by side and run two descriptive checks on the PhoQ picks. No model is called.

For the grid, scrambled GB1 and scrambled PhoQ it reports each model's re-testing share and final pick with 95%
seed-bootstrap intervals, the share of nominees with one successful reading, and Wellocate's reference rows (the
best scripted policy, and the guessing rule at its best k). It pairs each model's pick with the guessing rule's on
the same seeds, and repeats Appendix E's nominee-grouped sensitivity analysis for Sol's lead on PhoQ. The grid and
PhoQ cells must equal the numbers already published from other files.

Usage: python3 scripts/landscapes_0an8.py      (writes results/landscapes_0an8.json)
"""
import collections, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
from repdef import envs as EV                                             # noqa: E402
from wellocate import baselines as WB, env as W, scorecard as SC          # noqa: E402
import analyse_0an7 as A7                                                 # noqa: E402
import analyse_0an8 as A8                                                 # noqa: E402
import analyse_grid as AG                                                 # noqa: E402
import basins as BS                                                       # noqa: E402
import gb1_sensitivity_0an7 as GS                                         # noqa: E402
import launch_0an8 as L8                                                  # noqa: E402

RES = os.path.join(ROOT, "results")
MODELS = [("opus", "Opus 4.7"), ("flash", "Gemini 2.5 Flash"), ("deepseek", "DeepSeek V3.1"), ("sol", "GPT-6.1 Sol"),
          ("gem", "Gemini 3.1 Pro")]
GB1_INSTANCE = "gb1/scramble:20261003"


def arms():
    """{landscape: {label: (model id, [tags])}}, the paper's arms."""
    out = {"grid": {}, "GB1": {}, "PhoQ": {}}
    for land, key in (("grid", "grid Blind"), ("GB1", "GB1 Blind")):
        for label, model, tags in BS.ARMS[key]:
            out[land][label] = (model, tags.split("+"))
    for short, label in MODELS:
        model = [m for m in L8.MODELS if m[0] == short][0][1]
        out["PhoQ"][label] = (model, A8.tags_of(short, False))
    return out


def rows_for(model, tags):
    rows = [r for t in tags for r in A7.rows_of(t) if r["model"] == model]
    if len({r["seed"] for r in rows}) != len(rows):
        raise SystemExit("REFUSED: a seed is written twice in %s" % tags)
    return rows


def wellocate_best(split):
    w = json.load(open(os.path.join(RES, "wellocate_scorecard.json")))["splits"]
    v = w[split]
    v = v.get("assay", v)
    return v["best_scripted"]


def canary_gb1():
    w = W.Wellocate(GB1_INSTANCE, seed=8_200_000).env
    h = EV.gb1_scrambled()
    same = (w.fit == h.fit, w.pool == h.pool, w.anchor == h.anchor, w.rng_key == h.rng_key)
    if not all(same):
        raise SystemExit("ABORT: Wellocate's %s is not the harness's gb1_scrambled: %s" % (GB1_INSTANCE, same))
    # the guessing rule at k = 0 on the first reference seeds must reproduce the published yardstick rows
    y = json.load(open(os.path.join(RES, "yardsticks_0am.json")))["landscapes"][h.label]["check_first_seeds"]["0"]
    for i, (pick, share) in enumerate(y):
        sc = SC.run_episode(WB.guessing(0), GB1_INSTANCE, 8_200_000 + i, "assay")
        if abs(sc["pick"] - pick) > 1e-9 or abs(sc["share_budget"] - share) > 1e-9:
            raise SystemExit("ABORT: GB1 guessing k=0 at seed %d gives %.6f / %.4f, 0am %.6f / %.4f"
                             % (8_200_000 + i, sc["pick"], sc["share_budget"], pick, share))
    return len(y)


def paired(rows, twin, tag):
    pr = [(r["nominated_true"], twin[r["seed"]]) for r in rows if twin.get(r["seed"]) is not None]
    d = [a - b for a, b in pr]
    return dict(pairs=len(d), diff=st.mean(d), ci=list(AG.boot_ci(d, tag=tag)), agent_mean=st.mean(a for a, _b in pr),
                guessing_mean=st.mean(b for _a, b in pr))


def sol_sensitivity(rows, g):
    """Appendix E's four sensitivity versions, on Sol's PhoQ campaigns."""
    gh = 1.96 * g["pick_se"]
    fit = EV.phoq_scrambled().fit
    top, count = collections.Counter(r["nominated"] for r in rows).most_common(1)[0]
    if any(abs(r["nominated_true"] - fit[r["nominated"]]) > 1e-9 for r in rows):
        raise SystemExit("ABORT: a campaign's pick is not its nominee's true value")
    collapsed = [r for r in rows if r["nominated"] != top] + [next(r for r in rows if r["nominated"] == top)]
    picks, picks_c = [r["nominated_true"] for r in rows], [r["nominated_true"] for r in collapsed]
    versions = {
        "as registered (seed bootstrap)": (picks, AG.boot_ci(picks, tag="0an8S|seed")),
        "cluster bootstrap by nominee": (picks, GS.cluster_ci([(r["nominated"], r["nominated_true"]) for r in rows],
                                                              "0an8S|cl")),
        "%s collapsed to one (seed bootstrap)" % top: (picks_c, AG.boot_ci(picks_c, tag="0an8S|col")),
        "%s collapsed, cluster bootstrap" % top: (picks_c, GS.cluster_ci([(r["nominated"], r["nominated_true"])
                                                                          for r in collapsed], "0an8S|colcl")),
    }
    out = dict(top_nominee=top, top_nominee_campaigns=count, top_nominee_true=fit[top], campaigns=len(rows),
               distinct_nominees=len({r["nominated"] for r in rows}), guessing=g["pick"], guessing_se=g["pick_se"],
               versions={})
    for name, (p, pci) in versions.items():
        m = st.mean(p)
        lead = m - g["pick"]
        ci = [lead - ((m - pci[0]) ** 2 + gh ** 2) ** 0.5, lead + ((pci[1] - m) ** 2 + gh ** 2) ** 0.5]
        out["versions"][name] = dict(n=len(p), pick=m, pick_ci=list(pci), lead=lead, lead_ci=ci, above=ci[0] > 0)
        print("Sol on PhoQ, %-40s n=%2d pick %.3f, lead %+.3f [%+.3f, %+.3f]" % (name, len(p), m, lead, ci[0], ci[1]))
    out["survives_every_version"] = all(v["above"] for v in out["versions"].values())
    # stable keys for the findings row, whatever the top nominee is called
    out["by_role"] = {"registered": out["versions"]["as registered (seed bootstrap)"],
                      "by_nominee": out["versions"]["cluster bootstrap by nominee"],
                      "top_once": out["versions"]["%s collapsed to one (seed bootstrap)" % top],
                      "top_once_by_nominee": out["versions"]["%s collapsed, cluster bootstrap" % top]}
    return out


def main():
    a8 = json.load(open(os.path.join(RES, "analysis_0an8.json")))
    r7 = json.load(open(os.path.join(RES, "references_0an7.json")))
    r8 = json.load(open(os.path.join(RES, "references_0an8.json")))
    out = dict(cells={}, references={}, paired_with_guessing={}, checks={})
    A = arms()
    rowsets = {}
    for land, ms in A.items():
        out["cells"][land] = {}
        for label, (model, tags) in ms.items():
            rows = rows_for(model, tags)
            rowsets[(land, label)] = rows
            reads = A7.nominee_readings("+".join(tags))
            d = A7.describe(rows, reads, "0an8L|%s|%s" % (land, label))
            out["cells"][land][label] = dict(tags=tags, n=d["n"], share=d["share_budget"], share_ci=d["share_budget_ci"],
                                             pick=d["pick"], pick_ci=d["pick_ci"],
                                             one_reading_pct=100.0 * d["nominee_one_reading"],
                                             without_history=sum(1 for r in rows if (r["model"], r["seed"]) not in reads))
            c = out["cells"][land][label]
            print("%-5s %-17s n=%3d share %5.1f%% pick %.3f one reading %3.0f%%" % (land, label, c["n"], c["share"],
                                                                                c["pick"], c["one_reading_pct"]))
    # the references, by Wellocate's definition
    gb = wellocate_best("gb1:paper")
    out["references"] = {
        "grid": dict(best=wellocate_best("nk:paper"), guessing=dict(k=r7["grid"]["guessing"]["kstar"],
                     share=r7["grid"]["guessing"]["at_kstar"]["share_budget"], pick=r7["grid"]["guessing"]["at_kstar"]["pick"])),
        "GB1": dict(best=gb, guessing=dict(k=r7["gb1_scrambled"]["guessing"]["kstar"],
                    share=r7["gb1_scrambled"]["guessing"]["at_kstar"]["share_budget"],
                    pick=r7["gb1_scrambled"]["guessing"]["at_kstar"]["pick"])),
        "PhoQ": dict(best=dict(policy=r8["best_scripted"]["policy"], pick=r8["best_scripted"]["pick"],
                               share_budget=r8["best_scripted"]["share_budget"]),
                     guessing=dict(k=r8["guessing_kstar"], share=a8["references"]["guessing_at_kstar"]["share_budget"],
                                   pick=a8["references"]["guessing_at_kstar"]["pick"]))}
    # Checks against numbers already published from other files
    figrow = {h["name"]: h["value"] for r in json.load(open(os.path.join(RES, "findings.json")))["rows"]
              if r["id"] == "headline figure data: five models on the grid" for h in r["headline"]}
    bad = []
    for _s, label in MODELS:
        g = out["cells"]["grid"][label]
        for k, name in (("share", "%s, re-testing share, %%" % label), ("pick", "%s, final pick" % label)):
            if abs(round(g[k], 4) - figrow[name]) > 1e-4:
                bad.append("grid %s %s: %.4f against the headline figure's %.4f" % (label, k, g[k], figrow[name]))
        p = out["cells"]["PhoQ"][label]
        m8 = a8["models"][label]
        if abs(p["share"] - m8["share_budget"]) > 1e-9 or abs(p["pick"] - m8["pick"]) > 1e-9:
            bad.append("PhoQ %s differs from analysis_0an8.json" % label)
    a7 = json.load(open(os.path.join(RES, "analysis_0an7.json")))
    pro_grid = 100.0 * a7["cells"]["gem|grid_blind"]["nominee_one_reading"]
    if abs(out["cells"]["grid"]["Gemini 3.1 Pro"]["one_reading_pct"] - pro_grid) > 1e-9:
        bad.append("Gemini 3.1 Pro's grid one-reading share %.4f against analysis_0an7's %.4f"
                   % (out["cells"]["grid"]["Gemini 3.1 Pro"]["one_reading_pct"], pro_grid))
    if bad:
        raise SystemExit("ABORT:\n  " + "\n  ".join(bad))
    out["checks"]["grid and PhoQ cells equal the published numbers"] = True
    out["checks"]["GB1 Wellocate canary seeds"] = canary_gb1()
    # Paired with the guessing rule on the agents' own seeds
    k8 = r8["guessing_kstar"]
    twin8 = {L8.SEED0 + i: (r or {}).get("pick") for i, r in enumerate(r8["agent_seeds_rows"]["guessing k=%d" % k8])}
    out["paired_with_guessing"]["PhoQ"] = {"k": k8}
    out["paired_with_guessing"]["GB1"] = {"k": r7["gb1_scrambled"]["guessing"]["kstar"]}
    kg = out["paired_with_guessing"]["GB1"]["k"]
    for _s, label in MODELS:
        out["paired_with_guessing"]["PhoQ"][label] = paired(rowsets[("PhoQ", label)], twin8, "0an8P|PhoQ|" + label)
        rows = rowsets[("GB1", label)]
        twin = {}
        for r in rows:
            sc = SC.run_episode(WB.guessing(kg), GB1_INSTANCE, r["seed"], "assay")
            twin[r["seed"]] = sc["pick"] if sc else None
        out["paired_with_guessing"]["GB1"][label] = paired(rows, twin, "0an8P|GB1|" + label)
        for land in ("GB1", "PhoQ"):
            v = out["paired_with_guessing"][land][label]
            print("paired %-5s %-17s %2d pairs, pick minus guessing %+.3f [%+.3f, %+.3f]"
                  % (land, label, v["pairs"], v["diff"], v["ci"][0], v["ci"][1]))
    out["sol_phoq_by_nominee"] = sol_sensitivity(rowsets[("PhoQ", "GPT-6.1 Sol")],
                                                 dict(pick=r8["reference"]["guessing k=%d" % k8]["pick"],
                                                      pick_se=r8["reference"]["guessing k=%d" % k8]["pick_se"]))
    json.dump(out, open(os.path.join(RES, "landscapes_0an8.json"), "w"), indent=1)
    print("wrote results/landscapes_0an8.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
