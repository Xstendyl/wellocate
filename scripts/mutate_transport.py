#!/usr/bin/env python3
"""Mutation test for tests/test_a_transport_failure_is_not_the_agents_fault.py.

Mutant 1 returns an empty proposal list on a transport error, so campaign.py would charge the agent a
forfeited round. The test must fail on it.
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import mutate

TARGET = os.path.join(ROOT, "repdef", "llm_policy.py")
TEST = ["discover", "-s", "tests", "-p", "test_a_transport_failure_is_not_the_agents_fault.py"]

MUTANTS = [
    ("THE ORIGINAL BUG: an empty list on a transport error",
     '''            if not call.ok:
                # THE CALL DID NOT HAPPEN. Previously this became an empty proposal list, which
                # campaign.py charged as a forfeited round. Abandon the campaign instead.
                _raise_transport(self.model, call.error, "round")
            got, status, notes = parse(call.text, n_slots, alphabet=self.alphabet)
            if status == "ok":
                break''',
     '''            got, status, notes = (parse(call.text, n_slots, alphabet=self.alphabet) if call.ok
                                  else ([], "transport_error", [call.error or ""]))
            if status == "ok" or status == "transport_error":
                break'''),
    ("a 402 is treated as an ordinary transport failure, so the run does not halt",
     '    if "402" in str(error):\n        raise CreditsExhausted(model, error, kind)',
     '    if False:\n        raise CreditsExhausted(model, error, kind)'),
    ("the nomination call keeps returning a campaign after a failed outcome call",
     '''        if not call.ok:
            # The nomination call IS the primary outcome. A campaign whose outcome was never measured
            # cannot be written, whatever happened in its rounds.
            _raise_transport(self.model, call.error, "nomination")''',
     '''        if False:
            _raise_transport(self.model, call.error, "nomination")'''),
    ("a PARSE failure is raised too, which would discard real measurements",
     '            got, status, notes = parse(call.text, n_slots, alphabet=self.alphabet)',
     '            got, status, notes = parse(call.text, n_slots, alphabet=self.alphabet)\n'
     '            _raise_transport(self.model, "parse", "round")'),
    ("the failure no longer names the call kind",
     '        self.model, self.error, self.kind = model, error, kind',
     '        self.model, self.error, self.kind = model, error, "unknown"'),
]


def main():
    green, log = mutate.baseline(TEST)
    print("BASELINE green=%s" % green)
    if not green:
        print(log)
        sys.exit("baseline is not green")
    rows = []
    for label, old, new in MUTANTS:
        v = mutate.check(TARGET, old, new, TEST, imports="from repdef import llm_policy",
                         label=label, timeout=300)
        rows.append((label, v))
        print("  %-58s %s" % (label[:58], v))
    missed = [l for l, v in rows if v != "CAUGHT"]
    print("\nCAUGHT %d/%d" % (len(rows) - len(missed), len(rows)))
    for l in missed:
        print("  MISSED: %s" % l)
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
