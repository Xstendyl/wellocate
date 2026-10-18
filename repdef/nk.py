"""Seeded generator for Kauffman NK landscapes, so each run can use a fresh landscape with an unseen optimum.

Each of N positions contributes a value keyed on itself and its K interaction partners; fitness is the
mean of the N contributions. Contributions are computed from a hash of the seed and key, not stored.
"""

import hashlib
import itertools
import math

DEFAULT_ALPHABET = "ABCDEFGHIJKLMNOPQRST"          # 20 symbols, abstract by design


DISTS = ("uniform", "exponential", "lognormal", "pareto")


def _contribution(u, dist, shape):
    """Map a uniform draw to the contribution distribution (uniform or a heavy-tailed alternative)."""
    if dist == "uniform":
        return u
    u = min(max(u, 1e-12), 1 - 1e-12)
    if dist == "exponential":
        return -math.log(1.0 - u)
    if dist == "lognormal":
        # Inverse normal CDF by bisection on erf.
        lo, hi = -8.0, 8.0
        target = 2.0 * u - 1.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if math.erf(mid / math.sqrt(2.0)) < target:
                lo = mid
            else:
                hi = mid
        return math.exp(shape * 0.5 * (lo + hi))
    if dist == "pareto":
        return (1.0 - u) ** (-1.0 / shape) - 1.0
    raise ValueError("unknown dist %r" % (dist,))


def _u01(seed, pos, key):
    """uniform[0,1) keyed on (seed, position, the values in that position's interaction set)."""
    h = hashlib.blake2b(digest_size=8)
    h.update(b"nk")
    h.update(int(seed).to_bytes(8, "big"))
    h.update(int(pos).to_bytes(2, "big"))
    h.update(key.encode("ascii"))
    return int.from_bytes(h.digest(), "big") / float(1 << 64)


class NKLandscape(object):
    """A generated landscape with the same interface the pipeline expects of a real one."""

    __slots__ = ("n", "alphabet", "k", "seed", "sites", "fitness", "pool", "threshold", "name",
                 "dist", "shape")

    def __init__(self, k, seed, n=4, alphabet=DEFAULT_ALPHABET, threshold_percentile=93.0,
                 name=None, dist="uniform", shape=1.5):
        if not 0 <= k <= n - 1:
            raise ValueError("K must be in [0, N-1], got %r for N=%d" % (k, n))
        self.n = n
        self.alphabet = alphabet
        self.k = int(k)
        self.seed = int(seed)
        if dist not in DISTS:
            raise ValueError("dist must be one of %s" % (DISTS,))
        self.dist = dist
        self.shape = float(shape)
        self.name = name or ("nk_k%d_s%d" % (k, seed))
        # Interaction sets: position i interacts with the next K positions, wrapping around.
        self.sites = tuple(tuple([i] + [(i + j + 1) % n for j in range(self.k)])
                           for i in range(n))
        self.fitness = self._build()
        vals = sorted(self.fitness.values())
        idx = min(len(vals) - 1, int(threshold_percentile / 100.0 * len(vals)))
        self.threshold = vals[idx]
        self.pool = frozenset(s for s, v in self.fitness.items() if v > self.threshold)

    def _build(self):
        out = {}
        for tup in itertools.product(self.alphabet, repeat=self.n):
            s = "".join(tup)
            tot = 0.0
            for i, st_ in enumerate(self.sites):
                tot += _contribution(_u01(self.seed, i, "".join(s[j] for j in st_)),
                                     self.dist, self.shape)
            out[s] = tot / self.n
        return out

    # -- landscape properties -------------------------------------------------------------
    def autocorrelation(self, n_pairs=200000, seed=0):
        """Hamming-1 autocorrelation, the same statistic measured on PhoQ (0.264) and GB1 (0.403)."""
        import math
        import random
        rng = random.Random(seed)
        keys = list(self.fitness)
        xs, ys = [], []
        for _ in range(n_pairs):
            s = rng.choice(keys)
            i = rng.randrange(self.n)
            a = rng.choice(self.alphabet)
            if a == s[i]:
                continue
            t = s[:i] + a + s[i + 1:]
            xs.append(self.fitness[s]); ys.append(self.fitness[t])
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
        return num / den if den else float("nan")

    def pool_fraction(self):
        return len(self.pool) / float(len(self.fitness))

    def __repr__(self):
        return "NKLandscape(K=%d, seed=%d, n=%d, pool=%d (%.2f%%), thresh=%.4f)" % (
            self.k, self.seed, self.n, len(self.pool), 100 * self.pool_fraction(),
            self.threshold)
