#!/usr/bin/env python3
"""Simulate a confirmation round on the agents' own grid traces. No model is called.

For each grid Blind campaign of GPT-6.1 Sol, Gemini 3.1 Pro and the control models (Gemini 2.5 Flash, DeepSeek
V3.1), the history is rebuilt through the seeded oracle, which reproduces every reading exactly. The agent's
final-round orders are then replaced by re-measurements of the top k candidates by mean reading (k = 1 to 4),
and the nominee is chosen by the pre-registered shrinkage rule. Reports the pick change against the agent's own
pick, paired by seed with a 95% bootstrap interval, and how much of its selection shortfall this recovers.
With --replace-rounds 2 the last two rounds are replaced instead; this variant is exploratory.

Usage: python3 scripts/confirm_counterfactual_0an7.py [--replace-rounds 2]
       (writes results/confirm_counterfactual_0an7.json, or _r2.json with --replace-rounds 2)
"""
import collections, json, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
from repdef import campaign as C, oracle as O, view as V                 # noqa: E402
import analyse_0al as A0L                                                 # noqa: E402
import analyse_grid as AG                                                 # noqa: E402
import fair_reference_curve as FRC                                        # noqa: E402

ARMS = {"GPT-6.1 Sol": ("openai/gpt-6.1-sol", ["gen_0an7_sol_grid_blind"]),
        "Gemini 3.1 Pro": ("google/gemini-3.1-pro-preview", ["gen_0an7_gem_grid_blind", "gen_0an7_gem_grid_blind_rerun"]),
        "Gemini 2.5 Flash (F0)": ("google/gemini-2.5-flash", ["gen_0an_f0_control"]),
        "DeepSeek V3.1 (F0)": ("deepseek/deepseek-chat-v3.1", ["gen_0an_f0_control"])}
F0 = "0an F0 control|gemini-2.5-flash"
F0_LOSS = {"GPT-6.1 Sol": lambda a: a["cells"]["sol|grid_blind"]["comparators"][F0]["paired"]["d_selection_shortfall"],
           "Gemini 3.1 Pro": lambda a: a["cells"]["gem|grid_blind"]["comparators"][F0]["paired"]["d_selection_shortfall"]}
LINE = re.compile(r"^\s*(\d+)\s+(\S{4})\s+(.*)$")
KS = (1, 2, 3, 4)
LAST = 15 - (int(sys.argv[sys.argv.index("--replace-rounds") + 1]) if "--replace-rounds" in sys.argv else 1)
ALLOC = {1: (0, 0, 0, 0), 2: (0, 0, 1, 1), 3: (0, 0, 1, 2), 4: (0, 1, 2, 3)}


def sigma(f):
    return ((FRC.FLOOR ** 2) + (abs(f) * FRC.CV) ** 2) ** 0.5


def history(prompt):
    out = []
    for line in prompt.split("HISTORY", 1)[1].split("Choose", 1)[0].split("ANSWER", 1)[0].splitlines():
        m = LINE.match(line)
        if not m:
            continue
        rnd, seq, rest = int(m.group(1)), m.group(2), m.group(3).strip()
        if re.match(r"^-?\d+\.\d+$", rest):
            out.append((rnd, seq, "ok", float(rest)))
        elif rest.startswith("order failed"):
            out.append((rnd, seq, "failed", None))
        elif rest.startswith("rejected"):
            out.append((rnd, seq, "rejected", None))
        elif rest.startswith("SLOT LOST"):
            out.append((rnd, seq, "abandoned", None))
        elif rest.startswith("ROUND LOST"):
            out.append((rnd, seq, "round_lost", None))
    return out


