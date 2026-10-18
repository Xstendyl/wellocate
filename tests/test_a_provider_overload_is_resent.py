"""Tests that a provider overload is resent while every other failure still abandons the campaign.

With --provider-retry, a raw response carrying error code 502 or 503, or error_type provider_unavailable, is
resent identically up to 5 attempts after waits of 30, 60, 120 and 240 s, and each overloaded attempt is kept
in the call archive. grid.main runs end to end on a mocked provider with a fake clock, for one overload, a
different failure, five overloads, and one overload with the flag off.
"""
import gzip, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = "unittest_overload"
OVERLOAD = {"id": "gen-test", "error": {"message": "Our servers are currently overloaded. Please try again later.",
                                        "code": 502, "metadata": {"error_type": "provider_unavailable"}}}

DRIVER = r'''
import hashlib, json, os, re, sys
tree, mode, retry = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
sys.path[:0] = [tree, os.path.join(tree, "scripts")]
os.chdir(tree)
import time as _t
clock = [1.8e9]
def fake_time():
    clock[0] += 0.125
    return clock[0]
_t.time = fake_time
waits = []
_t.sleep = lambda s: waits.append(s)
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
OVERLOAD = @OVERLOAD@
seen = {"overloaded": 0}

def fake_complete(prompt, model, **kw):
    if "ROUND 3 OF 15." in prompt and "ANSWER: XXXX" not in prompt:
        if mode in ("one", "off") and seen["overloaded"] == 0 or mode == "five":
            seen["overloaded"] += 1
            return llm.Call(model=model, error="empty content after 0 completion tokens (finish_reason=None): "
                                                "raise max_tokens or lower reasoning effort", raw=OVERLOAD)
        if mode == "other":
            return llm.Call(model=model, completion_tokens=7, finish_reason="stop", raw={"choices": [{}]},
                            error="empty content after 7 completion tokens (finish_reason=stop): raise "
                                  "max_tokens or lower reasoning effort")
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
        c = ref if b % 2 == 0 else ref[:(b // 2) % 4] + "ABCDEFGHIJKLMNOPQRST"[h[i + 8] % 20] + ref[(b // 2) % 4 + 1:]
        lines.append("%s | step %d" % (ref if c in excl else c, i))
    return llm.Call(text="\n".join(lines), model=model, prompt_tokens=len(prompt) // 4, completion_tokens=8 * n,
                    cost_usd=0.0001, provider="fake", finish_reason="stop", raw={"fake": 1})

llm.complete = fake_complete
sys.argv = ["grid.py", "--models", "openai/gpt-6.1-sol", "--conditions", "Blind", "--campaigns", "1",
            "--seed0", "300000", "--tag", "@TAG@", "--max-tokens", "16000", "--max-reasks", "3",
            "--temperature", "0.0", "--noise", "multiplicative", "--credit-floor", "0", "--workers", "1",
            "--shuffle", "--order-seed", "1", "--truthful-reask", "--budget-usd", "5"] + (["--provider-retry"] if retry else [])
try:
    grid.main()
finally:
    with open(os.path.join(tree, "waits.json"), "w") as f:
        json.dump(waits, f)
'''.replace("@TAG@", TAG).replace("@OVERLOAD@", repr(OVERLOAD))


def run(tmp, mode, retry):
    tree = os.path.join(tmp, "%s_%d" % (mode, retry))
    os.makedirs(tree)
    for d in ("scripts", "repdef", "wellocate"):
        shutil.copytree(os.path.join(ROOT, d), os.path.join(tree, d), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    os.makedirs(os.path.join(tree, "results"))
    shutil.copy(os.path.join(ROOT, "results", "step7_nk_reference_curve.json"), os.path.join(tree, "results"))
    drv = os.path.join(tmp, "driver.py")
    with open(drv, "w") as fh:
        fh.write(DRIVER)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "OPENROUTER_API_KEY")}
    r = subprocess.run([sys.executable, "-B", drv, tree, mode, "1" if retry else "0"], cwd=tree, capture_output=True,
                       text=True, env=env, timeout=600)
    res = os.path.join(tree, "results")
    lines = []
    adir = os.path.join(res, "grid_%s_calls" % TAG)
    if os.path.isdir(adir):
        for f in sorted(os.listdir(adir)):
            if f.endswith(".gz"):
                with gzip.open(os.path.join(adir, f), "rt") as fh:
                    lines += [l for l in fh.read().splitlines() if l.strip()]
    camp = os.path.join(res, "grid_%s_campaigns.jsonl" % TAG)
    ab = os.path.join(res, "grid_%s_abandoned_calls.jsonl" % TAG)
    with open(os.path.join(tree, "waits.json")) as fh:
        waits = json.load(fh)
    def rd(p):
        if not os.path.exists(p):
            return b""
        with open(p, "rb") as fh:
            return fh.read()
    return dict(out=r.stdout + r.stderr, code=r.returncode, campaigns=rd(camp), call_lines=lines, waits=waits,
                abandoned=[json.loads(l) for l in rd(ab).decode().splitlines() if l.strip()] if os.path.exists(ab) else None)


