#!/usr/bin/env python3
"""Does temperature 0 give one fixed answer? Measured from the pilot log, at no cost.

Several round-1 prompts in the pilot were sent more than once as identical strings, so the agreement between
their replies shows whether temperature 0 is deterministic. If it is not, campaigns that share a round-1
prompt are separate draws, which sets the effective sample size of the round-1 contamination rate.

Writes results/step6_temperature_zero_determinism.json.
"""
import collections, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef import landscape as L

LOG = os.path.join(ROOT, "results", "pilot_opus47_calls.jsonl")


def main():
    rows = [json.loads(l) for l in open(LOG)]
    calls = [r for r in rows if r.get("kind") != "nomination" and r.get("parsed") is not None]
    by = collections.defaultdict(list)
    for r in calls:
        by[(r["prompt"], r["model"], r["temperature"])].append(r)
    repeated = {k: v for k, v in by.items() if len(v) > 1}

    n_rep_groups = len(repeated)
    n_rep_calls = sum(len(v) for v in repeated.values())
    identical_groups = 0
    rows_out = []
    for k, v in sorted(repeated.items(), key=lambda kv: -len(kv[1])):
        outs = collections.Counter(tuple(r["parsed"]) for r in v)
        # Order-insensitive too: a set of four proposals reordered is the same decision.
        sets = collections.Counter(frozenset(r["parsed"]) for r in v)
        if len(outs) == 1:
            identical_groups += 1
        rows_out.append(dict(calls=len(v), distinct_ordered=len(outs), distinct_sets=len(sets),
                             modal_share=outs.most_common(1)[0][1] / len(v),
                             rung=v[0]["rung"], sigma=v[0]["sigma"], temperature=v[0]["temperature"],
                             n_slots=v[0]["n_slots"]))

    print("=" * 84)
    print("TEMPERATURE 0 DETERMINISM, measured on byte-identical prompts")
    print("=" * 84)
    print("parsed calls in log                     %d" % len(calls))
    print("distinct (prompt, model, temperature)   %d" % len(by))
    print("groups sent more than once              %d  (%d calls)" % (n_rep_groups, n_rep_calls))
    print("groups whose every reply was identical  %d of %d" % (identical_groups, n_rep_groups))
    print()
    print("  calls  distinct  distinct  modal   rung        sigma  slots")
    print("         ordered   as a set  share")
    for d in rows_out:
        print("  %5d  %8d  %8d  %.2f    %-11s %5.3f  %d"
              % (d["calls"], d["distinct_ordered"], d["distinct_sets"], d["modal_share"],
                 d["rung"], d["sigma"], d["n_slots"]))

    # The headline: among repeated groups, the chance that two calls of the same prompt agree.
    agree_num = agree_den = 0
    for k, v in repeated.items():
        outs = collections.Counter(frozenset(r["parsed"]) for r in v)
        n = len(v)
        agree_den += n * (n - 1) // 2
        for _, c in outs.items():
            agree_num += c * (c - 1) // 2
    p_agree = agree_num / agree_den if agree_den else float("nan")

    # Effective sample size of the contamination rate: campaigns sharing a prompt are separate draws
    # when p_agree < 1.
    best = "FWAA"
    camps = collections.defaultdict(list)
    for r in rows:
        if r.get("kind") != "nomination":
            camps[(r["rung"], r["ratio"], r["campaign_seed"])].append(r)
    cells = collections.defaultdict(list)
    for (rung, ratio, seed), cs in camps.items():
        cells[(rung, ratio)].append(any(best in r["parsed"] for r in cs if r["round"] == 1))
    within_cell_varies = sum(1 for v in cells.values() if 0 < sum(v) < len(v))

    print()
    print("pairwise agreement between two calls of the SAME prompt   %.3f" % p_agree)
    print("cells whose 5 campaigns do NOT all agree                  %d of %d"
          % (within_cell_varies, len(cells)))
    print()
    verdict = ("NOT deterministic" if p_agree < 0.999 else "deterministic")
    print("VERDICT: temperature 0 on this provider is %s." % verdict)
    print()
    if p_agree < 0.999:
        print("So replicate campaigns at temperature 0 sample the model's own variability, and the")
        print("round-1 contamination rate is a rate over campaigns and not over prompts. The")
        print("cost is that llm.py's stated rationale is wrong: sampling noise is NOT excluded, it")
        print("is present and unmeasured, and the methods section has to say so. The grid therefore")
        print("needs replicate campaigns per cell for a reason the pre-registration did not give.")

    out = dict(parsed_calls=len(calls), distinct_prompts=len(by), repeated_groups=n_rep_groups,
               repeated_calls=n_rep_calls, groups_all_identical=identical_groups,
               pairwise_agreement=p_agree, cells_with_within_cell_variation=within_cell_varies,
               cells=len(cells), verdict=verdict, groups=rows_out)
    dest = os.path.join(ROOT, "results", "step6_temperature_zero_determinism.json")
    json.dump(out, open(dest, "w"), indent=1)
    print("\nsaved %s" % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
