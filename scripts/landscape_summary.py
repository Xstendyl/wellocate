#!/usr/bin/env python3
"""Compute the numbers behind the landscape figure (Figure 2) and its caption.

Covers the grid landscape (NK, K=1, best candidate rescaled to 8.762) and its reference candidate, each model's
mean final pick over the core-grid campaigns (fallback campaigns excluded), and the guessing policy's mean pick
at k=1. "Top x% of viable" is the share of viable candidates whose true fitness is at least the value.

Usage: python3 scripts/landscape_summary.py     (writes results/landscape_summary.json)
"""
import json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
import analyse_grid as AG                                   # noqa: E402
import fair_reference_curve as FRC                          # noqa: E402

TAGS = ("stage1", "topup_opus", "topup_gemini", "topup_deepseek")
MODELS = ("anthropic/claude-opus-4.7", "google/gemini-2.5-flash", "deepseek/deepseek-chat-v3.1")
ALPHABET = "ABCDEFGHIJKLMNOPQRST"
BINS = 70                                                   # bin edges over the full fitness range
OUT = os.path.join(ROOT, "results", "landscape_summary.json")


def main():
    fit, pool = FRC.landscape()
    pool = set(pool)
    viable = sorted(fit[s] for s in pool)
    top_pct = lambda x: 100.0 * sum(1 for y in viable if y >= x) / len(viable)
    ref = FRC.anchor_of(fit, pool)
    best = max(fit, key=fit.get)
    cutoff = min(fit[s] for s in pool)
    # numpy binning, matching the figure: [a, b) for every bin and [a, b] for the last.
    import numpy as np
    allv = np.array(list(fit.values()))
    edges_np = np.linspace(allv.min(), allv.max(), BINS)
    edges = [float(x) for x in edges_np]
    counts = {"viable": [int(c) for c in np.histogram(allv[allv >= cutoff], bins=edges_np)[0]],
              "not_viable": [int(c) for c in np.histogram(allv[allv < cutoff], bins=edges_np)[0]]}
    rows, _ = AG.drop_fallbacks(AG.load("+".join(TAGS)), AG.fallback_seeds(list(TAGS)))
    picks = {}
    for m in MODELS:
        v = [r["nominated_true"] for r in rows if r["model"] == m]
        picks[m] = dict(n=len(v), mean=st.mean(v), top_pct_of_viable=top_pct(st.mean(v)))
    scripted = json.load(open(FRC.CORRECTED))["curves"]["fair"]["1"]["mean"]
    def slice_through(seq):
        """The 20 x 20 slice with positions 3 and 4 fixed at seq's letters; rows are the letter at position 2."""
        grid = [[fit[a + b + seq[2] + seq[3]] for a in ALPHABET] for b in ALPHABET]
        vgrid = [[(a + b + seq[2] + seq[3]) in pool for a in ALPHABET] for b in ALPHABET]
        return dict(fixed_positions=[3, 4], fixed_letters=[seq[2], seq[3]], alphabet=ALPHABET,
                    fitness=grid, viable=vgrid, n_viable=sum(map(sum, vgrid)), n_cells=len(ALPHABET) ** 2)

    out = dict(
        n=len(fit), viable=len(pool), viable_pct=100.0 * len(pool) / len(fit), cutoff=cutoff,
        reference=dict(seq=ref, value=fit[ref], top_pct_of_viable=top_pct(fit[ref])),
        best=dict(seq=best, value=fit[best]),
        histogram=dict(edges=edges, **counts),
        picks=picks, scripted=dict(mean=scripted, top_pct_of_viable=top_pct(scripted)),
        slice=slice_through(best), start_slice=slice_through(ref))
    json.dump(out, open(OUT, "w"), indent=1)
    print("candidates %d, viable %d (%.2f%%), cutoff %.4f" % (out["n"], out["viable"], out["viable_pct"], cutoff))
    print("reference %s %.4f (top %.1f%% of viable), best %s %.4f" % (ref, fit[ref], top_pct(fit[ref]), best, fit[best]))
    for m, p in picks.items():
        print("  %-30s n=%4d mean pick %.4f, top %.2f%% of viable" % (m, p["n"], p["mean"], p["top_pct_of_viable"]))
    print("scripted (guessing, k=1) %.4f, top %.2f%% of viable" % (scripted, top_pct(scripted)))
    print("slice: positions 3-4 fixed at %s%s, %d of %d viable, %d not viable"
          % (best[2], best[3], out["slice"]["n_viable"], out["slice"]["n_cells"],
             out["slice"]["n_cells"] - out["slice"]["n_viable"]))
    print("start slice: positions 3-4 fixed at %s%s, %d of %d viable"
          % (ref[2], ref[3], out["start_slice"]["n_viable"], out["start_slice"]["n_cells"]))
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
