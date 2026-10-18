"""Tests for the pipeline's contracts.

Covers oracle semantics, seed-keyed pairing, campaign accounting, policies, metrics, the statistics helpers
and the keyed random-number helpers.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from repdef import campaign as C, landscape as L, metrics as M  # noqa: E402
from repdef import oracle as O, policies as P, rng as R, view as V  # noqa: E402

TOY = {"AAAA": 10.0, "AAAC": 5.0, "AAAD": 1.0, "CAAA": 8.0, "DAAA": 0.0}
TOY_POOL = frozenset({"AAAA", "AAAC", "CAAA"})       # AAAD, DAAA are below threshold


class TestOracleSemantics(unittest.TestCase):

    def test_a_rejection_consumes_no_slot_and_no_draw(self):
        """A rejection consumes no slot and no noise draw, so invalid orders cannot shift the paired noise field."""
        orc = O.Oracle(TOY, TOY_POOL, 1.0, 1, 0.0)
        r = orc.measure("AAAD", 1)
        self.assertEqual(r.outcome, O.REJECTED)
        self.assertFalse(r.slot_consumed)
        self.assertEqual(orc.slots_used, 0)
        # the next real measurement must get replicate_index 0, proving no draw was spent
        r2 = orc.measure("AAAA", 1)
        self.assertEqual(r2.replicate_index, 0)

    def test_a_rejection_is_still_logged(self):
        orc = O.Oracle(TOY, TOY_POOL, 1.0, 1, 0.0)
        orc.measure("AAAD", 1)
        self.assertEqual(len(orc.history), 1)

    def test_true_is_recorded_on_every_outcome(self):
        orc = O.Oracle(TOY, TOY_POOL, 1.0, 1, 1.0)     # failure_rate 1.0 -> always fails
        f = orc.measure("AAAA", 1)
        self.assertEqual(f.outcome, O.FAILED)
        self.assertTrue(f.slot_consumed)
        self.assertEqual(f.true, 10.0)
        rej = orc.measure("AAAD", 1)
        self.assertEqual(rej.true, 1.0, "true must be logged even on a rejection")

    def test_failure_consumes_a_slot(self):
        orc = O.Oracle(TOY, TOY_POOL, 1.0, 1, 1.0)
        for _ in range(3):
            orc.measure("AAAA", 1)
        self.assertEqual(orc.slots_used, 3)
        self.assertEqual(orc.n_ok(), 0)

    def test_sigma_zero_returns_the_truth_exactly(self):
        orc = O.Oracle(TOY, TOY_POOL, 0.0, 1, 0.0)
        self.assertEqual(orc.measure("AAAA", 1).observed, 10.0)

    def test_repeat_measurements_differ(self):
        """Replication has to be informative, so the same sequence must draw fresh noise."""
        orc = O.Oracle(TOY, TOY_POOL, 2.0, 1, 0.0)
        a = orc.measure("AAAA", 1).observed
        b = orc.measure("AAAA", 1).observed
        self.assertNotEqual(a, b)

    def test_measurable_defaults_to_the_pool_but_can_be_widened(self):
        """The oracle measures only the pool by default and can be widened to the full landscape."""
        strict = O.Oracle(TOY, TOY_POOL, 0.0, 1, 0.0)
        self.assertEqual(strict.measure("DAAA", 1).outcome, O.REJECTED)
        wide = O.Oracle(TOY, TOY_POOL, 0.0, 1, 0.0, measurable=frozenset(TOY))
        self.assertEqual(wide.measure("DAAA", 1).outcome, O.OK)

    def test_it_refuses_nonsense_parameters(self):
        for bad in (dict(sigma=-1.0), dict(failure_rate=1.5), dict(failure_rate=-0.1)):
            kw = dict(sigma=1.0, seed=1, failure_rate=0.0)
            kw.update(bad)
            with self.assertRaises(ValueError):
                O.Oracle(TOY, TOY_POOL, **kw)


class TestPairingIsRealAndCounterBased(unittest.TestCase):

    def test_the_same_coordinates_give_the_same_reading_regardless_of_order(self):
        """Two policies that reach the same sequence at different points in their histories see the same reading."""
        a = O.Oracle(TOY, TOY_POOL, 3.0, 99, 0.0)
        b = O.Oracle(TOY, TOY_POOL, 3.0, 99, 0.0)
        a.measure("AAAA", 1)
        b.measure("CAAA", 1); b.measure("AAAC", 1); b.measure("AAAA", 1)
        first_a = [r for r in a.history if r.seq == "AAAA"][0]
        first_b = [r for r in b.history if r.seq == "AAAA"][0]
        self.assertEqual(first_a.observed, first_b.observed)

    def test_a_different_campaign_seed_gives_a_different_field(self):
        a = O.Oracle(TOY, TOY_POOL, 3.0, 1, 0.0)
        b = O.Oracle(TOY, TOY_POOL, 3.0, 2, 0.0)
        self.assertNotEqual(a.measure("AAAA", 1).observed, b.measure("AAAA", 1).observed)

    def test_failure_outcomes_are_also_paired(self):
        a = O.Oracle(TOY, TOY_POOL, 1.0, 7, 0.5)
        b = O.Oracle(TOY, TOY_POOL, 1.0, 7, 0.5)
        b.measure("CAAA", 1)
        self.assertEqual(a.measure("AAAA", 1).outcome, b.measure("AAAA", 1).outcome)

    def test_policy_decisions_mix_the_campaign_seed(self):
        """Policy decisions mix the campaign seed, so campaigns in the same state do not all make the same choice."""
        pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
        picks = set()
        for seed in range(12):
            orc = O.Oracle(TOY, TOY_POOL, 0.0, seed, 0.0)
            v = V.build(orc, 1, 15, 4, 60, tuple(sorted(TOY_POOL)))
            picks.add(tuple(pol.propose(v, 2)))
        self.assertGreater(len(picks), 1,
                           "every campaign opened identically: the campaign seed is not "
                           "reaching the policy's decision keys")

    def test_exploration_decisions_also_mix_the_campaign_seed(self):
        """Exploration decisions also mix the campaign seed, a path the cold-start test above never reaches."""
        big = {a + b + c + d: 1.0 + ord(d) / 100.0
               for a in "ACD" for b in "ACD" for c in "ACD" for d in "ACDEFG"}
        pool = frozenset(big)
        pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
        explored = set()
        for seed in range(12):
            orc = O.Oracle(big, pool, 0.0, seed, 0.0)
            orc.measure("AAAA", 1)                 # same champion in every campaign
            v = V.build(orc, 2, 15, 4, 60, tuple(sorted(pool)))
            self.assertEqual(v.best_by_mean(), "AAAA")
            picks = pol.propose(v, 4)
            explored.add(tuple(picks[1:]))         # picks[0] is the champion re-measurement
        self.assertGreater(len(explored), 1,
                           "with an identical champion at an identical round, every "
                           "campaign explored identically: the campaign seed is not "
                           "reaching the exploration key, so campaigns are not independent")


class TestEveryDecisionKeyIsPerCampaign(unittest.TestCase):
    """Every keyed draw inside a policy mixes `view.campaign_seed`, checked on the source so new branches are covered too."""

    def test_every_keyed_draw_in_policies_mixes_the_campaign_seed(self):
        import re
        src = open(os.path.join(ROOT, "repdef", "policies.py")).read()
        # Skip comments and def lines: the scan is for call sites, not the `_pick_distinct` signature.
        code = "\n".join(l for l in src.splitlines()
                         if not l.lstrip().startswith("#")
                         and not l.lstrip().startswith("def "))
        # Each call to a keyed rng helper, or to _pick_distinct, taken with its arguments.
        calls = re.findall(r"(?:R\.(?:shuffled|choice|uniform|normal|"
                           r"sample_without_replacement)|_pick_distinct)\s*\((?:[^()]|\([^()]*\))*\)",
                           code, re.S)
        self.assertGreaterEqual(len(calls), 5,
                                "the scan found %d keyed draws, so the pattern is stale and "
                                "the invariant is not actually being checked" % len(calls))
        offenders = [" ".join(c.split()) for c in calls if "campaign_seed" not in c]
        self.assertEqual(offenders, [],
                         "these policy draws do not mix the campaign seed, so campaigns "
                         "sharing a state will make identical choices: %s" % (offenders,))


class TestCampaignAccounting(unittest.TestCase):

    def test_the_budget_is_never_exceeded(self):
        for k in (0, 1, 2, 3):
            r = C.run(TOY, TOY_POOL, P.GreedyWithReplication(k, 0), 1.0, 3, 0.15)
            self.assertLessEqual(r.slots_used, r.rounds * 4)

    def test_a_bad_policy_is_re_asked_then_abandoned(self):
        """A policy that never gives a valid order is re-asked a capped number of times, then the slot is abandoned."""

        class AlwaysInvalid(P.Policy):
            name = "always_invalid"

            def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
                return ["ZZZZ"] * n_slots

        r = C.run(TOY, TOY_POOL, AlwaysInvalid(), 1.0, 1, 0.0, rounds=2)
        self.assertGreater(r.n_rejected, 0)
        self.assertGreater(r.n_abandoned, 0)
        self.assertEqual(r.n_ok, 0)
        # capped: at most MAX_REASKS+1 rejections per slot
        self.assertLessEqual(r.n_rejected, 2 * 4 * (C.MAX_REASKS + 1))

    def test_a_replacement_reask_never_returns_a_replication(self):
        """A replacement ask never returns the champion, so a rejected exploration slot cannot become a replication."""
        orc = O.Oracle(TOY, TOY_POOL, 0.0, 1, 0.0)
        orc.measure("AAAA", 1)
        orc.measure("AAAC", 1)
        v = V.build(orc, 2, 15, 4, 60, tuple(sorted(TOY_POOL)))
        champ = v.best_by_mean()
        for pol in (P.GreedyWithReplication(3, 0), P.GreedyRandomReplication(3, 0)):
            round_pick = pol.propose(v, 4, kind="round")
            self.assertIn(champ, round_pick, "a normal round should still replicate")
            repl = pol.propose(v, 1, kind="replacement")
            self.assertNotIn(champ, repl,
                             "%s turned a slot refill into a replication" % pol.name)

    def test_the_reask_cap_is_structurally_finite(self):
        """The re-ask cap is a small named integer bound, since a missing cap would hang rather than fail."""
        self.assertIsInstance(C.MAX_REASKS, int)
        self.assertGreaterEqual(C.MAX_REASKS, 1)
        self.assertLess(C.MAX_REASKS, 100)
        src = open(os.path.join(ROOT, "repdef", "campaign.py")).read()
        # Check the property: the loop compares against a named bound that defaults to MAX_REASKS, never a literal.
        import re as _re
        m = _re.search(r"if tries > (\w+):", src)
        self.assertIsNotNone(m, "the re-ask loop must compare against a named bound, so that "
                                "raising it is a visible edit and not a literal in the loop")
        bound = m.group(1)
        self.assertFalse(bound.isdigit(), "the re-ask bound is a literal: %r" % bound)
        self.assertIn("MAX_REASKS if max_reasks is None", src,
                      "the named bound must default to MAX_REASKS")

    def test_nomination_needs_a_successful_reading(self):
        r = C.run(TOY, TOY_POOL, P.RandomPolicy(0), 1.0, 1, 1.0, rounds=3)
        self.assertEqual(r.n_ok, 0)
        self.assertIsNone(r.nominated)
        self.assertEqual(r.nominated_true, 0.0)

    def test_at_sigma_zero_there_is_no_selection_error(self):
        """With no noise the nominee is the best measured sequence, so regression loss is zero for every k."""
        ls_like = dict(TOY)
        for k in (0, 1, 2, 3):
            r = C.run(ls_like, TOY_POOL, P.GreedyWithReplication(k, 0), 0.0, 5, 0.0)
            self.assertEqual(r.regression_loss, 0.0)

    def test_nomination_rules_can_disagree(self):
        """Mean and max nomination disagree on some seeds."""
        seen = set()
        for seed in range(40):
            a = C.run(TOY, TOY_POOL, P.GreedyWithReplication(1, 0), 4.0, seed, 0.0)
            b = C.run(TOY, TOY_POOL, P.GreedyWithReplication(1, 0), 4.0, seed, 0.0,
                      nomination="max")
            seen.add(a.nominated == b.nominated)
        self.assertIn(False, seen, "mean and max nomination never disagreed")

    def test_an_unknown_nomination_rule_raises(self):
        with self.assertRaises(ValueError):
            C.run(TOY, TOY_POOL, P.RandomPolicy(0), 1.0, 1, 0.0, nomination="vibes")


class TestPolicies(unittest.TestCase):

    def test_random_policy_never_repeats_a_measured_sequence(self):
        r = C.run(TOY, TOY_POOL, P.RandomPolicy(0), 1.0, 4, 0.0, rounds=5)
        self.assertEqual(r.replication_count, 0)

    def test_k_slots_go_to_the_champion(self):
        ls = dict(TOY)
        orc = O.Oracle(ls, TOY_POOL, 0.0, 1, 0.0)
        for s in ("AAAA", "AAAC"):
            orc.measure(s, 1)
        v = V.build(orc, 2, 15, 4, 60, tuple(sorted(TOY_POOL)))
        champ = v.best_by_mean()
        self.assertEqual(champ, "AAAA")
        picks = P.GreedyWithReplication(2, 0).propose(v, 4)
        self.assertEqual(picks[:2], [champ, champ])

    def test_explore_scope_pool_never_proposes_a_dead_variant(self):
        ls = dict(TOY)
        orc = O.Oracle(ls, TOY_POOL, 0.0, 1, 0.0)
        orc.measure("AAAA", 1)
        v = V.build(orc, 2, 15, 4, 60, tuple(sorted(TOY_POOL)))
        for s in P.GreedyWithReplication(0, 0, "pool", "fresh_pool").propose(v, 3):
            self.assertIn(s, TOY_POOL)

    def test_explore_scope_landscape_can_propose_outside_the_pool(self):
        """With a landscape exploration scope a policy can propose outside the pool, as thresh.py does."""
        big = {a + b + c + d: 1.0 for a in "AC" for b in "AC" for c in "AC" for d in "AC"}
        pool = frozenset(["AAAA"])
        orc = O.Oracle(big, pool, 0.0, 1, 0.0, measurable=frozenset(big))
        orc.measure("AAAA", 1)
        v = V.build(orc, 2, 15, 4, 60, tuple(sorted(pool)))
        picks = P.GreedyWithReplication(0, 0, "landscape", "any_pool").propose(v, 3)
        self.assertTrue(any(s not in pool for s in picks))

    def test_the_f1_control_replicates_something_other_than_the_champion(self):
        ls = dict(TOY)
        orc = O.Oracle(ls, TOY_POOL, 0.0, 1, 0.0)
        for s in ("AAAA", "AAAC", "CAAA"):
            orc.measure(s, 1)
        v = V.build(orc, 2, 15, 4, 60, tuple(sorted(TOY_POOL)))
        champ = v.best_by_mean()
        picked_non_champ = False
        for seed in range(30):
            pol = P.GreedyRandomReplication(1, seed)
            if pol.propose(v, 4)[0] != champ:
                picked_non_champ = True
                break
        self.assertTrue(picked_non_champ, "the control only ever re-measured the champion, "
                                         "so it is not a control")

    def test_it_rejects_unknown_configuration(self):
        with self.assertRaises(ValueError):
            P.GreedyWithReplication(1, 0, explore_scope="everything")
        with self.assertRaises(ValueError):
            P.GreedyWithReplication(1, 0, fallback="whatever")


class TestMetrics(unittest.TestCase):

    def test_a_single_observation_has_no_standard_error(self):
        """Reporting 0 would claim certainty from one data point."""
        self.assertIsNone(M.mean_se([4.0])[1])

    def test_paired_se_beats_unpaired_when_arms_correlate(self):
        a = [float(i) for i in range(50)]
        b = [x + 1.0 for x in a]          # perfectly correlated, constant difference
        pd = M.paired_diff(b, a)
        self.assertAlmostEqual(pd["diff"], 1.0)
        self.assertAlmostEqual(pd["se"], 0.0)
        self.assertAlmostEqual(pd["correlation"], 1.0)

    def test_paired_comparison_refuses_misaligned_samples(self):
        with self.assertRaises(ValueError):
            M.paired_diff([1.0, 2.0], [1.0])

    def test_power_scales_as_the_inverse_square_of_the_effect(self):
        n1 = M.power_n(1.0, 0.1)
        n2 = M.power_n(1.0, 0.05)
        self.assertAlmostEqual(n2 / n1, 4.0, delta=0.05)

    def test_power_is_undefined_for_a_zero_effect(self):
        self.assertIsNone(M.power_n(1.0, 0.0))

    def test_rank_is_one_for_the_best_and_ties_share_the_best_rank(self):
        ls = {"AAAA": 5.0, "AAAC": 5.0, "CAAA": 1.0}
        pool = frozenset(ls)
        self.assertEqual(M.rank_of(ls, pool, "AAAA"), 1)
        self.assertEqual(M.rank_of(ls, pool, "AAAC"), 1)
        self.assertEqual(M.rank_of(ls, pool, "CAAA"), 3)

    def test_optimal_match_credits_any_argmax_under_a_tie(self):
        """Optimal match credits any k that ties for the best."""
        class R0(object):
            history = (O.Record(1, "A", O.OK, 1.0, 1.0, 0, True),
                       O.Record(1, "A", O.OK, 1.0, 1.0, 1, True))
        m_single = M.optimal_match([R0()], 1)[0]
        m_set = M.optimal_match([R0()], {1, 2})[0]
        self.assertEqual(m_single, 1.0)
        self.assertEqual(m_set, 1.0)
        self.assertEqual(M.optimal_match([R0()], 0)[0], 0.0)


class TestRng(unittest.TestCase):

    def test_length_prefixing_prevents_key_collisions(self):
        self.assertNotEqual(R.uniform("a", "bc"), R.uniform("ab", "c"))

    def test_shuffled_does_not_mutate_its_input(self):
        src = [1, 2, 3, 4, 5]
        R.shuffled(src, "k")
        self.assertEqual(src, [1, 2, 3, 4, 5])

    def test_choice_on_empty_returns_none_rather_than_raising(self):
        self.assertIsNone(R.choice([], "k"))

    def test_sample_without_replacement_is_distinct(self):
        got = R.sample_without_replacement(list(range(50)), 10, "k")
        self.assertEqual(len(set(got)), 10)

    def test_normal_is_standard(self):
        import statistics as st
        xs = [R.normal("t", i) for i in range(6000)]
        self.assertAlmostEqual(st.mean(xs), 0.0, delta=0.06)
        self.assertAlmostEqual(st.pstdev(xs), 1.0, delta=0.05)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TheCampaignCannotOverspendItsBudget(unittest.TestCase):
    """A campaign never spends more slots or runs more rounds than its budget allows."""

    def _ls(self):
        fit = {("%04d" % i): float(i % 37) for i in range(400)}
        pool = {k for k, v in fit.items() if v > 0.0}
        return fit, pool

    def test_it_spends_exactly_its_slot_budget_and_no_more(self):
        from repdef import campaign as C, policies as P
        fit, pool = self._ls()
        ps = tuple(sorted(pool))
        for rounds, slots in ((15, 4), (8, 2), (5, 8), (1, 4)):
            for seed in range(6):
                r = C.run(fit, pool, P.GreedyWithReplication(1, 0, "pool", "fresh_pool"),
                          0.5, 3_000_000 + seed, 0.15, rounds=rounds, slots_per_round=slots,
                          pool_sorted=ps)
                spent = sum(1 for h in r.history if h.slot_consumed)
                self.assertLessEqual(spent, rounds * slots,
                                     "rounds=%d slots=%d seed=%d spent %d of %d"
                                     % (rounds, slots, seed, spent, rounds * slots))

    def test_it_never_runs_more_rounds_than_it_was_given(self):
        from repdef import campaign as C, policies as P
        fit, pool = self._ls()
        ps = tuple(sorted(pool))
        for rounds in (1, 3, 15):
            r = C.run(fit, pool, P.GreedyWithReplication(1, 0, "pool", "fresh_pool"),
                      0.5, 3_100_000 + rounds, 0.15, rounds=rounds, pool_sorted=ps)
            self.assertLessEqual(max((h.round for h in r.history), default=0), rounds)


class TheStatsHelpersAreCorrect(unittest.TestCase):
    """Holm correction, Welch's test and OLS on worked examples and edge cases."""

    def test_holm_against_a_worked_example(self):
        from repdef.stats import holm
        # m=5, p = .01 .. .05. Holm: .01*5 = .05 passes, .02*4 = .08 fails, and everything larger is
        # retained with it. So exactly one rejection at alpha = .05.
        res = holm([0.01, 0.02, 0.03, 0.04, 0.05])
        self.assertEqual([r[3] for r in res], [True, False, False, False, False])
        self.assertAlmostEqual(res[0][2], 0.05, places=12)
        self.assertAlmostEqual(res[1][2], 0.08, places=12)

    def test_holm_adjusted_values_are_monotone(self):
        from repdef.stats import holm
        res = holm([0.04, 0.001, 0.2, 0.03, 0.5, 0.01])
        adj = [a for _, _, a in [(i, p, a) for i, p, a, _ in res]]
        by_p = sorted(zip([r[1] for r in res], adj))
        self.assertEqual([a for _, a in by_p], sorted(a for _, a in by_p))

    def test_holm_preserves_the_original_order(self):
        from repdef.stats import holm
        res = holm([0.5, 0.001])
        self.assertEqual([r[0] for r in res], [0, 1])
        self.assertEqual(res[1][1], 0.001)

    def test_holm_is_never_less_strict_than_no_correction(self):
        from repdef.stats import holm
        ps = [0.001, 0.01, 0.02, 0.03, 0.04, 0.05]
        for i, p, a, _ in holm(ps):
            self.assertGreaterEqual(a, p)

    def test_welch_finds_a_known_shift_and_not_a_zero_one(self):
        from repdef.stats import welch_p
        import random
        random.seed(7)
        a = [random.gauss(0, 1) for _ in range(60)]
        b = [random.gauss(0.8, 1) for _ in range(60)]
        _d, _se, p = welch_p(a, b)
        self.assertLess(p, 0.01)
        _d, _se, p2 = welch_p(a, list(a))
        self.assertGreater(p2, 0.99)

    def test_ols_recovers_a_planted_slope(self):
        from repdef.stats import ols
        xs = list(range(40))
        ys = [3.0 + 0.5 * x for x in xs]
        b, se, n = ols(xs, ys)
        self.assertAlmostEqual(b, 0.5, places=9)
        self.assertEqual(n, 40)
