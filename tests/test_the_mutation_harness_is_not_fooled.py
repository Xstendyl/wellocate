"""Tests of the mutation harness itself.

A same-length mutation must reach the interpreter rather than stale bytecode, a mutant that did not load is
refused, the file is always restored, a concurrent edit is never overwritten, and a hang is caught.
"""
import io, os, unittest
from repdef import mutate

PROMPTS = os.path.join(mutate.REPO, "repdef", "prompts.py")


class ASameLengthMutationReachesTheInterpreter(unittest.TestCase):
    def test_the_canary_sees_a_same_length_swap(self):
        # Both alphabets are 20 characters, so the swap keeps the file length and can be masked by stale bytecode.
        self.assertEqual(len("ABCDEFGHIJKLMNOPQRST"), len("ACDEFGHIKLMNPQRSTVWY"))
        verdict = mutate.check(
            PROMPTS, 'alphabet="ABCDEFGHIJKLMNOPQRST"', 'alphabet="ACDEFGHIKLMNPQRSTVWY"',
            ["tests.test_interventions_are_clean"],
            canary="prompts.LANDSCAPES['abstract']['alphabet']",
            expect="ACDEFGHIKLMNPQRSTVWY", label="same-length-alphabet")
        self.assertEqual(verdict, "CAUGHT")

    def test_a_mutant_that_does_not_load_is_refused_not_reported(self):
        # Ask the canary for a value the mutation does not produce: the harness must raise rather than give a
        # verdict on code that never ran.
        with self.assertRaises(mutate.StaleMutant):
            mutate.check(PROMPTS, 'metric="score"', 'metric="score "',
                         ["tests.test_interventions_are_clean"],
                         canary="prompts.LANDSCAPES['abstract']['metric']",
                         expect="something else entirely", label="deliberately-wrong-canary")

    def test_a_drifted_anchor_raises_instead_of_passing(self):
        with self.assertRaises(ValueError):
            mutate.check(PROMPTS, "this text is not in the file", "x",
                         ["tests.test_interventions_are_clean"])

    def test_the_file_is_restored_even_when_the_canary_fails(self):
        before = io.open(PROMPTS, encoding="utf-8").read()
        try:
            mutate.check(PROMPTS, 'metric="score"', 'metric="scorx"',
                         ["tests.test_interventions_are_clean"],
                         canary="prompts.LANDSCAPES['abstract']['metric']",
                         expect="never", label="restore-check")
        except mutate.StaleMutant:
            pass
        self.assertEqual(io.open(PROMPTS, encoding="utf-8").read(), before)

    def test_it_knows_about_the_pycache_prefix_layout(self):
        # The harness must look under sys.pycache_prefix when one is set, not only beside the source.
        paths = mutate.bytecode_paths(PROMPTS)
        self.assertTrue(any("__pycache__" in p for p in paths))
        import sys
        if sys.pycache_prefix:
            self.assertTrue(any(p.startswith(sys.pycache_prefix) for p in paths),
                            "harness ignores sys.pycache_prefix: %s" % paths)

    def test_it_refuses_to_restore_over_a_concurrent_edit(self):
        # A file edited while it holds a mutant must not be overwritten by the restore; the harness raises instead.
        # The edit is injected in the test-run step, after the mutant is written and before the restore.
        marker = "\n# a concurrent writer was here\n"
        before = io.open(PROMPTS, encoding="utf-8").read()
        orig_run = mutate._run

        def run_and_edit(cmd, cwd=mutate.REPO, timeout=None):
            cur = io.open(PROMPTS, encoding="utf-8").read()
            io.open(PROMPTS, "w", encoding="utf-8").write(cur + marker)
            return orig_run(cmd, cwd=cwd, timeout=timeout)

        mutate._run = run_and_edit
        try:
            with self.assertRaises(mutate.ConcurrentEdit):
                mutate.check(PROMPTS, 'metric="score"', 'metric="scoreX"',
                             ["tests.test_interventions_are_clean"], label="concurrent", timeout=30)
            # The concurrent writer's content must survive.
            self.assertIn(marker, io.open(PROMPTS, encoding="utf-8").read())
        finally:
            mutate._run = orig_run
            io.open(PROMPTS, "w", encoding="utf-8").write(before)
            mutate.clear_bytecode()

    def test_a_hanging_mutant_is_caught_and_does_not_stall_the_run(self):
        # A mutant that hangs the suite is recorded as its own outcome within the timeout.
        import time
        t0 = time.time()
        v = mutate.check(PROMPTS, "def _fmt(x):",
                         "def _fmt(x):\n    import time as _t; _t.sleep(600)",
                         ["tests.test_interventions_are_clean"], label="hang", timeout=6)
        self.assertEqual(v, "CAUGHT (hang)")
        self.assertLess(time.time() - t0, 60)

    def test_the_baseline_is_green(self):
        ok, out = mutate.baseline(["tests.test_interventions_are_clean"])
        self.assertTrue(ok, "cannot mutation-test against a red baseline:\n" + out[-2000:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
