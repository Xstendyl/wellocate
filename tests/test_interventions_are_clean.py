"""Tests that the two interventions, the aggregated history and the decision rule, each change exactly one thing in the prompt.

Also covers landscape substitution, the stated noise model and the reply parser.
"""
import math, re, unittest
from repdef import prompts

H = [(1, "VDGV", "ok", 1.02), (1, "VDGV", "ok", 1.31), (1, "ADGV", "ok", 2.40),
     (1, "WWGV", "rejected", None), (2, "ADGV", "failed", None), (2, "VDGV", "ok", 0.88)]


def body(rung, hist=H, **kw):
    return prompts.build(rung, hist, 2, 15, 4, 56, 0.42, **kw).split("\nROUND 2 OF")[0]


def history_of(rung, hist=H, **kw):
    """The HISTORY block alone, without the footer that follows it."""
    block = prompts.build(rung, hist, 2, 15, 4, 56, 0.42, **kw).split("HISTORY\n")[1]
    return block.split("\n\n")[0]


class AggregatedChangesOnlyThePresentation(unittest.TestCase):
    def test_its_instructions_are_identical_to_instructed(self):
        # Identical instructions, so a gain comes from the aggregation and not from new wording.
        self.assertEqual(body("aggregated"), body("instructed"))

    def test_it_adds_no_number_that_is_not_derivable_from_the_raw_history(self):
        # The strong form of "no new information": recompute every printed value from the raw rows.
        vals = [o for (_, s, oc, o) in H if s == "VDGV" and oc == "ok"]
        n = len(vals)
        mean = sum(vals) / n
        se = math.sqrt(sum((x - mean) ** 2 for x in vals) / (n - 1) / n)
        line = [l for l in history_of("aggregated").splitlines() if l.startswith("VDGV")][0]
        self.assertIn(str(n), line.split())
        self.assertIn("%.3f" % mean, line)
        self.assertIn("%.3f" % se, line)

    def test_it_does_not_order_variants_by_mean(self):
        # Ordering by mean would put the leader on top and so recommend it; order is by first appearance.
        seqs = [l.split()[0] for l in history_of("aggregated").splitlines()[1:]]
        self.assertEqual(seqs, ["VDGV", "ADGV", "WWGV"])

    def test_it_still_reports_failures_and_rejections(self):
        # Failures and rejections stay visible so the agent can still track its budget.
        h = history_of("aggregated")
        self.assertIn("failed", h)
        self.assertIn("not viable", h)

    def test_it_does_not_invent_a_standard_error_from_one_measurement(self):
        # An SE from one reading is undefined; printing 0.000 would claim the reading is exact.
        line = [l for l in history_of("aggregated").splitlines() if l.startswith("ADGV")][0]
        self.assertIn("not estimable", line)
        self.assertNotIn("0.000", line)

    def test_the_raw_rungs_are_not_aggregated(self):
        for rung in ("blind", "baseline", "informed", "instructed", "forced", "decision_rule"):
            self.assertIn("round  candidate  reading", history_of(rung), rung)

    def test_aggregation_survives_to_the_nomination_prompt(self):
        # The nomination prompt must be aggregated too, since that is where the decision is made.
        nom = prompts.build_nomination("aggregated", H, 15, 4, 0.42)
        self.assertIn("standard error of the mean", nom)
        self.assertNotIn("round  candidate  reading", nom)


class DecisionRuleAddsOneSentenceAndNoFact(unittest.TestCase):
    def test_it_is_instructed_plus_exactly_one_block(self):
        extra = body("decision_rule")[len(body("instructed")):]
        self.assertEqual(extra.strip().count("\n- "), 0, "more than one bullet added")
        self.assertIn("AVERAGE", extra)

    def test_it_does_not_name_the_failure_mode(self):
        # Naming the failure mode would give the agent a diagnosis the other rungs lack.
        extra = body("decision_rule")[len(body("instructed")):].lower()
        for leak in ("single highest", "highest single", "curse", "inflat", "overestimat",
                     "regress", "impostor", "lucky"):
            self.assertNotIn(leak, extra, leak)

    def test_it_does_not_change_the_history_presentation(self):
        self.assertEqual(history_of("decision_rule"), history_of("instructed"))

    def test_it_is_absent_from_every_other_rung(self):
        for rung in ("blind", "baseline", "informed", "instructed", "forced", "aggregated"):
            self.assertNotIn("AVERAGE", body(rung), rung)


