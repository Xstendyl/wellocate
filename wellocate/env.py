"""The Wellocate environment: one campaign as a step-by-step episode.

An agent has a fixed budget of assay slots (15 rounds of 4 by default). Each round it orders candidates. Each
order returns a noisy reading, or fails (the slot is spent and nothing comes back), or is rejected because the
candidate is not viable (no slot is spent, and the agent is asked for a replacement, at most 3 times). After
the last round the agent nominates one candidate, and the episode's reward is that candidate's true value.

The rules are the paper's: `_campaign` below is `repdef.campaign.run`'s loop for the paper's settings, with
each `policy.propose` call turned into a request the caller answers through `step`. The oracle, the view and
the nomination rule are the harness's own objects, and the tests check that both give identical histories.

Observations hold no true value. They carry the readings, outcomes and budget, built by `repdef.view.build`.
The only true number disclosed is the reference point's value, which every prompt in the paper states. The
nominee's true value and the scorecard arrive in `info` when the episode ends.

Text mode serves language models: `prompt()` returns the exact prompt the paper's agents received
(repdef.prompts, through repdef.llm_policy.LLMPolicy), and `act_text(reply)` reads the reply with the same
parser and the same re-ask rule (one re-ask on an unreadable reply; then the round spends nothing).
"""
import collections
import dataclasses

from repdef import campaign as C
from repdef import llm_policy as LP
from repdef import oracle as O
from repdef import view as V
from wellocate import landscapes as LS
from wellocate import splits as SP
from wellocate import stress as ST

# The noise floor is one post-selection read of the GB1 assay, (1/557)/0.512 in fitness units, as in the paper.
NOISE_FLOOR = (1 / 557) / (285 / 557)
# Coefficient of variation per preset. "assay" is the paper's 0.073, derived from the read depth of the GB1
# deep mutational scan (557 input and 285 selected reads per variant; Wu et al. 2016). "low" and "high" halve and double it for sensitivity studies; they are not taken from any assay.
NOISE_PRESETS = collections.OrderedDict([("low", 0.0365), ("assay", 0.073), ("high", 0.146)])
SHAPED = (None, "best_measured_gain")
LOST = (O.ABANDONED, O.ROUND_LOST, O.CAP_LOST)


@dataclasses.dataclass(frozen=True)
class Observation:
    """What the agent may see. `phase` is "round", "replacement", "nominate" or "done"."""
    phase: str
    round: int
    n_slots: int                      # candidates to send now: up to this many in a round, exactly 1 as a replacement
    exclude: frozenset                # candidates rejected this round, not to be sent again this round
    history: tuple                    # repdef.view.Observation(round, seq, outcome, observed), oldest first
    slots_used: int
    slots_total: int
    rounds: int
    alphabet: str
    anchor: str                       # the reference point
    anchor_reading: str               # its value as the prompt states it, two decimals
    example: str                      # the prompt's format example, a neighbour of the reference point
    view: object                      # repdef.view.CampaignView, for the scripted baselines. It carries the viable
                                      # set (view.pool, view.pool_sorted), which only the informed rule may use;
                                      # a fair agent reads history, alphabet and anchor and never view.pool.


def noise_cv_of(noise):
    if isinstance(noise, str):
        if noise not in NOISE_PRESETS:
            raise ValueError("unknown noise preset %r; known: %s" % (noise, ", ".join(NOISE_PRESETS)))
        return NOISE_PRESETS[noise]
    return float(noise)


def shrinkage_nominee(view, noise_cv=NOISE_PRESETS["assay"], noise_floor=NOISE_FLOOR):
    """The paper's registered nomination rule on a view: empirical-Bayes shrinkage, the prior fitted from the
    campaign's own readings (repdef.campaign). Raises campaign.UnusableSigma below two measured candidates."""
    sig = lambda f: ((noise_floor ** 2) + (abs(f) * noise_cv) ** 2) ** 0.5
    ep = C.empirical_prior(view, sig)
    if ep is None:
        raise C.UnusableSigma("an empirical prior needs at least two measured variants")
    return C._shrinkage_nominate(view, sig, ep[0], ep[1])


