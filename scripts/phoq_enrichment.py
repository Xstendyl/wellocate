#!/usr/bin/env python3
"""Round-1 enrichment diagnostic on PhoQ: how often does the model propose PhoQ's optimum in round 1?

On GB1 the model proposes the global optimum far above chance in round 1, a sign the landscape is known to it.
This runs the same design on PhoQ (same model, temperature and cells, sigma derived from the landscape,
round 1 only, one ask per campaign), and re-scores GB1 under the same one-ask rule for comparison.
"""
import argparse, collections, json, math, os, statistics as st, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import landscape as L, prompts, llm, llm_policy, policies as P, campaign as C

ENV = os.path.expanduser("<sibling-project>/.env")   # the key is read at runtime, never copied
MODEL = "anthropic/claude-opus-4.7"
CELLS = [("blind", 2.0), ("blind", 8.0), ("instructed", 2.0), ("instructed", 8.0)]
SEEDS = (0, 1, 2, 3, 4)
SLOTS, ROUNDS, TOTAL = 4, 15, 60


def sigma_unit(ls, n=400):
    """median(top1 - top2) of true values over a 60-measurement random campaign.

    Same calculation as the 'random from pool' row of scripts/falsify.py.
    """
    ps = tuple(sorted(ls.pool))
    gaps = []
    for i in range(n):
        r = C.run(ls.fitness, ls.pool, P.RandomPolicy(0), 0.0, 10_000 + i, 0.0, pool_sorted=ps)
        tv = sorted((ls.fitness[s] for s in {h.seq for h in r.history if h.outcome == "ok"}),
                    reverse=True)
        if len(tv) >= 2:
            gaps.append(tv[0] - tv[1])
    # statistics.median, to match falsify.py exactly.
    return st.median(gaps)


def enrichment(hits, n_camp, n_pool, draws):
    obs = hits / n_camp
    chance = float(draws) / n_pool
    se = math.sqrt(obs * (1 - obs) / n_camp) if 0 < obs < 1 else 1.0 / n_camp
    return obs, chance, obs / chance, se / chance


