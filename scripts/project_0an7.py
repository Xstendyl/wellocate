#!/usr/bin/env python3
"""Project the cost per candidate model for the new-model design, from the existing campaign logs and probes.

Design per model: Blind on the grid (n = 60), Blind on scrambled GB1 (n = 30), menu tool on scrambled GB1 (n = 30).
Calls, prompt tokens and answer tokens per call come from the same arms already run, under a high (Opus 4.7) and
a low (Gemini 2.5 Flash) behaviour profile. Reasoning tokens per call come from probes at each model's lowest
setting. Prices are OpenRouter's listed per-token prices; cache discounts are ignored.

Usage: python3 scripts/project_0an7.py      (writes results/project_0an7.json)
"""
import json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyse_0al as A0                                                 # noqa: E402

ARMS = (("grid Blind", "panelA0_original", "blind", 60), ("GB1 Blind", "gen_r_gb1scr", "blind", 30),
        ("GB1 Menu", "gen_0an6_gb1_menu", None, 30))
PROFILES = {"high (Opus 4.7 pattern)": "anthropic/claude-opus-4.7", "low (Gemini 2.5 Flash pattern)": "google/gemini-2.5-flash"}


def usage(tag, cond, model):
    calls, camp = [], {}
    for c in A0.calls(tag):
        if c["model"] != model or (cond and cond not in (c.get("cell") or "").lower()):
            continue
        calls.append(c)
        camp[c["campaign_seed"]] = camp.get(c["campaign_seed"], 0) + 1
    return dict(calls_per_campaign=st.mean(camp.values()), prompt_tokens=st.mean(c.get("prompt_tokens") or 0 for c in calls),
                answer_tokens=st.mean((c.get("completion_tokens") or 0) - (c.get("reasoning_tokens") or 0) for c in calls))


def main():
    probes = []
    for f in ("probe_0an7.json", "probe_0an7_extra.json"):
        probes += json.load(open(os.path.join(ROOT, "results", f)))["probes"]
    lowest = lambda m: [p["reasoning_tokens"] for p in probes if p["model"] == m and p.get("http") == 200
                        and (p.get("reasoning_param") or {}).get("effort") == "minimal"]
    models = {
        "openai/gpt-6.1-sol": dict(price_in=2e-6, price_out=10e-6, reasoning=st.mean(lowest("openai/gpt-6.1-sol")),
                                   basis="probed at effort minimal"),
        "google/gemini-3.1-pro-preview": dict(price_in=2e-6, price_out=12e-6,
                                              reasoning=st.mean(lowest("google/gemini-3.1-pro-preview")),
                                              basis="probed at effort minimal"),
        "anthropic/claude-opus-5.5": dict(price_in=4e-6, price_out=20e-6, reasoning=0.0,
                                          basis="priced only; assumes reasoning off, as for Opus 4.7"),
        "openai/gpt-6-astra": dict(price_in=10e-6, price_out=50e-6, reasoning=0.0,
                                   basis="priced only; assumes no reasoning tokens at minimal effort, as GPT-6.1 Sol"),
    }
    use = {(arm, prof): usage(tag, cond, m) for arm, tag, cond, _n in ARMS for prof, m in PROFILES.items()}
    out = dict(design={arm: n for arm, _t, _c, n in ARMS}, usage={"%s|%s" % k: v for k, v in use.items()}, models={})
    for mid, m in models.items():
        d = dict(m)
        for prof in PROFILES:
            tot = 0.0
            for arm, _t, _c, n in ARMS:
                u = use[(arm, prof)]
                tot += n * u["calls_per_campaign"] * (u["prompt_tokens"] * m["price_in"]
                                                      + (u["answer_tokens"] + m["reasoning"]) * m["price_out"])
            d[prof] = tot
        out["models"][mid] = d
        print("%-32s reasoning/call %6.1f (%s): projected $%.2f to $%.2f for 120 campaigns"
              % (mid, m["reasoning"], m["basis"], d["low (Gemini 2.5 Flash pattern)"], d["high (Opus 4.7 pattern)"]))
    json.dump(out, open(os.path.join(ROOT, "results", "project_0an7.json"), "w"), indent=1)
    for k, v in out["usage"].items():
        print("   %-46s %.1f calls/campaign, %.0f prompt tokens/call, %.0f answer tokens/call"
              % (k, v["calls_per_campaign"], v["prompt_tokens"], v["answer_tokens"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
