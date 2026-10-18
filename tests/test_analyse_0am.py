"""Tests for the landscape-generalisation analysis: its reading rule and its trigger for more campaigns.

The numbers are chosen to sit either side of every line, so a label on the wrong side of a line, or a trigger
that misses its own condition, fails here.
"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_0am as A                                                    # noqa: E402


class ReadingRule(unittest.TestCase):

    def test_lines_are_2y_on_nk_and_y_plus_10_where_y_is_small(self):
        self.assertEqual(A.lines(23.73), (28.73, 47.46))
        self.assertEqual(A.lines(0.89), (5.89, 10.89))
        self.assertEqual(A.lines(10.0), (15.0, 20.0))

    def test_each_label_on_its_side_of_each_line(self):
        y = 23.73
        self.assertEqual(A.label(47.46, y), "re-testing generalises")
        self.assertEqual(A.label(47.45, y), "partial")
        self.assertEqual(A.label(28.74, y), "partial")
        self.assertEqual(A.label(28.73, y), "does not generalise")
        self.assertEqual(A.label(3.0, y), "does not generalise", "below the yardstick is not generalising")

    def test_the_small_yardstick_bands_do_not_overlap(self):
        y = 0.89
        self.assertEqual(A.label(5.0, y), "does not generalise")
        self.assertEqual(A.label(8.0, y), "partial")
        self.assertEqual(A.label(75.0, y), "re-testing generalises")

    def test_an_interval_across_a_line_is_flagged(self):
        self.assertEqual(A.label(50.0, 23.73, (45.0, 55.0)), "re-testing generalises (interval crosses a line)")
        self.assertEqual(A.label(50.0, 23.73, (48.0, 52.0)), "re-testing generalises")


class TopUp(unittest.TestCase):

    def test_wide_interval_triggers(self):
        hit, half = A.topup_trigger(5.0, (1.9, 8.1))
        self.assertTrue(hit)
        self.assertAlmostEqual(half, 3.1, places=12)
        self.assertFalse(A.topup_trigger(5.0, (2.1, 7.9))[0], "a half-width of 2.9 away from zero does not")

    def test_straddling_zero_triggers_only_beyond_two_points(self):
        self.assertTrue(A.topup_trigger(2.5, (-0.4, 5.3))[0])
        self.assertTrue(A.topup_trigger(-2.5, (-5.3, 0.4))[0])
        self.assertFalse(A.topup_trigger(1.5, (-1.0, 4.0))[0])

    def test_narrow_interval_away_from_zero_does_not_trigger(self):
        self.assertFalse(A.topup_trigger(4.0, (1.5, 6.5))[0])


class Trend(unittest.TestCase):

    def test_slope_recovers_a_planted_trend_and_its_interval_covers_it(self):
        pts = [(k, "L%d_%d" % (k, j), 70.0 + 3.0 * k + (j % 3 - 1)) for k in range(4) for j in range(20)]
        est, ci = A.cluster_boot_slope(pts, "test", b=2000)
        self.assertAlmostEqual(est, 3.0, places=9)
        self.assertLess(ci[0], 3.0)
        self.assertGreater(ci[1], 3.0)


if __name__ == "__main__":
    unittest.main()


class Adaptation(unittest.TestCase):
    """The unpaired change in re-testing share, its ratio to the yardstick's change, and the slope on the yardstick."""

    def rows(self, shares):
        return [dict(replication_count=s, slots_used=100) for s in shares]

    def test_unpaired_change_and_ratio(self):
        agent = self.rows([50, 52, 48, 51, 49] * 6)
        grid = self.rows([75, 77, 73, 76, 74] * 20)
        d = A.adaptation_r(agent, grid, -23.0, "t")
        self.assertAlmostEqual(d["d_share"], -25.0)
        self.assertLess(d["d_share_ci"][0], -25.0)
        self.assertGreater(d["d_share_ci"][1], -25.0)
        self.assertAlmostEqual(d["ratio"], 25.0 / 23.0)
        self.assertLessEqual(d["ratio_ci"][0], d["ratio"])
        self.assertGreaterEqual(d["ratio_ci"][1], d["ratio"])

    def test_slope_one_when_share_tracks_the_yardstick_and_zero_when_flat(self):
        ys = [23.0 + (j % 5) * 0.5 for j in range(77)] + [46.0, 47.0, 45.0]
        track = [("L%d" % j, y, 50.0 + y + (j % 3 - 1)) for j, y in enumerate(ys)]
        flat = [("L%d" % j, y, 75.0 + (j % 3 - 1)) for j, y in enumerate(ys)]
        s1, ci1 = A.landscape_slope(track, "track", b=2000)
        s0, ci0 = A.landscape_slope(flat, "flat", b=2000)
        self.assertAlmostEqual(s1, 1.0, delta=0.1)
        self.assertLess(ci1[0], s1)
        self.assertGreater(ci1[1], s1)
        self.assertAlmostEqual(s0, 0.0, delta=0.1)
        self.assertTrue(ci0[0] < 0.0 < ci0[1])


class SlotLossGuard(unittest.TestCase):
    """Lost slots can only lower the share, so only a reading below "generalises" is guarded against them."""

    def rows(self, lost, share=80, ooa=None, abandoned=None):
        ab = lost if abandoned is None else abandoned
        return [dict(replication_count=share, slots_used=100, lost_slots=lost, slots_abandoned=ab,
                     rounds_lost_slots=lost - ab, nominated_true=1.0, n_distinct_measured=10, spend=0.1,
                     out_of_alphabet_proposals=sum((ooa or {}).values()), out_of_alphabet_letters=ooa or {})
                for _ in range(5)]

    def test_a_generalising_reading_stands_whatever_the_loss(self):
        d = A.cell_summary(self.rows(30.0), "g1", y=23.73)
        self.assertEqual(d["label"], "re-testing generalises")
        self.assertTrue(d["lost_above_10"])

    def test_a_lower_reading_above_ten_is_not_interpretable_and_ten_is_read(self):
        self.assertEqual(A.cell_summary(self.rows(10.5, share=20), "g2", y=23.73)["label"], A.NOT_INTERPRETABLE)
        self.assertEqual(A.cell_summary(self.rows(11.0, share=35), "g3", y=23.73)["label"], A.NOT_INTERPRETABLE)
        self.assertEqual(A.cell_summary(self.rows(10.0, share=20), "g4", y=23.73)["label"], "does not generalise")
        self.assertEqual(A.cell_summary(self.rows(11.0, share=35), "g5", y=23.73)["reading_before_guard"], "partial")

    def test_a_descriptive_cell_carries_no_label(self):
        self.assertNotIn("label", A.cell_summary(self.rows(30), "g6"))

    def test_share_over_non_lost_slots_and_the_channel_split(self):
        d = A.cell_summary(self.rows(20.0, share=40, abandoned=15), "g7", y=23.73)
        self.assertAlmostEqual(d["share_non_lost"], 50.0)
        self.assertAlmostEqual(d["lost_nonviable_mean"], 15.0)
        self.assertAlmostEqual(d["lost_rounds_mean"], 5.0)

    def test_out_of_alphabet_letters_are_summed_per_cell(self):
        d = A.cell_summary(self.rows(0, ooa={"U": 2, "V": 1}), "g5", y=23.73)
        self.assertEqual(d["out_of_alphabet_proposals"], 15)
        self.assertEqual(d["out_of_alphabet_campaigns"], 5)
        self.assertEqual(d["out_of_alphabet_letters"], {"U": 10, "V": 5})
