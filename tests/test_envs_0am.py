"""Tests for the additional landscapes: the relabelling, the rules carried over from the grid, seed pairing, the yardsticks and an end-to-end run.

The relabelling must be a bijection that carries fitness and Hamming neighbours over exactly, draws must
pair by seed across names, the yardsticks must reproduce from the committed file, and a campaign must run
end to end on every new landscape with a prompt that says what the landscape is.
"""
import json, os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEEDS_DATA = unittest.skipUnless(
    all(os.path.exists(os.path.join(ROOT, "data", f)) for f in ("gb1.csv", "phoq.csv")),
    "needs the protein data: python3 scripts/download_data.py")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from repdef import envs as E, landscape as L, llm, oracle as O              # noqa: E402
import repdef.rng as R                                                      # noqa: E402

YARD = os.path.join(ROOT, "results", "yardsticks_0am.json")


def h1(seq, alphabet):
    return {seq[:i] + a + seq[i + 1:] for i in range(4) for a in alphabet if a != seq[i]}


@NEEDS_DATA
class Relabelling(unittest.TestCase):

    def test_each_position_is_an_independent_bijection(self):
        for seed in E.SCRAMBLE_SEEDS.values():
            maps = E.scramble(seed)
            self.assertEqual(len(maps), 4)
            for m in maps:
                self.assertEqual(sorted(m), sorted(E.AA))
                self.assertEqual(sorted(m.values()), sorted(E.ABSTRACT), "not onto A to T")
            self.assertEqual(len({tuple(sorted(m.items())) for m in maps}), 4,
                             "two positions share a map, so they are not independent draws")
        self.assertNotEqual(E.scramble(E.SCRAMBLE_SEEDS["gb1"]), E.scramble(E.SCRAMBLE_SEEDS["phoq"]))

    def _carries_over(self, env, source):
        ls = L.load(source)
        f = E.GB1_MAX / max(ls.fitness.values())
        maps = E.scramble(env.meta["scramble_seed"])
        self.assertEqual(len(env.fit), 160_000)
        for s in sorted(ls.fitness)[::997]:
            d = E.relabel(s, maps)
            self.assertEqual(env.fit[d], ls.fitness[s] * f)
            self.assertEqual({E.relabel(x, maps) for x in h1(s, E.AA)}, h1(d, E.ABSTRACT),
                             "Hamming neighbours are not carried over for %s" % s)
            self.assertEqual(env.source(d), s)
            self.assertEqual(env.rng_key[d], s)

    def test_gb1_fitness_and_neighbours_are_carried_over_exactly(self):
        self._carries_over(E.gb1_scrambled(), "gb1")

    def test_phoq_fitness_and_neighbours_are_carried_over_exactly(self):
        self._carries_over(E.phoq_scrambled(), "phoq")

    def test_the_scrambled_and_real_gb1_arms_are_one_landscape(self):
        real, scr = E.gb1_real(), E.gb1_scrambled()
        self.assertEqual({scr.source(s) for s in scr.pool}, set(real.pool))
        self.assertEqual(scr.source(scr.anchor), real.anchor)
        self.assertEqual(scr.source(scr.example), real.example)
        self.assertEqual([scr.source(s) for s in scr.top10], list(real.top10))
        self.assertEqual(scr.reading, real.reading)
        self.assertEqual(real.top10[0], "FWAA")