class TheLadderStaysCumulative(unittest.TestCase):
    def test_forced_and_blind_are_byte_identical(self):
        self.assertEqual(body("forced"), body("blind"))

    def test_each_rung_contains_its_predecessor(self):
        for lo, hi in (("blind", "baseline"), ("baseline", "informed"),
                       ("informed", "instructed"), ("instructed", "decision_rule")):
            self.assertTrue(body(hi).startswith(body(lo)), "%s -> %s" % (lo, hi))

    def test_blind_never_mentions_measurement_error(self):
        b = body("blind").lower()
        for leak in ("measurement error", "sigma", "noise", "average", "replicat", "sqrt"):
            self.assertNotIn(leak, b, leak)

    def test_an_unknown_rung_raises(self):
        with self.assertRaises(ValueError):
            prompts.build("aggregated_v2", H, 2, 15, 4, 56, 0.42)


class LandscapeSubstitutionIsTotal(unittest.TestCase):
    def test_no_landscape_leaks_another_landscapes_vocabulary(self):
        # An abstract cell that keeps a biological word would keep the prior it exists to remove.
        # History is empty because a campaign's own sequences come from the harness; only the template is tested.
        for name in prompts.LANDSCAPES:
            txt = prompts.build("instructed", [], 1, 15, 4, 60, 0.42, landscape=name).lower()
            mine = {v.lower() for v in prompts.LANDSCAPES[name].values()
                    if isinstance(v, str)}
            # Words in the unsubstituted template belong to every landscape; only words filled in from
            # placeholders can leak.
            template = (prompts.HEADER + prompts.BASELINE_BLOCK + prompts.INFORMED_BLOCK
                        + prompts.INSTRUCTED_BLOCK + prompts.DECISION_RULE_BLOCK
                        + prompts.FOOTER + prompts.NOMINATE).lower()
            for other, t in prompts.LANDSCAPES.items():
                if other == name:
                    continue
                for key in ("metric", "system", "parent", "item"):
                    term = t[key].lower()
                    # A term contained in one of this landscape's own values ("score" in "functional score") is not a leak.
                    if any(term in v for v in mine) or term in template:
                        continue
                    self.assertNotIn(term, txt, "%s leaked %s=%r from %s"
                                     % (name, key, term, other))

    def test_the_abstract_framing_carries_no_biology(self):
        txt = prompts.build("instructed", [], 1, 15, 4, 60, 0.42, landscape="abstract").lower()
        for bio in ("protein", "amino acid", "binding", "gb1", "phoq", "kinase", "variant"):
            self.assertNotIn(bio, txt, bio)

    def test_the_abstract_alphabet_is_not_the_amino_acid_alphabet(self):
        # The amino-acid alphabet alone would let a model recognise the biology with no biological word present.
        abstract = prompts.LANDSCAPES["abstract"]["alphabet"]
        for name, t in prompts.LANDSCAPES.items():
            if name != "abstract":
                self.assertNotEqual(abstract, t["alphabet"],
                                    "abstract shares %s's alphabet" % name)
        self.assertNotIn("abstract", [None])  # keep the intent explicit below
        # Positive form: the abstract alphabet must be the first 20 letters, which no protein uses.
        self.assertEqual(abstract, "".join(chr(ord("A") + i) for i in range(20)))

    def test_the_abstract_cell_shares_no_sequence_with_a_biological_cell(self):
        # A real GB1 sequence in the abstract cell would restore the biological prior with no biological word present.
        a = prompts.LANDSCAPES["abstract"]
        for name, t in prompts.LANDSCAPES.items():
            if name == "abstract":
                continue
            for key in ("parent", "example"):
                self.assertNotEqual(a[key], t[key], "abstract shares %s's %s" % (name, key))
        # Its own sequences must be spellable in its own alphabet, or the prompt contradicts itself.
        for key in ("parent", "example"):
            self.assertTrue(set(a[key]) <= set(a["alphabet"]),
                            "abstract %s=%r is not spellable in its alphabet" % (key, a[key]))

    def test_every_placeholder_is_filled_in_every_landscape_and_rung(self):
        for name in prompts.LANDSCAPES:
            for rung in prompts.RUNGS:
                for txt in (prompts.build(rung, H, 2, 15, 4, 56, 0.42, landscape=name),
                            prompts.build_nomination(rung, H, 15, 4, 0.42, landscape=name)):
                    self.assertNotIn("{", txt, "%s/%s" % (name, rung))

    def test_an_unknown_landscape_or_substitution_raises(self):
        with self.assertRaises(ValueError):
            prompts.terms("gb1_chemistry")
        with self.assertRaises(ValueError):
            prompts.terms("gb1_bio", solvent="water")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TheNoiseStatementMustNotMISQUOTETheNoise(unittest.TestCase):
    """The Quantitative rung's noise statement matches the real noise model and its constants."""
    CV, FLOOR = 0.073, (1 / 557) / (285 / 557)

    def mult(self, rung="informed", **kw):
        return prompts.build(rung, [], 1, 15, 4, 60, 0.0, noise_model="multiplicative",
                             cv=self.CV, noise_floor=self.FLOOR, **kw)

    def numbers_in_the_statement(self, txt):
        line = " ".join(l for l in txt.splitlines() if "sigma(f)" in l or "* f)^2" in l)
        return [float(x) for x in re.findall(r"\d+\.\d+", line)]

    def test_the_stated_constants_round_trip_to_the_real_ones(self):
        got = self.numbers_in_the_statement(self.mult())
        self.assertTrue(got, "no multiplicative noise statement found")
        # Every printed constant must equal a real one to within its own printed precision.
        for want in (self.FLOOR, self.CV):
            self.assertTrue(any(abs(g - want) <= 0.005 * abs(want) for g in got),
                            "constant %r is not stated within 0.5%% anywhere in %r" % (want, got))

    def test_the_floor_is_not_printed_as_zero(self):
        for g in self.numbers_in_the_statement(self.mult()):
            self.assertNotEqual(g, 0.0)
        self.assertNotIn("sqrt(0^2", self.mult())
        self.assertNotIn("sqrt(0.00^2", self.mult())

    def test_the_cv_is_not_truncated_to_two_decimals(self):
        # Check the stated value against the real cv, not the absence of one string.
        got = self.numbers_in_the_statement(self.mult())
        best = min(got, key=lambda g: abs(g - self.CV))
        self.assertLess(abs(best - self.CV), 0.0005,
                        "cv stated as %r against a true %r" % (best, self.CV))

    def test_the_two_noise_statements_never_appear_together(self):
        m, a = self.mult(), prompts.build("informed", [], 1, 15, 4, 60, 4.456)
        self.assertIn("sigma(f)", m)
        self.assertNotIn("standard deviation sigma = ", m)
        self.assertIn("standard deviation sigma = ", a)
        self.assertNotIn("sigma(f)", a)

    def test_the_noise_model_is_chosen_by_the_noise_and_not_by_the_rung(self):
        # The noise model is a required, validated argument, so the prompt cannot state a different model from the oracle's.
        with self.assertRaises(ValueError):
            prompts.build("informed", [], 1, 15, 4, 60, 0.0, noise_model="multiplicative")
        with self.assertRaises(ValueError):
            prompts.build("informed", [], 1, 15, 4, 60, 0.0, noise_model="heteroscedastic",
                          cv=0.073, noise_floor=0.0035)

    def test_the_blind_rung_says_nothing_about_noise_under_either_model(self):
        b = self.mult(rung="blind").lower()
        for leak in ("sigma", "gaussian", "standard deviation", "measurement error"):
            self.assertNotIn(leak, b, leak)

    def test_the_statement_recommends_nothing(self):
        extra = self.mult()[len(self.mult(rung="baseline")):].lower()
        for advice in ("you should", "consider", "it is worth", "we recommend", "therefore you",
                       "replicate", "average", "repeat"):
            self.assertNotIn(advice, extra, advice)

    def test_every_rung_renders_under_multiplicative_noise(self):
        for rung in prompts.RUNGS:
            txt = self.mult(rung=rung)
            self.assertNotIn("{", txt, rung)


