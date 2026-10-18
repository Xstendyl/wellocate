"""Tests that a run refuses an API key shared with another project and that the manifest records which key it used.

`llm._key` falls back to a sibling project's .env file when OPENROUTER_API_KEY is unset, so the run checks
where its key came from. The key never appears in output; it is identified only by an eight-hex
fingerprint of its SHA256.
"""
import hashlib, io, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import grid  # noqa: E402

MINE, THEIRS = "sk-or-test-repdef-key", "sk-or-test-sibling-platform-key"


class TheRunUsesItsOwnKey(unittest.TestCase):

    def setUp(self):
        self._env = os.environ.get("OPENROUTER_API_KEY")
        self._real = grid._key_line
        self.addCleanup(self._restore)

    def _restore(self):
        grid._key_line = self._real
        if self._env is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = self._env

    def files(self, mine=MINE, theirs=THEIRS):
        grid._key_line = lambda p: mine if p == grid.REPDEF_ENV else theirs

    def test_the_happy_path_names_repdef_env_and_fingerprints_it(self):
        self.files()
        os.environ["OPENROUTER_API_KEY"] = MINE
        src, fp = grid.key_source()
        self.assertEqual(src, "repdef/.env")
        self.assertEqual(fp, hashlib.sha256(MINE.encode()).hexdigest()[:8])
        self.assertNotIn(MINE, src)
        self.assertEqual(len(fp), 8)

    def test_an_absent_env_var_refuses_because_the_fallback_is_the_shared_key(self):
        """A missing env var is refused, because llm._key would then fall back to the shared key."""
        self.files()
        os.environ.pop("OPENROUTER_API_KEY", None)
        with self.assertRaises(SystemExit) as cm:
            grid.key_source()
        self.assertIn("fall back", str(cm.exception))
        self.assertIn("sibling project", str(cm.exception))

    def test_the_shared_key_in_the_environment_is_refused_too(self):
        """The shared key is refused even when it is set in the environment."""
        self.files()
        os.environ["OPENROUTER_API_KEY"] = THEIRS
        with self.assertRaises(SystemExit) as cm:
            grid.key_source()
        self.assertIn("SAME", str(cm.exception))

    def test_a_third_key_is_allowed_but_labelled_as_unmatched(self):
        """A key from an environment variable that matches no .env file is allowed but labelled as unmatched."""
        self.files()
        os.environ["OPENROUTER_API_KEY"] = "sk-or-some-other-key"
        src, fp = grid.key_source()
        self.assertNotEqual(src, "repdef/.env")
        self.assertIn("matches no .env file", src)

    def test_it_still_refuses_when_the_sibling_file_is_missing_and_no_env_var_is_set(self):
        """The run still refuses when the sibling file is missing and no env var is set."""
        grid._key_line = lambda p: MINE if p == grid.REPDEF_ENV else None
        os.environ.pop("OPENROUTER_API_KEY", None)
        with self.assertRaises(SystemExit):
            grid.key_source()

    def test_the_fingerprint_is_not_the_key_and_distinguishes_keys(self):
        a = grid._fp(MINE)
        b = grid._fp(THEIRS)
        self.assertNotEqual(a, b)
        for f in (a, b):
            self.assertEqual(len(f), 8)
            self.assertNotIn(f, MINE)
            self.assertNotIn(f, THEIRS)
        self.assertIsNone(grid._fp(None))

    def test_the_real_repdef_env_is_ignored_by_git(self):
        """The real repdef/.env is ignored by git and not tracked."""
        import subprocess
        r = subprocess.run(["git", "check-ignore", ".env"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, "repdef/.env is NOT gitignored")
        r2 = subprocess.run(["git", "ls-files", "--error-unmatch", ".env"], cwd=ROOT,
                            capture_output=True, text=True)
        self.assertNotEqual(r2.returncode, 0, "repdef/.env is TRACKED by git")


if __name__ == "__main__":
    unittest.main()


class TheSpendableCreditIsTheBindingLimit(unittest.TestCase):
    """The spendable credit is the smaller of the account balance and the key's remaining limit."""

    def setUp(self):
        self._real = grid.urllib.request.urlopen
        self._key = grid.LP.llm._key
        grid.LP.llm._key = lambda _e=None: "test-key"
        self.addCleanup(lambda: setattr(grid.urllib.request, "urlopen", self._real))
        self.addCleanup(lambda: setattr(grid.LP.llm, "_key", self._key))

    def serve(self, credits=None, keyinfo=None):
        import io as _io, json as _json

        class R(object):
            def __init__(self, payload):
                self._b = _json.dumps({"data": payload}).encode()

            def read(self):
                return self._b

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if url.endswith("/credits"):
                if credits is None:
                    raise RuntimeError("credits unreadable")
                return R(credits)
            if credits is None and keyinfo is None:
                raise RuntimeError("both unreadable")
            if keyinfo is None:
                raise RuntimeError("key unreadable")
            return R(keyinfo)
        grid.urllib.request.urlopen = fake

    def test_the_key_limit_binds_when_it_is_the_smaller(self):
        self.serve({"total_credits": 2300, "total_usage": 1171.88},
                   {"limit_remaining": 828.08, "expires_at": "2026-10-28T04:16:20Z"})
        d = grid.credit_balance(detail=True)
        self.assertAlmostEqual(d["account"], 1128.12, places=2)
        self.assertAlmostEqual(d["key_remaining"], 828.08, places=2)
        self.assertAlmostEqual(d["binding"], 828.08, places=2)
        self.assertEqual(d["bound_by"], "key")

    def test_the_account_binds_when_it_is_the_smaller(self):
        self.serve({"total_credits": 100, "total_usage": 90}, {"limit_remaining": 500})
        d = grid.credit_balance(detail=True)
        self.assertAlmostEqual(d["binding"], 10.0, places=6)
        self.assertEqual(d["bound_by"], "account")

    def test_it_falls_back_to_limit_minus_usage_when_remaining_is_absent(self):
        self.serve({"total_credits": 900, "total_usage": 0}, {"limit": 1000, "usage": 400})
        self.assertAlmostEqual(grid.credit_balance(), 600.0, places=6)

    def test_one_readable_endpoint_is_enough_and_the_other_does_not_veto(self):
        """One readable endpoint is enough; a failure of the other does not block a launch."""
        self.serve(None, {"limit_remaining": 700})
        self.assertAlmostEqual(grid.credit_balance(), 700.0, places=6)

    def test_both_unreadable_returns_none_and_never_raises(self):
        self.serve(None, None)
        self.assertIsNone(grid.credit_balance())
        bal, ok = grid.check_credit("unittest")
        self.assertIsNone(bal)
        self.assertTrue(ok, "an unreadable endpoint must not block a launch")
