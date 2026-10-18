"""Optional prompt tools computed from the agent's own history. None of them gives advice.

  LEDGER   every candidate with a reading, in order of first reading: count, mean and standard error.
  MENU     ten never-ordered candidates one letter away from the agent's three best by mean reading,
           ranked by an additive per-position model fitted to its readings, with keyed tie-breaks. With no
           readings yet, the ten are one-letter changes of the reference point in a keyed order.
  AT LIMIT the candidates the repeat cap now refuses: those already ordered 1 + repeat_cap times,
           failed orders included.
"""
import collections

from repdef import rng as R

MENU_SIZE = 10


def readings(rows):
    """{candidate: [readings]} in order of first reading, from (round, seq, outcome, observed) rows."""
    out = collections.OrderedDict()
    for (_rnd, seq, outcome, obs) in rows:
        if outcome == "ok":
            out.setdefault(seq, []).append(obs)
    return out


def ledger_text(rows):
    r = readings(rows)
    lines = ["MEASURED CANDIDATES, computed from the history above"]
    if not r:
        return "\n".join(lines + ["(no readings yet)"])
    lines.append("candidate  readings  mean     standard error")
    for seq, v in r.items():
        n = len(v)
        mean = sum(v) / n
        if n > 1:
            se = "%.3f" % ((sum((x - mean) ** 2 for x in v) / (n - 1) / n) ** 0.5)
        else:
            se = "not estimable from 1 reading"
        lines.append("%-9s  %-8d  %-7.3f  %s" % (seq, n, mean, se))
    return "\n".join(lines)


def _neighbours(seq, alphabet):
    return [seq[:i] + a + seq[i + 1:] for i in range(len(seq)) for a in alphabet if a != seq[i]]


def menu(rows, parent, alphabet, campaign_seed, rnd, n=MENU_SIZE):
    """(candidates, ranked): up to n never-ordered candidates, and whether a model ranked them."""
    ordered = {seq for (_r, seq, _o, _x) in rows}
    r = readings(rows)
    if not r:
        cands = [s for s in _neighbours(parent, alphabet) if s not in ordered]
        cands.sort(key=lambda s: R._u64("menu", campaign_seed, rnd, s))
        return cands[:n], False
    first = {seq: i for i, seq in enumerate(r)}
    means = {seq: sum(v) / len(v) for seq, v in r.items()}
    top = sorted(r, key=lambda s: (-means[s], first[s]))[:3]
    pool, seen = [], set()
    for t in top:
        for s in _neighbours(t, alphabet):
            if s not in ordered and s not in seen:
                seen.add(s)
                pool.append(s)
    allv = [x for v in r.values() for x in v]
    overall = sum(allv) / len(allv)
    site = collections.defaultdict(list)
    for seq, v in r.items():
        for i, c in enumerate(seq):
            site[(i, c)].extend(v)
    effect = {k: sum(v) / len(v) for k, v in site.items()}

    def score(s):
        return sum(effect.get((i, c), overall) for i, c in enumerate(s))
    pool.sort(key=lambda s: (-score(s), R._u64("menu", campaign_seed, rnd, s)))
    return pool[:n], True


def menu_text(cands, ranked, candidate_word="candidate"):
    lines = ["SUGGESTED NEW CANDIDATES"]
    if ranked:
        lines.append(
            "These are %d %ss you have not ordered, each one letter away from one of your three highest %ss by "
            "mean reading. They are ranked by an additive model fitted to your readings: a %s scores the sum, "
            "over its four positions, of the mean reading of the measured %ss with the same letter there, and a "
            "letter not yet measured at a position counts as the mean of all readings. You may ignore this list."
            % (len(cands), candidate_word, candidate_word, candidate_word, candidate_word))
    else:
        lines.append(
            "These are %d %ss you have not ordered, each one letter away from the reference point. There are no "
            "readings yet, so they are in no particular order. You may ignore this list."
            % (len(cands), candidate_word))
    lines += ["%d. %s" % (i + 1, s) for i, s in enumerate(cands)]
    return "\n".join(lines)


def at_limit(rows, repeat_cap):
    """Candidates ordered 1 + repeat_cap times (ok or failed orders; rejected ones do not count), sorted."""
    n = collections.Counter(seq for (_r, seq, outcome, _o) in rows if outcome in ("ok", "failed"))
    return sorted(s for s, k in n.items() if k >= 1 + repeat_cap)


def at_limit_text(seqs, candidate_word="candidate"):
    """The at-limit text block, or None when nothing is at the limit yet."""
    if not seqs:
        return None
    return ("AT THE LIMIT\nThese %ss have been ordered the maximum number of times and cannot be ordered "
            "again: %s." % (candidate_word, ", ".join(seqs)))
