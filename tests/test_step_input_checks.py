"""step() refuses malformed candidates and reset() refuses negative episode indices."""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from wellocate import Wellocate  # noqa: E402


class StepInputChecks(unittest.TestCase):
    def test_malformed_candidates_raise(self):
        for bad in (["AAA"], ["ZZZZ"], [1234], ["ghrm"], [None]):
            env = Wellocate("nk", "nk:test", seed=0)
            with self.assertRaises(ValueError, msg=repr(bad)):
                env.step(bad)

    def test_well_formed_candidates_are_accepted(self):
        env = Wellocate("nk", "nk:test", seed=0)
        obs, _r, done, _i = env.step([env.observation.anchor] * env.observation.n_slots)
        self.assertFalse(done)
        self.assertEqual(obs.slots_used, 4)

    def test_negative_seed_raises(self):
        with self.assertRaises(ValueError):
            Wellocate("nk", "nk:test", seed=-1)


if __name__ == "__main__":
    unittest.main()
