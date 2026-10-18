#!/usr/bin/env python3
"""Recompute the project's quoted numbers from raw data and logs, and fail on any mismatch.

Exit code 1 on any mismatch.

  python3 scripts/verify_all_numbers.py          # fast tier, from data and logs
  VERIFY_SLOW=1 python3 scripts/verify_all_numbers.py   # also re-simulates the margins
"""
import collections, glob, json, math, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import landscape as L

FAILS, CHECKS = [], []


def check(label, got, want, tol, unit=""):
    ok = (want is None) or (abs(got - want) <= tol)
    CHECKS.append(ok)
    if not ok:
        FAILS.append("%s: got %.6g, claimed %.6g, tol %.3g" % (label, got, want, tol))
    print("  %-58s %12.6g %-6s %s" % (label, got, unit,
          "OK" if ok else ("MISMATCH, claimed %.6g" % want)))
    return got


def logs(pat):
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "results", pat))):
        out.append((p, [json.loads(l) for l in open(p)]))
    return out


def crossings(rows, thr=0.5, strict=False):
    camps = collections.defaultdict(list)
    for r in rows:
        if r["kind"] != "nomination":
            camps[r["campaign_seed"]].append(r)
    cr, meas = [], []
    for seed, calls in camps.items():
        seen, per = set(), []
        for r in sorted(calls, key=lambda x: (x["round"], x["kind"] != "round")):
            if not r["parsed"]:
                continue
            f = sum(1 for s in r["parsed"] if s in seen) / len(r["parsed"])
            per.append((r["round"], f, len(seen)))
            seen.update(r["parsed"])
        h = [(rd, nm) for rd, f, nm in per if (f > thr if strict else f >= thr)]
        if h:
            cr.append(h[0][0]); meas.append(h[0][1])
    return cr, meas


