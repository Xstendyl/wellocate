#!/usr/bin/env python3
"""Check that the main grid run and each model's later extra-seed run sent the same prompt templates.

Every logged prompt is reduced to a template by replacing the history, round counter, slot and candidate
counts, and quoted candidate strings with placeholders. The set of templates per (condition, model, call kind)
must match between the two runs byte for byte.

Usage: python3 scripts/check_prompt_templates.py      (exit 1 on any difference)
"""
import collections, glob, gzip, hashlib, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPUP = {"anthropic/claude-opus-4.7": "topup_opus", "google/gemini-2.5-flash": "topup_gemini",
         "deepseek/deepseek-chat-v3.1": "topup_deepseek"}
RUNGS = ("blind", "informed", "instructed", "aggregated", "decision_rule")


def template(p):
    p = re.sub(r"HISTORY\n.*?(?=\n\n|\Z)", "HISTORY\n<history>", p, flags=re.S)
    p = re.sub(r"ROUND \d+ OF \d+\. You have \d+ measurements? remaining\.", "ROUND <r>. <remaining>.", p)
    p = re.sub(r"\b\d+ (such lines?|candidates?|lines?|replacements?|slots?)\b", r"<n> \1", p)
    p = re.sub(r"\b[A-T]{4}\b", "<seq>", p)
    # The rejected list names one candidate or several, as the campaign went, so it is one placeholder.
    p = re.sub(r"(this round: )<seq>(?:, <seq>)*", r"\1<seq list>", p)
    # A re-ask appends the same notice once per attempt, so repeats of a paragraph collapse to one.
    paras, out = p.split("\n\n"), []
    for para in paras:
        if not out or para != out[-1]:
            out.append(para)
    # The re-ask notice appears only after a malformed reply; it is compared separately in `notices`.
    out = [x for x in out if not x.lstrip().startswith(REASK)]
    return "\n\n".join(out)


REASK = "Your previous reply did not contain exactly"


def notices(tag):
    """Every distinct re-ask notice paragraph the tag sent, after the same placeholders."""
    out = set()
    for g in sorted(glob.glob(os.path.join(ROOT, "results", "grid_%s_calls" % tag, "*.jsonl.gz"))):
        with gzip.open(g, "rt") as fh:
            for line in fh:
                if REASK in line:
                    p = json.loads(line)["prompt"]
                    for para in p.split("\n\n"):
                        if para.lstrip().startswith(REASK):
                            out.add(re.sub(r"\b\d+ (such lines?|candidates?)\b", r"<n> \1", para))
    return out


def templates(tag):
    out = collections.defaultdict(set)
    for g in sorted(glob.glob(os.path.join(ROOT, "results", "grid_%s_calls" % tag, "*.jsonl.gz"))):
        with gzip.open(g, "rt") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    out[(r["rung"], r["model"], r["kind"])].add(template(r["prompt"]))
    return out


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def main():
    s1 = templates("stage1")
    bad, rows = [], 0
    for model, tag in TOPUP.items():
        tu = templates(tag)
        for rung in RUNGS:
            kinds = sorted({k for (r_, m, k) in list(s1) + list(tu) if r_ == rung and m == model})
            for kind in kinds:
                a, b = s1.get((rung, model, kind), set()), tu.get((rung, model, kind), set())
                same = a == b
                rows += 1
                print("%-14s %-30s %-12s stage1 %d template(s) %-40s %-15s %d %s  %s"
                      % (rung, model, kind, len(a), ",".join(sorted(h(x) for x in a))[:40], tag, len(b),
                         ",".join(sorted(h(x) for x in b))[:40], "IDENTICAL" if same else "DIFFERS"))
                if not same:
                    bad.append((rung, model, kind, tag))
    ns1 = notices("stage1")
    for model, tag in TOPUP.items():
        nt = notices(tag)
        same = nt <= ns1 and bool(nt)
        print("re-ask notice  %-30s stage1 %d distinct, %s %d distinct: %s"
              % (model, len(ns1), tag, len(nt), "IDENTICAL TEXT" if same else "DIFFERS"))
        if not same:
            bad.append(("re-ask notice", model, "", tag))
    print("\n%d (condition, model, call kind) groups compared, plus the re-ask notice per model; %d differ"
          % (rows, len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
