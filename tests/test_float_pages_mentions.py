"""Tests that a figure cited only by panel ("Figure 5a") counts as a mention in the layout check in scripts/float_pages.py."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import float_pages as FP                                             # noqa: E402


class Mentions(unittest.TestCase):

    def test_plain_and_panel_references_count(self):
        for text in ("as Figure 5 shows", "in Figure 5a", "(Figure 5b, 5c)", "see Figure 5.", "Figure 5d)"):
            self.assertTrue(FP.mentions("Figure", 5, text), text)

    def test_other_numbers_and_the_caption_do_not(self):
        for text in ("Figure 50 shows", "Figure 5: Where each model", "Figure 15a"):
            self.assertFalse(FP.mentions("Figure", 5, text), text)


if __name__ == "__main__":
    unittest.main()
