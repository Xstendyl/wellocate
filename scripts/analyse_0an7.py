#!/usr/bin/env python3
"""Analyse the reasoning-model runs (GPT-6.1 Sol and Gemini 3.1 Pro Preview at minimal effort).

Per model and arm (grid Blind, GB1 Blind, GB1 Menu) it reports the re-testing share over the budget and over
slots not lost, the nominee's true value, nominee concentration, seed-paired comparisons against earlier
comparator models, the Menu minus Blind difference on GB1, lost slots and abandoned campaigns.

Usage: python3 scripts/analyse_0an7.py [--smoke]      (writes results/analysis_0an7.json, or analysis_0an7_smoke.json)
"""
import argparse, collections, json, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_0al as A0L                                                # noqa: E402
import analyse_0an as A                                                  # noqa: E402
import analyse_grid as AG                                                # noqa: E402

MODELS = {"openai/gpt-6.1-sol": "sol", "google/gemini-3.1-pro-preview": "gem"}
ARMS = {"grid_blind": "grid", "gb1_blind": "gb1_scrambled", "gb1_menu": "gb1_scrambled"}
GB1_YARD = 0.888888888888889                 # the pre-registered GB1 guessing yardstick, used for the Menu label
ROW = re.compile(r"^\s*\d+\s+([A-Z]{4})\s+(-?\d+\.\d+)\s*$", re.M)
COMPARATORS = {
    "grid_blind": [("0an F0 control", "gen_0an_f0_control", "blind", "same prompt options"),
                   ("Panel A0", "panelA0_original", "blind", "prompt differs only by the truthful re-ask line"),
                   ("Panel c", "panelc", "blind", "prompt differs only by the truthful re-ask line; medium effort")],
    "gb1_blind": [("0am Panel R", "gen_r_gb1scr+gen_r_gb1scr_top", "blind", "same prompt options")],
    "gb1_menu": [("0an.6 Menu", "gen_0an6_gb1_menu", "blind", "same prompt options")],
}


def share_b(r):
    return 100.0 * r["replication_count"] / r["slots_used"] if r["slots_used"] else 0.0


def share_n(r):
    u = r["slots_used"] - r["lost_slots"]
    return 100.0 * r["replication_count"] / u if u > 0 else 0.0


def ci(v, t):
    return list(AG.boot_ci(v, tag=t)) if len(v) > 1 else [None, None]


def rows_of(tags, cond="Blind"):
    rows = []
    for t in tags.split("+"):
        p = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % t)
        if os.path.exists(p):
            r, _ = AG.drop_fallbacks(AG.load(t), AG.fallback_seeds([t]))
            rows += [x for x in r if x["condition"] == cond]
    return rows


def nominee_readings(tags):
    out = {}
    for t in tags.split("+"):
        for c in A0L.calls(t):
            if c.get("kind") == "nomination" and (c.get("cell") or "Blind").lower() == "blind":
                p = c.get("prompt") or ""
                n = collections.Counter(s for s, _v in ROW.findall(p.split("HISTORY", 1)[1] if "HISTORY" in p else ""))
                out[(c["model"], c["campaign_seed"])] = n
    return out


def abandoned(tags):
    out = []
    for t in tags.split("+"):
        p = os.path.join(ROOT, "results", "grid_%s.log" % t)
        if os.path.exists(p):
            out += [l.strip()[:300] for l in open(p) if "FAILED" in l or "ABANDONED" in l]
    return out


def describe(rows, reads, t):
    one = [1.0 if reads.get((r["model"], r["seed"]), {}).get(r["nominated"], 0) == 1 else 0.0 for r in rows]
    noms = collections.Counter(r["nominated"] for r in rows)
    top, cnt = noms.most_common(1)[0] if noms else (None, 0)
    sb, sn = [share_b(r) for r in rows], [share_n(r) for r in rows]
    pk = [r["nominated_true"] for r in rows]
    return dict(n=len(rows), share_budget=st.mean(sb), share_budget_ci=ci(sb, t + "|sb"), share_nonlost=st.mean(sn),
                share_nonlost_ci=ci(sn, t + "|sn"), pick=st.mean(pk), pick_ci=ci(pk, t + "|pick"),
                exploration_shortfall=st.mean(r["exploration_shortfall"] for r in rows),
                selection_shortfall=st.mean(r["selection_shortfall"] for r in rows),
                distinct=st.mean(r["n_distinct_measured"] for r in rows),
                lost_rejection=st.mean(r["slots_abandoned"] for r in rows),
                lost_rounds=st.mean(r["rounds_lost_slots"] for r in rows),
                lost_cap=st.mean(r.get("slots_cap_lost") or 0 for r in rows),
                campaigns_over_lost_round_limit=sum(1 for r in rows if r["rounds_lost_slots"] > 10),
                nominee_one_reading=st.mean(one), nominee_highest_single=st.mean(1.0 if r.get("agent_chose_max") else 0.0
                                                                                 for r in rows),
                top_nominee=top, top_nominee_count=cnt, distinct_nominees=len(noms))


