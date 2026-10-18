"""Tests for three optional prompt settings, each off by default.

With every option off, all thirty default renders match hashes pinned before the options existed. Each
option changes only the text and rule it names, and grid.one_campaign passes one dict to both the prompt
and the campaign rule.
"""
import hashlib, os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from repdef import campaign as C, llm_policy as LP, oracle as O, policies as P, prompts  # noqa: E402

HIST = [(1, "GDIF", "ok", 6.9712), (1, "GDIJ", "failed", None), (1, "GDIE", "rejected", None),
        (1, "GDIF", "ok", 7.5131), (2, "GDIJ", "ok", 7.5952), (2, "AAAA", "lost", None)]
RUNGS = ("blind", "informed", "instructed", "aggregated", "decision_rule")
COMMON = dict(parent="GDIF", fail_pct=15, total=60, example="ADIF", landscape="abstract",
              anchor_reading="6.87", max_reasks=3)
NOISE = {"multiplicative": dict(noise_model="multiplicative", cv=0.073, noise_floor=0.0035087719298245615),
         "exact": dict(noise_model="exact")}
# SHA256 of each default render, taken before the options existed.
PINNED = {
    "exact|aggregated|nomination": "e34a03b52ddead6a24e94010d3c0ec3d0cdcc9a9536b2a89824640a136848ea9",
    "exact|aggregated|replacement": "2024a7596cfc7cacf3392e841631461c6e71068709122a227788dbf209336046",
    "exact|aggregated|round": "a1e8c5e92d42a4a74fd0be0deb885396deb60df2dcc23561d18cd60c06682fbb",
    "exact|blind|nomination": "baa5df0b3fb1a0219230210a2c7bcf04df1238bc0d82ed10f1ed49fa7b909a97",
    "exact|blind|replacement": "fc78950202495cfe2f41f56c6b63f11f1f79a201b91005848585aa82b3d69d15",
    "exact|blind|round": "53c631523494e4c12999253bbe138f7263ca443c28ae73310779306e8bf6ae1d",
    "exact|decision_rule|nomination": "9b5cac4f99b2eeec53e7b1a35732d438430b982798622763a8d0dde34b2e57d2",
    "exact|decision_rule|replacement": "bdb002cf084583458bb5db28e607bedc5c0bca793bd323d66e2cd7b894ba5f0d",
    "exact|decision_rule|round": "bf59ec2d368c940b97969881177b0434b88d7edb78fff6a1c6c11cf05ba8b0a4",
    "exact|informed|nomination": "38ddcdd3aaabb13d995ac92ecda81eaf4bf85a8e599323b04c1a18bfb728fd41",
    "exact|informed|replacement": "ece8e7164e5f16f61f6d11819b7bdb769d4ef1220b0deefaf501fae6cea8c748",
    "exact|informed|round": "a8b8229c9171a4a14e1d2abd9bbd1ce472d6fbe8ed44387ac15e1c5a6a2aa0d5",
    "exact|instructed|nomination": "533f3135f2e01390b3d1094be5044712f4a8e104d43598d4c111660820382d01",
    "exact|instructed|replacement": "f00e358b853988132bacae363866a86ebb323e29ef30745edabb84d3f5dff23e",
    "exact|instructed|round": "87468397e0b10c480bb9363f1eb3b555a3d2c1e3115c530e088add9b92c3c097",
    "multiplicative|aggregated|nomination": "3cad48eaa2465fafced8cd0506273539633484ceaecd49bdb0810bfba548789e",
    "multiplicative|aggregated|replacement": "cb783a874d6c915eff3610d5e655c0816a08eeadec8e476131acdd86c52625e9",
    "multiplicative|aggregated|round": "f342cf4e0c3d6e76dffa6350732f8d42582a881124d0e0e643d1a6869fc4656c",
    "multiplicative|blind|nomination": "baa5df0b3fb1a0219230210a2c7bcf04df1238bc0d82ed10f1ed49fa7b909a97",
    "multiplicative|blind|replacement": "fc78950202495cfe2f41f56c6b63f11f1f79a201b91005848585aa82b3d69d15",
    "multiplicative|blind|round": "53c631523494e4c12999253bbe138f7263ca443c28ae73310779306e8bf6ae1d",
    "multiplicative|decision_rule|nomination": "9896c8bc826cb72786eeb68a7d3d72a8c717a5a5ec9758d8f1a2665ee90b0be6",
    "multiplicative|decision_rule|replacement": "8dce900b3e6a43734d04f9502b45036b571775329748c41e1096d72709e5feeb",
    "multiplicative|decision_rule|round": "2b9f6257bd7fd4b8f506891cf7486b9d442b29a2a601bbcafc3e490f2e285a42",
    "multiplicative|informed|nomination": "82889fabfdb4b17d0f44b456a86bf49ca0cde38d595dee3ce4d16a1e7b93cb38",
    "multiplicative|informed|replacement": "2baaf7b5cf2b92ff68fe91ea5b70b01202ee94734712b20e7521a000f372020a",
    "multiplicative|informed|round": "fd1d7ddf59311fdb8bf57b4a859e4af3c450566139f70834d950bcd83114ff36",
    "multiplicative|instructed|nomination": "4d0ce0964b6946db5f19d5d2422ee2c4e8d9ac0d54dae845b38a22049cee0c6a",
    "multiplicative|instructed|replacement": "5578be842e489bcfad25d87917a7312d5adc1f6fcdef0eb0b715466c2178070f",
    "multiplicative|instructed|round": "98b3027d18857a90a9e45e81809fa7989983cff0e51ce1578f0f320f34a80100"
}
GOAL = "At the end you will nominate one candidate, and your score is that candidate's true value."
RISKFREE = ("An order for a non-viable\ncandidate is rejected at no cost and you choose again. No slot is "
            "ever lost to a non-viable order.")


