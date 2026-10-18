"""Tests for the prompt contract across every rung, noise mode and prompt type.

Every rendered prompt carries all its rung's block sentences and the full header, nominations differ across
rungs exactly where round prompts do, and a SHA256 snapshot makes any prompt change fail until the snapshot
is updated on purpose.
"""
import hashlib, io, os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from repdef import prompts  # noqa: E402

CV, FLOOR = 0.073, (1 / 557) / (285 / 557)
HIST = [(1, "GDIF", "ok", 6.9), (1, "GDIF", "ok", 7.1), (2, "GDAF", "ok", 7.4),
        (2, "GDBF", "rejected", None), (2, "GDBF", "abandoned", None), (3, "----", "round_lost", None)]
SNAP = os.path.join(ROOT, "spec", "PROMPT_SNAPSHOT.txt")
# The last sentence of the shared HEADER. If a prompt is truncated anywhere in the header, this goes.
HEADER_TAIL = "and its slots count against your budget."


def kw(noise):
    d = dict(landscape="abstract", parent="GDIF", example="ADIF", anchor_reading="6.87", max_reasks=3)
    if noise == "multiplicative":
        d.update(noise_model="multiplicative", cv=CV, noise_floor=FLOOR)
    else:
        d.update(noise_model="exact")
    return d


def rendered():
    """{(rung, noise, kind): text} for every combination the harness can produce."""
    out = {}
    for noise in ("multiplicative", "exact"):
        for rung in prompts.RUNGS:
            base = prompts.build(rung, HIST, 4, 15, 4, 44, 0.0, **kw(noise))
            out[(rung, noise, "round")] = base
            # The replacement ask is built with slots=1, as llm_policy builds it, so the snapshot covers the
            # replacement prompt that is actually sent.
            base_one = prompts.build(rung, HIST, 4, 15, 1, 44, 0.0, **kw(noise))
            out[(rung, noise, "replacement")] = base_one + (
                "\n\nThese candidates were just rejected as non-viable and must not be "
                "proposed again this round: GDBF, GDCF.")
            # The re-ask after a wrong count, exactly as llm_policy composes it.
            out[(rung, noise, "reask")] = base + (
                "\n\nYour previous reply did not contain exactly 4 candidates, one per line, in the "
                "form\nCANDIDATE | one short reason\nReply again with exactly 4 such lines and "
                "nothing else.")
            out[(rung, noise, "nomination")] = prompts.build_nomination(
                rung, HIST, 15, 4, 0.0, **kw(noise))
    return out


def blocks_for(rung, noise):
    """Every sentence this rung's prompt must contain, from the block table itself."""
    fmt = prompts._fmt_dict("abstract", "GDIF", "ADIF", "6.87", 15, 4, 60, 15, 0.0, CV, FLOOR, 3)
    want = []
    for name in prompts._BLOCKS[rung]:
        if noise == "exact":
            name = {"baseline": "baseline_exact", "informed": "informed_exact",
                    "instructed": "instructed_exact"}.get(name, name)
        elif name == "informed":
            name = "informed_multiplicative"
        want.append(prompts._BLOCK_TEXT[name].format(**fmt))
    return want


