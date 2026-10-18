#!/usr/bin/env python3
"""Compare the PhoQ round-1 percentile against nulls drawn from the anchor's own neighbourhood.

The anchor's neighbours are not a random sample of the pool, so a percentile below 0.5 can come from landscape
geometry alone. Two nulls are computed: random in-pool sequences at Hamming distance 1 from the anchor, and a
distance-matched null that draws random in-pool sequences at the same distance as each model proposal.

No API calls.
"""
import collections, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import landscape as L, rng as R

AA = "ACDEFGHIKLMNPQRSTVWY"


def hamming(a, b):
    return sum(1 for x, y in zip(a, b) if x != y)


def shell(pool, anchor, d):
    """Every in-pool sequence at exactly Hamming distance d from the anchor."""
    return [s for s in pool if hamming(s, anchor) == d]


def pct_of(sorted_vals, v):
    lo, hi = 0, len(sorted_vals)
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_vals[mid] < v:
            lo = mid + 1
        else:
            hi = mid
    return lo / len(sorted_vals)


def first_asks(path):
    rows = [json.loads(l) for l in open(path)]
    first = {}
    for r in rows:
        if r.get("kind") == "nomination" or r.get("round") != 1:
            continue
        k = (r["rung"], r["ratio"], r["campaign_seed"])
        if k not in first:
            first[k] = r
    return list(first.values())


def analyse(name, rows, ls, anchor, draws=4000):
    pool = ls.pool
    sorted_vals = sorted(ls.fitness[s] for s in pool)
    props = [s for r in rows for s in (r.get("parsed") or []) if s in pool and s != anchor]
    obs_pct = [pct_of(sorted_vals, ls.fitness[s]) for s in props]
    mean_obs = st.mean(obs_pct)
    se_obs = st.stdev(obs_pct) / math.sqrt(len(obs_pct)) if len(obs_pct) > 1 else float("nan")

    shells = {d: shell(pool, anchor, d) for d in (1, 2, 3, 4)}
    # Null 1: Hamming-distance-1 neighbours only.
    h1 = [pct_of(sorted_vals, ls.fitness[s]) for s in shells[1]]
    # Null 2: matched to the model's own proposal distances.
    dist_counts = collections.Counter(hamming(s, anchor) for s in props)
    matched, seedn = [], 0
    for d, cnt in sorted(dist_counts.items()):
        sh = shells[d]
        if not sh:
            continue
        per = max(1, int(draws * cnt / len(props)))
        for i in range(per):
            seedn += 1
            s = sh[R._u64("null", d, seedn) % len(sh)]
            matched.append(pct_of(sorted_vals, ls.fitness[s]))
    mean_h1 = st.mean(h1) if h1 else float("nan")
    se_h1 = st.stdev(h1) / math.sqrt(len(h1)) if len(h1) > 1 else float("nan")
    mean_m = st.mean(matched) if matched else float("nan")
    se_m = st.stdev(matched) / math.sqrt(len(matched)) if len(matched) > 1 else float("nan")

    def z(a, sa, b, sb):
        s = math.sqrt(sa ** 2 + sb ** 2)
        return ((a - b) / s if s else float("nan")), s

    z_h1, s_h1 = z(mean_obs, se_obs, mean_h1, se_h1)
    z_m, s_m = z(mean_obs, se_obs, mean_m, se_m)
    return dict(name=name, anchor=anchor, n_props=len(props),
                shell_sizes={d: len(v) for d, v in shells.items()},
                proposal_distances=dict(sorted(dist_counts.items())),
                mean_observed=mean_obs, se_observed=se_obs,
                mean_h1_null=mean_h1, se_h1_null=se_h1, n_h1=len(h1),
                mean_matched_null=mean_m, se_matched_null=se_m, n_matched=len(matched),
                z_vs_h1=z_h1, se_vs_h1=s_h1, z_vs_matched=z_m, se_vs_matched=s_m,
                z_vs_half=((mean_obs - 0.5) / se_obs if se_obs else float("nan")))


def main():
    gb1, ph = L.load("gb1"), L.load("phoq")
    out = [analyse("GB1", first_asks(os.path.join(ROOT, "results", "pilot_opus47_calls.jsonl")),
                   gb1, "VDGV"),
           analyse("PhoQ", [json.loads(l) for l in
                            open(os.path.join(ROOT, "results", "step6_phoq_round1_calls.jsonl"))],
                   ph, "AVST")]
    print("=" * 94)
    print("ROUND-1 FITNESS PERCENTILE AGAINST THE ANCHOR'S OWN NEIGHBOURHOOD")
    print("=" * 94)
    for d in out:
        print("\n%s, anchor %s   %d in-pool non-anchor proposals" % (d["name"], d["anchor"],
                                                                    d["n_props"]))
        print("  in-pool shell sizes by distance      %s" % d["shell_sizes"])
        print("  the model's own proposal distances   %s" % d["proposal_distances"])
        print("  model round-1 percentile             %.3f +- %.3f" % (d["mean_observed"],
                                                                       d["se_observed"]))
        print("  H1 null (all in-pool H1 neighbours)  %.3f +- %.3f   over %d sequences"
              % (d["mean_h1_null"], d["se_h1_null"], d["n_h1"]))
        print("  DISTANCE-MATCHED null                %.3f +- %.3f   over %d draws"
              % (d["mean_matched_null"], d["se_matched_null"], d["n_matched"]))
        print("  model vs H1 null                     %+.3f +- %.3f  (%.1f SE)"
              % (d["mean_observed"] - d["mean_h1_null"], d["se_vs_h1"], abs(d["z_vs_h1"])))
        print("  model vs DISTANCE-MATCHED null       %+.3f +- %.3f  (%.1f SE)"
              % (d["mean_observed"] - d["mean_matched_null"], d["se_vs_matched"],
                 abs(d["z_vs_matched"])))
        print("  (the old, wrong comparison vs 0.500  %.1f SE)" % abs(d["z_vs_half"]))

    g, p = out
    print("\n" + "=" * 94)
    print("WHAT THE RIGHT NULL DOES TO THE CLAIM")
    print("=" * 94)
    dg = g["mean_observed"] - g["mean_matched_null"]
    dp = p["mean_observed"] - p["mean_matched_null"]
    sd = math.sqrt(g["se_vs_matched"] ** 2 + p["se_vs_matched"] ** 2)
    print("  GB1  model minus matched null   %+.3f +- %.3f  (%.1f SE)"
          % (dg, g["se_vs_matched"], abs(g["z_vs_matched"])))
    print("  PhoQ model minus matched null   %+.3f +- %.3f  (%.1f SE)"
          % (dp, p["se_vs_matched"], abs(p["z_vs_matched"])))
    print("  difference of the two excesses  %+.3f +- %.3f  (%.1f SE)"
          % (dg - dp, sd, abs((dg - dp) / sd) if sd else float("nan")))
    print()
    print("  The excess over the anchor's OWN neighbourhood is what memory would produce, because")
    print("  geometry is held fixed inside each distance shell. PhoQ's raw 0.414 sitting below 0.5")
    print("  is geometry: AVST is a low-reading anchor, so its neighbours are expected low.")
    dest = os.path.join(ROOT, "results", "step6_anchor_neighbourhood_null.json")
    json.dump(out, open(dest, "w"), indent=1)
    print("\nsaved %s" % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