class TheParserMustAcceptTheAlphabetThePromptGAVE(unittest.TestCase):
    """The parser accepts every letter of the alphabet the prompt states, including B, J and O on the generated landscape."""

    def test_a_proposal_legal_in_the_landscapes_alphabet_is_accepted(self):
        from repdef import llm_policy as LP
        abstract = prompts.LANDSCAPES["abstract"]["alphabet"]
        for seq in ("GDJF", "BBBB", "OJBO", "ABCD"):
            got, status, notes = LP.parse("%s | a reason" % seq, 1, alphabet=abstract)
            self.assertEqual(status, "ok", "%s rejected on the abstract alphabet: %s" % (seq, notes))
            self.assertEqual(got[0][0], seq)

    def test_the_protein_alphabet_still_rejects_ambiguity_codes(self):
        from repdef import llm_policy as LP
        got, status, notes = LP.parse("GDJF | a reason", 1)
        self.assertNotEqual(status, "ok")
        self.assertIn("J", "".join(notes))

    def test_a_proposal_illegal_in_the_landscapes_alphabet_is_rejected(self):
        from repdef import llm_policy as LP
        abstract = prompts.LANDSCAPES["abstract"]["alphabet"]
        _, status, _ = LP.parse("VWYZ | a reason", 1, alphabet=abstract)
        self.assertNotEqual(status, "ok", "V, W, Y, Z are outside the abstract alphabet")

    def test_the_policy_takes_its_alphabet_from_its_prompt_landscape(self):
        # The alphabet the prompt states and the alphabet the parser accepts must be the same.
        from repdef import llm_policy as LP
        for name, t in prompts.LANDSCAPES.items():
            pol = LP.LLMPolicy("m", "instructed", 1.0, landscape=name)
            self.assertEqual(set(pol.alphabet), set(t["alphabet"]), name)
            stated = prompts.build("instructed", [], 1, 15, 4, 60, 1.0, landscape=name)
            self.assertIn(t["alphabet"], stated,
                          "%s states an alphabet the prompt does not contain" % name)


