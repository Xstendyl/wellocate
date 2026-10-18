#!/usr/bin/env python3
"""Analysis of the GB1 Blind arm repeated on scrambled PhoQ: five models, 30 campaigns each.

Per model, the primary test asks whether the lower end of the 95% seed-bootstrap interval on the re-testing share
(replication_count / slots_used) lies above the best scripted policy's share on PhoQ at assay noise. It also reports
the final pick against the guessing rule at its best k (with the rule's own uncertainty added), exploration and
selection losses, nominee and basin descriptives, unpaired cross-checks against each model's GB1 Blind arm and an
earlier PhoQ Blind run, campaign counts (a seed abandoned twice is dropped), and spend.

Usage: python3 scripts/analyse_0an8.py [--smoke]      (writes results/analysis_0an8.json, or analysis_0an8_smoke.json)
"""
import argparse, collections, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
from repdef import envs as EV, policies as P                             # noqa: E402
import analyse_0al as A0L                                                # noqa: E402
import analyse_0an7 as A7                                                # noqa: E402
import analyse_grid as AG                                                # noqa: E402
import basins as BS                                                      # noqa: E402
import launch_0an8 as L8                                                 # noqa: E402

RES = os.path.join(ROOT, "results")
LABEL = {"opus": "Opus 4.7", "flash": "Gemini 2.5 Flash", "deepseek": "DeepSeek V3.1", "sol": "GPT-6.1 Sol",
         "gem": "Gemini 3.1 Pro"}
OAM_PHOQ = "gen_r_phoqscr"                     # earlier run: scrambled PhoQ, Blind and Mechanism, three models
OAM_MODELS = ("anthropic/claude-opus-4.7", "google/gemini-2.5-flash", "deepseek/deepseek-chat-v3.1")


def ci(v, t):
    return A7.ci(v, t)


def tags_of(short, smoke):
    # Sol alone has _cont (its unrun seeds), _cont_rerun and _fin (its last 8 seeds, run with transport retries).
    return [L8.smoke_tag(short)] if smoke else [L8.main_tag(short) + x for x in ("", "_rerun", "_cont", "_cont_rerun", "_fin")]


def counts(short, smoke):
    if smoke:
        t = L8.smoke_tag(short)
        return dict(written=len(L8.rows(t)), abandoned=L8.first_pass_abandoned(t), rerun_written=[], dropped=[])
    t = L8.main_tag(short)
    gone = L8.first_pass_abandoned(t)
    rer = sorted(r["seed"] for r in L8.rows(t + "_rerun"))
    twice = L8.first_pass_abandoned(t + "_rerun") + L8.first_pass_abandoned(t + "_cont_rerun") + \
        L8.first_pass_abandoned(t + "_fin")
    return dict(written=len(L8.rows(t)), abandoned=gone, rerun_written=rer, dropped=twice,
                continuation_written=sorted(r["seed"] for r in L8.rows(t + "_cont")),
                continuation_abandoned=L8.first_pass_abandoned(t + "_cont"),
                continuation_rerun_written=sorted(r["seed"] for r in L8.rows(t + "_cont_rerun")),
                rerun_abandoned=L8.first_pass_abandoned(t + "_rerun"),
                finish_written=sorted(r["seed"] for r in L8.rows(t + "_fin")),
                finish_dropped=L8.first_pass_abandoned(t + "_fin"),
                stopped=(L8.state().get("stopped") or {}).get(short))


def campaign_rows(short, model, smoke):
    rows = []
    for t in tags_of(short, smoke):
        rows += [r for r in A7.rows_of(t) if r["model"] == model]
    seeds = collections.Counter(r["seed"] for r in rows)
    dup = [s for s, n in seeds.items() if n > 1]
    if dup:
        raise SystemExit("REFUSED: %s has seeds written twice: %s" % (short, dup[:5]))
    return rows


def nominee_prompts(tags, model):
    out = {}
    for t in tags:
        for c in A0L.calls(t):
            if c.get("model") == model and c.get("kind") == "nomination":
                out[c["campaign_seed"]] = c["prompt"]
    return out


def basin_view(rows, prompts, fit, peak, gpeak, start, tag):
    cells = [dict(start=start, nominee=r["nominated"], measured=BS.measured(prompts[r["seed"]]))
             for r in rows if r["seed"] in prompts]
    d = BS.summarise(cells, gpeak, fit, peak, tag) if len(cells) > 1 else dict(n=len(cells))
    d["campaigns_without_a_nomination_prompt"] = len(rows) - len(cells)
    return d


