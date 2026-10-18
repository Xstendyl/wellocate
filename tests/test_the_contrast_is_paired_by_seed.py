"""Tests that the confirmatory contrast is paired by seed, matching on the seed value and not on row order.

At one seed the oracle draws the same noise, failures and screening in every condition, so the cells are
dependent by construction and an unpaired (Welch) standard error can be too large or too small. Pairing must
also hold when the two cells were written in different orders.
"""
import math, os, statistics as st, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import analyse_grid as AG  # noqa: E402
import repdef.rng as R  # noqa: E402

M = "test/model"


def rows(pairs, condition, model=M):
    """pairs: {seed: value} -> the row shape confirmatory() consumes."""
    return [dict(condition=condition, model=model, seed=s, nominated_true=v)
            for s, v in pairs.items()]


def anticorrelated(n=40, spread=1.0):
    """A cell pair whose within-seed correlation is strongly NEGATIVE, so paired and unpaired
    standard errors are far apart and a test can tell which one was used."""
    a, b = {}, {}
    for i in range(n):
        u = R._u64("t", 0, i) % 1000 / 1000.0 - 0.5
        a[1000 + i] = 5.0 + spread * u
        b[1000 + i] = 5.0 - spread * u          # exact mirror: correlation -1
    return a, b


class PairedBySeed(unittest.TestCase):

    def test_the_reported_se_is_the_paired_se_and_not_welch(self):
        a, b = anticorrelated()
        seeded = AG.by_seed(rows(a, "Mechanism") + rows(b, "Aggregated"))
        (row,) = AG.confirmatory(seeded, [M], [("Aggregated", "Mechanism")])
        _m, _c, n, drop, diff, se, _lo, _hi, _wp, _pt, se_welch, _pw, corr, _du = row
        ks = sorted(a)
        d = [b[k] - a[k] for k in ks]
        self.assertAlmostEqual(se, st.stdev(d) / math.sqrt(len(d)), places=12)
        self.assertAlmostEqual(corr, -1.0, places=9)
        # The two standard errors are far apart here, so the assertion above can fail.
        self.assertGreater(se / se_welch, 1.3)

    def test_it_pairs_on_the_seed_and_not_on_row_order(self):
        a, b = anticorrelated()
        forward = rows(a, "Mechanism") + rows(b, "Aggregated")
        shuffled = rows(a, "Mechanism") + list(reversed(rows(b, "Aggregated")))
        r1 = AG.confirmatory(AG.by_seed(forward), [M], [("Aggregated", "Mechanism")])
        r2 = AG.confirmatory(AG.by_seed(shuffled), [M], [("Aggregated", "Mechanism")])
        self.assertEqual(r1, r2)
        # Positional pairing on the reversed cell would give a DIFFERENT se, so this discriminates.
        ks = sorted(a)
        wrong = [list(reversed([b[k] for k in ks]))[i] - a[k] for i, k in enumerate(ks)]
        self.assertGreater(abs(st.stdev(wrong) / math.sqrt(len(ks)) - r1[0][5]), 1e-6)

    def test_the_point_estimate_is_unchanged_by_pairing(self):
        """Pairing moves the standard error and must not move the effect."""
        a, b = anticorrelated()
        seeded = AG.by_seed(rows(a, "Mechanism") + rows(b, "Aggregated"))
        (row,) = AG.confirmatory(seeded, [M], [("Aggregated", "Mechanism")])
        self.assertAlmostEqual(row[4], row[13], places=12)   # paired diff == welch diff

    def test_a_missing_seed_is_reported_and_not_silently_intersected(self):
        a, b = anticorrelated()
        b.pop(sorted(b)[0])
        seeded = AG.by_seed(rows(a, "Mechanism") + rows(b, "Aggregated"))
        (row,) = AG.confirmatory(seeded, [M], [("Aggregated", "Mechanism")])
        self.assertEqual(row[2], len(a) - 1)
        self.assertEqual(row[3], 1)

    def test_one_weight_per_seed_on_the_pair_equals_one_weight_on_the_difference(self):
        """One bootstrap weight per seed on the pair is the same draw as one weight on the centred difference.

        (1/n) sum w (r_B - r_A) == (1/n) sum w (d - mean d).
        """
        a, b = anticorrelated()
        ks = sorted(a)
        ya, yb = [a[k] for k in ks], [b[k] for k in ks]
        d = [y - x for x, y in zip(ya, yb)]
        ma, mb, md = st.mean(ya), st.mean(yb), st.mean(d)
        ra, rb, rd = ([x - ma for x in ya], [x - mb for x in yb], [x - md for x in d])
        n = len(ks)
        for rep in range(50):
            w = [1 if R._u64("id", rep, j) % 2 else -1 for j in range(n)]
            two = (st.mean([w[j] * rb[j] for j in range(n)])
                   - st.mean([w[j] * ra[j] for j in range(n)]))
            one = st.mean([w[j] * rd[j] for j in range(n)])
            self.assertAlmostEqual(two, one, places=12)

    def test_a_non_finite_p_is_refused_instead_of_entering_the_holm_family(self):
        """A non-finite p-value raises instead of entering the Holm family, where it would silently reorder the correction."""
        a = {1000 + i: 5.0 for i in range(10)}
        b = {1000 + i: 6.0 for i in range(10)}
        seeded = AG.by_seed(rows(a, "Mechanism") + rows(b, "Aggregated"))
        with self.assertRaises(AG.NonFinite):
            AG.confirmatory(seeded, [M], [("Aggregated", "Mechanism")])

    def test_the_bootstrap_imposes_the_null_and_is_reproducible(self):
        """The bootstrap imposes the null and is reproducible: a large effect gives a small p, a zero effect does not, and the same input gives the same p."""
        big = [1.0 + (0.01 if i % 2 else -0.01) for i in range(40)]
        zero = [0.5 if i % 2 else -0.5 for i in range(40)]
        self.assertLess(AG.paired_wild_p(big, reps=2000, tag="x"), 0.01)
        self.assertGreater(AG.paired_wild_p(zero, reps=2000, tag="x"), 0.5)
        self.assertEqual(AG.paired_wild_p(zero, reps=2000, tag="x"),
                         AG.paired_wild_p(zero, reps=2000, tag="x"))


if __name__ == "__main__":
    unittest.main()
