#!/usr/bin/env python3
"""Post-hoc PPO reports, built from the per-episode files that ppo_robustness2.py writes.

  behaviour     results/b11_behaviour.json (behaviour replay of Run A and Run B)
  real          results/b11_real_landscapes.json (unscrambled GB1 and PhoQ)
  zero-shot     results/b11_zero_shot.json (held-out K2 and K3; budgets 10x4, 20x4, 4x24)

Usage: python3 wellocate/examples/ppo_robustness2_report.py behaviour
"""
import hashlib, importlib.util, json, os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
_spec = importlib.util.spec_from_file_location("ppo_robustness2", os.path.join(HERE, "ppo_robustness2.py"))
R2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R2)
RES, WORK = R2.RES, R2.WORK
with open(os.path.abspath(__file__), "rb") as _f:
    CODE_SHA256 = hashlib.sha256(_f.read()).hexdigest()
RANK_BINS = (("1", lambda r: r == 1), ("2", lambda r: r == 2), ("3", lambda r: r == 3), ("4-8", lambda r: 4 <= r <= 8),
             ("9+", lambda r: r >= 9))


def shares(values, bins):
    n = len(values)
    return {name: (sum(1 for v in values if f(v)) / n if n else None) for name, f in bins}


# -- behaviour replay ---------------------------------------------------------------------------------------------------
def behaviour():
    out = dict(label=R2.LABEL, spec="spec/B11_ROBUSTNESS_2.md", code_sha256=CODE_SHA256, runs={},
               definitions=dict(
                   retest="a slot-consuming order of a sequence that used a slot before (the scorecard's definition)",
                   retest_rank=("rank by mean reading at the start of the order's round, 1 the highest; "
                                "'retry_after_failure' if every earlier attempt failed; 'same_round_replicate' if first "
                                "read earlier in the same round"),
                   parent_rank=("best rank among sequences read before the round that are one letter away; 'start' "
                                "if only the start point is one letter away; 'none' otherwise"),
                   nominee=("compared with the highest mean reading and with the shrinkage nominee on the same final "
                            "readings; pick cost is the nominee's true value minus theirs")))
    key = 7500
    for run in ("A", "B"):
        for split in ("nk:test", "gb1:test", "phoq:test"):
            p = os.path.join(WORK, "replay_%s_%s.json" % (run, split.replace(":", "_")))
            if not os.path.exists(p):
                continue
            d = json.load(open(p))
            eps = [tuple(e) for e in d["episodes"]]
            key += 1
            cl = R2.Cluster([e[0] for e in eps], key)
            blk = dict(rows_equal_registered=d["rows_equal_registered"], seeds={})
            seeds = sorted(d["seeds"], key=int)
            for sd in seeds:
                logs = d["seeds"][sd]["logs"]
                rt = [r for lg in logs for r in lg["retest_rank"]]
                pa = [r for lg in logs for r in lg["parent_rank"]]
                by_round = np.mean([[x / 4.0 for x in lg["retests_by_round"]] for lg in logs], axis=0) * 100
                nm = [lg for lg in logs if lg["nominee"] is not None]
                blk["seeds"][sd] = dict(
                    retest_share_by_round=[float(x) for x in by_round],
                    retests=len(rt), retest_rank=dict(shares(rt, RANK_BINS),
                                                      retry_after_failure=(sum(1 for r in rt if r == -1) / len(rt)
                                                                           if rt else None),
                                                      same_round_replicate=(sum(1 for r in rt if r == -2) / len(rt)
                                                                            if rt else None)),
                    new_candidates=len(pa),
                    parent_rank=dict(shares(pa, RANK_BINS), start=sum(1 for r in pa if r == 0) / len(pa),
                                     none=sum(1 for r in pa if r == -1) / len(pa)),
                    nominee_is_max_mean=sum(1 for lg in nm if lg["nominee"] == lg["max_mean"]) / len(nm),
                    nominee_is_shrinkage=sum(1 for lg in nm if lg["nominee"] == lg["shrinkage"]) / len(nm))
            # pick cost of the nominee against the shrinkage nominee and the highest mean, all seeds
            for other in ("shrinkage", "max_mean"):
                per = [[None if lg[other + "_pick"] is None else dict(pick=lg["pick"] - lg[other + "_pick"])
                        for lg in d["seeds"][sd]["logs"]] for sd in seeds]
                zero = [[None if r is None else dict(pick=0.0) for r in rows] for rows in per]
                c = R2.cluster_paired(cl, per, zero, "pick")
                blk["pick_cost_vs_%s" % other] = c
            ms = lambda f: float(np.mean([f(blk["seeds"][s]) for s in seeds]))
            share = lambda s: float(np.mean(s["retest_share_by_round"]))
            lead = lambda s: sum(s["retest_rank"][k] for k in ("1", "2", "3"))
            blk["mean_over_seeds"] = dict(
                retest_share_by_round=[float(np.mean([blk["seeds"][s]["retest_share_by_round"][r] for s in seeds]))
                                       for r in range(15)],
                retest_share=ms(share),
                retry_after_failure=ms(lambda s: s["retest_rank"]["retry_after_failure"]),
                same_round_replicate=ms(lambda s: s["retest_rank"]["same_round_replicate"]),
                retests_of_top3=ms(lead),
                # re-tests of one of the three leading read candidates, as a share of all slots
                top3_retests_pct_of_slots=ms(lambda s: share(s) * lead(s)),
                parent_top1=ms(lambda s: s["parent_rank"]["1"]),
                parent_top3=ms(lambda s: s["parent_rank"]["1"] + s["parent_rank"]["2"] + s["parent_rank"]["3"]),
                nominee_is_max_mean=ms(lambda s: s["nominee_is_max_mean"]),
                nominee_is_shrinkage=ms(lambda s: s["nominee_is_shrinkage"]))
            out["runs"]["%s %s" % (run, split)] = blk
    path = os.path.join(RES, "b11_behaviour.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    for name, b in out["runs"].items():
        m = b["mean_over_seeds"]
        print("\nRun %s (replay rows equal registered: %d)" % (name, b["rows_equal_registered"]))
        print("  re-testing share by round, %%: %s" % " ".join("%.0f" % x for x in m["retest_share_by_round"]))
        for sd, s in b["seeds"].items():
            print("  seed %s: re-test rank %s | parent rank %s | nominee = max mean %.0f%%, = shrinkage %.0f%%" % (
                sd, " ".join("%s:%.0f%%" % (k, 100 * v) for k, v in s["retest_rank"].items() if v is not None),
                " ".join("%s:%.0f%%" % (k, 100 * v) for k, v in s["parent_rank"].items() if v is not None),
                100 * s["nominee_is_max_mean"], 100 * s["nominee_is_shrinkage"]))
        for other in ("shrinkage", "max_mean"):
            c = b["pick_cost_vs_%s" % other]
            print("  nominee minus %-9s pick %+.3f [%+.3f, %+.3f]" % (other, c["mean"], c["ci"][0], c["ci"][1]))
    print("written %s" % os.path.relpath(path, ROOT))


# -- real landscapes and zero-shot --------------------------------------------------------------------------------------
def eval_report(files, out_name, extra=None):
    out = dict(label=R2.LABEL, spec="spec/B11_ROBUSTNESS_2.md", code_sha256=CODE_SHA256, sets={})
    key = 7600 if "real" in out_name else 7700
    for fn in files:
        p = os.path.join(WORK, fn)
        if not os.path.exists(p):
            continue
        part = json.load(open(p))
        part["options"] = dict(rounds=part["rounds"], slots=part["slots"])
        key += 1
        b = R2.stress_block(part["split"], "%dx%d" % (part["rounds"], part["slots"]), part, key)
        b["scripted_names"] = part["scripted_names"]
        if extra:
            b.update(extra(part, b))
        out["sets"]["%s %dx%d" % (part["split"], part["rounds"], part["slots"])] = b
    path = os.path.join(RES, out_name)
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    for name, b in out["sets"].items():
        sn = b["scripted_names"]
        print("\n%s (%d episodes)" % (name, b["episodes"]))
        for n in ("Run A",) + tuple(R2.SCRIPTED):
            p = b["policies"][n]
            print("  %-14s pick %.3f [%.3f, %.3f]  share %.1f%%" % (sn.get(n, n), p["pick"]["mean"], p["pick"]["ci"][0],
                                                                    p["pick"]["ci"][1], p["share"]["mean"]))
        print("  best scripted %s; Run A minus random %s; Run A minus best %s" % (
            sn.get(b["best_scripted"], b["best_scripted"]), R2.fmtd(b["run_a_minus_random"]["pick"]),
            R2.fmtd(b["run_a_minus_best"]["pick"])))
        for rule, h in b["heavy_vs_moderate"].items():
            print("  %s: best %s; heavy (%s) minus moderate (%s) %s -> matches or beats: %s" % (
                rule, sn.get(b["best_k"][rule]["best"], b["best_k"][rule]["best"]), sn.get(h["best_heavy"], h["best_heavy"]),
                sn.get(h["best_moderate"], h["best_moderate"]), R2.fmtd(h["heavy_minus_moderate"]),
                "YES" if h["heavy_matches_or_beats"] else "no"))
        for k, v in b.items():
            if k.startswith("registered_"):
                print("  %s: %s" % (k, v))
    print("written %s" % os.path.relpath(path, ROOT))


def registered_k(part, b):
    """The comparators: guessing and informed at the k chosen on validation."""
    vk = json.load(open(R2.R.TEST_A))["splits"][R2.VAL_SPLIT[part["split"]]]["validation_k"]
    out = {}
    for rule in ("guessing", "informed"):
        n = "%s k=%d" % (rule, vk[rule])
        out["registered_%s" % rule] = dict(k=vk[rule], pick=b["policies"][n]["pick"], share=b["policies"][n]["share"]["mean"])
    return out


def features_out_of_range(part, b):
    r, s = part["rounds"], part["slots"]
    flags = {}
    if s > 4:
        flags["slots_left/4 and chosen_retests/4"] = "reach %.1f (trained range 0 to 1)" % (s / 4.0)
    if r * s > 60:
        flags["len(means)/60"] = "can reach %.2f (trained range up to 1)" % (r * s / 60.0)
    return dict(features_out_of_range=flags or "none")


def main(argv=None):
    cmd = (argv or sys.argv[1:] or ["behaviour"])[0]
    if cmd == "behaviour":
        behaviour()
    elif cmd == "real":
        eval_report(["eval_gb1_transfer_real_15x4.json", "eval_phoq_transfer_real_15x4.json"], "b11_real_landscapes.json",
                    registered_k)
    elif cmd == "zero-shot":
        eval_report(["eval_nk_test_ood_k2_15x4.json", "eval_nk_test_ood_k3_15x4.json", "eval_nk_test_10x4.json",
                     "eval_nk_test_20x4.json", "eval_nk_test_4x24.json"], "b11_zero_shot.json", features_out_of_range)
    else:
        raise SystemExit("unknown command %r" % cmd)


if __name__ == "__main__":
    main()
