"""Aggregate metrics with standard errors, including paired differences for seed-aligned arms."""

import math
import statistics as st


def mean_se(xs):
    """Return (mean, standard error, n). SE is None for n < 2."""
    xs = list(xs)
    n = len(xs)
    if n == 0:
        return (float("nan"), None, 0)
    if n == 1:
        return (xs[0], None, 1)
    return (st.mean(xs), st.stdev(xs) / math.sqrt(n), n)


def paired_diff(a, b):
    """Mean of (a - b) with its paired standard error. `a` and `b` must be aligned by seed."""
    a, b = list(a), list(b)
    if len(a) != len(b):
        raise ValueError("paired comparison needs aligned samples: %d vs %d" % (len(a), len(b)))
    d = [x - y for x, y in zip(a, b)]
    m, se, n = mean_se(d)
    return {"diff": m, "se": se, "n": n,
            "sd_of_diff": st.stdev(d) if n > 1 else None,
            "correlation": _corr(a, b)}


def _corr(a, b):
    n = len(a)
    if n < 3:
        return None
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da == 0 or db == 0:
        return None
    return num / (da * db)


def rank_of(landscape, pool, seq):
    """1-based rank of `seq` inside the pool by true fitness, 1 being best. Ties share the best rank."""
    if seq is None:
        return None
    t = landscape[seq]
    return 1 + sum(1 for s in pool if landscape[s] > t)


def optimal_match(results, optimal_k, slots_per_round=4):
    """Fraction of rounds whose replication count equals the optimal k, with an SE over campaigns.

    `optimal_k` may be an int or a set; under ties any of the tied values counts as a match."""
    want = {optimal_k} if isinstance(optimal_k, int) else set(optimal_k)
    per_campaign = []
    for r in results:
        by_round = {}
        seen = set()
        for rec in r.history:
            if not rec.slot_consumed:
                continue
            by_round.setdefault(rec.round, 0)
            if rec.seq in seen:
                by_round[rec.round] += 1
            seen.add(rec.seq)
        if not by_round:
            continue
        hit = sum(1 for v in by_round.values() if v in want)
        per_campaign.append(hit / len(by_round))
    return mean_se(per_campaign)


def replication_fraction(results):
    """Fraction of consumed slots that re-measured an already-measured sequence."""
    vals = []
    for r in results:
        if r.slots_used:
            vals.append(r.replication_count / r.slots_used)
    return mean_se(vals)


def summarise(results, landscape=None, pool=None, global_max=None):
    """Every headline number for one cell, each with its SE."""
    out = {
        "true_of_nominated": mean_se([r.nominated_true for r in results]),
        "best_true_measured": mean_se([r.best_true_measured for r in results]),
        "regression_loss": mean_se([r.regression_loss for r in results]),
        "n_distinct": mean_se([r.n_distinct for r in results]),
        "n_ok": mean_se([r.n_ok for r in results]),
        "n_failed": mean_se([r.n_failed for r in results]),
        "n_rejected": mean_se([r.n_rejected for r in results]),
        "n_abandoned": mean_se([r.n_abandoned for r in results]),
        "slots_used": mean_se([r.slots_used for r in results]),
        "replication_fraction": replication_fraction(results),
        "n_campaigns": len(results),
    }
    if global_max is not None:
        # Loss measured against the best value in the whole pool.
        out["regression_loss_global"] = mean_se(
            [global_max - r.nominated_true for r in results])
    if landscape is not None and pool is not None:
        out["rank_of_nominated"] = mean_se(
            [rank_of(landscape, pool, r.nominated) for r in results])
    return out


def power_n(sd_of_diff, effect, alpha=0.05, power=0.80):
    """Campaigns needed per arm to resolve `effect` given the SD of the relevant contrast.

    For a paired design pass the SD of the per-campaign differences; for an unpaired one
    pass sqrt(2) times the per-campaign SD. Normal approximation, two-sided."""
    if effect == 0 or sd_of_diff is None or sd_of_diff <= 0:
        return None
    z_a, z_b = 1.959963985, 0.8416212336
    return int(math.ceil(((z_a + z_b) * sd_of_diff / abs(effect)) ** 2))
