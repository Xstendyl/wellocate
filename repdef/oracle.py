"""Simulated measurement device: holds true fitness, returns noisy readings and logs every attempt.

Main outcomes:

    rejected  the sequence is outside the measurable set. No slot consumed, no random draw.
    failed    synthesis failed. Slot consumed, no reading returned.
    ok        a reading of true + noise is returned.

`true` is stored on every record for analysis only; policies see a CampaignView (view.py).
Draws are keyed on (seed, seq, replicate_index), so rejections do not shift the noise field
and policies stay paired by seed.
"""

import collections

Record = collections.namedtuple(
    "Record", "round seq outcome observed true replicate_index slot_consumed")

REJECTED = "rejected"
# Outcomes for a slot consumed with nothing measured.
ABANDONED = "abandoned"      # every replacement for this slot was also non-viable
ROUND_LOST = "round_lost"    # the reply was not the requested number of candidates
FAILED = "failed"
OK = "ok"
# Repeat cap: an order for a candidate already ordered the allowed number of times is refused before
# anything is measured. No slot is consumed and the agent chooses again.
CAPPED = "capped"
ABANDONED = "abandoned"          # written by campaign.py when re-asks run out
# A slot lost after the repeat cap refused an order. Only written when the cap is on.
CAP_LOST = "cap_lost"


