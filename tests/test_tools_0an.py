"""Tests for the three agent tools: the ledger, the menu and the repeat cap.

The ledger must hold the agent's own readings and nothing else. The menu must hold only candidates the agent
never ordered, on the landscape's own letters, ranked exactly as the prompt says. The cap must refuse an order
without spending a slot or a draw, tell the agent why, and count every slot it costs.
"""
import os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from repdef import campaign as C, llm, policies as P, prompts, tools          # noqa: E402

AT = "ABCDEFGHIJKLMNOPQRST"


class Ledger(unittest.TestCase):

    def test_it_is_the_agents_own_readings_in_order_of_first_reading(self):
        rows = [(1, "BBBB", "ok", 2.0), (1, "CCCC", "rejected", None), (1, "AAAA", "ok", 1.0),
                (2, "BBBB", "ok", 4.0), (2, "DDDD", "failed", None)]
        t = tools.ledger_text(rows).splitlines()
        self.assertEqual(t[0], "MEASURED CANDIDATES, computed from the history above")
        self.assertTrue(t[2].startswith("BBBB") and t[3].startswith("AAAA"))
        self.assertIn("2         3.000    1.000", t[2])
        self.assertIn("not estimable from 1 reading", t[3])
        self.assertEqual(len(t), 4, "rejected and failed orders have no reading and no row")
        self.assertIn("(no readings yet)", tools.ledger_text([]))


def independent_score(rows, s):
    r = tools.readings(rows)
    allv = [x for v in r.values() for x in v]
    m = sum(allv) / len(allv)
    tot = 0.0
    for i, c in enumerate(s):
        v = [x for seq, xs in r.items() if seq[i] == c for x in xs]
        tot += sum(v) / len(v) if v else m
    return tot


class Menu(unittest.TestCase):
    # A high reading (DDDC) and a low one (EEED) make some neighbours of the top three score above the rest, so the
    # ranking is not decided by the tie-break alone. The top three are computed, never typed.
    ROWS = [(1, "AAAA", "ok", 5.0), (1, "BAAA", "ok", 7.0), (1, "CAAA", "rejected", None),
            (2, "BAAA", "ok", 7.4), (2, "BBAA", "ok", 6.0), (2, "BCAA", "failed", None), (2, "ABAA", "capped", None),
            (3, "DDDC", "ok", 9.0), (3, "EEED", "ok", 2.0)]
    TOP3 = None                     # set below the class, from the readings

    def test_never_ordered_one_letter_from_a_top_three_and_on_the_landscape_letters(self):
        cands, ranked = tools.menu(self.ROWS, "AAAA", AT, 7, 3)
        self.assertTrue(ranked)
        self.assertEqual(len(cands), 10)
        ordered = {r[1] for r in self.ROWS}
        top3 = self.TOP3
        everything, _r = tools.menu(self.ROWS, "AAAA", AT, 7, 3, n=10_000)
        self.assertIn("BBAA", {x for t in self.TOP3 for x in tools._neighbours(t, AT)}, "an ordered neighbour exists")
        self.assertFalse(set(everything) & ordered, "no ordered candidate anywhere in the ranked pool")
        for s in cands:
            self.assertNotIn(s, ordered)
            self.assertTrue(set(s) <= set(AT))
            self.assertTrue(any(sum(a != b for a, b in zip(s, t)) == 1 for t in top3), s)

    def test_ranked_exactly_as_the_prompt_says(self):
        cands, _r = tools.menu(self.ROWS, "AAAA", AT, 7, 3)
        scores = [independent_score(self.ROWS, s) for s in cands]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertGreater(scores[0], scores[-1], "a ranking with every score equal ranks nothing")
        # Nothing outside the list beats the list's last entry.
        ordered = {r[1] for r in self.ROWS}
        pool = {s for t in self.TOP3 for s in tools._neighbours(t, AT)} - ordered
        self.assertLessEqual(max(independent_score(self.ROWS, s) for s in pool - set(cands)), scores[-1] + 1e-12)

    def test_with_no_readings_it_says_so_and_uses_the_reference_point(self):
        cands, ranked = tools.menu([], "GDIF", AT, 7, 1)
        self.assertFalse(ranked)
        self.assertTrue(all(sum(a != b for a, b in zip(s, "GDIF")) == 1 for s in cands))
        self.assertIn("in no particular order", tools.menu_text(cands, ranked))
        self.assertEqual(cands, tools.menu([], "GDIF", AT, 7, 1)[0], "deterministic")


def _top3(rows):
    m = {k: sum(v) / len(v) for k, v in tools.readings(rows).items()}
    return sorted(m, key=lambda k: -m[k])[:3]


Menu.TOP3 = _top3(Menu.ROWS)


