#!/usr/bin/env python3
"""Round-1 diagnostics for prior knowledge (contamination) of a landscape, from the same round-1 proposals.

  1. Hamming distance from the reference: a searching model proposes neighbours, a retrieving model
     proposes distant sequences it knows are good. Needs no knowledge of the optimum.
  2. Fitness percentile of in-pool proposals against the pool's distribution (0.5 under chance).
  3. Clopper-Pearson upper bound on the rate of naming the optimum.
"""
import collections, json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import landscape as L


def hamming(a, b):
    return sum(1 for x, y in zip(a, b) if x != y)


def beta_upper(k, n, conf=0.95):
    """Exact one-sided Clopper-Pearson upper bound, by bisection on the binomial tail.

    P(X <= k | p) = conf. The binomial tail is summed directly, without scipy.
    """
    def tail(p):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if tail(mid) > 1 - conf:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def percentile_of(ls, seq, sorted_vals):
    v = ls.fitness[seq]
    lo, hi = 0, len(sorted_vals)
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_vals[mid] < v:
            lo = mid + 1
        else:
            hi = mid
    return lo / len(sorted_vals)


def first_asks(path, slots=4):
    rows = [json.loads(l) for l in open(path)]
    first = {}
    for r in rows:
        if r.get("kind") == "nomination" or r.get("round") != 1:
            continue
        k = (r["rung"], r["ratio"], r["campaign_seed"])
        if k not in first:
            first[k] = r
    return list(first.values())


def analyse(name, rows, ls, parent, argmax):
    pool = ls.pool
    sorted_vals = sorted(ls.fitness[s] for s in pool)
    props = [s for r in rows for s in (r.get("parsed") or [])]
    inpool = [s for s in props if s in pool]
    n_camp = len(rows)
    hits = sum(1 for r in rows if argmax in (r.get("parsed") or []))

    # 1. Hamming. Exclude the reference itself, which every campaign proposes and which carries no
    #    information about search versus retrieval.
    d = [hamming(s, parent) for s in props if s != parent]
    dist = collections.Counter(d)
    far = sum(1 for x in d if x >= 3)

    # 2. Fitness percentile of in-pool proposals. Under pure chance this averages 0.5.
    pcts = [percentile_of(ls, s, sorted_vals) for s in inpool]
    mean_pct = sum(pcts) / len(pcts) if pcts else float("nan")
    # SE of a mean of percentiles, which under the null has variance 1/12.
    se_pct = math.sqrt((1.0 / 12) / len(pcts)) if pcts else float("nan")

    # 3. Upper bound on the argmax rate.
    chance = 4.0 / len(pool)
    ub = beta_upper(hits, n_camp)
    return dict(name=name, n_camp=n_camp, n_prop=len(props), n_inpool=len(inpool),
                hits=hits, rate=hits / n_camp, chance=chance,
                enrichment=(hits / n_camp) / chance,
                rate_upper95=ub, enrichment_upper95=ub / chance,
                hamming=dict(sorted(dist.items())), n_nonparent=len(d),
                mean_hamming=sum(d) / len(d) if d else float("nan"),
                frac_distance_ge3=far / len(d) if d else float("nan"),
                mean_fitness_percentile=mean_pct, se_fitness_percentile=se_pct,
                z_percentile=((mean_pct - 0.5) / se_pct) if pcts else float("nan"))


