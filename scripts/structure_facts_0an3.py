#!/usr/bin/env python3
"""The numbers behind each fact in the STRUCTURE prompt paragraph, measured on the grid's landscape itself.

The landscape (grid.landscape(): NK, N = 4, K = 1, seed 1, uniform contributions, rescaled to a maximum of 8.762,
viable above the 93rd percentile) is enumerated in full, so every number here is exact except the interaction
check, which samples.

  1  WHICH POSITIONS INTERACT. For each pair of positions, the interaction of two letter changes,
     e = f(both) - f(first) - f(second) + f(neither), over 200,000 sampled (candidate, letter, letter) triples
     per pair: its mean absolute size and its largest absolute size, against the mean absolute effect of one
     change.
  2  NEIGHBOURS SCORE ALIKE. The correlation of scores between candidates one letter apart, over every ordered
     pair of viable candidates, and over every ordered pair in the space for reference.
  3  NON-INTERACTING CHANGES ADD UP. From 1: the share of double changes at a non-interacting pair whose
     interaction is below 1e-9.
  4  VIABLE NEIGHBOURS. The share of one-letter neighbours that are viable, for viable candidates and for
     non-viable ones, against the base rate.

Usage: python3 scripts/structure_facts_0an3.py      (writes results/structure_facts_0an3.json)
"""
import itertools, json, math, os, random, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import grid                                                             # noqa: E402

AB = grid.ALPHABET


def swap(s, i, a):
    return s[:i] + a + s[i + 1:]


def corr(xs, ys):
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return num / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))


def main():
    fit, pool = grid.landscape()
    keys = sorted(fit)
    rng = random.Random(20261003)
    out = {"space": len(fit), "viable": len(pool), "base_rate": len(pool) / len(fit)}
    # 1 and 3: interactions per pair of positions
    single = []
    inter = {}
    for i, j in itertools.combinations(range(4), 2):
        es = []
        for _ in range(200000):
            s = rng.choice(keys)
            a = rng.choice([x for x in AB if x != s[i]])
            b = rng.choice([x for x in AB if x != s[j]])
            f0, fa, fb, fab = fit[s], fit[swap(s, i, a)], fit[swap(s, j, b)], fit[swap(swap(s, i, a), j, b)]
            es.append(fab - fa - fb + f0)
            single.append(abs(fa - f0))
        inter["%d-%d" % (i + 1, j + 1)] = dict(mean_abs=st.mean(abs(e) for e in es), max_abs=max(abs(e) for e in es),
                                              share_below_1e9=sum(1 for e in es if abs(e) < 1e-9) / len(es))
    out["interaction"] = inter
    out["mean_abs_single_change"] = st.mean(single)
    # 2: neighbour correlation
    xs, ys, ax, ay = [], [], [], []
    viable_nb = total_nb = dead_viable_nb = dead_total_nb = 0
    for s in keys:
        for i in range(4):
            for a in AB:
                if a == s[i]:
                    continue
                t = swap(s, i, a)
                ax.append(fit[s]); ay.append(fit[t])
                if s in pool:
                    total_nb += 1
                    if t in pool:
                        viable_nb += 1
                        xs.append(fit[s]); ys.append(fit[t])
                else:
                    dead_total_nb += 1
                    dead_viable_nb += 1 if t in pool else 0
    out["neighbour_correlation_viable_pairs"] = corr(xs, ys)
    out["viable_pairs"] = len(xs)
    out["neighbour_correlation_all_pairs"] = corr(ax, ay)
    # 4: viable neighbours
    out["viable_rate_among_neighbours_of_viable"] = viable_nb / total_nb
    out["viable_rate_among_neighbours_of_nonviable"] = dead_viable_nb / dead_total_nb
    json.dump(out, open(os.path.join(ROOT, "results", "structure_facts_0an3.json"), "w"), indent=1)
    print("space %d, viable %d, base rate %.2f%%" % (out["space"], out["viable"], 100 * out["base_rate"]))
    print("1/3 interaction of two changes, by pair of positions (mean |one change| %.4f):"
          % out["mean_abs_single_change"])
    for k, v in inter.items():
        print("   positions %s: mean |e| %.4f, max |e| %.2e, share below 1e-9 %.4f"
              % (k, v["mean_abs"], v["max_abs"], v["share_below_1e9"]))
    print("2   correlation of scores one letter apart: %.3f over %d ordered viable pairs; %.3f over all pairs"
          % (out["neighbour_correlation_viable_pairs"], out["viable_pairs"], out["neighbour_correlation_all_pairs"]))
    print("4   viable among one-letter neighbours: %.2f%% of a viable candidate's, %.2f%% of a non-viable one's, "
          "base %.2f%%" % (100 * out["viable_rate_among_neighbours_of_viable"],
                          100 * out["viable_rate_among_neighbours_of_nonviable"], 100 * out["base_rate"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
