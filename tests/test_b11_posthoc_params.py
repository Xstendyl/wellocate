"""Tests that the post-hoc parameters of the PPO training script leave the registered run and test unchanged.

The test function's defaults are the registered seeds, splits and output file; a test with other seeds,
splits or checkpoint directory refuses to write results/b11_test_<run>.json; and a CONFIG override keeps
the registered type, changes only its key and refuses an unknown key.
"""
import importlib.util, inspect, os, sys, unittest

try:
    import torch  # noqa: F401
except ImportError:
    raise unittest.SkipTest("needs torch: pip install -r requirements.txt")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("ppo", os.path.join(ROOT, "wellocate", "examples", "ppo.py"))
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


class PosthocParams(unittest.TestCase):
    def test_defaults_are_registered(self):
        sig = inspect.signature(P.test).parameters
        self.assertEqual(sig["seeds"].default, (0, 1, 2))
        self.assertIsNone(sig["path"].default)
        self.assertIsNone(sig["splits"].default)
        self.assertEqual(sig["out"].default, P.OUT)

    def test_posthoc_test_cannot_write_registered_file(self):
        for kw in (dict(seeds=(3, 4)), dict(splits=["phoq:test", "nk:test"]), dict(out="/tmp/elsewhere")):
            with self.assertRaises(ValueError):
                P.test("B", **kw)

    def test_config_override(self):
        before = dict(P.CONFIG)
        try:
            P.apply_sets(["entropy_coef=0.05"])
            self.assertEqual(P.CONFIG["entropy_coef"], 0.05)
            self.assertIsInstance(P.CONFIG["entropy_coef"], float)
            self.assertEqual({k: v for k, v in P.CONFIG.items() if k != "entropy_coef"},
                             {k: v for k, v in before.items() if k != "entropy_coef"})
            with self.assertRaises(ValueError):
                P.apply_sets(["entropy=0.05"])
        finally:
            P.CONFIG.clear()
            P.CONFIG.update(before)


if __name__ == "__main__":
    unittest.main()
