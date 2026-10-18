#!/usr/bin/env python3
"""Is the reference table a lucky draw? Sweep thresh.py's fixed seed base.

thresh.py fixes `random.Random(1000+k)`. If the reference cells move by many SE when that
1000 becomes 2000, the table is one draw from a high-variance distribution and "within 2 SE
of the reference" is not a meaningful bar.

Run from the data directory: cd data && python3 ../scripts/seed_stability.py
"""
import csv
import random
import statistics as st

AA = "ACDEFGHIKLMNPQRSTVWY"
_NB = {}


def load(p):
    d = {}
    with open(p) as f:
        r = csv.reader(f)
        next(r)
        for v, fit in r:
            d[v] = float(fit)
    return d


def nbrs(s):
    g = _NB.get(s)
    if g is None:
        g = [s[:i] + a + s[i + 1:] for i in range(4) for a in AA if a != s[i]]
        _NB[s] = g
    return g


def campaign(d, pool, k, sigma, rng, rounds=15, per=4, fail=0.15):
    """thresh.py's campaign, verbatim."""
    obs = {}

    def mean_of(s):
        return sum(obs[s]) / len(obs[s])

    def champ():
        return max(obs, key=mean_of) if obs else None

    for _ in range(rounds):
        picks = []
        c = champ()
        if c is not None and k > 0:
            picks += [c] * k
        need = per - len(picks)
        if c is None:
            picks += [rng.choice(pool) for _ in range(need)]
        else:
            cand = [x for x in nbrs(c) if x in d and x not in obs]
            rng.shuffle(cand)
            take = cand[:need]
            while len(take) < need:
                take.append(rng.choice(pool))
            picks += take
        for s in picks:
            if rng.random() < fail:
                continue
            obs.setdefault(s, []).append(d[s] + rng.gauss(0, sigma))
    if not obs:
        return 0.0, 0.0
    return d[champ()], max(d[s] for s in obs)


REF = {"PhoQ": {1.0: {0: 28.109, 1: 27.835, 2: 23.815, 3: 20.462},
                2.0: {0: 21.040, 1: 23.320, 2: 22.001, 3: 19.073},
                4.0: {0: 12.443, 1: 15.574, 2: 14.911, 3: 15.076}},
       "GB1": {1.0: {0: 5.141, 1: 4.836, 2: 4.247, 3: 3.483},
               2.0: {0: 4.186, 1: 4.292, 2: 3.939, 3: 3.224},
               4.0: {0: 2.684, 1: 3.097, 2: 2.972, 3: 2.648}}}


def main(n=1200, bases=(1000, 2000, 3000, 4000)):
    for name, path, thr, unit in (("PhoQ", "phoq.csv", 1.0, 4.24),
                                  ("GB1", "gb1.csv", 0.1, 0.42)):
        d = load(path)
        pool = [s for s, v in d.items() if v > thr]
        print("=" * 78)
        print(name)
        for ratio in (1.0, 2.0, 4.0):
            sig = unit * ratio
            print("  ratio %.1f   reference -> %s" % (
                ratio, " ".join("k%d=%7.3f" % (k, REF[name][ratio][k]) for k in (0, 1, 2, 3))))
            for base in bases:
                row = []
                for k in (0, 1, 2, 3):
                    rng = random.Random(base + k)
                    vals = [campaign(d, pool, k, sig, rng)[0] for _ in range(n)]
                    row.append((st.mean(vals), st.stdev(vals) / n ** 0.5))
                bk = max(range(4), key=lambda i: row[i][0])
                dev = [abs(row[k][0] - REF[name][ratio][k]) / row[k][1] for k in range(4)]
                print("    base %4d -> %s | best k=%d | dev from ref in SE: %s"
                      % (base,
                         " ".join("k%d=%7.3f+-%.3f" % (k, row[k][0], row[k][1]) for k in range(4)),
                         bk, " ".join("%.0f" % x for x in dev)))


if __name__ == "__main__":
    main()
