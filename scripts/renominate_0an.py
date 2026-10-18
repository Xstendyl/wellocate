#!/usr/bin/env python3
"""Re-nominate each tool-arm campaign's final pick by simple rules: would the arm's exploration give better picks?

Each campaign's final pick is re-nominated from the agent's own measured readings by three rules:
  (a) highest mean         the harness's own ref_mean, computed on the campaign's readings;
  (b) shrinkage            the harness's own ref_shrinkage: the empirical-Bayes posterior-mean rule the scripted
                           references use, with the same prior and noise model;
  (c) highest mean, n >= 2 the highest mean among candidates with at least two readings, from the nomination
                           prompt's per-reading history; with no such candidate, the highest mean (counted).
The true value of each pick comes from the landscape. Per arm (ledger, menu, structure) and model, it gives the
paired change against the control re-nominated the same way, with a 95% percentile bootstrap over pairs, and the
agent's own pick beside it. Rule (a) from the parsed history must agree with ref_mean.

Usage: python3 scripts/renominate_0an.py [--with-topup]      (writes results/renominate_0an.json)
"""
import collections, json, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_0al as A0L                                                # noqa: E402
import analyse_0an as A                                                  # noqa: E402
import analyse_grid as AG                                                # noqa: E402
import grid                                                              # noqa: E402

ROW = re.compile(r"^\s*\d+\s+([A-Z]{4})\s+(-?\d+\.\d+)\s*$", re.M)
RULES = ("agent", "highest mean", "shrinkage", "highest mean, n >= 2")


def histories(tag):
    out = {}
    for c in A0L.calls(tag):
        # Blind only: the Opus control tag also holds Mechanism campaigns on the same seeds.
        if c.get("kind") == "nomination" and (c.get("cell") or "Blind") == "Blind":
            p = c.get("prompt") or ""
            v = collections.defaultdict(list)
            for s, x in ROW.findall(p.split("HISTORY", 1)[1] if "HISTORY" in p else ""):
                v[s].append(float(x))
            out[(c["model"], c["campaign_seed"])] = v
    return out


def picks(r, hist, fit, stats):
    v = hist.get((r["model"], r["seed"]), {})
    mean = lambda s: sum(v[s]) / len(v[s])
    hm = max(v, key=mean) if v else None
    two = [s for s in v if len(v[s]) >= 2]
    if two:
        hm2 = max(two, key=mean)
    else:
        hm2 = hm
        stats["no candidate with 2 readings"] += 1
    stats["parsed highest mean agrees with ref_mean"] += 1 if hm == r["ref_mean"] else 0
    stats["campaigns"] += 1
    return {"agent": fit[r["nominated"]], "highest mean": fit[r["ref_mean"]], "shrinkage": fit[r["ref_shrinkage"]],
            "highest mean, n >= 2": fit[hm2] if hm2 else float("nan")}


def main():
    fit, _pool = grid.landscape()
    a0, _ = AG.drop_fallbacks(AG.load(A.A0_TAG), AG.fallback_seeds([A.A0_TAG]))
    control = {(r["model"], r["seed"]): r for r in a0 if r["condition"] == "Blind" and "opus" in r["model"]}
    f0, _ = A.load_arm(A.CONTROL_TAG, None)
    control.update({(r["model"], r["seed"]): r for r in f0 if "opus" not in r["model"]})
    hist = histories(A.A0_TAG)
    hist.update(histories(A.CONTROL_TAG))
    stats = collections.Counter()
    out = {}
    for arm, (tag, option) in A.ARMS.items():
        rows, _n = A.load_arm(tag, option)
        harm = histories(tag)
        for m, short in A.MODELS.items():
            pr = [(r, control[(m, r["seed"])]) for r in rows if r["model"] == m and (m, r["seed"]) in control]
            if not pr:
                continue
            pa = [(picks(x, harm, fit, stats), picks(y, hist, fit, stats)) for x, y in pr]
            cell = {"pairs": len(pr)}
            for rule in RULES:
                d = [x[rule] - y[rule] for x, y in pa]
                cell[rule] = dict(arm=st.mean(x[rule] for x, _y in pa), control=st.mean(y[rule] for _x, y in pa),
                                  d=st.mean(d), ci=list(AG.boot_ci(d, tag="0an-renom|%s|%s|%s" % (arm, short, rule))))
            out["%s|%s" % (arm, short)] = cell
    out["_checks"] = dict(stats)
    json.dump(out, open(os.path.join(ROOT, "results", "renominate_0an.json"), "w"), indent=1)
    print("checks: %s" % dict(stats))
    print("%-22s %4s  %-26s %-26s %-26s %-26s" % ("arm|model", "n", *RULES))
    for k, c in out.items():
        if k.startswith("_"):
            continue
        print("%-22s %4d  " % (k, c["pairs"]) + "  ".join("%+.3f [%+.3f, %+.3f]   " % (c[r]["d"], c[r]["ci"][0], c[r]["ci"][1])
                                                     for r in RULES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
