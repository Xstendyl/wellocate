#!/usr/bin/env python3
"""Attractor basins on each Wellocate landscape and where campaigns ended up. Descriptive; no model is called.

Steepest ascent over viable one-letter neighbours (ties to the lexicographically first string) gives every viable
variant its peak, the peak's value and the basin size. Peak counts use the viability cut and rescaling, so they
differ from the counts in Wu et al. 2016. For each model and arm (grid Blind, GB1 Blind, GB1 Menu) it reports
whether the nominee lies in the start's basin, the nominee's basin peak against the global peak, and the number of
distinct basins measured, beside the guessing and informed rules at their best k, with 95% seed-bootstrap intervals.

Usage: python3 scripts/basins.py      (writes results/basins.json and results/basins_variants.json)
"""
import collections, json, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
from repdef import campaign as C, envs as EV, policies as P            # noqa: E402
import analyse_0al as A0L                                               # noqa: E402
import analyse_0an7 as A7                                               # noqa: E402
import analyse_grid as AG                                               # noqa: E402
import fair_reference_curve as FRC                                      # noqa: E402
import yardsticks_0am as Y                                              # noqa: E402

LINE = re.compile(r"^\s*(\d+)\s+(\S{4})\s+(.*)$")
WU2016 = dict(peaks_complete_space=30, source="Wu et al. 2016, eLife 5:e16965 (PMC4985287), Results",
              sentence=("In the complete sequence space, we identified a total of 30 fitness peaks (i.e. local maxima); "
                        "among them 15 peaks had fitness larger than WT and their combined basins of attraction covered "
                        "99% of the sequence space"))
O7 = lambda short, arm: "+".join("gen_0an7_%s_%s%s" % (short, arm, r) for r in ("", "_rerun", "_cont"))
ARMS = {
    "grid Blind": [("Opus 4.7", "anthropic/claude-opus-4.7", "panelA0_original"),
                   ("Gemini 2.5 Flash", "google/gemini-2.5-flash", "gen_0an_f0_control"),
                   ("DeepSeek V3.1", "deepseek/deepseek-chat-v3.1", "gen_0an_f0_control"),
                   ("GPT-6.1 Sol", "openai/gpt-6.1-sol", O7("sol", "grid_blind")),
                   ("Gemini 3.1 Pro", "google/gemini-3.1-pro-preview", O7("gem", "grid_blind"))],
    "GB1 Blind": [("Opus 4.7", "anthropic/claude-opus-4.7", "gen_r_gb1scr+gen_r_gb1scr_top"),
                  ("Gemini 2.5 Flash", "google/gemini-2.5-flash", "gen_0an6_gb1_control"),
                  ("DeepSeek V3.1", "deepseek/deepseek-chat-v3.1", "gen_0an6_gb1_control"),
                  ("GPT-6.1 Sol", "openai/gpt-6.1-sol", O7("sol", "gb1_blind")),
                  ("Gemini 3.1 Pro", "google/gemini-3.1-pro-preview", O7("gem", "gb1_blind"))],
    "GB1 Menu": [("Opus 4.7", "anthropic/claude-opus-4.7", "gen_0an6_gb1_menu"),
                 ("Gemini 2.5 Flash", "google/gemini-2.5-flash", "gen_0an6_gb1_menu"),
                 ("DeepSeek V3.1", "deepseek/deepseek-chat-v3.1", "gen_0an6_gb1_menu"),
                 ("GPT-6.1 Sol", "openai/gpt-6.1-sol", O7("sol", "gb1_menu")),
                 ("Gemini 3.1 Pro", "google/gemini-3.1-pro-preview", O7("gem", "gb1_menu"))],
}


