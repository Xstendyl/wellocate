"""Tests that an abandoned campaign keeps its calls and its failing request, and that nothing else changes.

grid.main runs end to end against a mocked provider under a reference commit and under the current code. A
completed campaign's record and archived calls are byte-identical under both. An abandoned campaign is
abandoned the same way under both, and only the current code writes grid_<tag>_abandoned_calls.jsonl with the
earlier rounds' calls and the failing request.
"""
import gzip, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEFORE = "07f0b02"  # reference commit, before abandoned campaigns kept their calls
TAG = "unittest_abandon"

DRIVER = r'''
import hashlib, os, re, sys
tree, mode = sys.argv[1], sys.argv[2]
sys.path[:0] = [tree, os.path.join(tree, "scripts")]
os.chdir(tree)
import time as _t
clock = [1.8e9]
def fake_time():
    clock[0] += 0.125
    return clock[0]
_t.time = fake_time
from repdef import llm
import grid
grid.key_source = lambda: ("test", "00000000")
grid.check_credit = lambda where, floor=0: (500.0, True)
grid.credit_balance = lambda detail=False: (dict(account=500.0, key_remaining=500.0, binding=500.0,
                                                 key_expires_at=None, bound_by="key") if detail else 500.0)
grid.code_provenance = lambda: dict(git_commit="0" * 40, git_status_porcelain=[], code_dirty=False,
                                    code_dirty_paths=[], code_diff_sha256=None, git_commit_describes_the_code=True)
REF = re.compile(r'The reference point is "([A-T]{4})"')
N = re.compile(r"Reply with exactly (\d+) lines")
EXCL = re.compile(r"must not be proposed again this round: ([A-T, ]+)\.")
RAW_ERROR = {"error": {"code": 502, "message": "upstream provider error"}}

def fake_complete(prompt, model, **kw):
    if mode == "abandoned" and "ROUND 3 OF 15." in prompt:
        return llm.Call(model=model, error="empty content after 0 completion tokens (finish_reason=None): "
                                            "raise max_tokens or lower reasoning effort", raw=RAW_ERROR)
    ref = REF.search(prompt).group(1)
    h = hashlib.sha256(prompt.encode("utf-8")).digest()
    if "ANSWER: XXXX" in prompt:
        return llm.Call(text="ANSWER: %s\nREASON: highest so far" % ref, model=model, prompt_tokens=len(prompt) // 4,
                        completion_tokens=12, cost_usd=0.0001, provider="fake", finish_reason="stop", raw={"fake": 1})
    n = int(N.search(prompt).group(1))
    m = EXCL.search(prompt)
    excl = set(x.strip() for x in m.group(1).split(",")) if m else set()
    lines = []
    for i in range(n):
        b = h[i]
        if b % 2 == 0:
            c = ref
        else:
            pos, let = (b // 2) % 4, "ABCDEFGHIJKLMNOPQRST"[h[i + 8] % 20]
            c = ref[:pos] + let + ref[pos + 1:]
        if c in excl:
            c = ref
        lines.append("%s | step %d" % (c, i))
    return llm.Call(text="\n".join(lines), model=model, prompt_tokens=len(prompt) // 4, completion_tokens=8 * n,
                    cost_usd=0.0001, provider="fake", finish_reason="stop", raw={"fake": 1})

llm.complete = fake_complete
sys.argv = ["grid.py", "--models", "anthropic/claude-opus-4.7", "--conditions", "Blind", "--campaigns", "1",
            "--seed0", "300000", "--tag", "@TAG@", "--max-tokens", "6000", "--max-reasks", "3",
            "--temperature", "0.0", "--noise", "multiplicative", "--credit-floor", "0", "--workers", "1",
            "--shuffle", "--order-seed", "1", "--truthful-reask", "--budget-usd", "5"]
grid.main()
'''.replace("@TAG@", TAG)


