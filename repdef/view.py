"""The read-only view of a campaign that a policy receives, with no true fitness values.

Observation carries `observed` and never `true`, and the view holds no reference to the Oracle
or the landscape. tests/test_view_leak.py checks that no true value is reachable from it.
"""

import collections

Observation = collections.namedtuple("Observation", "round seq outcome observed")


class CampaignView(object):
    """An immutable snapshot of what the policy knows."""

    __slots__ = ("history", "pool", "pool_sorted", "rounds_left", "slots_per_round",
                 "current_round", "total_rounds", "slots_used", "slots_total",
                 "campaign_seed", "screen")

    def __init__(self, history, pool, current_round, total_rounds, slots_per_round,
                 slots_used, slots_total, pool_sorted=None, campaign_seed=0, screen=None):
        self.history = tuple(history)
        self.pool = pool                       # frozenset; membership only
        # Sorted pool, computed once per campaign.
        self.pool_sorted = pool_sorted if pool_sorted is not None else tuple(sorted(pool))
        # The campaign's seed. Policies mix it into their random keys so campaigns that reach
        # the same state still make independent choices. It carries no fitness information.
        self.campaign_seed = campaign_seed
        # The viability prescreen. `screen.passes(seq)` is a predictor output and carries no
        # fitness value; see repdef/screen.py.
        if screen is None:
            from repdef.screen import NoScreen
            screen = NoScreen()
        self.screen = screen
        self.current_round = current_round
        self.total_rounds = total_rounds
        self.rounds_left = total_rounds - current_round + 1
        self.slots_per_round = slots_per_round
        self.slots_used = slots_used
        self.slots_total = slots_total

    # -- convenience the policy may use ---------------------------------------------
    def readings(self):
        """dict[seq] -> list of observed readings. Only successful measurements appear."""
        out = collections.defaultdict(list)
        for o in self.history:
            if o.outcome == "ok":
                out[o.seq].append(o.observed)
        return dict(out)

    def measured(self):
        """Every sequence the campaign has spent a slot on, successful or not.

        Includes sequences whose synthesis failed."""
        return {o.seq for o in self.history if o.outcome in ("ok", "failed")}

    def with_readings(self):
        """Sequences that have at least one usable reading."""
        return set(self.readings())

    def best_by_mean(self):
        """The current champion by mean observed reading; ties go to the earliest first measurement."""
        r = self.readings()
        if not r:
            return None
        first_seen = {}
        for i, o in enumerate(self.history):
            if o.outcome == "ok" and o.seq not in first_seen:
                first_seen[o.seq] = i
        return min(r, key=lambda s: (-sum(r[s]) / len(r[s]), first_seen[s]))

    def best_by_max(self):
        """Champion by single highest reading."""
        r = self.readings()
        if not r:
            return None
        first_seen = {}
        for i, o in enumerate(self.history):
            if o.outcome == "ok" and o.seq not in first_seen:
                first_seen[o.seq] = i
        return min(r, key=lambda s: (-max(r[s]), first_seen[s]))

    def __repr__(self):
        return "CampaignView(round=%d/%d, slots=%d/%d, seen=%d)" % (
            self.current_round, self.total_rounds, self.slots_used,
            self.slots_total, len(self.measured()))


def build(oracle, current_round, total_rounds, slots_per_round, slots_total,
          pool_sorted=None, screen=None):
    """Build a CampaignView from an Oracle, dropping `true` and `replicate_index` from every record."""
    obs = tuple(Observation(r.round, r.seq, r.outcome, r.observed) for r in oracle.history)
    return CampaignView(obs, oracle.pool, current_round, total_rounds,
                        slots_per_round, oracle.slots_used, slots_total, pool_sorted,
                        campaign_seed=oracle.seed, screen=screen)