@NEEDS_DATA
class GridRulesCarryOver(unittest.TestCase):

    def test_the_viability_rule_is_the_grids(self):
        import grid
        fit, pool = grid.landscape()
        thr, mine = E.grid_pool(fit)
        self.assertEqual(mine, pool)

    def test_pools_are_the_grids_size_and_every_zero_is_non_viable(self):
        for env, source in ((E.gb1_real(), "gb1"), (E.phoq_scrambled(), "phoq")):
            self.assertEqual(len(env.pool), 11_199)
            self.assertGreater(env.threshold, 0.0)
            zeros = [s for s, v in env.fit.items() if v == 0.0]
            self.assertEqual(len(zeros), L.EXPECTED[source]["exact_zeros"])
            self.assertFalse(set(zeros) & env.pool)
            self.assertAlmostEqual(env.global_best, E.GB1_MAX, places=9)

    def test_the_reference_point_rule_is_the_grids(self):
        import grid
        fit, pool = grid.landscape()
        self.assertEqual(E.reference_point(fit, pool, E.ABSTRACT), grid.reference_point(fit, pool))

    def test_panel_k_seeds_are_fresh_disjoint_and_planned_by_offset(self):
        seen = set()
        for k in E.PANEL_K:
            s = set(E.PANEL_K_SEEDS[k])
            self.assertEqual(len(s), E.PANEL_K_N)
            self.assertFalse(s & seen)
            seen |= s
        self.assertNotIn(1, seen, "seed 1 is the grid's landscape")
        self.assertEqual([E.panel_k_index(i) for i in (0, 19, 20, 39, 40, 59)], [0, 19, 0, 19, 0, 19])
        self.assertEqual(E.panel_k_env(2, 23).meta["nk_seed"], E.PANEL_K_SEEDS[2][3])


@NEEDS_DATA
class DrawsPairBySeed(unittest.TestCase):

    def test_the_same_variant_draws_the_same_failures_and_noise_under_either_name(self):
        real, scr = E.gb1_real(), E.gb1_scrambled()
        kw = dict(noise_model="multiplicative", cv=0.073, noise_floor=(1 / 557) / (285 / 557))
        o1 = O.Oracle(real.fit, real.pool, 0.0, 424242, 0.15, **kw)
        o2 = O.Oracle(scr.fit, scr.pool, 0.0, 424242, 0.15, rng_key=scr.rng_key, **kw)
        maps = E.scramble(scr.meta["scramble_seed"])
        order = list(real.top10) * 3 + [real.anchor, "VDGV", "AAAA"] * 2
        outs = set()
        for s in order:
            a, b = o1.measure(s, 1), o2.measure(E.relabel(s, maps), 1)
            self.assertEqual((a.outcome, a.observed), (b.outcome, b.observed))
            outs.add(a.outcome)
        self.assertTrue({"ok", "failed"} <= outs, "the sequence exercised too few outcomes: %s" % outs)

    def test_without_a_key_the_draws_are_unchanged(self):
        o = O.Oracle({"ABCD": 2.0}, {"ABCD"}, 0.0, 7, 0.0, noise_model="multiplicative", cv=0.073,
                     noise_floor=0.0035)
        sd = (0.0035 ** 2 + (2.0 * 0.073) ** 2) ** 0.5
        self.assertEqual(o.measure("ABCD", 1).observed, 2.0 + sd * R.normal("noise", 7, "ABCD", 0))


@unittest.skipUnless(os.path.exists(YARD), "results/yardsticks_0am.json is not built yet")
@NEEDS_DATA
class Yardsticks(unittest.TestCase):

    def test_the_committed_policy_reproduces_the_published_curve(self):
        y = json.load(open(YARD))
        self.assertTrue(y["grid"]["reproduces_committed"])
        pub = json.load(open(os.path.join(ROOT, "results", "fair_reference_curve.json")))["curves"]["fair"]
        for k, row in y["grid"]["committed_policy"]["curve"].items():
            self.assertEqual(row["mean"], pub[k]["mean"])

    def test_the_alphabet_policy_never_proposes_a_string_outside_its_landscape(self):
        y = json.load(open(YARD))
        self.assertGreater(y["grid"]["committed_policy"]["curve"]["1"]["proposed_outside_landscape"], 0,
                           "the committed policy's defect should show on the grid's landscape")
        for lab, s in list(y["landscapes"].items()) + [("grid", y["grid"]["alphabet_policy"])]:
            for k, row in s["curve"].items():
                self.assertEqual(row["proposed_outside_landscape"], 0, (lab, k))

    def test_yardsticks_reproduce_from_their_seeds(self):
        import yardsticks_0am as Y
        y = json.load(open(YARD))
        for label, name in (("gb1_scrambled_s20261003_p93.0", "gb1_scrambled"),
                            ("nk_uniform_k3_s7300_p93.0", "nk:3:7300")):
            want = y["landscapes"][label]["check_first_seeds"]["1"]
            got = [Y.one((name, "alphabet", 1, i))[4] for i in range(Y.CHECK_N)]
            self.assertEqual([None if g is None else [g["nom"], g["share"]] for g in got], want, label)

    def test_every_landscape_has_a_yardstick_and_panel_k_is_complete(self):
        y = json.load(open(YARD))
        for k in E.PANEL_K:
            self.assertEqual(len(y["panel_k"][str(k)]["landscapes"]), E.PANEL_K_N)
        self.assertIn("phoq_scrambled_s20261004_p93.0", y["landscapes"])
        self.assertNotIn("gb1_real_p93.0", y["landscapes"], "real-name GB1 gets no yardstick")


