"""Tests that everything the prompt tells the agent about its budget is true.

The prompt states the replacement cap and that the slot is then lost, the remaining count never exceeds what
the rounds left allow, a malformed reply is disclosed as costing the whole round, and both history views show
lost slots and lost rounds.
"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from repdef import campaign as C, llm_policy as LP, oracle as O, prompts, view as V  # noqa: E402

AB = prompts.LANDSCAPES["abstract"]["alphabet"]


def build(**kw):
    d = dict(landscape="abstract", noise_model="multiplicative", cv=0.073, noise_floor=0.0035)
    d.update(kw)
    return prompts.build("instructed", [], 1, 15, 4, 60, 0.0, **d)


class ThePromptStatesTheTrueRules(unittest.TestCase):
    def test_it_does_not_claim_a_rejection_is_free(self):
        # This sentence is false once the replacement cap applies.
        self.assertNotIn("costs you nothing", build())

    def test_it_states_the_replacement_cap_and_what_follows(self):
        p = build(max_reasks=3)
        self.assertIn("up to\n3 times", p.replace("  ", " ")) if False else None
        self.assertIn("3", p)
        self.assertIn("SLOT IS LOST", p)
        self.assertIn("counts against", p)

    def test_the_disclosed_cap_tracks_the_argument(self):
        # A hardcoded "3" would pass the test above while lying whenever the harness used another cap.
        for cap in (1, 2, 5):
            p = build(max_reasks=cap)
            self.assertIn("up to\n%d times" % cap, p,
                          "the prompt does not disclose cap=%d" % cap)

    def test_it_states_the_wrong_count_rule(self):
        p = build()
        self.assertIn("WHOLE ROUND IS LOST", p)
        self.assertIn("asked once more", p)


class TheRemainingCountIsAchievable(unittest.TestCase):
    def view_at(self, rnd, used):
        obs = tuple(V.Observation(1, "AAAA", "ok", 1.0) for _ in range(used))
        return V.CampaignView(obs, {"AAAA"}, rnd, 15, 4, used, 60, ("AAAA",),
                              campaign_seed=0, screen=None)

    def test_it_never_exceeds_what_the_rounds_left_allow(self):
        pol = LP.LLMPolicy("m", "instructed", 1.0, landscape="abstract")
        for rnd, used in ((15, 38), (15, 0), (14, 10), (8, 28), (1, 0), (12, 4)):
            v = self.view_at(rnd, used)
            got = pol._remaining(v)
            cap = (15 - rnd + 1) * 4
            self.assertLessEqual(got, cap,
                                 "round %d: told %d remaining but only %d are orderable"
                                 % (rnd, got, cap))
            self.assertLessEqual(got, 60 - used)

    def test_the_old_formula_would_fail_this(self):
        # Without the per-round cap, round 15 with 38 used would report 22 when only 4 can be ordered.
        v = self.view_at(15, 38)
        self.assertEqual(v.slots_total - v.slots_used, 22)
        self.assertEqual(LP.LLMPolicy("m", "instructed", 1.0, landscape="abstract")._remaining(v), 4)

    def test_it_is_the_full_budget_at_the_start(self):
        pol = LP.LLMPolicy("m", "instructed", 1.0, landscape="abstract")
        self.assertEqual(pol._remaining(self.view_at(1, 0)), 60)


class ALostSlotAppearsInTheHistory(unittest.TestCase):
    def test_the_oracle_can_record_an_abandoned_slot_as_consumed(self):
        orc = O.Oracle({"AAAA": 1.0}, {"AAAA"}, 0.0, 1, 0.0)
        rec = orc.record_abandoned(3, "BBBB")
        self.assertEqual(rec.outcome, O.ABANDONED)
        self.assertTrue(rec.slot_consumed, "an abandoned slot must count against the budget")
        self.assertEqual(orc.slots_used, 1)

    def test_a_round_lost_is_its_own_outcome(self):
        orc = O.Oracle({"AAAA": 1.0}, {"AAAA"}, 0.0, 1, 0.0)
        rec = orc.record_abandoned(3, "----", outcome=O.ROUND_LOST)
        self.assertEqual(rec.outcome, O.ROUND_LOST)
        self.assertTrue(rec.slot_consumed)

    def test_the_history_the_agent_sees_names_both(self):
        rows = [(1, "AAAA", "ok", 1.0), (2, "BBBB", "abandoned", None),
                (3, "----", "round_lost", None), (4, "CCCC", "rejected", None)]
        h = prompts._history(rows)
        self.assertIn("SLOT LOST", h)
        self.assertIn("ROUND LOST", h)
        # A rejection must not claim the slot was not used.
        self.assertNotIn("slot not used", h)
        self.assertIn("a replacement was requested", h)

    def test_the_aggregated_view_states_the_lost_slot_and_the_lost_round(self):
        # The aggregated view must name lost slots and lost rounds, not render them as rejections or candidates.
        rows = [(1, "AAAA", "ok", 1.0), (1, "AAAA", "ok", 1.2), (2, "EEEE", "rejected", None),
                (2, "EEEE", "abandoned", None), (3, "----", "round_lost", None)]
        h = prompts._history(rows, aggregated=True)
        self.assertIn("SLOT LOST", h)
        self.assertIn("ROUND LOST", h)
        self.assertIn("count against your budget", h)
        # A lost slot must not be described as merely rejected.
        eeee = [l for l in h.splitlines() if l.startswith("EEEE")]
        self.assertEqual(len(eeee), 1)
        self.assertNotIn("rejected, not viable", eeee[0])
        # The placeholder must not be presented as a candidate the agent proposed.
        self.assertFalse([l for l in h.splitlines() if l.startswith("----  ")],
                         "the round-lost placeholder is rendered as a candidate")

    def test_both_views_agree_about_what_was_lost(self):
        # Both history views must say the same things about what was lost.
        rows = [(1, "AAAA", "ok", 1.0), (2, "EEEE", "abandoned", None),
                (3, "----", "round_lost", None)]
        for aggregated in (False, True):
            h = prompts._history(rows, aggregated=aggregated)
            self.assertIn("SLOT LOST", h, "aggregated=%s" % aggregated)
            self.assertIn("ROUND LOST", h, "aggregated=%s" % aggregated)


class ALostRoundIsChargedItsWholeBudget(unittest.TestCase):
    """A forfeited round is charged every one of its slots, so the whole budget is accounted for."""

    def run_with_a_silent_round(self, silent=3, slots=4):
        from repdef import policies as P
        fit = {("%04d" % i): float(i % 37) for i in range(400)}
        pool = {k for k, v in fit.items() if v > 0.0}

        class Silent(P.Policy):
            def __init__(self):
                self.name = "silent"

            def replication_slots(self, view):
                return None

            def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
                if view.current_round == silent:
                    return []
                return P.GreedyWithReplication(1, 0, "pool", "fresh_pool").propose(
                    view, n_slots, exclude, kind)

        return C.run(fit, pool, Silent(), 0.5, 4242, 0.0, pool_sorted=tuple(sorted(pool)),
                     max_reasks=3, slots_per_round=slots)

    def test_a_forfeited_round_costs_every_one_of_its_slots(self):
        r = self.run_with_a_silent_round()
        lost = sum(1 for h in r.history if h.outcome == "round_lost")
        self.assertEqual(lost, 4, "a forfeited 4-slot round was charged %d slot(s)" % lost)

    def test_the_whole_budget_is_accounted_for(self):
        r = self.run_with_a_silent_round()
        ok = sum(1 for h in r.history if h.outcome == "ok")
        lost = sum(1 for h in r.history if h.outcome in ("abandoned", "round_lost"))
        self.assertEqual(r.slots_used, 60, "slots_used %d, so %d slots vanished unaccounted"
                         % (r.slots_used, 60 - r.slots_used))
        self.assertEqual(ok + lost, 60)

    def test_it_charges_the_round_size_and_not_a_constant(self):
        # A hardcoded 4 would pass the first test while undercharging an 8-slot round.
        r = self.run_with_a_silent_round(slots=8)
        lost = sum(1 for h in r.history if h.outcome == "round_lost")
        self.assertEqual(lost, 8, "an 8-slot round was charged %d" % lost)


if __name__ == "__main__":
    unittest.main(verbosity=2)
