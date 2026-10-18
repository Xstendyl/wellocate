"""Tests for the agent-tools analysis: its reading rules, on numbers chosen to sit either side of every line."""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_0an as A                                                    # noqa: E402

Y = 23.78


class Share(unittest.TestCase):

    def test_removes_at_or_below_twice_the_yardstick(self):
        self.assertEqual(A.share_label(47.56, -30, (45, 47.5), (-32, -28), 0, Y), "removes re-testing")
        self.assertEqual(A.share_label(47.57, -30, (46, 49), (-32, -28), 0, Y),
                         "reduces")

    def test_reduces_needs_a_drop_of_more_than_ten(self):
        self.assertEqual(A.share_label(60.0, -10.01, (58, 62), (-12, -8.5), 0, Y),
                         "reduces (interval crosses a line)")
        self.assertEqual(A.share_label(60.0, -10.0, (58, 62), (-11, -9), 0, Y),
                         "no effect (interval crosses a line)")
        self.assertEqual(A.share_label(80.0, -2.0, (78, 82), (-4, 0), 0, Y), "no effect")

    def test_the_guard_is_asymmetric(self):
        self.assertEqual(A.share_label(40.0, -35, (38, 42), (-37, -33), 10.5, Y), A.NOT_INTERPRETABLE)
        self.assertEqual(A.share_label(60.0, -15, (58, 62), (-17, -13), 12.0, Y), A.NOT_INTERPRETABLE)
        self.assertEqual(A.share_label(80.0, -2, (78, 82), (-4, 0), 30.0, Y), "no effect")
        self.assertEqual(A.share_label(40.0, -35, (38, 42), (-37, -33), 10.0, Y), "removes re-testing")


class Pick(unittest.TestCase):

    def test_each_label_on_its_side(self):
        self.assertEqual(A.pick_label((0.01, 0.30), 0.22), "pick rises")
        self.assertEqual(A.pick_label((-0.30, -0.01), 0.22), "pick falls")
        self.assertEqual(A.pick_label((-0.22, 0.22), 0.22), "no change beyond delta")
        self.assertEqual(A.pick_label((-0.23, 0.10), 0.22), "unresolved")


if __name__ == "__main__":
    unittest.main()


class F3HasNoShareLabel(unittest.TestCase):
    """The repeat-cap arm's share is capped at 50% by construction, under the 47.56% line, so it gets no share label."""

    D = dict(d_pick_ci=(0.05, 0.3), delta=0.22, pick_powered=True, share=40.0, d_share=-35.0,
             share_ci=(38, 42), d_share_ci=(-37, -33), lost_slots=0.0)

    def test_f3_gets_only_a_pick_label(self):
        lab = A.labels("F3 cap", self.D, Y)
        self.assertEqual(set(lab), {"pick_label"})
        self.assertEqual(lab["pick_label"], "pick rises")

    def test_f1_and_f2_get_both(self):
        for arm in ("F1 ledger", "F2 menu"):
            self.assertEqual(set(A.labels(arm, self.D, Y)), {"pick_label", "share_label"})

    def test_the_ceiling_is_one_order_in_two(self):
        self.assertEqual(A.SHARE_CEILING_F3, 50.0)
        self.assertLess(2 * Y, A.SHARE_CEILING_F3, "the removes line sits under the mechanical ceiling")


class ZeroAnOne(unittest.TestCase):
    """Each cell reads its band at its own arm's n, and the repeat-cap arm reports capped attempts with an interval."""

    def test_opus_reads_the_band_of_its_own_n(self):
        import json, launch_0an as L
        plan = json.load(open(os.path.join(ROOT, "results", "plan_0an.json")))
        opus = "anthropic/claude-opus-4.7"
        self.assertEqual((L.N_BY_ARM["f1_ledger"][opus], L.N_BY_ARM["f2_menu"][opus], L.N_BY_ARM["f3_cap"][opus]),
                         (60, 30, 30))
        self.assertEqual(plan["plan_n"]["Opus"]["60"]["pick_delta"], plan["plan"]["Opus"]["pick_delta"])
        self.assertGreater(plan["plan_n"]["Opus"]["30"]["pick_delta"], plan["plan"]["Opus"]["pick_delta"])
        self.assertGreaterEqual(plan["plan_n"]["Opus"]["30"]["p_meet_no_change"], 0.95)

    def test_capped_attempts_and_the_loss_channels(self):
        def row(capped, abandoned, hits, rounds_lost):
            return dict(replication_count=10, slots_used=60, lost_slots=abandoned + rounds_lost,
                        slots_abandoned=abandoned, repeat_cap_hits=hits, rounds_lost_slots=rounds_lost,
                        n_distinct_measured=20, n_rejected=50, n_capped=capped, nominated_true=8.0)
        pr = [(row(c, 9, 1, 4), row(0, 0, 0, 0)) for c in (40, 50, 60, 70)]
        d = A.summary(pr, "test", 0.31, False)
        self.assertEqual(d["capped"], 55.0)
        self.assertTrue(40 <= d["capped_ci"][0] <= 55 <= d["capped_ci"][1] <= 70)
        self.assertEqual((d["lost_rejection"], d["lost_cap_bound"], d["lost_rounds"]), (8.0, 1.0, 4.0))
        self.assertEqual(d["lost_slots"], d["lost_rejection"] + d["lost_cap_bound"] + d["lost_rounds"])

