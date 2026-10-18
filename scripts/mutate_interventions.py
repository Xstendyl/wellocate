#!/usr/bin/env python3
"""Mutation battery for the two interventions, run through the canary-guarded harness.

Every entry carries a canary: an expression evaluated in a fresh interpreter whose value proves the
mutant is the code under test.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from repdef import mutate

P = os.path.join(mutate.REPO, "repdef", "prompts.py")
SUITE = ["tests.test_interventions_are_clean"]
B = "prompts.build(%r,[(1,'VDGV','ok',1.0),(1,'VDGV','ok',1.2),(2,'ADGV','failed',None)],2,15,4,56,0.42%s)"

MUTANTS = [
 ("abstract keeps the biological metric",
  'metric="score", item="string"', 'metric="binding activity", item="string"',
  "prompts.LANDSCAPES['abstract']['metric']", "binding activity"),
 ("abstract keeps the amino-acid alphabet",
  'alphabet="ABCDEFGHIJKLMNOPQRST"', 'alphabet="ACDEFGHIKLMNPQRSTVWY"',
  "prompts.LANDSCAPES['abstract']['alphabet']", "ACDEFGHIKLMNPQRSTVWY"),
 ("abstract keeps the word variant",
  'metric="score", item="string"', 'metric="score", item="variant"',
  "prompts.LANDSCAPES['abstract']['item']", "variant"),
 ("abstract keeps a protein parent",
  'parent="AAAA", example="BAAA"', 'parent="VDGV", example="ADGV"',
  "prompts.LANDSCAPES['abstract']['parent']", "VDGV"),
 ("aggregated ordered by mean, which recommends the leader",
  '    out = ["candidate  n  mean     standard error of the mean"]',
  '    order = sorted(order, key=lambda q: -(sum(readings[q])/len(readings[q]) if readings[q] else -1e9))\n'
  '    out = ["candidate  n  mean     standard error of the mean"]',
  "prompts._history_aggregated([(1,'A','ok',1.0),(1,'B','ok',9.0)]).splitlines()[1].split()[0]", "B"),
 ("aggregated invents SE=0 from one measurement",
  '            se = "not estimable from 1 measurement"', '            se = "0.000"',
  "'0.000' in prompts._history_aggregated([(1,'A','ok',1.0)])", True),
 ("aggregated uses population sd, the flattering convention",
  '            var = sum((x - mean) ** 2 for x in v) / (n - 1)',
  '            var = sum((x - mean) ** 2 for x in v) / n',
  "prompts._history_aggregated([(1,'A','ok',1.0),(1,'A','ok',2.0)]).splitlines()[1].split()[-1]", "0.354"),
 ("aggregated reports sd where it says standard error",
  '            se = "%.3f" % ((var / n) ** 0.5)', '            se = "%.3f" % (var ** 0.5)',
  "prompts._history_aggregated([(1,'A','ok',1.0),(1,'A','ok',2.0)]).splitlines()[1].split()[-1]", "0.707"),
 ("decision rule names the failure mode",
  '  AVERAGE reading across all of its measurements."""',
  '  AVERAGE reading, not the single highest reading."""',
  "'single highest' in prompts.DECISION_RULE_BLOCK", True),
 ("decision rule leaks into the instructed rung",
  '    "instructed":    ("baseline", "informed", "instructed"),',
  '    "instructed":    ("baseline", "informed", "instructed", "decision_rule"),',
  "'AVERAGE' in " + (B % ("instructed", "")), True),
 ("aggregated gains wording of its own",
  '    "aggregated":    ("baseline", "informed", "instructed"),',
  '    "aggregated":    ("baseline", "informed", "instructed", "decision_rule"),',
  "'AVERAGE' in " + (B % ("aggregated", "")), True),
 ("aggregation dropped at the nomination, the one moment that matters",
  '                                            aggregated=(rung in AGGREGATED_RUNGS), sigma=sigma))',
  '                                            aggregated=False, sigma=sigma))',
  "'standard error of the mean' in prompts.build_nomination('aggregated',[(1,'A','ok',1.0)],15,4,0.42)", False),
 ("blind regains the measurement-error line",
  '    "blind":         (),', '    "blind":         ("baseline",),',
  "'measurement error' in " + (B % ("blind", "")), True),
 ("forced diverges from blind",
  '    "forced":        (),', '    "forced":        ("baseline",),',
  (B % ("forced", "")) + " == " + (B % ("blind", "")), False),
 ("instructed loses its sigma",
  '    "instructed":    ("baseline", "informed", "instructed"),',
  '    "instructed":    ("baseline", "instructed"),',
  "'sigma' in " + (B % ("instructed", "")), False),
 ("aggregated hides further failed orders",
  '            extra = "   (%d further order(s) failed)" % fails[seq]', '            extra = ""',
  "'failed' in prompts._history_aggregated([(1,'A','ok',1.0),(2,'A','failed',None)])", False),
 ("aggregated hides rejections",
  '            note = ("all %d orders failed" % fails[seq]) if fails[seq] else "rejected, not viable"',
  '            note = ""',
  "'not viable' in prompts._history_aggregated([(1,'A','rejected',None)])", False),
 ("an unknown landscape silently defaults to GB1",
  '        raise ValueError("unknown landscape %r; known: %s"\n'
  '                         % (landscape, ", ".join(sorted(LANDSCAPES))))',
  '        landscape = "gb1_bio"',
  "prompts.terms('does_not_exist')['metric']", "binding activity"),
 ("an unknown substitution is silently ignored",
  '            raise ValueError("unknown substitution %r for landscape %r" % (k, landscape))',
  '            continue',
  "prompts.terms('gb1_bio', solvent='water')['metric']", "binding activity"),
 ("every rung is silently aggregated",
  'AGGREGATED_RUNGS = ("aggregated",)', 'AGGREGATED_RUNGS = RUNGS',
  "'standard error of the mean' in " + (B % ("blind", "")), True),
 ("an unknown rung silently becomes blind",
  '        raise ValueError("unknown rung %r; known: %s" % (rung, ", ".join(RUNGS)))',
  '        rung = "blind"',
  "'measurement error' in " + (B % ("not_a_rung", "")), False),
]


def main():
    ok, out = mutate.baseline(SUITE)
    print("baseline green: %s" % ok)
    if not ok:
        print(out[-3000:]); return 1
    print("%d mutants, each canary-verified before its verdict is believed\n" % len(MUTANTS))
    missed, stale = [], []
    for label, old, new, canary, expect in MUTANTS:
        try:
            v = mutate.check(P, old, new, SUITE, canary=canary, expect=expect, label=label)
        except mutate.StaleMutant as e:
            stale.append(label); print("STALE   %s\n        %s" % (label, e)); continue
        except ValueError as e:
            stale.append(label); print("ANCHOR  %s\n        %s" % (label, e)); continue
        if v == "MISSED":
            missed.append(label)
        print("%-7s %s" % (v, label))
    print("\n%d caught, %d missed, %d refused (stale or drifted anchor), of %d"
          % (len(MUTANTS) - len(missed) - len(stale), len(missed), len(stale), len(MUTANTS)))
    for m in missed:
        print("  MISSED: %s" % m)
    for m in stale:
        print("  REFUSED: %s" % m)
    ok2, _ = mutate.baseline(SUITE)
    print("restored green: %s" % ok2)
    return 0 if not missed and not stale and ok2 else 1


if __name__ == "__main__":
    sys.exit(main())