def calls_view(tags, model):
    every = [c for t in tags for c in A0L.calls(t) if c.get("model") == model]
    # Transport retries are logged as rows of their own kind and counted apart.
    retries = [c for c in every if c.get("kind") == "transport_retry"]
    calls = [c for c in every if c.get("kind") != "transport_retry"]
    prov = collections.Counter(c.get("provider") or "?" for c in calls)
    rt = [c.get("reasoning_tokens") or 0 for c in calls]
    return dict(calls=len(calls), providers={k: round(100.0 * v / len(calls), 1) for k, v in prov.most_common()} if calls else {},
                median_reasoning_tokens=st.median(rt) if rt else None, max_reasoning_tokens=max(rt) if rt else None,
                empty_answers=sum(1 for c in calls if c.get("empty_text")),
                truncated=sum(1 for c in calls if c.get("finish_reason") == "length"),
                genuine_parser_disagreements=sum(1 for c in calls if L8.genuine_disagreement(c)),
                # replies that are a bare single valid token, which the primary parser read
                bare_token_agreements=sum(1 for c in calls if not c.get("parsers_agree", True) and L8.bare_single_token(c)),
                transport_retries=len(retries), transport_retry_wait_s=sum(c.get("wait_s") or 0 for c in retries),
                campaigns_with_transport_retries=len({c.get("campaign_seed") for c in retries}))


def side(tags, model, cond="Blind"):
    rows = [r for t in tags.split("+") for r in A7.rows_of(t, cond) if r["model"] == model]
    sb, pk = [A7.share_b(r) for r in rows], [r["nominated_true"] for r in rows]
    return dict(tags=tags, n=len(rows), share_budget=st.mean(sb), share_budget_ci=ci(sb, "0an8side|%s|%s|sb" % (tags, model)),
                pick=st.mean(pk), pick_ci=ci(pk, "0an8side|%s|%s|pk" % (tags, model)))