class AProviderOverloadIsResent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="overload_")
        cls.r = {k: run(cls.tmp, *k) for k in (("clean", True), ("one", True), ("other", True), ("five", True),
                                                ("off", False))}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def retry_rows(self, lines):
        return [json.loads(l) for l in lines if json.loads(l).get("kind") == "transport_retry"]

    def test_one_overload_then_success_writes_the_same_campaign(self):
        c, o = self.r[("clean", True)], self.r[("one", True)]
        for v in (c, o):
            self.assertEqual(v["code"], 0, v["out"][-2000:])
        self.assertEqual(len(c["campaigns"].splitlines()), 1)
        self.assertEqual(c["campaigns"], o["campaigns"], "the campaign record must be byte-identical")
        kept = [l for l in o["call_lines"] if json.loads(l).get("kind") != "transport_retry"]
        self.assertEqual(kept, c["call_lines"], "the call archive, the retry row set aside, must be byte-identical")
        rr = self.retry_rows(o["call_lines"])
        self.assertEqual(len(rr), 1)
        self.assertEqual((rr[0]["attempt"], rr[0]["wait_s"], rr[0]["retry_of"], rr[0]["round"]), (1, 30, "round", 3))
        self.assertEqual(rr[0]["raw_payload"], OVERLOAD)
        self.assertIn("ROUND 3 OF 15.", rr[0]["prompt"])
        self.assertEqual(rr[0]["campaign_seed"], 300000)
        self.assertEqual(o["waits"], [30])
        self.assertEqual(c["waits"], [])
        self.assertIsNone(o["abandoned"])

    def test_any_other_failure_still_abandons_at_once(self):
        v = self.r[("other", True)]
        self.assertIn("seed 300000 FAILED: transport failure on the round call", v["out"])
        self.assertEqual(v["campaigns"], b"")
        self.assertEqual(v["waits"], [], "a model's empty reply with a finish reason is never resent")
        self.assertEqual([r for r in (v["abandoned"] or []) if r.get("kind") == "transport_retry"], [])

    def test_five_overloads_abandon_and_keep_the_evidence(self):
        v = self.r[("five", True)]
        self.assertIn("seed 300000 FAILED: transport failure on the round call", v["out"])
        self.assertEqual(v["campaigns"], b"")
        self.assertEqual(v["call_lines"], [])
        self.assertEqual(v["waits"], [30, 60, 120, 240])
        recs = v["abandoned"]
        retries = [r for r in recs if r.get("kind") == "transport_retry"]
        fail = [r for r in recs if r.get("failing_call")]
        calls = [r for r in recs if r.get("kind") not in ("transport_retry",) and not r.get("failing_call")]
        self.assertEqual([r["attempt"] for r in retries], [1, 2, 3, 4])
        self.assertTrue(all(r["raw_payload"] == OVERLOAD and "ROUND 3 OF 15." in r["prompt"] for r in retries))
        self.assertEqual(len(fail), 1)
        self.assertEqual((fail[0]["round"], fail[0]["raw_payload"]), (3, OVERLOAD))
        self.assertEqual({c["round"] for c in calls}, {1, 2})

    def test_without_the_flag_an_overload_abandons_as_registered(self):
        v = self.r[("off", False)]
        self.assertIn("seed 300000 FAILED: transport failure on the round call", v["out"])
        self.assertEqual(v["campaigns"], b"")
        self.assertEqual(v["waits"], [])
        self.assertEqual([r for r in (v["abandoned"] or []) if r.get("kind") == "transport_retry"], [])


if __name__ == "__main__":
    unittest.main()
