"""Tests that an analysis run with --redact writes no number to any output file.

The check covers the whole output directory, including summary.json, not only the tables passed through
table(). Model identifiers carry version numbers that are not results, so they are excluded from the check
and must survive redaction intact.
"""
import glob, io, os, re, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECIMAL = re.compile(r"[-+]?\d+\.\d+")
MODEL_IDS = ("anthropic/claude-opus-4.7", "google/gemini-2.5-flash", "deepseek/deepseek-chat-v3.1",
             "claude-opus-4.7", "gemini-2.5-flash", "deepseek-chat-v3.1")
REAL_TAG = "stage1"          # a real tag with real condition means and a full set of six contrasts


def strip_model_ids(t):
    for m in MODEL_IDS:
        t = t.replace(m, "")
    return t


class RedactionLeavesNoNumber(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % REAL_TAG)):
            raise unittest.SkipTest("no %s data on disk" % REAL_TAG)
        cls.out = tempfile.mkdtemp(prefix="repdef_redact_test_")
        env = dict(os.environ)
        env.pop("ANALYSE_GRID_COMPLETE", None)  # --redact must work without the completion gate
        env.pop("ANALYSE_GRID_REDACT", None)
        cls.proc = subprocess.run(
            [sys.executable, "-B", os.path.join(ROOT, "scripts", "analyse_grid.py"),
             REAL_TAG, "--redact", "--out", cls.out],
            capture_output=True, text=True, env=env, cwd=ROOT)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "out", ""), ignore_errors=True)

    def files(self):
        return sorted(glob.glob(os.path.join(self.out, "*")))

    def test_it_ran_at_all_without_the_completion_gate(self):
        self.assertEqual(self.proc.returncode, 0,
                         "--redact must work without ANALYSE_GRID_COMPLETE:\n" +
                         (self.proc.stdout + self.proc.stderr)[-800:])
        self.assertGreaterEqual(len(self.files()), 6, "it wrote almost nothing, so this test is vacuous")

    def test_no_output_file_contains_a_decimal_number(self):
        leaks = []
        for f in self.files():
            with io.open(f, encoding="utf-8", errors="replace") as fh:
                found = DECIMAL.findall(strip_model_ids(fh.read()))
            if found:
                leaks.append("%s: %d (%s)" % (os.path.basename(f), len(found), ", ".join(found[:4])))
        self.assertEqual(leaks, [], "a --redact run wrote numbers to disk:\n  " + "\n  ".join(leaks))

    def test_the_json_summary_is_covered_and_not_only_the_text_tables(self):
        """summary.json is redacted as well as the text tables."""
        j = os.path.join(self.out, "summary.json")
        self.assertTrue(os.path.exists(j), "summary.json was not written, so nothing was checked")
        with io.open(j, encoding="utf-8") as fh:
            body = fh.read()
        self.assertEqual(DECIMAL.findall(strip_model_ids(body)), [])
        self.assertIn("REDACTED", body, "summary.json shows no sign of having been redacted at all")

    def test_the_contrast_structure_survives_so_the_run_is_still_verifiable(self):
        """Redaction removes the values but keeps the six contrasts and their structure."""
        import json
        with io.open(os.path.join(self.out, "summary.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertEqual(len(d.get("contrasts") or []), 6, "the six contrasts must still be present")
        self.assertTrue(d.get("paired_by_seed"))
        for c in d["contrasts"]:
            self.assertEqual(c["diff"], "REDACTED")
            self.assertIsInstance(c["seeds"], int)        # counts are not results

    def test_model_identifiers_are_not_mangled_by_redaction(self):
        """Model identifiers such as claude-opus-4.7 survive redaction unchanged."""
        with io.open(os.path.join(self.out, "table2_confirmatory.txt"), encoding="utf-8") as fh:
            t = fh.read()
        self.assertIn("claude-opus-4.7", t)
        self.assertNotIn("claude-opusREDACTED", t)


if __name__ == "__main__":
    unittest.main()
