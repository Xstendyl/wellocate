"""Run one campaign: 15 rounds x 4 slots, a capped re-ask loop for rejected orders, and a nomination.

The slot is the unit of budget. A rejected proposal costs no slot and the policy is re-asked,
up to a fixed number of times.
"""

import collections

from repdef import oracle as O
from repdef import view as V

DEFAULT_ROUNDS = 15
DEFAULT_SLOTS = 4
MAX_REASKS = 3
# Bound on replacement asks per slot under riskfree_rejection. A slot that reaches it is recorded as lost
# and counted in Result.rejection_cap_hits.
RISKFREE_CAP = 20

Result = collections.namedtuple(
    "Result", "nominated nominated_true best_true_measured regression_loss "
              "n_distinct n_ok n_failed n_rejected n_abandoned slots_used "
              "replication_count history rounds "
              "n_useful n_dead_measured realized_precision rounds_used "
              "replication_fraction_of_useful exploration_shortfall selection_shortfall "
              "ref_mean ref_max ref_shrinkage ref_shrinkage_note ref_shrinkage_oracle "
              "empirical_prior_mean empirical_prior_var agent_reason "
              "riskfree_rejection rejection_cap_hits repeat_cap n_capped repeat_cap_hits")


def empirical_prior(view, sigma, rel_floor=0.01):
    """An empirical-Bayes prior fitted from the campaign's own readings. Reads no true value.

    Method of moments:
      prior mean      the mean of the per-variant observed means
      prior variance  the spread of those means minus the average sampling variance of a mean
      floor           a small positive multiple of the average sampling variance, so the
                      variance cannot be zero or negative

    Returns (mean, variance), or None when fewer than two variants have readings.
    """
    r = view.readings()
    if len(r) < 2:
        return None
    pairs = [(sum(xs) / len(xs), len(xs)) for xs in r.values()]
    means = [m for m, _ in pairs]
    pm = sum(means) / len(means)
    spread = sum((m - pm) ** 2 for m in means) / (len(means) - 1)
    noise = 0.0
    for m, n in pairs:
        sg = sigma(m) if callable(sigma) else sigma
        noise += (sg ** 2) / n
    noise /= len(pairs)
    floor = rel_floor * noise if noise > 0 else 1e-9
    return pm, max(spread - noise, floor)


def empirical_prior_floor_binds(view, sigma, rel_floor=0.01):
    """True if the variance floor, not the data, set the empirical prior variance. None when undefined."""
    r = view.readings()
    if len(r) < 2:
        return None
    pairs = [(sum(xs) / len(xs), len(xs)) for xs in r.values()]
    means = [m for m, _ in pairs]
    pm = sum(means) / len(means)
    spread = sum((m - pm) ** 2 for m in means) / (len(means) - 1)
    noise = sum((((sigma(m) if callable(sigma) else sigma) ** 2) / n) for m, n in pairs) / len(pairs)
    return (spread - noise) <= (rel_floor * noise if noise > 0 else 1e-9)


class UnusableSigma(Exception):
    """A shrinkage nomination was requested with a sigma or prior it cannot use.

    Raised instead of falling back to the mean rule. Under multiplicative noise pass a callable sigma(f).
    """


def _shrinkage_nominate(view, sigma, prior_mean, prior_var):
    """Nominate the sequence with the highest posterior mean under a normal prior.

    A sequence with one reading is pulled strongly toward the prior; one with several readings less so."""
    r = view.readings()
    if not r:
        return None
    if prior_var <= 0.0:
        raise UnusableSigma("shrinkage needs a positive prior variance, got %r" % (prior_var,))
    # `sigma` may be a float or a callable f -> sigma(f) for multiplicative noise. The callable is
    # evaluated at the observed mean, since the nominator does not know true fitness.
    scalar = not callable(sigma)
    if scalar and sigma <= 0.0:
        raise UnusableSigma(
            "shrinkage was asked for with sigma=%r. Under multiplicative noise pass a callable "
            "sigma(f)." % (sigma,))
    best, best_post = None, None
    first = {}
    for i, o in enumerate(view.history):
        if o.outcome == "ok" and o.seq not in first:
            first[o.seq] = i
    for s, xs in r.items():
        n = len(xs)
        m = sum(xs) / n
        sig = sigma if scalar else sigma(m)
        if sig <= 0.0:
            raise UnusableSigma("sigma(%r) returned %r" % (m, sig))
        post = (prior_mean / prior_var + n * m / (sig ** 2)) / \
               (1.0 / prior_var + n / (sig ** 2))
        keyed = (-post, first[s])
        if best_post is None or keyed < best_post:
            best, best_post = s, keyed
    return best