def basins(fit, pool, alphabet):
    pool = set(pool)
    up = {}
    for s in pool:
        best = None
        for i in range(4):
            for a in alphabet:
                if a == s[i]:
                    continue
                n = s[:i] + a + s[i + 1:]
                if n in pool and fit[n] > fit[s] and (best is None or (fit[n], best) > (fit[best], n)):
                    best = n
        up[s] = best
    peak = {}
    for s in pool:
        path, x = [], s
        while x not in peak and up[x] is not None:
            path.append(x)
            x = up[x]
        p = peak.get(x, x)
        for y in path + [x]:
            peak[y] = p
    size = collections.Counter(peak.values())
    return peak, size


def measured(prompt):
    out = set()
    for line in prompt.split("HISTORY", 1)[1].split("Choose", 1)[0].split("ANSWER", 1)[0].splitlines():
        m = LINE.match(line)
        if m and re.match(r"^-?\d+\.\d+$", m.group(3).strip()):
            out.add(m.group(2))
    return out


def summarise(cells, gpeak, fit, peak, tag):
    inb = [1.0 if peak.get(c["nominee"]) == peak[c["start"]] else 0.0 for c in cells]
    pv = [fit[peak[c["nominee"]]] if c["nominee"] in peak else 0.0 for c in cells]
    nb = [len({peak[s] for s in c["measured"] if s in peak}) for c in cells]
    pk = [fit[c["nominee"]] if c["nominee"] in fit else 0.0 for c in cells]
    d = dict(n=len(cells), nominee_value=st.mean(pk), nominee_in_start_basin=st.mean(inb), nominee_in_start_basin_ci=list(AG.boot_ci(inb, tag=tag + "|inb")),
             nominee_basin_peak=st.mean(pv), nominee_basin_peak_ci=list(AG.boot_ci(pv, tag=tag + "|pv")),
             nominee_basin_peak_is_global=st.mean(1.0 if v == gpeak else 0.0 for v in pv),
             distinct_basins=st.mean(nb), distinct_basins_ci=list(AG.boot_ci(nb, tag=tag + "|nb")))
    return d


