#!/usr/bin/env python3
"""What does an agent say when it names a candidate already at the order limit?

For every round and replacement call in a tag, each accepted proposal is checked against the prompt's own
AT THE LIMIT list or, when the prompt has none, against the candidates with two slot-using orders in its
history. A proposal at the limit is an "echo" when its reason restates the refusal (it says the candidate is at
the maximum, cannot be ordered again, or asks for a different choice), and a "push" otherwise. Also listed:
every genuine parser disagreement, with the reply.

Usage: python3 scripts/capped_replies_0an1.py [tag]      (writes results/capped_replies_<tag>.json)
"""
import collections, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_0al as A0                                                # noqa: E402
import resmoke_f3_check_0an1 as R                                       # noqa: E402

ECHO = re.compile(r"maximum|cannot be ordered|already been ordered|choose a different|at the limit|"
                  r"been ordered the max", re.I)


def at_limit(prompt):
    if "AT THE LIMIT" in prompt:
        return set(prompt.split(R.BLOCK, 1)[1].split(".", 1)[0].split(", "))
    return set(R.at_limit_from_history(prompt))


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "smoke0an1_f3_cap"
    n = collections.defaultdict(collections.Counter)
    examples, disagreements = {}, []
    for c in A0.calls(tag):
        if c.get("kind") == "nomination":
            continue
        m = c["model"].split("/")[-1]
        lim = at_limit(c["prompt"])
        reasons = dict(re.findall(r"^\s*([A-Z]{4})\s*\|\s*(.*)$", c.get("raw_response") or "", re.M))
        for s in c.get("parsed") or []:
            if s in lim:
                kind = "echo" if ECHO.search(reasons.get(s, "")) else "push"
                n[m][kind] += 1
                examples.setdefault((m, kind), "%s | %s" % (s, reasons.get(s, "")))
        if c.get("parsers_agree") is False and c.get("parsed"):
            disagreements.append(dict(model=m, seed=c["campaign_seed"], round=c["round"], n_slots=c["n_slots"],
                                      primary=c.get("parsed"), secondary=c.get("parsed_secondary"),
                                      reply=c.get("raw_response")))
    out = dict(counts={m: dict(v) for m, v in n.items()},
               examples={"%s|%s" % k: v for k, v in examples.items()}, disagreements=disagreements)
    json.dump(out, open(os.path.join(ROOT, "results", "capped_replies_%s.json" % tag), "w"), indent=1)
    for m, v in sorted(n.items()):
        print("%-20s at-limit proposals %4d: echo %4d, push %4d" % (m, sum(v.values()), v["echo"], v["push"]))
    for k, v in sorted(examples.items()):
        print("   e.g. %-28s %s" % ("%s %s:" % k, v[:150]))
    for d in disagreements:
        print("DISAGREEMENT %s seed %d round %d slots %d primary %s secondary %s\n%s"
              % (d["model"], d["seed"], d["round"], d["n_slots"], d["primary"], d["secondary"], d["reply"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
