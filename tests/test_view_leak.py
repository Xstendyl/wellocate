"""Tests that no true fitness value is reachable from the campaign view.

The view's whole object graph is walked by reflection (every attribute, slot and container element, to a
bounded depth), and no reachable float may be a true value. The test runs at sigma > 0, where an observed
reading equal to a true value has probability zero in practice.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from repdef import campaign as C, landscape as L, policies as P, view as V, oracle as O  # noqa: E402


def reachable_floats(obj, max_depth=6):
    """Every float reachable from `obj`, with the path that reached it."""
    found, seen = [], set()

    def walk(o, path, depth):
        if depth > max_depth:
            return
        oid = id(o)
        if oid in seen:
            return
        if isinstance(o, (str, bytes, int, bool, type(None))):
            return
        seen.add(oid)
        if isinstance(o, float):
            found.append((path, o))
            return
        if isinstance(o, dict):
            for k, v in o.items():
                walk(k, path + "[key]", depth + 1)
                walk(v, path + "[%r]" % (k,), depth + 1)
            return
        if isinstance(o, (list, tuple, set, frozenset)):
            for i, v in enumerate(o):
                walk(v, path + "[%d]" % i, depth + 1)
            return
        for name in getattr(type(o), "__slots__", ()) or ():
            if hasattr(o, name):
                walk(getattr(o, name), path + "." + name, depth + 1)
        for name, v in vars(o).items() if hasattr(o, "__dict__") else ():
            walk(v, path + "." + name, depth + 1)

    walk(obj, "view", 0)
    return found


class TestTheViewLeaksNoTruth(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            cls.ls = L.load("phoq")
        except L.LandscapeError as e:
            raise unittest.SkipTest(str(e))
        cls.ps = tuple(sorted(cls.ls.pool))

    def _view_after_a_real_campaign(self, sigma=8.48):
        orc = O.Oracle(self.ls.fitness, self.ls.pool, sigma, 11, 0.15)
        pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
        for rnd in range(1, 9):
            v = V.build(orc, rnd, 15, 4, 60, self.ps)
            for s in pol.propose(v, 4):
                orc.measure(s, rnd)
        return V.build(orc, 9, 15, 4, 60, self.ps), orc

    def test_no_reachable_float_is_a_true_value(self):
        """No float reachable from the view is a true value."""
        view, orc = self._view_after_a_real_campaign()
        truths = set(self.ls.fitness.values())
        floats = reachable_floats(view)
        self.assertGreater(len(floats), 5, "the walk found almost nothing, so it is not "
                                           "actually traversing the view")
        leaks = [(p, x) for p, x in floats if x in truths]
        self.assertEqual(leaks, [], "true fitness reachable from the view at: %s"
                         % (leaks[:5],))

    def test_the_walk_would_catch_a_leak(self):
        """The walk catches a true value planted two containers deep."""
        view, orc = self._view_after_a_real_campaign()
        truths = set(self.ls.fitness.values())
        planted = orc.history[0].true
        self.assertIn(planted, truths)

        class Sneaky(object):
            __slots__ = ("inner",)

            def __init__(self, inner):
                self.inner = inner

        # Buried two containers deep inside an innocuous-looking wrapper.
        bait = Sneaky({"notes": [("harmless", planted)]})
        floats = reachable_floats(bait)
        self.assertTrue(any(x in truths for _, x in floats),
                        "the reflection walk failed to reach a planted true value")

    def test_the_view_holds_no_reference_to_the_oracle_or_landscape(self):
        view, orc = self._view_after_a_real_campaign()
        for name in getattr(type(view), "__slots__", ()):
            val = getattr(view, name, None)
            self.assertNotIsInstance(val, O.Oracle)
            # the full 160k table must not be reachable as a mapping
            if isinstance(val, dict):
                self.assertLess(len(val), 1000, "%s looks like the landscape table" % name)

    def test_observation_has_no_true_field(self):
        self.assertNotIn("true", V.Observation._fields)
        self.assertNotIn("replicate_index", V.Observation._fields)

    def test_history_length_matches_but_content_is_reduced(self):
        view, orc = self._view_after_a_real_campaign()
        self.assertEqual(len(view.history), len(orc.history))
        self.assertTrue(all(len(o) == 4 for o in view.history))
        self.assertEqual(len(orc.history[0]), 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
