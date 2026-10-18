"""Tests that a run manifest records whether its commit describes the code that ran.

A dirty code tree, including an untracked or renamed code file, means the commit does not describe the code.
`_git` is replaced by a stub, so the results do not depend on the state of the checkout.
"""
import io, json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import grid  # noqa: E402

CLEAN = ""
DIRTY_CODE = " M repdef/prompts.py\n M scripts/grid.py\n"
DIRTY_SPEC = " M spec/GRID_PREREGISTRATION.md\n?? results/grid_x_campaigns.jsonl\n"
UNTRACKED_CODE = "?? scripts/brand_new_module.py\n"
RENAME_INTO_CODE = 'R  old/thing.py -> scripts/thing.py\n'


class FakeGit:
    """Stands in for `_git`, so the test does not depend on the checkout being clean or dirty."""

    def __init__(self, porcelain, diff="--- a/x\n+++ b/x\n+changed\n", head="a" * 40):
        self.porcelain, self.diff, self.head = porcelain, diff, head

    def __call__(self, *args):
        if args[:2] == ("status", "--porcelain"):
            return self.porcelain
        if args[0] == "diff":
            return self.diff
        if args[:2] == ("rev-parse", "HEAD"):
            return self.head + "\n"
        return ""


class ManifestProvenance(unittest.TestCase):

    def setUp(self):
        self._real = grid._git
        self.addCleanup(lambda: setattr(grid, "_git", self._real))

    def prov(self, porcelain, **kw):
        grid._git = FakeGit(porcelain, **kw)
        return grid.code_provenance()

    def test_a_clean_tree_says_the_commit_describes_the_code(self):
        p = self.prov(CLEAN, diff="")
        self.assertTrue(p["git_commit_describes_the_code"])
        self.assertFalse(p["code_dirty"])
        self.assertEqual(p["code_dirty_paths"], [])

    def test_a_dirty_code_tree_says_the_commit_does_not(self):
        p = self.prov(DIRTY_CODE)
        self.assertFalse(p["git_commit_describes_the_code"])
        self.assertTrue(p["code_dirty"])
        self.assertEqual(len(p["code_dirty_paths"]), 2)
        self.assertIsNotNone(p["code_diff_sha256"])

    def test_a_change_only_under_spec_or_results_does_not_block_a_launch(self):
        """A change only under spec/ or results/ leaves the code clean and does not block a launch."""
        p = self.prov(DIRTY_SPEC, diff="")
        self.assertTrue(p["git_commit_describes_the_code"])
        self.assertFalse(p["code_dirty"])
        # The full git status is still recorded.
        self.assertEqual(len(p["git_status_porcelain"]), 2)

    def test_an_untracked_code_file_counts_as_dirty(self):
        """An untracked code file counts as dirty even though `git diff` cannot see it."""
        p = self.prov(UNTRACKED_CODE, diff="")
        self.assertTrue(p["code_dirty"])
        self.assertFalse(p["git_commit_describes_the_code"])

    def test_a_rename_into_a_code_directory_counts_as_dirty(self):
        p = self.prov(RENAME_INTO_CODE, diff="")
        self.assertTrue(p["code_dirty"])

    def test_it_refuses_by_default_and_records_when_told_to_proceed(self):
        grid._git = FakeGit(DIRTY_CODE)
        p = grid.code_provenance()
        with self.assertRaises(SystemExit):
            grid.refuse_if_the_code_is_uncommitted(p, False, "unittest_tag")
        dst = os.path.join(grid.RESULTS, "grid_unittest_tag_uncommitted.diff")
        self.addCleanup(lambda: os.path.exists(dst) and os.remove(dst))
        grid.refuse_if_the_code_is_uncommitted(p, True, "unittest_tag")   # must NOT raise
        self.assertTrue(os.path.exists(dst))
        self.assertIn("+changed", io.open(dst, encoding="utf-8").read())

    def test_the_saved_record_includes_an_untracked_file_that_no_diff_can_show(self):
        """The saved record includes the contents of an untracked file, which no diff can show."""
        rel = "scripts/_provenance_test_untracked.py"
        abs_ = os.path.join(ROOT, rel)
        with io.open(abs_, "w", encoding="utf-8") as f:
            f.write("MARKER_ONLY_IN_THE_UNTRACKED_FILE = 42\n")
        self.addCleanup(lambda: os.path.exists(abs_) and os.remove(abs_))
        grid._git = FakeGit("?? %s\n" % rel, diff="")
        p = grid.code_provenance()
        self.assertTrue(p["code_dirty"])
        dst = os.path.join(grid.RESULTS, "grid_unittest_untracked_uncommitted.diff")
        self.addCleanup(lambda: os.path.exists(dst) and os.remove(dst))
        grid.refuse_if_the_code_is_uncommitted(p, True, "unittest_untracked")
        saved = io.open(dst, encoding="utf-8").read()
        self.assertIn("MARKER_ONLY_IN_THE_UNTRACKED_FILE", saved)
        self.assertIn(rel, saved)

    def test_the_provenance_fields_cannot_be_shadowed_by_the_manifest(self):
        """`manifest.update(prov)` comes last in grid.main, so no earlier key can overwrite a provenance field."""
        src = io.open(os.path.join(ROOT, "scripts", "grid.py"), encoding="utf-8").read()
        # Slice forward from the manifest, because `os.makedirs(RESULTS` also appears earlier in the file.
        i = src.index("    manifest = dict(")
        body = src[i:src.index("    os.makedirs(RESULTS", i)]
        self.assertGreater(len(body), 500)        # the slice must actually contain the block
        self.assertIn("manifest.update(prov)", body)
        self.assertNotIn("git_commit=", body)     # the raw field is gone; provenance owns it now


if __name__ == "__main__":
    unittest.main()