class Wellocate(object):
    """env = Wellocate("gb1", "gb1:test", seed=0); obs = env.reset(); obs, r, done, info = env.step([...])."""

    def __init__(self, landscape="gb1", split=None, seed=0, rounds=15, slots=4, noise_cv="assay",
                 failure_rate=0.15, shaped_reward=None, condition="blind", max_reasks=C.MAX_REASKS,
                 riskfree_rejection=False, noise_floor=NOISE_FLOOR, batch_sd=0.0, outlier_rate=0.0,
                 outlier_kind=None):
        """riskfree_rejection is the paper's risk-free rule: a rejected order costs nothing and the agent chooses
        again, up to campaign.RISKFREE_CAP replacement asks per slot, after which the slot is lost and counted
        (scorecard["rejection_cap_hits"]). Off by default: the grid's rule loses the slot after 3.
        noise_floor, batch_sd, outlier_rate and outlier_kind are the stress options of wellocate/stress.py;
        their defaults reproduce the paper's oracle exactly."""
        if shaped_reward not in SHAPED:
            raise ValueError("shaped_reward must be one of %s" % (SHAPED,))
        if isinstance(landscape, str) and "/" not in landscape and landscape not in LS.FAMILY_TRACK:
            raise ValueError("unknown landscape %r; families: %s" % (landscape, ", ".join(LS.FAMILY_TRACK)))
        self.family = landscape if isinstance(landscape, str) else None
        self.split = split if split is not None else ("%s:test" % landscape if self.family in LS.FAMILY_TRACK
                                                       else None)
        self.rounds, self.slots, self.failure_rate = int(rounds), int(slots), float(failure_rate)
        self.noise_cv = noise_cv_of(noise_cv)
        self.noise_floor = float(noise_floor)
        ST.check(batch_sd, outlier_rate, outlier_kind)
        self.stress = dict(batch_sd=float(batch_sd), outlier_rate=float(outlier_rate), outlier_kind=outlier_kind)
        self.shaped_reward, self.condition, self.max_reasks = shaped_reward, condition, int(max_reasks)
        self.riskfree = bool(riskfree_rejection)
        self._landscape_arg = landscape
        self.seed = seed
        self._gen = None
        self.reset(seed)

    # -- episode selection ------------------------------------------------------------------------
    def _episode(self, seed):
        """(env, campaign seed) for episode `seed` of the split, or a named instance with campaign seed `seed`."""
        lan = self._landscape_arg
        if not isinstance(lan, str):
            return lan, int(seed)                      # a repdef.envs.Env passed directly
        if "/" in lan:
            return LS.instance(lan), int(seed)
        if int(seed) < 0:
            raise ValueError("seed is an episode index and must be 0 or more, got %r" % (seed,))
        if not self.split.startswith(lan + ":"):
            raise ValueError("split %r is not a %s split" % (self.split, lan))
        inst, cseed = SP.episodes(self.split, int(seed) + 1)[int(seed)]
        return LS.instance(inst), cseed

    def reset(self, seed=None):
        if seed is not None:
            self.seed = seed
        self.env, self.campaign_seed = self._episode(self.seed)
        e = self.env
        self.fit, self.pool, self.ps = e.fit, e.pool, e.ps
        self.global_best = e.global_best
        self.track = LS.FAMILY_TRACK.get(e.meta.get("source", "nk"), "sandbox")
        kw = dict(noise_model="multiplicative", cv=self.noise_cv, noise_floor=self.noise_floor, rng_key=e.rng_key)
        if ST.active(**self.stress):
            self._orc = ST.StressOracle(e.fit, e.pool, 0.0, self.campaign_seed, self.failure_rate, **dict(kw, **self.stress))
        else:
            self._orc = O.Oracle(e.fit, e.pool, 0.0, self.campaign_seed, self.failure_rate, **kw)
        self._done, self._info, self._best_seen = False, None, 0.0
        self._text, self._attempts = None, 0
        self._gen = self._campaign()
        self._req = next(self._gen)
        return self.observation

    # -- the paper's loop, as a generator of requests ---------------------------------------------
    def _campaign(self):
        """campaign.run's slot-budget loop with the paper's settings: no screen and no repeat cap; the risk-free
        rule when asked for. Each `yield` is one `policy.propose` call of that loop."""
        orc, R_, S_ = self._orc, self.rounds, self.slots
        total = R_ * S_
        cap = C.RISKFREE_CAP if self.riskfree else self.max_reasks
        self._replication, measured_before, self._n_abandoned, self._cap_hits = 0, set(), 0, 0
        for rnd in range(1, R_ + 1):
            if orc.slots_used >= total:
                break
            budget = min(S_, total - orc.slots_used)
            view = V.build(orc, rnd, R_, S_, total, self.ps)
            picks = list((yield ("round", view, budget, frozenset())))[:budget]
            if not picks:
                for _lost in range(budget):
                    orc.record_abandoned(rnd, "----", outcome=O.ROUND_LOST)
            filled, rejected = 0, set()
            for pick in picks:
                if filled >= budget:
                    break
                seq, tries = pick, 0
                while True:
                    rec = orc.measure(seq, rnd)
                    if rec.outcome != O.REJECTED:
                        break
                    rejected.add(seq)
                    tries += 1
                    if tries > cap:
                        self._n_abandoned += 1
                        if self.riskfree:
                            self._cap_hits += 1
                        orc.record_abandoned(rnd, seq, outcome=O.ABANDONED)
                        seq = None
                        break
                    v2 = V.build(orc, rnd, R_, S_, total, self.ps)
                    again = (yield ("replacement", v2, 1, frozenset(rejected)))
                    if not again:
                        self._n_abandoned += 1
                        orc.record_abandoned(rnd, seq, outcome=O.ABANDONED)
                        seq = None
                        break
                    seq = again[0]
                if seq is None:
                    filled += 1
                    continue
                if seq in measured_before:
                    self._replication += 1
                measured_before.add(seq)
                filled += 1
        rounds_used = max((r.round for r in orc.history), default=0)
        final = V.build(orc, rounds_used or 1, R_, S_, total, self.ps)
        yield ("nominate", final, 1, frozenset())

    # -- the agent's side -------------------------------------------------------------------------
    @property
    def observation(self):
        kind, view, n, excl = self._req
        e = self.env
        return Observation("done" if self._done else kind, view.current_round, n, excl, view.history,
                           view.slots_used, view.slots_total, self.rounds, e.alphabet, e.anchor,
                           "%.2f" % e.reading, e.example, view)

    def step(self, candidates):
        """Order candidates: up to n_slots in a round, exactly one as a replacement. An empty list forfeits the
        round, which spends all its slots, as in the paper. Returns (observation, reward, done, info)."""
        kind, view, n, _excl = self._req
        if self._done or kind == "nominate":
            raise RuntimeError("the budget is spent; call nominate(seq)")
        candidates = list(candidates)
        if len(candidates) > n:
            raise ValueError("%d candidates sent for %d slot(s)" % (len(candidates), n))
        width, alphabet = len(self.env.anchor), set(self.env.alphabet)
        for c in candidates:
            if not isinstance(c, str) or len(c) != width or not set(c) <= alphabet:
                raise ValueError("candidate %r is not a %d-letter string over %s" % (c, width, self.env.alphabet))
        if kind == "replacement" and not candidates:
            pass                                           # declining a replacement loses the slot, as in the paper
        self._req = self._gen.send(candidates)
        self._text, self._attempts = None, 0
        return self.observation, self._shaped(), False, {}

    def nominate(self, seq):
        """End the episode with a nominee. An invalid nominee falls back to the highest mean reading, as in the
        paper's harness, and info says so. The reward is the nominee's true value."""
        kind, view, _n, _e = self._req
        if self._done:
            raise RuntimeError("the episode is over; call reset()")
        if kind != "nominate":
            raise RuntimeError("nominate is allowed once the budget is spent (phase %r)" % kind)
        fallback = seq is None or seq not in self.fit
        nom = view.best_by_mean() if fallback else seq
        self._done = True
        self._info = dict(nominee=nom, nominee_true=self.fit[nom] if nom is not None else 0.0,
                          nomination_fallback=fallback, scorecard=self.scorecard(nom, view))
        return self.observation, self._info["nominee_true"] + self._shaped(), True, self._info

    def _shaped(self):
        if self.shaped_reward != "best_measured_gain":
            return 0.0
        # Computed from true values; off by default and never part of the observation.
        b = self._orc.best_true_measured()
        gain, self._best_seen = b - self._best_seen, max(b, self._best_seen)
        return max(gain, 0.0)

    def scorecard(self, nominee, view):
        """One episode's numbers, with the definitions repdef.campaign.run and the paper's analyses use."""
        orc = self._orc
        lost = sum(1 for r in orc.history if r.outcome in LOST)
        used = orc.slots_used
        reads = view.readings()
        best = orc.best_true_measured()
        pick = self.fit[nominee] if nominee is not None else 0.0
        try:
            ref = shrinkage_nominee(view, self.noise_cv, self.noise_floor)
        except C.UnusableSigma:
            ref = None
        return dict(pick=pick, global_best=self.global_best, best_true_measured=best,
                    exploration_shortfall=self.global_best - best, selection_shortfall=best - pick,
                    replication_count=self._replication, slots_used=used, lost_slots=lost,
                    share_budget=100.0 * self._replication / used if used else 0.0,
                    share_nonlost=100.0 * self._replication / (used - lost) if used - lost > 0 else 0.0,
                    distinct=len(orc.measured_seqs()),
                    rejected=sum(1 for r in orc.history if r.outcome == O.REJECTED),
                    failed=sum(1 for r in orc.history if r.outcome == O.FAILED),
                    nominee_readings=len(reads.get(nominee, ())), rejection_cap_hits=self._cap_hits,
                    shrinkage_nominee=ref, shrinkage_pick=self.fit[ref] if ref else None)

    # -- text mode --------------------------------------------------------------------------------
    def _llm(self):
        e = self.env
        pol = LP.LLMPolicy("text-mode", self.condition, 0.0, parent=e.anchor, fail_pct=int(round(100 * self.failure_rate)),
                           landscape=e.prompt_landscape, noise_model="multiplicative", cv=self.noise_cv,
                           noise_floor=self.noise_floor, anchor_reading="%.2f" % e.reading, example=e.example)
        pol.max_reasks_disclosed = self.max_reasks
        pol.riskfree_rejection = self.riskfree
        return pol

    def prompt(self):
        """The exact prompt the paper's agents received for the current request."""
        if self._done:
            raise RuntimeError("the episode is over")
        if self._text is None:
            kind, view, n, excl = self._req
            pol = self._llm()
            self._text = pol.nomination_prompt(view) if kind == "nominate" else pol.round_prompt(view, n, excl)
        return self._text

    def act_text(self, reply):
        """Read a model's reply to prompt() with the harness's parser and re-ask rule, then act on it. Returns
        (observation, reward, done, info); info["reask"] is True when the reply was unreadable and prompt()
        now holds the re-ask."""
        kind, view, n, _excl = self._req
        prompt = self.prompt()
        pol = self._llm()
        if kind == "nominate":
            seq, _reason, _notes = LP.parse_answer(reply, pol.alphabet)
            return self.nominate(seq or None)
        self._attempts += 1
        got, status, notes = LP.parse(reply, n, alphabet=pol.alphabet)
        if status != "ok" and self._attempts <= pol.parse_retries:
            notes.append("re-asked: attempt %d of %d produced status %r" % (self._attempts, pol.parse_retries + 1, status))
            self._text = pol.reask_prompt(prompt, notes, n)
            return self.observation, 0.0, False, dict(reask=True, parse_status=status)
        if status != "ok" and len(got) != n:
            got = []
        return self.step([g[0] for g in got])