class EveryPromptCarriesItsRung(unittest.TestCase):
    def setUp(self):
        self.R = rendered()

    def test_a_every_block_sentence_is_present_in_every_prompt_type(self):
        for (rung, noise, kind), txt in sorted(self.R.items()):
            for b in blocks_for(rung, noise):
                self.assertIn(b, txt, "%s/%s/%s is MISSING a block sentence: %r"
                              % (rung, noise, kind, b[:60]))

    def test_b_the_header_is_complete_in_every_prompt(self):
        for (rung, noise, kind), txt in sorted(self.R.items()):
            self.assertIn(HEADER_TAIL, txt,
                          "%s/%s/%s is TRUNCATED inside the header" % (rung, noise, kind))

    def test_c_nominations_differ_across_rungs_exactly_where_rounds_do(self):
        for noise in ("multiplicative", "exact"):
            rungs = list(prompts.RUNGS)
            for i in range(len(rungs)):
                for j in range(i + 1, len(rungs)):
                    a, b = rungs[i], rungs[j]
                    rounds_same = (self.R[(a, noise, "round")] == self.R[(b, noise, "round")])
                    noms_same = (self.R[(a, noise, "nomination")] == self.R[(b, noise, "nomination")])
                    self.assertEqual(rounds_same, noms_same,
                                     "%s vs %s (%s): round prompts %s but nominations %s"
                                     % (a, b, noise, "match" if rounds_same else "differ",
                                        "match" if noms_same else "differ"))

    def test_d_the_snapshot_matches(self):
        cur = {"%s|%s|%s" % k: hashlib.sha256(v.encode()).hexdigest() for k, v in self.R.items()}
        if not os.path.exists(SNAP):
            self.fail("no snapshot at %s; run scripts/snapshot_prompts.py" % SNAP)
        old = {}
        for line in io.open(SNAP, encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                h, k = line.split(None, 1)
                old[k.strip()] = h
        added = sorted(set(cur) - set(old))
        removed = sorted(set(old) - set(cur))
        changed = sorted(k for k in set(cur) & set(old) if cur[k] != old[k])
        self.assertEqual((added, removed, changed), ([], [], []),
                         "PROMPTS CHANGED. added=%s removed=%s changed=%s\n"
                         "If deliberate, run scripts/snapshot_prompts.py and show the diff."
                         % (added, removed, changed))

    def test_the_nomination_asks_for_an_answer(self):
        for (rung, noise, kind), txt in sorted(self.R.items()):
            if kind == "nomination":
                self.assertIn("ANSWER:", txt)
                self.assertIn("Your budget is spent", txt)



class TheStatedPerRoundCountIsWatched(unittest.TestCase):
    """The header states 4 orders per round in every prompt except the replacement ask, which states 1.

    `LLMPolicy.propose` passes its `n_slots` into `prompts.build`, so a replacement ask for one rejected slot
    reads "1 orders per round". This is the same in every condition, so it cannot bias a contrast, and it is
    kept unchanged so all campaigns stay comparable. A new occurrence in another prompt kind fails.
    """

    EXPECTED = 4
    ACCEPTED = {"replacement": 1}

    def test_every_prompt_states_four_orders_per_round_except_the_known_case(self):
        surprises = []
        for (rung, noise, kind), text in sorted(rendered().items()):
            m = re.search(r"(\d+) orders per round", text)
            self.assertIsNotNone(m, "%s|%s|%s states no per-round count at all" % (rung, noise, kind))
            got = int(m.group(1))
            want = self.ACCEPTED.get(kind, self.EXPECTED)
            if got != want:
                surprises.append("%s|%s|%s says %d, expected %d" % (rung, noise, kind, got, want))
        self.assertEqual(surprises, [],
                         "a prompt's stated per-round count changed:\n  " + "\n  ".join(surprises))

    def test_the_accepted_exception_is_exactly_the_replacement_kind(self):
        """The accepted exception is exactly the replacement kind."""
        self.assertEqual(set(self.ACCEPTED), {"replacement"})
        for (rung, noise, kind), text in rendered().items():
            got = int(re.search(r"(\d+) orders per round", text).group(1))
            if kind == "replacement":
                self.assertEqual(got, 1)
            else:
                self.assertEqual(got, 4, "%s|%s|%s is not a replacement and must say 4" % (rung, noise, kind))

    def test_the_total_budget_is_never_wrong(self):
        """Every prompt states the correct total budget of 60 measurements."""
        for (rung, noise, kind), text in rendered().items():
            self.assertIn("60 measurements in total", text,
                          "%s|%s|%s misstates the total budget" % (rung, noise, kind))


if __name__ == "__main__":
    unittest.main(verbosity=2)