def spend(short, smoke):
    rec = {t: sum(r["spend"] for r in L8.rows(t)) for t in [L8.smoke_tag(short)] + ([] if smoke else tags_of(short, False))}
    s = L8.state()
    end = (s.get("model_end") or {}).get(short) or {}
    cont = (s.get("cont_end") or {}).get(short) or {}
    fin = (s.get("fin_end") or {}).get(short) or {}
    return dict(recorded=rec, recorded_total=sum(rec.values()), main_by_balance=end.get("by_balance"),
                start_balance=(s.get("model_start") or {}).get(short), end_balance=end.get("balance"),
                continuation_by_balance=cont.get("by_balance"), finish_by_balance=fin.get("by_balance"),
                by_balance_total=((end.get("by_balance") or 0) + (cont.get("by_balance") or 0)
                                  + (fin.get("by_balance") or 0)) if end else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    ref = json.load(open(os.path.join(RES, "references_0an8.json")))
    best = ref["best_scripted"]
    gk = ref["guessing_kstar"]
    g = ref["reference"]["guessing k=%d" % gk]
    env = EV.phoq_scrambled()
    fit, pool = env.fit, env.pool
    peak, _size = BS.basins(fit, pool, P.alphabet_of(tuple(sorted(fit))))
    gpeak = max(fit[p] for p in pool)
    out = dict(smoke=a.smoke, references=dict(best_scripted=best, guessing_kstar=gk, guessing_at_kstar=g,
                                              informed_kstar=ref["informed_kstar"],
                                              informed_at_kstar=ref["reference"]["informed k=%d" % ref["informed_kstar"]],
                                              model_guided=ref["reference"]["model-guided k=1 with confirmation"],
                                              guessing_curve={k: ref["reference"]["guessing k=%d" % k] for k in range(5)}),
               models={})
    gh = 1.96 * g["pick_se"]
    for short, model, _tok, _eff, _ceil in L8.MODELS:
        tags = tags_of(short, a.smoke)
        rows = campaign_rows(short, model, a.smoke)
        if len(rows) < 2:
            out["models"][LABEL[short]] = dict(n=len(rows), counts=counts(short, a.smoke))
            continue
        reads = A7.nominee_readings("+".join(tags))
        t = "0an8%s|%s" % ("smoke" if a.smoke else "", short)
        d = A7.describe(rows, reads, t)
        for k in ("exploration_shortfall", "selection_shortfall", "distinct"):
            v = [r["exploration_shortfall"] if k == "exploration_shortfall" else
                 r["selection_shortfall"] if k == "selection_shortfall" else r["n_distinct_measured"] for r in rows]
            d[k + "_ci"] = ci(v, t + "|" + k)
        d["nominee_one_reading"] *= 100.0
        d["nominees_without_history"] = sum(1 for r in rows if (r["model"], r["seed"]) not in reads)
        d["nominee_highest_single"] *= 100.0
        # primary test
        lo = d["share_budget_ci"][0]
        d["primary"] = dict(best_scripted_policy=best["policy"], best_scripted_share=best["share_budget"],
                            share_minus_best=d["share_budget"] - best["share_budget"],
                            interval_above_best=lo is not None and lo > best["share_budget"])
        d["named_test"] = dict(claim="re-tests more than the best scripted policy, as on GB1",
                               extends_to_phoq=d["primary"]["interval_above_best"],
                               sensitivity_vs_guessing_kstar=dict(guessing_share=g["share_budget"],
                                                                  interval_above=lo is not None and lo > g["share_budget"]))
        # pick against the guessing rule, adding its uncertainty
        ph = (d["pick_ci"][1] - d["pick_ci"][0]) / 2.0
        lead = d["pick"] - g["pick"]
        lo_h = ((d["pick"] - d["pick_ci"][0]) ** 2 + gh ** 2) ** 0.5
        hi_h = ((d["pick_ci"][1] - d["pick"]) ** 2 + gh ** 2) ** 0.5
        d["secondary"] = dict(pick_minus_guessing=lead, pick_minus_guessing_ci=[lead - lo_h, lead + hi_h],
                              pick_half_width=ph, guessing_pick=g["pick"], guessing_pick_se=g["pick_se"],
                              guessing_exploration_shortfall=g["exploration_shortfall"],
                              guessing_selection_shortfall=g["selection_shortfall"])
        # pick paired by seed with the guessing rule at k* on the same seeds
        twin = ref["agent_seeds_rows"]["guessing k=%d" % gk]
        by_seed = {L8.SEED0 + i: r for i, r in enumerate(twin)}
        pr = [(r["nominated_true"], by_seed[r["seed"]]["pick"]) for r in rows
              if r["seed"] in by_seed and by_seed[r["seed"]] is not None]
        if len(pr) > 1:
            dd = [x - y for x, y in pr]
            d["paired_vs_guessing_same_seeds"] = dict(pairs=len(dd), diff=st.mean(dd), ci=ci(dd, t + "|paired_guess"))
        prompts = nominee_prompts(tags, model)
        d["basin"] = basin_view(rows, prompts, fit, peak, gpeak, env.anchor, t + "|basin")
        d["out_of_alphabet_proposals"] = sum(r.get("out_of_alphabet_proposals") or 0 for r in rows)
        d["campaigns_with_out_of_alphabet"] = sum(1 for r in rows if r.get("out_of_alphabet_proposals"))
        d["calls"] = calls_view(tags, model)
        d["counts"] = counts(short, a.smoke)
        d["spend"] = spend(short, a.smoke)
        # descriptive cross-checks
        gb1 = [x for x in BS.ARMS["GB1 Blind"] if x[1] == model]
        if gb1:
            d["gb1_blind"] = side(gb1[0][2], model)
            if "+" in gb1[0][2]:
                # Opus 4.7's GB1 arm has 60 campaigns; its first 30 seeds are also reported on their own.
                d["gb1_blind_first_tag_only"] = side(gb1[0][2].split("+")[0], model)
        if model in OAM_MODELS:
            d["oam_phoq_blind"] = side(OAM_PHOQ, model)
        out["models"][LABEL[short]] = d
        print("%-17s n=%2d share %5.1f%% [%5.1f, %5.1f] (best scripted %.2f%%: above %s; guessing %.2f%%: above %s) | "
              "pick %.3f [%.3f, %.3f], minus guessing %+.3f [%+.3f, %+.3f] | explore %.2f select %.2f | distinct %.1f | "
              "one reading %.0f%% | top nominee %s x%d"
              % (LABEL[short], d["n"], d["share_budget"], d["share_budget_ci"][0], d["share_budget_ci"][1],
                 best["share_budget"], d["primary"]["interval_above_best"], g["share_budget"],
                 d["named_test"]["sensitivity_vs_guessing_kstar"]["interval_above"], d["pick"], d["pick_ci"][0],
                 d["pick_ci"][1], lead, *d["secondary"]["pick_minus_guessing_ci"], d["exploration_shortfall"],
                 d["selection_shortfall"], d["distinct"], d["nominee_one_reading"], d["top_nominee"],
                 d["top_nominee_count"]))
    done = [m for m in out["models"].values() if "named_test" in m]
    out["named_test_all_models"] = dict(models=len(done), extends=sum(1 for m in done if m["named_test"]["extends_to_phoq"]),
                                        holds_for_all_five=len(done) == 5 and all(m["named_test"]["extends_to_phoq"] for m in done))
    bal = L8.balances()
    s = L8.state()
    out["panel_spend"] = dict(recorded=sum(m.get("spend", {}).get("recorded_total", 0) for m in out["models"].values()),
                              balance_rows=bal,
                              # start balance minus the last balance read, so every later run counts
                              by_balance=(s["panel_start"] - [b for b in bal if b.get("balance") is not None][-1]["balance"])
                              if s.get("panel_start") and bal else None,
                              last_balance_event=[b for b in bal if b.get("balance") is not None][-1]["event"] if bal else None)
    path = os.path.join(RES, "analysis_0an8%s.json" % ("_smoke" if a.smoke else ""))
    json.dump(out, open(path, "w"), indent=1)
    print("named test: extends to PhoQ for %d of %d models; wrote %s"
          % (out["named_test_all_models"]["extends"], len(done), os.path.relpath(path, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
