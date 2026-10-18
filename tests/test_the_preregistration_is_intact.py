"""Tests that the pre-registration still contains every section it has ever contained.

Each required section is checked by heading and order, along with the commitments an edit would be most
likely to remove.
"""
import io, os, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRID = os.path.join(ROOT, "spec", "GRID_PREREGISTRATION.md")
NK = os.path.join(ROOT, "spec", "NK_PREREGISTRATION.md")
METHODS = os.path.join(ROOT, "spec", "METHODS_VERBATIM.md")

REQUIRED_SECTIONS = [
    "## 0. AMENDMENT",
    "## 0b. THE SCRIPTED REFERENCE",
    "## 0c. OUTCOME AMENDMENT",
    "## 0d. THE REPLICATION FRACTION IS REPORTED FOUR WAYS",
    "## 0e. SIZING AMENDMENT",
    "## 0f. THE HEADLINE BEHAVIOURAL METRIC IS DISTINCT VARIANTS MEASURED",
    "## 0g. CONFIRMATORY FAMILY",
    "## 0h. RUN ORDER, DRIFT AND REPORTING",
    "## 0i. THE BLIND RUNG",
    "## 0j. WHAT THE AGENT IS",
    "## 0k. SCAFFOLDED CONDITIONS",
    "## 0l. DEVIATIONS AND CORRECTIONS RECORDED BEFORE THE TOP-UP",
    "## 0m. PRE-REGISTERED BEFORE THE TOP-UP LAUNCHES",
    "## 0n. THE ENVIRONMENT MISREPORTED THE BUDGET",
    "## 0o. THE SIZING RULE",
    "## 0p. THE HARNESS IS FROZEN",
    "## 0q. THE THREE PARALLEL PANELS",
    "## 0r. THE NOMINATION PROMPT WAS TRUNCATED",
    "## 0s. THE CONFIRMATORY CONTRASTS ARE PAIRED BY SEED",
    "## 0t. TWO PANELS RAN CODE THAT NO COMMIT CONTAINED",
    "## 0u. THE REASONING TREATMENT IS THE GRID'S OWN SETTING",
    "## 0v. A CALL IS BOUNDED IN TOTAL TIME AND ATTRIBUTED TO A PROVIDER",
    "## 0w. THE TOP-UP N, AND THE LAUNCH",
    "## 0x. THE ZERO-NOISE CEILING RISES TO $110",
    "## 0y. DEEPSEEK IS EXCLUDED FROM THE REASONING PANEL",
    "## 0z. CREDITS RAN OUT AND THE HARNESS CHARGED IT TO THE AGENT",
    "## 0aa. THE BIOLOGY-LAB FRAMING PANEL",
    "## 0ab. A SECOND GATE BYPASS OF MINE",
    "## 0ac. THE CREDIT FIGURES",
    "## 0ad. THE CENTRAL TEST",
    "## 0ae. THREE BUGS IN THE FIRST TABLE 2c",
    "## 0af. REPLICATION IS JUDGED AT MEASUREMENT TIME",
    "## 0ag. A SILENT NOMINATION FALLBACK",
    "## 0ah. SILENT-SUBSTITUTION SWEEP",
    "## 0ai. THE SCRIPTED REFERENCE IS UNFAIR ON EXPLORATION",
]

