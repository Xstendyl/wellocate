#!/usr/bin/env python3
"""The baseline scorecard of Wellocate per split, and the environment's measured throughput.

Built from the chunks scripts/wellocate_chunks.py writes (one policy on one split, every episode, through the
step API); run that script, which calls build() here when every chunk is complete. Baselines: random, the
guessing rule at its best k, the informed rule at its best k, the model-guided policy (k = 1 with
confirmation) and a simple confirmation policy (4 slots, a reference point, not tuned), each scored by wellocate.evaluate against the
references on the same episodes. The paper's LLM results sit beside them as read-only rows on the paper splits,
read from results/analysis_0an7.json and results/analysis_0an6.json; they are not rerun.

Writes results/wellocate_scorecard.json.
"""
import json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import campaign as C                                   # noqa: E402
from wellocate import baselines as B, scorecard as S, splits as SP  # noqa: E402

OUT = os.path.join(ROOT, "results", "wellocate_scorecard.json")
BASELINES = [("random", "random"), ("guessing at k*", None), ("informed at k*", None), ("model-guided", "model_guided"),
             ("simple confirmation (4 slots), a reference point, not tuned", "confirmation_4")]


def llm_rows():
    a7 = json.load(open(os.path.join(ROOT, "results", "analysis_0an7.json")))
    a6 = json.load(open(os.path.join(ROOT, "results", "analysis_0an6.json")))
    g = a7["cells"]["gem|grid_blind"]["comparators"]
    row = lambda c, src: dict(pick=c["pick"], pick_ci=c.get("pick_ci"), share_budget=c["share_budget"],
                              share_budget_ci=c.get("share_budget_ci"), n=c.get("n"), source=src)
    grid = {"GPT-6.1 Sol": row(a7["cells"]["sol|grid_blind"], "0an.7"),
            "Gemini 3.1 Pro": row(a7["cells"]["gem|grid_blind"], "0an.7"),
            "Claude Opus 4.7": row(g["Panel A0|claude-opus-4.7"], "Panel A0"),
            "Gemini 2.5 Flash": row(g["0an F0 control|gemini-2.5-flash"], "0an F0 control"),
            "DeepSeek V3.1": row(g["0an F0 control|deepseek-chat-v3.1"], "0an F0 control")}
    gb1 = {"GPT-6.1 Sol": row(a7["cells"]["sol|gb1_blind"], "0an.7"),
           "Gemini 3.1 Pro": row(a7["cells"]["gem|gb1_blind"], "0an.7")}
    for m, name in (("Opus", "Claude Opus 4.7"), ("Gemini", "Gemini 2.5 Flash"), ("DeepSeek", "DeepSeek V3.1")):
        c = a6["cells"][m]
        gb1[name] = dict(pick=c["partner_pick"], pick_ci=None, share_budget=c["partner_share"], share_budget_ci=None,
                         n=c["pairs"], source="0an.6 Blind control (%s)" % c["control"])
    return {"nk:paper": grid, "gb1:paper": gb1}


def throughput():
    """Episodes and agent steps per second through the step API, one core, guessing rule, on the paper's grid
    (one landscape, built before the clock starts; building an NK landscape takes about half a second)."""
    from wellocate import env as W
    eps = SP.episodes("nk:paper", 200)
    S.run_episode(B.guessing(1), eps[0][0], eps[0][1])
    t0, steps = time.time(), 0
    for inst, seed in eps:
        env = W.Wellocate(inst, seed=seed)
        pol = B.guessing(1)(env.env)
        obs = env.observation
        while obs.phase in ("round", "replacement"):
            obs, _r, _d, _i = env.step(pol.propose(obs.view, obs.n_slots, obs.exclude, obs.phase))
            steps += 1
        env.nominate(W.shrinkage_nominee(obs.view))
    dt = time.time() - t0
    e0 = W.Wellocate(eps[0][0], seed=eps[0][1]).env
    t1 = time.time()
    for _inst, seed in eps:
        C.run(e0.fit, e0.pool, B.guessing(1)(e0), 0.0, seed, 0.15, pool_sorted=e0.ps, nomination="shrinkage",
              prior="empirical", noise_model="multiplicative", cv=0.073, noise_floor=W.NOISE_FLOOR)
    dt2 = time.time() - t1
    return dict(episodes_per_s=len(eps) / dt, steps_per_s=steps / dt, steps_per_episode=steps / len(eps),
                harness_campaigns_per_s=len(eps) / dt2, note="one core, guessing rule k = 1, landscape already built")


def build(read):
    out = dict(splits={}, llm_reference_rows=llm_rows(), throughput=throughput(),
               note="baselines run through the step API; LLM rows are read-only, from the paper's campaigns")
    import wellocate_chunks as WC
    for split in WC.SCORECARD_SPLITS:
        g = {k: read((split, "guessing_k%d" % k, "assay")) for k in S.KS}
        i = {k: read((split, "informed_k%d" % k, "assay")) for k in S.KS}
        ref = S.refs_from(g, i, read((split, "model_guided", "assay")))
        rows = {name: (read((split, key, "assay")) if key else
                       (g[ref["guessing_kstar"]] if name.startswith("guessing") else i[ref["informed_kstar"]]))
                for name, key in BASELINES}
        out["splits"][split] = dict(
            baselines={name: S.evaluate(None, split, refs={split: ref}, rows={split: r})[split] for name, r in rows.items()},
            guessing_kstar=ref["guessing_kstar"], informed_kstar=ref["informed_kstar"], best_scripted=ref["best_scripted"],
            band=S.registered_band(split, "assay"),
            n=SP.load()["splits"][split]["episodes"])
    json.dump(out, open(OUT, "w"), indent=1)
    tp = out["throughput"]
    print("throughput: %.0f episodes/s, %.0f steps/s through the step API; harness loop %.0f campaigns/s"
          % (tp["episodes_per_s"], tp["steps_per_s"], tp["harness_campaigns_per_s"]))
    for s, r in out["splits"].items():
        b = r["best_scripted"]
        print("\n%s (n = %d; guessing k* = %d, informed k* = %d; best scripted: %s, pick %.3f, share %.1f%%%s)"
              % (s, r["n"], r["guessing_kstar"], r["informed_kstar"], b["policy"], b["pick"], b["share_budget"],
                 "; band %.2f%% to %.2f%% (%s)" % (r["band"]["lower"], r["band"]["upper"], r["band"]["source"])
                 if r["band"] else ""))
        for name, sc in r["baselines"].items():
            print("  %-30s pick %.3f [%.3f, %.3f]  regret %+.3f  share %5.1f%%  expl %.3f  sel %.3f  distinct %4.1f  "
                  "lost %.2f%s%s" % (name[:30], sc["pick"]["mean"], sc["pick"]["ci"][0], sc["pick"]["ci"][1],
                                            sc["regret_vs_informed"]["mean"], sc["share_budget"]["mean"],
                                            sc["exploration_shortfall"]["mean"], sc["selection_shortfall"]["mean"],
                                            sc["distinct"]["mean"], sc["lost_slots"]["mean"],
                                            "  band %s" % sc["band"]["label"] if "band" in sc else "",
                                            ", %d collapsed" % sc["collapsed"] if sc["collapsed"] else ""))


if __name__ == "__main__":
    print("Run scripts/wellocate_chunks.py, which builds this file when every chunk is complete.")