def renders(noise, rung, **opt):
    nk = NOISE[noise]
    nom_opt = {k: v for k, v in opt.items() if k == "riskfree_rejection"}
    return {"round": prompts.build(rung, HIST, 3, 15, 4, 52, 0.0, **COMMON, **nk, **opt),
            "replacement": prompts.build(rung, HIST, 3, 15, 1, 52, 0.0, **COMMON, **nk, **opt),
            "nomination": prompts.build_nomination(rung, HIST, 15, 4, 0.0, **COMMON, **nk, **nom_opt)}


class Defaults(unittest.TestCase):
    def test_every_default_render_is_byte_identical_to_the_grid(self):
        bad = []
        for noise in NOISE:
            for rung in RUNGS:
                for kind, txt in renders(noise, rung).items():
                    key = "%s|%s|%s" % (noise, rung, kind)
                    if hashlib.sha256(txt.encode()).hexdigest() != PINNED[key]:
                        bad.append(key)
        self.assertEqual(bad, [], "a default prompt changed, so the grid is no longer reproducible")
        self.assertEqual(len(PINNED), 30)


class GoalTrueValue(unittest.TestCase):
    def test_round_and_replacement_carry_it_identically_in_every_condition(self):
        for noise in NOISE:
            goals = set()
            for rung in RUNGS:
                r = renders(noise, rung, goal_true_value=True)
                for kind in ("round", "replacement"):
                    goal = re.search(r"GOAL\n(.*?)\n\nBUDGET", r[kind], re.S).group(1)
                    self.assertIn(GOAL, goal)
                    goals.add(goal)
                self.assertNotIn(GOAL, r["nomination"], "the nomination prompt was not to change")
            self.assertEqual(len(goals), 1, "the GOAL text differs between conditions")

    def test_it_says_nothing_about_readings_or_error(self):
        """Blind withholds that readings carry error; this sentence must not hand it over."""
        for word in ("reading", "error", "noise", "observed", "measure"):
            self.assertNotIn(word, GOAL.lower())

    def test_off_means_absent(self):
        for rung in RUNGS:
            for txt in renders("multiplicative", rung).values():
                self.assertNotIn("your score is", txt)