# Commitments that must survive any edit, each made before any result existed.
REQUIRED_COMMITMENTS = [
    ("empirical-Bayes", "the fair comparator"),
    ("ref_shrinkage_oracle", "the oracle prior kept only as a labelled reference"),
    ("MINIMAL AGENT", "what the agent is"),
    ("HOLM", "the correction across the confirmatory family"),
    ("Aggregated vs Mechanism", "the confirmatory contrasts"),
    ("distinct variants measured", "the headline behavioural metric"),
    ("0.06", "the minimal effect of interest"),
    ("2.8", "the standard-error target"),
    ("k\\* = 1", "the scripted optimum on the primary landscape"),
    ("SAME seeds", "the scaffolded cells are matched to Mechanism"),
    ("zero-noise control", "the confirmatory test of the Blind result"),
    ("shuffled", "the top-up's run order"),
    ("3.4799", "the z that powers the confirmatory family under Holm"),
    ("Temperature is 0", "the decoding temperature, which belongs in the pre-registration"),
    ("PAIRED BY SEED", "the confirmatory contrasts pair on the seed"),
    ("common random numbers", "why the cells are dependent"),
    ("git_commit_describes_the_code", "the manifest states whether its commit is the code"),
    ("nomination call", "the provider sensitivity restricts on the outcome call"),
    ("UNRECOVERABLE", "stage 1's providers are not known"),
    ("abandoned unwritten", "a transport failure is never charged to the agent"),
    ("credit-floor", "money is a pre-flight check"),
    ("top-up campaigns only", "the sensitivity that answers stage 1's blocked order"),
    ("did print condition means", "the deviation I have to own"),
    ("STAGE 0", "the 600 campaigns are a pilot and do not pool"),
    ("min(60 - used, rounds_left x 4)", "the corrected remaining count"),
    ("SLOT LOST", "a lost slot is visible to the agent"),
    ("+0.914", "the cell-level correlation, kept with its within-model correction"),
    ("proposal viability", "the defensible description of lost slots"),
    ("+0.016", "the within-model correlation that corrects the cell-level one"),
    ("N - k", "the pooling divisor"),
    ("BETWEEN-STAGE DRIFT", "what the top-up-only analysis is for once both halves are shuffled"),
    ("The freeze is at", "the harness freeze, whose commit moves when a rerun forces it"),
    ("PLACEBOS by construction", "why the zero-noise control runs all five conditions"),
    ("stops at twice the floor", "the cost rule on the reasoning panel"),
    ("STAGE 1a", "the void run kept as a behaviour pilot"),
    ("PROMPT CANARY", "the pre-launch check on the nomination prompt"),
]

REQUIRED_NK = ["FIFTH AMENDMENT", "FOURTH AMENDMENT", "THIRD AMENDMENT", "SECOND AMENDMENT",
               "FIRST AMENDMENT"]


class ThePreregistrationIsIntact(unittest.TestCase):
    def setUp(self):
        self.grid = io.open(GRID, encoding="utf-8").read()

    def test_every_section_is_present(self):
        for h in REQUIRED_SECTIONS:
            self.assertIn(h, self.grid, "MISSING SECTION: %s" % h)

    def test_the_sections_are_in_order(self):
        pos = [self.grid.index(h) for h in REQUIRED_SECTIONS if h in self.grid]
        self.assertEqual(pos, sorted(pos), "sections are out of order, so an insertion misfired")

    def test_every_commitment_survives(self):
        # Case-insensitive, because some commitments appear capitalised in the document.
        low = self.grid.lower()
        for needle, why in REQUIRED_COMMITMENTS:
            self.assertIn(needle.lower(), low, "MISSING COMMITMENT (%s): %r" % (why, needle))

    def test_no_section_is_empty(self):
        # A heading with nothing under it is what a bad slice leaves behind.
        for i, h in enumerate(REQUIRED_SECTIONS):
            start = self.grid.index(h)
            nxt = min((self.grid.index(x) for x in REQUIRED_SECTIONS[i + 1:]
                       if x in self.grid and self.grid.index(x) > start), default=len(self.grid))
            body = self.grid[start + len(h):nxt].strip()
            self.assertGreater(len(body), 120, "section %s has almost no body" % h)

    def test_every_nk_amendment_survives(self):
        nk = io.open(NK, encoding="utf-8").read()
        for a in REQUIRED_NK:
            self.assertIn(a, nk, "MISSING NK AMENDMENT: %s" % a)

    def test_the_methods_define_the_minimal_agent(self):
        m = io.open(METHODS, encoding="utf-8").read()
        self.assertIn("MINIMAL AGENT", m)
        for needle in ("no tools", "no memory beyond", "no code execution"):
            self.assertIn(needle, m, needle)


if __name__ == "__main__":
    unittest.main(verbosity=2)