def stub(prompt, model, **kw):
    """A model that follows the format: it orders the reference point's neighbours in the prompt's own
    alphabet, never repeating within a reply, and nominates the reference point."""
    ref = re.search(r'The reference point is "([A-Z]{4})"', prompt).group(1)
    alphabet = re.search(r"\(([A-Z]{20})\)", prompt).group(1)
    if "ANSWER: XXXX" in prompt:
        return llm.Call(text="ANSWER: %s\nREASON: the reference point" % ref, model=model)
    n = int(re.search(r"Reply with exactly (\d+) lines", prompt).group(1))
    rnd = int(re.search(r"ROUND (\d+) OF", prompt).group(1))
    nb = sorted(h1(ref, alphabet))
    excl = set(re.findall(r"\b([A-Z]{4})\b", prompt.split("must not be proposed again")[-1])) \
        if "must not be proposed again" in prompt else set()
    start = (rnd * 7 + len(excl)) % len(nb)
    cands = [s for s in nb[start:] + nb[:start] if s not in excl]
    lines = ([ref] + cands)[:n] if n > 1 else cands[:1]
    return llm.Call(text="\n".join("%s | stub" % s for s in lines), model=model)


@NEEDS_DATA
class StubEndToEnd(unittest.TestCase):
    """One campaign per new landscape through grid.one_campaign, with a stub in place of the model."""

    def setUp(self):
        self._real = llm.complete
        self.addCleanup(lambda: setattr(llm, "complete", self._real))
        llm.complete = stub

    def run_one(self, env, rung="blind"):
        import grid
        own = []
        row = grid.one_campaign(env.fit, env.pool, env.ps, env.prior, "vendor/stub", rung, 991_000, own,
                                6000, 3, env=env)
        return row, own

    def test_every_new_landscape_runs_and_says_what_it_is(self):
        cases = [(E.gb1_scrambled(), "abstract four-position system", "ABCDEFGHIJKLMNOPQRST"),
                 (E.gb1_real(), "protein G domain B1 (GB1)", "ACDEFGHIKLMNPQRSTVWY"),
                 (E.phoq_scrambled(), "abstract four-position system", "ABCDEFGHIJKLMNOPQRST")]
        cases += [(E.panel_k_env(k, 0), "abstract four-position system", "ABCDEFGHIJKLMNOPQRST")
                  for k in E.PANEL_K]
        for env, system, alphabet in cases:
            for rung in ("blind", "instructed"):
                row, calls = self.run_one(env, rung)
                self.assertEqual(row["landscape"], env.label)
                self.assertEqual(row["anchor"], env.anchor)
                self.assertGreater(row["n_ok"], 0, env.label)
                self.assertEqual((row["slots_used"], row["slots_unaccounted"]), (60, 0), env.label)
                self.assertEqual(row["nominated"], env.anchor)
                self.assertEqual(row["nominated_true"], env.fit[env.anchor])
                self.assertIn("round1_top10_distinct", row)
                self.assertEqual(row["round1_orders"][0], env.anchor)
                first = calls[0]["prompt"]
                self.assertIn(system, first)
                self.assertIn("(%s)" % alphabet, first)
                self.assertIn('The reference point is "%s"' % env.anchor, first)
                self.assertIn("reads about %.2f" % env.reading, first)
                self.assertTrue(all(c["landscape"] == env.label for c in calls))
                self.assertTrue(all(c["parse_status"] == "ok" for c in calls), env.label)
                if env.prompt_landscape == "abstract":
                    for word in ("GB1", "protein", "binding", "PhoQ", "amino"):
                        self.assertNotIn(word, first, (env.label, word))

    def test_real_and_scrambled_gb1_campaigns_pair_by_seed_end_to_end(self):
        """Real-name and scrambled GB1 campaigns pair by seed through grid.one_campaign, not only through the oracle."""
        real, scr = E.gb1_real(), E.gb1_scrambled()
        maps = E.scramble(scr.meta["scramble_seed"])
        want = ["FWAA", "FYAA", "VDGV", real.anchor, "ANCA", "FWCA", "AAAA"]

        def orders(names):
            def model(prompt, model, **kw):
                if "ANSWER: XXXX" in prompt:
                    return llm.Call(text="ANSWER: %s\nREASON: x" % names[0], model=model)
                n = int(re.search(r"Reply with exactly (\d+) lines", prompt).group(1))
                rnd = int(re.search(r"ROUND (\d+) OF", prompt).group(1))
                pick = [names[(rnd + j) % len(names)] for j in range(n)]
                return llm.Call(text="\n".join("%s | x" % q for q in pick), model=model)
            return model

        def readings(calls, env):
            hist = calls[-1]["prompt"].split("HISTORY", 1)[1]
            return [(int(m.group(1)), env.source(m.group(2)), m.group(3).strip()) for m in
                    re.finditer(r"^\s*(\d+)\s+([A-Z]{4})\s+(.+)$", hist, re.M)]
        llm.complete = orders(want)
        _r1, c1 = self.run_one(real)
        llm.complete = orders([E.relabel(q, maps) for q in want])
        _r2, c2 = self.run_one(scr)
        a, b = readings(c1, real), readings(c2, scr)
        self.assertGreater(len(a), 40)
        self.assertEqual(a, b)
        self.assertTrue(any("failed" in x[2] for x in a) and any(re.match(r"^\d", x[2]) for x in a))

    def test_the_round1_top10_log_counts_what_was_ordered(self):
        env = E.gb1_real()

        def knows(prompt, model, **kw):
            if "ANSWER: XXXX" in prompt:
                return llm.Call(text="ANSWER: FWAA\nREASON: recall", model=model)
            n = int(re.search(r"Reply with exactly (\d+) lines", prompt).group(1))
            rnd = int(re.search(r"ROUND (\d+) OF", prompt).group(1))
            # Top-10 variants in round 1 only, so a log that read any other round would count none.
            want = ["FWAA", "FYAA", "VDGV", "AAAA"] if rnd == 1 else ["VDGV", env.anchor]
            return llm.Call(text="\n".join("%s | x" % s for s in (want * 4)[:n]), model=model)
        llm.complete = knows
        row, _c = self.run_one(env)
        self.assertEqual(row["round1_top10_distinct"], 2)
        self.assertTrue(row["round1_top10_any"])
        self.assertTrue(row["round1_global_best"])
        self.assertIsNone(row["round1_orders_source"])


