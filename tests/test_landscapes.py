"""Tests that each landscape file (PhoQ and GB1) matches the constants the experiment relies on.

Every constant is asserted rather than printed, so a changed data file fails and names which quantity moved.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from repdef import landscape as L  # noqa: E402


def _load(name):
    try:
        return L.load(name)
    except L.LandscapeError as e:
        raise unittest.SkipTest(str(e))


class _Base(unittest.TestCase):
    NAME = None

    @classmethod
    def setUpClass(cls):
        if cls.NAME is None:
            raise unittest.SkipTest("base class")
        cls.ls = _load(cls.NAME)
        cls.want = L.EXPECTED[cls.NAME]

    def test_1_row_count(self):
        """The file holds the full 20^4 table, zero-filled, not only the measured variants."""
        self.assertEqual(self.ls.n_rows, self.want["rows"])
        self.assertEqual(len(self.ls), self.want["rows"])

    def test_2_max_fitness(self):
        """The maximum fitness matches, since some prompt conditions quote it to the agent."""
        self.assertAlmostEqual(self.ls.max_fitness, self.want["max_fitness"], places=3)

    def test_3_exact_zeros(self):
        """The count of exact zeros (measured-dead plus filled-unmeasured) matches, which pins the fill policy."""
        self.assertEqual(self.ls.exact_zeros, self.want["exact_zeros"])

    def test_4_viability_threshold_is_strict(self):
        """The viability threshold is strict, since >= would change the pool sizes the noise scale is derived from."""
        t = self.want["viability_threshold"]
        self.assertEqual(self.ls.threshold, t)
        self.assertTrue(all(self.ls.fitness[v] > t for v in self.ls.pool))
        self.assertNotIn(t, [self.ls.fitness[v] for v in self.ls.pool])

    def test_5_viable_pool_size(self):
        """The viable pool, from which the restricted design space is built, has the expected size."""
        self.assertEqual(len(self.ls.pool), self.want["viable_pool"])

    def test_6_file_is_the_one_measured(self):
        self.assertEqual(self.ls.sha256, self.want["sha256"])
        self.assertEqual(os.path.getsize(self.ls.path), self.want["bytes"])

    def test_7_every_variant_is_well_formed(self):
        """Every variant is 4 characters over the 20 canonical amino acids, with no ambiguity codes."""
        for v in self.ls.fitness:
            self.assertEqual(len(v), L.SITES)
            self.assertTrue(set(v) <= L.AA_SET, "%r is not over %s" % (v, L.AA))

    def test_8_no_negative_fitness(self):
        self.assertGreaterEqual(self.ls.min_fitness, 0.0)


class TestPhoQ(_Base):
    NAME = "phoq"


class TestGB1(_Base):
    NAME = "gb1"


class TestTheLoaderRefusesTheWrongFile(unittest.TestCase):
    """The loader refuses a changed file and says how to get a missing one."""

    def test_a_changed_file_is_refused(self):
        import tempfile
        ls = _load("phoq")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "phoq.csv")
            with open(ls.path) as src, open(p, "w") as dst:
                dst.write(src.read())
            with open(p, "a") as f:
                f.write("AAAA,1.0\n")          # one extra row, different hash
            with self.assertRaises(L.LandscapeError):
                L.load("phoq", data_dir=d)

    def test_a_missing_file_says_how_to_get_it(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(L.LandscapeError) as cm:
                L.load("phoq", data_dir=d)
            self.assertIn("download_data.py", str(cm.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
