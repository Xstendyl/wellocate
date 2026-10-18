"""Scripted baselines. Each is a factory: called with a landscape (repdef.envs.Env), it returns a policy with
`propose(view, n_slots, exclude, kind)`. Every baseline nominates by the paper's registered shrinkage rule.

  random         distinct, untried candidates drawn uniformly from the whole design space, viable or not.
  guessing(k)    the paper's guessing rule (FairGreedyAlphabet): re-test the current best k times per round and
                 try untried neighbours of it with the rest, guessing viability as an agent must.
  informed(k)    the same rule told which candidates are viable (PoolGreedyAlphabet), an upper reference.
  model_guided   the paper's model-guided policy: an additive model of its own readings proposes
                 candidates; k = 1 re-test per round, and the last three rounds re-test the top 4.
  confirmation(c)  simple confirmation, a reference point and not tuned: guessing at k = 0, then the last c
                 slots re-measure the top candidates by mean reading, one slot each per round (c = 4, 8 or 12
                 is one, two or three final rounds). It trails the guessing rule on the grid.
The first four are the policy classes the paper ran, imported unchanged from its scripts.
"""
import os
import sys

from repdef import policies as P
from repdef import rng as R

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import fair_reference_curve as FRC                    # noqa: E402
import model_guided_0an4 as MG                        # noqa: E402
import yardsticks_0am as Y                            # noqa: E402


_SPACES = {}


def _space(env):
    """The sorted design space and its alphabet, built once per landscape. P.alphabet_of caches by object, so
    building a fresh tuple per episode would keep every copy alive."""
    hit = _SPACES.get(env.label)
    if hit is None or hit[0] is not env:
        if len(_SPACES) >= 16:
            _SPACES.clear()
        space = tuple(sorted(env.fit))
        hit = _SPACES[env.label] = (env, space, P.alphabet_of(space))
    return hit[1], hit[2]


class RandomGuess(P.Policy):
    name = "random"

    def __init__(self, env):
        self.space, _a = _space(env)

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        seen = {o.seq for o in view.history} | set(exclude)
        out, i = [], 0
        while len(out) < n_slots and i < 10_000:
            s = self.space[R._u64("wellocate_random", view.campaign_seed, view.current_round, len(view.history),
                                  i) % len(self.space)]
            if s not in seen and s not in out:
                out.append(s)
            i += 1
        return out


class Confirmation(P.Policy):
    """Guessing at k = 0, then the last `confirm_slots` slots re-measure the top candidates by mean reading."""

    def __init__(self, env, confirm_slots=4):
        space, alpha = _space(env)
        self.inner = Y.FairGreedyAlphabet(0, env.anchor, space, alpha, seed=0)
        self.confirm_slots = int(confirm_slots)
        self.name = "confirmation_%d" % self.confirm_slots

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        confirm_rounds = -(-self.confirm_slots // view.slots_per_round)
        if kind == "round" and view.current_round > view.total_rounds - confirm_rounds:
            r = view.readings()
            top = sorted(r, key=lambda s: (-sum(r[s]) / len(r[s]), s))[:n_slots]
            if len(top) < n_slots:
                top += [c for c in self.inner.propose(view, n_slots - len(top), exclude, "replacement")
                        if c not in top]
            return top[:n_slots]
        return self.inner.propose(view, n_slots, exclude, kind)


def random():
    return lambda env: RandomGuess(env)


def guessing(k):
    def make(env):
        space, alpha = _space(env)
        return Y.FairGreedyAlphabet(k, env.anchor, space, alpha, seed=0)
    make.label = "guessing k=%d" % k
    return make


def informed(k):
    def make(env):
        space, _a = _space(env)
        return FRC.PoolGreedyAlphabet(k, space)
    make.label = "informed k=%d" % k
    return make


def model_guided(k=1, confirm=True):
    def make(env):
        _s, alpha = _space(env)
        return MG.ModelGuided(env.anchor, alpha, k, confirm)
    make.label = "model-guided k=%d%s" % (k, " with confirmation" if confirm else "")
    return make


def confirmation(confirm_slots=4):
    def make(env):
        return Confirmation(env, confirm_slots)
    make.label = "confirmation, %d slots" % confirm_slots
    return make
