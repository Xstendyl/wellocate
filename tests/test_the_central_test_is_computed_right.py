"""Tests for the central replication analysis on synthetic prompts whose answer is known by construction.

The metric is rebuilt from the history each prompt showed, with parsers for both the per-reading and the
aggregated history. Every prompt is written by hand, so the expected r* and replication count follow from
the text.
"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import post_repeat_replication as P  # noqa: E402


def per_reading(rows):
    return "HEADER\n\nHISTORY\nround  candidate  reading\n" + "\n".join(
        "%d  %s  %.3f" % r for r in rows) + "\n\nChoose 4 candidates.\n"


def final_hist(rows):
    """A nomination prompt whose HISTORY is the measurement-ordered record the primary path reads.

    rows: (round, seq, kind) with kind in read / failed / lost / round_lost.
    """
    TEXT = {"read": "%.3f", "failed": "order failed, no reading",
            "lost": "SLOT LOST: every replacement for this slot was also non-viable",
            "round_lost": "ROUND LOST: the reply was not the requested number of candidates"}
    out = ["HEADER", "", "HISTORY", "round  candidate  reading"]
    for i, (rnd, seq, kind) in enumerate(rows):
        tail = (TEXT[kind] % (7.0 + 0.01 * i)) if kind == "read" else TEXT[kind]
        out.append("%5d  %-9s  %s" % (rnd, seq, tail))
    return "\n".join(out) + "\n\nName the single candidate.\n"


def nomination_call(rows, rung="blind", seed=1, model="vendor/X"):
    return dict(kind="nomination", round=15, rung=rung, campaign_seed=seed, model=model,
                prompt=final_hist(rows), parsed=["AAAA"])


def aggregated(rows):
    return ("HEADER\n\nHISTORY\ncandidate  n  mean     standard error of the mean\n" + "\n".join(
        "%s       %d  %.3f    %s" % (seq, n, mean, "0.100" if n > 1 else
                                     "not estimable from 1 measurement")
        for seq, n, mean in rows) + "\n\nChoose 4 candidates.\n")


class TheParsersSeeWhatTheAgentSaw(unittest.TestCase):

    def test_the_per_reading_view_counts_successful_readings(self):
        t = per_reading([(1, "GDIF", 7.0), (1, "GDAF", 7.4), (2, "GDIF", 6.9)])
        self.assertEqual(P.read_counts(t), {"GDIF": 2, "GDAF": 1})

    def test_the_aggregated_view_counts_n(self):
        """The aggregated history view counts n, so the Aggregated cell contributes to the analysis."""
        t = aggregated([("GDIF", 2, 7.0), ("GDAF", 1, 7.4)])
        self.assertEqual(P.read_counts(t), {"GDIF": 2, "GDAF": 1})

    def test_the_aggregated_view_is_not_matched_by_the_per_reading_parser(self):
        t = aggregated([("GDIF", 2, 7.0)])
        self.assertEqual([l for l in t.splitlines() if P.ROW.match(l)], [])

    def test_a_lost_slot_row_reads_as_zero_and_not_as_a_reading(self):
        t = ("HEADER\n\nHISTORY\ncandidate  n  mean     standard error of the mean\n"
             "GDIF       2  7.000    0.100\n"
             "GDBF       0  SLOT LOST: every replacement for this slot was also non-viable\n")
        self.assertEqual(P.read_counts(t), {"GDIF": 2, "GDBF": 0})

    def test_an_empty_history_yields_nothing(self):
        self.assertEqual(P.read_counts("HEADER\n\nHISTORY\n(no measurements yet)\n"), {})
        self.assertEqual(P.read_counts("a prompt with no history section at all"), {})

    def test_a_prompt_matching_both_formats_is_refused_and_not_guessed(self):
        both = ("HEADER\n\nHISTORY\n1  GDIF  7.000\nGDAF       2  7.400    0.100\n")
        with self.assertRaises(ValueError):
            P.read_counts(both)

    def test_a_failed_only_variant_is_not_a_successful_reading(self):
        """A variant with only failed readings has no successful reading, so it is not counted."""
        t = ("HEADER\n\nHISTORY\nround  candidate  reading\n"
             "1  GDIF  7.000\n2  GDAF  FAILED\n")
        self.assertEqual(P.read_counts(t), {"GDIF": 1})
        self.assertNotIn("GDAF", P.read_counts(t))


class RStarAndThePostRepeatWindow(unittest.TestCase):
    """r* is one BEFORE the first round whose shown history holds a duplicate, because a reading received
    in round k is only visible in the prompt for round k+1."""

    VIABLE = {"AAAA", "BBBB", "CCCC", "DDDD"}
    MODEL = "vendor/X"

    def calls(self, prompts_and_orders, rung="blind", seed=1):
        out = []
        for rnd, (prompt, orders) in enumerate(prompts_and_orders, start=1):
            out.append(dict(kind="round", round=rnd, rung=rung, campaign_seed=seed,
                            model=self.MODEL, prompt=prompt, parsed=orders))
        return out

    def run_on(self, calls):
        real = P.calls_of
        P.calls_of = lambda _tag: iter(calls)
        try:
            return P.per_campaign("synthetic", self.VIABLE)
        finally:
            P.calls_of = real

    def test_r_star_is_the_round_the_second_reading_arrives(self):
        """Read from the final history, which is the measurement-ordered record."""
        rows = [(1, "AAAA", "read"), (1, "BBBB", "read"), (2, "AAAA", "read"),
                (3, "AAAA", "read"), (3, "CCCC", "read")]
        got = self.run_on([nomination_call(rows)])[(self.MODEL, "blind", 1)]
        self.assertEqual(got["r_star"], 2)                 # AAAA's second reading lands in round 2
        # Round 3 has two measured slots, one of them a re-measure of AAAA.
        self.assertEqual((got["reps_after"], got["orders_after"]), (1, 2))
        self.assertAlmostEqual(got["post_repeat"], 0.5)

    def test_a_campaign_that_never_repeats_is_excluded_and_not_scored_zero(self):
        rows = [(1, "AAAA", "read"), (2, "BBBB", "read"), (3, "CCCC", "read")]
        got = self.run_on([nomination_call(rows)])[(self.MODEL, "blind", 1)]
        self.assertIsNone(got["r_star"])
        self.assertIsNone(got["post_repeat"], "no repeat must be EXCLUDED, never counted as 0.0")

    def test_a_failed_order_is_a_charged_slot_and_can_be_replication(self):
        rows = [(1, "AAAA", "read"), (1, "AAAA", "read"), (2, "AAAA", "failed"), (2, "BBBB", "read")]
        got = self.run_on([nomination_call(rows)])[(self.MODEL, "blind", 1)]
        self.assertEqual(got["r_star"], 1)
        self.assertEqual((got["reps_after"], got["orders_after"]), (1, 2))

    def test_a_lost_slot_is_charged_but_is_neither_part_of_the_fraction(self):
        """A lost slot is charged, but it is neither a re-measure nor an opportunity in the fraction."""
        rows = [(1, "AAAA", "read"), (1, "AAAA", "read"),
                (2, "AAAA", "lost"), (2, "----", "round_lost"), (2, "BBBB", "read")]
        got = self.run_on([nomination_call(rows)])[(self.MODEL, "blind", 1)]
        self.assertEqual(got["orders_after"], 1, "only BBBB was an attempted measurement")
        self.assertEqual(got["reps_after"], 0)
        self.assertEqual(got["slots_counted"], 5, "all five rows are charged slots")


class ThreeBugsFoundByAudit(unittest.TestCase):
    """The campaign key includes the model, the fraction is over slots, and r* depends on the prompt kind.

    Models sharing a seed range stay separate; rejected proposals take no slot and are not counted; a
    replacement prompt is rendered mid-round, so a duplicate visible there was received in that round.
    """

    VIABLE = {"AAAA", "BBBB", "CCCC", "DDDD"}     # "ZZZZ" is non-viable in these tests

    def run_on(self, calls):
        real = P.calls_of
        P.calls_of = lambda _tag: iter(calls)
        try:
            return P.per_campaign("synthetic", self.VIABLE)
        finally:
            P.calls_of = real

    def test_two_models_on_one_seed_stay_separate(self):
        """Two models on the same seed and rung stay separate and are not pooled into one number."""
        calls = [
            # model X re-measures AAAA after its repeat; model Y explores instead.
            nomination_call([(1, "AAAA", "read"), (1, "AAAA", "read"),
                             (2, "AAAA", "read"), (2, "AAAA", "read")], seed=7, model="vendor/X"),
            nomination_call([(1, "AAAA", "read"), (1, "AAAA", "read"),
                             (2, "CCCC", "read"), (2, "DDDD", "read")], seed=7, model="vendor/Y"),
        ]
        got = self.run_on(calls)
        self.assertEqual(len(got), 2, "the model must be part of the key")
        x = got[("vendor/X", "blind", 7)]
        y = got[("vendor/Y", "blind", 7)]
        self.assertEqual(x["post_repeat"], 1.0)
        self.assertEqual(y["post_repeat"], 0.0)
        self.assertNotEqual(x["post_repeat"], y["post_repeat"],
                            "two models on one seed collapsed into one value")

    def test_a_rejected_non_viable_proposal_takes_no_slot(self):
        # A rejected proposal never appears as a charged slot in the final history at all, which is how
        # the record itself encodes "took no slot".
        calls = [nomination_call([(1, "AAAA", "read"), (1, "AAAA", "read"), (2, "AAAA", "read")], seed=1)]
        got = self.run_on(calls)[("vendor/X", "blind", 1)]
        self.assertEqual(got["slots_counted"], 3)
        self.assertEqual(got["orders_after"], 1)
        self.assertEqual(got["post_repeat"], 1.0)

    def test_a_replacement_prompt_shows_mid_round_state_so_r_star_is_that_round(self):
        """A round prompt's history covers completed rounds; a replacement prompt's does not."""
        dup = per_reading([(1, "AAAA", 7.0), (1, "AAAA", 7.1)])
        as_replacement = [
            dict(kind="round", round=1, rung="blind", campaign_seed=1, model="vendor/X",
                 prompt=per_reading([]), parsed=["AAAA", "AAAA", "ZZZZ"]),
            dict(kind="replacement", round=1, rung="blind", campaign_seed=1, model="vendor/X",
                 prompt=dup, parsed=["BBBB"]),
        ]
        self.assertEqual(self.run_on(as_replacement)[("vendor/X", "blind", 1)]["r_star"], 1,
                         "a mid-round replacement view means the repeat arrived in THIS round")
        as_round = [
            dict(kind="round", round=1, rung="blind", campaign_seed=1, model="vendor/X",
                 prompt=per_reading([]), parsed=["AAAA", "AAAA"]),
            dict(kind="round", round=2, rung="blind", campaign_seed=1, model="vendor/X",
                 prompt=dup, parsed=["BBBB"]),
        ]
        self.assertEqual(self.run_on(as_round)[("vendor/X", "blind", 1)]["r_star"], 1,
                         "a round-2 view of a duplicate means it arrived in round 1")

    def test_r_star_is_never_zero(self):
        """Zero would claim a repeat was visible before the first round existed."""
        calls = [nomination_call([(1, "AAAA", "read"), (1, "AAAA", "read"), (2, "BBBB", "read")], seed=1)]
        self.assertGreaterEqual(self.run_on(calls)[("vendor/X", "blind", 1)]["r_star"], 1)
