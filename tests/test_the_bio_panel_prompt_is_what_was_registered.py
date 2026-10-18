"""Tests that the biology-framing panel sends the pre-registered prompt and that its design properties hold.

The panel changes one sentence of a frozen prompt, so each cell must differ from the grid's Blind prompt in
exactly the ways the design says, the role sentence must make no claim about when a result arrives, and every
hash must match the pre-registration.
"""
import json, os, re, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD = os.path.join(ROOT, "results", "bio_framing_prompts.json")
PREREG = os.path.join(ROOT, "spec", "GRID_PREREGISTRATION.md")
KINDS = ["round", "replacement", "reask", "nomination"]
CELLS = ["bio_role", "bio_role_noisy", "bio_role_exact"]


class BioPanelPrompt(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Regenerate from the script, so the test checks the implementation and not a stale file.
        subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "bio_framing_diff.py")],
                       capture_output=True, cwd=ROOT, check=True)
        cls.d = json.load(open(RECORD))
        cls.r = cls.d["rendered"]
        cls.pre = open(PREREG).read()

    def test_the_role_sentence_makes_no_claim_about_when_a_result_arrives(self):
        role = self.d["role"]
        self.assertTrue(role.endswith("submitted to the lab's assay facility."), role[-60:])
        for phrase in ("end of the round", "comes back", "at the end of"):
            self.assertNotIn(phrase, role,
                             "the role text must not describe timing: a replacement prompt renders "
                             "mid-round and shows readings from that same round")

    def test_the_role_text_is_the_one_in_the_preregistration(self):
        self.assertIn(self.d["role"].replace("'", "'"), self.pre.replace("\n> ", " ").replace("\n", " "),
                      "the pre-registration must quote the role text the script actually applies")

    def test_every_diff_is_two_lines(self):
        for cell in CELLS:
            for kind in KINDS:
                self.assertEqual(self.r["%s|%s" % (cell, kind)]["diff_lines"], 2,
                                 "%s/%s changed more than the one sentence" % (cell, kind))

    def test_the_exact_cell_is_byte_identical_to_the_role_cell(self):
        """bio_role_exact differs from bio_role only in sigma, so its prompts are the same bytes."""
        for kind in KINDS:
            self.assertEqual(self.r["bio_role|%s" % kind]["sha256"],
                             self.r["bio_role_exact|%s" % kind]["sha256"],
                             "%s differs, so the exact cell is not a pure noise manipulation" % kind)

    def test_the_noisy_cell_differs_in_every_prompt_type(self):
        for kind in KINDS:
            self.assertNotEqual(self.r["bio_role|%s" % kind]["sha256"],
                                self.r["bio_role_noisy|%s" % kind]["sha256"],
                                "%s is identical, so the noise sentence did not land" % kind)

    def test_the_grid_prompts_are_untouched(self):
        """Every cell has the grid's own Blind prompt as its base: one base hash per prompt type, four distinct in all."""
        bases = {}
        for cell in CELLS:
            for kind in KINDS:
                bases.setdefault(kind, set()).add(self.r["%s|%s" % (cell, kind)]["base_sha256"])
        for kind, vals in bases.items():
            self.assertEqual(len(vals), 1, "%s has more than one base prompt" % kind)
        self.assertEqual(len({next(iter(v)) for v in bases.values()}), 4,
                         "the four prompt types must have four distinct base hashes")

    def test_every_hash_appears_in_the_preregistration(self):
        for cell in CELLS:
            for kind in KINDS:
                h = self.r["%s|%s" % (cell, kind)]["sha256"][:16]
                self.assertIn(h, self.pre,
                              "%s/%s hashes to %s, which no amendment records" % (cell, kind, h))

    def test_the_script_touches_nothing_under_repdef(self):
        src = open(os.path.join(ROOT, "scripts", "bio_framing_diff.py")).read()
        self.assertFalse(re.search(r"open\([^)]*repdef[^)]*['\"]w", src),
                         "the panel must not write into the frozen harness")


if __name__ == "__main__":
    unittest.main()