if __name__ == "__main__":
    unittest.main()


class TruthfulReask(unittest.TestCase):
    """With truthful re-asks on, a reply whose lines were dropped for bad letters is told so; every other re-ask is unchanged."""

    def setUp(self):
        self._real = llm.complete
        self.addCleanup(lambda: setattr(llm, "complete", self._real))
        self.prompts = []

    def model(self, first, second):
        def f(prompt, model, **kw):
            self.prompts.append(prompt)
            return llm.Call(text=first if len(self.prompts) == 1 else second, model=model)
        return f

    def view(self):
        from repdef import view as V
        return V.CampaignView((), {"AAAA"}, 1, 15, 4, 0, 60, ("AAAA",), campaign_seed=0, screen=None)

    def policy(self, on):
        from repdef import llm_policy as LP
        p = LP.LLMPolicy("vendor/model-x", "blind", 0.0, landscape="abstract", parent="AAAA", example="BAAA",
                         anchor_reading="1.00")
        p.truthful_reask = on
        return p

    GOOD = "ABCD | a\nABCE | b\nABCF | c\nABCG | d"
    BADU = "ABCD | a\nABCE | b\nABCF | c\nABCU | step past T"

    def test_on_names_the_dropped_lines_and_restates_the_alphabet(self):
        from repdef import llm_policy as LP
        llm.complete = self.model(self.BADU, self.GOOD)
        p = self.policy(True)
        self.assertEqual(p.propose(self.view(), 4), ["ABCD", "ABCE", "ABCF", "ABCG"])
        self.assertTrue(self.prompts[1].endswith(LP.truthful_reask(["ABCU"], "ABCDEFGHIJKLMNOPQRST", 4)))
        self.assertNotIn("did not contain exactly", self.prompts[1])
        self.assertEqual(p.calls[-1]["out_of_alphabet"], ["ABCU"])

    def test_off_sends_the_grids_reask_byte_for_byte(self):
        llm.complete = self.model(self.BADU, self.GOOD)
        self.policy(False).propose(self.view(), 4)
        self.assertTrue(self.prompts[1].endswith(
            "\n\nYour previous reply did not contain exactly 4 candidates, one per line, in the form\n"
            "CANDIDATE | one short reason\nReply again with exactly 4 such lines and nothing else."))

    def test_on_leaves_a_plain_wrong_count_reask_unchanged(self):
        llm.complete = self.model("ABCD | a\nABCE | b\nABCF | c", self.GOOD)
        self.policy(True).propose(self.view(), 4)
        self.assertIn("did not contain exactly 4 candidates", self.prompts[1])
        self.assertNotIn("not in the alphabet", self.prompts[1])

    def test_both_attempts_bad_are_both_logged(self):
        llm.complete = self.model(self.BADU, self.BADU.replace("ABCU", "ABCV"))
        p = self.policy(True)
        self.assertEqual(p.propose(self.view(), 4), [])
        self.assertEqual(p.calls[-1]["out_of_alphabet"], ["ABCU", "ABCV"])


