#!/usr/bin/env python3
"""Does any prompt tell an agent a slot was lost to non-viable replacements when the cap lost it?

A genuine non-viable loss names a non-viable candidate, so the signature is a SLOT LOST line naming a candidate in
the grid's viable pool. Distinct (model, seed, round, candidate) instances are counted, since a line repeats in every
later prompt of its campaign. Campaign rows are checked for any sign of the cap.

Usage: python3 scripts/scan_false_slot_lost.py [tag ...]      (default: the control, ledger and menu panel, then the
repeat-cap pilot runs as controls; writes results/scan_false_slot_lost.json)
"""
import gzip, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import grid                                                             # noqa: E402

PANEL = ("gen_0an_f0_control", "gen_0an_f1_ledger", "gen_0an_f2_menu")
CONTROLS = ("smoke0an_f3_cap", "smoke0an1_f3_cap")
LINE = re.compile(r"^\s*(\d+)\s+([A-Z]{4})\s+SLOT LOST: every replacement for this slot was also non-viable", re.M)


def calls(tag):
    p = os.path.join(ROOT, "results", "grid_%s_calls.jsonl" % tag)
    files = [open(p)] if os.path.exists(p) else []
    files += [gzip.open(g, "rt") for g in sorted(glob.glob(os.path.join(ROOT, "results", "grid_%s_calls" % tag,
                                                                        "*.jsonl.gz")))]
    for fh in files:
        with fh:
            for line in fh:
                if line.strip():
                    try:
                        yield json.loads(line)
                    except ValueError:
                        continue            # a line still being written by a running panel


def scan(tag, pool):
    false, n_calls, cap_text = set(), 0, 0
    for c in calls(tag):
        n_calls += 1
        p = c.get("prompt") or ""
        if "AT THE LIMIT" in p or "maximum number of times" in p:
            cap_text += 1
        for rnd, seq in LINE.findall(p):
            if seq in pool:
                false.add((c["model"], c["campaign_seed"], int(rnd), seq))
    rows = []
    rp = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
    if os.path.exists(rp):
        rows = [json.loads(l) for l in open(rp) if l.strip()]
    cap_rows = sum(1 for r in rows if (r.get("prompt_options") or {}).get("repeat_cap") or r.get("repeat_cap")
                   or r.get("n_capped") or r.get("repeat_cap_hits"))
    return dict(calls=n_calls, campaigns=len(rows), campaigns_with_the_cap=cap_rows, prompts_with_cap_text=cap_text,
                false_lines=len(false), examples=sorted(false)[:5])


def main():
    tags = sys.argv[1:] or list(PANEL + CONTROLS)
    _fit, pool = grid.landscape()
    out = {t: scan(t, pool) for t in tags}
    json.dump(out, open(os.path.join(ROOT, "results", "scan_false_slot_lost.json"), "w"), indent=1, default=list)
    for t, d in out.items():
        print("%-22s %4d campaigns, %5d calls | campaigns with the cap %d | prompts with cap text %d | false "
              "SLOT LOST lines %d %s" % (t, d["campaigns"], d["calls"], d["campaigns_with_the_cap"],
                                         d["prompts_with_cap_text"], d["false_lines"], d["examples"][:2]))
    bad = [t for t in tags if t in PANEL and (out[t]["false_lines"] or out[t]["campaigns_with_the_cap"]
                                              or out[t]["prompts_with_cap_text"])]
    print("PANEL CLEAN" if not bad else "FOUND IN THE PANEL: %s" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
