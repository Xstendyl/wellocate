#!/usr/bin/env python3
"""Landscape numbers quoted in Section 2 of the paper, computed from the data into one results file.

  - GB1 and PhoQ: the share of all 160,000 variants above each landscape's viability threshold (repdef/landscape.py:
    fitness > 0.1 in GB1, > 1.0 in PhoQ), from the pinned data files. Each wild type's own fitness is recorded with
    the share of variants at least as fit as it, because the text describes the two cutoffs against the wild type.
    In GB1 the wild type (VDGV) reads 1.0, so the cutoff is a tenth of it. In PhoQ the wild type (AVST) reads 3.29,
    so the cutoff of 1.0 is not the wild type's fitness.
  - The grid: in Figure 3(b)'s slice (positions 3 and 4 fixed at the best candidate's letters), the best candidate's
    one-letter neighbours shown and how many are viable, read from results/landscape_summary.json.
  - Figure 3(c)'s slice through the start (positions 3 and 4 fixed at the start's letters): its viable cells, the
    viable cells in the start's own row and column, the slice's best candidate, and how many of the start's 76
    neighbours lie off the slice (a change at position 3 or 4) and are viable.
  - Whether good candidates cluster. On the grid, scrambled GB1 and scrambled PhoQ (the Wellocate instances the paper
    runs, all cut to their top 7%), the share of each viable candidate's one-letter neighbours (4 positions x 19
    letters) that are viable: over every viable candidate, over the top 10% of them by true value, and for the
    start candidate; against the viable share of the whole landscape. The mean over candidates and the pooled share
    are both kept; they are equal, because every candidate has the same number of neighbours.

The wild types are the parents repdef/prompts.py gives each protein (LANDSCAPES["gb1_bio"], ["phoq_bio"]).

Usage: python3 scripts/landscape_shares.py     (writes results/landscape_shares.json)
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import landscape as L                           # noqa: E402
from repdef import prompts as PR                            # noqa: E402
from wellocate import landscapes as WL                      # noqa: E402

OUT = os.path.join(ROOT, "results", "landscape_shares.json")
CLUSTER = (("grid", "nk/K1/seed1"), ("gb1_scrambled", "gb1/scramble:20261003"), ("phoq_scrambled", "phoq/scramble:20261004"))
TOP = 0.10                                                  # "good candidates": the top tenth of the viable ones


def protein(name):
    land = L.load(name)
    wt = PR.LANDSCAPES[name + "_bio"]["parent"]
    fit = land.fitness
    n = len(fit)
    at_least_wt = sum(1 for v in fit.values() if v >= fit[wt])
    return dict(variants=n, threshold=land.threshold, rule="fitness > threshold", viable=len(land.pool),
                viable_pct=100.0 * len(land.pool) / n, wild_type=wt, wild_type_fitness=fit[wt],
                at_least_wild_type=at_least_wt, at_least_wild_type_pct=100.0 * at_least_wt / n)


def slice_neighbours():
    s = json.load(open(os.path.join(ROOT, "results", "landscape_summary.json")))
    S, best = s["slice"], s["best"]["seq"]
    A, V = S["alphabet"], S["viable"]                 # V[letter at position 2][letter at position 1]
    i, j = A.index(best[0]), A.index(best[1])
    row = [V[j][x] for x in range(len(A)) if x != i]
    col = [V[y][i] for y in range(len(A)) if y != j]
    return dict(best=best, fixed_positions=S["fixed_positions"], fixed_letters=S["fixed_letters"],
                neighbours_shown=len(row) + len(col), neighbours_viable=sum(row) + sum(col),
                slice_viable=S["n_viable"], slice_cells=S["n_cells"],
                slice_viable_pct=100.0 * S["n_viable"] / S["n_cells"])


def start_slice():
    s = json.load(open(os.path.join(ROOT, "results", "landscape_summary.json")))
    S, ref = s["start_slice"], s["reference"]["seq"]
    A, V, G = S["alphabet"], S["viable"], S["fitness"]   # [letter at position 2][letter at position 1]
    i, j = A.index(ref[0]), A.index(ref[1])
    row = [V[j][x] for x in range(len(A)) if x != i]
    col = [V[y][i] for y in range(len(A)) if y != j]
    bx, by = max(((x, y) for y in range(len(A)) for x in range(len(A))), key=lambda c: G[c[1]][c[0]])
    env = WL.instance(CLUSTER[0][1])
    if env.anchor != ref:
        raise SystemExit("ABORT: landscape_summary.json's start %s is not the grid's start %s" % (ref, env.anchor))
    nbrs = [ref[:p] + a + ref[p + 1:] for p in range(len(ref)) for a in env.alphabet if a != ref[p]]
    off = [t for t in nbrs if t[2:] != ref[2:]]
    return dict(seq=ref, fixed_positions=S["fixed_positions"], fixed_letters=S["fixed_letters"],
                viable_cells=S["n_viable"], cells=S["n_cells"], viable_pct=100.0 * S["n_viable"] / S["n_cells"],
                row_column_neighbours=len(row) + len(col), row_column_viable=sum(row) + sum(col),
                best=A[bx] + A[by] + "".join(S["fixed_letters"]), best_value=G[by][bx],
                best_viable=bool(V[by][bx]), neighbours=len(nbrs), neighbours_viable=sum(t in env.pool for t in nbrs),
                off_slice_neighbours=len(off), off_slice_viable=sum(t in env.pool for t in off))


def clustering(name):
    env = WL.instance(name)
    A, fit, pool = env.alphabet, env.fit, env.pool

    def neighbours(s):
        return [s[:p] + a + s[p + 1:] for p in range(len(s)) for a in A if a != s[p]]

    per = len(neighbours(env.anchor))
    viable_nbrs = {v: sum(1 for t in neighbours(v) if t in pool) for v in pool}
    ranked = sorted(pool, key=lambda s: -fit[s])
    top = ranked[:int(round(TOP * len(pool)))]
    if fit[top[-1]] == fit[ranked[len(top)]]:
        raise SystemExit("ABORT: %s has a tie at the top-10%% cutoff, so the set of good candidates is not defined" % name)

    def share(group):
        return dict(candidates=len(group),
                    mean_viable_neighbour_pct=100.0 * sum(viable_nbrs[v] / float(per) for v in group) / len(group),
                    pooled_viable_neighbour_pct=100.0 * sum(viable_nbrs[v] for v in group) / (per * len(group)))

    start = sum(1 for t in neighbours(env.anchor) if t in pool)
    return dict(instance=name, variants=len(fit), viable=len(pool), viable_pct=100.0 * len(pool) / len(fit),
                neighbours_per_candidate=per, all_viable=share(ranked),
                top_viable=dict(share(top), fraction=TOP, value_cutoff=fit[top[-1]]),
                start=dict(seq=env.anchor, value=fit[env.anchor], neighbours=per, viable_neighbours=start,
                           viable_neighbour_pct=100.0 * start / per))


def main():
    out = dict(gb1=protein("gb1"), phoq=protein("phoq"), grid_slice=slice_neighbours(),
               clustering={k: clustering(name) for k, name in CLUSTER}, start_slice=start_slice())
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    for k in ("gb1", "phoq"):
        p = out[k]
        print("%-4s viable %d of %d (%.2f%%, fitness > %g) | wild type %s reads %.4f; %.2f%% at least as fit"
              % (k, p["viable"], p["variants"], p["viable_pct"], p["threshold"], p["wild_type"],
                 p["wild_type_fitness"], p["at_least_wild_type_pct"]))
    g = out["grid_slice"]
    print("grid slice: %d of %s's %d one-letter neighbours shown are viable" % (g["neighbours_viable"], g["best"],
                                                                                g["neighbours_shown"]))
    for k, c in out["clustering"].items():
        print("%-15s viable %.2f%% | viable neighbours: all viable %.2f%%, top 10%% %.2f%% (value >= %.3f) | start %s "
              "%d of %d" % (k, c["viable_pct"], c["all_viable"]["pooled_viable_neighbour_pct"],
                            c["top_viable"]["pooled_viable_neighbour_pct"], c["top_viable"]["value_cutoff"],
                            c["start"]["seq"], c["start"]["viable_neighbours"], c["start"]["neighbours"]))
    t = out["start_slice"]
    print("start slice through %s (positions 3-4 = %s): %d of %d viable; row and column %d of %d viable; best %s %.4f; "
          "%d of its %d viable neighbours lie off the slice" % (t["seq"], "".join(t["fixed_letters"]), t["viable_cells"],
                                                                t["cells"], t["row_column_viable"],
                                                                t["row_column_neighbours"], t["best"], t["best_value"],
                                                                t["off_slice_viable"], t["neighbours_viable"]))
    print("written %s" % os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
