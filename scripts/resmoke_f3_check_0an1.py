#!/usr/bin/env python3
"""Check the capped-order arm's rerun from its own call log.

  1. No prompt carries a refused-order history line.
  2. Every round and replacement prompt's AT THE LIMIT list equals the candidates its own HISTORY shows with two
     slot-using orders (a reading or a failed order), and the block is absent when that set is empty.
  3. Calls per campaign by kind, and prompt tokens per call, against the arm's first run.

Usage: python3 scripts/resmoke_f3_check_0an1.py      (writes results/resmoke_f3_check_0an1.json)
"""
import collections, json, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_0al as A0                                                # noqa: E402

ROW = re.compile(r"^\s*\d+\s+([A-Z]{4})\s+(.*)$")
BLOCK = "AT THE LIMIT\nThese candidates have been ordered the maximum number of times and cannot be ordered again: "


def kind(c):
    if c.get("kind") == "nomination":
        return "nomination"
    return "round" if c.get("n_slots") == c.get("slots_per_round") else "replacement"


def at_limit_from_history(prompt):
    hist = prompt.split("HISTORY", 1)[1]
    n = collections.Counter()
    for line in hist.splitlines():
        m = ROW.match(line)
        if m and (re.match(r"^-?\d+\.\d+$", m.group(2).strip()) or m.group(2).startswith("order failed")):
            n[m.group(1)] += 1
    return sorted(s for s, k in n.items() if k >= 2)


def stats(tag):
    per = collections.defaultdict(collections.Counter)
    tok = collections.defaultdict(list)
    faults = []
    for c in A0.calls(tag):
        m = c["model"].split("/")[-1]
        per[(m, c["campaign_seed"])][kind(c)] += 1
        tok[m].append(c.get("prompt_tokens") or 0)
        p = c.get("prompt") or ""
        if "not ordered: already ordered" in p:
            faults.append((m, c["campaign_seed"], c.get("round"), "a refused-order history line"))
        if kind(c) == "nomination" or tag.startswith("smoke0an_"):
            continue
        want = at_limit_from_history(p)
        got = p.split(BLOCK, 1)[1].split(".", 1)[0].split(", ") if BLOCK in p else []
        if got != want:
            faults.append((m, c["campaign_seed"], c.get("round"), "AT THE LIMIT %s, history says %s" % (got, want)))
    return per, tok, faults


def main():
    out = {}
    for tag in ("smoke0an_f3_cap", "smoke0an1_f3_cap"):
        per, tok, faults = stats(tag)
        out[tag] = dict(calls={"%s|%s" % k: dict(v) for k, v in per.items()},
                        prompt_tokens={m: dict(mean=st.mean(v), max=max(v)) for m, v in tok.items()},
                        faults=faults)
        print(tag)
        for k, v in sorted(per.items()):
            print("   %-22s seed %d  %s" % (k[0], k[1], dict(v)))
        for m, v in tok.items():
            print("   %-22s prompt tokens per call: mean %.0f, max %d" % (m, st.mean(v), max(v)))
        print("   faults: %d%s" % (len(faults), "".join("\n      %s" % (f,) for f in faults[:10])))
    json.dump(out, open(os.path.join(ROOT, "results", "resmoke_f3_check_0an1.json"), "w"), indent=1)
    return 1 if out["smoke0an1_f3_cap"]["faults"] else 0


if __name__ == "__main__":
    sys.exit(main())
