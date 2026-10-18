"""Tests that the shrinkage nomination is actually applied and differs from the mean and max rules where it should.

A scalar sigma of zero or a degenerate prior raises instead of falling back to the mean rule, a
level-dependent sigma is applied per reading, and constructed histories show the cases where shrinkage must
disagree with max-mean and max-single.
"""
import math, statistics as st, unittest
from repdef import campaign as C, policies as P
from repdef.nk import NKLandscape

CV, FLOOR, GB1_MAX = 0.073, (1 / 557) / (285 / 557), 8.762


def landscape():
    nk = NKLandscape(k=1, seed=1, threshold_percentile=93.0, dist="exponential")
    f = GB1_MAX / max(nk.fitness.values())
    return {k: v * f for k, v in nk.fitness.items()}, nk.pool


class ShrinkageIsNotSilentlyTheMeanRule(unittest.TestCase):
    def setUp(self):
        self.fit, self.pool = landscape()
        self.ps = tuple(sorted(self.pool))
        vals = [self.fit[s] for s in self.pool]
        self.prior = (st.mean(vals), st.variance(vals))
        self.pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")

    def run_one(self, nomination, seed):
        return C.run(self.fit, self.pool, self.pol, 0.0, seed, 0.15, pool_sorted=self.ps,
                     nomination=nomination, prior=self.prior,
                     noise_model="multiplicative", cv=CV, noise_floor=FLOOR)

    def test_shrinkage_and_mean_disagree_on_some_campaign(self):
        # If the two rules never disagree over many campaigns, one of them is not being applied.
        diff = 0
        for i in range(200):
            a = self.run_one("shrinkage", 4_000_000 + i)
            b = self.run_one("mean", 4_000_000 + i)
            if a.nominated != b.nominated:
                diff += 1
        self.assertGreater(diff, 0,
                           "shrinkage and mean agreed on all 200 campaigns, so the shrinkage "
                           "nomination is almost certainly falling back to the mean")

    def test_a_scalar_zero_sigma_raises_instead_of_falling_back(self):
        view = _one_view(self)
        with self.assertRaises(C.UnusableSigma):
            C._shrinkage_nominate(view, 0.0, self.prior[0], self.prior[1])

    def test_a_degenerate_prior_raises(self):
        view = _one_view(self)
        with self.assertRaises(C.UnusableSigma):
            C._shrinkage_nominate(view, 0.5, self.prior[0], 0.0)

    def test_a_callable_sigma_is_used_per_variant(self):
        # Two different sigma functions must be able to produce two different nominations, or the
        # callable is being ignored.
        view = _one_view(self)
        tight = C._shrinkage_nominate(view, lambda f: 1e-6, *self.prior)
        loose = C._shrinkage_nominate(view, lambda f: 50.0, *self.prior)
        self.assertIsNotNone(tight)
        self.assertIsNotNone(loose)
        # With a near-zero sigma the data dominate and shrinkage matches the mean rule; with a huge
        # sigma the prior dominates and the ordering is driven by n. They must not be identical for
        # every view, so assert over several.
        agree = 0
        for i in range(40):
            v = _one_view(self, seed=5_000_000 + i)
            if C._shrinkage_nominate(v, lambda f: 1e-6, *self.prior) == \
               C._shrinkage_nominate(v, lambda f: 50.0, *self.prior):
                agree += 1
        self.assertLess(agree, 40, "the sigma callable does not affect the nomination")

    def test_the_nomination_sigma_matches_the_oracle_formula(self):
        # The rule must use the noise the measurements carried, from the same formula as the oracle.
        f = 3.7
        want = math.sqrt(FLOOR ** 2 + (abs(f) * CV) ** 2)
        got = None
        orig = C._shrinkage_nominate

        def spy(view, sigma, pm, pv):
            nonlocal got
            got = sigma(f) if callable(sigma) else sigma
            return orig(view, sigma, pm, pv)
        C._shrinkage_nominate = spy
        try:
            self.run_one("shrinkage", 6_000_001)
        finally:
            C._shrinkage_nominate = orig
        self.assertAlmostEqual(got, want, places=12)

    def test_with_no_replication_the_two_rules_must_agree(self):
        # With no replication, shrinkage and max agree on this landscape. This is not general: under a
        # level-dependent sigma the posterior is not monotone in a single reading (see the non-monotone test
        # below), so the agreement holds only because the turning point lies outside the reachable readings.
        pol0 = P.GreedyWithReplication(0, 0, "pool", "fresh_pool")
        for i in range(30):
            a = C.run(self.fit, self.pool, pol0, 0.0, 7_000_000 + i, 0.15, pool_sorted=self.ps,
                      nomination="shrinkage", prior=self.prior,
                      noise_model="multiplicative", cv=CV, noise_floor=FLOOR)
            self.assertEqual(a.nominated, a.ref_max)


