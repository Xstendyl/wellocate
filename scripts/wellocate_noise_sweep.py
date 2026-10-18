#!/usr/bin/env python3
"""How the best split between exploring and confirming moves with noise. Scripted, no model calls.

Built from the chunks scripts/wellocate_chunks.py writes. On both tracks (the sandbox grid; scrambled GB1 and PhoQ
for bio), on the paper's 1,500 campaign seeds, through the step API, at five noise levels: the presets low, assay
and high (CV 0.0365, 0.073, 0.146) and a design sweep at CV 0.3 and 0.6, which is not a pre-registered test.
  Guessing rule   k = 0 to 4 re-tests of the current best per round, under the grid's rule (a slot is lost after
                  3 rejected replacements) and under the risk-free rule (rejections cost no slot, up to 20 asks).
                  k* is the k with the highest mean pick under each rule. Comparing the two separates the value of
                  re-testing for confirmation from its value in avoiding non-viable proposals.
  Confirmation    a simple confirmation policy (a reference point, not tuned) with 4, 8 and 12 confirmation slots.
Per level, the best scripted share is the re-testing share of the grid-rule policy above with the highest mean
pick, named. The crossover is the lowest level at which k* exceeds 0. Means carry 95% bootstrap intervals.
At assay noise the grid and GB1 grid-rule curves must equal results/references_0an7.json, and the grid's
risk-free curve must equal results/riskfree_reference_alphabet.json at every k; the build refuses otherwise.

Writes results/wellocate_noise_sweep.json.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from wellocate import scorecard as S, env as W   # noqa: E402

LANDS = [("sandbox", "grid", "nk:paper"), ("bio", "GB1", "gb1:paper"), ("bio", "PhoQ", "phoq:paper")]
LEVELS = [("low", W.NOISE_PRESETS["low"], "preset"), ("assay", W.NOISE_PRESETS["assay"], "preset"),
          ("high", W.NOISE_PRESETS["high"], "preset"), ("cv0.3", 0.3, "design sweep, not a registered test"),
          ("cv0.6", 0.6, "design sweep, not a registered test")]
OUT = os.path.join(ROOT, "results", "wellocate_noise_sweep.json")


def summary(rows, tag):
    rows = [r for r in rows if r is not None]
    cols = {m: [r[m] for r in rows] for m in ("pick", "share_budget", "lost_slots", "selection_shortfall", "rejected")}
    return dict(n=len(rows), **S._boot(cols, 1000, tag))


def build(read):
    out = dict(levels=[dict(key=k, cv=cv, kind=kind) for k, cv, kind in LEVELS], lands={})
    for track, label, split in LANDS:
        d = out["lands"][label] = dict(track=track, split=split, levels={}, crossover={})
        for key, cv, kind in LEVELS:
            g = {k: summary(read((split, "guessing_k%d" % k, key)), "sweep|%s|%s|g%d" % (split, key, k)) for k in S.KS}
            rf = {k: summary(read((split, "guessing_k%d_riskfree" % k, key)), "sweep|%s|%s|rf%d" % (split, key, k))
                  for k in S.KS}
            c = {str(x): summary(read((split, "confirmation_%d" % x, key)), "sweep|%s|%s|c%d" % (split, key, x))
                 for x in (4, 8, 12)}
            ks = max(S.KS, key=lambda k: g[k]["pick"]["mean"])
            ksr = max(S.KS, key=lambda k: rf[k]["pick"]["mean"])
            allp = [("guessing k=%d" % k, g[k]) for k in S.KS] + [("simple confirmation, %s slots" % x, c[x]) for x in c]
            bname, brow = max(allp, key=lambda t: t[1]["pick"]["mean"])
            d["levels"][key] = dict(
                cv=cv, times_assay=cv / W.NOISE_PRESETS["assay"], kind=kind, guessing={str(k): g[k] for k in S.KS}, kstar=ks, pick_at_kstar=g[ks]["pick"],
                share_at_kstar=g[ks]["share_budget"], riskfree={str(k): rf[k] for k in S.KS}, kstar_riskfree=ksr,
                pick_at_kstar_riskfree=rf[ksr]["pick"], share_at_kstar_riskfree=rf[ksr]["share_budget"],
                confirmation=c, best_scripted=dict(policy=bname, pick=brow["pick"], share_budget=brow["share_budget"]))
        for rule, field in (("grid rule", "kstar"), ("risk-free rule", "kstar_riskfree")):
            over = [key for key, cv, _k in LEVELS if d["levels"][key][field] > 0]
            first = over[0] if over else None
            d["crossover"][rule] = dict(first_level_with_kstar_above_0=first,
                                        cv=d["levels"][first]["cv"] if first else None,
                                        times_assay=(d["levels"][first]["cv"] / W.NOISE_PRESETS["assay"]) if first else None)
    ref = json.load(open(os.path.join(ROOT, "results", "references_0an7.json")))
    for label, key in (("grid", "grid"), ("GB1", "gb1_scrambled")):
        mine, theirs = out["lands"][label]["levels"]["assay"], ref[key]["guessing"]
        if mine["kstar"] != theirs["kstar"] or abs(mine["pick_at_kstar"]["mean"] - theirs["at_kstar"]["pick"]) > 1e-9:
            raise SystemExit("REFUSED: the assay level does not reproduce the paper's %s reference" % label)
    rfr = json.load(open(os.path.join(ROOT, "results", "riskfree_reference_alphabet.json")))["riskfree"]["curve"]
    for k in S.KS:
        if abs(out["lands"]["grid"]["levels"]["assay"]["riskfree"][str(k)]["pick"]["mean"] - rfr[str(k)]["mean"]) > 1e-9:
            raise SystemExit("REFUSED: the grid's risk-free curve at k=%d does not reproduce the paper's" % k)
    out["assay_reproduces_the_paper"] = True
    json.dump(out, open(OUT, "w"), indent=1)
    for label, d in out["lands"].items():
        for key, x in d["levels"].items():
            print("%-5s %-6s cv %.4f  grid rule: k* = %d, pick %.3f, share %4.1f%% | risk-free: k* = %d, pick %.3f | "
                  "selection loss k=0 %.3f k=1 %.3f | lost k=0 %.1f k=1 %.1f | best scripted %s"
                  % (label, key, x["cv"], x["kstar"], x["pick_at_kstar"]["mean"], x["share_at_kstar"]["mean"],
                     x["kstar_riskfree"], x["pick_at_kstar_riskfree"]["mean"],
                     x["guessing"]["0"]["selection_shortfall"]["mean"], x["guessing"]["1"]["selection_shortfall"]["mean"],
                     x["guessing"]["0"]["lost_slots"]["mean"], x["guessing"]["1"]["lost_slots"]["mean"],
                     x["best_scripted"]["policy"]))
        print("%-5s crossover: %s" % (label, d["crossover"]))


if __name__ == "__main__":
    print("Run scripts/wellocate_chunks.py, which builds this file when every chunk is complete.")
