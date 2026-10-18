#!/usr/bin/env python3
"""Two further analyses of the logged pilot data.

A. Champion tracking: when the agent re-orders a variant, is that variant the mean-argmax of its own history or
   the max-single-reading argmax? The two differ exactly when replication matters.

B. Replication fraction by round, to tell a flat response to noise from drift with context length. The raw
   curve is compared against an availability-matched null: the chance that a uniform draw from the
   11,522-variant pool hits an already-measured variant, |measured| / 11,522.
"""
import collections
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import landscape as L

LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "results", "pilot_opus47_calls.jsonl")
# The pilot's "blind" cell told the agent that readings carry measurement error, so it is relabelled.
RELABEL = {"blind": "baseline(mislabelled blind)", "instructed": "mechanism"}


def slope(xs, ys):
    """OLS slope with its standard error."""
    n = len(xs)
    if n < 3:
        return None, None
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None, None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    resid = [y - (my + b * (x - mx)) for x, y in zip(xs, ys)]
    if n <= 2:
        return b, None
    s2 = sum(r * r for r in resid) / (n - 2)
    return b, (s2 / sxx) ** 0.5


def main():
    ls = L.load("gb1")
    pool_n = len(ls.pool)
    rows = [json.loads(l) for l in open(LOG)]
    print("Re-analysis of %d logged calls, no new spend.\n" % len(rows))

    # group by campaign so history can be replayed
    camps = collections.defaultdict(list)
    for r in rows:
        camps[(r["rung"], r["ratio"], r["campaign_seed"])].append(r)

    print("=" * 100)
    print("A. CHAMPION TRACKING: when the agent re-orders, does it track the MEAN or the MAX?")
    print("=" * 100)
    agree = collections.Counter()
    for key, calls in sorted(camps.items()):
        obs = collections.defaultdict(list)
        for r in sorted(calls, key=lambda x: (x["round"], x["kind"] != "round")):
            # what the history implied BEFORE this round's proposals
            if obs:
                means = {s: sum(v) / len(v) for s, v in obs.items()}
                maxes = {s: max(v) for s, v in obs.items()}
                mean_arg = max(means, key=means.get)
                max_arg = max(maxes, key=maxes.get)
                if mean_arg != max_arg:          # only informative when the rules disagree
                    for s in r["parsed"]:
                        if s in obs:
                            if s == mean_arg and s != max_arg:
                                agree["tracked_mean"] += 1
                            elif s == max_arg and s != mean_arg:
                                agree["tracked_max"] += 1
                            else:
                                agree["other_measured_variant"] += 1
            # then apply this round's readings, reconstructed from the campaign log
            for s in r["parsed"]:
                pass
        # replay readings from the stored per-round history in the NEXT call's prompt is not
        # available, so rebuild from the observed values the harness recorded
        for r in calls:
            for s in r["parsed"]:
                obs[s].append(None)
    print("  NOT COMPUTABLE FROM THIS LOG. The per-call record stores the prompt and the parsed")
    print("  proposals but not the observed READING each proposal returned, so the agent's own")
    print("  history cannot be replayed to compare mean-argmax against max-argmax.")
    print("  This is a logging gap, not an analysis choice: the brief asked for observed value and")
    print("  true value per proposal and the harness logs them on the campaign Result, not on the")
    print("  call. One field to add before the next run; the analysis is then free.")
    print()

    print("=" * 100)
    print("B. REPLICATION FRACTION BY ROUND, against the availability-matched null")
    print("=" * 100)
    print("  %-28s %s" % ("cell", "  ".join("r%-2d" % i for i in range(1, 16))))
    per_cell_slopes = {}
    for (rung, ratio) in sorted({(k[0], k[1]) for k in camps}):
        byr = collections.defaultdict(list)
        for key, calls in camps.items():
            if key[0] != rung or key[1] != ratio:
                continue
            seen = set()
            for r in sorted(calls, key=lambda x: (x["round"], x["kind"] != "round")):
                if not r["parsed"]:
                    continue
                rep = sum(1 for s in r["parsed"] if s in seen)
                byr[r["round"]].append(rep / len(r["parsed"]))
                seen.update(r["parsed"])
        xs, ys = [], []
        cells = []
        for rnd in range(1, 16):
            if byr.get(rnd):
                m = st.mean(byr[rnd])
                cells.append("%3.0f" % (100 * m))
                xs.append(rnd); ys.append(m)
            else:
                cells.append("  -")
        b, se = slope(xs, ys)
        per_cell_slopes[(rung, ratio)] = (b, se)
        print("  %-28s %s" % ("%s r%.0f" % (RELABEL.get(rung, rung), ratio), "  ".join(cells)))
    print()
    print("  availability-matched null: a uniform draw hits an already-measured variant with")
    print("  probability |measured|/%d, which is under %.2f%% even at 60 measurements." % (pool_n, 100*60/pool_n))
    print()
    print("  ROUND SLOPE against NOISE SLOPE, the confound test:")
    for (rung, ratio), (b, se) in sorted(per_cell_slopes.items()):
        print("    %-28s round slope %+6.2f pts/round +- %s"
              % ("%s r%.0f" % (RELABEL.get(rung, rung), ratio),
                 100 * b if b is not None else float("nan"),
                 ("%.2f" % (100 * se)) if se is not None else "n/a"))
    pairs = {}
    for (rung, ratio), (b, se) in per_cell_slopes.items():
        pairs.setdefault(rung, {})[ratio] = b
    print()
    for rung, d in sorted(pairs.items()):
        if 2.0 in d and 8.0 in d:
            print("    %-28s mean round slope %+.2f pts/round; the NOISE effect measured earlier"
                  % (RELABEL.get(rung, rung), 100 * st.mean([d[2.0], d[8.0]])))
    print("    was +7.7 and +5.9 points TOTAL across an eightfold noise change.")


if __name__ == "__main__":
    main()