def main():
    gb1, phoq = L.load("gb1"), L.load("phoq")
    cases = [
        ("GB1  (VDGV -> FWAA)", first_asks(os.path.join(ROOT, "results", "pilot_opus47_calls.jsonl")),
         gb1, "VDGV", "FWAA"),
        ("PhoQ (AVST -> TEMH)", [json.loads(l) for l in
                                 open(os.path.join(ROOT, "results", "step6_phoq_round1_calls.jsonl"))],
         phoq, "AVST", "TEMH"),
    ]
    out = [analyse(n, r, l, p, a) for n, r, l, p, a in cases]

    print("=" * 92)
    print("ROUND-1 PRIOR DIAGNOSTICS, same model, same temperature, same one-ask rule")
    print("=" * 92)
    for d in out:
        print("\n%s   %d campaigns, %d proposals, %d in pool"
              % (d["name"], d["n_camp"], d["n_prop"], d["n_inpool"]))
        print("  names the global optimum      %d of %d = %.1f%%   enrichment %.1fx"
              % (d["hits"], d["n_camp"], 100 * d["rate"], d["enrichment"]))
        print("  95%% upper bound on that rate  %.1f%%                  enrichment <= %.0fx"
              % (100 * d["rate_upper95"], d["enrichment_upper95"]))
        print("  Hamming from the reference    %s" % d["hamming"])
        print("    mean %.2f over %d non-reference proposals, %.0f%% at distance >= 3"
              % (d["mean_hamming"], d["n_nonparent"], 100 * d["frac_distance_ge3"]))
        print("  mean fitness percentile       %.3f +- %.3f   (chance 0.500, z = %+.1f)"
              % (d["mean_fitness_percentile"], d["se_fitness_percentile"], d["z_percentile"]))

    g, p = out
    # Every comparison below reports the difference and its standard error.
    def two_prop(k1, n1, k2, n2):
        p1, p2 = k1 / n1, k2 / n2
        pp = (k1 + k2) / (n1 + n2)
        se = math.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2))
        return p1 - p2, se, (p1 - p2) / se if se else float("nan")

    d_far, se_far, z_far = two_prop(g["hamming"].get(4, 0), g["n_nonparent"],
                                   p["hamming"].get(4, 0), p["n_nonparent"])
    d_ge3, se_ge3, z_ge3 = two_prop(sum(v for k, v in g["hamming"].items() if k >= 3), g["n_nonparent"],
                                    sum(v for k, v in p["hamming"].items() if k >= 3), p["n_nonparent"])
    d_pct = g["mean_fitness_percentile"] - p["mean_fitness_percentile"]
    se_pct = math.sqrt(g["se_fitness_percentile"] ** 2 + p["se_fitness_percentile"] ** 2)
    d_ham = g["mean_hamming"] - p["mean_hamming"]

    print("\n" + "=" * 92)
    print("THE CONTRAST, each difference with its standard error")
    print("=" * 92)
    print("names the global optimum           GB1 %.0f%%     PhoQ %.0f%%     DECISIVE"
          % (100 * g["rate"], 100 * p["rate"]))
    print("mean fitness percentile            GB1 %.3f   PhoQ %.3f   diff %+.3f +- %.3f  (%.1f SE)"
          % (g["mean_fitness_percentile"], p["mean_fitness_percentile"], d_pct, se_pct,
             abs(d_pct / se_pct)))
    print("proposals at distance 4            GB1 %.0f%%     PhoQ %.0f%%     diff %+.3f +- %.3f  (%.1f SE)"
          % (100 * g["hamming"].get(4, 0) / g["n_nonparent"],
             100 * p["hamming"].get(4, 0) / p["n_nonparent"], d_far, se_far, abs(z_far)))
    print("proposals at distance >= 3         GB1 %.0f%%     PhoQ %.0f%%     diff %+.3f +- %.3f  (%.1f SE)"
          % (100 * g["frac_distance_ge3"], 100 * p["frac_distance_ge3"], d_ge3, se_ge3, abs(z_ge3)))
    print("MEAN Hamming distance              GB1 %.2f    PhoQ %.2f    diff %+.2f           NOT A SEPARATOR"
          % (g["mean_hamming"], p["mean_hamming"], d_ham))
    print()
    print("WHAT SURVIVES. The fitness percentile separates the two landscapes at %.1f SE, and the"
          % abs(d_pct / se_pct))
    print("argmax indicator separates them outright. The MEAN Hamming distance does not separate")
    print("them at all, %.2f against %.2f, so any account resting on \"it searches further afield\""
          % (g["mean_hamming"], p["mean_hamming"]))
    print("is unavailable. What differs is the SHAPE: GB1's distances are bimodal, %s,"
          % dict(g["hamming"]))
    print("a spike on single mutants of the reference plus a second spike four mutations away, with")
    print("almost nothing between. PhoQ's decay monotonically, %s. A jump straight to"
          % dict(p["hamming"]))
    print("distance 4 is not a step in a search. At %.1f SE the shape difference is SUGGESTIVE and"
          % abs(z_far))
    print("not significant at 5%, so it is a mechanism consistent with the percentile result and not")
    print("independent evidence for it. Separating the two would need more round-1 campaigns.")
    print()
    print("The percentile also has a SIGN worth keeping. PhoQ's %.3f sits BELOW chance, because the"
          % p["mean_fitness_percentile"])
    print("model proposes neighbours of AVST and AVST reads %.2f against a pool median of %.2f. Local"
          % (phoq.fitness["AVST"], __import__("statistics").median(
              [phoq.fitness[s] for s in phoq.pool])))
    print("search around a mediocre reference lands below the pool average, which is what an")
    print("uninformed proposer looks like. GB1's %.3f is what a retrieving one looks like."
          % g["mean_fitness_percentile"])
    print()
    print("HONEST LIMIT. PhoQ's 0 of 20 excludes GB1-level contamination decisively. On its own it")
    print("admits enrichment up to %.0fx at 95%%, so the argmax indicator is not what licenses PhoQ."
          % p["enrichment_upper95"])
    print("The percentile and the distance-4 fraction are what carry the claim, and both are")
    print("computable on a landscape whose optimum the model could never have seen.")
    out.append(dict(name="contrast", diff_percentile=d_pct, se_percentile=se_pct,
                    se_units_percentile=abs(d_pct / se_pct), diff_dist4=d_far, z_dist4=z_far,
                    diff_dist_ge3=d_ge3, z_dist_ge3=z_ge3, diff_mean_hamming=d_ham,
                    mean_hamming_is_a_separator=False))

    dest = os.path.join(ROOT, "results", "step6_round1_prior_diagnostics.json")
    json.dump(out, open(dest, "w"), indent=1)
    print("\nsaved %s" % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
