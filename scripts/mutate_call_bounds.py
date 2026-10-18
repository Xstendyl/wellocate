#!/usr/bin/env python3
"""Mutation test for tests/test_the_call_is_bounded_and_attributed.py: reintroduce each fault and check the test fails.

The first mutation sends the provider field unconditionally, which would change which provider answers.
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import mutate

TARGET = os.path.join(ROOT, "repdef", "llm.py")
TEST = ["discover", "-s", "tests", "-p", "test_the_call_is_bounded_and_attributed.py"]

MUTANTS = [
    ("sends the provider field always, changing the request",
     "    if provider_order:\n        payload_in[\"provider\"] = {\"order\": list(provider_order), \"allow_fallbacks\": False}",
     "    payload_in[\"provider\"] = {\"order\": list(provider_order or []), \"allow_fallbacks\": False}"),
    ("allows provider fallbacks, so a pinned model is still a mixture",
     '"allow_fallbacks": False}', '"allow_fallbacks": True}'),
    ("drops the total deadline, the forty-minute silence",
     "        if deadline_s and (t0 - started) >= deadline_s:",
     "        if False:"),
    ("hands the last attempt the full socket timeout, past the deadline",
     "        attempt_timeout = timeout if not deadline_s else max(1, min(timeout,\n"
     "                                                                   int(deadline_s - (t0 - started))))",
     "        attempt_timeout = timeout"),
    ("stops recording which provider answered",
     '                        provider=str(payload.get("provider") or ""),\n                        latency_ms=ms, raw=payload)',
     '                        latency_ms=ms, raw=payload)'),
    ("records the provider only on success, not on the empty-text return",
     '                                provider=str(payload.get("provider") or ""),\n                                error="empty content after %d completion tokens "',
     '                                error="empty content after %d completion tokens "'),
    ("shortens a healthy call by applying the deadline as the timeout",
     "        attempt_timeout = timeout if not deadline_s else max(1, min(timeout,\n"
     "                                                                   int(deadline_s - (t0 - started))))",
     "        attempt_timeout = 1"),
]


def main():
    green, log = mutate.baseline(TEST)
    print("BASELINE green=%s" % green)
    if not green:
        print(log)
        sys.exit("baseline is not green")
    rows = []
    for label, old, new in MUTANTS:
        v = mutate.check(TARGET, old, new, TEST, imports="from repdef import llm",
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
