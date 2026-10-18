#!/usr/bin/env python3
"""Build a candidate table for the model-breadth panel from the live OpenRouter catalogue.

Candidates are picked to span vendors, open weights, capability and release date beyond the three current
models. Cost per campaign is projected from the grid's own measured token profile and each model's listed
prices. For open-weight candidates the available providers are listed so one can be pinned.
"""
import collections, glob, gzip, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURRENT = ["anthropic/claude-opus-4.7", "google/gemini-2.5-flash", "deepseek/deepseek-chat-v3.1"]
PANEL_CAMPAIGNS = 400          # 2 conditions x 40 seeds x 5 candidates, as a working figure


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "repdef/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def token_profile():
    """Prompt and completion tokens per campaign, measured, averaged over the three current models."""
    pt = collections.defaultdict(int)
    ct = collections.defaultdict(int)
    camp = collections.defaultdict(set)
    for f in glob.glob(os.path.join(ROOT, "results", "grid_stage1_calls", "*.jsonl.gz")):
        with gzip.open(f, "rt") as fh:
            for l in fh:
                if not l.strip():
                    continue
                r = json.loads(l)
                m = r["model"]
                pt[m] += r.get("prompt_tokens") or 0
                ct[m] += r.get("completion_tokens") or 0
                camp[m].add((r["rung"], r["campaign_seed"]))
    p = [pt[m] / len(camp[m]) for m in pt]
    c = [ct[m] / len(camp[m]) for m in ct]
    return sum(p) / len(p), sum(c) / len(c)


def per_campaign(m, prompt_t, compl_t):
    pr = m.get("pricing") or {}
    try:
        return prompt_t * float(pr.get("prompt") or 0) + compl_t * float(pr.get("completion") or 0)
    except (TypeError, ValueError):
        return float("nan")


def main():
    prompt_t, compl_t = token_profile()
    data = fetch("https://openrouter.ai/api/v1/models")["data"]
    by_id = {m["id"]: m for m in data}
    print("=" * 112)
    print("MODEL BREADTH CANDIDATES.  cost projected on OUR measured profile: %.0f prompt + %.0f "
          "completion tokens/campaign" % (prompt_t, compl_t))
    print("=" * 112)

    print("\nTHE THREE ALREADY IN THE GRID, for calibration:")
    print("  %-34s %-9s %9s %9s %10s %8s" % ("model", "weights", "$/Mtok in", "$/Mtok out",
                                             "$/campaign", "released"))
    for mid in CURRENT:
        m = by_id.get(mid)
        if not m:
            print("  %-34s NOT IN THE LIVE CATALOGUE" % mid)
            continue
        pr = m["pricing"]
        print("  %-34s %-9s %9.2f %9.2f %10.4f %8s"
              % (mid.split("/")[-1][:34], "open" if m.get("hugging_face_id") else "closed",
                 1e6 * float(pr["prompt"]), 1e6 * float(pr["completion"]),
                 per_campaign(m, prompt_t, compl_t), (m.get("knowledge_cutoff") or "?")))

    # Candidates: one per vendor family not already represented, plus a small model, ranked by recency.
    families = {"openai": "OpenAI", "meta-llama": "Meta", "qwen": "Alibaba Qwen",
                "mistralai": "Mistral", "x-ai": "xAI", "moonshotai": "Moonshot",
                "z-ai": "Z.ai", "microsoft": "Microsoft"}
    print("\nCANDIDATES, newest first within each vendor family not already in the grid.")
    print("Excluded: :free variants, anything with an expiration date, and non-text output.")
    print("  %-40s %-13s %-7s %9s %9s %10s %7s"
          % ("model id", "vendor", "weights", "$/Mtok in", "$/Mtok out", "$/campaign", "ctx k"))
    shortlist = []
    for fam, label in families.items():
        rows = []
        for m in data:
            mid = m["id"]
            if not mid.startswith(fam + "/") or ":free" in mid or m.get("expiration_date"):
                continue
            # Skip models that cannot run an interactive campaign (guard, moderation, batch, embedding, audio).
            if any(w in mid for w in (":batch", "guard", "moderation", "embed", "rerank", "-tts",
                                      "-stt", "whisper", "ocr")):
                continue
            arch = m.get("architecture") or {}
            if "text" not in (arch.get("output_modalities") or ["text"]):
                continue
            pr = m.get("pricing") or {}
            if not pr.get("prompt") or float(pr["prompt"]) <= 0:
                continue
            rows.append(m)
        rows.sort(key=lambda m: -(m.get("created") or 0))
        for m in rows[:2]:
            pr = m["pricing"]
            cpc = per_campaign(m, prompt_t, compl_t)
            print("  %-40s %-13s %-7s %9.2f %9.2f %10.4f %7d"
                  % (m["id"][:40], label, "open" if m.get("hugging_face_id") else "closed",
                     1e6 * float(pr["prompt"]), 1e6 * float(pr["completion"]), cpc,
                     (m.get("context_length") or 0) // 1000))
            shortlist.append(dict(id=m["id"], vendor=label,
                                  open_weight=bool(m.get("hugging_face_id")),
                                  usd_per_campaign=cpc,
                                  context=m.get("context_length"),
                                  created=m.get("created"),
                                  supports_reasoning=("reasoning" in (m.get("supported_parameters") or []))))
    print("\n  A panel of five candidates x 2 conditions x 40 seeds = 400 campaigns.")
    print("  Open-weight candidates need ONE PINNED PROVIDER each. Their endpoints:")
    for x in shortlist:
        if not x["open_weight"]:
            continue
        try:
            eps = fetch("https://openrouter.ai/api/v1/models/%s/endpoints" % x["id"])
            names = [e.get("provider_name") for e in (eps.get("data") or {}).get("endpoints") or []]
        except Exception as e:                      # noqa: BLE001
            names = ["<could not fetch: %s>" % type(e).__name__]
        x["providers"] = names
        print("    %-38s %s" % (x["id"][:38], ", ".join(str(n) for n in names[:6]) or "none listed"))
    cheap = sorted(x["usd_per_campaign"] for x in shortlist)[:5]
    dear = sorted((x["usd_per_campaign"] for x in shortlist), reverse=True)[:5]
    print("  Five cheapest of the above: $%.2f for the panel. Five dearest: $%.2f."
          % (80 * sum(cheap), 80 * sum(dear)))
    dst = os.path.join(ROOT, "results", "model_breadth_candidates.json")
    json.dump(dict(prompt_tokens_per_campaign=prompt_t, completion_tokens_per_campaign=compl_t,
                   panel_campaigns=PANEL_CAMPAIGNS, current=CURRENT, candidates=shortlist),
              open(dst, "w"), indent=1)
    print("\n  wrote %s" % os.path.relpath(dst, ROOT))


if __name__ == "__main__":
    main()