class TheHarnessRendersTheConfirmedBytes(unittest.TestCase):
    """The harness, which renders what the panel sends, reproduces the twelve confirmed prompt hashes."""

    # The twelve confirmed prompt hashes (first 16 hex digits).
    CONFIRMED = {
        ("bio_role", "round"): "a1e526cdb571bd78",
        ("bio_role", "replacement"): "e2cd57690baae7c2",
        ("bio_role", "reask"): "0313ba8cde99368d",
        ("bio_role", "nomination"): "00d1176f43ccd6aa",
        ("bio_role_noisy", "round"): "d017e7984c8c1a6b",
        ("bio_role_noisy", "replacement"): "8bf7e390a1abd2ca",
        ("bio_role_noisy", "reask"): "b62964333d6cfb2c",
        ("bio_role_noisy", "nomination"): "53a5e26d01e62ddc",
        ("bio_role_exact", "round"): "a1e526cdb571bd78",
        ("bio_role_exact", "replacement"): "e2cd57690baae7c2",
        ("bio_role_exact", "reask"): "0313ba8cde99368d",
        ("bio_role_exact", "nomination"): "00d1176f43ccd6aa",
    }

    def test_the_harness_reproduces_every_confirmed_hash(self):
        import hashlib
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import test_prompt_contract as C
        from repdef import prompts
        for (cell, kind), want in sorted(self.CONFIRMED.items()):
            kw = dict(C.kw("multiplicative"), opening=cell)
            if kind == "nomination":
                text = prompts.build_nomination("blind", C.HIST, 15, 4, 0.0, **kw)
            elif kind == "replacement":
                text = prompts.build("blind", C.HIST, 4, 15, 1, 44, 0.0, **kw) + (
                    "\n\nThese candidates were just rejected as non-viable and must not be "
                    "proposed again this round: GDBF, GDCF.")
            elif kind == "reask":
                text = prompts.build("blind", C.HIST, 4, 15, 4, 44, 0.0, **kw) + (
                    "\n\nYour previous reply did not contain exactly 4 candidates, one per line, in the "
                    "form\nCANDIDATE | one short reason\nReply again with exactly 4 such lines and "
                    "nothing else.")
            else:
                text = prompts.build("blind", C.HIST, 4, 15, 4, 44, 0.0, **kw)
            got = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            self.assertEqual(got, want,
                             "the HARNESS renders %s/%s as %s; the confirmed value is %s"
                             % (cell, kind, got, want))

    def test_the_role_text_exists_in_exactly_one_place(self):
        """The role sentence is defined only in the harness; the script imports it."""
        src = open(os.path.join(ROOT, "scripts", "bio_framing_diff.py")).read()
        self.assertIn("from repdef.prompts import OPENINGS", src)
        self.assertNotIn("protein engineer working in a wet lab", src,
                         "the script must import the role text, never restate it")


class TheRunPathSelectsTheRightEnvironment(unittest.TestCase):
    """grid.py hands each bio cell both its opening and its sigma, and hands the grid neither.

    A cell rendered with the right opening but run at the wrong sigma would look complete and answer a
    different question.
    """

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import grid
        self.grid = grid

    def test_each_bio_cell_maps_to_its_opening_and_noise(self):
        self.assertEqual(self.grid.CELL_ENV["BioRole"], ("bio_role", "multiplicative"))
        self.assertEqual(self.grid.CELL_ENV["BioRoleNoisy"], ("bio_role_noisy", "multiplicative"))
        self.assertEqual(self.grid.CELL_ENV["BioRoleExact"], ("bio_role_exact", "exact"))

    def test_the_exact_cell_is_the_only_one_at_sigma_zero(self):
        at_zero = [k for k, (_o, n) in self.grid.CELL_ENV.items() if n == "exact"]
        self.assertEqual(at_zero, ["BioRoleExact"])

    def test_a_grid_condition_gets_the_default_opening(self):
        for name, _rung in self.grid.CONDITIONS:
            self.assertNotIn(name, self.grid.CELL_ENV,
                             "%s would be rendered with a panel opening" % name)

    def test_the_bio_cells_are_not_in_the_default_condition_list(self):
        names = {c[0] for c in self.grid.CONDITIONS}
        for name, _rung in self.grid.BIO_CONDITIONS:
            self.assertNotIn(name, names, "%s would run in a plain grid launch" % name)

    def test_every_bio_cell_runs_on_the_blind_rung(self):
        for _name, rung in self.grid.BIO_CONDITIONS:
            self.assertEqual(rung, "blind",
                             "the panel copies the Blind prompt, so every cell is the blind rung")

    def test_every_cell_env_opening_exists_in_the_harness(self):
        from repdef import prompts
        for name, (opening, _n) in self.grid.CELL_ENV.items():
            self.assertIn(opening, prompts.OPENINGS, "%s names an opening the harness lacks" % name)

    def test_the_policy_refuses_an_opening_the_harness_does_not_know(self):
        from repdef import llm_policy
        with self.assertRaises(ValueError):
            llm_policy.LLMPolicy("m", "blind", 0.0, opening="no_such_opening")