class Oracle(object):
    """Measures sequences against a landscape, with noise and synthesis failure."""

    __slots__ = ("landscape", "pool", "measurable", "sigma", "seed", "failure_rate",
                 "history", "_attempts", "_rng", "screen_q", "noise_model", "cv", "noise_floor",
                 "rng_key", "refused")

    def __init__(self, landscape, pool, sigma, seed, failure_rate=0.15, rng=None,
                 measurable=None, screen_q=None, noise_model="additive", cv=None,
                 noise_floor=0.0, rng_key=None):
        if sigma < 0:
            raise ValueError("sigma must be >= 0, got %r" % (sigma,))
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError("failure_rate must be in [0,1], got %r" % (failure_rate,))
        self.landscape = landscape            # dict[str, float], the full table
        self.pool = pool                      # the viable subset a policy may propose from
        # The set the instrument will measure, which may differ from what a policy may propose.
        # Defaults to the pool; passing the full table also measures dead variants.
        self.measurable = pool if measurable is None else measurable
        # Screen strength q in [0,1]: a non-viable proposal is rejected with probability q and
        # otherwise measured, consuming a slot. The draw is keyed on the sequence, so each variant
        # has one verdict per campaign and the verdict is paired across policies.
        # Noise model: "additive" uses a constant sigma; "multiplicative" uses sigma(f) = f * cv,
        # consistent with sequencing read-depth noise that rises with fitness.
        if noise_model not in ("additive", "multiplicative"):
            raise ValueError("noise_model must be 'additive' or 'multiplicative'")
        self.noise_model = noise_model
        self.cv = None if cv is None else float(cv)
        # Noise floor for the multiplicative model: sd = sqrt(floor^2 + (f*cv)^2), so dead variants
        # still get some noise.
        self.noise_floor = float(noise_floor)
        if noise_model == "multiplicative" and not self.cv:
            raise ValueError("multiplicative noise needs cv")
        self.screen_q = None if screen_q is None else float(screen_q)
        if self.screen_q is not None and not 0.0 <= self.screen_q <= 1.0:
            raise ValueError("screen_q must be in [0,1], got %r" % (screen_q,))
        self.sigma = float(sigma)
        self.seed = int(seed)
        self.failure_rate = float(failure_rate)
        self.history = []
        # Slot-consuming attempts per sequence. This is what indexes the noise field, so a
        # rejection must not increment it.
        self._attempts = collections.Counter()
        from repdef import rng as _rng
        self._rng = rng or _rng
        # Optional map from the sequence the agent sees to the string random draws are keyed on.
        # None keys on the sequence itself. A relabelled landscape maps each label back to its
        # source sequence, so relabelled and original arms draw the same noise for the same variant.
        self.rng_key = rng_key
        # Orders refused by the repeat cap, as (round, sequence). Kept out of the history because
        # they use no slot and draw nothing.
        self.refused = []

    def record_capped(self, rnd, seq):
        """Record an order refused by the repeat cap in `refused`. No slot is consumed and no history line is written."""
        rec = Record(rnd, seq, CAPPED, None, self.landscape.get(seq), None, False)
        self.refused.append((rnd, seq))
        return rec

    def orders_of(self, seq):
        """Slot-consuming orders of `seq` so far, failed ones included: the count the repeat cap reads."""
        return self._attempts[seq]

    def record_abandoned(self, rnd, seq, outcome=ABANDONED):
        """Record a slot consumed with nothing measured."""
        rec = Record(rnd, seq, outcome, None, None, None, True)
        self.history.append(rec)
        return rec

    # -- accounting ------------------------------------------------------------------
    @property
    def slots_used(self):
        return sum(1 for r in self.history if r.slot_consumed)

    def n_ok(self):
        return sum(1 for r in self.history if r.outcome == OK)

    def measure(self, seq, rnd):
        """One measurement attempt. Returns the Record, which is also appended to history."""
        true = self.landscape.get(seq)
        key = seq if self.rng_key is None else self.rng_key.get(seq, seq)
        if self.screen_q is None:
            admitted = seq in self.measurable
        elif seq not in self.landscape:
            admitted = False                      # not a sequence at all
        elif seq in self.pool:
            admitted = True                       # viable: a screen never rejects these
        else:
            # Dead. Caught by the screen with probability q, keyed on the sequence so the
            # verdict is stable within a campaign and identical across policies.
            admitted = self._rng.uniform("screen", self.seed, key) >= self.screen_q
        if not admitted:
            rec = Record(rnd, seq, REJECTED, None, true, None, False)
            self.history.append(rec)
            return rec

        n = self._attempts[seq]               # 0 for the first slot-consuming attempt
        self._attempts[seq] = n + 1

        if self.failure_rate > 0.0 and \
                self._rng.uniform("fail", self.seed, key, n) < self.failure_rate:
            rec = Record(rnd, seq, FAILED, None, true, n, True)
            self.history.append(rec)
            return rec

        if self.noise_model == "multiplicative":
            # sigma scales with the TRUE value, plus a floor so a dead variant is not read exactly.
            sd = ((self.noise_floor ** 2) + (abs(true) * self.cv) ** 2) ** 0.5
            noise = sd * self._rng.normal("noise", self.seed, key, n)
        else:
            noise = self.sigma * self._rng.normal("noise", self.seed, key, n) \
                if self.sigma > 0.0 else 0.0
        rec = Record(rnd, seq, OK, true + noise, true, n, True)
        self.history.append(rec)
        return rec

    # -- analysis-side views (never handed to a policy) -------------------------------
    def observations(self):
        """dict[seq] -> list of ok readings, in measurement order."""
        out = collections.defaultdict(list)
        for r in self.history:
            if r.outcome == OK:
                out[r.seq].append(r.observed)
        return dict(out)

    def measured_seqs(self):
        """Sequences with at least one ok reading."""
        return {r.seq for r in self.history if r.outcome == OK}

    def best_true_measured(self):
        m = self.measured_seqs()
        return max((self.landscape[s] for s in m), default=0.0)

    def n_useful(self):
        """Slots that produced a reading of a viable variant."""
        return sum(1 for r in self.history
                   if r.outcome == OK and r.seq in self.pool)

    def n_dead_measured(self):
        return sum(1 for r in self.history
                   if r.outcome == OK and r.seq not in self.pool)

    def realized_precision(self):
        """Fraction of consumed slots that landed on a viable variant."""
        used = self.slots_used
        if not used:
            return float("nan")
        return sum(1 for r in self.history
                   if r.slot_consumed and r.seq in self.pool) / used
