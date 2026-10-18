"""Tests that a scripted policy proposes only strings in the alphabet of the landscape it searches.

`policies.neighbours` uses the amino acids, while the grid's landscape is spelled A to T. The property is
checked on real campaign histories for every policy the paper's numbers come from, and the amino-acid
policy is shown to leave the landscape, so the test exercises the difference.
"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from repdef import campaign as C, policies as P                            # noqa: E402
import fair_reference_curve as FRC                                         # noqa: E402

FIT, POOL = FRC.landscape()
PS, SPACE = tuple(sorted(POOL)), tuple(sorted(FIT))
ANCHOR = FRC.anchor_of(FIT, POOL)


def proposed(pol, seed=8_200_000):
    r = C.run(FIT, POOL, pol, 0.0, seed, 0.15, pool_sorted=PS, nomination="mean",
              noise_model="multiplicative", cv=FRC.CV, noise_floor=FRC.FLOOR)
    return {h.seq for h in r.history if h.seq != "----"}


def outside(pol, seeds=5):
    return sum(len({s for s in proposed(pol, 8_200_000 + i) if s not in FIT}) for i in range(seeds))


class EveryPolicyStaysOnItsLandscape(unittest.TestCase):

    def test_the_alphabet_is_read_from_the_landscape(self):
        self.assertEqual(P.alphabet_of(SPACE), "ABCDEFGHIJKLMNOPQRST")
        self.assertEqual(P.alphabet_of(FIT), "ABCDEFGHIJKLMNOPQRST")

    def test_the_published_policies_leave_the_landscape_and_the_corrected_ones_do_not(self):
        self.assertGreater(outside(FRC.FairGreedy(1, ANCHOR, SPACE)), 0, "the published defect should show")
        self.assertEqual(outside(FRC.FairGreedyAlphabet(1, ANCHOR, SPACE)), 0)
        self.assertEqual(outside(FRC.PoolGreedyAlphabet(1, SPACE)), 0)

    def test_the_corrected_policies_reach_letters_the_amino_acids_lack(self):
        got = set()
        for i in range(5):
            got |= {c for s in proposed(FRC.FairGreedyAlphabet(1, ANCHOR, SPACE), 8_200_000 + i) for c in s}
        self.assertTrue({"B", "J", "O"} & got)

    def test_the_lab_protocols_the_step7_curve_and_the_canary_policy(self):
        import lab_protocols as LPR, nk_reference_curve as NRC
        for fair in (True, False):
            self.assertEqual(outside(LPR.QueueProtocol(3, ANCHOR, SPACE, fair)), 0, fair)
        self.assertEqual(outside(NRC.policy(1, FIT)), 0)
        pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
        pol.alphabet = P.alphabet_of(FIT)
        self.assertEqual(outside(pol), 0)

    def test_the_default_is_unchanged(self):
        pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
        self.assertIsNone(pol.alphabet)
        self.assertEqual(pol._neighbours("GDIF"), P.neighbours("GDIF"))

    def test_the_two_corrected_fair_policies_are_one_policy(self):
        """The two copies of the alphabet-aware fair policy behave identically."""
        import yardsticks_0am as Y
        for i in range(20):
            a = C.run(FIT, POOL, FRC.FairGreedyAlphabet(1, ANCHOR, SPACE), 0.0, FRC.SEED0 + i, 0.15,
                      pool_sorted=PS, nomination="shrinkage", prior="empirical", noise_model="multiplicative",
                      cv=FRC.CV, noise_floor=FRC.FLOOR)
            b = C.run(FIT, POOL, Y.FairGreedyAlphabet(1, ANCHOR, SPACE, "ABCDEFGHIJKLMNOPQRST"), 0.0,
                      FRC.SEED0 + i, 0.15, pool_sorted=PS, nomination="shrinkage", prior="empirical",
                      noise_model="multiplicative", cv=FRC.CV, noise_floor=FRC.FLOOR)
            self.assertEqual([(h.seq, h.outcome) for h in a.history], [(h.seq, h.outcome) for h in b.history])
            self.assertEqual(a.nominated_true, b.nominated_true)


if __name__ == "__main__":
    unittest.main()
