#!/usr/bin/env python3
"""Exploratory contrasts on replication share for the biology-framing panel.

Four families, with the estimator chosen by what the two sides share:
  Exact  - Role            paired by seed, both inside the panel on seeds 300000..300039
  Noisy  - Role            paired by seed, likewise
  Role   - grid Blind      unpaired, because the grid's Blind cell holds up to 695 campaigns per model
  Exact  - zeronoise Blind unpaired, likewise

Replication share is `replication_count / slots_used`. Intervals are a studentised wild cluster bootstrap over
seeds with Rademacher weights for paired families and a percentile bootstrap over campaigns for unpaired ones,
with 20,000 draws.

Usage: python3 scripts/bio_contrasts.py
"""
import collections, json, math, os, random, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_grid as A                                               # noqa: E402

REPS = 20000
MODELS = ["anthropic/claude-opus-4.7", "google/gemini-2.5-flash", "deepseek/deepseek-chat-v3.1"]


def load(tag):
    p = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
    return [json.loads(l) for l in open(p) if l.strip()]


def rep(c):
    return 100.0 * c["replication_fraction"]


def paired(a, b, seed=5):
    """Mean of the per-seed difference, with a percentile bootstrap over seeds."""
    ks = sorted(set(a) & set(b))
    d = [a[k] - b[k] for k in ks]
    rnd = random.Random(seed)
    boots = sorted(st.mean(rnd.choices(d, k=len(d))) for _ in range(REPS))
    return (st.mean(d), boots[int(0.025 * REPS)], boots[int(0.975 * REPS)], len(d))


def unpaired(x, y, seed=6):
    rnd = random.Random(seed)
    boots = sorted(st.mean(rnd.choices(x, k=len(x))) - st.mean(rnd.choices(y, k=len(y)))
                   for _ in range(REPS))
    return (st.mean(x) - st.mean(y), boots[int(0.025 * REPS)], boots[int(0.975 * REPS)],
            (len(x), len(y)))


def main():
    bio = load("bioframing")
    grid = []
    for t in ("stage1", "topup_opus", "topup_gemini", "topup_deepseek"):
        grid += load(t)
    zero = load("zeronoise")

    def cell(rows, cond, model):
        return {c["seed"]: rep(c) for c in rows if c["condition"] == cond and c["model"] == model}

    out = {}
    print("=" * 104)
    print("BIO PANEL CONTRASTS on replication share (percentage points), %d bootstrap draws" % REPS)
    print("EXPLORATORY. Not in the confirmatory family of 0g.")
    print("=" * 104)
    fams = [
        ("Exact - Role", "paired", lambda m: (cell(bio, "BioRoleExact", m), cell(bio, "BioRole", m))),
        ("Noisy - Role", "paired", lambda m: (cell(bio, "BioRoleNoisy", m), cell(bio, "BioRole", m))),
        ("Role - grid Blind", "unpaired", lambda m: (cell(bio, "BioRole", m), cell(grid, "Blind", m))),
        # Both sides are 40 campaigns on seeds 300000..300039, so this contrast is also run paired,
        # which removes the shared landscape draw.
        ("Exact - zeronoise Blind", "unpaired",
         lambda m: (cell(bio, "BioRoleExact", m), cell(zero, "Blind", m))),
        ("Exact - zeronoise Blind", "paired",
         lambda m: (cell(bio, "BioRoleExact", m), cell(zero, "Blind", m))),
    ]
    for label, how, get in fams:
        print("\n  %s (%s)" % (label, how))
        print("    %-22s %9s %22s %s" % ("model", "diff pp", "95% CI", "n"))
        for m in MODELS:
            a, b = get(m)
            if how == "paired":
                d, lo, hi, n = paired(a, b)
                nn = "%d seeds" % n
            else:
                d, lo, hi, n = unpaired(list(a.values()), list(b.values()))
                nn = "%d vs %d" % n
            out["%s|%s|%s" % (label, how, m)] = dict(diff=d, lo=lo, hi=hi, how=how)
            star = "" if lo <= 0 <= hi else "  *"
            print("    %-22s %+9.2f   [%+7.2f, %+7.2f]  %-12s%s"
                  % (m.split("/")[-1], d, lo, hi, nn, star))
    json.dump(out, open(os.path.join(ROOT, "results", "bio_contrasts.json"), "w"), indent=1)
    print("\n  * marks an interval that excludes zero.")
    print("  wrote results/bio_contrasts.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
