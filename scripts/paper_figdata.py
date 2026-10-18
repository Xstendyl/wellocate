#!/usr/bin/env python3
"""The per-model numbers behind the paper's headline figures, with 95% seed-bootstrap intervals. No model calls.

Five models on the grid with the Blind prompt: GPT-6.1 Sol, Gemini 3.1 Pro, Gemini 2.5 Flash and DeepSeek V3.1
(same prompt options), and Opus 4.7 (whose prompt differs only by the truthful re-ask line). Per model: the
re-testing share over the budget and over slots not lost, final pick, exploration loss, selection loss and
distinct candidates, plus the release month, reasoning setting and median reasoning tokens per call for the
model table. The build refuses unless every share and pick equals results/analysis_0an7.json.

Usage: python3 scripts/paper_figdata.py      (writes results/paper_figdata.json)
"""
import glob, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_0an7 as A7                                   # noqa: E402
import analyse_0al as A0L                                   # noqa: E402

MODELS = [("Opus 4.7", "anthropic/claude-opus-4.7", "panelA0_original", ("cells", "gem|grid_blind", "comparators", "Panel A0|claude-opus-4.7")),
          ("Gemini 2.5 Flash", "google/gemini-2.5-flash", "gen_0an_f0_control",
           ("cells", "gem|grid_blind", "comparators", "0an F0 control|gemini-2.5-flash")),
          ("DeepSeek V3.1", "deepseek/deepseek-chat-v3.1", "gen_0an_f0_control",
           ("cells", "gem|grid_blind", "comparators", "0an F0 control|deepseek-chat-v3.1")),
          ("GPT-6.1 Sol", "openai/gpt-6.1-sol", "gen_0an7_sol_grid_blind+gen_0an7_sol_grid_blind_rerun+gen_0an7_sol_grid_blind_cont",
           ("cells", "sol|grid_blind")),
          ("Gemini 3.1 Pro", "google/gemini-3.1-pro-preview",
           "gen_0an7_gem_grid_blind+gen_0an7_gem_grid_blind_rerun+gen_0an7_gem_grid_blind_cont", ("cells", "gem|grid_blind"))]


def main():
    a7 = json.load(open(os.path.join(ROOT, "results", "analysis_0an7.json")))
    out = dict(models={}, references=dict(guessing_pick=a7["references"]["grid"]["guessing"]["pick"],
                                          informed_pick=a7["references"]["grid"]["informed"]["pick"],
                                          band=[a7["band_grid"]["lower"]["share_budget"], a7["band_grid"]["upper"]["share_budget"]]))
    for name, model, tags, path in MODELS:
        rows = [r for t in tags.split("+") for r in A7.rows_of(t) if r["model"] == model]
        reg = a7
        for p in path:
            reg = reg[p]
        d = dict(n=len(rows), source=tags.split("+")[0])
        for key, f in (("share_budget", A7.share_b), ("share_nonlost", A7.share_n), ("pick", lambda r: r["nominated_true"]),
                       ("exploration_shortfall", lambda r: r["exploration_shortfall"]),
                       ("selection_shortfall", lambda r: r["selection_shortfall"]),
                       ("distinct", lambda r: r["n_distinct_measured"])):
            v = [f(r) for r in rows]
            d[key] = dict(mean=st.mean(v), ci=A7.ci(v, "figdata|%s|%s" % (name, key)))
        for key in ("share_budget", "share_nonlost", "pick", "exploration_shortfall", "selection_shortfall", "distinct"):
            if abs(d[key]["mean"] - reg[key]) > 1e-9 or d["n"] != reg["n"]:
                raise SystemExit("REFUSED: %s %s does not equal analysis_0an7.json" % (name, key))
        calls = [c for t in tags.split("+") for c in A0L.calls(t)
                 if c.get("model") == model and (c.get("cell") or c.get("rung") or "").lower() == "blind"]
        toks = [int(c.get("reasoning_tokens") or 0) for c in calls]
        man = json.load(open(os.path.join(ROOT, "results", "grid_%s_manifest.json" % tags.split("+")[0])))
        released = next((m["released"] for m in man.get("models", []) if m.get("id") == model), None)
        d.update(calls=len(calls), reasoning_tokens_median=st.median(toks), reasoning_tokens_max=max(toks),
                 released=released, reasoning_effort=man.get("reasoning_effort"))
        out["models"][name] = d
        print("%-17s n=%3d share %5.1f%% [%5.1f, %5.1f]  pick %.3f [%.3f, %.3f]  exploration %.3f [%.3f, %.3f]  "
              "selection %.3f [%.3f, %.3f]" % (name, d["n"], d["share_budget"]["mean"], *d["share_budget"]["ci"],
                                               d["pick"]["mean"], *d["pick"]["ci"], d["exploration_shortfall"]["mean"],
                                               *d["exploration_shortfall"]["ci"], d["selection_shortfall"]["mean"],
                                               *d["selection_shortfall"]["ci"]))
    json.dump(out, open(os.path.join(ROOT, "results", "paper_figdata.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
