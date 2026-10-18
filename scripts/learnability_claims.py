#!/usr/bin/env python3
"""Recompute each claim of the learnability appendix from a run file and its rescored file, old against new.

  OLD  the files as first published, from the policy that drew neighbours from the amino acids;
  NEW  the files in results/ now, rerun with neighbours over the landscape's own letters.

Usage: python3 scripts/learnability_claims.py      (writes results/learnability_claims.json and .txt)
"""
import collections, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_COMMIT = "e325069"
OUT = os.path.join(ROOT, "results", "learnability_claims")


def old(p):
    return json.loads(subprocess.run(["git", "show", "%s:results/%s" % (OLD_COMMIT, p)], cwd=ROOT,
                                     capture_output=True, check=True).stdout)


def new(p):
    return json.load(open(os.path.join(ROOT, "results", p)))


def claims(run, res):
    s, cells = run["settings"], res["cells"]
    learned = {sc: (run["part2"][sc]["trained_k"], run["part2"][sc]["trained_selector"]) for sc in run["part2"]}
    best_or_tied = sum(1 for x in s if int(x["kstar"]) == learned[x["scope"]][0]
                       or (int(x["runner_up"]) == learned[x["scope"]][0] and x["gap_is_a_tie"]))
    k2 = [x for x in s if int(x["kstar"]) == 2]
    raw = [c["raw"]["C k* shrinkage"] - c["raw"]["D k=0 shrinkage"] for c in cells]
    # A NaN score (held-out span zero or negative) is undefined, so ranges use defined scores only and
    # undefined cells are counted separately.
    ok = lambda x: x == x
    lt = [c["norm_training"]["LEARNED"] for c in cells if ok(c["norm_training"]["LEARNED"])]
    lh = [c["norm_heldout"]["LEARNED"] for c in cells if ok(c["norm_heldout"]["LEARNED"])]
    undefined = [c for c in cells if not ok(c["norm_heldout"]["LEARNED"])]
    exact = [c for c in cells if ok(c["norm_heldout"]["LEARNED"]) and abs(c["norm_heldout"]["LEARNED"] - 1.0) < 1e-12]
    other = [c["norm_heldout"]["LEARNED"] for c in cells
             if int(c["kstar"]) != 1 and ok(c["norm_heldout"]["LEARNED"])]
    coll = sorted({(x["sweep"]["4"]["collapsed"], x["sweep"]["3"]["collapsed"]) for x in s
                   if int(x["K"]) == 3 and x["scope"] == "fair"})
    return collections.OrderedDict([
        ("learner's choice, per scope", {sc: "k=%d %s" % v for sc, v in sorted(learned.items())}),
        ("settings where the learner's k is k* or tied with it, of 18", best_or_tied),
        ("settings with k* = 1", sum(1 for x in s if int(x["kstar"]) == 1)),
        ("settings with k* = 2", len(k2)),
        ("settings with k* = 2 at double noise", sum(1 for x in k2 if float(x["cv_mult"]) == 2.0)),
        ("settings with k* = 2 within two SEs (ties)", sum(1 for x in k2 if x["gap_is_a_tie"])),
        ("gaps to the runner-up inside two SEs, of 18", sum(1 for x in s if x["gap_is_a_tie"])),
        ("raw paired difference, k* shrinkage minus never-replicate, held out", [min(raw), max(raw)]),
        ("learned score, training endpoints", [min(lt), max(lt)]),
        ("learned score, held-out endpoints", [min(lh), max(lh)]),
        ("cells scoring exactly 1.000 held out", len(exact)),
        ("cells whose held-out score is undefined (held-out span zero or negative)",
         ["K=%s cv=%s %s k*=%s" % (c["K"], c["cv"], c["scope"], c["kstar"]) for c in undefined]),
        ("k* = 1 cells scoring exactly 1.000", sum(1 for c in exact if int(c["kstar"]) == 1)),
        ("settings with k* = 0", sum(1 for x in s if int(x["kstar"]) == 0)),
        ("learned score held out where k* is not 1 (defined cells)", [min(other), max(other)] if other else None),
        ("collapses at K=3, guessing policy: (k=4, k=3) of n", coll),
        ("n per cell", run["n_per_cell"]),
    ])


def fmt(v):
    if isinstance(v, float):
        return "%.4f" % v
    if isinstance(v, list) and v and all(isinstance(x, float) for x in v):
        return "%.4f to %.4f" % tuple(v)
    return str(v)


def main():
    out, lines = {}, []
    for n in (200, 1500):
        a = claims(old("learnability_fresh_n%d.json" % n), old("learnability_fresh_n%d_rescored.json" % n))
        b = claims(new("learnability_fresh_n%d.json" % n), new("learnability_fresh_n%d_rescored.json" % n))
        out[str(n)] = [dict(claim=k, old=a[k], new=b[k], changed=(a[k] != b[k])) for k in a]
        lines.append("=" * 110)
        lines.append("learnability, %d landscapes per cell" % n)
        lines.append("=" * 110)
        for r in out[str(n)]:
            lines.append("%s %-62s old %-26s new %s" % ("*" if r["changed"] else " ", r["claim"], fmt(r["old"]),
                                                       fmt(r["new"])))
    json.dump(out, open(OUT + ".json", "w"), indent=1, default=str)
    open(OUT + ".txt", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("\n* marks a claim whose value changed. Wrote %s.json and .txt" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
