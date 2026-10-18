"""Tests that rerunning a tag does not erase the calls that tag already archived.

A rerun replaces campaigns, not cells or runs: rows for campaigns the new log does not mention are carried
forward, rows for campaigns it does mention are replaced rather than duplicated, untouched cells stay in place
and in the manifest, and the plain log is deleted only when every expected line is accounted for.
"""
import glob, gzip, json, os, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import grid  # noqa: E402


def row(rung, seed, model, kind="round", i=0):
    return json.dumps(dict(rung=rung, campaign_seed=seed, model=model, kind=kind, i=i,
                           prompt="p%d" % i, raw_response="r%d" % i)) + "\n"


class ReRunArchive(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_results = grid.RESULTS
        grid.RESULTS = self.tmp

    def tearDown(self):
        grid.RESULTS = self.old_results
        shutil.rmtree(self.tmp, ignore_errors=True)

    def archive(self, tag, lines):
        lp = os.path.join(self.tmp, "grid_%s_calls.jsonl" % tag)
        with open(lp, "w") as f:
            f.writelines(lines)
        grid.archive_calls(tag, os.path.join(self.tmp, "grid_%s_campaigns.jsonl" % tag), lp)
        return lp

    def read_archive(self, tag):
        out = {}
        for g in sorted(glob.glob(os.path.join(self.tmp, "grid_%s_calls" % tag, "*.jsonl.gz"))):
            with gzip.open(g, "rt") as f:
                out[os.path.basename(g)] = [json.loads(l) for l in f if l.strip()]
        return out

    def test_the_first_archive_is_unchanged_in_behaviour(self):
        lp = self.archive("t1", [row("blind", 1, "a/m"), row("blind", 2, "a/m"), row("instructed", 1, "b/m")])
        self.assertFalse(os.path.exists(lp), "plain log should be removed after verification")
        arc = self.read_archive("t1")
        self.assertEqual(sorted(arc), ["blind__a_m.jsonl.gz", "instructed__b_m.jsonl.gz"])
        self.assertEqual(len(arc["blind__a_m.jsonl.gz"]), 2)

    def test_a_rerun_carries_forward_the_campaigns_it_does_not_mention(self):
        self.archive("t2", [row("blind", 1, "a/m", i=1), row("blind", 2, "a/m", i=2),
                            row("blind", 3, "a/m", i=3)])
        self.archive("t2", [row("blind", 2, "a/m", i=99)])
        seeds = [(d["campaign_seed"], d["i"]) for d in self.read_archive("t2")["blind__a_m.jsonl.gz"]]
        self.assertEqual(sorted(seeds), [(1, 1), (2, 99), (3, 3)],
                         "seed 2 replaced, seeds 1 and 3 carried forward, nothing duplicated")

    def test_a_rerun_leaves_untouched_cells_alone_and_still_lists_them(self):
        self.archive("t3", [row("blind", 1, "a/m"), row("instructed", 1, "b/m"),
                            row("instructed", 2, "b/m")])
        before = open(os.path.join(self.tmp, "grid_t3_calls", "instructed__b_m.jsonl.gz"), "rb").read()
        self.archive("t3", [row("blind", 1, "a/m", i=7)])
        after = open(os.path.join(self.tmp, "grid_t3_calls", "instructed__b_m.jsonl.gz"), "rb").read()
        self.assertEqual(before, after, "an untouched cell must not be rewritten")
        man = json.load(open(os.path.join(self.tmp, "grid_t3_calls", "MANIFEST.json")))
        self.assertIn("instructed__b_m.jsonl.gz", man["files"],
                      "an untouched cell must still appear in the manifest")
        self.assertEqual(man["untouched_cell_lines"], 2)
        self.assertEqual(man["total_lines"], 3)

    def test_the_plain_log_survives_when_the_count_does_not_add_up(self):
        self.archive("t4", [row("blind", 1, "a/m"), row("blind", 2, "a/m")])
        # Verification is made to fail without touching the data, so the only thing under test is
        # whether a failed check still deletes the operator's only plain copy.
        real = gzip.open

        def lying_open(path, mode="rb", *a, **k):
            if "r" in mode and str(path).endswith(".gz"):
                import io
                return io.StringIO("")
            return real(path, mode, *a, **k)
        gzip.open = lying_open
        try:
            lp = self.archive("t4", [row("blind", 3, "a/m")])
        finally:
            gzip.open = real
        self.assertTrue(os.path.exists(lp), "a failed verification must keep the plain log")

    def test_the_merge_is_what_makes_the_carry_forward_happen(self):
        """Removing the merge makes the replace-not-duplicate property fail."""
        src = open(os.path.join(ROOT, "scripts", "grid.py")).read()
        self.assertIn("carried += len(keep)", src)
        self.assertIn("cells_out[(rung, model)] = keep + lines", src)
        self.assertIn("expected = len(rows) + carried + untouched", src)
        self.assertNotIn("total == len(rows):", src.split("def archive_calls")[1].split("\ndef ")[0])


if __name__ == "__main__":
    unittest.main()


class TwoCellsOnOneRungAreNotOneCampaign(unittest.TestCase):
    """The campaign key includes the cell, so cells sharing a rung and a seed range are not merged into one campaign.

    `cell` is stamped on every call row and falls back to `rung`, so archives written before the field existed
    merge as before.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = grid.RESULTS
        grid.RESULTS = self.tmp

    def tearDown(self):
        grid.RESULTS = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def row(self, cell, seed, model="a/m", i=0):
        return json.dumps(dict(rung="blind", cell=cell, campaign_seed=seed, model=model,
                               kind="round", i=i)) + "\n"

    def archive(self, tag, lines):
        lp = os.path.join(self.tmp, "grid_%s_calls.jsonl" % tag)
        with open(lp, "w") as f:
            f.writelines(lines)
        grid.archive_calls(tag, os.path.join(self.tmp, "grid_%s_campaigns.jsonl" % tag), lp)

    def read(self, tag):
        out = []
        for g in sorted(glob.glob(os.path.join(self.tmp, "grid_%s_calls" % tag, "*.jsonl.gz"))):
            with gzip.open(g, "rt") as f:
                out += [json.loads(l) for l in f if l.strip()]
        return out

    def test_rerunning_one_cell_keeps_the_other_cells_rows(self):
        self.archive("bio", [self.row("BioRole", 7, i=1), self.row("BioRoleNoisy", 7, i=2),
                             self.row("BioRoleExact", 7, i=3)])
        self.archive("bio", [self.row("BioRole", 7, i=99)])
        got = sorted((r["cell"], r["i"]) for r in self.read("bio"))
        self.assertEqual(got, [("BioRole", 99), ("BioRoleExact", 3), ("BioRoleNoisy", 2)],
                         "rerunning one cell must not drop the other two cells at the same seed")

    def test_a_row_without_a_cell_still_keys_on_its_rung(self):
        """Every archive written before `cell` existed must merge exactly as it did."""
        old = json.dumps(dict(rung="blind", campaign_seed=7, model="a/m", kind="round", i=1)) + "\n"
        self.archive("legacy", [old])
        self.archive("legacy", [json.dumps(dict(rung="blind", campaign_seed=7, model="a/m",
                                                kind="round", i=42)) + "\n"])
        got = [r["i"] for r in self.read("legacy")]
        self.assertEqual(got, [42], "a legacy row must still be replaced by its rerun")

    def test_the_key_reads_the_cell_before_the_rung(self):
        src = open(os.path.join(ROOT, "scripts", "grid.py")).read()
        self.assertIn('d.get("cell") or d.get("rung")', src)