def run(landscape, pool, policy, sigma, seed, failure_rate=0.15,
        rounds=DEFAULT_ROUNDS, slots_per_round=DEFAULT_SLOTS,
        nomination="mean", prior=None, pool_sorted=None, measurable=None,
        screen_q=None, budget_mode="slots", target_useful=None, max_rounds_hard=200,
        global_best=None, max_reasks=None, noise_model="additive", cv=None,
        noise_floor=0.0, prior_rel_floor=0.01, riskfree_rejection=False, riskfree_cap=RISKFREE_CAP,
        rng_key=None, repeat_cap=None):
    """Run one campaign and return a Result. `landscape` is the full dict, `pool` a set.

    `pool_sorted` is an optional precomputed sorted pool, so a sweep sorts it only once."""
    slots_total = rounds * slots_per_round
    if pool_sorted is None:
        pool_sorted = tuple(sorted(pool))
    if budget_mode not in ("slots", "useful"):
        raise ValueError("budget_mode must be 'slots' or 'useful', got %r" % (budget_mode,))
    if budget_mode == "useful" and not target_useful:
        raise ValueError("budget_mode='useful' needs target_useful")
    # The re-ask cap is a parameter because each re-ask costs an LLM policy an API call.
    reask_cap = MAX_REASKS if max_reasks is None else int(max_reasks)
    # Under the risk-free rule the cap is only a safety bound.
    if riskfree_rejection:
        reask_cap = int(riskfree_cap)
    n_cap_hits = 0
    n_repeat_cap_hits = 0
    # The screen filters what a policy may propose, so the oracle measures whatever is ordered,
    # dead variants included. See repdef/screen.py.
    screen = None
    if screen_q is not None:
        from repdef.screen import Screen
        screen = Screen(pool, screen_q, seed)
        if measurable is None:
            measurable = frozenset(landscape)
    orc = O.Oracle(landscape, pool, sigma, seed, failure_rate, measurable=measurable,
                   noise_model=noise_model, cv=cv, noise_floor=noise_floor, rng_key=rng_key)
    n_abandoned = 0
    replication_count = 0
    measured_before = set()

    # Budget mode. "slots": a fixed number of slots, and a dead measurement uses one.
    # "useful": run until a fixed number of viable readings is obtained. This adds rounds, and k
    # is per round, so low-q campaigns also get more champion re-measurements.
    last_round = rounds if budget_mode == "slots" else max_rounds_hard
    for rnd in range(1, last_round + 1):
        if budget_mode == "slots":
            if orc.slots_used >= slots_total:
                break
            budget = min(slots_per_round, slots_total - orc.slots_used)
        else:
            if orc.n_useful() >= target_useful:
                break
            budget = slots_per_round
        view = V.build(orc, rnd, last_round, slots_per_round, slots_total, pool_sorted,
                       screen=screen)
        picks = list(policy.propose(view, budget))[:budget]
        if not picks:
            # An empty or malformed reply forfeits the whole round: record one lost slot per slot,
            # so the next prompt shows the cost.
            for _lost in range(budget):
                orc.record_abandoned(rnd, "----", outcome=O.ROUND_LOST)

        filled = 0
        rejected_this_round = set()
        capped_this_round = set()
        for pick in picks:
            if filled >= budget:
                break
            seq, tries, capped_tries = pick, 0, 0
            while True:
                # Repeat cap: a candidate already ordered 1 + repeat_cap times is refused before
                # measurement (no slot, no draw) and the policy chooses again. Non-viable orders
                # follow the separate rejection rule.
                if repeat_cap is not None and orc.orders_of(seq) >= 1 + repeat_cap:
                    orc.record_capped(rnd, seq)
                    capped_this_round.add(seq)
                    capped_tries += 1
                    if capped_tries > riskfree_cap:
                        n_repeat_cap_hits += 1
                        n_abandoned += 1
                        orc.record_abandoned(rnd, seq, outcome=O.CAP_LOST)
                        seq = None
                        break
                    v2 = V.build(orc, rnd, last_round, slots_per_round, slots_total, pool_sorted,
                                 screen=screen)
                    again = policy.propose(v2, 1, exclude=rejected_this_round | capped_this_round,
                                           kind="replacement")
                    if not again:
                        n_abandoned += 1
                        orc.record_abandoned(rnd, seq, outcome=O.CAP_LOST)
                        seq = None
                        break
                    seq = again[0]
                    continue
                rec = orc.measure(seq, rnd)
                if rec.outcome != O.REJECTED:
                    break
                rejected_this_round.add(seq)
                tries += 1
                if tries > reask_cap:
                    n_abandoned += 1
                    if riskfree_rejection:
                        n_cap_hits += 1                 # a slot lost under the risk-free rule
                    # Record the lost slot, marking it CAP_LOST if the repeat cap was involved.
                    orc.record_abandoned(rnd, seq, outcome=O.CAP_LOST if capped_tries else O.ABANDONED)
                    seq = None
                    break
                # Re-ask for this slot only, telling the policy what it may not repeat.
                v2 = V.build(orc, rnd, last_round, slots_per_round, slots_total, pool_sorted,
                             screen=screen)
                again = policy.propose(v2, 1, exclude=rejected_this_round | capped_this_round,
                                       kind="replacement")
                if not again:
                    n_abandoned += 1
                    orc.record_abandoned(rnd, seq, outcome=O.CAP_LOST if capped_tries else O.ABANDONED)
                    seq = None
                    break
                seq = again[0]
            if seq is None:
                filled += 1              # the slot is gone even though nothing was measured
                continue
            if seq in measured_before:
                replication_count += 1
            measured_before.add(seq)
            filled += 1

    # -- nomination ------------------------------------------------------------------
    rounds_used = max((r.round for r in orc.history), default=0)
    final = V.build(orc, rounds_used or 1, last_round, slots_per_round, slots_total,
                    pool_sorted, screen=screen)
    agent_reason = None
    if nomination == "mean":
        nom = final.best_by_mean()
    elif nomination == "max":
        nom = final.best_by_max()
    elif nomination == "agent":
        # The agent names its own answer. The mean and max rules are recorded alongside for comparison.
        nom, agent_reason, _ = policy.nominate(final)
        if nom is None or nom not in landscape:
            nom = final.best_by_mean()          # unparseable answer falls back, and is logged
    elif nomination == "shrinkage":
        if prior == "empirical":
            _e = empirical_prior(final, sigma if noise_model != "multiplicative" else
                                 (lambda f: ((noise_floor ** 2) + (abs(f) * (cv or 0.0)) ** 2) ** 0.5))
            if _e is None:
                raise UnusableSigma("an empirical prior needs at least two measured variants")
            pm, pv = _e
        else:
            pm, pv = prior if prior else (0.0, 0.0)
        # Use the oracle's own noise model. Under multiplicative noise sigma depends on the level,
        # sqrt(floor^2 + (f*cv)^2), so it is passed as a callable.
        if noise_model == "multiplicative":
            _floor, _cv = noise_floor, (cv or 0.0)

            def _nom_sigma(f, _floor=_floor, _cv=_cv):
                return ((_floor ** 2) + (abs(f) * _cv) ** 2) ** 0.5

            nom = _shrinkage_nominate(final, _nom_sigma, pm, pv)
        else:
            nom = _shrinkage_nominate(final, sigma, pm, pv)
    else:
        raise ValueError("unknown nomination rule %r" % (nomination,))

    nom_true = landscape[nom] if nom is not None else 0.0
    best_meas = orc.best_true_measured()
    counts = collections.Counter(r.outcome for r in orc.history)
    # Both reference rules, so an agent nomination can be scored against each.
    ref_mean = final.best_by_mean()
    ref_max = final.best_by_max()
    # Shrinkage comparator, computed on every run from the campaign's own history. It is a reference,
    # not an achievable policy, since it knows the noise model. Sigma comes from the oracle's fields.
    if noise_model == "multiplicative":
        _f, _c = noise_floor, (cv or 0.0)

        def _ref_sigma(f, _f=_f, _c=_c):
            return ((_f ** 2) + (abs(f) * _c) ** 2) ** 0.5
    else:
        _ref_sigma = sigma

    # Primary comparator: an empirical-Bayes prior fitted from the campaign's own readings.
    # With no noise the comparator is undefined, so it is recorded as None with a reason.
    ref_shrinkage, ref_shrinkage_note = None, ""
    _noiseless = (not callable(_ref_sigma)) and _ref_sigma <= 0.0
    if _noiseless:
        ref_shrinkage_note = "no noise: a shrinkage comparator is undefined"
    else:
        _ep = empirical_prior(final, _ref_sigma, rel_floor=prior_rel_floor)
        if _ep is None:
            ref_shrinkage_note = "fewer than two measured variants"
        elif _ep[1] <= 0.0:
            ref_shrinkage_note = "empirical prior variance collapsed to zero"
        else:
            ref_shrinkage = _shrinkage_nominate(final, _ref_sigma, _ep[0], _ep[1])
    _ep = _ep if not _noiseless else None

    # Upper reference using a prior from the pool's true distribution, which no agent has.
    ref_shrinkage_oracle = None
    if prior and prior != "empirical" and not _noiseless:
        _pm, _pv = prior
        if _pv > 0.0 and (callable(_ref_sigma) or _ref_sigma > 0.0):
            ref_shrinkage_oracle = _shrinkage_nominate(final, _ref_sigma, _pm, _pv)
    n_useful = orc.n_useful()
    # Replication as a share of viable measurements. A weaker screen raises this at fixed k,
    # because replications land on the viable champion while exploration often does not.
    rep_useful = 0
    seen_u = set()
    for r in orc.history:
        if r.outcome == O.OK and r.seq in pool:
            if r.seq in seen_u:
                rep_useful += 1
            seen_u.add(r.seq)
    gb = global_best
    return Result(
        nominated=nom,
        nominated_true=nom_true,
        best_true_measured=best_meas,
        regression_loss=best_meas - nom_true,
        n_distinct=len(orc.measured_seqs()),
        n_ok=counts[O.OK],
        n_failed=counts[O.FAILED],
        n_rejected=counts[O.REJECTED],
        n_abandoned=n_abandoned,
        slots_used=orc.slots_used,
        replication_count=replication_count,
        history=tuple(orc.history),
        rounds=rounds,
        n_useful=n_useful,
        n_dead_measured=orc.n_dead_measured(),
        realized_precision=orc.realized_precision(),
        rounds_used=rounds_used,
        replication_fraction_of_useful=(rep_useful / n_useful) if n_useful else float("nan"),
        # Per-campaign decomposition:
        #   global_best - true(nominated) = exploration shortfall + selection shortfall
        exploration_shortfall=(gb - best_meas) if gb is not None else None,
        selection_shortfall=(best_meas - nom_true),
        ref_mean=ref_mean,
        ref_max=ref_max,
        ref_shrinkage=ref_shrinkage,
        ref_shrinkage_note=ref_shrinkage_note,
        ref_shrinkage_oracle=ref_shrinkage_oracle,
        empirical_prior_mean=(_ep[0] if _ep else None),
        empirical_prior_var=(_ep[1] if _ep else None),
        agent_reason=agent_reason,
        riskfree_rejection=bool(riskfree_rejection),
        rejection_cap_hits=n_cap_hits,
        repeat_cap=repeat_cap,
        n_capped=len(orc.refused),
        repeat_cap_hits=n_repeat_cap_hits,
    )