def replay(fit, pool, seed, lines, upto=None):
    orc = O.Oracle(fit, pool, 0.0, seed, 0.15, noise_model="multiplicative", cv=FRC.CV, noise_floor=FRC.FLOOR)
    bad = 0
    for rnd, seq, outc, obs in lines:
        if upto is not None and rnd > upto:
            continue
        if outc in ("abandoned", "round_lost"):
            orc.record_abandoned(rnd, seq, outcome=O.ABANDONED if outc == "abandoned" else O.ROUND_LOST)
            continue
        rec = orc.measure(seq, rnd)
        if rec.outcome != outc or (outc == "ok" and abs(rec.observed - obs) > 0.0006):
            bad += 1
    return orc, bad


def shrinkage_pick(orc, ps):
    final = V.build(orc, max(r.round for r in orc.history), 15, 4, 60, ps)
    ep = C.empirical_prior(final, sigma, rel_floor=0.01)
    if ep is None or ep[1] <= 0.0:
        return None
    return C._shrinkage_nominate(final, sigma, ep[0], ep[1])


def retests(orc):
    seen, rep, used = set(), 0, 0
    for r in orc.history:
        if r.slot_consumed:
            used += 1
        if r.outcome in ("ok", "failed"):
            rep += 1 if r.seq in seen else 0
            seen.add(r.seq)
    return rep, used