class Insist(P.Policy):
    """Orders the same candidate in every slot, the strongest test of a repeat cap."""
    name = "insist"

    def __init__(self, seq, give_up_after=None):
        self.seq, self.n, self.give_up_after, self.excludes = seq, 0, give_up_after, []

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        self.excludes.append(set(exclude))
        if kind == "replacement" and self.give_up_after is not None:
            self.n += 1
            if self.n > self.give_up_after:
                return []
        return [self.seq] * n_slots

    def replication_slots(self, view):
        return None


def grid():
    import grid as G
    return G.landscape()


class RepeatCap(unittest.TestCase):

    def run_insist(self, cap, give_up_after=None):
        fit, pool = grid()
        seq = sorted(pool)[0]
        pol = Insist(seq, give_up_after)
        r = C.run(fit, pool, pol, 0.0, 424242, 0.0, rounds=3, slots_per_round=4, nomination="mean",
                  noise_model="multiplicative", cv=0.073, noise_floor=0.0035, repeat_cap=cap)
        return r, pol, seq

    def test_a_third_order_is_refused_without_a_slot_or_a_draw_and_counted(self):
        r, pol, seq = self.run_insist(1)
        orders = [h for h in r.history if h.seq == seq and h.outcome in ("ok", "failed")]
        self.assertEqual(len(orders), 2, "at most twice")
        self.assertGreater(r.n_capped, 0)
        self.assertFalse(any(h.outcome == "capped" for h in r.history),
                         "0an.1: a refused order leaves no history line; it is counted in n_capped")
        self.assertGreater(r.repeat_cap_hits, 0, "an agent that insists past the bound loses the slot, counted")
        self.assertEqual(r.slots_used, 12)
        self.assertTrue(any(seq in e for e in pol.excludes), "the replacement ask is told what it may not order")

    def test_a_slot_the_cap_lost_says_so_truthfully(self):
        # A slot the cap loses is reported as cap-lost, never as lost to non-viable replacements. Both ways the
        # cap loses a slot are covered: the bound of 20 refusals, and a replacement ask that yields nothing.
        for give_up in (None, 1):
            r, _p, seq = self.run_insist(1, give_up_after=give_up)
            lost = [h for h in r.history if h.outcome in ("abandoned", "cap_lost")]
            self.assertTrue(lost)
            self.assertTrue(all(h.outcome == "cap_lost" for h in lost), "a slot the cap touched is never 'abandoned'")
            text = prompts._history([(h.round, h.seq, h.outcome, h.observed) for h in r.history])
            self.assertIn(prompts.CAP_LOST_LINE, text)
            self.assertNotIn("also non-viable", text)
            agg = prompts._history([(h.round, h.seq, h.outcome, h.observed) for h in r.history], aggregated=True)
            self.assertNotIn("also non-viable", agg)

    def test_with_the_cap_off_a_lost_slot_is_never_cap_lost(self):
        fit, pool = grid()
        dead = next(s for s in sorted(fit) if s not in pool)
        r = C.run(fit, pool, Insist(dead), 0.0, 424242, 0.0, rounds=2, slots_per_round=4, nomination="mean",
                  noise_model="multiplicative", cv=0.073, noise_floor=0.0035, repeat_cap=None)
        self.assertTrue(any(h.outcome == "abandoned" for h in r.history))
        self.assertFalse(any(h.outcome == "cap_lost" for h in r.history))

    def test_without_a_cap_nothing_changes(self):
        r, _p, seq = self.run_insist(None)
        self.assertEqual(r.n_capped, 0)
        self.assertEqual(sum(1 for h in r.history if h.seq == seq), 12)


