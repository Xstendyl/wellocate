#!/usr/bin/env python3
"""Check whether the final N powers the confirmatory family of paired contrasts, using variances from the data.

Each contrast is sized at 80% power for the Holm first step across six contrasts, z(1 - alpha/12) + z(0.80),
from its own two cells' paired variance; pooled variances use n*k - k degrees of freedom. Reports both the
required N and the power at the currently chosen N.
"""
import collections, json, math, os, statistics as st, sys
from statistics import NormalDist

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEI, ALPHA, POWER, FAMILY = 0.06, 0.05, 0.80, 6
CHOSEN_N = 374
COST = {"anthropic/claude-opus-4.7": 0.2003, "google/gemini-2.5-flash": 0.0059,
        "deepseek/deepseek-chat-v3.1": 0.0044}
CONTRASTS = [("Aggregated", "Mechanism"), ("Decision-rule", "Mechanism")]


def z_for(alpha, power=POWER):
    return NormalDist().inv_cdf(1 - alpha / 2) + NormalDist().inv_cdf(power)


def cells(rows):
    c = collections.defaultdict(list)
    for r in rows:
        c[(r["condition"], r["model"])].append(r["nominated_true"])
    return c


def seeded(rows):
    """condition, model -> seed -> value; the contrasts are paired by seed."""
    c = collections.defaultdict(dict)
    for r in rows:
        c[(r["condition"], r["model"])][r["seed"]] = r["nominated_true"]
    return c


