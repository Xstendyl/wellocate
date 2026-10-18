#!/usr/bin/env python3
"""Reference for the risk-free run: the guessing scripted policy under the risk-free rejection rule.

Simulation only, no model calls. The guessing policy (FairGreedyAlphabet, k = 0 to 4) runs on the fair reference
curve's 1,500 seeds and settings twice: under the grid's rule (three replacement asks, then the slot is lost),
which must reproduce results/reference_curve_alphabet.json exactly, and under
campaign.run(riskfree_rejection=True). For each k it reports the mean final pick, the replication share
(replication_count / slots_used), distinct candidates, rejections, lost slots and cap hits; k* is the k with
the best mean.

Usage: python3 scripts/riskfree_reference.py      (writes results/riskfree_reference_alphabet.json)
"""
import json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from repdef import campaign as C                                  # noqa: E402
import fair_reference_curve as FRC                                # noqa: E402

OUT = os.path.join(ROOT, "results", "riskfree_reference_alphabet.json")


def curve(fit, pool, ps, space, anchor, riskfree):
    out = {}
    for k in FRC.KS:
        nom, share, dis, rej, lost, caps, dead = [], [], [], [], [], [], 0
        for i in range(FRC.N):
            pol = FRC.FairGreedyAlphabet(k, anchor, space, seed=0)
            try:
                r = C.run(fit, pool, pol, 0.0, FRC.SEED0 + i, 0.15, pool_sorted=ps,
                          nomination="shrinkage", prior="empirical", noise_model="multiplicative",
                          cv=FRC.CV, noise_floor=FRC.FLOOR, riskfree_rejection=riskfree)
            except C.UnusableSigma:
                dead += 1
                continue
            nom.append(r.nominated_true)
            share.append(100.0 * r.replication_count / r.slots_used if r.slots_used else 0.0)
            dis.append(len({h.seq for h in r.history if h.outcome == "ok"}))
            rej.append(sum(1 for h in r.history if h.outcome == "rejected"))
            lost.append(sum(1 for h in r.history if h.outcome == "abandoned"))
            caps.append(r.rejection_cap_hits)
        m = lambda v: st.mean(v) if v else float("nan")
        out[k] = dict(n=len(nom), collapsed=dead, mean=m(nom),
                      se=(st.stdev(nom) / len(nom) ** 0.5 if len(nom) > 1 else float("nan")),
                      replication_share=m(share), distinct=m(dis), rejections=m(rej), lost=m(lost),
                      cap_hits_total=sum(caps), campaigns_hitting_cap=sum(1 for c in caps if c))
    kstar = max((k for k in FRC.KS if out[k]["n"] > 1), key=lambda k: out[k]["mean"])
    return out, kstar


def main():
    fit, pool = FRC.landscape()
    ps, space = tuple(sorted(pool)), tuple(sorted(fit))
    anchor = FRC.anchor_of(fit, pool)
    old, old_k = curve(fit, pool, ps, space, anchor, riskfree=False)
    committed = json.load(open(FRC.CORRECTED))["curves"]["fair"]
    bad = [k for k in FRC.KS if abs(old[k]["mean"] - committed[str(k)]["mean"]) > 1e-12
           or old[k]["n"] != committed[str(k)]["n"]]
    if bad:
        raise SystemExit("REFUSED: the old-rule rerun does not reproduce reference_curve_alphabet.json at k=%s" % bad)
    new, new_k = curve(fit, pool, ps, space, anchor, riskfree=True)
    for label, res, ks in (("grid rule (reproduces the committed curve)", old, old_k),
                           ("risk-free rule", new, new_k)):
        print("\n  %s, n=%d per k, k* = %d" % (label, FRC.N, ks))
        print("  %3s %8s %7s %9s %9s %11s %6s %9s %8s" % ("k", "mean", "SE", "share %", "distinct",
                                                         "rejections", "lost", "cap hits", "collapsed"))
        for k in FRC.KS:
            d = res[k]
            print("  %3d %8.4f %7.4f %9.2f %9.2f %11.2f %6.2f %9d %8d" % (
                k, d["mean"], d["se"], d["replication_share"], d["distinct"], d["rejections"], d["lost"],
                d["cap_hits_total"], d["collapsed"]))
    json.dump(dict(n=FRC.N, seed0=FRC.SEED0, anchor=anchor, cap=C.RISKFREE_CAP,
                   grid_rule=dict(curve=old, kstar=old_k), riskfree=dict(curve=new, kstar=new_k)),
              open(OUT, "w"), indent=1)
    print("\n  risk-free k* = %d: mean %.4f, replication share %.2f%%; Panel B's 'twice' line is %.2f%%"
          % (new_k, new[new_k]["mean"], new[new_k]["replication_share"], 2 * new[new_k]["replication_share"]))
    print("  wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
