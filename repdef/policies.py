"""Fixed (non-LLM) search policies, including the random-replication control.

`explore_scope` sets where exploration looks:

    "pool"       Hamming-1 neighbours restricted to the viable pool.
    "landscape"  the full Hamming-1 shell, filtered only by the prescreen.

`fallback` sets how a short candidate list is filled: "fresh_pool" draws distinct unmeasured
pool members; "any_pool" draws from the pool with replacement, so an exploration slot can
become a replication.
"""

from repdef import rng as R

AA = "ACDEFGHIKLMNPQRSTVWY"
_NBR_CACHE = {}


def neighbours(seq):
    """The 76 Hamming-1 neighbours over the amino-acid alphabet (cached)."""
    got = _NBR_CACHE.get(seq)
    if got is None:
        got = tuple(seq[:i] + a + seq[i + 1:] for i in range(len(seq)) for a in AA
                    if a != seq[i])
        _NBR_CACHE[seq] = got
    return got


# `neighbours` assumes the amino acids. Landscapes spelled with other letters use `neighbours_over`
# with the alphabet read from the landscape itself.
_NBR_ALPHA_CACHE = {}
_ALPHABET_OF = {}


def neighbours_over(seq, alphabet):
    """The Hamming-1 neighbours of `seq` over `alphabet`."""
    key = (seq, alphabet)
    got = _NBR_ALPHA_CACHE.get(key)
    if got is None:
        got = tuple(seq[:i] + a + seq[i + 1:] for i in range(len(seq)) for a in alphabet if a != seq[i])
        _NBR_ALPHA_CACHE[key] = got
    return got


def alphabet_of(strings):
    """The letters a landscape is spelled with, read from its own strings.

    Cached by object id; the cache holds a reference so the id is not reused."""
    hit = _ALPHABET_OF.get(id(strings))
    if hit is not None and hit[0] is strings:
        return hit[1]
    letters = "".join(sorted(set("".join(strings))))
    _ALPHABET_OF[id(strings)] = (strings, letters)
    return letters


class Policy(object):
    """propose(view, n_slots, exclude) -> list of sequences, at most n_slots long."""

    name = "policy"

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        """`kind="round"` is a normal round's allocation. `kind="replacement"` asks for
        exploration picks only, to refill a slot without adding a replication."""
        raise NotImplementedError

    def replication_slots(self, view):
        """How many of this round's slots this policy intends as re-measurements. Used by
        the optimal-match metric. A policy that cannot say returns None."""
        return None


def _pick_distinct(pool_sorted, n, forbidden, *key):
    """`n` distinct pool members avoiding `forbidden`, by keyed rejection sampling.

    `forbidden` is small relative to the pool, so a draw is rarely rejected."""
    out, seen, i, limit = [], set(), 0, 64 * max(n, 1) + 64
    m = len(pool_sorted)
    if m == 0:
        return out
    while len(out) < n and i < limit:
        s = pool_sorted[R._u64("pd", i, *key) % m]
        if s not in forbidden and s not in seen:
            out.append(s)
            seen.add(s)
        i += 1
    return out


def _cold_start(view, n_slots, seed, exclude):
    """Round 1, with no champion. Distinct sequences drawn uniformly from the pool.

    Keyed on the campaign seed and round, so every policy in a campaign opens on the same sequences."""
    return _pick_distinct(view.pool_sorted, n_slots, set(exclude),
                          "cold", seed, view.campaign_seed, view.current_round)


class RandomPolicy(Policy):
    """Distinct, previously unmeasured sequences drawn uniformly from the pool."""

    name = "random"

    def __init__(self, seed=0):
        self.seed = seed

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        taken = view.measured() | set(exclude)
        return _pick_distinct(view.pool_sorted, n_slots, taken,
                              "rand", self.seed, view.campaign_seed, view.current_round)

    def replication_slots(self, view):
        return 0


class GreedyWithReplication(Policy):
    """k slots re-measure the champion, n-k explore its neighbourhood.

    The champion is the sequence with the highest mean observed reading."""

    def __init__(self, k, seed=0, explore_scope="pool", fallback="fresh_pool"):
        if explore_scope not in ("pool", "landscape"):
            raise ValueError("explore_scope must be 'pool' or 'landscape'")
        if fallback not in ("fresh_pool", "any_pool"):
            raise ValueError("fallback must be 'fresh_pool' or 'any_pool'")
        self.k = k
        self.seed = seed
        self.explore_scope = explore_scope
        self.fallback = fallback
        self.name = "greedy_k%d_%s_%s" % (k, explore_scope, fallback)

    # None means the amino-acid alphabet. See `alphabet_of`.
    alphabet = None

    def _neighbours(self, seq):
        return neighbours(seq) if self.alphabet is None else neighbours_over(seq, self.alphabet)

    def champion(self, view):
        return view.best_by_mean()

    def replication_slots(self, view):
        return 0 if self.champion(view) is None else self.k

    def _explore(self, view, champ, need, exclude):
        if need <= 0:
            return []
        seen = view.measured() | set(exclude)
        nb = self._neighbours(champ)
        if self.explore_scope == "pool":
            cand = [x for x in nb if x in view.pool and x not in seen]
        else:
            # The whole shell minus whatever the prescreen catches. With a perfect screen
            # this equals the "pool" branch.
            cand = [x for x in nb if x not in seen and view.screen.passes(x)]
        cand.sort()
        take = R.sample_without_replacement(
            cand, min(need, len(cand)), "expl", self.seed, view.campaign_seed,
            view.current_round, champ)
        if len(take) < need:
            if self.fallback == "fresh_pool":
                take += _pick_distinct(view.pool_sorted, need - len(take),
                                       seen | set(take),
                                       "fb", self.seed, view.campaign_seed,
                                       view.current_round, champ)
            else:
                # With replacement: may re-pick a measured sequence or the champion.
                ps = view.pool_sorted
                while len(take) < need:
                    take.append(R.choice(ps, "fb", self.seed, view.campaign_seed,
                                         view.current_round, champ, len(take)))
        return take

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        champ = self.champion(view)
        if champ is None:
            return _cold_start(view, n_slots, self.seed, exclude)
        if kind == "replacement":
            # Refilling one slot must not become an extra replication.
            return self._explore(view, champ, n_slots, exclude)
        picks = [champ] * min(self.k, n_slots)
        return picks + self._explore(view, champ, n_slots - len(picks), exclude)


class GreedyRandomReplication(GreedyWithReplication):
    """Control policy: like GreedyWithReplication, but the k replication slots re-measure a
    uniformly chosen already-measured sequence instead of the champion.

    It spends the same number of slots on re-measurement, so it separates aiming replication at
    the selection decision from simply exploring less."""

    def __init__(self, k, seed=0, explore_scope="pool", fallback="fresh_pool"):
        GreedyWithReplication.__init__(self, k, seed, explore_scope, fallback)
        self.name = "greedy_randrep_k%d_%s_%s" % (k, explore_scope, fallback)

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        champ = self.champion(view)
        if champ is None:
            return _cold_start(view, n_slots, self.seed, exclude)
        if kind == "replacement":
            return self._explore(view, champ, n_slots, exclude)
        have = sorted(view.with_readings())
        picks = []
        for i in range(min(self.k, n_slots)):
            pick = R.choice(have, "randrep", self.seed, view.campaign_seed,
                            view.current_round, i)
            if pick is not None:
                picks.append(pick)
        # Exploration still walks the champion's neighbourhood; only the replication target differs.
        return picks + self._explore(view, champ, n_slots - len(picks), exclude)