def main():
    fit, pool = FRC.landscape()
    ps = tuple(sorted(pool))
    a7 = json.load(open(os.path.join(ROOT, "results", "analysis_0an7.json")))
    out = {}
    for name, (model, tags) in ARMS.items():
        rows = {}
        for t in tags:
            rr, _ = AG.drop_fallbacks(AG.load(t), AG.fallback_seeds([t]))
            rows.update({r["seed"]: r for r in rr if r["model"] == model and r["condition"] == "Blind"})
        prompts = {}
        for t in tags:
            for c in A0L.calls(t):
                if c["model"] == model and c.get("kind") == "nomination" and (c.get("cell") or "Blind") == "Blind":
                    prompts[c["campaign_seed"]] = c["prompt"]
        used, skipped = [], collections.Counter()
        for seed, r in sorted(rows.items()):
            if seed not in prompts:
                skipped["no nomination prompt"] += 1
                continue
            lines = history(prompts[seed])
            orc, bad = replay(fit, pool, seed, lines)
            rep, _u = retests(orc)
            if bad or shrinkage_pick(orc, ps) != r["ref_shrinkage"] or rep != r["replication_count"]:
                skipped["rebuild did not reproduce the campaign"] += 1
                continue
            base, _ = replay(fit, pool, seed, lines, upto=LAST)
            reads = V.build(base, LAST, 15, 4, 60, ps).readings()
            top = sorted(reads, key=lambda s: (-sum(reads[s]) / len(reads[s]), s))
            cell = dict(seed=seed, agent_pick=r["nominated_true"], shrinkage_repick=fit[r["ref_shrinkage"]],
                        selection_shortfall=r["selection_shortfall"], best=r["best_true_measured"],
                        share_before=100.0 * r["replication_count"] / r["slots_used"], k={})
            for k in KS:
                o2, _ = replay(fit, pool, seed, lines, upto=LAST)
                cand = top[:k]
                for rnd in range(LAST + 1, 16):
                    for slot in ALLOC[k]:
                        o2.measure(cand[min(slot, len(cand) - 1)], rnd)
                nom = shrinkage_pick(o2, ps)
                rep2, used2 = retests(o2)
                n_reads = len(V.build(o2, 15, 15, 4, 60, ps).readings().get(nom, ())) if nom else 0
                cell["k"][k] = dict(pick=fit[nom] if nom else float("nan"), share=100.0 * rep2 / used2,
                                    best=o2.best_true_measured(), one_reading=n_reads == 1)
            used.append(cell)
        loss = (F0_LOSS[name](a7) if name in F0_LOSS else None)
        res = dict(campaigns=len(used), skipped=dict(skipped), k={}, selection_loss_vs_f0=loss,
                   share_before=st.mean(c["share_before"] for c in used))
        rp = [c["shrinkage_repick"] - c["agent_pick"] for c in used]
        res["repick_minus_agent_ci"] = list(AG.boot_ci(rp, tag="A1|%s|repick-agent" % name))
        sh = st.mean(c["selection_shortfall"] for c in used)
        for k in KS:
            d_agent = [c["k"][k]["pick"] - c["agent_pick"] for c in used]
            d_repick = [c["k"][k]["pick"] - c["shrinkage_repick"] for c in used]
            res["k"][str(k)] = dict(
                pick=st.mean(c["k"][k]["pick"] for c in used), d_vs_agent=st.mean(d_agent),
                d_vs_agent_ci=list(AG.boot_ci(d_agent, tag="A1|%s|%d|agent" % (name, k))), d_vs_shrinkage_repick=st.mean(d_repick),
                d_vs_shrinkage_repick_ci=list(AG.boot_ci(d_repick, tag="A1|%s|%d|repick" % (name, k))),
                recovered_share_of_selection_shortfall=st.mean(d_agent) / sh if sh else float("nan"),
                share_after=st.mean(c["k"][k]["share"] for c in used),
                exploration_given_up=st.mean(c["best"] - c["k"][k]["best"] for c in used),
                campaigns_losing_their_best=sum(c["k"][k]["best"] < c["best"] for c in used),
                nominee_one_reading=st.mean(c["k"][k]["one_reading"] for c in used))
            if loss:
                res["k"][str(k)]["recovered_share_of_selection_loss_vs_f0"] = st.mean(d_agent) / loss
        res.update(agent_pick=st.mean(c["agent_pick"] for c in used),
                   shrinkage_repick=st.mean(c["shrinkage_repick"] for c in used), selection_shortfall=sh,
                   repick_minus_agent=st.mean(c["shrinkage_repick"] - c["agent_pick"] for c in used))
        rp_ci = res["repick_minus_agent_ci"]
        res["best_k"] = max(KS, key=lambda k: res["k"][str(k)]["d_vs_agent"])
        out[name] = res
        print("%s: %d campaigns rebuilt exactly (%s skipped); agent pick %.3f, shrinkage re-pick %+.3f [%+.3f, %+.3f], "
              "selection shortfall %.3f, loss vs F0 %s, share before %.1f%%"
              % (name, len(used), dict(skipped), res["agent_pick"], res["repick_minus_agent"], rp_ci[0], rp_ci[1], sh,
                 "%+.3f" % loss if loss else "n/a", res["share_before"]))
        for k in KS:
            x = res["k"][str(k)]
            print("   k=%d: pick %.3f, change vs the agent %+.3f [%+.3f, %+.3f], vs its shrinkage re-pick %+.3f [%+.3f, %+.3f], "
                  "recovers %.0f%% of the selection shortfall, share after %.1f%%, gives up %.3f exploration (%d lose their best), "
                  "one-reading nominees %.0f%%"
                  % (k, x["pick"], x["d_vs_agent"], x["d_vs_agent_ci"][0], x["d_vs_agent_ci"][1], x["d_vs_shrinkage_repick"],
                     x["d_vs_shrinkage_repick_ci"][0], x["d_vs_shrinkage_repick_ci"][1],
                     100 * x["recovered_share_of_selection_shortfall"], x["share_after"], x["exploration_given_up"],
                     x["campaigns_losing_their_best"], 100 * x["nominee_one_reading"]))
    if LAST == 14:
        out["_label"] = "a simulation on the agents' own traces: the final round replaced by confirmation re-measurements"
        name = "confirm_counterfactual_0an7.json"
    else:
        out["_label"] = ("EXPLORATORY, it gates nothing. A simulation on the agents' own traces with the last %d rounds "
                         "replaced by confirmation re-measurements" % (15 - LAST))
        name = "confirm_counterfactual_0an7_r%d.json" % (15 - LAST)
    json.dump(out, open(os.path.join(ROOT, "results", name), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