def _one_view(tc, seed=4_000_000):
    """A finished campaign's view, for testing the nominator directly."""
    holder = {}
    orig = C._shrinkage_nominate

    def grab(view, sigma, pm, pv):
        holder["v"] = view
        return orig(view, sigma, pm, pv)
    C._shrinkage_nominate = grab
    try:
        C.run(tc.fit, tc.pool, tc.pol, 0.0, seed, 0.15, pool_sorted=tc.ps,
              nomination="shrinkage", prior=tc.prior,
              noise_model="multiplicative", cv=CV, noise_floor=FLOOR)
    finally:
        C._shrinkage_nominate = orig
    return holder["v"]


if __name__ == "__main__":
    unittest.main(verbosity=2)


# --------------------------------------------------------------------------------------------
# Tests on constructed histories, which depend on no landscape, seed or policy.
from repdef import view as V


def constructed(readings, pool=None, rounds=15, slots=4):
    """A CampaignView holding exactly the readings given, as {seq: [values]}."""
    obs, rnd = [], 1
    for seq, xs in readings.items():
        for x in xs:
            obs.append(V.Observation(rnd, seq, "ok", x))
    pool = pool or set(readings)
    return V.CampaignView(tuple(obs), pool, 2, rounds, slots, len(obs), rounds * slots,
                          tuple(sorted(pool)), campaign_seed=0, screen=None)


class TheTwoTestsThatWouldHaveCaughtItOnDayOne(unittest.TestCase):
    def test_unequal_replicate_counts_make_shrinkage_differ_from_max_mean(self):
        # A lucky singleton at 5.0 against a well-measured 4.6. Max-mean takes the singleton;
        # shrinkage distrusts a single reading and takes the variant with four.
        v = constructed({"AAAA": [5.0], "BBBB": [4.6, 4.6, 4.6, 4.6]})
        prior_mean, prior_var = 1.0, 1.0
        shrunk = C._shrinkage_nominate(v, 0.9, prior_mean, prior_var)
        self.assertEqual(v.best_by_mean(), "AAAA", "fixture no longer exercises the contrast")
        self.assertEqual(shrunk, "BBBB")
        self.assertNotEqual(shrunk, v.best_by_mean())

    def test_heteroscedastic_sigma_makes_shrinkage_differ_from_max_single(self):
        # Under sigma(f) = sqrt(floor^2 + (f*cv)^2) a HIGH reading is noisier, so it is shrunk
        # harder. With a big enough spread the top single reading loses to a lower, quieter one.
        # This is the case where a constant and a level-dependent sigma give different answers.
        def sig(f):
            return math.sqrt(0.0035 ** 2 + (abs(f) * 0.9) ** 2)

        v = constructed({"HIGH": [60.0], "MID": [15.0]})
        self.assertEqual(v.best_by_max(), "HIGH", "fixture no longer exercises the contrast")
        het = C._shrinkage_nominate(v, sig, 1.0, 1.0)
        hom = C._shrinkage_nominate(v, sig(15.0), 1.0, 1.0)
        self.assertEqual(het, "MID", "a level-dependent sigma should shrink the noisy 60 below 15")
        self.assertEqual(hom, "HIGH", "with one shared sigma the top single reading must win")
        self.assertNotEqual(het, hom)

    def test_the_posterior_is_non_monotone_under_a_level_dependent_sigma(self):
        # Under a level-dependent sigma the posterior is not monotone in the reading, which is why the
        # k=0 agreement depends on the parameters.
        def post(m, n, pm, pv, cv=0.9, floor=0.0035):
            s = math.sqrt(floor ** 2 + (abs(m) * cv) ** 2)
            return (pm / pv + n * m / s ** 2) / (1.0 / pv + n / s ** 2)
        vals = [post(m / 10.0, 1, 1.0, 1.0) for m in range(1, 1000)]
        self.assertFalse(all(b >= a for a, b in zip(vals, vals[1:])),
                         "posterior is monotone here, so this fixture no longer demonstrates the "
                         "non-monotonicity the amendment describes")
        # With a constant sigma the posterior is monotone in the reading.
        flat = [post(m / 10.0, 1, 1.0, 1.0, cv=0.0, floor=0.5) for m in range(1, 1000)]
        self.assertTrue(all(b > a for a, b in zip(flat, flat[1:])))
