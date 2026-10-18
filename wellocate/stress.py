"""Assay-realism stress options for Wellocate. Off by default.

The paper's oracle (repdef.oracle.Oracle) draws one reading per slot: the true value plus noise of SD
sqrt(floor^2 + (f * CV)^2). StressOracle keeps every one of those draws and changes a reading only after it is
drawn, from random streams of its own, so with every option off it is the paper's oracle exactly.

  batch_sd       each round draws one factor 1 + batch_sd * z, z keyed on (campaign seed, round), and every
                 reading of that round is multiplied by it: a plate or batch effect the readings share.
  outlier_rate   a reading becomes an outlier with this probability, keyed on (campaign seed, sequence, attempt).
  outlier_kind   "zero": a failed-well value, floor * |z|; "spike": three times the reading.

The additive floor itself is a Wellocate argument (noise_floor), since the paper's oracle already has one.
"""
from repdef import oracle as O

OUTLIER_KINDS = ("zero", "spike")


def check(batch_sd=0.0, outlier_rate=0.0, outlier_kind=None):
    if batch_sd < 0:
        raise ValueError("batch_sd must be >= 0, got %r" % (batch_sd,))
    if not 0.0 <= outlier_rate <= 1.0:
        raise ValueError("outlier_rate must be in [0, 1], got %r" % (outlier_rate,))
    if outlier_rate > 0 and outlier_kind not in OUTLIER_KINDS:
        raise ValueError("outlier_kind must be one of %s when outlier_rate > 0" % (OUTLIER_KINDS,))


def active(batch_sd=0.0, outlier_rate=0.0, outlier_kind=None):
    return batch_sd > 0 or outlier_rate > 0


class StressOracle(O.Oracle):
    """The paper's oracle with readings changed after they are drawn; failures and rejections are untouched."""

    def __init__(self, *a, batch_sd=0.0, outlier_rate=0.0, outlier_kind=None, **kw):
        check(batch_sd, outlier_rate, outlier_kind)
        O.Oracle.__init__(self, *a, **kw)
        self.batch_sd, self.outlier_rate, self.outlier_kind = float(batch_sd), float(outlier_rate), outlier_kind
        self.outliers = 0

    def batch_factor(self, rnd):
        return 1.0 + self.batch_sd * self._rng.normal("batch", self.seed, rnd) if self.batch_sd > 0 else 1.0

    def measure(self, seq, rnd):
        rec = O.Oracle.measure(self, seq, rnd)
        if rec.outcome != O.OK:
            return rec
        key = seq if self.rng_key is None else self.rng_key.get(seq, seq)
        x = rec.observed * self.batch_factor(rnd)
        if self.outlier_rate > 0 and self._rng.uniform("outlier", self.seed, key, rec.replicate_index) < self.outlier_rate:
            self.outliers += 1
            if self.outlier_kind == "zero":
                x = self.noise_floor * abs(self._rng.normal("outlier_zero", self.seed, key, rec.replicate_index))
            else:
                x = 3.0 * x
        if x == rec.observed:
            return rec
        new = rec._replace(observed=x)
        self.history[-1] = new
        return new