def paired_var(S, m, i_, b_):
    """Variance of the per-seed difference, for sizing a paired contrast.

    Returns (variance, n_seeds, seeds_dropped, correlation) or None when the cells cannot be paired.
    Draws are keyed on the seed, so the cells are dependent and the unpaired s_a^2 + s_b^2 omits -2cov.
    """
    A, B = S.get((b_, m)), S.get((i_, m))
    if not A or not B:
        return None
    ks = sorted(set(A) & set(B))
    if len(ks) < 2:
        return None
    ya = [A[k] for k in ks]
    yb = [B[k] for k in ks]
    d = [y - x for x, y in zip(ya, yb)]
    sa, sb = st.stdev(ya), st.stdev(yb)
    ma, mb = st.mean(ya), st.mean(yb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ya, yb)) / (len(ks) - 1)
    r = cov / (sa * sb) if sa and sb else float("nan")
    return st.variance(d), len(ks), len(set(A) ^ set(B)), r


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "stage1"
    path = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
    rows = [json.loads(l) for l in open(path) if l.strip()]
    # The full grid is 5 conditions x 3 models x 40 seeds; warn when it is incomplete.
    if len(rows) < 600:
        print("!" * 100)
        print("!! %s HAS %d CAMPAIGNS, NOT 600. These variances are from a PART-FINISHED grid and no"
              % (tag, len(rows)))
        print("!! number below is a sizing decision. Section 0o sizes from the COMPLETE stage.")
        print("!" * 100)
    C = cells(rows)
    models = sorted({m for _c, m in C})

    print("=" * 100)
    print("(a) THE Z FOR THE CONFIRMATORY FAMILY")
    print("=" * 100)
    z_un = z_for(ALPHA)
    z_holm = z_for(ALPHA / FAMILY)
    print("  unadjusted  alpha %.4f  ->  z(1-a/2) %.4f + z(0.80) %.4f = %.4f   (section 0e used 2.8)"
          % (ALPHA, NormalDist().inv_cdf(1 - ALPHA / 2), NormalDist().inv_cdf(POWER), z_un))
    print("  Holm step 1 alpha %.6f ->  z(1-a/2) %.4f + z(0.80) %.4f = %.4f"
          % (ALPHA / FAMILY, NormalDist().inv_cdf(1 - ALPHA / FAMILY / 2),
             NormalDist().inv_cdf(POWER), z_holm))
    print("  the required N scales as z^2, so the ratio is (%.4f/%.4f)^2 = %.3fx"
          % (z_holm, z_un, (z_holm / z_un) ** 2))

    print("\n" + "=" * 100)
    print("(c) THE POOLING DIVISOR, per model over its five conditions")
    print("=" * 100)
    print("  %-30s %10s %10s %8s" % ("model", "sd (N-1)", "sd (N-k)", "N/cell shift"))
    for m in models:
        vals, k = [], 0
        for (cond, mm), v in C.items():
            if mm == m:
                mu = st.mean(v)
                vals += [x - mu for x in v]
                k += 1
        n = len(vals)
        ss = sum(x * x for x in vals)
        sd1, sdk = math.sqrt(ss / (n - 1)), math.sqrt(ss / (n - k))
        n1 = math.ceil(2 * (z_holm * sd1 / MEI) ** 2)
        nk = math.ceil(2 * (z_holm * sdk / MEI) ** 2)
        print("  %-30s %10.4f %10.4f %8s" % (m, sd1, sdk, "%d -> %d" % (n1, nk)))
    print("  (k = 5 cells, n = 200 values, so the divisor is 195 and not 199)")

    print("\n" + "=" * 100)
    print("(b) CONTRAST-SPECIFIC N, PAIRED BY SEED, from each contrast's own difference, at z = %.4f" % z_holm)
    print("=" * 100)
    need = collections.defaultdict(int)
    S = seeded(rows)
    print("  PAIRED BY SEED (amendment 0s). The sizing variance is the variance of the per-seed")
    print("  DIFFERENCE. The unpaired column is kept beside it because pairing is NOT automatically")
    print("  cheaper: a negative within-seed correlation makes the paired requirement LARGER.")
    print("  %-26s %-26s %8s %8s %7s %8s %8s %8s"
          % ("model", "contrast", "sd pair", "sd unpr", "corr", "N paired", "N unpr", "power@%d" % CHOSEN_N))
    for m in models:
        for a, b in CONTRASTS:
            va, vb = C.get((a, m)), C.get((b, m))
            pv = paired_var(S, m, a, b)
            if not va or not vb or pv is None:
                continue
            s1, s2 = st.variance(va), st.variance(vb)
            vd, nseed, dropped, r = pv
            n_req = math.ceil((z_holm / MEI) ** 2 * vd)              # paired: the binding number
            n_unp = math.ceil((z_holm / MEI) ** 2 * (s1 + s2))       # unpaired, for comparison only
            se = math.sqrt(vd / CHOSEN_N)
            zc = NormalDist().inv_cdf(1 - ALPHA / FAMILY / 2)
            pw = NormalDist().cdf(MEI / se - zc)
            need[m] = max(need[m], n_req)
            if dropped:
                print("    WARNING: %s %s vs %s has %d unmatched seeds; paired on the %d it shares"
                      % (m, a, b, dropped, nseed))
            print("  %-26s %-26s %8.4f %8.4f %+7.3f %8d %8d %8.2f"
                  % (m.split("/")[-1], "%s vs %s" % (a, b), math.sqrt(vd),
                     math.sqrt(s1 + s2), r, n_req, n_unp, pw))
    print("\n  WORST CONTRAST PER MODEL, which is what each model's cells must be sized to:")
    tot_cost = tot_camp = 0
    for m in models:
        c = need[m] * 5 * COST.get(m, 0.2)
        tot_cost += c
        tot_camp += need[m] * 5
        print("    %-30s N/cell %4d   %5d campaigns   $%8.2f" % (m, need[m], need[m] * 5, c))
    print("    %-30s %14s %5d campaigns   $%8.2f" % ("TOTAL, per-model sizing", "", tot_camp, tot_cost))
    nmax = max(need.values())
    uni_cost = sum(nmax * 5 * COST.get(m, 0.2) for m in models)
    print("    %-30s N/cell %4d   %5d campaigns   $%8.2f"
          % ("ALTERNATIVE: uniform at the max", nmax, nmax * 5 * len(models), uni_cost))
    print("\n  The uniform option now costs $%.0f more, not eleven dollars, because the model driving the"
          % (uni_cost - tot_cost))
    print("  maximum is no longer the cheap one. That premise is withdrawn.")

    print("\n" + "=" * 100)
    print("POWER AT THE CURRENTLY CHOSEN N = %d, on the first Holm step" % CHOSEN_N)
    print("=" * 100)
    for m in models:
        pws = []
        for a, b in CONTRASTS:
            va, vb = C.get((a, m)), C.get((b, m))
            if not va or not vb:
                continue
            se = math.sqrt((st.variance(va) + st.variance(vb)) / CHOSEN_N)
            pws.append(NormalDist().cdf(MEI / se - NormalDist().inv_cdf(1 - ALPHA / FAMILY / 2)))
        print("  %-30s power %.2f to %.2f" % (m, min(pws), max(pws)))
    out = dict(z_unadjusted=z_un, z_holm_step1=z_holm, mei=MEI, family=FAMILY,
               chosen_n=CHOSEN_N,
               per_model_required={m: need[m] for m in models},
               uniform_required=nmax, cost_per_model=tot_cost, cost_uniform=uni_cost)
    # The input tag goes in the output's filename and content.
    out["tag"] = tag
    out["campaigns"] = len(rows)
    out["paired_by_seed"] = True
    dst = os.path.join(ROOT, "results", "step10_contrast_power_%s.json" % tag)
    json.dump(out, open(dst, "w"), indent=1)
    print("\nsaved %s" % os.path.relpath(dst, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