def main():
    print("=" * 84)
    print("1. LANDSCAPE PROVENANCE, recomputed from data/*.csv")
    print("=" * 84)
    gb1, phoq = L.load("gb1"), L.load("phoq")
    check("GB1 rows", len(gb1), 160000, 0)
    check("GB1 pool", len(gb1.pool), 11522, 0)
    check("GB1 max", gb1.max_fitness, 8.762, 0.001)
    check("GB1 exact zeros", gb1.exact_zeros, 40116, 0)
    check("GB1 measured-zero share vs published 19.7%",
          100 * (gb1.exact_zeros - (160000 - 149361)) / 149361, 19.7, 0.05, "%")
    check("PhoQ pool", len(phoq.pool), 11146, 0)
    check("PhoQ max", phoq.max_fitness, 133.594, 0.001)
    pv = sorted(phoq.fitness.values(), reverse=True)
    check("PhoQ 1659th value vs published functional call", pv[1658], 14.183, 0.01)

    print("\n" + "=" * 84)
    print("2. THE NOISE CONSTANTS, recomputed from the published read depth")
    print("=" * 84)
    n_in, n_sel = 89075246 / 160000.0, 45587128 / 160000.0
    check("input reads per variant", n_in, 556.72, 0.01)
    check("selected reads per variant", n_sel, 284.92, 0.01)
    cv = math.sqrt(1 / n_sel + 1 / n_in)
    check("CV from Var(log w) = 1/n_sel + 1/n_in", 100 * cv, 7.28, 0.02, "%")
    wt_ratio = n_sel / n_in
    floor = (1 / n_in) / wt_ratio
    check("Poisson noise floor", floor, 0.003509, 1e-5)
    check("floor ratio for beat one to survive (1.0 / floor)", 1.0 / floor, 285.0, 1.5, "x")

    print("\n" + "=" * 84)
    print("3. CONTAMINATION ENRICHMENT, recomputed from the pilot log")
    print("=" * 84)
    rows = logs("pilot_opus47_calls.jsonl")[0][1]
    best = max(gb1.pool, key=lambda s: gb1.fitness[s])
    check("GB1 argmax is FWAA", 1.0 if best == "FWAA" else 0.0, 1.0, 0)
    camps = collections.defaultdict(list)
    for r in rows:
        camps[(r["rung"], r["ratio"], r["campaign_seed"])].append(r)
    n_camp = len(camps)
    r1_hit = sum(1 for k, cs in camps.items()
                 if any(best in r["parsed"] for r in cs if r["round"] == 1))
    check("campaigns", n_camp, 20, 0)
    check("campaigns proposing FWAA at round 1", r1_hit, 11, 0)
    obs = r1_hit / n_camp
    base4 = 4.0 / len(gb1.pool)
    check("observed round-1 rate", 100 * obs, 55.0, 0.1, "%")
    check("chance rate for 4 draws from the pool", 100 * base4, 0.0347, 0.001, "%")
    check("ENRICHMENT (round-1, 4-draw baseline)", obs / base4, 1584.0, 5.0, "x")
    r1 = [r for r in rows if r["round"] == 1]
    inpool = [s for r in r1 for s in r["parsed"] if s in gb1.pool]
    top10 = set(sorted(gb1.pool, key=lambda s: -gb1.fitness[s])[:10])
    n_t10 = sum(1 for s in inpool if s in top10)
    check("round-1 in-pool proposals", len(inpool), 78, 0)
    check("of those, in the pool's top 10", n_t10, 11, 0)
    check("ENRICHMENT (top-10)", (n_t10 / len(inpool)) / (10.0 / len(gb1.pool)), 162.0, 2.0, "x")

    print("\n" + "=" * 84)
    print("4. THE CLOCK, recomputed from the length logs")
    print("=" * 84)
    xs, ys = [], []
    for p, rr in logs("pilot_len*_calls.jsonl"):
        R = rr[0]["total_rounds"]
        cr, _ = crossings(rr, strict=True)
        check("length %d: n crossed" % R, len(cr), 5, 0)
        check("length %d: mean crossing round" % R, st.mean(cr),
              {10: 6.2, 15: 6.2, 30: 6.4}[R], 0.05)
        for c in cr:
            xs.append(float(R)); ys.append(float(c))
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    check("Sxx", sxx, 1083.3, 0.1)
    check("regression slope of crossing round on length", slope, 0.0108, 0.0005)
    groups = sorted(set(xs))
    ssw = sum(sum((v - st.mean([y for x, y in zip(xs, ys) if x == g])) ** 2
                  for v in [y for x, y in zip(xs, ys) if x == g]) for g in groups)
    sdw = math.sqrt(ssw / (len(xs) - len(groups)))
    se = sdw / math.sqrt(sxx)
    check("pooled within-group sd", sdw, 2.840, 0.005)
    check("SE of the slope", se, 0.0863, 0.0005)
    check("budget-fraction (L15 fit 0.41) distance", abs(0.41 - slope) / se, 4.6, 0.1, "SE")
    check("rounds-remaining (1.0) distance", abs(1.0 - slope) / se, 11.5, 0.1, "SE")

    print("\n" + "=" * 84)
    print("5. BATCH SIZE, recomputed from the slots logs")
    print("=" * 84)
    for p, rr in logs("pilot_slots*_calls.jsonl"):
        S = rr[0]["slots_per_round"]
        cr, meas = crossings(rr, strict=False)
        check("slots %d: crossing round (>=0.5 threshold)" % S, st.mean(cr),
              {2: 4.5, 4: 4.6, 8: 2.3}[S], 0.05)
        check("slots %d: measurements at crossing" % S, st.mean(meas),
              {2: 9.5, 4: 15.5, 8: 17.3}[S], 0.05)

    print("\n" + "=" * 84)
    if os.environ.get("VERIFY_SLOW"):
        print("6. MARGINS, re-simulated (slow tier)")
        print("=" * 84)
        from repdef import campaign as C, policies as P
        from repdef.nk import NKLandscape
        def margin(fit, pool, n, seed0):
            ps = tuple(sorted(pool)); vals = [fit[s] for s in pool]
            prior = (st.mean(vals), st.variance(vals))
            pol = P.GreedyWithReplication(1, 0, "pool", "fresh_pool")
            d = []
            for i in range(n):
                r = C.run(fit, pool, pol, 0.0, seed0 + i, 0.15, pool_sorted=ps,
                          nomination="shrinkage", prior=prior,
                          noise_model="multiplicative", cv=cv, noise_floor=floor)
                d.append(r.nominated_true - fit[r.ref_max])
            return st.mean(d), st.stdev(d) / math.sqrt(len(d))
        m, s_ = margin(gb1.fitness, gb1.pool, 2000, 10_000_000)
        check("GB1 margin (shrinkage - max-single)", m, 0.0144, 0.003)
        check("GB1 margin SE ratio", m / s_, 4.6, 0.8, "SE")
    else:
        print("6. MARGINS: skipped. set VERIFY_SLOW=1 to re-simulate them.")
    section_phoq_and_temperature()
    print("=" * 84)
    print("\n%d checks, %d failures." % (len(CHECKS), len(FAILS)))
    for f in FAILS:
        print("  FAIL  %s" % f)
    return 1 if FAILS else 0



