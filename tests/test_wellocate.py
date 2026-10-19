"""Tests that Wellocate wraps the paper's harness without changing it.

Scripted policies give the same campaigns through the step API as through repdef.campaign.run, the paper's
reference values reproduce exactly on its 1,500 seeds, text mode sends and reads the same bytes as LLMPolicy,
the splits manifest is frozen and disjoint, and an observation carries no true value.
"""
import hashlib, json, os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEEDS_DATA = unittest.skipUnless(
    all(os.path.exists(os.path.join(ROOT, "data", f)) for f in ("gb1.csv", "phoq.csv")),
    "needs the protein data: python3 scripts/download_data.py")
sys.path.insert(0, ROOT)
import wellocate as W                                        # noqa: E402
from wellocate import baselines as B, scorecard as S, splits as SP, landscapes as LS   # noqa: E402
from repdef import campaign as C, llm, llm_policy as LP, rng as R                     # noqa: E402

REF = json.load(open(os.path.join(ROOT, "results", "references_0an7.json")))


def harness_run(factory, env, seed, nomination="shrinkage", policy=None, riskfree=False, cv=0.073):
    pol = policy or factory(env)
    return C.run(env.fit, env.pool, pol, 0.0, seed, 0.15, pool_sorted=env.ps, nomination=nomination,
                 prior="empirical", noise_model="multiplicative", cv=cv, noise_floor=W.NOISE_FLOOR,
                 rng_key=env.rng_key, riskfree_rejection=riskfree)


def env_run(factory, instance, seed, riskfree=False, cv=0.073):
    env = W.Wellocate(instance, seed=seed, riskfree_rejection=riskfree, noise_cv=cv)
    pol = factory(env.env)
    obs = env.observation
    while obs.phase in ("round", "replacement"):
        obs, _r, _d, _i = env.step(pol.propose(obs.view, obs.n_slots, obs.exclude, obs.phase))
    nom = W.shrinkage_nominee(obs.view, cv)
    _o, reward, done, info = env.nominate(nom)
    return env, reward, info


@NEEDS_DATA
class SameAsTheHarness(unittest.TestCase):

    def test_scripted_policies_match_campaign_run(self):
        pols = [B.guessing(1), B.informed(1), B.random(), B.model_guided(1, True), B.confirmation(8)]
        for inst in ("nk/K1/seed1", "gb1/scramble:20261003"):
            env0 = LS.instance(inst)
            for f in pols:
                for seed in range(8_200_000, 8_200_012):
                    r = harness_run(f, env0, seed)
                    env, reward, info = env_run(f, inst, seed)
                    sc = info["scorecard"]
                    self.assertEqual(tuple(env._orc.history), r.history, (inst, seed))
                    self.assertEqual(info["nominee"], r.nominated)
                    self.assertEqual(reward, r.nominated_true)
                    self.assertEqual(sc["replication_count"], r.replication_count)
                    self.assertEqual(sc["slots_used"], r.slots_used)
                    self.assertEqual(sc["distinct"], r.n_distinct)
                    self.assertEqual(sc["shrinkage_nominee"], r.ref_shrinkage)
                    self.assertAlmostEqual(sc["selection_shortfall"], r.selection_shortfall, places=12)

    def test_riskfree_rule_and_other_noise_match_campaign_run(self):
        for inst in ("nk/K1/seed1", "gb1/scramble:20261003"):
            env0 = LS.instance(inst)
            for f in (B.guessing(0), B.guessing(1)):
                for riskfree, cv in ((True, 0.073), (False, 0.3), (True, 0.6)):
                    for seed in range(8_200_000, 8_200_008):
                        r = harness_run(f, env0, seed, riskfree=riskfree, cv=cv)
                        env, reward, info = env_run(f, inst, seed, riskfree=riskfree, cv=cv)
                        self.assertEqual(tuple(env._orc.history), r.history, (inst, seed, riskfree, cv))
                        self.assertEqual(reward, r.nominated_true)
                        self.assertEqual(info["scorecard"]["rejection_cap_hits"], r.rejection_cap_hits)

    def test_the_paper_references_reproduce_exactly(self):
        g = REF["grid"]["guessing"]["at_kstar"]
        i = REF["grid"]["informed"]["at_kstar"]
        self.assertEqual(REF["grid"]["guessing"]["kstar"], 1)
        self.assertEqual(REF["grid"]["informed"]["kstar"], 1)
        rows = S.run(B.guessing(1), "nk:paper")
        inf = S.run(B.informed(1), "nk:paper")
        self.assertEqual(sum(r is None for r in rows + inf), 0)
        pick = sum(r["pick"] for r in rows) / len(rows)
        share = sum(r["share_budget"] for r in rows) / len(rows)
        ipick = sum(r["pick"] for r in inf) / len(inf)
        self.assertEqual(len(rows), 1500)
        self.assertAlmostEqual(pick, g["pick"], places=12)
        self.assertAlmostEqual(share, g["share_budget"], places=10)
        self.assertAlmostEqual(ipick, i["pick"], places=12)
        self.assertEqual(("%.4f" % pick, "%.2f" % share, "%.4f" % ipick), ("7.8659", "23.78", "7.9993"))


