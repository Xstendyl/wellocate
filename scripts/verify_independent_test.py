#!/usr/bin/env python3
"""Re-score the independent test from the logged prompts and replies, and fail on a mismatch with the reported values.

The scorer shares no code with the original: it takes the measured set from the HISTORY block of each prompt and
the proposals from the reply text, and never calls a model. Scoring rule:
  - every proposal line in the reply is counted, up to four;
  - the denominator is always 4, so missing lines count as non-repeats;
  - a four-letter token with letters outside the alphabet is a proposal and cannot be a repeat.

Usage: verify_independent_test.py  (exit 1 on any mismatch)
"""
import collections, math, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "independent_check")

FILES = [("anthropic/claude-opus-4.7", "all_prompts_and_responses.md"),
         ("google/gemini-2.5-flash", "all_prompts_and_responses_gemini-2.5-flash.md"),
         ("deepseek/deepseek-chat-v3.1", "all_prompts_and_responses_deepseek-chat-v3.1.md")]
ARMS = [("A", "exact, stated"), ("B", "exact, unstated"), ("C", "noisy, stated")]
SLOTS = 4

# The reported repeat shares, in percent, to be reproduced.
CLAIMED = {
    "anthropic/claude-opus-4.7": {"A": 24.2, "B": 24.2, "C": 61.7},
    "google/gemini-2.5-flash": {"A": 45.0, "B": 50.8, "C": 95.0},
    "deepseek/deepseek-chat-v3.1": {"A": 55.8, "B": 49.2, "C": 94.2},
}

SEC = re.compile(r"^## seed (\d+), arm ([ABC])", re.M)
HIST_ROW = re.compile(r"^\s*\d+\s+([A-Za-z]{4})\s+(-?\d+\.\d+)\s*$", re.M)
PROPOSAL = re.compile(r"^\s*\**\s*([A-Za-z]{4})\s*\**\s*\|", re.M)


def sections(path):
    """(seed, arm, prompt, response) for every call in one file, from its own headings."""
    text = open(path).read()
    marks = [(m.start(), int(m.group(1)), m.group(2)) for m in SEC.finditer(text)]
    out = []
    for i, (pos, seed, arm) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        block = text[pos:end]
        blocks = re.findall(r"```\n(.*?)```", block, re.S)
        if len(blocks) < 2:
            raise SystemExit("REFUSED: seed %d arm %s has %d fenced blocks, expected prompt and response"
                             % (seed, arm, len(blocks)))
        out.append((seed, arm, blocks[0], blocks[1]))
    return out


def score(prompt, response):
    """Repeat share over four slots, and whether the best-by-mean-reading candidate was re-ordered."""
    rows = HIST_ROW.findall(prompt)
    if not rows:
        raise SystemExit("REFUSED: a prompt has no parseable HISTORY rows")
    measured = [c.upper() for c, _v in rows]
    reads = collections.defaultdict(list)
    for c, v in rows:
        reads[c.upper()].append(float(v))
    champ = max(reads, key=lambda c: st.mean(reads[c]))
    props = [p.upper() for p in PROPOSAL.findall(response)][:SLOTS]
    repeats = sum(1 for p in props if p in set(measured))
    return repeats / float(SLOTS), (champ in props), len(props), len(set(measured))


def main():
    fails = []
    print("=" * 96)
    print("INDEPENDENT TEST, re-scored from the prompts and replies as sent")
    print("=" * 96)
    print("  %-28s %-16s %4s %8s %8s %10s %9s"
          % ("model", "arm", "n", "repeat%", "SE", "best re-ord", "short<4"))
    table = {}
    for model, fname in FILES:
        path = os.path.join(DIR, fname)
        if not os.path.exists(path):
            fails.append("%s is missing" % fname)
            continue
        secs = sections(path)
        by = collections.defaultdict(dict)
        for seed, arm, prompt, response in secs:
            by[arm][seed] = score(prompt, response)
        if sorted(by) != ["A", "B", "C"]:
            fails.append("%s does not hold all three arms" % fname)
        table[model] = {}
        for arm, label in ARMS:
            v = by[arm]
            shares = [x[0] for x in v.values()]
            se = st.stdev(shares) / math.sqrt(len(shares)) if len(shares) > 1 else float("nan")
            table[model][arm] = (100.0 * st.mean(shares), 100.0 * se, len(shares),
                                 sum(1 for x in v.values() if x[1]),
                                 sum(1 for x in v.values() if x[2] < SLOTS))
            got, gse, n, champ, short = table[model][arm]
            want = CLAIMED.get(model, {}).get(arm)
            ok = want is None or abs(got - want) <= 0.05
            if not ok:
                fails.append("%s arm %s: re-scored %.2f%%, claimed %.1f%%" % (model, arm, got, want))
            print("  %-28s %-16s %4d %7.2f%% %7.2f%% %6d/%-3d %9d  %s"
                  % (model.split("/")[-1], label, n, got, gse, champ, n, short,
                     "OK" if ok else "MISMATCH vs %.1f" % want))
        # Paired contrasts on the shared seeds.
        for x, y, lab in (("C", "A", "noise effect, C minus A"),
                          ("B", "A", "stating exactness, B minus A")):
            ks = sorted(set(by[x]) & set(by[y]))
            d = [by[x][k][0] - by[y][k][0] for k in ks]
            m = 100.0 * st.mean(d)
            se = 100.0 * st.stdev(d) / math.sqrt(len(d))
            print("  %-28s %-16s %4d %7.2f%% %7.2f%%   (paired over the shared seeds)"
                  % ("", lab, len(ks), m, se))
        print()
    print("=" * 96)
    if fails:
        print("%d MISMATCH(ES):" % len(fails))
        for f in fails:
            print("  %s" % f)
        return 1
    print("every reported figure reproduces from the prompts and replies as sent, to 0.05 pp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
