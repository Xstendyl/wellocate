#!/usr/bin/env python3
"""How often a new name is rejected, for the agents and for the guessing policy, under one convention.

A per-campaign count of rejections mostly measures how many new names were ordered, so this uses a per-name
rate. New-name orders = rejected orders + distinct candidates measured, where a distinct candidate has at least
one reading (`n_distinct_measured` for the agents, the curve's "distinct" for the policy). A name re-ordered
after a rejection counts each time, and the given starting candidate is not counted. The rate is rejected
orders over new-name orders, as a ratio of sums.

  agents   the 5,075 core-grid campaigns, per cell and pooled
  policy   the guessing policy at k = 1 on the 1,500 seeds of results/reference_curve_alphabet.json, rerun
           here for its per-campaign counts; its mean rejections and distinct candidates must equal the
           curve file's exactly, or the script refuses

Usage: python3 scripts/rejection_rates.py      (writes results/rejection_rates.json)
"""
import collections, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from repdef import campaign as C                                   # noqa: E402
import fair_reference_curve as FRC                                 # noqa: E402

OUT = os.path.join(ROOT, "results", "rejection_rates.json")
CORE = ("stage1", "topup_opus", "topup_gemini", "topup_deepseek")


def rate(rej, new):
    return 100.0 * rej / new if new else float("nan")


def main():
    rows = [json.loads(l) for t in CORE for l in open(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % t))
            if l.strip()]
    agg = collections.defaultdict(lambda: [0, 0, 0, 0])      # rejections, distinct, reference measured, campaigns
    for r in rows:
        k = (r["condition"], r["model"].split("/")[-1])
        a = agg[k]
        a[0] += r["n_rejected"]
        a[1] += r["n_distinct_measured"]
        a[2] += 1 if r["anchor_orders"] > 0 else 0
        a[3] += 1
    tot = [sum(v[i] for v in agg.values()) for i in range(4)]
    agents = dict(campaigns=tot[3], rejections_per_campaign=tot[0] / tot[3], distinct_per_campaign=tot[1] / tot[3],
                  reference_measured_share=tot[2] / tot[3],
                  rate=rate(tot[0], tot[0] + tot[1] - tot[2]),
                  rate_counting_the_reference=rate(tot[0], tot[0] + tot[1]))
    cells = {"%s|%s" % k: dict(campaigns=v[3], rate=rate(v[0], v[0] + v[1] - v[2])) for k, v in sorted(agg.items())}

    fit, pool = FRC.landscape()
    ps, space, anchor = tuple(sorted(pool)), tuple(sorted(fit)), FRC.anchor_of(fit, pool)
    prej = pdis = pref = 0
    for i in range(FRC.N):
        res = C.run(fit, pool, FRC.FairGreedyAlphabet(1, anchor, space, seed=0), 0.0, FRC.SEED0 + i, 0.15,
                    pool_sorted=ps, nomination="shrinkage", prior="empirical", noise_model="multiplicative",
                    cv=FRC.CV, noise_floor=FRC.FLOOR)
        ok = {h.seq for h in res.history if h.outcome == "ok"}
        prej += sum(1 for h in res.history if h.outcome == "rejected")
        pdis += len(ok)
        pref += 1 if anchor in ok else 0
    curve = json.load(open(FRC.CORRECTED))["curves"]["fair"]["1"]
    if abs(prej / FRC.N - curve["rejections"]) > 1e-9 or abs(pdis / FRC.N - curve["distinct"]) > 1e-9:
        raise SystemExit("REFUSED: the rerun does not reproduce the corrected curve's rejections and distinct")
    policy = dict(campaigns=FRC.N, rejections_per_campaign=prej / FRC.N, distinct_per_campaign=pdis / FRC.N,
                  reference_measured_share=pref / FRC.N, rate=rate(prej, prej + pdis - pref),
                  rate_counting_the_reference=rate(prej, prej + pdis))
    viable = lambda x: 100.0 - x
    out = dict(convention="new-name orders = rejected orders + distinct candidates measured, the given starting "
                          "candidate not counted; rate = rejected orders / new-name orders, a ratio of sums",
               agents=agents, policy=policy, cells=cells,
               cell_rate_min=min(c["rate"] for c in cells.values()), cell_rate_max=max(c["rate"] for c in cells.values()),
               cells_above_policy=sorted(k for k, c in cells.items() if c["rate"] > policy["rate"]),
               viable_hit_ratio=viable(agents["rate"]) / viable(policy["rate"]),
               viable_hit_ratio_counting_the_reference=(viable(agents["rate_counting_the_reference"]) /
                                                        viable(policy["rate_counting_the_reference"])))
    json.dump(out, open(OUT, "w"), indent=1)
    print("convention: %s" % out["convention"])
    for who in ("agents", "policy"):
        d = out[who]
        print("%-7s %5d campaigns: %.2f rejections and %.2f distinct per campaign, reference measured in %.1f%%; "
              "per-name rejection rate %.1f%% (%.1f%% counting the reference)"
              % (who, d["campaigns"], d["rejections_per_campaign"], d["distinct_per_campaign"],
                 100 * d["reference_measured_share"], d["rate"], d["rate_counting_the_reference"]))
    print("viable hits per new name, agents over policy: %.2f (%.2f counting the reference)"
          % (out["viable_hit_ratio"], out["viable_hit_ratio_counting_the_reference"]))
    print("per cell: %.1f%% to %.1f%%; above the policy's %.1f%%: %s"
          % (out["cell_rate_min"], out["cell_rate_max"], policy["rate"], out["cells_above_policy"]))
    for k, c in cells.items():
        print("   %-34s %5.1f%%" % (k, c["rate"]))
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
