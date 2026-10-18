"""Tests that the writing-style linter catches a sentence that breaks each rule and lets each exemption through."""
import os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINT = os.path.join(ROOT, "scripts", "style_lint.py")

MUST_CATCH = {
    "contrast framing": "This is not a threshold, it is a rationalisation.",
    "X, not Y": "The task tests memory, not search.",
    "and not Y": "A pilot figure is an estimate and not a number.",
    "rather than": "We localise the shortfall to evaluation rather than tool selection.",
    "em or en dash": "The result is clear \u2014 agents replicate too much.",
    "rhetorical question": "So what does this mean for lab agents?",
    "reveal opener": "Here's the thing about replication.",
    "hype or filler": "Crucially, the agents delve into the noise model.",
    "robust as praise": "The pipeline is robust and well engineered.",
    "landscape as metaphor": "The current landscape of agent benchmarks is crowded.",
    "slogan or chiasmus": "It survives review; the reverse does not.",
    "vague quantity": "Many orders were non-viable in the first round.",
    "process narration": "We fixed the parser before the top-up launched.",
    # A sentence whose only job is to say the next one matters.
    "empty deixis": "The supply of instances is unbounded. That matters here.",
    "self-reference as emphasis": "The reference is easier in exactly the way this paper is about.",
    "negated claim": "That persistence is not role-triggered.",
    "enumerating lead-in": "We contribute five things.",
    "sentence opens with a conjunction": "We validate it outside. And guidance for builders follows.",
    "good-at / poor-at antithesis":
        "That uses what these models are decent at, proposing candidates, and removes what they are "
        "poor at, allocating a budget.",
}

# Headings are checked as LaTeX headings, the form in which the heading rules apply.
MUST_CATCH_IN_A_HEADING = {
    "heading asks a question": "\\paragraph{Is the environment too easy?}",
    "heading as slogan": "\\paragraph{Calibration is the skill.}",
    "heading states a negative": "\\paragraph{The environment is not trivial.}",
    "heading echoes itself": "\\paragraph{The reference is a climber, and so are the agents.}",
    "two sentences in a heading": "\\paragraph{On why the rate is high. This is a hypothesis.}",
}

# A complete sentence opening with "But" is ordinary English; the conjunction rule targets "And" fragments.
SIGNIFICANT_AS_A_TEST_RESULT = ("With one of six contrasts significant and three different responses, we do not "
                                "generalise. The drop was significant after Holm correction.")
AS_MANY_COMPARES = "It tried about as many candidates under the rule (3.7 against 3.8)."
MANY_IS_VAGUE = "It tried many candidates under the rule."
SIGNIFICANT_AS_A_SIZE = "Replication showed a significant increase under the rule."
BUT_IS_ALLOWED = "They tried few variants. But the ones they skipped cost them more than careful picking gained."

# A caption is prose and is meant to run to several sentences. It is the one exemption.
CAPTION_MUST_NOT_CATCH = "\\caption{The two scripted references. Neither replaces the other.}"

# The rules run on whole paragraphs, so a banned phrase split across a line break is still caught.
WRAPPED = ("A reference that does not pay for a wrong guess is easier in exactly the\n"
           "dimension this paper is about.")
WRAPPED_ANTITHESIS = ("That uses what these models are decent\n"
                      "at, proposing candidates, and removes what they are poor at, allocating a budget.")

# Advisory rules report the line without failing the run, because no regex can tell whether a triplet
# adds content or whether a passive sentence is the right choice.
MUST_ADVISE = {
    "rhythm triplet": "The pipeline is fast, cheap and reliable.",
    "passive voice": "Re-orders were observed in every condition.",
    "unchecked invariance": "The agents hold one share nearly everywhere.",
}

