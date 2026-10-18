"""Golden fixtures for the reply parser: realistic model output in, the exact expected proposals out.

Each fixture is a shape a model has produced or plausibly could, including a real reply whose reasoning
preamble mentions many sequences. Both parsers are checked on every fixture.
"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from repdef import llm_policy as LP, prompts  # noqa: E402

AB = prompts.LANDSCAPES["abstract"]["alphabet"]
AA = prompts.LANDSCAPES["gb1_bio"]["alphabet"]

# (name, raw text, n_slots, alphabet, expected primary proposals, expected status)
FIXTURES = [
    ("plain pipe lines",
     "GDPF | extend position 3\nGDSF | try S\nGDKF | replicate the leader\nGDTF | probe T",
     4, AB, ["GDPF", "GDSF", "GDKF", "GDTF"], "ok"),

    ("REAL opus preamble listing readings with colons, answer at the bottom",
     "Looking at the data:\n"
     "- GDKF: readings 8.142, 7.282, 6.975, 7.357 -> mean ~7.35\n"
     "- GDNF: 7.738, 7.512, 7.222 -> mean ~7.28\n"
     "- GDOF: 7.529, 7.220 -> mean ~7.37\n"
     "- GDMF: 7.090\n\n"
     "Position 3 K/N/O all look good. Should explore nearby:\n"
     "GDPF | extend position 3\nGDSF | try S\nGDKF | replicate the leader\nGDTF | probe T",
     4, AB, ["GDPF", "GDSF", "GDKF", "GDTF"], "ok"),

    ("markdown bullets on the answer lines",
     "- GDPF | extend\n- GDSF | try S\n- GDKF | replicate\n- GDTF | probe",
     4, AB, ["GDPF", "GDSF", "GDKF", "GDTF"], "ok"),

    ("numbered answer lines",
     "1. GDPF | extend\n2. GDSF | try S\n3. GDKF | replicate\n4. GDTF | probe",
     4, AB, ["GDPF", "GDSF", "GDKF", "GDTF"], "ok"),

    ("a markdown table of past readings, then the answer",
     "| variant | n | mean |\n|---|---|---|\n| GDKF | 4 | 7.35 |\n| GDNF | 3 | 7.28 |\n\n"
     "GDPF | extend\nGDSF | try S\nGDKF | replicate\nGDTF | probe",
     4, AB, ["GDPF", "GDSF", "GDKF", "GDTF"], "ok"),

    ("a code fence around the answer",
     "Here you go:\n```\nGDPF | extend\nGDSF | try S\nGDKF | replicate\nGDTF | probe\n```",
     4, AB, ["GDPF", "GDSF", "GDKF", "GDTF"], "ok"),

    ("lowercase sequences",
     "gdpf | extend\ngdsf | try s\ngdkf | replicate\ngdtf | probe",
     4, AB, ["GDPF", "GDSF", "GDKF", "GDTF"], "ok"),

    ("THREE proposals for four slots: a count failure, not silently padded",
     "GDPF | extend\nGDSF | try S\nGDKF | replicate",
     4, AB, ["GDPF", "GDSF", "GDKF"], "wrong_count"),

    ("FIVE proposals for four slots: AMBIGUOUS, and never truncated to four",
     "GDPF | a\nGDSF | b\nGDKF | c\nGDTF | d\nGDAF | e",
     4, AB, ["GDPF", "GDSF", "GDKF", "GDTF", "GDAF"], "ambiguous"),

    ("colon separators only, no pipe anywhere: leniency still applies",
     "GDPF: extend\nGDSF: try S\nGDKF: replicate\nGDTF: probe",
     4, AB, ["GDPF", "GDSF", "GDKF", "GDTF"], "ok"),

    ("a bare list with no separators at all",
     "GDPF\nGDSF\nGDKF\nGDTF", 4, AB, ["GDPF", "GDSF", "GDKF", "GDTF"], "ok"),

    ("GB1's protein alphabet accepts VWY and rejects J",
     "VDGV | parent\nADGV | A at 1\nWDGV | W at 1\nFWAA | the known optimum",
     4, AA, ["VDGV", "ADGV", "WDGV", "FWAA"], "ok"),

    ("a J on the PROTEIN alphabet is rejected and the count says the alphabet caused it",
     "VDGV | parent\nADGV | A at 1\nJDGV | J at 1\nWDGV | W at 1",
     4, AA, ["VDGV", "ADGV", "WDGV"], "alphabet_then_wrong_count"),

    ("the same J is FINE on the abstract alphabet",
     "GDIF | a\nGDIE | b\nGDJF | c\nHDIF | d",
     4, AB, ["GDIF", "GDIE", "GDJF", "HDIF"], "ok"),

    ("a refusal",
     "I cannot choose candidates without knowing the objective. Could you clarify?",
     4, AB, [], "refusal"),

    ("an empty response",
     "   \n  ", 4, AB, [], "unparseable"),

    ("prose with no parseable line",
     "I will explore position three this round and replicate the leader.", 4, AB, [],
     "unparseable"),
]


class GoldenFixtures(unittest.TestCase):
    def test_every_fixture_parses_exactly_as_specified(self):
        for name, text, n, alpha, want, want_status in FIXTURES:
            got, status, notes = LP.parse(text, n, alphabet=alpha)
            self.assertEqual([g[0] for g in got], want, "%s: proposals" % name)
            self.assertEqual(status, want_status, "%s: status (notes %s)" % (name, notes))

    def test_the_second_parser_agrees_wherever_the_answer_uses_pipes(self):
        # parse_b reads only the final block of pipe lines, so it is silent on the colon-only, bare and
        # prose fixtures. Where pipes are used it must agree with the main parser.
        for name, text, n, alpha, want, _ in FIXTURES:
            if "|" not in text:
                continue
            b = LP.parse_b(text, n, alphabet=alpha)
            if not b:
                continue
            self.assertEqual(b, want, "%s: second parser disagrees" % name)

    def test_every_accepted_proposal_appears_in_the_line_it_came_from(self):
        # A self-consistency check on the parse: if a captured sequence is not present in the raw line
        # it was captured from, the regex has mis-captured and the proposal is an invention.
        for name, text, n, alpha, want, _ in FIXTURES:
            got, _s, _n = LP.parse(text, n, alphabet=alpha)
            upper = [l.upper() for l in text.splitlines()]
            for seq, reason in got:
                self.assertTrue(any(seq in l for l in upper),
                                "%s: %s appears in no line of the response" % (name, seq))

    def test_no_fixture_yields_more_than_it_was_asked_for_without_saying_so(self):
        for name, text, n, alpha, want, want_status in FIXTURES:
            got, status, _ = LP.parse(text, n, alphabet=alpha)
            if len(got) > n:
                self.assertEqual(status, "ambiguous", "%s: over-count not flagged" % name)

    def test_the_candidate_counter_sees_the_reasoning_the_parser_ignores(self):
        # On the real preamble fixture the parser accepts 4 while the reply mentions many more legal
        # tokens; that ratio flags a reasoning-heavy reply for inspection.
        pre = [f for f in FIXTURES if f[0].startswith("REAL opus preamble")][0]
        got, _s, _n = LP.parse(pre[1], pre[2], alphabet=pre[3])
        anywhere = LP.candidates_anywhere(pre[1], pre[3])
        self.assertEqual(len(got), 4)
        self.assertGreater(len(anywhere), len(got),
                           "the counter should see more tokens than the parser accepts here")


if __name__ == "__main__":
    unittest.main(verbosity=2)
