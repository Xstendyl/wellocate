"""Tests for the Wellocate stress options: batch effects, a larger noise floor and outliers.

With every option off, Wellocate builds the paper's oracle and reproduces the registered test rows exactly.
When on, each option changes only the readings it names, and invalid settings are refused.
"""
import json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import oracle as O                                               # noqa: E402
from wellocate import baselines as B                                         # noqa: E402
from wellocate import env as W                                               # noqa: E402
from wellocate import landscapes as LS                                       # noqa: E402
from wellocate import scorecard as SC                                        # noqa: E402
from wellocate import splits as SP                                           # noqa: E402
from wellocate import stress as ST                                           # noqa: E402

GRID = LS.instance("nk/K1/seed300000")


def pair(seed=4242, **stress):
    """The paper's oracle and a stressed one on the same landscape and campaign seed."""
    kw = dict(noise_model="multiplicative", cv=0.073, noise_floor=W.NOISE_FLOOR, rng_key=GRID.rng_key)
    return (O.Oracle(GRID.fit, GRID.pool, 0.0, seed, 0.15, **kw),
            ST.StressOracle(GRID.fit, GRID.pool, 0.0, seed, 0.15, **dict(kw, **stress)))


def orders(n_rounds=6, per_round=8):
    seqs = sorted(GRID.pool)[:40]
    return [(r, seqs[(r * per_round + i) % len(seqs)]) for r in range(n_rounds) for i in range(per_round)]


class DefaultsAreThePapers(unittest.TestCase):
    def test_default_builds_the_paper_oracle(self):
        env = W.Wellocate(GRID, seed=7)
        self.assertIs(type(env._orc), O.Oracle)
        self.assertEqual(env.noise_floor, W.NOISE_FLOOR)

    def test_registered_rows_reproduce(self):
        reg = json.load(open(os.path.join(ROOT, "results", "b11_test_A.json")))["splits"]["nk:test"]
        k = reg["validation_k"]["guessing"]
        want = {(r["instance"], r["campaign_seed"]): r for r in reg["per_episode"]["guessing"] if r}
        eps = sorted(SP.episodes("nk:test"), key=lambda e: e[0])[:12]
        for inst, cs in eps:
            sc = SC.run_episode(B.guessing(k), LS.instance(inst), cs)
            w = want[(inst, cs)]
            self.assertAlmostEqual(sc["pick"], w["pick"], places=12)
            self.assertAlmostEqual(sc["share_budget"], w["share"], places=12)

    def test_zero_options_equal_default(self):
        for cs in (11, 12, 13):
            a = SC.run_episode(B.informed(1), GRID, cs)
            b = SC.run_episode(B.informed(1), GRID, cs, batch_sd=0.0, outlier_rate=0.0)
            self.assertEqual(a, b)


class StressDoesWhatItSays(unittest.TestCase):
    def test_outcomes_unchanged_readings_changed(self):
        base, st = pair(batch_sd=0.1)
        for r, s in orders():
            a, b = base.measure(s, r), st.measure(s, r)
            self.assertEqual((a.outcome, a.true, a.replicate_index), (b.outcome, b.true, b.replicate_index))
            if a.outcome == O.OK:
                self.assertNotEqual(a.observed, b.observed)

    def test_batch_factor_shared_within_round(self):
        base, st = pair(batch_sd=0.1)
        ratio = {}
        for r, s in orders():
            a, b = base.measure(s, r), st.measure(s, r)
            if a.outcome == O.OK:
                ratio.setdefault(r, []).append(b.observed / a.observed)
        for r, v in ratio.items():
            self.assertTrue(all(abs(x - v[0]) < 1e-12 for x in v), "round %d" % r)
            self.assertAlmostEqual(v[0], st.batch_factor(r), places=12)
        self.assertGreater(len({round(v[0], 12) for v in ratio.values()}), len(ratio) - 1)

    def test_outlier_rate_and_kinds(self):
        for kind in ST.OUTLIER_KINDS:
            base, st = pair(seed=99, outlier_rate=0.02, outlier_kind=kind)
            n_ok = n_out = 0
            for i in range(6000):
                s = sorted(GRID.pool)[i % 300]
                a, b = base.measure(s, i // 8), st.measure(s, i // 8)
                if a.outcome != O.OK:
                    continue
                n_ok += 1
                if b.observed != a.observed:
                    n_out += 1
                    if kind == "zero":
                        self.assertLess(b.observed, 6 * W.NOISE_FLOOR)
                    else:
                        self.assertAlmostEqual(b.observed, 3 * a.observed, places=12)
            rate = n_out / n_ok
            self.assertLess(abs(rate - 0.02), 4 * (0.02 * 0.98 / n_ok) ** 0.5, kind)
            self.assertEqual(st.outliers, n_out)

    def test_floor_reaches_oracle_and_nominee(self):
        env = W.Wellocate(GRID, seed=7, noise_floor=0.17524)
        self.assertEqual(env._orc.noise_floor, 0.17524)
        self.assertIs(type(env._orc), O.Oracle)
        sc = SC.run_episode(B.informed(1), GRID, 7, noise_floor=0.17524)
        self.assertIsNotNone(sc)

    def test_refuses_bad_settings(self):
        for bad in (dict(batch_sd=-0.1), dict(outlier_rate=1.5), dict(outlier_rate=0.02)):
            with self.assertRaises(ValueError):
                W.Wellocate(GRID, seed=1, **bad)


if __name__ == "__main__":
    unittest.main()