def build(tree, src):
    """A temporary tree: the code dirs from `src` (a commit, or None for the working tree) and the one results
    file grid.main reads."""
    os.makedirs(tree)
    if src:
        arch = subprocess.run(["git", "archive", src, "scripts", "repdef", "wellocate"], cwd=ROOT,
                              capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", tree], input=arch, check=True)
    else:
        for d in ("scripts", "repdef", "wellocate"):
            shutil.copytree(os.path.join(ROOT, d), os.path.join(tree, d),
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    os.makedirs(os.path.join(tree, "results"))
    shutil.copy(os.path.join(ROOT, "results", "step7_nk_reference_curve.json"), os.path.join(tree, "results"))


def run(tree, mode, tmp):
    drv = os.path.join(tmp, "driver.py")
    with open(drv, "w") as fh:
        fh.write(DRIVER)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "OPENROUTER_API_KEY")}
    r = subprocess.run([sys.executable, "-B", drv, tree, mode], cwd=tree, capture_output=True, text=True, env=env,
                       timeout=600)
    res = os.path.join(tree, "results")
    calls = {}
    adir = os.path.join(res, "grid_%s_calls" % TAG)
    if os.path.isdir(adir):
        for f in sorted(os.listdir(adir)):
            if f.endswith(".gz"):
                with gzip.open(os.path.join(adir, f), "rb") as fh:
                    calls[f] = fh.read()
    camp = os.path.join(res, "grid_%s_campaigns.jsonl" % TAG)
    ab = os.path.join(res, "grid_%s_abandoned_calls.jsonl" % TAG)
    read = lambda p, mode: open(p, mode).read() if os.path.exists(p) else None
    text = read(ab, "r")
    return dict(out=r.stdout + r.stderr, code=r.returncode, campaigns=read(camp, "rb") or b"", calls=calls,
                abandoned=[json.loads(l) for l in text.splitlines() if l.strip()] if text is not None else None)


class AnAbandonedCampaignKeepsItsEvidence(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        have = subprocess.run(["git", "cat-file", "-e", BEFORE + "^{commit}"], cwd=ROOT, capture_output=True)
        if have.returncode != 0:
            raise unittest.SkipTest("commit %s is not in this clone" % BEFORE)
        cls.tmp = tempfile.mkdtemp(prefix="abandon_evidence_")
        cls.r = {}
        for version, src in (("before", BEFORE), ("now", None)):
            for mode in ("written", "abandoned"):
                tree = os.path.join(cls.tmp, "%s_%s" % (version, mode))
                build(tree, src)
                cls.r[(version, mode)] = run(tree, mode, cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def test_a_written_campaign_is_byte_identical_before_and_after(self):
        b, n = self.r[("before", "written")], self.r[("now", "written")]
        self.assertEqual(b["code"], 0, b["out"][-2000:])
        self.assertEqual(n["code"], 0, n["out"][-2000:])
        self.assertEqual(len(b["campaigns"].splitlines()), 1, "the written run must write its one campaign")
        self.assertTrue(b["calls"], "the written run must archive its calls")
        self.assertEqual(b["campaigns"], n["campaigns"])
        self.assertEqual(b["calls"], n["calls"])
        self.assertIsNone(n["abandoned"], "a written campaign must not create the abandoned file")

    def test_an_abandoned_campaign_is_unwritten_under_both_and_kept_only_now(self):
        b, n = self.r[("before", "abandoned")], self.r[("now", "abandoned")]
        line = "seed 300000 FAILED: transport failure on the round call to anthropic/claude-opus-4.7, " \
               "campaign abandoned unwritten: empty content after 0 completion tokens (finish_reason=None)"
        for v in (b, n):
            self.assertIn(line, v["out"])
            self.assertEqual(v["campaigns"], b"")
            self.assertEqual(v["calls"], {})
        self.assertIsNone(b["abandoned"], "the code before the change kept nothing")
        recs = n["abandoned"]
        self.assertTrue(recs and all(r["abandoned"] for r in recs))
        fail = [r for r in recs if r.get("failing_call")]
        calls = [r for r in recs if not r.get("failing_call")]
        self.assertEqual(len(fail), 1)
        f = fail[0]
        self.assertEqual((f["round"], f["kind"], f["campaign_seed"]), (3, "round", 300000))
        self.assertIn("ROUND 3 OF 15.", f["prompt"])
        self.assertEqual(f["raw_payload"], {"error": {"code": 502, "message": "upstream provider error"}})
        self.assertEqual((f["completion_tokens"], f["finish_reason"], f["empty_text"]), (0, "", True))
        self.assertIn("abandoned unwritten", f["exception"])
        self.assertTrue(calls and {c["round"] for c in calls} == {1, 2},
                        "the calls before the failure are kept: rounds 1 and 2")
        self.assertTrue(all(c["campaign_seed"] == 300000 for c in calls))


if __name__ == "__main__":
    unittest.main()
