#!/usr/bin/env python3
"""Prompt-check numbers the paper quotes that results/analysis_0al.json does not hold.

  - Precision of the first prompt-check panel: per cell, the SD of the paired fitness difference against the grid
    and the smallest 95% half-width 60 pairs can give, 1.96 x SD / sqrt(n).
  - DeepSeek V3.1's provider shares in each prompt-check panel and in the grid's follow-up runs, from the call
    archives.
  - The second panel's two segments: the campaigns each ran and each segment's ceiling, and the bound on the
    spend left unrecorded at the stop (two Opus 4.7 campaigns at that panel's mean cost).

Usage: python3 scripts/prompt_checks_detail.py      (writes results/prompt_checks_detail.json)
"""
import collections, glob, gzip, json, math, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_grid as AG                                   # noqa: E402
import analyse_0al as A0L                                   # noqa: E402

R = os.path.join(ROOT, "results")
OUT = os.path.join(R, "prompt_checks_detail.json")


def provider_shares(tag, model="deepseek/deepseek-chat-v3.1"):
    c = collections.defaultdict(collections.Counter)
    for g in sorted(glob.glob(os.path.join(R, "grid_%s_calls" % tag, "*.jsonl.gz"))):
        with gzip.open(g, "rt") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get("model") == model and r.get("rung") in ("blind", "instructed"):
                    c[r["rung"]][r.get("provider") or "unrecorded"] += 1
    return {rung: {p: 100.0 * n / sum(v.values()) for p, n in v.items()} for rung, v in c.items()}


def main():
    orig = AG.load("+".join(A0L.ORIGINAL))
    fb = AG.fallback_seeds(list(A0L.ORIGINAL))
    old = {(r["condition"], r["model"], r["seed"]): r for r in orig
           if (AG.RUNG_OF[r["condition"]], r["model"], r["seed"]) not in fb}
    _rows, _fb, new = A0L.load_panel("A", "panelA_wording")
    precision = {}
    for cond in A0L.CONDITIONS:
        for m in A0L.MODELS:
            ks = [k for k in new if k[0] == cond and k[1] == m and k in old]
            d = [new[k]["nominated_true"] - old[k]["nominated_true"] for k in ks]
            sd = st.stdev(d)
            precision["%s|%s" % (cond, m.split("/")[-1])] = dict(pairs=len(ks), sd=sd,
                                                                 half_width=1.96 * sd / math.sqrt(len(ks)))
    providers = {"A": provider_shares("panelA_wording"), "B": provider_shares("panelB_riskfree"),
                 "A0": provider_shares("panelA0_original")}
    grid = collections.defaultdict(collections.Counter)
    for t in ("topup_opus", "topup_gemini", "topup_deepseek"):
        for rung, v in provider_shares(t).items():
            for p, s in v.items():
                grid[rung][p] = s          # only topup_deepseek carries DeepSeek calls
    providers["grid"] = {r: dict(v) for r, v in grid.items()}
    seg1_log = open(os.path.join(R, "grid_panelB_riskfree.txt")).read()
    seg2_log = open(os.path.join(R, "grid_panelB_riskfree_part2.txt")).read()
    seg1_n = int(re.search(r"TOTAL SPEND \$[\d.]+ over \d+ calls, (\d+) campaigns", seg1_log).group(1))
    seg2_run = int(re.search(r"SHUFFLED order over (\d+) campaigns", seg2_log).group(1))
    m1 = json.load(open(os.path.join(R, "grid_panelB_riskfree_manifest_segment1.json")))
    m2 = json.load(open(os.path.join(R, "grid_panelB_riskfree_manifest.json")))
    b_rows = [json.loads(l) for l in open(os.path.join(R, "grid_panelB_riskfree_campaigns.jsonl")) if l.strip()]
    opus_b = st.mean(r["spend"] for r in b_rows if r["model"] == "anthropic/claude-opus-4.7")
    out = dict(precision=precision, deepseek_provider_shares=providers,
               panel_b_segments=dict(segment1_campaigns=seg1_n, segment2_campaigns=seg2_run,
                                     total=len(b_rows), ceiling1=m1["budget_usd"], ceiling2=m2["budget_usd"],
                                     commit1=m1["git_commit"][:7], commit2=m2["git_commit"][:7],
                                     workers=m1["workers"], opus_mean_spend=opus_b,
                                     unrecorded_bound=(m1["workers"] - 1) * opus_b),
               riskfree_cap=m2.get("riskfree_cap"))
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
