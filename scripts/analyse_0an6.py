#!/usr/bin/env python3
"""Analyse the menu-tool runs on scrambled GB1 against a no-tool control, paired by seed.

Gemini 2.5 Flash and DeepSeek V3.1 are compared with a concurrent control and Opus 4.7 with earlier Blind
campaigns on the same landscape. Per model it reports the change in replication share (with its label), in the
true value of the pick, and in the viability of the candidates the agent names.

Usage: python3 scripts/analyse_0an6.py [--menu TAG --control TAG]      (writes results/analysis_0an6.json)
"""
import argparse, json, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_0an as A                                                  # noqa: E402
import analyse_grid as AG                                                # noqa: E402
import menu_check_0an as MC                                              # noqa: E402
from repdef import envs as EV                                            # noqa: E402

OPUS = "anthropic/claude-opus-4.7"
OAM = ["gen_r_gb1scr", "gen_r_gb1scr_top"]
MODELS = {"anthropic/claude-opus-4.7": "Opus", "google/gemini-2.5-flash": "Gemini", "deepseek/deepseek-chat-v3.1": "DeepSeek"}


def load(tag, menu):
    rows, _ = AG.drop_fallbacks(AG.load(tag), AG.fallback_seeds([tag]))
    for r in rows:
        o = r.get("prompt_options") or {}
        if r["condition"] != "Blind" or not o.get("truthful_reask") or bool(o.get("menu")) != menu:
            raise SystemExit("REFUSED: %s seed %s ran Blind=%s with options %s" % (tag, r["seed"], r["condition"], o))
    return rows


def crosschecks(env, menu, control_tag, oam):
    """Cross-checks recomputed from the campaign files.
      control_reproduces_0am  the concurrent control's mean pick against the earlier GB1-scrambled Blind campaigns
                              of the same models on the same seeds, paired by seed, and how often each control's
                              nominee is the start candidate or one letter from it;
      sign_counts             per model, the paired seeds where the Menu's pick is higher, lower or equal;
      nominee_le_best         campaigns whose nominated true value exceeds the best true value measured (must be 0);
      distinct_nominees       per model, how many different candidates the Menu campaigns nominated, and the most
                              any single candidate was nominated;
      menu_reads_no_true_value  tools.menu's source names no landscape or true value, and the rows it is given are
                              the view's Observations, whose fields are round, candidate, outcome and reading."""
    import collections, inspect
    from repdef import tools, view as VW
    ctrl, _ = AG.drop_fallbacks(AG.load(control_tag), AG.fallback_seeds([control_tag]))
    one = lambda s: sum(1 for x, y in zip(s, env.anchor) if x != y) <= 1
    out = {"control_reproduces_0am": {}, "sign_counts": {}, "distinct_nominees": {}}
    oam_b = {(r["model"], r["seed"]): r for r in oam if r["condition"] == "Blind"}
    for m, short in MODELS.items():
        cur = [r for r in ctrl if r["model"] == m]
        if cur:
            pr = [(r, oam_b[(m, r["seed"])]) for r in cur if (m, r["seed"]) in oam_b]
            d = [x["nominated_true"] - y["nominated_true"] for x, y in pr]
            out["control_reproduces_0am"][short] = dict(
                pairs=len(pr), pick_0an6=st.mean(x["nominated_true"] for x, _y in pr),
                pick_0am=st.mean(y["nominated_true"] for _x, y in pr), d_pick=st.mean(d),
                d_pick_ci=ci(d, "0an6-xc|%s" % short),
                share_0an6=st.mean(100.0 * x["replication_count"] / x["slots_used"] for x, _y in pr),
                share_0am=st.mean(100.0 * y["replication_count"] / y["slots_used"] for _x, y in pr),
                nominee_start_or_neighbour_0an6=sum(1 for x in cur if one(x["nominated"])) / len(cur),
                nominee_start_0an6=sum(1 for x in cur if x["nominated"] == env.anchor) / len(cur),
                nominee_start_or_neighbour_0am=sum(1 for _x, y in pr if one(y["nominated"])) / len(pr))
        mine = [r for r in menu if r["model"] == m]
        partner = {(r["model"], r["seed"]): r for r in ctrl}
        partner.update({k: v for k, v in oam_b.items() if k[0] == OPUS})
        pr = [(r, partner[(m, r["seed"])]) for r in mine if (m, r["seed"]) in partner]
        out["sign_counts"][short] = dict(
            pairs=len(pr), menu_higher=sum(1 for x, y in pr if x["nominated_true"] > y["nominated_true"]),
            menu_lower=sum(1 for x, y in pr if x["nominated_true"] < y["nominated_true"]),
            equal=sum(1 for x, y in pr if x["nominated_true"] == y["nominated_true"]),
            control="0am Panel R, non-concurrent" if m == OPUS else "concurrent no-tool control")
        noms = collections.Counter(r["nominated"] for r in mine)
        out["distinct_nominees"][short] = dict(campaigns=len(mine), distinct=len(noms),
                                               most_nominated=noms.most_common(1)[0][1] if noms else 0)
    every = list(menu) + list(ctrl) + [r for r in oam if r["condition"] == "Blind"]
    out["nominee_le_best"] = dict(campaigns=len(every),
                                  exceed=sum(1 for r in every if r["nominated_true"] > r["best_true_measured"] + 1e-12))
    # Check what tools.menu is given and can reach: its parameters, the modules in tools.py, and the row fields.
    import types
    params = list(inspect.signature(tools.menu).parameters)
    mods = sorted(n for n, v in vars(tools).items() if isinstance(v, types.ModuleType))
    reach = [m for m in mods if m in ("grid", "nk", "envs", "oracle", "campaign", "landscape")]
    out["menu_reads_no_true_value"] = dict(
        parameters=params, modules_in_tools=mods, landscape_modules_reachable=reach,
        observation_fields=list(VW.Observation._fields),
        holds=(params == ["rows", "parent", "alphabet", "campaign_seed", "rnd", "n"] and not reach
               and list(VW.Observation._fields) == ["round", "seq", "outcome", "observed"]))
    return out


