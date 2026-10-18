#!/usr/bin/env python3
"""Mutation tests for the core simulation modules, run through the shared harness in repdef/mutate.py.

The harness snapshots each mutated file, refuses on concurrent edits, purges the bytecode cache, requires a canary
that observes the mutation, and records a hang as its own outcome.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import mutate

R = mutate.REPO
POL = os.path.join(R, "repdef", "policies.py")
ORC = os.path.join(R, "repdef", "oracle.py")
CAM = os.path.join(R, "repdef", "campaign.py")
VIE = os.path.join(R, "repdef", "view.py")
PIPE = ["tests.test_pipeline"]

# (label, file, old, new, suite, canary, expect, imports, timeout, extra_edits)
MUTANTS = [
 ("drop the campaign seed from exploration keys (the bug that was found)", POL,
  'cand, min(need, len(cand)), "expl", self.seed, view.campaign_seed,\n            view.current_round, champ)',
  'cand, min(need, len(cand)), "expl", self.seed,\n            view.current_round, champ)',
  # The class mentions view.campaign_seed twice (exploration key and cold start); the mutant removes one.
  PIPE, "__import__('inspect').getsource(policies.GreedyWithReplication).count('view.campaign_seed')",
  2, "from repdef import policies", 120, ()),
 ("drop the campaign seed from the cold start", POL,
  '"cold", seed, view.campaign_seed, view.current_round)',
  '"cold", seed, view.current_round)',
  PIPE, "'\"cold\", seed, view.campaign_seed' in __import__('inspect').getsource(policies)",
  False, "from repdef import policies", 120, ()),
 ("make a rejection consume a slot", ORC,
  'rec = Record(rnd, seq, REJECTED, None, true, None, False)',
  'rec = Record(rnd, seq, REJECTED, None, true, None, True)',
  PIPE, "'REJECTED, None, true, None, True' in __import__('inspect').getsource(oracle)",
  True, "from repdef import oracle", 120, ()),
 ("leak `true` into the Observation the policy sees", VIE,
  'Observation = collections.namedtuple("Observation", "round seq outcome observed")',
  'Observation = collections.namedtuple("Observation", "round seq outcome observed true")',
  ["tests.test_view_leak"], "'true' in view.Observation._fields", True, "from repdef import view",
  120,
  ((os.path.join(R, "repdef", "view.py"),
    "Observation(r.round, r.seq, r.outcome, r.observed)",
    "Observation(r.round, r.seq, r.outcome, r.observed, r.true)"),)),
 ("remove the re-ask cap", CAM,
  '                if tries > reask_cap:', '                if tries > 10 ** 6:',
  PIPE, "'tries > 10 ** 6' in __import__('inspect').getsource(campaign)", True,
  "from repdef import campaign", 45, ()),
 # Removing the slot-budget break would be an equivalent mutant (the break is unreachable when
 # rounds*slots_per_round == slots_total), so this mutant overspends instead.
 ("let the campaign overspend its slot budget", CAM,
  '            budget = min(slots_per_round, slots_total - orc.slots_used)',
  '            budget = slots_per_round + 1',
  PIPE, "'budget = slots_per_round + 1' in __import__('inspect').getsource(campaign.run)", True,
  "from repdef import campaign", 45, ()),
 ("silently fall back to the mean when shrinkage gets an unusable sigma", CAM,
  '''    if scalar and sigma <= 0.0:
        raise UnusableSigma(''',
  '''    if scalar and sigma <= 0.0:
        return view.best_by_mean()
    if False:
        raise UnusableSigma(''',
  ["tests.test_shrinkage_actually_runs"],
  "'return view.best_by_mean()' in __import__('inspect').getsource(campaign._shrinkage_nominate)",
  True, "from repdef import campaign", 120, ()),
 ("pass the scalar sigma to shrinkage under multiplicative noise", CAM,
  '            nom = _shrinkage_nominate(final, _nom_sigma, pm, pv)',
  '            nom = _shrinkage_nominate(final, sigma, pm, pv)',
  ["tests.test_shrinkage_actually_runs"],
  "'_shrinkage_nominate(final, sigma, pm, pv)' in __import__('inspect').getsource(campaign.run)",
  True, "from repdef import campaign", 120, ()),
]


def main():
    suites = sorted({tuple(m[4]) for m in MUTANTS})
    for su in suites:
        ok, out = mutate.baseline(list(su))
        print("baseline %-34s %s" % (" ".join(su), "green" if ok else "RED"))
        if not ok:
            print(out[-2500:]); return 1
    print()
    missed, refused = [], []
    for (label, path, old, new, suite, canary, expect, imports, timeout, extra) in MUTANTS:
        try:
            v = mutate.check(path, old, new, suite, canary=canary, expect=expect,
                             imports=imports, label=label, timeout=timeout, extra_edits=extra)
        except mutate.StaleMutant as e:
            refused.append(label); print("STALE    %s\n         %s" % (label, e)); continue
        except mutate.ConcurrentEdit as e:
            print("ABORTING: %s" % e); return 2
        except ValueError as e:
            refused.append(label + " [anchor drifted]")
            print("ANCHOR   %s\n         %s" % (label, e)); continue
        if v == "MISSED":
            missed.append(label)
        print("%-12s %s" % (v, label))
    print("\n%d caught, %d missed, %d refused, of %d"
          % (len(MUTANTS) - len(missed) - len(refused), len(missed), len(refused), len(MUTANTS)))
    for m in missed:
        print("  MISSED:  %s" % m)
    for m in refused:
        print("  REFUSED: %s   (a drifted anchor is NOT a pass: that coverage is gone)" % m)
    return 0 if not missed and not refused else 1


if __name__ == "__main__":
    sys.exit(main())
