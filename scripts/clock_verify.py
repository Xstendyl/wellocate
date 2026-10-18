#!/usr/bin/env python3
"""The clock regression on the n=20 logs, using the tiered parser and one crossing-round definition.

A crossing round is the first with replication fraction ">=50%". Since that fraction is a multiple of 1/S,
">50%" would mean a different threshold at each slot count. Each hypothesis predicts a slope of crossing
round on campaign length:
  absolute clock          0     the agent turns at a fixed round whatever the horizon
  pacing against budget   f     the agent turns at a fixed fraction of the horizon, so r = f * R;
                                f is estimated from the length-15 cell, which is the design's centre
  rounds remaining        1     the agent turns a fixed number of rounds from the end
"""
import glob, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import llm_policy as LP

AA = "ACDEFGHIKLMNPQRSTVWY"
LOGS = {10: "pilot_L10n20_calls.jsonl", 15: "pilot_L15n20_calls.jsonl",
        30: "pilot_L30n20_calls.jsonl"}
N5 = {10: "pilot_len10_calls.jsonl", 15: "pilot_len15_calls.jsonl", 30: "pilot_len30_calls.jsonl"}


def crossings(path, strict=False, reparse=True):
    """Per-campaign crossing round. `strict` selects ">50%"; the default is ">=50%"."""
    rows = [json.loads(l) for l in open(os.path.join(ROOT, "results", path))]
    camps = {}
    for r in rows:
        if r.get("kind") == "nomination":
            continue
        camps.setdefault(r["campaign_seed"], []).append(r)
    out = []
    for seed, calls in camps.items():
        seen, hit = set(), None
        for r in sorted(calls, key=lambda x: (x["round"], x.get("kind") != "round")):
            if reparse and (r.get("raw_response") or "").strip():
                got, _s, _n = LP.parse(r["raw_response"], r.get("n_slots") or 4, alphabet=AA)
                props = [g[0] for g in got][:(r.get("n_slots") or 4)]
            else:
                props = list(r.get("parsed") or [])
            if not props:
                continue
            f = sum(1 for s in props if s in seen) / len(props)
            if hit is None and (f > 0.5 if strict else f >= 0.5):
                hit = r["round"]
            seen.update(props)
        if hit is not None:
            out.append(hit)
    return out


def ols(xs, ys):
    n = len(xs)
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return float("nan"), float("nan")
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    s2 = sum(r * r for r in resid) / (n - 2) if n > 2 else float("nan")
    return b, math.sqrt(s2 / sxx)


def wls(xs, ys, ws):
    """Weighted least squares, weights 1/SE^2, with the SE from the known weights."""
    S = sum(ws)
    mx = sum(w * x for w, x in zip(ws, xs)) / S
    my = sum(w * y for w, y in zip(ws, ys)) / S
    sxx = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs))
    b = sum(w * (x - mx) * (y - my) for w, x, y in zip(ws, xs, ys)) / sxx
    return b, math.sqrt(1.0 / sxx)


def main():
    print("=" * 96)
    print("CROSSING ROUND UNDER BOTH DEFINITIONS, n=20 logs, tiered parser")
    print("=" * 96)
    print("  %-8s %6s | %-18s %-18s" % ("length", "n", ">=50% (KEEP)", ">50% (the old one)"))
    data = {}
    for L, f in sorted(LOGS.items()):
        inc = crossings(f, strict=False)
        exc = crossings(f, strict=True)
        data[L] = inc
        print("  %-8d %6d | %6.2f +- %-10.2f %6.2f +- %-10.2f"
              % (L, len(inc), st.mean(inc), st.stdev(inc) / math.sqrt(len(inc)),
                 st.mean(exc) if exc else float("nan"),
                 (st.stdev(exc) / math.sqrt(len(exc))) if len(exc) > 1 else float("nan")))
    print("\n  the n=5 logs, for the record, under the SAME >=50%% definition:")
    for L, f in sorted(N5.items()):
        inc = crossings(f, strict=False)
        exc = crossings(f, strict=True)
        print("    length %-3d n=%-3d  >=50%%: %5.2f    >50%%: %5.2f"
              % (L, len(inc), st.mean(inc) if inc else float("nan"),
                 st.mean(exc) if exc else float("nan")))

    xs = [L for L, v in data.items() for _ in v]
    ys = [y for L, v in data.items() for y in v]
    b, se = ols(xs, ys)
    print("\n" + "=" * 96)
    print("THE REGRESSION: crossing round on campaign length, over all %d campaigns" % len(xs))
    print("=" * 96)
    print("  slope %+.4f +- %.4f" % (b, se))
    f15 = st.mean(data[15]) / 15.0
    hyps = [("absolute clock", 0.0), ("pacing against the budget", f15), ("rounds remaining", 1.0)]
    print("\n  %-28s %10s %12s  %s" % ("hypothesis", "predicted", "distance", "verdict"))
    out = {}
    for name, pred in hyps:
        d = abs(b - pred) / se if se else float("nan")
        print("  %-28s %+10.3f %10.1f SE  %s"
              % (name, pred, d, "CONSISTENT" if d < 2 else "rejected"))
        out[name] = dict(predicted=pred, distance_se=d, rejected=bool(d >= 2))
    print("\n  the pacing fraction is estimated from the length-15 cell: %.2f / 15 = %.3f"
          % (st.mean(data[15]), f15))

    # The weighted three-point fit on cell means, reported beside the campaign-level OLS the paper quotes.
    Ls = sorted(data)
    means = [st.mean(data[L]) for L in Ls]
    ses = [st.stdev(data[L]) / math.sqrt(len(data[L])) for L in Ls]
    bw, sew = wls(Ls, means, [1.0 / e ** 2 for e in ses])
    bu, seu = ols(Ls, means)
    print("\n  %-40s %10s %10s | %9s %9s"
          % ("estimator", "slope", "SE", "pacing", "remaining"))
    for lbl, bb, ss in (("campaign-level OLS, 60 campaigns (QUOTED)", b, se),
                        ("WLS on 3 cell means, weights 1/SE^2", bw, sew),
                        ("OLS on 3 cell means, unweighted", bu, seu)):
        print("  %-40s %+10.4f %10.4f | %6.1f SE %6.1f SE"
              % (lbl, bb, ss, abs(bb - f15) / ss, abs(bb - 1.0) / ss))
    json.dump(dict(definition=">=50%", slope=b, se=se, n=len(xs),
                   estimator="campaign-level OLS",
                   wls_cell_means=dict(slope=bw, se=sew, n_cells=len(Ls)),
                   ols_cell_means=dict(slope=bu, se=seu, n_cells=len(Ls)),
                   cell_means={str(k): st.mean(v) for k, v in data.items()},
                   cell_ns={str(k): len(v) for k, v in data.items()},
                   pacing_fraction=f15, hypotheses=out),
              open(os.path.join(ROOT, "results", "step8_clock_verify.json"), "w"), indent=1)
    print("\nsaved results/step8_clock_verify.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