MUST_NOT_CATCH = [
    # A verbatim quotation is evidence. Both of these are real quotes from cited papers.
    'They report that "all other configurations did not result in robust exploratory behavior".',
    'They localise the shortfall "to evaluation rather than tool selection: agents pick tools well".',
    # Backticked code is not prose.
    "Set `explore_scope=\"landscape\"` so non-viable proposals happen.",
    # Legitimate technical uses that the rules deliberately allow.
    "The conclusion is robust to the choice of reference.",
    "A robustness check on 1,500 seeds gives the same optimum.",
    "Fitness comes from a generated NK landscape with K=1.",
    "We replicate one slot in four, not only at the start.",
]


def lint(text, name="PAPER_probe.md", extra=""):
    d = tempfile.mkdtemp()
    p = os.path.join(d, name)
    with open(p, "w") as f:
        f.write("# Probe\n\n" + text + "\n" + extra)
    r = subprocess.run([sys.executable, "-B", LINT, p], capture_output=True, text=True)
    return r.returncode, r.stdout


class StyleLintCatchesItsRules(unittest.TestCase):

    def test_every_rule_catches_a_sentence_written_to_break_it(self):
        for rule, sentence in MUST_CATCH.items():
            code, out = lint(sentence)
            self.assertEqual(code, 1, "rule %r did not fail on %r" % (rule, sentence))
            self.assertIn(rule, out, "rule %r fired under a different name on %r:\n%s"
                          % (rule, sentence, out))

    def test_every_heading_rule_catches_a_heading_written_to_break_it(self):
        for rule, heading in MUST_CATCH_IN_A_HEADING.items():
            code, out = lint(heading, name="PAPER_probe.tex")
            self.assertEqual(code, 1, "heading rule %r did not fail on %r" % (rule, heading))
            self.assertIn(rule, out, "heading rule %r fired under another name:\n%s" % (rule, out))

    def test_significant_as_a_test_result_is_allowed(self):
        code, out = lint(SIGNIFICANT_AS_A_TEST_RESULT)
        self.assertNotIn("vague quantity", out, "a stated test result was flagged as vague:\n%s" % out)

    def test_as_many_with_both_numbers_is_allowed(self):
        code, out = lint(AS_MANY_COMPARES)
        self.assertNotIn("vague quantity", out, "a comparison with both numbers stated was flagged:\n%s" % out)

    def test_many_alone_is_still_caught(self):
        code, out = lint(MANY_IS_VAGUE)
        self.assertIn("vague quantity", out, "'many candidates' hides a count and was not caught")

    def test_significant_as_a_size_is_still_caught(self):
        code, out = lint(SIGNIFICANT_AS_A_SIZE)
        self.assertIn("vague quantity", out, "'a significant increase' hides a size and was not caught")

    def test_a_sentence_opening_with_but_is_allowed(self):
        code, out = lint(BUT_IS_ALLOWED)
        self.assertNotIn("sentence opens with a conjunction", out,
                         "a complete sentence opening with But was flagged:\n%s" % out)

    def test_a_caption_may_run_to_several_sentences(self):
        code, out = lint(CAPTION_MUST_NOT_CATCH, name="PAPER_probe.tex")
        self.assertNotIn("two sentences in a heading", out,
                         "a caption is prose and must not be held to one phrase:\n%s" % out)
        self.assertEqual(code, 0, out)

    def test_a_banned_phrase_split_across_a_line_break_is_still_caught(self):
        code, out = lint(WRAPPED, name="PAPER_probe.tex")
        self.assertIn("self-reference as emphasis", out,
                      "a phrase that wraps went unreported:\n%s" % out)
        self.assertEqual(code, 1, out)

    def test_the_good_at_poor_at_pairing_is_caught_across_a_line_break(self):
        """The good-at / poor-at pairing is caught when it wraps across a line break."""
        code, out = lint(WRAPPED_ANTITHESIS, name="PAPER_probe.tex")
        self.assertIn("good-at / poor-at antithesis", out,
                      "the pairing went unreported when it wrapped:\n%s" % out)
        self.assertEqual(code, 1, out)

    def test_a_wording_rule_binds_inside_an_appendix(self):
        """A wording rule still applies inside an appendix, where the length cap does not."""
        code, out = lint("% lint-scope: appendix\nThat persistence is not role-triggered.",
                         name="PAPER_probe.tex")
        self.assertIn("negated claim", out, "a wording rule stopped at the appendix boundary:\n%s" % out)
        self.assertEqual(code, 1, out)

    def test_the_advisory_rules_report_without_failing_the_run(self):
        for rule, sentence in MUST_ADVISE.items():
            code, out = lint(sentence)
            self.assertIn(rule, out, "advisory rule %r did not report on %r" % (rule, sentence))
            self.assertIn("advisory", out)
            self.assertEqual(code, 0, "advisory rule %r must not fail the run:\n%s" % (rule, out))

    def test_process_narration_fails_in_the_main_text_and_passes_in_an_appendix(self):
        line = "On 2026-09-28 we fixed the parser."
        code, _out = lint(line)
        self.assertEqual(code, 1, "process narration must fail in the main text")
        code, out = lint("Short sentence here.", extra="\n## Appendix C\n\n" + line + "\n")
        self.assertEqual(code, 0, "process narration belongs in the appendix:\n%s" % out)

    def test_an_explicit_scope_marker_opens_and_closes_appendix_scope(self):
        line = "On 2026-09-28 we fixed the parser."
        code, out = lint("<!-- lint-scope: appendix -->\n\n" + line)
        self.assertEqual(code, 0, "a lint-scope marker must exempt the section:\n%s" % out)
        code, _out = lint("<!-- lint-scope: appendix -->\n\nfine.\n\n"
                          "<!-- lint-scope: main -->\n\n" + line)
        self.assertEqual(code, 1, "closing the marker must restore the main-text rules")

    def test_how_many_is_a_question_and_not_a_vague_quantity(self):
        code, out = lint("How many replicates to take has a classical answer.")
        self.assertEqual(code, 0, "'how many' is a question phrase:\n%s" % out)

    def test_quotations_code_and_technical_uses_are_not_flagged(self):
        for sentence in MUST_NOT_CATCH:
            code, out = lint(sentence)
            self.assertEqual(code, 0, "false positive on %r:\n%s" % (sentence, out))

    def test_a_long_main_text_sentence_fails_and_the_same_one_in_an_appendix_does_not(self):
        long = " ".join(["word"] * 40) + "."
        code, out = lint(long)
        self.assertEqual(code, 1)
        self.assertIn("sentence over cap", out)
        code, out = lint("Short sentence here.", extra="\n## Appendix A\n\n" + long + "\n")
        self.assertEqual(code, 0, "an appendix sentence must not fail the main-text cap:\n%s" % out)

    def test_a_long_quotation_does_not_count_against_the_author(self):
        quote = '"' + " ".join(["quoted"] * 40) + '"'
        code, out = lint("They write %s in their abstract." % quote)
        self.assertEqual(code, 0, "a verbatim quotation must not trip the sentence cap:\n%s" % out)

    def test_a_latex_quotation_is_exempt_and_the_same_words_unquoted_are_not(self):
        quoted = "By its fixed rule the replication read ``direction holds, not significant'' on 119 pairs."
        code, out = lint(quoted, name="PAPER_probe.tex")
        self.assertEqual(code, 0, "a LaTeX-quoted label was linted as the authors' writing:\n%s" % out)
        code, out = lint("The effect was real, not significant.", name="PAPER_probe.tex")
        self.assertEqual(code, 1, "the same construction outside quotes must still be caught:\n%s" % out)

    def test_the_paper_files_are_clean_at_head(self):
        r = subprocess.run([sys.executable, "-B", LINT], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, "spec/PAPER_*.md is not clean:\n%s" % r.stdout)


if __name__ == "__main__":
    unittest.main()
