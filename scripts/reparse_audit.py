#!/usr/bin/env python3
"""Re-parse the behavioural logs recorded with the old parser, using the tiered parser. No API calls.

The old parser accepted ":" and "-" as separators, so a model's analysis preamble, which lists variants already
measured, could be read as proposals and inflate the replication fraction as the history grows. The logs are the
GB1 pilot, the length experiment (10/15/30 rounds) and the slots experiment (2/4/8 slots).

Reported per experiment: the fraction of calls where the two parsers disagree on the proposal list, and the
replication fraction and crossing round (with standard errors) under each. Decision rule: if the crossing rounds
agree within their standard errors, the clock result stands; otherwise the length experiment is re-run on NK.
"""
import collections, glob, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import llm_policy as LP

AA = "ACDEFGHIKLMNPQRSTVWY"        # every re-parsed experiment ran on GB1, a protein landscape


def reparse(c):
    """The tiered parser on this call's logged raw output, with the landscape's own alphabet."""
    if not (c.get("raw_response") or "").strip():
        return list(c.get("parsed") or [])
    got, _status, _notes = LP.parse(c["raw_response"], c.get("n_slots") or 4, alphabet=AA)
    return [g[0] for g in got][:(c.get("n_slots") or 4)]


def per_campaign(rows, key="parsed"):
    """Replication fraction and crossing round per campaign, using `key` as the proposal list."""
    camps = collections.defaultdict(list)
    for r in rows:
        if r.get("kind") != "nomination":
            camps[r["campaign_seed"]].append(r)
    reps, cross = [], []
    for seed, calls in camps.items():
        seen, spent, rep, hit = set(), 0, 0, None
        for r in sorted(calls, key=lambda x: (x["round"], x.get("kind") != "round")):
            props = r[key]
            if not props:
                continue
            f = sum(1 for s in props if s in seen) / len(props)
            if hit is None and f >= 0.5:
                hit = r["round"]
            for s in props:
                spent += 1
                if s in seen:
                    rep += 1
                seen.add(s)
        if spent:
            reps.append(rep / spent)
        if hit is not None:
            cross.append(hit)
    return reps, cross


def mse(v):
    if not v:
        return float("nan"), float("nan"), 0
    return (st.mean(v), (st.stdev(v) / math.sqrt(len(v)) if len(v) > 1 else 0.0), len(v))


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "results", "pilot_*_calls.jsonl")))
    print("=" * 104)
    print("RE-PARSE AUDIT: every pre-fix behavioural log, old parser against tiered parser")
    print("=" * 104)
    print("  %-26s %6s %9s | %-17s %-17s | %-15s %-15s"
          % ("experiment", "calls", "disagree", "replication OLD", "replication NEW",
             "crossing OLD", "crossing NEW"))
    out, verdicts = {}, []
    for path in files:
        rows = [json.loads(l) for l in open(path)]
        calls = [r for r in rows if r.get("kind") != "nomination"]
        if not calls:
            continue
        dis = 0
        for r in rows:
            r["reparsed"] = reparse(r)
            if r.get("kind") != "nomination" and list(r.get("parsed") or []) != r["reparsed"]:
                dis += 1
        ro, co = per_campaign(rows, "parsed")
        rn, cn = per_campaign(rows, "reparsed")
        mo, so, no = mse(ro); mn, sn, nn = mse(rn)
        xo, xso, nxo = mse([float(x) for x in co]); xn, xsn, nxn = mse([float(x) for x in cn])
        name = os.path.basename(path).replace("pilot_", "").replace("_calls.jsonl", "")
        print("  %-26s %6d %8.0f%% | %6.1f%% +- %-6.1f %6.1f%% +- %-6.1f | %5.2f +- %-6.2f %5.2f +- %-6.2f"
              % (name, len(calls), 100.0 * dis / len(calls), 100 * mo, 100 * so, 100 * mn, 100 * sn,
                 xo, xso, xn, xsn))
        # The decision rule: do the crossing rounds agree within their standard errors?
        agree = None
        if nxo and nxn:
            pooled = math.sqrt(xso ** 2 + xsn ** 2)
            agree = (abs(xo - xn) <= max(pooled, 1e-9)) if pooled else (abs(xo - xn) < 1e-9)
            verdicts.append((name, xo, xn, abs(xo - xn), pooled, agree))
        out[name] = dict(calls=len(calls), disagree_frac=dis / len(calls),
                         rep_old=mo, rep_old_se=so, rep_new=mn, rep_new_se=sn,
                         cross_old=xo, cross_old_se=xso, n_cross_old=nxo,
                         cross_new=xn, cross_new_se=xsn, n_cross_new=nxn)

    print("\n" + "=" * 104)
    print("THE DECISION: do the crossing rounds hold within their standard errors?")
    print("=" * 104)
    print("  %-26s %8s %8s %9s %9s  %s" % ("experiment", "old", "new", "|diff|", "pooled SE",
                                           "verdict"))
    for name, xo, xn, d, p, ok in verdicts:
        print("  %-26s %8.2f %8.2f %9.2f %9.2f  %s"
              % (name, xo, xn, d, p, "holds" if ok else "MOVES beyond its SE"))
    bad = [v for v in verdicts if not v[-1]]
    print()
    if not bad:
        print("  ALL crossing rounds hold within their standard errors, so the clock result STANDS and")
        print("  the preamble bug did not move it. The replication FRACTIONS may still shift, and the")
        print("  new values are the ones to quote.")
    else:
        print("  %d experiment(s) MOVE beyond their standard error: %s."
              % (len(bad), ", ".join(v[0] for v in bad)))
        print("  The clock result does NOT survive the correction, and the length experiment is re-run")
        print("  on NK before any turn-counter claim is made.")
    dest = os.path.join(ROOT, "results", "step8_reparse_audit.json")
    json.dump(dict(experiments=out, verdicts=[
        dict(name=n, cross_old=a, cross_new=b, diff=d, pooled_se=p, holds=bool(k))
        for n, a, b, d, p, k in verdicts], all_hold=not bad), open(dest, "w"), indent=1)
    print("\nsaved %s" % dest)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
