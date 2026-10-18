#!/usr/bin/env python3
"""Split each tool arm's change in final pick into exploration and selection parts, and describe how it explores.

Per arm (ledger, menu, structure) and model, paired by seed with the concurrent control: the pick change as the
change in best true value measured minus the change in (best measured - nominated), with 95% percentile bootstraps
over pairs; readings of the nominated candidate and the share of nominations that were the agent's highest mean;
distinct candidates measured and rejections per new name. Descriptive only.

Usage: python3 scripts/decompose_0an.py      (writes results/decompose_0an.json)
"""
import collections, json, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_0al as A0L                                                # noqa: E402
import analyse_0an as A                                                  # noqa: E402
import analyse_grid as AG                                                # noqa: E402

OUT = os.path.join(ROOT, "results", "decompose_0an.json")
ROW = re.compile(r"^\s*\d+\s+([A-Z]{4})\s+(-?\d+\.\d+)\s*$", re.M)


def readings_of_nominated(tag):
    """(model, seed) -> readings of the nominated candidate, from the nomination prompt's per-reading history."""
    out = {}
    for c in A0L.calls(tag):
        # Blind only: the Opus control tag also holds Mechanism campaigns on the same seeds.
        if c.get("kind") != "nomination" or (c.get("cell") or "Blind") != "Blind":
            continue
        p = c.get("prompt") or ""
        hist = p.split("HISTORY", 1)[1] if "HISTORY" in p else ""
        n = collections.Counter(seq for seq, _v in ROW.findall(hist))
        nom = (c.get("parsed") or [None])[0] if isinstance(c.get("parsed"), list) else c.get("parsed")
        out[(c["model"], c["campaign_seed"])] = (n, nom)
    return out


def rej_per_new_name(rows):
    rej = sum(r["n_rejected"] for r in rows)
    new = rej + sum(r["n_distinct_measured"] for r in rows) - sum(1 for r in rows if r["anchor_orders"] > 0)
    return 100.0 * rej / new if new else float("nan")


def ci(v, tag):
    return list(AG.boot_ci(v, tag=tag))


def main():
    a0, _ = AG.drop_fallbacks(AG.load(A.A0_TAG), AG.fallback_seeds([A.A0_TAG]))
    control = {(r["model"], r["seed"]): r for r in a0 if r["condition"] == "Blind" and "opus" in r["model"]}
    f0, _ = A.load_arm(A.CONTROL_TAG, None)
    control.update({(r["model"], r["seed"]): r for r in f0 if "opus" not in r["model"]})
    reads = readings_of_nominated(A.A0_TAG)
    reads.update(readings_of_nominated(A.CONTROL_TAG))
    out = {}
    for arm, (tag, option) in A.ARMS.items():
        rows, _n = A.load_arm(tag, option)
        reads_arm = readings_of_nominated(tag)
        for m, short in A.MODELS.items():
            pr = [(r, control[(m, r["seed"])]) for r in rows if r["model"] == m and (m, r["seed"]) in control]
            if not pr:
                continue
            t = "0an-decompose|%s|%s" % (arm, short)
            d_pick = [x["nominated_true"] - y["nominated_true"] for x, y in pr]
            d_best = [x["best_true_measured"] - y["best_true_measured"] for x, y in pr]
            d_sel = [(x["best_true_measured"] - x["nominated_true"]) - (y["best_true_measured"] - y["nominated_true"])
                     for x, y in pr]

            def nom_reads(rd, r):
                n, nom = rd.get((r["model"], r["seed"]), (collections.Counter(), None))
                return n.get(r["nominated"], 0)
            ra = [nom_reads(reads_arm, x) for x, _y in pr]
            rc = [nom_reads(reads, y) for _x, y in pr]
            out["%s|%s" % (arm, short)] = dict(
                pairs=len(pr), d_pick=st.mean(d_pick), d_pick_ci=ci(d_pick, t + "|pick"),
                exploration_part=st.mean(d_best), exploration_ci=ci(d_best, t + "|best"),
                selection_part=st.mean(d_sel), selection_ci=ci(d_sel, t + "|sel"),
                best_measured=st.mean(x["best_true_measured"] for x, _y in pr),
                control_best_measured=st.mean(y["best_true_measured"] for _x, y in pr),
                pick=st.mean(x["nominated_true"] for x, _y in pr),
                control_pick=st.mean(y["nominated_true"] for _x, y in pr),
                nominated_readings=st.mean(ra), control_nominated_readings=st.mean(rc),
                nominated_one_reading=sum(1 for v in ra if v == 1) / len(ra),
                control_nominated_one_reading=sum(1 for v in rc if v == 1) / len(rc),
                chose_highest_mean=st.mean(1.0 if x.get("agent_chose_mean") else 0.0 for x, _y in pr),
                control_chose_highest_mean=st.mean(1.0 if y.get("agent_chose_mean") else 0.0 for _x, y in pr),
                distinct=st.mean(x["n_distinct_measured"] for x, _y in pr),
                control_distinct=st.mean(y["n_distinct_measured"] for _x, y in pr),
                rejections_per_new_name=rej_per_new_name([x for x, _y in pr]),
                control_rejections_per_new_name=rej_per_new_name([y for _x, y in pr]))
    json.dump(out, open(OUT, "w"), indent=1)
    for k, d in out.items():
        print("%-22s n=%3d pick %+.3f [%+.3f, %+.3f] = exploration %+.3f [%+.3f, %+.3f] - selection %+.3f [%+.3f, %+.3f]"
              % (k, d["pairs"], d["d_pick"], d["d_pick_ci"][0], d["d_pick_ci"][1], d["exploration_part"],
                 d["exploration_ci"][0], d["exploration_ci"][1], d["selection_part"], d["selection_ci"][0],
                 d["selection_ci"][1]))
        print("%-22s       nominated readings %.2f (control %.2f), one reading %.0f%% (%.0f%%), highest mean %.0f%% "
              "(%.0f%%) | distinct %.1f (%.1f) | rejected per new name %.1f%% (%.1f%%)"
              % ("", d["nominated_readings"], d["control_nominated_readings"], 100 * d["nominated_one_reading"],
                 100 * d["control_nominated_one_reading"], 100 * d["chose_highest_mean"],
                 100 * d["control_chose_highest_mean"], d["distinct"], d["control_distinct"],
                 d["rejections_per_new_name"], d["control_rejections_per_new_name"]))
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
