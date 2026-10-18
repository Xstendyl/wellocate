#!/usr/bin/env python3
"""Read the three intervention arms together against the three explanations for re-testing.

Reads results/analysis_0an.json (share labels), results/decompose_0an.json (pick split, nomination,
exploration) and results/menu_usage_gen_0an_f2_menu.json (menu use). Writes results/readout_0an.md.

An arm "works" in a model when its share label is "removes re-testing" or "reduces". The ledger arm tests
"the agent loses track of what it has measured"; the menu arm tests "the agent cannot find new candidates";
the structure arm tests "the agent lacks knowledge of the problem's structure". If the structure arm works,
the cause is missing knowledge; if only the menu arm works, the bottleneck is producing candidates.

Usage: python3 scripts/readout_0an.py      (writes results/readout_0an.md)
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
MODELS = ("Opus", "Gemini", "DeepSeek")
ARMS = (("F1 ledger", "losing track of what was measured"), ("F2 menu", "not producing new candidates"),
        ("F5 structure", "missing knowledge of the structure"))


def works(label):
    return label.startswith("removes") or label.startswith("reduces")


def main():
    a = json.load(open(os.path.join(RES, "analysis_0an.json")))["cells"]
    d = json.load(open(os.path.join(RES, "decompose_0an.json")))
    mp = os.path.join(RES, "menu_usage_gen_0an_f2_menu.json")
    menu = json.load(open(mp)) if os.path.exists(mp) else {}
    L = ["# 0an readout: F1, F2 and F5 against the three explanations", "",
         "Share is re-tests over slots used. Each change is the arm minus its concurrent control (F0 for Gemini and",
         "DeepSeek, Panel A0 for Opus), paired by seed, with its 95% interval. The label is the registered one.", "",
         "| explanation tested | arm | Opus | Gemini | DeepSeek |", "|---|---|---|---|---|"]
    for arm, expl in ARMS:
        cells = []
        for m in MODELS:
            c = a.get("%s|%s" % (arm, m))
            cells.append("%+.1f [%+.1f, %+.1f]: %s" % (c["d_share"], c["d_share_ci"][0], c["d_share_ci"][1],
                                                      c["share_label"]) if c else "no data")
        L.append("| %s | %s | %s |" % (expl, arm, " | ".join(cells)))
    L += ["", "Joint reading per model (registered rule of 0an.3):", ""]
    for m in MODELS:
        w = {arm: works(a["%s|%s" % (arm, m)]["share_label"]) for arm, _e in ARMS if "%s|%s" % (arm, m) in a}
        if w.get("F5 structure"):
            r = "F5 works: missing knowledge is a cause"
        elif w.get("F2 menu"):
            r = "F2 works and F5 does not: the bottleneck is producing candidates"
        else:
            r = "neither F2 nor F5 works"
        if w.get("F1 ledger"):
            r += "; F1 works: losing track is a cause"
        else:
            r += "; F1 does not work"
        L.append("- %s: %s." % (m, r))
    L += ["", "## Final pick, split by seed into exploration and selection", "",
          "Pick change = exploration part (change in the best true value measured) minus selection part (change in",
          "best measured minus nominated). The pick label is the registered one, with its band.", "",
          "| arm | model | pairs | pick change | label | exploration part | selection part | readings of the nominated "
          "candidate (control) | nominated the highest mean (control) |", "|---|---|---|---|---|---|---|---|---|"]
    for arm, _e in ARMS:
        for m in MODELS:
            k = "%s|%s" % (arm, m)
            if k not in d:
                continue
            x, c = d[k], a[k]
            L.append("| %s | %s | %d | %+.3f [%+.3f, %+.3f] | %s | %+.3f [%+.3f, %+.3f] | %+.3f [%+.3f, %+.3f] | "
                     "%.1f (%.1f) | %.0f%% (%.0f%%) |"
                     % (arm, m, x["pairs"], x["d_pick"], x["d_pick_ci"][0], x["d_pick_ci"][1], c["pick_label"],
                        x["exploration_part"], x["exploration_ci"][0], x["exploration_ci"][1], x["selection_part"],
                        x["selection_ci"][0], x["selection_ci"][1], x["nominated_readings"],
                        x["control_nominated_readings"], 100 * x["chose_highest_mean"],
                        100 * x["control_chose_highest_mean"]))
    L += ["", "## Exploration and lost slots", "",
          "| arm | model | distinct (control) | rejected per new name, % (control) | lost slots: non-viable, rounds |",
          "|---|---|---|---|---|"]
    for arm, _e in ARMS:
        for m in MODELS:
            k = "%s|%s" % (arm, m)
            if k not in d:
                continue
            x, c = d[k], a[k]
            L.append("| %s | %s | %.1f (%.1f) | %.1f (%.1f) | %.2f, %.2f |"
                     % (arm, m, x["distinct"], x["control_distinct"], x["rejections_per_new_name"],
                        x["control_rejections_per_new_name"], c["lost_rejection"], c["lost_rounds"]))
    if menu:
        L += ["", "## F2: the menu in the panel", "",
              "| model | new names taken from the list | viable, from the list | viable, its own |", "|---|---|---|---|"]
        for full, v in sorted(menu.items()):
            L.append("| %s | %d of %d (%.0f%%) | %.1f%% (%d) | %.1f%% (%d) |"
                     % (full.split("/")[1], v["new_from_menu"], v["new_proposals"], 100 * v["new_from_menu_share"],
                        100 * (v["menu_new_viable_rate"] or 0), v["new_from_menu"],
                        100 * (v["own_new_viable_rate"] or 0), v["new_own"]))
    cp = os.path.join(RES, "menu_check_0an.json")
    if os.path.exists(cp):
        mc = json.load(open(cp))
        L += ["", "## F2: list names against the agent's own (scripts/menu_check_0an.py)", "",
              "New names exclude the starting candidate. \"Earlier list\" names were shown on an earlier list but not the",
              "current one. Intervals resample whole campaigns. The baseline is the same definition with no list.", "",
              "| model | list: viable (names) | earlier list | own | own minus list | own minus list, matched on rounds "
              "| no list: F0 | no list: A0 Blind |", "|---|---|---|---|---|---|---|---|"]

        def r(x):
            return "%.1f%% [%.1f, %.1f] (%d)" % (100 * x["rate"], 100 * x["ci"][0], 100 * x["ci"][1], x["names"])

        def dd(x):
            return "%+.1f [%+.1f, %+.1f]" % (100 * x["diff"], 100 * x["ci"][0], 100 * x["ci"][1])
        for full, v in sorted(mc.items()):
            bl = v["baseline"]
            L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                full.split("/")[1], r(v["list"]), r(v["earlier list"]), r(v["own"]), dd(v["own_minus_list"]),
                dd(v["own_std_minus_list"]), r(bl["F0 control"]) if "F0 control" in bl else "none",
                r(bl["Panel A0 Blind"]) if "Panel A0 Blind" in bl else "none"))
    open(os.path.join(RES, "readout_0an.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
