"""Viability prescreen applied as a filter on the candidates a policy may propose.

Viable variants always pass. A dead variant passes with probability 1 - q, so q=1 leaves only
viable variants and q=0 leaves the whole Hamming-1 shell.
"""


class Screen(object):
    """Screen verdicts that are fixed per (campaign seed, sequence), so every policy sees the same ones."""

    __slots__ = ("pool", "q", "seed", "_rng", "_cache")

    def __init__(self, pool, q, seed, rng=None):
        if not 0.0 <= q <= 1.0:
            raise ValueError("screen strength q must be in [0,1], got %r" % (q,))
        self.pool = pool
        self.q = float(q)
        self.seed = int(seed)
        if rng is None:
            from repdef import rng as _r
            rng = _r
        self._rng = rng
        self._cache = {}

    def passes(self, seq):
        """True if the policy may propose `seq`. Viable variants always pass."""
        if seq in self.pool:
            return True
        if self.q >= 1.0:
            return False
        if self.q <= 0.0:
            return True
        got = self._cache.get(seq)
        if got is None:
            got = self._rng.uniform("screen", self.seed, seq) >= self.q
            self._cache[seq] = got
        return got

    def __repr__(self):
        return "Screen(q=%.3f, seed=%d)" % (self.q, self.seed)


class NoScreen(object):
    """Everything proposable. Used when the pool restriction is enforced elsewhere."""

    __slots__ = ()
    q = 0.0

    def passes(self, seq):
        return True

    def __repr__(self):
        return "NoScreen()"
