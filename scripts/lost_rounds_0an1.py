#!/usr/bin/env python3
"""Classify what is in a reply that lost its round under the re-test limit.

For every round call whose parse failed, each line of the logged reply is classed:
  pipe line naming a candidate at the limit (from the prompt's own block)
  pipe line naming a candidate already in the history (measured, failed or rejected)
  pipe line naming a new candidate
  a line without the pipe format (prose, headings such as "Final 4:")
The logged reply is the last attempt's, since the policy keeps one raw_response per call. Base rates of lost
rounds are given for the same model in the earlier limit run, that run's other arms, and the grid.

Usage: python3 scripts/lost_rounds_0an1.py [tag]      (writes results/lost_rounds_<tag>.json)
"""
import collections, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_0al as A0                                                # noqa: E402

PIPE = re.compile(r"^\s*([A-Za-z]{4})\s*\|")
ROW = re.compile(r"^\s*\d+\s+([A-Z]{4})\s+")
BLOCK = "cannot be ordered again: "


def classify(c):
    p = c["prompt"]
    limit = set(p.split("AT THE LIMIT", 1)[1].split(BLOCK, 1)[1].split(".", 1)[0].split(", ")) \
        if "AT THE LIMIT" in p else set()
    hist = {m.group(1) for line in p.split("HISTORY", 1)[1].split("Choose", 1)[0].splitlines()
            for m in [ROW.match(line)] if m}
    out = collections.Counter()
    for line in (c.get("raw_response") or "").splitlines():
        if not line.strip():
            continue
        m = PIPE.match(line)
        if not m:
            out["prose"] += 1
        elif m.group(1).upper() in limit:
            out["pipe: at the limit"] += 1
        elif m.group(1).upper() in hist:
            out["pipe: in the history"] += 1
        else:
            out["pipe: new"] += 1
    return out, sorted(limit)


def lost_rounds(tag):
    per = collections.defaultdict(lambda: collections.Counter())
    for c in A0.calls(tag):
        if c.get("kind") == "nomination":
            continue
        k = "round" if c.get("n_slots") == c.get("slots_per_round") else "replacement"
        per[(c["model"].split("/")[-1], k)]["calls"] += 1
        if c.get("parse_status") != "ok" and not c.get("parsed"):
            per[(c["model"].split("/")[-1], k)]["lost"] += 1
    return per


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "smoke0an1_f3_cap"
    rows = []
    for c in A0.calls(tag):
        if c.get("kind") == "nomination" or c.get("parse_status") == "ok" or c.get("parsed"):
            continue
        cls, limit = classify(c)
        rows.append(dict(model=c["model"].split("/")[-1], seed=c["campaign_seed"], round=c["round"],
                         n_slots=c["n_slots"], status=c["parse_status"], attempts=c["parse_attempts"],
                         at_limit=limit, lines=dict(cls)))
        print("%-18s seed %d round %2d slots %d %-26s at limit %s | %s"
              % (rows[-1]["model"], c["campaign_seed"], c["round"], c["n_slots"], c["parse_status"], limit, dict(cls)))
    base = {}
    for t in (tag, "smoke0an_f3_cap", "smoke0an_f1_ledger", "smoke0an_f2_menu", "smoke0an_f0_control"):
        base[t] = {"%s|%s" % k: dict(v) for k, v in lost_rounds(t).items()}
        print("%-22s %s" % (t, {k: "%d lost of %d" % (v.get("lost", 0), v["calls"]) for k, v in base[t].items()}))
    json.dump(dict(lost=rows, base=base), open(os.path.join(ROOT, "results", "lost_rounds_%s.json" % tag), "w"),
              indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