class FixReplacementBudget(unittest.TestCase):
    def test_the_replacement_budget_line_states_the_real_orders_per_round(self):
        for rung in RUNGS:
            old = renders("multiplicative", rung)["replacement"]
            self.assertIn("15 rounds, 1 orders per round, 60 measurements in total.", old)
            new = prompts.build(rung, HIST, 3, 15, 1, 52, 0.0, **COMMON, **NOISE["multiplicative"],
                                slots_per_round=4)
            self.assertIn("15 rounds, 4 orders per round, 60 measurements in total.", new)
            self.assertIn("Choose 1 candidates to order this round.", new,
                          "the ask itself must still be for the one slot being refilled")

    def test_a_round_prompt_is_unchanged_by_it(self):
        for rung in RUNGS:
            a = prompts.build(rung, HIST, 3, 15, 4, 52, 0.0, **COMMON, **NOISE["multiplicative"])
            b = prompts.build(rung, HIST, 3, 15, 4, 52, 0.0, **COMMON, **NOISE["multiplicative"],
                              slots_per_round=4)
            self.assertEqual(a, b)


class RiskFreePrompt(unittest.TestCase):
    def test_every_prompt_kind_states_the_risk_free_rule_and_never_the_lost_slot(self):
        for noise in NOISE:
            for rung in RUNGS:
                for kind, txt in renders(noise, rung, riskfree_rejection=True).items():
                    self.assertIn(RISKFREE, txt, "%s %s %s" % (noise, rung, kind))
                    self.assertNotIn("THE SLOT IS LOST", txt)
                    self.assertNotIn("up to\n3 times", txt)


class _Stubborn(P.Policy):
    """Proposes non-viable candidates for the first `dead` asks of every slot, then a viable one."""

    def __init__(self, dead, viable_seq, dead_seqs):
        self.dead, self.ok, self.dead_seqs, self.asks = dead, viable_seq, list(dead_seqs), 0

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        out = []
        for _ in range(n_slots):
            if kind == "round":
                self.asks = 0
            self.asks += 1
            out.append(self.dead_seqs[self.asks % len(self.dead_seqs)] if self.asks <= self.dead
                       else self.ok)
        return out


class RiskFreeCampaign(unittest.TestCase):
    def setUp(self):
        import fair_reference_curve as FRC
        self.fit, pool = FRC.landscape()
        self.pool = set(pool)
        self.viable = sorted(self.pool)[0]
        self.dead = [s for s in sorted(self.fit) if s not in self.pool][:40]

    def run_one(self, dead, **kw):
        pol = _Stubborn(dead, self.viable, self.dead)
        return C.run(self.fit, self.pool, pol, 0.0, 12345, 0.0, rounds=2, slots_per_round=1,
                     nomination="mean", max_reasks=3, **kw)

    def test_the_old_rule_loses_the_slot_after_three_replacements(self):
        r = self.run_one(dead=4)
        self.assertEqual(sum(1 for h in r.history if h.outcome == O.ABANDONED), 2)
        self.assertEqual(r.rejection_cap_hits, 0)
        self.assertFalse(r.riskfree_rejection)

    def test_the_risk_free_rule_never_loses_a_slot_below_the_cap(self):
        r = self.run_one(dead=C.RISKFREE_CAP, riskfree_rejection=True)
        self.assertEqual(sum(1 for h in r.history if h.outcome == O.ABANDONED), 0)
        self.assertEqual(sum(1 for h in r.history if h.outcome == O.OK), 2)
        self.assertEqual(r.rejection_cap_hits, 0)

    def test_the_cap_is_a_counted_exception(self):
        r = self.run_one(dead=C.RISKFREE_CAP + 1, riskfree_rejection=True)
        self.assertEqual(r.rejection_cap_hits, 2, "every slot that reached the cap must be counted")
        self.assertEqual(sum(1 for h in r.history if h.outcome == O.ABANDONED), 2)


class FakeCall(object):
    def __init__(self, text):
        self.text, self.model, self.provider = text, "stub/model", "Stub"
        self.prompt_tokens = self.completion_tokens = self.reasoning_tokens = 1
        self.finish_reason, self.cost_usd, self.latency_ms, self.error, self.raw = "stop", 0.0, 1, None, None
        self.ok = True