def gb1_one_ask_rate():
    """GB1's rate under PhoQ's rule: the first round-1 ask of each campaign only."""
    p = os.path.join(ROOT, "results", "pilot_opus47_calls.jsonl")
    rows = [json.loads(l) for l in open(p)]
    first = {}
    for r in rows:
        if r.get("kind") == "nomination" or r.get("round") != 1:
            continue
        k = (r["rung"], r["ratio"], r["campaign_seed"])
        if k not in first:
            first[k] = r
    hits = sum(1 for r in first.values() if "FWAA" in (r.get("parsed") or []))
    n4 = sum(1 for r in first.values() if r.get("n_slots") == SLOTS)
    return hits, len(first), n4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--dry", action="store_true", help="print one prompt and the plan, spend nothing")
    a = ap.parse_args()

    ph = L.load("phoq")
    pool_sorted = tuple(sorted(ph.pool))
    best = max(ph.pool, key=lambda s: ph.fitness[s])
    top10 = set(sorted(ph.pool, key=lambda s: -ph.fitness[s])[:10])
    unit = sigma_unit(ph)
    print("=" * 88)
    print("PHOQ ROUND-1 ENRICHMENT  model=%s  temp=0.0" % a.model)
    print("=" * 88)
    print("pool %d of %d | argmax %s (%.2f) | parent AVST (%.2f) | sigma unit %.4f"
          % (len(ph.pool), len(ph.fitness), best, ph.fitness[best], ph.fitness["AVST"], unit))
    print("cells %s x seeds %s = %d campaigns, one 4-slot ask each"
          % (CELLS, list(SEEDS), len(CELLS) * len(SEEDS)))

    if a.dry:
        print("\n--- the exact round-1 prompt, blind, ratio 2.0 ---")
        print(prompts.build("blind", [], 1, ROUNDS, SLOTS, TOTAL, 2.0 * unit,
                            landscape="phoq_bio", total=TOTAL))
        return 0

    out, spend = [], 0.0
    for rung, ratio in CELLS:
        sigma = ratio * unit
        prompt = prompts.build(rung, [], 1, ROUNDS, SLOTS, TOTAL, sigma,
                               landscape="phoq_bio", total=TOTAL)
        for seed in SEEDS:
            t0 = time.time()
            call = llm.complete(prompt, a.model, temperature=0.0, env_file=ENV)
            parsed, status, notes = llm_policy.parse(call.text, SLOTS)
            seqs = [s for s, _ in parsed]
            spend += call.cost_usd or 0.0
            rec = dict(landscape="phoq", rung=rung, ratio=ratio, sigma=sigma, round=1,
                       campaign_seed=seed, model=a.model, temperature=0.0, n_slots=SLOTS,
                       parsed=seqs, reasons=[r for _, r in parsed], parse_status=status,
                       parse_notes=notes, raw_response=call.text, prompt=prompt,
                       prompt_tokens=call.prompt_tokens, completion_tokens=call.completion_tokens,
                       cost_usd=call.cost_usd, latency_ms=int(1000 * (time.time() - t0)),
                       in_pool=[s for s in seqs if s in ph.pool],
                       hit_argmax=best in seqs, kind="round")
            out.append(rec)
            print("  %-11s r%.0f seed%d  %-28s %s%s"
                  % (rung, ratio, seed, ",".join(seqs) or "(none)", status,
                     "  <-- ARGMAX" if rec["hit_argmax"] else ""))

    dest = os.path.join(ROOT, "results", "step6_phoq_round1_calls.jsonl")
    with open(dest, "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")

    n = len(out)
    hits = sum(1 for r in out if r["hit_argmax"])
    obs, chance, enr, enr_se = enrichment(hits, n, len(ph.pool), SLOTS)
    inpool = [s for r in out for s in r["in_pool"]]
    n_t10 = sum(1 for s in inpool if s in top10)
    t10_enr = ((n_t10 / len(inpool)) / (10.0 / len(ph.pool))) if inpool else float("nan")

    g_hits, g_n, g_n4 = gb1_one_ask_rate()
    g_obs, g_chance, g_enr, g_enr_se = enrichment(g_hits, g_n, len(L.load("gb1").pool), SLOTS)

    print("\n" + "=" * 88)
    print("RESULT")
    print("=" * 88)
    print("PhoQ campaigns proposing %s at round 1        %d of %d = %.1f%%" % (best, hits, n, 100*obs))
    print("chance for %d draws from a %d pool             %.4f%%" % (SLOTS, len(ph.pool), 100*chance))
    print("PhoQ ENRICHMENT (argmax, one ask)              %.1fx  (+-%.1f)" % (enr, enr_se))
    print("PhoQ round-1 in-pool proposals                 %d of %d" % (len(inpool), n * SLOTS))
    print("of those, in the pool's top 10                 %d" % n_t10)
    print("PhoQ ENRICHMENT (top 10)                       %.1fx" % t10_enr)
    print()
    print("GB1 under the SAME one-ask rule                %d of %d = %.1f%%" % (g_hits, g_n, 100*g_obs))
    print("GB1 ENRICHMENT (argmax, one ask)               %.1fx  (+-%.1f)" % (g_enr, g_enr_se))
    print("  (GB1's published 1,584x counted every round-1 ask including re-asks; %d of its %d"
          % (g_n4, g_n))
    print("   first asks were 4-slot, the rest were re-asks for fewer slots)")
    print()
    if enr > 100:
        print("VERDICT: PhoQ is CONTAMINATED at round 1. The cold recall probe was the wrong test.")
        print("PhoQ cannot serve as the uncontaminated landscape, and a second contaminated")
        print("reference landscape is itself a reportable result: recall-on-demand and")
        print("proposal-in-context come apart, so absence of recall does not license a benchmark.")
    elif enr > 10:
        print("VERDICT: PhoQ shows MATERIAL round-1 enrichment, smaller than GB1's. Usable only")
        print("with the enrichment reported alongside every PhoQ result.")
    else:
        print("VERDICT: PhoQ round-1 enrichment is small. It survives as a reference landscape,")
        print("and the recall probe and this diagnostic agree for once.")
    print("\nspend this run: $%.4f  |  saved %s" % (spend, dest))
    json.dump(dict(model=a.model, n=n, hits=hits, obs=obs, chance=chance, enrichment=enr,
                   enrichment_se=enr_se, argmax=best, pool=len(ph.pool), sigma_unit=unit,
                   inpool=len(inpool), top10_hits=n_t10, top10_enrichment=t10_enr,
                   gb1_one_ask_hits=g_hits, gb1_one_ask_n=g_n, gb1_one_ask_enrichment=g_enr,
                   spend_usd=spend),
              open(os.path.join(ROOT, "results", "step6_phoq_enrichment.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