@NEEDS_DATA
class CanaryTestsTheInstrument(unittest.TestCase):

    def test_shrinkage_is_inert_on_real_gb1_and_live_on_the_grid(self):
        import grid
        e = E.gb1_real()
        self.assertEqual(grid.comparator_liveness(e.fit, e.pool, e.prior), 0)
        fit, pool = grid.landscape()
        v = [fit[s] for s in pool]
        import statistics as st
        self.assertGreater(grid.comparator_liveness(fit, pool, (st.mean(v), st.variance(v))), 0)


@NEEDS_DATA
class OutOfAlphabetPerCampaign(unittest.TestCase):

    def setUp(self):
        self._real = llm.complete
        self.addCleanup(lambda: setattr(llm, "complete", self._real))

    def test_the_campaign_row_counts_every_out_of_alphabet_proposal_and_its_letters(self):
        import grid
        env = E.phoq_scrambled()

        def model(prompt, model, **kw):
            if "ANSWER: XXXX" in prompt:
                return llm.Call(text="ANSWER: %s\nREASON: x" % env.anchor, model=model)
            n = int(re.search(r"Reply with exactly (\d+) lines", prompt).group(1))
            told = "not in the alphabet" in prompt.rsplit("ROUND", 1)[-1]
            lines = [env.anchor] * n
            if not told and n == 4:
                lines[-1] = env.anchor[:3] + "U"
            return llm.Call(text="\n".join("%s | x" % q for q in lines), model=model)
        llm.complete = model
        row = grid.one_campaign(env.fit, env.pool, env.ps, env.prior, "vendor/stub", "blind", 991_000, [],
                                6000, 3, env=env, prompt_options={"truthful_reask": True})
        self.assertEqual(row["out_of_alphabet_proposals"], 15)
        self.assertEqual(row["out_of_alphabet_letters"], {"U": 15})
        self.assertEqual(row["rounds_lost_slots"], 0, "told the truth, the stub corrects and loses no round")
        self.assertTrue(row["prompt_options"]["truthful_reask"])