def ci(v, t):
    return list(AG.boot_ci(v, tag=t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--menu", default="gen_0an6_gb1_menu")
    ap.add_argument("--control", default="gen_0an6_gb1_control")
    a = ap.parse_args()
    env = EV.env_for("gb1_scrambled")
    yard = json.load(open(os.path.join(ROOT, "results", "yardsticks_0am.json")))["landscapes"][env.label]["share_at_kstar"]
    menu = load(a.menu, True)
    ctrl = {(r["model"], r["seed"]): r for r in load(a.control, False)}
    oam, _ = AG.drop_fallbacks(AG.load("+".join(OAM)), AG.fallback_seeds(OAM))
    ctrl.update({(r["model"], r["seed"]): r for r in oam if r["condition"] == "Blind" and r["model"] == OPUS})
    names = MC.names(a.menu, pool=env.pool)
    base = MC.names(a.control, pool=env.pool)
    for t in OAM:
        base.update({k: v for k, v in MC.names(t, cond="blind", pool=env.pool).items() if k[0] == OPUS})
    out = dict(yardstick=yard, removes_line=2 * yard, cells={})
    for m, short in MODELS.items():
        pr = [(r, ctrl[(m, r["seed"])]) for r in menu if r["model"] == m and (m, r["seed"]) in ctrl]
        if not pr:
            continue
        t = "0an6|%s" % short
        d = A.summary(pr, t, None, False)
        d["share_label"] = A.share_label(d["share"], d["d_share"], d["share_ci"], d["d_share_ci"], d["lost_slots"], yard)
        d["control"] = "0am Panel R, non-concurrent" if m == OPUS else "concurrent no-tool control"
        d["pick_note"] = "descriptive" if m == OPUS else "interval only; no GB1 band"
        hm = [env.fit[x["ref_mean"]] - env.fit[y["ref_mean"]] for x, y in pr]
        best = [x["best_true_measured"] - y["best_true_measured"] for x, y in pr]
        sel = [(x["best_true_measured"] - x["nominated_true"]) - (y["best_true_measured"] - y["nominated_true"])
               for x, y in pr]
        d.update(d_highest_mean_repick=st.mean(hm), d_highest_mean_repick_ci=ci(hm, t + "|hm"),
                 exploration_part=st.mean(best), exploration_ci=ci(best, t + "|best"),
                 selection_part=st.mean(sel), selection_ci=ci(sel, t + "|sel"))
        keys = [k for k in names if k[0] == m]
        v = {}
        for cls in ("list", "earlier list", "own"):
            r_, n, via = MC.rate(names, keys, lambda x, cls=cls: x[0] == cls)
            v[cls] = dict(names=n, viable=via, rate=r_,
                          ci=MC.boot(names, keys, lambda c, ks, cls=cls: MC.rate(c, ks, lambda x: x[0] == cls)[0],
                                     t + cls))
        std = MC.std_own(names, keys)
        v["own_std_minus_list"] = dict(diff=std - v["list"]["rate"], ci=MC.boot(
            names, keys, lambda c, ks: MC.std_own(c, ks) - MC.rate(c, ks, lambda x: x[0] == "list")[0], t + "stdd"))
        bk = [k for k in base if k[0] == m]
        if bk:
            r_, n, via = MC.rate(base, bk, lambda x: True)
            v["no_list_baseline"] = dict(names=n, viable=via, rate=r_, source=d["control"],
                                         ci=MC.boot(base, bk, lambda c, ks: MC.rate(c, ks, lambda x: True)[0], t + "base"))
        d["viability"] = v
        out["cells"][short] = d
    out["crosschecks"] = crosschecks(env, menu, a.control, oam)
    json.dump(out, open(os.path.join(ROOT, "results", "analysis_0an6.json"), "w"), indent=1)
    for s, d in out["cells"].items():
        v = d["viability"]
        print("%-8s n=%3d share %5.1f (control %5.1f, %s) change %+5.1f [%+5.1f, %+5.1f] lost %.1f -> %s"
              % (s, d["pairs"], d["share"], d["partner_share"], d["control"], d["d_share"], d["d_share_ci"][0],
                 d["d_share_ci"][1], d["lost_slots"], d["share_label"]))
        print("         pick %+.3f [%+.3f, %+.3f] (%s); highest-mean re-pick %+.3f [%+.3f, %+.3f]; exploration %+.3f, "
              "selection %+.3f" % (d["d_pick"], d["d_pick_ci"][0], d["d_pick_ci"][1], d["pick_note"],
                                   d["d_highest_mean_repick"], d["d_highest_mean_repick_ci"][0],
                                   d["d_highest_mean_repick_ci"][1], d["exploration_part"], d["selection_part"]))
        print("         viable: list %.1f%% (%d), earlier %.1f%% (%d), own %.1f%% (%d); own minus list, rounds matched "
              "%+.1f [%+.1f, %+.1f]%s" % (100 * v["list"]["rate"], v["list"]["names"], 100 * v["earlier list"]["rate"],
                                          v["earlier list"]["names"], 100 * v["own"]["rate"], v["own"]["names"],
                                          100 * v["own_std_minus_list"]["diff"], 100 * v["own_std_minus_list"]["ci"][0],
                                          100 * v["own_std_minus_list"]["ci"][1],
                                          "; no list %.1f%% (%d)" % (100 * v["no_list_baseline"]["rate"],
                                                                    v["no_list_baseline"]["names"])
                                          if "no_list_baseline" in v else ""))
    xc = out["crosschecks"]
    for s, d in xc["control_reproduces_0am"].items():
        print("control %-8s 0an.6 pick %.3f vs 0am %.3f, paired %+.3f [%+.3f, %+.3f]; share %.1f vs %.1f; nominee start "
              "or one-letter neighbour %.0f%% (0am %.0f%%), the start itself %.0f%%"
              % (s, d["pick_0an6"], d["pick_0am"], d["d_pick"], d["d_pick_ci"][0], d["d_pick_ci"][1], d["share_0an6"],
                 d["share_0am"], 100 * d["nominee_start_or_neighbour_0an6"], 100 * d["nominee_start_or_neighbour_0am"],
                 100 * d["nominee_start_0an6"]))
    for s, d in xc["sign_counts"].items():
        print("signs   %-8s Menu higher in %d of %d paired seeds, lower in %d, equal in %d (%s)"
              % (s, d["menu_higher"], d["pairs"], d["menu_lower"], d["equal"], d["control"]))
    for s, d in xc["distinct_nominees"].items():
        print("nominees %-8s %d different candidates over %d Menu campaigns; most nominated %d times"
              % (s, d["distinct"], d["campaigns"], d["most_nominated"]))
    print("nominated true value above the best measured: %d of %d campaigns" % (xc["nominee_le_best"]["exceed"],
                                                                                  xc["nominee_le_best"]["campaigns"]))
    print("menu reads no true value: %s (parameters %s; modules in tools %s; Observation fields %s)"
          % (xc["menu_reads_no_true_value"]["holds"], xc["menu_reads_no_true_value"]["parameters"],
             xc["menu_reads_no_true_value"]["modules_in_tools"], xc["menu_reads_no_true_value"]["observation_fields"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