def paired(a, b, t):
    pa = {r["seed"]: r for r in a}
    pr = [(x, pa[x["seed"]]) for x in b if x["seed"] in pa]
    if not pr:
        return None
    f = lambda g: [g(x) - g(y) for x, y in pr]          # ours (b) minus the comparator (a), by seed
    out = dict(pairs=len(pr))
    for k, g in (("share_budget", share_b), ("share_nonlost", share_n), ("pick", lambda r: r["nominated_true"]),
                 ("exploration_shortfall", lambda r: r["exploration_shortfall"]),
                 ("selection_shortfall", lambda r: r["selection_shortfall"])):
        v = f(g)
        out["d_" + k] = st.mean(v)
        out["d_" + k + "_ci"] = ci(v, "%s|%s" % (t, k))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    ref = json.load(open(os.path.join(ROOT, "results", "references_0an7.json")))
    mg = json.load(open(os.path.join(ROOT, "results", "model_guided_0an4.json")))["grid"]["confirm|k=1"]
    g, i = ref["gb1_scrambled"]["guessing"]["at_kstar"], ref["gb1_scrambled"]["informed"]["at_kstar"]
    gap, se = g["pick"] - i["pick"], (g["pick_se"] ** 2 + i["pick_se"] ** 2) ** 0.5
    out = dict(references={k: {p: v[p]["at_kstar"] | {"kstar": v[p]["kstar"]} for p in v} for k, v in ref.items()},
               band_grid=dict(lower=dict(policy="guessing yardstick", share_budget=ref["grid"]["guessing"]["at_kstar"]["share_budget"],
                                         share_nonlost=ref["grid"]["guessing"]["at_kstar"]["share_nonlost"]),
                              upper=dict(policy="model-guided, k = 1 with confirmation (0an.4)", share_budget=mg["share"],
                                         share_nonlost=mg["share_nonlost"])),
               gb1_informed_note=dict(guessing=g["pick"], informed=i["pick"], gap=gap, gap_in_se=gap / se,
                                      label="on scrambled GB1 the informed reference sits %.2f below guessing (%.1f unpaired "
                                            "standard errors), within noise; there it is a reference point only, with no "
                                            "claim to bound the agents' picks" % (gap, gap / se)),
               cells={}, menu_minus_blind={})
    model_rows = {}
    for m, short in MODELS.items():
        for arm, land in ARMS.items():
            base = "gen_0an7_%s_%s" % (short, arm)
            tags = ("smoke0an7_%s" % arm) if a.smoke else "+".join((base, base + "_rerun", base + "_cont"))
            rows = []
            for t_ in tags.split("+"):
                for r in rows_of(t_):
                    if r["model"] == m:
                        r["_source"] = t_
                        rows.append(r)
            if not rows:
                continue
            model_rows[(m, arm)] = rows
            t = "0an7|%s|%s" % (short, arm)
            d = describe(rows, nominee_readings(tags), t)
            rf = ref[land]
            d.update(pick_minus_informed=d["pick"] - rf["informed"]["at_kstar"]["pick"],
                     pick_minus_guessing=d["pick"] - rf["guessing"]["at_kstar"]["pick"],
                     abandoned=[l for l in abandoned(tags) if m in l], comparators={})
            for name, ctags, _c, label in COMPARATORS[arm]:
                crows = rows_of(ctags)
                creads = nominee_readings(ctags)
                for cm in sorted({r["model"] for r in crows}):
                    cr = [r for r in crows if r["model"] == cm]
                    cd = describe(cr, creads, t + "|" + name + cm)
                    cd["label"] = label
                    cd["count_of_our_top_nominee"] = sum(1 for r in cr if r["nominated"] == d["top_nominee"])
                    cd["paired"] = paired(cr, rows, t + "|" + name + cm)
                    d["comparators"]["%s|%s" % (name, cm.split("/")[1])] = cd
            # Per-campaign table with each campaign's source tag, so continuation and re-run seeds are flagged
            d["campaigns"] = [dict(seed=r["seed"], source=r["_source"], continuation=r["_source"].endswith("_cont"),
                                   rerun=r["_source"].endswith("_rerun"), share_budget=share_b(r), share_nonlost=share_n(r),
                                   pick=r["nominated_true"], nominee=r["nominated"], lost=r["lost_slots"])
                              for r in sorted(rows, key=lambda r: r["seed"])]
            d["seeds_distinct"] = len({r["seed"] for r in rows}) == len(rows)
            out["cells"]["%s|%s" % (short, arm)] = d
        b, mn = model_rows.get((m, "gb1_blind")), model_rows.get((m, "gb1_menu"))
        if b and mn:
            p = paired(b, mn, "0an7|%s|menu-blind" % short)
            dm = describe(mn, {}, "0an7|%s|mb" % short)
            p["label"] = A.share_label(dm["share_budget"], p["d_share_budget"], dm["share_budget_ci"],
                                       p["d_share_budget_ci"], dm["lost_rejection"] + dm["lost_rounds"], GB1_YARD)
            out["menu_minus_blind"][short] = p
    # Descriptive extras: calls above 16,000 reasoning tokens, spend reconciled from the credit balance,
    # and Gemini's grid result with the abandoned-then-rerun seeds left out of both sides.
    heavy = {}
    for m, short in MODELS.items():
        logged, from_errors = [], []
        for arm in ARMS:
            base = "gen_0an7_%s_%s" % (short, arm)
            for t_ in ((("smoke0an7_%s" % arm),) if a.smoke else (base, base + "_rerun", base + "_cont")):
                for c in A0L.calls(t_):
                    if c["model"] == m:
                        logged.append(c.get("reasoning_tokens") or 0)
                lp = os.path.join(ROOT, "results", "grid_%s.log" % t_)
                for l in (open(lp) if os.path.exists(lp) else []):
                    mm = re.search(r"empty content after (\d+) completion tokens", l)
                    if mm and m in l:
                        from_errors.append(int(mm.group(1)))
        heavy[short] = dict(logged_calls=len(logged), logged_above_16000=sum(1 for x in logged if x > 16000),
                            logged_max=max(logged) if logged else None, abandonment_errors_completion_tokens=from_errors)
    out["reasoning_heavy_calls"] = heavy
    if not a.smoke:
        fl = os.path.join(ROOT, "results", "finish_0an7.log")
        bal = [float(x) for x in re.findall(r"balance \$([\d.]+)", open(fl).read())] if os.path.exists(fl) else []
        rec = {short: sum(sum(r["spend"] for r in rows_of("gen_0an7_%s_%s" % (short, arm) + sfx))
                          for arm in ARMS for sfx in ("", "_rerun", "_cont")) for short in MODELS.values()}
        if bal:
            by_balance = 530.76110143 - bal[-1]
            out["spend_reconciliation"] = dict(
                launch_balance=530.76110143, final_balance=bal[-1], spent_by_balance=by_balance, recorded=rec,
                gem_by_balance=by_balance - rec["sol"], gem_unrecorded=by_balance - rec["sol"] - rec["gem"],
                assumption="Sol cancelled and abandoned nothing, so its balance spend equals its recorded spend")
        rerun_seeds = {300022, 300040, 300044}
        g = [r for r in model_rows.get(("google/gemini-3.1-pro-preview", "grid_blind"), []) if r["seed"] not in rerun_seeds]
        if g:
            d = describe(g, {}, "0an7|gem|grid|sens")
            d["seeds_left_out"] = sorted(rerun_seeds)
            d["paired_vs_F0"] = {}
            f0 = rows_of("gen_0an_f0_control")
            for cm in sorted({r["model"] for r in f0}):
                cr = [r for r in f0 if r["model"] == cm and r["seed"] not in rerun_seeds]
                d["paired_vs_F0"][cm.split("/")[1]] = paired(cr, g, "0an7|gem|grid|sens|" + cm)
            out["sensitivity_gem_grid_without_rerun_seeds"] = d
    path = os.path.join(ROOT, "results", "analysis_0an7%s.json" % ("_smoke" if a.smoke else ""))
    json.dump(out, open(path, "w"), indent=1)
    for k, d in out["cells"].items():
        print("%-16s n=%3d share %5.1f%% over the budget (primary) [%s], %5.1f%% over slots not lost (check) | pick %.3f (informed %+.3f, guessing %+.3f) | "
              "shortfall expl %.3f sel %.3f | distinct %.1f | nominee 1 reading %.0f%%, highest single %.0f%% | top %s x%d "
              "of %d | lost: rejection %.1f rounds %.1f | abandoned %d"
              % (k, d["n"], d["share_budget"], ", ".join("%.1f" % x for x in d["share_budget_ci"] if x is not None),
                 d["share_nonlost"], d["pick"], d["pick_minus_informed"], d["pick_minus_guessing"],
                 d["exploration_shortfall"], d["selection_shortfall"], d["distinct"], 100 * d["nominee_one_reading"],
                 100 * d["nominee_highest_single"], d["top_nominee"], d["top_nominee_count"], d["n"],
                 d["lost_rejection"], d["lost_rounds"], len(d["abandoned"])))
        for c, cd in d["comparators"].items():
            p = cd["paired"]
            print("     vs %-34s share %5.1f / %5.1f, pick %.3f, our top nominee x%d of %d%s"
                  % (c, cd["share_budget"], cd["share_nonlost"], cd["pick"], cd["count_of_our_top_nominee"], cd["n"],
                     "; paired %d: share %+.1f, pick %+.3f" % (p["pairs"], p["d_share_budget"], p["d_pick"]) if p else ""))
    for s_, h in out["reasoning_heavy_calls"].items():
        print("reasoning-heavy, %s: %d logged calls, %d above 16,000 reasoning tokens, largest %s; completion tokens in "
              "abandonment errors %s" % (s_, h["logged_calls"], h["logged_above_16000"], h["logged_max"],
                                         h["abandonment_errors_completion_tokens"]))
    if "spend_reconciliation" in out:
        sr = out["spend_reconciliation"]
        print("spend: $%.4f by balance; recorded Sol $%.4f, Gemini $%.4f; Gemini by balance $%.4f, unrecorded $%.4f"
              % (sr["spent_by_balance"], sr["recorded"]["sol"], sr["recorded"]["gem"], sr["gem_by_balance"], sr["gem_unrecorded"]))
    if "sensitivity_gem_grid_without_rerun_seeds" in out:
        d = out["sensitivity_gem_grid_without_rerun_seeds"]
        print("sensitivity, Gemini grid without seeds %s: n=%d share %.1f%% (not lost %.1f%%), pick %.3f; vs F0 %s"
              % (d["seeds_left_out"], d["n"], d["share_budget"], d["share_nonlost"], d["pick"],
                 {k: (round(v["d_share_budget"], 1), round(v["d_pick"], 3)) for k, v in d["paired_vs_F0"].items() if v}))
    for s, p in out["menu_minus_blind"].items():
        print("Menu minus Blind, %s: %d pairs, share %+.1f budget / %+.1f not lost, pick %+.3f, exploration %+.3f, "
              "selection %+.3f -> %s" % (s, p["pairs"], p["d_share_budget"], p["d_share_nonlost"], p["d_pick"],
                                        p["d_exploration_shortfall"], p["d_selection_shortfall"], p["label"]))
    b = out["band_grid"]
    print("band on the grid: %s %.2f%% / %.2f%%, %s %.2f%% / %.2f%% (over the budget / over slots not lost)"
          % (b["lower"]["policy"], b["lower"]["share_budget"], b["lower"]["share_nonlost"], b["upper"]["policy"],
             b["upper"]["share_budget"], b["upper"]["share_nonlost"]))
    print("GB1 informed reference: %s" % out["gb1_informed_note"]["label"])
    for land, v in out["references"].items():
        for pol, x in v.items():
            print("reference %-14s %-9s k*=%d pick %.4f, share %.2f%% budget / %.2f%% not lost"
                  % (land, pol, x["kstar"], x["pick"], x["share_budget"], x["share_nonlost"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