class TheHarnessSendsWhatTheOptionsSay(unittest.TestCase):
    """grid.one_campaign with a stub in place of the model: the prompts actually sent, end to end."""

    def campaign(self, **opts):
        import grid as G
        sent = []

        def fake_complete(prompt, model, **kw):
            sent.append(prompt)
            if "ANSWER:" in prompt:
                return FakeCall("ANSWER: GDIF\nREASON: stub")
            n = int(re.search(r"Choose (\d+) candidate", prompt).group(1))
            if "were just rejected" in prompt:          # a replacement ask: answer with a viable one
                return FakeCall("GDIF | stub")
            # A round: the first order is non-viable, so every round sends a replacement prompt too.
            return FakeCall("\n".join(["ADIF | stub"] + ["GDIF | stub"] * (n - 1)))
        real = LP.llm.complete
        LP.llm.complete = fake_complete
        try:
            fit, pool = G.landscape()
            ps = tuple(sorted(pool))
            row = G.one_campaign(fit, pool, ps, None, "deepseek/deepseek-chat-v3.1", "blind", 300000, [],
                                 6000, 3, prompt_options=opts)
        finally:
            LP.llm.complete = real
        return row, sent

    def test_all_three_reach_the_prompt_and_the_row(self):
        row, sent = self.campaign(goal_true_value=True, fix_replacement_budget=True,
                                  riskfree_rejection=True)
        rounds = [p for p in sent if "ANSWER:" not in p]
        replacements = [p for p in rounds if "were just rejected" in p]
        self.assertTrue(replacements, "the stub must exercise the replacement prompt")
        self.assertTrue(rounds and all(GOAL in p for p in rounds))
        self.assertTrue(all("4 orders per round" in p for p in replacements))
        self.assertTrue(all(RISKFREE in p for p in sent))
        self.assertTrue(all("4 orders per round" in p for p in sent))
        # The row records every option that shapes a prompt.
        self.assertEqual(row["prompt_options"], dict(goal_true_value=True, fix_replacement_budget=True,
                                                     riskfree_rejection=True, truthful_reask=False,
                                                     ledger=False, menu=False, repeat_cap=False, structure=False))
        self.assertIn("rejection_cap_hits", row)

    def test_the_risk_free_flag_reaches_the_campaign_rule(self):
        """The risk-free flag reaches the campaign rule as well as the prompt, from the same dict."""
        import grid as G
        dead = iter(["ADIF", "AAAA", "AAAC", "AAAD", "AAAE"] * 400)

        def stubborn(prompt, model, **kw):
            if "ANSWER:" in prompt:
                return FakeCall("ANSWER: GDIF\nREASON: stub")
            n = int(re.search(r"Choose (\d+) candidate", prompt).group(1))
            return FakeCall("\n".join("%s | stub" % next(dead) for _ in range(n)))   # never viable
        rows = {}
        for flag in (False, True):
            real = LP.llm.complete
            LP.llm.complete = stubborn
            try:
                fit, pool = G.landscape()
                rows[flag] = G.one_campaign(fit, pool, tuple(sorted(pool)), None,
                                            "deepseek/deepseek-chat-v3.1", "blind", 300000, [], 6000, 3,
                                            prompt_options=dict(riskfree_rejection=flag))
            finally:
                LP.llm.complete = real
        self.assertGreater(rows[False]["slots_abandoned"], 0, "off: dead orders must cost slots")
        self.assertEqual(rows[True]["slots_abandoned"], rows[True]["rejection_cap_hits"],
                         "on: the only slots lost are the counted cap hits")
        self.assertGreater(rows[True]["rejection_cap_hits"], 0,
                           "a policy that never proposes a viable candidate must reach the cap")

    def test_off_sends_the_grid_prompts(self):
        row, sent = self.campaign()
        self.assertFalse(any(GOAL in p or "at no cost" in p for p in sent))
        self.assertTrue(all("THE SLOT IS LOST" in p for p in sent))
        replacements = [p for p in sent if "were just rejected" in p]
        self.assertTrue(replacements and all("1 orders per round" in p for p in replacements),
                        "off, the replacement prompt must still say what the grid sent")


if __name__ == "__main__":
    unittest.main(verbosity=2)
