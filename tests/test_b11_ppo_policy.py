"""Tests for the example PPO policy: it acts only through the public observation, can order any candidate, and trains reproducibly.

The policy plays whole episodes with the view removed, its vectorised candidate set matches a plain loop
written from the definition, the last candidate is the random action, a cached landscape gives the split's
episode, and two one-update training runs with the same seed give identical weights.
"""
import collections, dataclasses, importlib.util, os, sys, tempfile, unittest

try:
    import numpy as np
    import torch
except ImportError:
    raise unittest.SkipTest("needs numpy and torch: pip install -r requirements.txt")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from wellocate import baselines as B                                         # noqa: E402
from wellocate import env as W                                               # noqa: E402
from wellocate import landscapes as LS                                       # noqa: E402
from wellocate import splits as SP                                           # noqa: E402

spec = importlib.util.spec_from_file_location("ppo", os.path.join(ROOT, "wellocate", "examples", "ppo.py"))
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


def states(family, split, index, every=7):
    """Public observations along one scripted episode (guessing at k = 1)."""
    e = W.Wellocate(family, split=split, seed=index)
    pol = B.guessing(1)(e.env)
    out, o, n = [], e.observation, 0
    while o.phase in ("round", "replacement"):
        if n % every == 0:
            out.append(P.public(o))
        o, _r, _d, _i = e.step(pol.propose(o.view, o.n_slots, o.exclude, o.phase))
        n += 1
    out.append(P.public(o))
    return out


def reference_set(st, exclude, chosen):
    """The candidate set from its definition, one candidate at a time."""
    seqs, rows = [], []
    blocked = set(exclude) | set(chosen) | st.rejected
    for s in sorted(st.ordered - blocked):
        seqs.append(s)
        rows.append(st.measured_row(s))
    parents = [st.anchor] + [p for p in st.parents if p != st.anchor]
    seen = set(seqs)
    bestz = st.z(st.means[st.best]) if st.best else 0.0
    for par in parents:
        pm = st.means.get(par, st.a)
        prow = [st.z(pm) / 10.0, st.rank.get(par, 0.5), len(st.reads.get(par, [])) / 4.0, float(par == st.best),
                float(par == st.anchor), st.logratio(pm)]
        if par not in st.ordered and par not in blocked and par not in seen:
            row = np.zeros(P.C_DIM)
            row[1] = row[3] = 1.0
            row[12:18] = prow
            seqs.append(par)
            rows.append(row)
            seen.add(par)
        muts = [(p, c, par[:p] + c + par[p + 1:]) for p in range(4) for c in st.alpha if c != par[p]]
        nb_rej = collections.Counter(p for p, _c, s in muts if s in st.rejected)
        nb_ord = sum(1 for _p, _c, s in muts if s in st.ordered)
        for p, c, s in muts:
            if s in st.ordered or s in blocked or s in seen:
                continue
            li = st.idx[c]
            row = np.zeros(P.C_DIM)
            row[1] = 1.0
            row[3] = float(s == st.anchor)
            row[8] = (bestz - st.z(pm)) / 10.0
            row[12:18] = prow
            row[18], row[19] = st.pl_n[p, li] / 10.0, st.pl_z[p, li] / 10.0
            row[20], row[21] = float(st.pl_n[p, li] > 0), st.pl_rej[p, li] / 10.0
            row[22], row[23] = nb_rej[p] / 5.0, nb_ord / 10.0
            row[24] = sum(x != y for x, y in zip(s, st.anchor)) / 4.0
            row[25] = sum(x != y for x, y in zip(s, st.best)) / 4.0 if st.best else 0.0
            seqs.append(s)
            rows.append(row)
            seen.add(s)
    row = np.zeros(P.C_DIM)
    row[2] = 1.0
    return seqs + [None], np.asarray(rows + [row], dtype=np.float32)


class B11Policy(unittest.TestCase):

    def test_plays_on_the_public_observation_only(self):
        e = W.Wellocate("gb1", split="gb1:train", seed=3)
        seen = []
        net = P.Net()
        pol = P.Policy(net)
        orig = pol.choose

        def spy(obs, rng, record):
            seen.append(obs)
            return orig(obs, rng, record)
        pol.choose = spy
        info = P.play(e, pol, np.random.default_rng(0))
        self.assertTrue(seen and all(o.view is None for o in seen))
        for o in seen:
            for f in dataclasses.fields(o):
                v = getattr(o, f.name)
                self.assertIsInstance(v, (str, int, tuple, frozenset, type(None)), f.name)
            for r in o.history:
                self.assertEqual(r._fields, ("round", "seq", "outcome", "observed"))
        self.assertIn("pick", info["scorecard"])

    def test_vectorised_candidate_set_matches_its_definition(self):
        n = 0
        for family, split in (("nk", "nk:train"), ("gb1", "gb1:train")):
            for obs in states(family, split, 5):
                st = P.State(obs)
                ref0, _r = reference_set(st, obs.exclude, [])
                fresh = [s for s in ref0 if s is not None and s not in st.ordered][3:5]
                for ch in ([], sorted(st.means)[:1], fresh):   # nothing, a re-test, and two new candidates chosen
                    got_s, got_r = P.candidate_set(st, obs.exclude, ch)
                    ref_s, ref_r = reference_set(st, obs.exclude, ch)
                    self.assertEqual(got_s, ref_s)
                    np.testing.assert_allclose(got_r, ref_r, atol=1e-6)
                    n += 1
        self.assertGreater(n, 20)

    def test_random_action_reaches_unordered_candidates(self):
        obs = states("nk", "nk:train", 2)[-2]
        st = P.State(obs)
        seqs, _rows = P.candidate_set(st, obs.exclude, [])
        self.assertIsNone(seqs[-1])
        rng = np.random.default_rng(1)
        drawn = {P.random_candidate(st, rng, st.ordered) for _ in range(200)}
        self.assertFalse(drawn & st.ordered)
        self.assertGreater(len(drawn), 150)

    def test_a_cached_landscape_gives_the_splits_episode(self):
        for family, split in (("nk", "nk:train"), ("phoq", "phoq:test")):
            inst, cs = SP.episodes(split, 4)[3]
            a = W.Wellocate(family, split=split, seed=3)
            b = W.Wellocate(LS.instance(inst), seed=cs)
            for e in (a, b):
                pol = B.guessing(1)(e.env)
                o = e.observation
                while o.phase in ("round", "replacement"):
                    o, _r, _d, _i = e.step(pol.propose(o.view, o.n_slots, o.exclude, o.phase))
                e.nominate(o.view.best_by_mean())
            self.assertEqual(a._info["scorecard"], b._info["scorecard"])
            self.assertEqual(a.campaign_seed, b.campaign_seed)

    def test_training_is_reproducible(self):
        saved = dict(P.CONFIG)
        P.CONFIG.update(episodes_per_update=4, instances_per_update=2, val_episodes_per_family=2, validate_every=1)
        try:
            weights = []
            for _ in range(2):
                with tempfile.TemporaryDirectory() as d:
                    s = P.train("B", 0, updates=1, out=d)
                    weights.append(torch.load(s["best_path"]))
                    self.assertEqual(s["episodes"], 4)
            for k in weights[0]:
                self.assertTrue(torch.equal(weights[0][k], weights[1][k]), k)
        finally:
            P.CONFIG.clear()
            P.CONFIG.update(saved)


if __name__ == "__main__":
    unittest.main()