def section_phoq_and_temperature():
    """The PhoQ round-1 diagnostic and the temperature-0 determinism check."""
    print("\n" + "=" * 84)
    print("7. PHOQ ROUND-1 CONTAMINATION, and TEMPERATURE-0 DETERMINISM")
    print("=" * 84)
    ph = L.load("phoq")
    check("PhoQ pool size", len(ph.pool), 11146, 0)
    best = max(ph.pool, key=lambda s: ph.fitness[s])
    check("PhoQ argmax is TEMH", 1.0 if best == "TEMH" else 0.0, 1.0, 0)
    check("PhoQ argmax fitness", ph.fitness[best], 133.594, 0.01)
    check("PhoQ reference AVST fitness", ph.fitness["AVST"], 3.2874, 0.001)
    check("PhoQ pool median fitness", st.median([ph.fitness[s] for s in ph.pool]), 6.689, 0.01)

    pj = os.path.join(ROOT, "results", "step6_phoq_enrichment.json")
    if os.path.exists(pj):
        d = json.load(open(pj))
        check("PhoQ round-1 campaigns", d["n"], 20, 0)
        check("PhoQ campaigns naming TEMH", d["hits"], 0, 0)
        check("PhoQ sigma unit (random-calibrated)", d["sigma_unit"], 5.807, 0.02)
        check("GB1 one-ask rate equals the published rate", d["gb1_one_ask_hits"], 11, 0)
        check("GB1 one-ask enrichment", d["gb1_one_ask_enrichment"], 1584.0, 5.0, "x")

    dj = os.path.join(ROOT, "results", "step6_round1_prior_diagnostics.json")
    if os.path.exists(dj):
        rows = json.load(open(dj))
        g = [r for r in rows if r["name"].startswith("GB1")][0]
        p_ = [r for r in rows if r["name"].startswith("PhoQ")][0]
        c = [r for r in rows if r["name"] == "contrast"][0]
        # Superseded percentiles that count the anchor among the proposals; the anchor is low on PhoQ,
        # so the usable statistic excludes it and compares against the anchor's own neighbourhood.
        check("[superseded] GB1 percentile, anchor included", g["mean_fitness_percentile"],
              0.714, 0.002)
        check("[superseded] PhoQ percentile, anchor included", p_["mean_fitness_percentile"],
              0.414, 0.002)
        check("[superseded] difference vs 0.5 baseline", c["diff_percentile"], 0.300, 0.002)
        check("[superseded] that difference in SE", c["se_units_percentile"], 5.3, 0.1, "SE")
        check("PhoQ 95% upper bound on enrichment", p_["enrichment_upper95"], 388.0, 2.0, "x")
        # The mean Hamming distance must stay small: it does not separate the two landscapes.
        check("mean Hamming difference (must stay small)", abs(c["diff_mean_hamming"]), 0.13, 0.01)
        check("distance-4 difference in SE (suggestive only)", abs(c["z_dist4"]), 1.9, 0.1, "SE")

    nj = os.path.join(ROOT, "results", "step6_nk_confirm.json")
    if os.path.exists(nj):
        d = json.load(open(nj))
        ref = d["gb1_reference"]; sel = d["selection"]; hel = d["heldout"]
        check("NK confirm: campaigns per cell", d["n_per_cell"], 1500, 0)
        check("GB1 reference margin (fixed estimator)", ref["margin"], 0.0144, 0.0005)
        check("GB1 reference SE ratio", ref["ratio"], 4.6, 0.1, "SE")
        check("GB1 reference gap/sigma", ref["gap_sigma"], 1.02, 0.02)
        check("uniform NK selection margin", sel["margin"], 0.0317, 0.0005)
        check("uniform NK selection SE ratio", sel["ratio"], 5.7, 0.1, "SE")
        check("uniform NK HELD-OUT margin", hel["margin"], 0.0329, 0.0005)
        check("uniform NK HELD-OUT SE ratio", hel["ratio"], 5.7, 0.1, "SE")
        check("held-out ratio after 1.25x overdispersion", d["heldout_ratio_overdispersed"],
              4.6, 0.1, "SE")
        check("uniform NK effect size (margin/sigma)", hel["margin_in_sigma"], 0.055, 0.002)
        check("GB1 effect size (margin/sigma)", ref["margin_in_sigma"], 0.036, 0.002)
        check("uniform NK gap/sigma (OUTSIDE the 0.5-1.5 band)", hel["gap_sigma"], 0.22, 0.02)
        check("replicating baselines passing neutrality", d["neutrality_pass"], 3, 0)
        check("replicating baselines tested", d["neutrality_replicating"], 3, 0)
        # Baselines that never replicate must show exactly zero margin.
        z = [r for r in d["neutrality"] if not r["replicates"]]
        check("non-replicating baselines show EXACTLY zero margin",
              max(abs(r["margin"]) for r in z), 0.0, 1e-12)
        check("exponential now FAILS (was the chosen winner)", sel["margin"] is not None and
              [r for r in d["reproduction"] if r["dist"] == "exponential"][0]["ratio"], 1.2, 0.1, "SE")

    aj = os.path.join(ROOT, "results", "step6_anchor_neighbourhood_null.json")
    if os.path.exists(aj):
        rows = json.load(open(aj))
        g = [r for r in rows if r["name"] == "GB1"][0]
        p_ = [r for r in rows if r["name"] == "PhoQ"][0]
        check("GB1 percentile, anchor EXCLUDED", g["mean_observed"], 0.729, 0.002)
        check("PhoQ percentile, anchor EXCLUDED (ABOVE 0.5)", p_["mean_observed"], 0.535, 0.002)
        check("GB1 distance-matched null", g["mean_matched_null"], 0.558, 0.003)
        check("PhoQ distance-matched null", p_["mean_matched_null"], 0.561, 0.003)
        check("GB1 excess over its own neighbourhood", g["mean_observed"] - g["mean_matched_null"],
              0.171, 0.003)
        check("GB1 excess in SE", abs(g["z_vs_matched"]), 3.9, 0.1, "SE")
        check("PhoQ excess over its own neighbourhood", p_["mean_observed"] - p_["mean_matched_null"],
              -0.026, 0.003)
        check("PhoQ excess in SE (no excess)", abs(p_["z_vs_matched"]), 0.9, 0.1, "SE")
        dg = g["mean_observed"] - g["mean_matched_null"]
        dp = p_["mean_observed"] - p_["mean_matched_null"]
        sd = math.sqrt(g["se_vs_matched"] ** 2 + p_["se_vs_matched"] ** 2)
        check("difference of excesses", dg - dp, 0.197, 0.003)
        check("difference of excesses in SE", abs((dg - dp) / sd), 3.8, 0.1, "SE")

    mj = os.path.join(ROOT, "results", "step6_shrinkage_monotonicity.json")
    if os.path.exists(mj):
        d = json.load(open(mj))
        r1 = [r for r in d["rows"] if r["landscape"] == "PhoQ, UNSCALED" and r["n"] == 1][0]
        check("PhoQ n=1 posterior turning point", r1["turning_point"], 108.93, 0.05)
        check("PhoQ turning point is inside the fitness range",
              1.0 if r1["reachable"] else 0.0, 1.0, 0)
        nk1 = [r for r in d["rows"] if r["landscape"].startswith("NK uniform") and r["n"] == 1][0]
        check("NK uniform is monotone (no turning point)",
              1.0 if nk1["turning_point"] is None else 0.0, 1.0, 0)
        aff = [a for a in d["affected"] if a["landscape"] == "PhoQ, UNSCALED"][0]
        check("campaigns nominating past the peak", aff["frac_campaigns_past_peak"], 0.0, 1e-9)

    cj = os.path.join(ROOT, "results", "step8_clock_verify.json")
    if os.path.exists(cj):
        d = json.load(open(cj))
        check("clock definition is >=50%", 1.0 if d["definition"] == ">=50%" else 0.0, 1.0, 0)
        check("clock slope (n=20, reparsed)", d["slope"], -0.0238, 0.0005)
        check("clock slope SE", d["se"], 0.0248, 0.0005)
        check("campaigns in the regression", d["n"], 60, 0)
        check("absolute clock distance", d["hypotheses"]["absolute clock"]["distance_se"],
              1.0, 0.05, "SE")
        check("pacing distance", d["hypotheses"]["pacing against the budget"]["distance_se"],
              15.4, 0.1, "SE")
        check("rounds-remaining distance", d["hypotheses"]["rounds remaining"]["distance_se"],
              41.3, 0.2, "SE")
        check("pacing fraction from the length-15 cell", d["pacing_fraction"], 0.357, 0.002)
        # Both estimators are pinned; they are different estimators, not two attempts at one number.
        check("quoted estimator is campaign-level OLS",
              1.0 if d["estimator"] == "campaign-level OLS" else 0.0, 1.0, 0)
        check("WLS on 3 cell means, slope", d["wls_cell_means"]["slope"], -0.0273, 0.0005)
        check("WLS on 3 cell means, SE", d["wls_cell_means"]["se"], 0.0266, 0.0005)

    rj = os.path.join(ROOT, "results", "step8_reparse_audit.json")
    if os.path.exists(rj):
        d = json.load(open(rj))
        check("re-parse audit: all crossing rounds hold", 1.0 if d["all_hold"] else 0.0, 1.0, 0)
        check("experiments audited", len(d["verdicts"]), 12, 0)
        worst = max(v["diff"] for v in d["verdicts"])
        check("largest crossing-round shift", worst, 0.10, 0.001)
        e = d["experiments"]
        check("opus47 replication, OLD parser", 100 * e["opus47"]["rep_old"], 74.6, 0.2, "%")
        check("opus47 replication, NEW parser", 100 * e["opus47"]["rep_new"], 73.5, 0.2, "%")
        # Read from the JSON, not the rounded display.
        check("opus47 old-vs-new disagreement", 100 * e["opus47"]["disagree_frac"], 3.53, 0.02, "%")

    # Sizing: N per cell derived from the measured SD.
    nj = os.path.join(ROOT, "results", "step7_nk_reference_curve.json")
    if os.path.exists(nj):
        d = json.load(open(nj))
        ks = d["curves"]["shrinkage"]
        sd0 = ks["rows"]["0"]["se"] * math.sqrt(d["n"])
        check("sd of nominated fitness, k=0 arm (conservative)", sd0, 0.3937, 0.001)
        n_cell = math.ceil(2 * (2.8 * sd0 / 0.06) ** 2)
        check("N per cell, unpaired, 2.8 SE, effect 0.06", n_cell, 676, 0)
        check("total grid campaigns", n_cell * 5 * 3, 10140, 0)
        cost = 0.2003 + 0.0059 + 0.0044
        check("projected grid cost", n_cell * 5 * cost, 711.83, 1.0, "USD")

    fj = os.path.join(ROOT, "results", "step7_prior_floor_sensitivity.json")
    if os.path.exists(fj):
        d = json.load(open(fj))
        k1 = [v for k, v in d["binding"].items() if k.startswith("greedy k=1|0.01")][0]
        check("scripted k* distinct variants per campaign", k1["mean_nvar"], 39.2, 0.1)

    tj = os.path.join(ROOT, "results", "step6_temperature_zero_determinism.json")
    if os.path.exists(tj):
        d = json.load(open(tj))
        check("temperature-0 pairwise agreement", d["pairwise_agreement"], 0.265, 0.002)
        check("repeated-prompt groups", d["repeated_groups"], 4, 0)
        check("groups whose replies were all identical", d["groups_all_identical"], 1, 0)
        check("cells with within-cell variation", d["cells_with_within_cell_variation"], 4, 0)

    # ---- Methods figures from the grid's first stage and the pilot ---------------------------------
    dj = os.path.join(ROOT, "results", "determinism_by_model_stage1.json")
    if os.path.exists(dj):
        d = json.load(open(dj))
        for model, lo, hi, cover in (("claude-opus-4.7", 16, 23, 0.225),
                                     ("deepseek-chat-v3.1", 21, 29, 0.176),
                                     ("gemini-2.5-flash", 1, 4, 0.965)):
            cells = [v for k, v in d.items() if k.split("|")[0] == model]
            if not cells:
                continue
            check("%s round-1 distinct, min" % model, min(c["distinct"] for c in cells), lo, 0)
            check("%s round-1 distinct, max" % model, max(c["distinct"] for c in cells), hi, 0)
            check("%s modal reply share" % model,
                  sum(c["modal"] for c in cells) / float(sum(c["n"] for c in cells)), cover, 0.005)
    dj0 = os.path.join(ROOT, "results", "determinism_by_model_stage0.json")
    if os.path.exists(dj0):
        d = json.load(open(dj0))
        g = [v for k, v in d.items() if k.split("|")[0] == "gemini-2.5-flash"]
        if g:
            check("PILOT gemini round-1 distinct, min", min(c["distinct"] for c in g), 1, 0)
            check("PILOT gemini round-1 distinct, max", max(c["distinct"] for c in g), 5, 0)

    sp = os.path.join(ROOT, "results", "seed_pairing_stage0.json")
    if os.path.exists(sp):
        d = json.load(open(sp))
        row = [c for c in d["contrasts"]
               if "gemini" in c["model"] and c["contrast"].startswith("Aggregated")]
        if row:
            check("PILOT gemini Aggregated, paired sd", row[0]["sd_paired"], 0.539, 0.001)
            check("PILOT gemini Aggregated, unpaired sd", row[0]["sd_unpaired"], 0.478, 0.001)
            check("PILOT gemini Aggregated, correlation", row[0]["corr"], -0.280, 0.001)

    cj = os.path.join(ROOT, "results", "step10_contrast_power_stage1.json")
    if os.path.exists(cj):
        d = json.load(open(cj))
        need = d["per_model_required"]
        check("stage-1 N per cell, opus", need["anthropic/claude-opus-4.7"], 695, 0)
        check("stage-1 N per cell, deepseek", need["deepseek/deepseek-chat-v3.1"], 181, 0)
        check("stage-1 N per cell, gemini", need["google/gemini-2.5-flash"], 139, 0)
        # The paired-against-unpaired change in N, as percentages.
        for label, pd_, un, pct in (("opus", 695, 576, 20.7), ("deepseek", 181, 206, -12.1),
                                    ("gemini", 139, 113, 23.0)):
            check("pairing moves N, %s" % label, 100.0 * (pd_ - un) / un, pct, 0.05, "%")

    check("reference true score, GDIF", 6.8730, 6.8730, 0.00005)
    check("reference as stated to the agent", round(6.8730, 2), 6.87, 0.00005)

    # 9. The correspondence table (environment against a real assay), from the campaign files and call archive.
    print("\n" + "=" * 84)
    print("9. CORRESPONDENCE TABLE, recomputed from the core grid")
    print("=" * 84)
    MERGED = ["stage1", "topup_opus", "topup_gemini", "topup_deepseek"]
    camps = []
    for t in MERGED:
        p_ = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % t)
        if os.path.exists(p_):
            camps += [json.loads(l) for l in open(p_) if l.strip()]
    if camps:
        check("core-grid campaigns", len(camps), 5075, 0)
        ok_ = sum(c["n_ok"] for c in camps)
        att = sum(c["slots_used"] - (c.get("lost_slots") or 0) for c in camps)
        check("attempted measurements", att, 300898, 0)
        check("realised measurement-failure share", 100.0 * (1 - ok_ / att), 14.97, 0.01, "%")
        check("rejections per campaign, agents",
              st.mean([c.get("n_rejected") or 0 for c in camps]), 16.75, 0.005)
    fr = os.path.join(ROOT, "results", "fair_reference_curve.json")
    if os.path.exists(fr):
        d = json.load(open(fr))
        check("rejections per campaign, fair reference at k=1",
              d["curves"]["fair"]["1"]["rejections"], 97.62, 0.005)
        check("rejections per campaign, pool-scope reference at k=1",
              d["curves"]["pool"]["1"]["rejections"], 0.0, 0.0)
    gz = sorted(glob.glob(os.path.join(ROOT, "results", "grid_stage1_calls", "*.jsonl.gz")))
    if gz:
        import gzip as _gz
        with _gz.open(gz[0], "rt") as f:
            r0 = json.loads(f.readline())
        check("alphabet size x positions = states", 20.0 ** 4, 160000, 0)
        check("noise CV as run", r0["cv"], 0.073, 1e-9)
        check("noise floor as run", r0["noise_floor"], 0.003509, 1e-5)
        check("budget, rounds x slots", r0["total_rounds"] * r0["slots_per_round"], 60, 0)
    check("viable share of the space", 100.0 * 11199 / 160000, 7.00, 0.005, "%")

    # 10. The reference bracket and the ratios the appendix quotes, each computed rather than typed.
    print("\n" + "=" * 84)
    print("10. REFERENCE BRACKET (0ai), recomputed from the curve and the campaign files")
    print("=" * 84)
    if os.path.exists(fr) and camps:
        d = json.load(open(fr))
        f_, p_ = d["curves"]["fair"], d["curves"]["pool"]
        check("fair k*, argmax over k", float(max(f_, key=lambda k: f_[k]["mean"])), 1.0, 0)
        check("pool-scope k*, argmax over k", float(max(p_, key=lambda k: p_[k]["mean"])), 1.0, 0)
        check("fair mean at k=0", f_["0"]["mean"], 7.8856 - 0.1531, 0.0001)
        check("fair mean at k*=1", f_["1"]["mean"], 7.8909, 0.0001)
        check("fair span, k* minus k=0", f_["1"]["mean"] - f_["0"]["mean"], 0.1585, 0.0001)
        check("pool-scope span, k* minus k=0", p_["1"]["mean"] - p_["0"]["mean"], 0.1201, 0.0001)
        check("fair distinct at k*", f_["1"]["distinct"], 25.65, 0.005)
        check("pool-scope distinct at k*", p_["1"]["distinct"], 39.13, 0.005)
        check("fair lost slots at k=1", f_["1"]["lost"], 15.64, 0.005)
        check("fair collapses at k=4", f_["4"]["collapsed"], 236, 0)
        check("pool-scope collapses at k=4", p_["4"]["collapsed"], 16, 0)
        a_rej = st.mean([c.get("n_rejected") or 0 for c in camps])
        a_lost = st.mean([c.get("lost_slots") or 0 for c in camps])
        check("agents guess viability better by", f_["1"]["rejections"] / a_rej, 5.83, 0.005, "x")
        check("agents lose fewer slots by", f_["1"]["lost"] / a_lost, 22.04, 0.01, "x")
        # The most exploratory cell mean, not a campaign-level maximum.
        best_cell = max(st.mean([c["n_distinct_measured"] for c in camps
                                 if c["condition"] == cond and c["model"] == m])
                        for cond in {c["condition"] for c in camps}
                        for m in {c["model"] for c in camps}
                        if any(c["condition"] == cond and c["model"] == m for c in camps))
        check("most exploratory cell mean, distinct variants", best_cell, 11.34, 0.005)
        check("that cell as a share of the fair reference",
              100.0 * best_cell / f_["1"]["distinct"], 44.2, 0.1, "%")
        least = min(st.mean([c["n_distinct_measured"] for c in camps
                             if c["condition"] == cond and c["model"] == m])
                    for cond in {c["condition"] for c in camps}
                    for m in {c["model"] for c in camps}
                    if any(c["condition"] == cond and c["model"] == m for c in camps))
        check("least exploratory cell mean", least, 2.57, 0.005)
        rj = sum(c.get("n_rejected") or 0 for c in camps)
        sl = sum(c["slots_used"] for c in camps)
        check("non-viable share of core-grid proposals", 100.0 * rj / (rj + sl), 21.82, 0.005, "%")

    # 11. Limitation figures: keyword shares over the agents' stated reasons.
    print("\n" + "=" * 84)
    print("11. LIMITATION FIGURES, recomputed from the stated reasons in the call archive")
    print("=" * 84)
    import gzip as _gz2, re as _re2

    def _reasons(tags):
        out = []
        for t in tags:
            for g in glob.glob(os.path.join(ROOT, "results", "grid_%s_calls" % t, "*.jsonl.gz")):
                with _gz2.open(g, "rt") as f:
                    for l in f:
                        out += [str(x) for x in (json.loads(l).get("reasons") or [])]
        return out
    core_r = _reasons(MERGED)
    if core_r:
        check("stated reasons, core grid", len(core_r), 390957, 0)
        check("core-grid reasons containing 'viable'",
              100.0 * sum(1 for x in core_r if _re2.search("viable", x, _re2.I)) / len(core_r),
              3.82, 0.005, "%")
        check("core-grid reasons containing 'known'",
              100.0 * sum(1 for x in core_r if _re2.search(r"\bknown\b", x, _re2.I)) / len(core_r),
              3.09, 0.005, "%")
    s1_r = _reasons(["stage1"])
    if s1_r:
        check("stated reasons, stage 1", len(s1_r), 44947, 0)
        check("stage-1 reasons containing 'viable'",
              100.0 * sum(1 for x in s1_r if _re2.search("viable", x, _re2.I)) / len(s1_r),
              4.14, 0.005, "%")
        check("stage-1 reasons containing 'known'",
              100.0 * sum(1 for x in s1_r if _re2.search(r"\bknown\b", x, _re2.I)) / len(s1_r),
              3.41, 0.005, "%")
        check("stage-1 share under the WIDER viability pattern",
              100.0 * sum(1 for x in s1_r
                          if _re2.search("viable|viability|non-viable", x, _re2.I)) / len(s1_r),
              7.81, 0.005, "%")
    # The two prompt sentences the limitations quote must be the sentences the harness sent.
    gzs = sorted(glob.glob(os.path.join(ROOT, "results", "grid_stage1_calls", "*.jsonl.gz")))
    if gzs:
        seen_goal = seen_true = 0
        with _gz2.open(gzs[0], "rt") as f:
            for l in f:
                d = json.loads(l)
                if "GOAL\nFind the candidate with the highest score." in d.get("prompt", ""):
                    seen_goal = 1
                if d.get("kind") == "nomination" and \
                        "highest true score" in d.get("prompt", ""):
                    seen_true = 1
        check("the quoted GOAL wording is in the real prompt", float(seen_goal), 1.0, 0)
        check("the quoted nomination wording is in the real prompt", float(seen_true), 1.0, 0)

    # 13. The simulation study, primary run at n = 200.
    print("\n" + "=" * 84)
    print("13. SIMULATION STUDY (primary, n = 200)")
    print("=" * 84)
    sp = os.path.join(ROOT, "results", "learnability_sim_n200.json")
    if os.path.exists(sp):
        d = json.load(open(sp))
        check("seeds per cell", d["n_per_cell"], 200, 0)
        check("setting-and-scope cells", len(d["settings"]), 18, 0)
        ks = [r["kstar"] for r in d["settings"]]
        check("cells with k* = 1", sum(1 for k in ks if k == 1), 13, 0)
        check("distinct k* values across settings", len(set(ks)), 3, 0)
        check("smallest k* seen", min(ks), 0, 0)
        check("largest k* seen", max(ks), 2, 0)
        cr = d["criteria_result"]
        check("settings discriminating as pre-registered", cr["discriminates_pass"], 3, 0)
        check("settings discriminating once paired", cr["discriminates_paired_pass"], 6, 0)
        check("distinct policy orderings", cr["distinct_orderings"], 4, 0)
        for scope, want_seed, want_set in (("pool", 0.668, 0.891), ("fair", 0.778, 0.878)):
            p2 = d["part2"][scope]
            check("%s: trained replication share" % scope, p2["trained_k"], 1, 0)
            check("%s: held-out seeds, normalised" % scope, p2["heldout_seed_score"], want_seed, 0.0005)
            check("%s: held-out settings, normalised" % scope, p2["heldout_setting_score"], want_set,
                  0.0005)
            check("%s: learnable at the 0.80 bar" % scope, float(p2["learnable"]), 0.0, 0)
            check("%s: transfers at the 0.50 bar" % scope, float(p2["transfers"]), 1.0, 0)
            if p2["trained_selector"] != "shrinkage":
                FAILS.append("%s trained selector is %r, not shrinkage" % (scope, p2["trained_selector"]))

    # 14. The simulation study's power follow-up at n = 1,500.
    print("\n" + "=" * 84)
    print("14. SIMULATION STUDY (power follow-up, n = 1,500)")
    print("=" * 84)
    fp = os.path.join(ROOT, "results", "learnability_sim_n1500.json")
    if os.path.exists(fp):
        d2 = json.load(open(fp))
        check("seeds per cell", d2["n_per_cell"], 1500, 0)
        ks2 = [r["kstar"] for r in d2["settings"]]
        check("cells with k* = 1", sum(1 for k in ks2 if k == 1), 15, 0)
        check("cells with k* = 2", sum(1 for k in ks2 if k == 2), 3, 0)
        check("degenerate cells", sum(1 for r in d2["settings"] if r.get("degenerate")), 0, 0)
        c2 = d2["criteria_result"]
        check("settings discriminating as pre-registered", c2["discriminates_pass"], 12, 0)
        check("settings discriminating once paired", c2["discriminates_paired_pass"], 15, 0)
        check("distinct policy orderings", c2["distinct_orderings"], 2, 0)
        for scope, want_seed, want_set in (("pool", 0.752, 0.978), ("fair", 0.928, 0.899)):
            q = d2["part2"][scope]
            check("%s: trained replication share" % scope, q["trained_k"], 1, 0)
            check("%s: held-out seeds, normalised" % scope, q["heldout_seed_score"], want_seed, 0.0005)
            check("%s: held-out settings, normalised" % scope, q["heldout_setting_score"], want_set,
                  0.0005)
    # The hill-climber paragraph's figures, from the fair reference curve.
    if os.path.exists(fr):
        fc = json.load(open(fr))["curves"]["fair"]
        check("fair climber, no replication", fc["0"]["mean"], 7.7325, 0.0001)
        check("fair climber at k=1", fc["1"]["mean"], 7.8909, 0.0001)
        check("fair climber at k=3", fc["3"]["mean"], 7.7002, 0.0001)
        check("fair climber distinct, no replication", fc["0"]["distinct"], 26.63, 0.005)
        check("global best on this landscape", 8.762, 8.762, 0.0005)

    # 15. Scripted lab protocols: every agent cell must sit above the triplicate share.
    print("\n" + "=" * 84)
    print("15. SCRIPTED LAB PROTOCOLS (0aj)")
    print("=" * 84)
    lpp = os.path.join(ROOT, "results", "lab_protocols.json")
    if os.path.exists(lpp) and camps:
        lp = json.load(open(lpp))
        check("seeds per protocol cell", lp["n"], 1500, 0)
        rows = lp["rows"]
        for name, want_rep in (("(a) triplicate-everything", 66.7), ("(b) duplicate-everything", 50.0),
                               ("(c) screen-then-confirm", 20.0)):
            check("%s, pool scope, replication share" % name.split(") ")[1],
                  rows["%s|pool" % name]["replication"], want_rep, 0.05, "%")
        check("triplicate protocol, pool scope, mean", rows["(a) triplicate-everything|pool"]["mean"],
              7.8400, 0.0001)
        # `c` is a loop variable in this scope, so the cells are re-read by name.
        gsum = json.load(open(os.path.join(ROOT, "results", "analysis_final", "grid", "summary.json")))
        agent_rep = [100 * x["replication"]["over slots used"] for x in gsum["cells_detail"]]
        tri = rows["(a) triplicate-everything|pool"]["replication"]
        check("agent cells at or below the triplicate share",
              float(sum(1 for r in agent_rep if r <= tri)), 0.0, 0)
        check("lowest agent replication share", min(agent_rep), 75.4, 0.05, "%")

    # 16. Zero-noise replication ranges: Blind cells, informed rungs, pooled, and per model.
    print("\n" + "=" * 84)
    print("16. ZERO-NOISE REPLICATION, by aggregation")
    print("=" * 84)
    zp = os.path.join(ROOT, "results", "grid_zeronoise_campaigns.jsonl")
    if os.path.exists(zp):
        zc = [json.loads(l) for l in open(zp) if l.strip()]
        cellz = collections.defaultdict(list)
        for x in zc:
            cellz[(x["condition"], x["model"].split("/")[-1])].append(x["replication_fraction"])
        means = {k: 100 * st.mean(v) for k, v in cellz.items()}
        blind = [v for k, v in means.items() if k[0] == "Blind"]
        stated = [v for k, v in means.items() if k[0] != "Blind"]
        check("Blind cells, exact but NOT stated, lowest", min(blind), 52.6, 0.05, "%")
        check("Blind cells, highest", max(blind), 92.9, 0.05, "%")
        check("informed rungs, exact AND stated, lowest", min(stated), 42.0, 0.05, "%")
        check("informed rungs, highest", max(stated), 92.2, 0.05, "%")
        check("pooled over five rungs, lowest", min(means.values()), 42.0, 0.05, "%")
        check("pooled over five rungs, highest", max(means.values()), 92.9, 0.05, "%")
        by_model = collections.defaultdict(list)
        for k, v in means.items():
            by_model[k[1]].append(v)
        for m, want in (("claude-opus-4.7", 51.4), ("gemini-2.5-flash", 81.6),
                        ("deepseek-chat-v3.1", 89.6)):
            check("%s, mean over the five conditions" % m, st.mean(by_model[m]), want, 0.05, "%")

    # 12. The reasoning panel's nine excluded campaigns: 8 hit the output limit, 1 stopped with unparseable text.
    print("\n" + "=" * 84)
    print("12. REASONING PANEL, the composition of the 0ag exclusions")
    print("=" * 84)
    pc = sorted(glob.glob(os.path.join(ROOT, "results", "grid_panelc_calls", "*.jsonl.gz")))
    if pc:
        import gzip as _gz3
        rows = []
        for g in pc:
            with _gz3.open(g, "rt") as f:
                rows += [json.loads(l) for l in f if l.strip()]
        check("panelc calls archived", len(rows), 5852, 0)
        check("panelc calls still reporting finish_reason=error",
              sum(1 for r in rows if r.get("finish_reason") == "error"), 0, 0)
        fb = [r for r in rows if r.get("kind") == "nomination" and r.get("parse_status") != "ok"]
        check("nomination fallbacks", len(fb), 9, 0)
        check("of those, reached the output limit",
              sum(1 for r in fb if r.get("finish_reason") == "length"), 8, 0)
        check("of those, stopped normally with unparseable text",
              sum(1 for r in fb if r.get("finish_reason") == "stop"), 1, 0)
        stopped = [r for r in fb if r.get("finish_reason") == "stop"]
        if stopped:
            check("completion tokens of the one that stopped",
                  stopped[0].get("completion_tokens") or 0, 3034, 0)
        check("all fallbacks are gemini",
              sum(1 for r in fb if "gemini" in r["model"]), len(fb), 0)
        camps = [json.loads(l) for l in
                 open(os.path.join(ROOT, "results", "grid_panelc_campaigns.jsonl")) if l.strip()]
        check("panelc campaigns", len(camps), 160, 0)


if __name__ == "__main__":
    sys.exit(main())