class AStatusMustNotMaskItsOwnCause(unittest.TestCase):
    """A short count caused by alphabet rejections is reported as such, not as a model format error."""

    def test_a_short_count_caused_by_the_alphabet_says_so(self):
        from repdef import llm_policy as LP
        txt = "\n".join(["GDIF | a", "GDIE | b", "GDJF | c", "HDIF | d"])
        got, status, notes = LP.parse(txt, 4)            # protein alphabet rejects the J
        self.assertEqual(len(got), 3)
        self.assertEqual(status, "alphabet_then_wrong_count")
        self.assertIn("CONSEQUENCE", " ".join(notes))

    def test_a_genuine_format_failure_is_still_called_one(self):
        from repdef import llm_policy as LP
        got, status, notes = LP.parse("GDIF | a\nGDIE | b", 4)
        self.assertEqual(status, "wrong_count")
        self.assertIn("no alphabet rejections", " ".join(notes))

    def test_the_same_reply_is_ok_on_the_landscape_that_allows_those_letters(self):
        from repdef import llm_policy as LP
        txt = "\n".join(["GDIF | a", "GDIE | b", "GDJF | c", "HDIF | d"])
        _, status, _ = LP.parse(txt, 4, alphabet=prompts.LANDSCAPES["abstract"]["alphabet"])
        self.assertEqual(status, "ok")


class TheParserMustReadTheDecisionAndNotTheReasoning(unittest.TestCase):
    """The parser reads the pipe-separated decision lines and ignores sequences mentioned in a reasoning preamble."""

    PREAMBLE = ("Looking at the data:\n"
                "- GDKF: readings 8.142, 7.282, 6.975 -> mean ~7.35\n"
                "- GDNF: 7.738, 7.512 -> mean ~7.28\n"
                "- GDOF: 7.529, 7.220 -> mean ~7.37\n"
                "- GDMF: 7.090\n\n"
                "Position 3 looks good, so:\n"
                "GDPF | extend position 3\n"
                "GDSF | extend position 3 further\n"
                "GDKF | replicate the leader\n"
                "GDTF | probe position 3\n")

    def test_it_takes_the_pipe_lines_and_ignores_the_preamble(self):
        from repdef import llm_policy as LP
        got, status, _ = LP.parse(self.PREAMBLE, 4,
                                  alphabet=prompts.LANDSCAPES["abstract"]["alphabet"])
        self.assertEqual(status, "ok")
        self.assertEqual([g[0] for g in got], ["GDPF", "GDSF", "GDKF", "GDTF"])
        # The preamble sequences must NOT appear as proposals in their own right.
        self.assertNotIn("GDNF", [g[0] for g in got])
        self.assertNotIn("GDOF", [g[0] for g in got])

    def test_leniency_survives_for_a_reply_that_never_uses_a_pipe(self):
        from repdef import llm_policy as LP
        got, status, _ = LP.parse("GDPF: a\nGDSF: b\nGDKF: c\nGDTF: d", 4,
                                  alphabet=prompts.LANDSCAPES["abstract"]["alphabet"])
        self.assertEqual(status, "ok")
        self.assertEqual(len(got), 4)

    def test_a_bare_list_still_parses(self):
        from repdef import llm_policy as LP
        got, status, _ = LP.parse("GDPF\nGDSF\nGDKF\nGDTF", 4,
                                  alphabet=prompts.LANDSCAPES["abstract"]["alphabet"])
        self.assertEqual(status, "ok")

    def test_the_tier_is_recorded(self):
        from repdef import llm_policy as LP
        for txt, want in ((self.PREAMBLE, "pipe"), ("GDPF: a\nGDSF: b", "loose"),
                          ("GDPF\nGDSF", "bare")):
            _, _, notes = LP.parse(txt, 2, alphabet=prompts.LANDSCAPES["abstract"]["alphabet"])
            self.assertIn("format tier: %s" % want, " ".join(notes))
