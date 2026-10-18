"""Tests that the primary comparator never reads a true fitness value.

The comparator asks whether a simple rule applied to the agent's own data could have done better, so its
prior must come from the readings alone. Three checks: invariance (different truths with the same readings
give the same answer), recomputation (the prior equals a method-of-moments estimate from the readings) and
reflection (no true value is reachable from the comparator's arguments).
"""
import math, os, statistics as st, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from repdef import campaign as C, policies as P, view as V  # noqa: E402
from repdef.nk import NKLandscape  # noqa: E402
from tests.test_view_leak import reachable_floats  # noqa: E402

CV, FLOOR, GB1_MAX = 0.073, (1 / 557) / (285 / 557), 8.762


def sig(f):
    return math.sqrt(FLOOR ** 2 + (abs(f) * CV) ** 2)


def constructed(readings):
    obs = tuple(V.Observation(1, s, "ok", x) for s, xs in readings.items() for x in xs)
    pool = set(readings)
    return V.CampaignView(obs, pool, 2, 15, 4, len(obs), 60, tuple(sorted(pool)),
                          campaign_seed=0, screen=None)


def landscape(scale=1.0, shift=0.0):
    nk = NKLandscape(k=1, seed=1, threshold_percentile=93.0, dist="uniform")
    f = GB1_MAX / max(nk.fitness.values())
    return {k: (v * f) * scale + shift for k, v in nk.fitness.items()}, nk.pool


class TheFairComparatorCannotSeeTheTruth(unittest.TestCase):
    def test_1_invariance_same_readings_different_truth_same_answer(self):
        # The comparator is a function of the view and the noise model, so changing every true value
        # must not move it.
        v = constructed({"AAAA": [6.9, 7.1], "BBBB": [7.4], "CCCC": [6.2, 6.4, 6.3]})
        ep = C.empirical_prior(v, sig)
        first = C._shrinkage_nominate(v, sig, ep[0], ep[1])
        for scale, shift in ((1.0, 0.0), (3.0, 0.0), (1.0, 100.0), (0.1, -2.0)):
            fit, pool = landscape(scale, shift)
            vals = [fit[s] for s in pool]
            oracle = (st.mean(vals), st.variance(vals))
            # The fair comparator, given the same view, must be unchanged whatever the truth is.
            self.assertEqual(C._shrinkage_nominate(v, sig, ep[0], ep[1]), first)
            # The oracle comparator takes the true-pool prior, so it can move.
            C._shrinkage_nominate(v, sig, oracle[0], oracle[1])

    def test_1b_the_oracle_prior_actually_changes_the_answer_somewhere(self):
        # The oracle prior must change the answer somewhere, or the invariance check would show nothing.
        fit, pool = landscape()
        ps = tuple(sorted(pool))
        vals = [fit[s] for s in pool]
        oracle = (st.mean(vals), st.variance(vals))
        pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
        diff = 0
        for i in range(120):
            r = C.run(fit, pool, pol, 0.0, 771_000 + i, 0.15, pool_sorted=ps,
                      nomination="mean", prior=oracle, noise_model="multiplicative",
                      cv=CV, noise_floor=FLOOR)
            if r.ref_shrinkage != r.ref_shrinkage_oracle:
                diff += 1
        self.assertGreater(diff, 0, "the fair and oracle comparators never disagreed, so either the "
                                    "fair one is still using the oracle prior or the leak is inert")

    def test_2_the_prior_equals_a_recomputation_from_the_readings_alone(self):
        readings = {"AAAA": [6.9, 7.1], "BBBB": [7.4], "CCCC": [6.2, 6.4, 6.3]}
        v = constructed(readings)
        got = C.empirical_prior(v, sig)
        means = [st.mean(xs) for xs in readings.values()]
        pm = st.mean(means)
        spread = st.variance(means)
        noise = st.mean([sig(st.mean(xs)) ** 2 / len(xs) for xs in readings.values()])
        self.assertAlmostEqual(got[0], pm, places=12)
        self.assertAlmostEqual(got[1], max(spread - noise, 0.01 * noise), places=12)

    def test_2b_the_prior_variance_subtracts_measurement_noise(self):
        # Using the raw spread would overstate how much real variation there is to shrink towards,
        # because the observed spread already contains the noise.
        readings = {"A": [6.0], "B": [7.0], "C": [8.0]}
        v = constructed(readings)
        pm, pv = C.empirical_prior(v, sig)
        raw = st.variance([6.0, 7.0, 8.0])
        self.assertLess(pv, raw)

    def test_2c_it_returns_None_with_fewer_than_two_variants(self):
        self.assertIsNone(C.empirical_prior(constructed({"AAAA": [6.9, 7.1]}), sig))
        self.assertIsNone(C.empirical_prior(constructed({}), sig))

    def test_2d_the_variance_is_always_positive(self):
        # A degenerate campaign where every variant reads the same would give spread 0 and a negative
        # variance after subtraction, and a non-positive prior variance raises in the nominator.
        pm, pv = C.empirical_prior(constructed({"A": [7.0], "B": [7.0], "C": [7.0]}), sig)
        self.assertGreater(pv, 0.0)

    def test_3_reflection_no_true_value_is_reachable_from_the_comparators_arguments(self):
        fit, pool = landscape()
        ps = tuple(sorted(pool))
        truths = {round(v, 9) for v in fit.values()}
        seen = {}

        orig = C._shrinkage_nominate

        def spy(view, sigma, pm, pv):
            # Everything the comparator is given. If a true value is reachable from here, the
            # comparator could in principle use it.
            for path, f in reachable_floats((view, pm, pv)):
                if round(f, 9) in truths:
                    seen.setdefault(path, f)
            return orig(view, sigma, pm, pv)

        C._shrinkage_nominate = spy
        try:
            pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
            for i in range(5):
                C.run(fit, pool, pol, 0.0, 772_000 + i, 0.15, pool_sorted=ps,
                      nomination="shrinkage", prior="empirical",
                      noise_model="multiplicative", cv=CV, noise_floor=FLOOR)
        finally:
            C._shrinkage_nominate = orig
        self.assertEqual(seen, {}, "a true fitness value is reachable from the fair comparator's "
                                  "arguments: %s" % seen)

    def test_4_a_campaign_needs_no_prior_argument_to_get_a_comparator(self):
        # With no prior passed, the fair comparator still exists and the oracle reference is absent.
        fit, pool = landscape()
        ps = tuple(sorted(pool))
        pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
        r = C.run(fit, pool, pol, 0.0, 773_001, 0.15, pool_sorted=ps, nomination="mean",
                  noise_model="multiplicative", cv=CV, noise_floor=FLOOR)
        self.assertIsNotNone(r.ref_shrinkage)
        self.assertIsNone(r.ref_shrinkage_oracle)
        self.assertIsNotNone(r.empirical_prior_mean)


if __name__ == "__main__":
    unittest.main(verbosity=2)