def main():
    lands = {"grid": FRC.landscape() + (None,), "GB1": None, "PhoQ": None}
    e = EV.gb1_scrambled(); lands["GB1"] = (e.fit, e.pool, e.rng_key)
    e = EV.phoq_scrambled(); lands["PhoQ"] = (e.fit, e.pool, e.rng_key)
    out, variants = dict(wu2016=WU2016, landscapes={}, arms={}, scripted={}), {}
    B = {}
    for name, (fit, pool, _k) in lands.items():
        alphabet = P.alphabet_of(tuple(sorted(fit)))
        peak, size = basins(fit, pool, alphabet)
        B[name] = (fit, pool, peak, size)
        g = max(pool, key=lambda s: (fit[s], s))
        top = sorted(size.items(), key=lambda kv: -kv[1])[:5]
        out["landscapes"][name] = dict(viable=len(pool), peaks=len(size), global_peak=g, global_peak_value=fit[g],
                                       global_peak_basin=size[g], largest_basins=[[p, n, fit[p]] for p, n in top],
                                       peaks_above_median_viable=sum(1 for p in size if fit[p] > st.median(fit[s] for s in pool)))
        start = FRC.anchor_of(fit, pool) if name == "grid" else (EV.gb1_scrambled() if name == "GB1" else EV.phoq_scrambled()).anchor
        ranked = sorted(size, key=lambda p: (-fit[p], p))
        out["landscapes"][name].update(
            start=start, start_value=fit[start], start_basin_peak=peak[start], start_basin_peak_value=fit[peak[start]],
            start_basin_peak_rank=ranked.index(peak[start]) + 1, start_basin_size=size[peak[start]],
            start_basin_share=size[peak[start]] / len(pool), start_to_peak_changes=sum(a != b for a, b in zip(start, peak[start])),
            start_in_global_basin=peak[start] == g)
        variants[name] = {s: [peak[s], round(fit[peak[s]], 6), size[peak[s]]] for s in sorted(pool)}
        L = out["landscapes"][name]
        print("%-5s viable %d, peaks %d, global peak %s (%.3f, basin %d of %d); start %s (%.3f) drains to %s (%.3f, rank %d, "
              "%d changes away)" % (name, len(pool), len(size), g, fit[g], size[g], len(pool), start, L["start_value"],
                                    L["start_basin_peak"], L["start_basin_peak_value"], L["start_basin_peak_rank"],
                                    L["start_to_peak_changes"]))
    for arm, entries in ARMS.items():
        land = "grid" if arm.startswith("grid") else "GB1"
        fit, pool, peak, size = B[land]
        gpeak = out["landscapes"][land]["global_peak_value"]
        default = FRC.anchor_of(fit, pool) if land == "grid" else EV.gb1_scrambled().anchor
        out["arms"][arm] = {}
        for label, model, tags in entries:
            rows = [r for t in tags.split("+") for r in A7.rows_of(t) if r["model"] == model]
            prompts = {}
            for t in tags.split("+"):
                for c in A0L.calls(t):
                    if c.get("model") == model and c.get("kind") == "nomination" and \
                            (c.get("cell") or c.get("rung") or "blind").lower() == "blind":
                        prompts[c["campaign_seed"]] = c["prompt"]
            cells, missing = [], 0
            if any(r.get("anchor") not in (None, default) for r in rows):
                raise SystemExit("REFUSED: a %s %s row records a start other than %s" % (arm, label, default))
            for r in rows:
                if r["seed"] not in prompts:
                    missing += 1
                    continue
                cells.append(dict(start=r.get("anchor") or default, nominee=r["nominated"],
                                  measured=measured(prompts[r["seed"]])))
            d = summarise(cells, gpeak, fit, peak, "basins|%s|%s" % (arm, label))
            d["campaigns_without_a_nomination_prompt"] = missing
            out["arms"][arm][label] = d
            print("%-10s %-17s n=%3d  nominee in start basin %.2f  nominee basin peak %.3f (global %.3f)  distinct basins %.1f"
                  % (arm, label, d["n"], d["nominee_in_start_basin"], d["nominee_basin_peak"], gpeak, d["distinct_basins"]))
    for land, k in (("grid", 1), ("GB1", 0)):
        fit, pool, peak, size = B[land]
        env = EV.gb1_scrambled() if land == "GB1" else None
        key = env.rng_key if env else None
        anchor = env.anchor if env else FRC.anchor_of(fit, pool)
        space = tuple(sorted(fit)); alpha = P.alphabet_of(space); ps = tuple(sorted(pool))
        out["scripted"][land] = {}
        for label, make in (("guessing rule", lambda: Y.FairGreedyAlphabet(k, anchor, space, alpha, seed=0)),
                            ("informed rule", lambda: FRC.PoolGreedyAlphabet(k, space))):
            cells = []
            for i in range(FRC.N):
                try:
                    r = C.run(fit, pool, make(), 0.0, FRC.SEED0 + i, 0.15, pool_sorted=ps, nomination="shrinkage",
                              prior="empirical", noise_model="multiplicative", cv=FRC.CV, noise_floor=FRC.FLOOR, rng_key=key)
                except C.UnusableSigma:
                    continue
                cells.append(dict(start=anchor, nominee=r.nominated, measured={h.seq for h in r.history if h.outcome == "ok"}))
            d = summarise(cells, out["landscapes"][land]["global_peak_value"], fit, peak, "basins|%s|%s" % (land, label))
            d["k"] = k
            out["scripted"][land][label] = d
            print("%-10s %-17s n=%4d  nominee in start basin %.2f  nominee basin peak %.3f  distinct basins %.1f"
                  % (land, label, d["n"], d["nominee_in_start_basin"], d["nominee_basin_peak"], d["distinct_basins"]))
    json.dump(out, open(os.path.join(ROOT, "results", "basins.json"), "w"), indent=1)
    json.dump(variants, open(os.path.join(ROOT, "results", "basins_variants.json"), "w"), separators=(",", ":"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