class Prompts(unittest.TestCase):
    KW = dict(parent="GDIF", example="ADIF", landscape="abstract", noise_model="multiplicative", cv=0.073,
              noise_floor=0.0035, anchor_reading="6.87")

    def test_the_cap_is_stated_in_every_prompt_kind(self):
        line = "- Each candidate can be ordered at most twice. A further order of it is rejected at no cost"
        self.assertIn(line, prompts.build("blind", [], 1, 15, 4, 60, 0.0, repeat_cap=1, **self.KW))
        self.assertIn(line, prompts.build("blind", [], 1, 15, 1, 60, 0.0, repeat_cap=1, **self.KW))
        self.assertIn(line, prompts.build_nomination("blind", [], 15, 4, 0.0, repeat_cap=1, **self.KW))
        self.assertNotIn("ordered at most", prompts.build("blind", [], 1, 15, 4, 60, 0.0, **self.KW))

    def test_a_refused_order_in_the_history_is_refused_by_name_in_both_views(self):
        # A refused order must never be shown as "rejected, not viable"; rendering it raises.
        for agg in (False, True):
            with self.assertRaises(ValueError):
                prompts._history([(2, "GDIF", "capped", None)], aggregated=agg)

    def test_the_at_limit_list_is_the_oracles_own_order_count(self):
        # The relationship that makes the list truthful: it names exactly what Oracle.orders_of says the cap
        # refuses, failed orders counted and rejected ones not.
        from repdef import oracle as O
        fit, pool = grid()
        viable, dead = sorted(pool)[:3], next(s for s in sorted(fit) if s not in pool)
        orc = O.Oracle(fit, pool, 0.0, 7, failure_rate=0.5, noise_model="multiplicative", cv=0.073,
                       noise_floor=0.0035)
        for rnd, seq in enumerate([viable[0], dead, viable[1], viable[0], dead, viable[1], viable[2], dead], 1):
            orc.measure(seq, rnd)
            rows = [(h.round, h.seq, h.outcome, h.observed) for h in orc.history]
            self.assertEqual(tools.at_limit(rows, 1),
                             sorted(s for s in set(viable) | {dead} if orc.orders_of(s) >= 2))
        self.assertIn("failed", {h.outcome for h in orc.history}, "the check must see a failed order")
        self.assertEqual(tools.at_limit_text([], "candidate"), None)


def stub(prompt, model, **kw):
    if "ANSWER: XXXX" in prompt:
        return llm.Call(text="ANSWER: GDIF\nREASON: x", model=model)
    n = int(re.search(r"Reply with exactly (\d+) lines", prompt).group(1))
    return llm.Call(text="\n".join("GDIF | the reference" for _ in range(n)), model=model)


class EndToEnd(unittest.TestCase):

    def setUp(self):
        self._real = llm.complete
        self.addCleanup(lambda: setattr(llm, "complete", self._real))
        llm.complete = stub

    def run_arm(self, **opts):
        import grid as G
        fit, pool = G.landscape()
        own = []
        row = G.one_campaign(fit, pool, tuple(sorted(pool)), (7.0, 0.1), "vendor/stub", "blind", 300000, own, 6000, 3,
                             prompt_options=dict(truthful_reask=True, **opts))
        return row, own

    def test_each_arm_reaches_the_prompt_and_the_row(self):
        row, calls = self.run_arm(ledger=True)
        later = calls[5]["prompt"]
        self.assertIn("MEASURED CANDIDATES, computed from the history above", later)
        self.assertLess(later.index("HISTORY"), later.index("MEASURED CANDIDATES"))
        self.assertNotIn("SUGGESTED NEW CANDIDATES", later)
        row, calls = self.run_arm(menu=True)
        self.assertIn("SUGGESTED NEW CANDIDATES", calls[5]["prompt"])
        self.assertIn("You may ignore this list.", calls[0]["prompt"])
        row, calls = self.run_arm(repeat_cap=True)
        self.assertGreater(row["n_capped"], 0)
        self.assertTrue(row["prompt_options"]["repeat_cap"])
        caps = [c for c in calls if "cannot be ordered again: GDIF" in c["prompt"]]
        self.assertTrue(caps, "a capped order is named as capped in the replacement ask")
        self.assertFalse(any("rejected as non-viable and must not be proposed again this round: GDIF" in c["prompt"]
                             for c in calls), "a capped candidate must never be called non-viable")
        self.assertFalse(any("not ordered: already ordered" in c["prompt"] for c in calls),
                         "0an.1: a refused order leaves no history line")
        block = "AT THE LIMIT\nThese candidates have been ordered the maximum number of times and cannot be ordered again: GDIF."
        rounds = [c["prompt"] for c in calls if "Reply with exactly 4 lines" in c["prompt"]]
        self.assertNotIn("AT THE LIMIT", rounds[0], "nothing is at the limit in round 1")
        self.assertTrue(any(block in p for p in rounds), "a round prompt lists the candidates at the limit")
        self.assertTrue(all(block in c["prompt"] for c in caps), "so does every replacement ask after a refusal")
        self.assertLess(rounds[-1].index("HISTORY"), rounds[-1].index("AT THE LIMIT"))
        self.assertGreater(row["slots_cap_lost"], 0)
        self.assertEqual(row["lost_slots"], row["slots_abandoned"] + row["rounds_lost_slots"] + row["slots_cap_lost"])
        self.assertFalse(any(re.search(r"GDIF\s+SLOT LOST: every replacement for this slot was also non-viable",
                                       c["prompt"]) for c in calls), "the viable GDIF is never called non-viable")
        row, calls = self.run_arm()
        self.assertNotIn("MEASURED CANDIDATES", calls[5]["prompt"])
        self.assertEqual(row["n_capped"], 0)


if __name__ == "__main__":
    unittest.main()
