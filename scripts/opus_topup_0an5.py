#!/usr/bin/env python3
"""Opus 4.7 with the Menu at n = 30 (pre-registered) and n = 60 (with extra campaigns), side by side.

Paired by seed with the all-options-off Opus Blind campaigns, fallbacks dropped. Per n: the share change and its
label (analyse_0an.labels, with the band sized for that n); the pick change split into exploration and
selection; and list against own-name viability, using menu_check_0an's classes and campaign bootstrap. The
n = 30 share label stands unless the n = 60 label differs, in which case both are reported.

Usage: python3 scripts/opus_topup_0an5.py      (writes results/opus_topup_0an5.json)
"""
import json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_0an as A                                                  # noqa: E402
import analyse_grid as AG                                                # noqa: E402
import grid                                                              # noqa: E402
import menu_check_0an as MC                                              # noqa: E402

OPUS = "anthropic/claude-opus-4.7"
TOPUP = "gen_0an5_f2_menu_opus"


def main():
    plan = json.load(open(os.path.join(ROOT, "results", "plan_0an.json")))
    yard = plan["yardstick"]
    a0, _ = AG.drop_fallbacks(AG.load(A.A0_TAG), AG.fallback_seeds([A.A0_TAG]))
    control = {r["seed"]: r for r in a0 if r["condition"] == "Blind" and r["model"] == OPUS}
    f2, _ = A.load_arm("gen_0an_f2_menu", "menu")
    top, _ = A.load_arm(TOPUP, "menu")
    rows = {30: [r for r in f2 if r["model"] == OPUS], 60: [r for r in f2 if r["model"] == OPUS] + top}
    _fit, pool = grid.landscape()
    names = MC.names("gen_0an_f2_menu", pool=pool)
    names.update(MC.names(TOPUP, pool=pool))
    out = {}
    for n, rs in rows.items():
        pr = [(r, control[r["seed"]]) for r in rs if r["seed"] in control]
        p = plan["plan_n"]["Opus"].get(str(n)) or plan["plan"]["Opus"]
        d = A.summary(pr, "0an5|n%d" % n, p["pick_delta"], p["pick_mde_80"] <= A.MIN_EFFECT)
        d.update(A.labels("F2 menu", d, yard))
        d_best = [x["best_true_measured"] - y["best_true_measured"] for x, y in pr]
        d_sel = [(x["best_true_measured"] - x["nominated_true"]) - (y["best_true_measured"] - y["nominated_true"])
                 for x, y in pr]
        d.update(exploration_part=st.mean(d_best), exploration_ci=list(AG.boot_ci(d_best, tag="0an5|best|%d" % n)),
                 selection_part=st.mean(d_sel), selection_ci=list(AG.boot_ci(d_sel, tag="0an5|sel|%d" % n)))
        keys = [(OPUS, r["seed"]) for r in rs if (OPUS, r["seed"]) in names]
        v = {}
        for cls in ("list", "earlier list", "own"):
            r_, cnt, via = MC.rate(names, keys, lambda x, cls=cls: x[0] == cls)
            v[cls] = dict(names=cnt, viable=via, rate=r_,
                          ci=MC.boot(names, keys, lambda c, ks, cls=cls: MC.rate(c, ks, lambda x: x[0] == cls)[0],
                                     "0an5|%d|%s" % (n, cls)))
        std = MC.std_own(names, keys)
        v["own_std_minus_list"] = dict(
            diff=std - v["list"]["rate"],
            ci=MC.boot(names, keys, lambda c, ks: MC.std_own(c, ks) - MC.rate(c, ks, lambda x: x[0] == "list")[0],
                       "0an5|%d|stdd" % n))
        d["viability"] = v
        out[str(n)] = d
    lab30, lab60 = out["30"]["share_label"], out["60"]["share_label"]
    out["share_label_registered"] = lab30
    out["share_label_note"] = ("n = 60 agrees" if lab30 == lab60 else "n = 60 reads %r; both reported" % lab60)
    json.dump(out, open(os.path.join(ROOT, "results", "opus_topup_0an5.json"), "w"), indent=1)
    for n in ("30", "60"):
        d = out[n]
        v = d["viability"]
        print("Opus F2 n=%s: share %.1f vs %.1f, change %+.1f [%+.1f, %+.1f] %s | pick %+.3f [%+.3f, %+.3f] %s | "
              "exploration %+.3f [%+.3f, %+.3f] selection %+.3f [%+.3f, %+.3f]"
              % (n, d["share"], d["partner_share"], d["d_share"], d["d_share_ci"][0], d["d_share_ci"][1],
                 d["share_label"], d["d_pick"], d["d_pick_ci"][0], d["d_pick_ci"][1], d["pick_label"],
                 d["exploration_part"], d["exploration_ci"][0], d["exploration_ci"][1], d["selection_part"],
                 d["selection_ci"][0], d["selection_ci"][1]))
        print("      viable: list %.1f%% (%d), earlier %.1f%% (%d), own %.1f%% [%.1f, %.1f] (%d); own minus list, rounds "
              "matched %+.1f [%+.1f, %+.1f]"
              % (100 * v["list"]["rate"], v["list"]["names"], 100 * v["earlier list"]["rate"],
                 v["earlier list"]["names"], 100 * v["own"]["rate"], 100 * v["own"]["ci"][0], 100 * v["own"]["ci"][1],
                 v["own"]["names"], 100 * v["own_std_minus_list"]["diff"], 100 * v["own_std_minus_list"]["ci"][0],
                 100 * v["own_std_minus_list"]["ci"][1]))
    print("share label: %s (%s)" % (out["share_label_registered"], out["share_label_note"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
