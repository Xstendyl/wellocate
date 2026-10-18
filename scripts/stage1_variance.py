#!/usr/bin/env python3
"""Pooled within-cell variance and drift check for the grid's first stage. Prints no condition means.

The first stage is used only to re-estimate the variance and fix the final N, so every cell is centred before
pooling and no condition mean is computed. It also checks whether the primary outcome drifts within a cell,
using the order campaigns were appended (completion order) as the time axis, since this stage has no timestamps.
"""
import collections, json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef.stats import ols

EFFECT, Z = 0.06, 2.8
OVER_SD = 1.25            # the measured across-seed overdispersion


def load(tag):
    p = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
    return [json.loads(l) for l in open(p)]


def var(v):
    n = len(v)
    if n < 2:
        return float("nan")
    m = sum(v) / n
    return sum((x - m) ** 2 for x in v) / (n - 1)


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "stage1"
    rows = load(tag)
    cells = collections.defaultdict(list)
    for i, r in enumerate(rows):
        r["_order"] = i
        cells[(r["condition"], r["model"])].append(r)

    print("=" * 100)
    print("STAGE 1 VARIANCE  tag=%s  %d campaigns, %d cells" % (tag, len(rows), len(cells)))
    print("=" * 100)
    print("  NO CONDITION MEANS ARE PRINTED. Variances only, each cell centred before pooling.\n")

    print("  %-13s %-28s %4s %11s %11s | %s"
          % ("condition", "model", "n", "sd(nom)", "sd(distinct)", "drift slope per campaign"))
    per_model, per_cond, pooled = collections.defaultdict(list), collections.defaultdict(list), []
    drifts = []
    for (cond, model), v in sorted(cells.items()):
        nom = [x["nominated_true"] for x in v]
        nd = [float(x["n_distinct_measured"]) for x in v]
        if len(nom) < 2:
            continue
        sd = math.sqrt(var(nom))
        mu = sum(nom) / len(nom)
        pooled.extend(x - mu for x in nom)              # centred, so no mean survives the pooling
        per_model[model].extend(x - mu for x in nom)
        per_cond[cond].extend(x - mu for x in nom)
        xs = [float(x["_order"]) for x in sorted(v, key=lambda z: z["_order"])]
        ys = [x["nominated_true"] for x in sorted(v, key=lambda z: z["_order"])]
        b, bse, _ = ols(xs, ys)
        drifts.append((cond, model, b, bse))
        print("  %-13s %-28s %4d %11.4f %11.4f | %+9.5f +- %.5f  %s"
              % (cond, model, len(nom), sd, math.sqrt(var(nd)), b, bse,
                 "" if (bse and abs(b / bse) < 2) else "DRIFT > 2 SE"))

    print("\n  " + "-" * 96)
    print("  POOLED WITHIN-CELL sd of the primary outcome")
    print("  " + "-" * 96)
    for lbl, d in (("by model", per_model), ("by condition", per_cond)):
        print("  %s:" % lbl)
        for k, v in sorted(d.items()):
            print("    %-30s sd %.4f   (n=%d)" % (k, math.sqrt(var(v)), len(v)))
    sd_all = math.sqrt(var(pooled))
    print("\n  POOLED ACROSS EVERYTHING          sd %.4f   (n=%d)" % (sd_all, len(pooled)))

    bad = [d for d in drifts if d[3] and abs(d[2] / d[3]) >= 2]
    print("\n  " + "-" * 96)
    print("  DRIFT: primary outcome against completion order WITHIN each cell")
    print("  " + "-" * 96)
    print("  cells with a slope beyond 2 SE: %d of %d" % (len(bad), len(drifts)))
    for cond, model, b, bse in bad:
        print("    %-13s %-28s %+9.5f +- %.5f  (%.1f SE)" % (cond, model, b, bse, abs(b / bse)))
    if not bad:
        print("    None. No cell shows the outcome moving with completion order, so the block order")
        print("    of stage 1 did not imprint a time trend on any cell. The top-up shuffles anyway.")

    print("\n  " + "-" * 96)
    print("  FINAL N PER MODEL, at the pre-registered effect of %.2f" % EFFECT)
    print("  " + "-" * 96)
    print("""  SIZED PER MODEL AND NEVER POOLED. A pooled standard deviation is dragged down by a model
  whose campaigns are near-degenerate: gemini spends its budget on very few distinct variants, so its
  outcome barely varies, and pooling its small variance with opus's would UNDER-SIZE exactly the
  contrasts the confirmatory family depends on. Each model's cells are sized from that model's own
  within-cell variance across all five conditions.
""")
    COST = {"anthropic/claude-opus-4.7": 0.2003, "google/gemini-2.5-flash": 0.0059,
            "deepseek/deepseek-chat-v3.1": 0.0044}
    print("  %-30s %9s %8s %8s %12s" % ("model", "sd", "N/cell", "campaigns", "cost"))
    per_model_n, total_cost, total_camp = {}, 0.0, 0
    for m in sorted(per_model):
        sd = math.sqrt(var(per_model[m]))
        N = math.ceil(2 * (Z * sd / EFFECT) ** 2)
        per_model_n[m] = dict(sd=sd, n=N)
        c = N * 5 * COST.get(m, 0.2)
        total_cost += c
        total_camp += N * 5
        print("  %-30s %9.4f %8d %8d %11.2f" % (m, sd, N, N * 5, c))
    n_max = max(v["n"] for v in per_model_n.values()) if per_model_n else 0
    print("  %-30s %9s %8d %8d %11.2f"
          % ("TOTAL, per-model sizing", "", 0, total_camp, total_cost))
    if per_model_n:
        uni_cost = sum(n_max * 5 * COST.get(m, 0.2) for m in per_model_n)
        print("  %-30s %9s %8d %8d %11.2f"
              % ("ALTERNATIVE: largest sd for all", "", n_max, n_max * 5 * len(per_model_n), uni_cost))
        print("""
  The alternative uses the LARGEST per-model N everywhere, which costs more and makes every cell the
  same size. It is the safer choice if any between-model comparison is to be read, since unequal cell
  sizes there would confound precision with model. Between-model comparisons are EXPLORATORY in section
  0g, so per-model sizing is sufficient for the confirmatory family; the uniform option is reported so
  the choice is visible and costed.""")
    print("\n  For reference, the POOLED sd would be %.4f giving N=%d, which is the number NOT used."
          % (sd_all, math.ceil(2 * (Z * sd_all / EFFECT) ** 2)))
    print("  PROJECTED N was 676 from the scripted k=0 arm.")
    N_final = n_max
    out = dict(tag=tag, n_campaigns=len(rows), sd_pooled=sd_all,
               per_model_n={k: v for k, v in per_model_n.items()},
               n_uniform_largest=n_max,
               sd_by_model={k: math.sqrt(var(v)) for k, v in per_model.items()},
               sd_by_condition={k: math.sqrt(var(v)) for k, v in per_cond.items()},
               effect=EFFECT, z=Z, n_final=N_final, n_projected=676,
               drift_cells_beyond_2se=len(bad), drift_cells=len(drifts),
               drift=[dict(condition=c, model=m, slope=b, se=e) for c, m, b, e in drifts])
    json.dump(out, open(os.path.join(ROOT, "results", "step9_stage1_variance.json"), "w"), indent=1)
    print("\nsaved results/step9_stage1_variance.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
