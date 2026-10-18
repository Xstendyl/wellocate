#!/usr/bin/env python3
"""Provider mixture for deepseek/deepseek-chat-v3.1: the balance check and the pre-registered sensitivity analysis.

OpenRouter routes an open-weight model to providers that differ in quantisation and sampling defaults, and the
mixing happens within campaigns, so restricting to single-provider campaigns keeps almost no paired seeds. Reported:

  1. Balance, the primary check: the AtlasCloud share of calls per condition.
  2. Sensitivity on the nomination call: a seed is kept only when both cells' nomination calls came from the
     majority provider.
  3. The all-calls restriction, reported as infeasible with its retention.
  4. The modal provider.

Older campaigns have no provider field, so every count says how much of each cell it could see.
"""
import collections, glob, gzip, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_grid as AG                                     # noqa: E402

CONTRASTS = [("Aggregated", "Mechanism"), ("Decision-rule", "Mechanism")]
RUNG_OF = {"Blind": "blind", "Quantitative": "informed", "Mechanism": "instructed",
           "Aggregated": "aggregated", "Decision-rule": "decision_rule"}
DEEPSEEK = "deepseek/deepseek-chat-v3.1"


def calls(tag):
    p = os.path.join(ROOT, "results", "grid_%s_calls.jsonl" % tag)
    if os.path.exists(p):
        with open(p) as f:
            for l in f:
                if l.strip():
                    yield json.loads(l)
        return
    for g in sorted(glob.glob(os.path.join(ROOT, "results", "grid_%s_calls" % tag, "*.jsonl.gz"))):
        with gzip.open(g, "rt") as f:
            for l in f:
                if l.strip():
                    yield json.loads(l)


def main():
    tags = sys.argv[1:] or ["topup_deepseek"]
    per_campaign = collections.defaultdict(list)     # (rung, seed) -> [provider per call]
    nomination = {}                                  # (rung, seed) -> provider of the nomination call
    unknown = collections.Counter()
    for tag in tags:
        for r in calls(tag):
            if DEEPSEEK not in r.get("model", ""):
                continue
            k = (r["rung"], r["campaign_seed"])
            if "provider" not in r:
                unknown[tag] += 1
                continue
            per_campaign[k].append(r["provider"])
            if r["kind"] == "nomination":
                nomination[k] = r["provider"]
    if not per_campaign:
        sys.exit("no deepseek calls with a provider field in %s" % ", ".join(tags))

    share = collections.Counter(p for v in per_campaign.values() for p in v)
    total = sum(share.values())
    majority = share.most_common(1)[0][0]
    print("=" * 100)
    print("DEEPSEEK PROVIDER MIXTURE  tags=%s" % ",".join(tags))
    print("=" * 100)
    print("  calls with a provider recorded: %d over %d campaigns" % (total, len(per_campaign)))
    for p, n in share.most_common():
        print("    %-18s %6d calls  %5.1f%%" % (p, n, 100.0 * n / total))
    if unknown:
        print("  CALLS WITH NO PROVIDER FIELD (pre-2026-09-28 code): %s"
              % ", ".join("%s=%d" % kv for kv in sorted(unknown.items())))
    print("  majority provider: %s" % majority)

    print("\n1. BALANCE. Routing can only bias a contrast by correlating with condition.")
    print("   %-16s %8s %8s %8s" % ("condition", "calls", majority[:8], "share"))
    rows = []
    for cond, rung in RUNG_OF.items():
        v = [p for (rg, _s), ps in per_campaign.items() if rg == rung for p in ps]
        if not v:
            continue
        a = sum(1 for p in v if p == majority)
        rows.append((cond, len(v), a, 100.0 * a / len(v)))
    for cond, n, a, pct in rows:
        print("   %-16s %8d %8d %7.1f%%" % (cond, n, a, pct))
    if rows:
        sp = max(r[3] for r in rows) - min(r[3] for r in rows)
        print("   spread across conditions: %.1f percentage points" % sp)

    print("\n2. SENSITIVITY on the NOMINATION call, paired: both cells' nomination served by %s."
          % majority)
    # The paired difference on the kept seeds, read from the campaigns file by seed.
    camps = []
    for tag in tags:
        fp = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
        if os.path.exists(fp):
            with open(fp) as f:
                camps += [json.loads(l) for l in f if l.strip()]
    val = {}
    for r in camps:
        if DEEPSEEK in r["model"]:
            val[(RUNG_OF.get(r["condition"], r["condition"]), r["seed"])] = r["nominated_true"]
    print("   %-26s %6s %6s %11s %11s %11s"
          % ("contrast", "pairs", "kept", "diff all", "diff kept", "shift"))
    out = []
    for i_, b_ in CONTRASTS:
        ra, rb = RUNG_OF[b_], RUNG_OF[i_]
        both = sorted(s for (rg, s) in val if rg == ra and (rb, s) in val)
        keep = [s for s in both
                if nomination.get((ra, s)) == majority and nomination.get((rb, s)) == majority]

        def dmean(seeds):
            d = [val[(rb, s)] - val[(ra, s)] for s in seeds]
            return (st.mean(d), st.stdev(d) / (len(d) ** 0.5)) if len(d) > 1 else (float("nan"),
                                                                                  float("nan"))
        da, _sa = dmean(both)
        dk, _sk = dmean(keep)
        print("   %-26s %6d %6d %11.4f %11.4f %11.4f"
              % ("%s vs %s" % (i_, b_), len(both), len(keep), da, dk,
                 (dk - da) if (dk == dk and da == da) else float("nan")))
        out.append(dict(contrast="%s vs %s" % (i_, b_), pairs=len(both), kept=len(keep),
                        diff_all=da, diff_kept=dk))
    print("   `shift` is how far the estimate moves when the non-majority nominations are dropped. A")
    print("   shift far below the minimal effect of interest, 0.06, is the reassuring result; a large")
    print("   one says the provider mixture is doing work and must be reported as such.")

    print("\n3. THE ALL-CALLS DEFINITION, reported as infeasible.")
    pure = sum(1 for v in per_campaign.values() if set(v) == {majority})
    n = len(per_campaign)
    print("   campaigns whose every call was %s: %d of %d (%.0f%%)" % (majority, pure, n, 100.0 * pure / n))
    print("   paired seeds that would survive, both cells pure: about %.1f%%" % (100.0 * (pure / n) ** 2))
    print("   A test with that capacity can only return a null, so it is not run.")

    print("\n4. THE MODAL-PROVIDER FACT.")
    modal = sum(1 for v in per_campaign.values()
                if collections.Counter(v).most_common(1)[0][0] == majority)
    print("   campaigns whose MODAL provider was %s: %d of %d (%.0f%%)"
          % (majority, modal, n, 100.0 * modal / n))
    mixed = collections.Counter(len(set(v)) for v in per_campaign.values())
    print("   providers per campaign: %s" % dict(sorted(mixed.items())))

    dst = os.path.join(ROOT, "results", "provider_sensitivity.json")
    json.dump(dict(tags=tags, majority=majority, calls=total, campaigns=n,
                   provider_share={k: v for k, v in share.items()},
                   calls_without_provider=dict(unknown),
                   balance=[dict(condition=c, calls=k, majority=a, pct=p) for c, k, a, p in rows],
                   sensitivity=out, all_calls_pure=pure, modal_majority=modal,
                   providers_per_campaign={str(k): v for k, v in mixed.items()}),
              open(dst, "w"), indent=1)
    print("\n  wrote %s" % os.path.relpath(dst, ROOT))


if __name__ == "__main__":
    main()
