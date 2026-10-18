#!/usr/bin/env python3
"""Recompute every number quoted in the results draft from the analysis outputs, failing on a mismatch.

Each figure is recomputed from `results/analysis_final/` and `results/fair_reference_curve.json` and searched
for in the draft with its own formatting, after normalising whitespace. A missing figure is reported by name.

Usage: python3 scripts/verify_results_draft.py   (exit 1 on any mismatch)
"""
import json, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "spec", "PAPER_RESULTS.md")


def main():
    if not os.path.exists(DRAFT):
        print("no draft at %s" % os.path.relpath(DRAFT, ROOT))
        return 0
    text = " ".join(open(DRAFT).read().split())
    g = json.load(open(os.path.join(ROOT, "results", "analysis_final", "grid", "summary.json")))
    z = json.load(open(os.path.join(ROOT, "results", "analysis_final", "zeronoise",
                                    "table2c_central_test.json")))["rows"]
    f = json.load(open(os.path.join(ROOT, "results", "fair_reference_curve.json")))["curves"]
    c = g["cells_detail"]
    lv = [r["panel_level"] for r in z]
    df = [r["diff"] for r in z]
    rep = [100 * x["replication"]["over slots used"] for x in c]
    rep2 = [100 * x["replication"]["excl anchor, slots used"] for x in c]
    dis = [x["distinct"] for x in c]
    mean = [x["mean"] for x in c]
    ex = [x["exploration_shortfall"] for x in c]
    se = [x["selection_shortfall"] for x in c]
    fk0, fks = f["fair"]["0"]["mean"], f["fair"]["1"]["mean"]
    pk0, pks = f["pool"]["0"]["mean"], f["pool"]["1"]["mean"]

    claims = [
        ("replication share, over slots used", "%.1f%% to %.1f%%" % (min(rep), max(rep))),
        ("replication share, excluding the anchor", "%.1f%% to %.1f%%" % (min(rep2), max(rep2))),
        ("distinct variants per campaign", "%.2f to %.2f" % (min(dis), max(dis))),
        ("fair reference distinct at k*", "%.2f" % f["fair"]["1"]["distinct"]),
        ("pool-scope reference distinct at k*", "%.2f" % f["pool"]["1"]["distinct"]),
        ("most exploratory cell as a share of the fair reference",
         "%.1f%%" % (100 * max(dis) / f["fair"]["1"]["distinct"])),
        ("cell means on the primary outcome", "%.4f to %.4f" % (min(mean), max(mean))),
        ("fair k*", "%.4f" % fks), ("pool-scope k*", "%.4f" % pks),
        ("fair k=0", "%.4f" % fk0), ("pool-scope k=0", "%.4f" % pk0),
        ("cells above fair k=0", "%d of 15" % sum(1 for x in c if x["mean"] > fk0)),
        ("cells above pool-scope k=0", "%d of 15" % sum(1 for x in c if x["mean"] > pk0)),
        ("exploration shortfall", "%.4f to %.4f" % (min(ex), max(ex))),
        ("selection shortfall", "%.4f to %.4f" % (min(se), max(se))),
        ("selection as a share of the total",
         "%.1f%% to %.1f%%" % (100 * min(s / (e + s) for e, s in zip(ex, se)),
                               100 * max(s / (e + s) for e, s in zip(ex, se)))),
        ("zero-noise level range", "%.4f" % min(lv)), ("zero-noise level top", "%.4f" % max(lv)),
        ("zero-noise median level", "%.4f" % st.median(lv)),
        ("zero-noise paired difference, smallest", "%.4f" % max(df)),
        ("zero-noise paired difference, largest", "%.4f" % min(df)),
        ("zero-noise cells rejecting after Holm",
         "%d of 15" % open(os.path.join(ROOT, "results", "analysis_final", "zeronoise",
                                        "table2c_central_test.txt")).read().count(" YES")),
    ]
    bad = []
    print("=" * 96)
    print("RESULTS DRAFT: every quoted figure, recomputed")
    print("=" * 96)
    for label, want in claims:
        # The draft bolds figures, so the search ignores asterisks as well as wrapping.
        hay = text.replace("**", "")
        ok = want.replace("**", "") in hay
        print("  %-54s %-22s %s" % (label, want, "present" if ok else "ABSENT"))
        if not ok:
            bad.append((label, want))
    print("=" * 96)
    if bad:
        print("%d figure(s) in the draft do not match the outputs, or are missing:" % len(bad))
        for label, want in bad:
            print("  %s: expected %r" % (label, want))
        return 1
    print("  all %d figures present and equal to the recomputed value" % len(claims))
    return 0


if __name__ == "__main__":
    sys.exit(main())