def fake_model(prompt):
    """A deterministic stand-in for a model: mostly well-formed, sometimes short, sometimes garbage."""
    h = R._u64("fake_model", hashlib.sha256(prompt.encode()).hexdigest())
    alphabet = re.search(r"\(([A-Z]{20})\)", prompt).group(1)
    if "ANSWER: XXXX" in prompt:
        seen = re.findall(r"^\s+\d+\s+([A-Z]{4})\s+-?\d", prompt, re.M)
        return "ANSWER: %s\nREASON: highest" % (seen[h % len(seen)] if seen and h % 7 else "QQQQQ")
    n = int(re.findall(r"Reply with exactly (\d+) line", prompt)[-1])
    anchor = re.search(r'The reference point is "([A-Z]{4})"', prompt).group(1)
    if h % 11 == 0:
        return "I am not sure what to do."
    if h % 13 == 0:
        n = max(1, n - 1)
    lines = []
    for j in range(n):
        x = R._u64("fake_pick", h % 1000003, j)
        s = list(anchor)
        if x % 3:
            s[x % 4] = alphabet[(x // 7) % 20]
        lines.append("%s | reason %d" % ("".join(s), j))
    return "\n".join(lines)


@NEEDS_DATA
class TextMode(unittest.TestCase):

    def test_act_text_plays_like_llmpolicy(self):
        real = llm.complete
        wire = []

        def complete(prompt, model, **kw):
            wire.append(prompt)
            return llm.Call(text=fake_model(prompt), model=model)
        llm.complete = complete
        try:
            for inst in ("nk/K1/seed1", "gb1/scramble:20261003"):
                for seed in range(8_200_000, 8_200_006):
                    env = W.Wellocate(inst, seed=seed)
                    e = env.env
                    pol = LP.LLMPolicy("fake", "blind", 0.0, parent=e.anchor, fail_pct=15, landscape=e.prompt_landscape,
                                       noise_model="multiplicative", cv=0.073, noise_floor=W.NOISE_FLOOR,
                                       anchor_reading="%.2f" % e.reading, example=e.example)
                    del wire[:]
                    r = harness_run(None, e, seed, nomination="agent", policy=pol)
                    # Every prompt actually sent, re-asks included (LLMPolicy's own log can hold one re-ask more than was sent).
                    sent, done, info = [], False, None
                    while not done:
                        p = env.prompt()
                        sent.append(p)
                        _o, _rw, done, info = env.act_text(fake_model(p))
                    self.assertEqual(tuple(env._orc.history), r.history, (inst, seed))
                    self.assertEqual(info["nominee"], r.nominated)
                    self.assertEqual(sent, wire)
                    self.assertTrue(any("Your previous reply" in x for x in sent) or seed != 8_200_000)
        finally:
            llm.complete = real


@NEEDS_DATA
class Splits(unittest.TestCase):

    def test_manifest_is_frozen_and_disjoint(self):
        doc = SP.load()
        self.assertEqual(SP.check_disjoint(doc), [])
        self.assertEqual(SP.verify(only_first=True), [])
        for fam in LS.FAMILY_TRACK:
            self.assertIn("%s:test" % fam, doc["splits"])


class NoTruthInTheObservation(unittest.TestCase):

    def test_observation_floats_are_readings(self):
        env = W.Wellocate("nk/K1/seed1", seed=8_200_000)
        pol = B.guessing(1)(env.env)
        obs = env.observation
        while obs.phase in ("round", "replacement"):
            obs, _r, _d, _i = env.step(pol.propose(obs.view, obs.n_slots, obs.exclude, obs.phase))
        truths = {env.fit[h.seq] for h in obs.history if h.outcome == "ok"}
        floats = {v for v in (h.observed for h in obs.history) if v is not None}
        floats |= {v for v in vars(obs).values() if isinstance(v, float)} if hasattr(obs, "__dict__") else set()
        self.assertFalse(truths & floats)


if __name__ == "__main__":
    unittest.main()
