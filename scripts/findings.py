#!/usr/bin/env python3
"""Index of every result: one row per experiment, with its numbers read from its sources by code.

Writes results/findings.json. Each row gives the question, data tags, analysis files,
commits, n per cell, headline numbers, outcome, paper status and limits. Headline numbers are either keys of
verify_paper_numbers.computed() or paths into an analysis JSON; a row's paper status is where its first verifier
key is printed (main text, appendix only, or nowhere).

--check rebuilds every row and fails when a number, n or paper status differs from the committed findings.json,
or when an analysis_*.json file or campaign tag in results/ belongs to no row. Rows marked pending are not compared.

Usage: python3 scripts/findings.py            (rebuild both files)
       python3 scripts/findings.py --check    (compare with the committed findings.json; exit 1 on a mismatch)
"""
import collections, glob, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# Which files are main text and which appendix is read from paper/main.tex (scripts/paper_files.py).
CORE = ["stage1", "topup_opus", "topup_gemini", "topup_deepseek"]


def V(key):
    return ("verifier", key)


def J(f, *path):
    return ("json", f, list(path))


# PhoQ panel headline numbers: per model, read by path from analysis_0an8.json, then the references and the spend.
PQ_FILE = "analysis_0an8.json"
PQ_HEADLINE = []
for _m in ("Opus 4.7", "Gemini 2.5 Flash", "DeepSeek V3.1", "GPT-6.1 Sol", "Gemini 3.1 Pro"):
    _J = lambda *path: J(PQ_FILE, "models", _m, *path)
    PQ_HEADLINE += [("%s, PhoQ campaigns" % _m, _J("n")),
                    ("%s, PhoQ re-testing share, %%" % _m, _J("share_budget"), _J("share_budget_ci")),
                    ("%s, PhoQ share over slots not lost, %%" % _m, _J("share_nonlost"), _J("share_nonlost_ci")),
                    ("%s, PhoQ final pick" % _m, _J("pick"), _J("pick_ci")),
                    ("%s, PhoQ pick minus the guessing rule" % _m, _J("secondary", "pick_minus_guessing"),
                     _J("secondary", "pick_minus_guessing_ci")),
                    ("%s, PhoQ exploration loss" % _m, _J("exploration_shortfall"), _J("exploration_shortfall_ci")),
                    ("%s, PhoQ selection loss" % _m, _J("selection_shortfall"), _J("selection_shortfall_ci")),
                    ("%s, PhoQ distinct candidates" % _m, _J("distinct")),
                    ("%s, PhoQ nominees with one reading, %%" % _m, _J("nominee_one_reading")),
                    ("%s, PhoQ top nominee count" % _m, _J("top_nominee_count")),
                    ("%s, PhoQ named claim extends (1 = yes)" % _m, _J("named_test", "extends_to_phoq")),
                    ("%s, PhoQ slots lost to incomplete rounds per campaign" % _m, _J("lost_rounds"))]
for _m in ("Opus 4.7", "Gemini 2.5 Flash", "DeepSeek V3.1"):
    # the earlier PhoQ Blind run of the same model on other seeds: a descriptive replication
    _O = (lambda m: (lambda *path: J(PQ_FILE, "models", m, "oam_phoq_blind", *path)))(_m)
    PQ_HEADLINE += [("%s, 0am PhoQ Blind campaigns" % _m, _O("n")),
                    ("%s, 0am PhoQ Blind share, %%" % _m, _O("share_budget"), _O("share_budget_ci")),
                    ("%s, 0am PhoQ Blind pick" % _m, _O("pick"), _O("pick_ci"))]
PQ_HEADLINE += [
    ("PhoQ best scripted share, %", J(PQ_FILE, "references", "best_scripted", "share_budget")),
    ("PhoQ best scripted pick (informed rule, k = 0)", J(PQ_FILE, "references", "best_scripted", "pick")),
    ("PhoQ guessing rule share at k* = 0, %", J(PQ_FILE, "references", "guessing_at_kstar", "share_budget")),
    ("PhoQ guessing rule pick at k* = 0", J(PQ_FILE, "references", "guessing_at_kstar", "pick")),
    ("PhoQ model-guided share, %", J(PQ_FILE, "references", "model_guided", "share_budget")),
    ("PhoQ model-guided pick", J(PQ_FILE, "references", "model_guided", "pick")),
    ("named claim holds for all five (1 = yes)", J(PQ_FILE, "named_test_all_models", "holds_for_all_five")),
    ("panel spend by credit balance, smoke included, $", J(PQ_FILE, "panel_spend", "by_balance")),
    ("panel spend by campaign records, smoke included, $", J(PQ_FILE, "panel_spend", "recorded"))]


# PhoQ panel descriptive rows (not pre-registered), read by path from landscapes_0an8.json.
LS_FILE = "landscapes_0an8.json"
LS_MODELS = ("Opus 4.7", "Gemini 2.5 Flash", "DeepSeek V3.1", "GPT-6.1 Sol", "Gemini 3.1 Pro")
LS_HEADLINE, LS_PAIRED = [], []
for _land in ("grid", "GB1", "PhoQ"):
    for _m in LS_MODELS:
        _J = (lambda land, m: (lambda *path: J(LS_FILE, "cells", land, m, *path)))(_land, _m)
        LS_HEADLINE += [("%s, %s, campaigns" % (_land, _m), _J("n")),
                        ("%s, %s, re-testing share, %%" % (_land, _m), _J("share"), _J("share_ci")),
                        ("%s, %s, final pick" % (_land, _m), _J("pick"), _J("pick_ci")),
                        ("%s, %s, nominees with one reading, %%" % (_land, _m), _J("one_reading_pct"))]
    LS_HEADLINE += [("%s, best scripted share, %%" % _land, J(LS_FILE, "references", _land, "best", "share_budget")),
                    ("%s, best scripted pick" % _land, J(LS_FILE, "references", _land, "best", "pick")),
                    ("%s, guessing rule share, %%" % _land, J(LS_FILE, "references", _land, "guessing", "share")),
                    ("%s, guessing rule pick" % _land, J(LS_FILE, "references", _land, "guessing", "pick"))]
for _land in ("GB1", "PhoQ"):
    for _m in LS_MODELS:
        LS_PAIRED += [("%s, %s, pick minus the guessing rule, paired by seed" % (_land, _m),
                       J(LS_FILE, "paired_with_guessing", _land, _m, "diff"),
                       J(LS_FILE, "paired_with_guessing", _land, _m, "ci")),
                      ("%s, %s, pairs" % (_land, _m), J(LS_FILE, "paired_with_guessing", _land, _m, "pairs"))]
LS_SOL = [("Sol PhoQ lead over the guessing rule, %s" % _v, J(LS_FILE, "sol_phoq_by_nominee", "by_role", _k, "lead"),
           J(LS_FILE, "sol_phoq_by_nominee", "by_role", _k, "lead_ci"))
          for _k, _v in (("registered", "as registered"), ("by_nominee", "grouped by nominee"),
                         ("top_once", "top nominee counted once"),
                         ("top_once_by_nominee", "top nominee once, grouped by nominee"))]
LS_SOL += [("Sol PhoQ top nominee campaigns", J(LS_FILE, "sol_phoq_by_nominee", "top_nominee_campaigns")),
           ("Sol PhoQ distinct nominees", J(LS_FILE, "sol_phoq_by_nominee", "distinct_nominees"))]

# One row per experiment or panel. "status" is the claim; for rows with verifier keys it is also checked.
ROWS = [
    dict(id="stage 0", amendment="0n", tags=["stage0"], analysis=[],
         question="The first full stage 1; void because the environment misreported the budget to the agent.",
         headline=[], outcome="void (0n); kept as the record of the truncated nomination prompt (0r)",
         status="withdrawn", limits="Prompts were truncated; no number from it is used."),
    dict(id="stage 1a", amendment="0r", tags=["stage1a"], analysis=[],
         question="The second stage-1 attempt, superseded after the aggregated-history fix.",
         headline=[], outcome="superseded", status="withdrawn", limits="No number from it is used."),
    dict(id="pre-grid probes", amendment="0q, 0u", tags=["probe", "probe2", "probe3", "rprobe", "rprobe20k"],
         analysis=["reasoning_budget_rprobe.json", "reasoning_budget_rprobe20k.json"],
         question="Whether the harness and the reasoning budget behave before the grid runs.",
         headline=[], outcome="used to set panel (c)'s ceiling", status="not yet in paper",
         limits="Smoke-sized; operational only."),
    dict(id="core grid", amendment="0e, 0o, 0w", tags=CORE, analysis=["strict_replication.json"],
         question="How much agents re-test, across five prompt conditions and three models.",
         headline=[("lowest replication share, %", V("75.4")), ("highest replication share, %", V("95.6")),
                   ("fewest distinct candidates", V("2.57")), ("most distinct candidates", V("11.34")),
                   ("lowest cell mean pick", V("7.6308")), ("highest cell mean pick", V("7.8501")),
                   ("strict share, lowest cell", V("74.7"))],
         outcome="every cell re-tests far above the guessing yardstick's 23.78%", status="appendix",
         limits="One landscape (NK K = 1), three models, a minimal prompt-only agent."),
    dict(id="scripted yardsticks", amendment="0ai, 0al", tags=[],
         analysis=["reference_curve_alphabet.json", "riskfree_reference_alphabet.json", "yardstick_fix_table.json",
                   "loss_vs_guessing.json", "reference_percentile.json"],
         question="What re-testing the landscape warrants, for a scripted policy playing the same rules.",
         headline=[("guessing policy pick at k*, two decimals", V("7.87")),
                   ("guessing policy pick at k*", V("7.8659")), ("informed policy pick at k*", V("7.9993")),
                   ("guessing share at k*, %", V("23.78")), ("risk-free share at k*, %", V("23.96")),
                   ("guessing distinct at k*", V("28.94"))],
         outcome="k* = 1 under both; corrected alphabet in 0al (published 7.8909 and 23.72)", status="main text",
         limits="Scripted policies on the grid's landscape only."),
    dict(id="zero-noise panel", amendment="0q, 0x", tags=["zeronoise"], analysis=[],
         question="Whether agents still re-test when readings are exact.",
         headline=[("lowest zero-noise level, %", V("51.8")), ("highest zero-noise level, %", V("97.5")),
                   ("median zero-noise level, %", V("90.6"))],
         outcome="re-testing persists with exact readings", status="appendix",
         limits="Same landscape; the prompt still states failures."),
    dict(id="central test", amendment="0ad", tags=["zeronoise"] + CORE, analysis=[],
         question="Whether post-repeat replication drops when noise is removed.",
         headline=[("largest zero-noise drop, points", V("35.0")), ("smallest zero-noise drop, points", V("0.9"))],
         outcome="as registered in 0ad", status="appendix", limits="Paired by seed with the grid."),
    dict(id="reasoning panel (c)", amendment="0u, 0y", tags=["panelc"], analysis=[],
         question="Whether switching reasoning on changes re-testing and the final pick.",
         headline=[("smallest drop in final pick", V("0.099")), ("largest drop in final pick", V("0.263"))],
         outcome="reasoning lowers the final pick", status="appendix",
         limits="Opus 4.7 and Gemini 2.5 Flash only; DeepSeek excluded (0y)."),
    dict(id="temperature panel (b)", amendment="0q", tags=["tpanel"], analysis=["step6_temperature_zero_determinism.json"],
         question="Whether temperature 1.0 changes re-testing under Mechanism.",
         headline=[], outcome="replication moves little (appendix)", status="appendix",
         limits="Mechanism only; one temperature."),
    dict(id="biology framing panel", amendment="0aa", tags=["bioframing"], analysis=["bio_contrasts.json",
                                                                                     "bio_coverage.json"],
         question="Whether a biology-lab framing changes re-testing.",
         headline=[("Role minus grid Blind, Opus, points",
                    J("bio_contrasts.json", "Role - grid Blind|unpaired|anthropic/claude-opus-4.7", "diff"))],
         outcome="see 0aa", status="appendix", limits="Blind rung only; unpaired against the grid."),
    dict(id="out-of-sample replication", amendment="0ak", tags=["replication_dsdr"],
         analysis=["replication_decision_rule.json", "replication_vs_original.json"],
         question="Whether the one contrast that survived Holm replicates on new seeds.",
         headline=[("Decision-rule arm mean", V("7.736")), ("Mechanism arm, original", V("7.664")),
                   ("Mechanism arm, replication", V("7.728"))],
         outcome=("label", "replication_decision_rule.json", ["label"]), status="appendix",
         limits="DeepSeek V3.1 only; one contrast."),
    dict(id="0al Panel A (wording fixes)", amendment="0al", tags=["panelA_wording"],
         analysis=["analysis_0al.json", "analysis_0al_panelA_only.json"],
         question="Whether two prompt wording fixes change re-testing or the final pick.",
         headline=[("Gemini Blind share change, points", V("4.6")), ("Gemini Mechanism pick change", V("0.160"))],
         outcome=("label", "analysis_0al.json", ["panel_A", "label"]), status="appendix",
         limits="Blind and Mechanism only; seeds 300,000 to 300,059."),
    dict(id="0al Panel B (risk-free rejections)", amendment="0al", tags=["panelB_riskfree"], analysis=["analysis_0al.json"],
         question="Whether making rejections free changes re-testing.",
         headline=[("lowest Panel B share, %", V("74.8")), ("Opus Mechanism pick change", V("0.1340"))],
         outcome=("label", "analysis_0al.json", ["panel_B", "label"]), status="appendix",
         limits="All three 0al options at once."),
    dict(id="0al Panel A0 (drift control)", amendment="0al.1", tags=["panelA0_original"], analysis=["analysis_0al.json"],
         question="How far a same-design rerun drifts from the grid a few days later.",
         headline=[("Opus Blind share drift, points",
                    J("analysis_0al.json", "panel_A0", "drift_vs_grid", "cells", "Blind|claude-opus-4.7", "d_share")),
                   ("Opus Blind pick drift",
                    J("analysis_0al.json", "panel_A0", "drift_vs_grid", "cells", "Blind|claude-opus-4.7", "d_fit")),
                   ("DeepSeek Blind pick drift",
                    J("analysis_0al.json", "panel_A0", "drift_vs_grid", "cells", "Blind|deepseek-chat-v3.1", "d_fit"))],
         outcome="drift small against the grid; Opus's control for 0an", status="not yet in paper",
         limits="One rerun; seeds 300,000 to 300,059."),
    dict(id="rejections per new name", amendment="(descriptive)", tags=[], analysis=["rejection_rates.json"],
         question="Whether agents guess viability better than the guessing policy, per new name ordered.",
         headline=[("agents rejected per new name, %", V("72.2")), ("guessing policy, %", V("74.4")),
                   ("lowest cell, %", V("68.5")), ("highest cell, %", V("89.0"))],
         outcome="about as well; 8 of 15 cells worse, 7 better", status="appendix",
         limits="One convention for new names; core grid only."),
    dict(id="learnability", amendment="(descriptive)", tags=[],
         analysis=["learnability_claims.json", "learnability_sim.json", "learnability_fresh_n200.json",
                   "learnability_fresh_n1500.json", "learnability_sim_n200.json", "learnability_sim_n1500.json",
                   "learnability_fresh_n200_rescored.json", "learnability_fresh_n1500_rescored.json"],
         question="Whether the landscape is learnable enough that exploring pays.",
         headline=[("lowest learned score, training endpoints", V("0.122")),
                   ("highest learned score, training endpoints", V("7.765"))],
         outcome="see appendix", status="appendix", limits="Simulated landscapes."),
    dict(id="0am Panel R (new landscapes)", amendment="0am", tags=["gen_r_gb1scr", "gen_r_gb1real", "gen_r_phoqscr",
                                                                  "gen_r_gb1scr_top", "gen_r_gb1real_top"],
         analysis=["analysis_0am.json", "checks_0am.json", "yardsticks_0am.json", "plan_0am.json"],
         question="Whether re-testing generalises to GB1 and PhoQ landscapes.",
         headline=[('Opus scrambled GB1 Blind share, %', J("analysis_0am.json", "panel_R", "gb1_scrambled|Blind|claude-opus-4.7", "share"), J("analysis_0am.json", "panel_R", "gb1_scrambled|Blind|claude-opus-4.7", "share_ci")),
                   ('Opus ratio of share change to yardstick change', J("analysis_0am.json", "adaptation", "panel_R", "gb1_scrambled|Blind|claude-opus-4.7", "ratio"), J("analysis_0am.json", "adaptation", "panel_R", "gb1_scrambled|Blind|claude-opus-4.7", "ratio_ci"))],
         outcome="re-testing generalises in every labelled cell", status="not yet in paper",
         limits="Two scrambled and one real landscape; Opus n = 60, others as registered."),
    dict(id="0am knowledge effect (GB1 real vs scrambled)", amendment="0am", tags=["gen_r_gb1real", "gen_r_gb1scr"],
         analysis=["analysis_0am.json"],
         question="Whether knowing the protein changes how much agents re-test.",
         headline=[('Opus Blind share, real minus scrambled, points', J("analysis_0am.json", "gb1_real_minus_scrambled", "Blind|claude-opus-4.7", "d_share"), J("analysis_0am.json", "gb1_real_minus_scrambled", "Blind|claude-opus-4.7", "d_share_ci")),
                   ('Opus Mechanism share, real minus scrambled, points', J("analysis_0am.json", "gb1_real_minus_scrambled", "Mechanism|claude-opus-4.7", "d_share"), J("analysis_0am.json", "gb1_real_minus_scrambled", "Mechanism|claude-opus-4.7", "d_share_ci")),
                   ('Opus Blind pick, real minus scrambled', J("analysis_0am.json", "gb1_real_minus_scrambled", "Blind|claude-opus-4.7", "d_pick"), J("analysis_0am.json", "gb1_real_minus_scrambled", "Blind|claude-opus-4.7", "d_pick_ci"))],
         outcome="mainly changes which candidates are tried; shifts re-testing a little", status="not yet in paper",
         limits="One protein; recall measured separately."),
    dict(id="0am Gemini real-GB1 slot loss", amendment="0am.3", tags=["gen_r_gb1real"], analysis=["analysis_0am.json"],
         question="Whether Gemini's low share on real GB1 is a knowledge effect or slot loss.",
         headline=[("share, raw, %", J("analysis_0am.json", "panel_R", "gb1_real|Blind|gemini-2.5-flash", "share")),
                   ("share over non-lost slots, %",
                    J("analysis_0am.json", "panel_R", "gb1_real|Blind|gemini-2.5-flash", "share_non_lost")),
                   ("lost slots per campaign",
                    J("analysis_0am.json", "panel_R", "gb1_real|Blind|gemini-2.5-flash", "lost_slots_mean"))],
         outcome="slot loss dominates; not presented as a knowledge effect", status="not yet in paper",
         limits="One cell."),
    dict(id="0am Panel K (ruggedness)", amendment="0am", tags=["gen_k0", "gen_k1", "gen_k2", "gen_k3"],
         analysis=["analysis_0am.json"],
         question="Whether re-testing tracks how rugged the landscape is.",
         headline=[('Opus share slope per K, points', J("analysis_0am.json", "panel_K_trend", "claude-opus-4.7", "slope_share_per_K"), J("analysis_0am.json", "panel_K_trend", "claude-opus-4.7", "ci")),
                   ('Opus adaptation slope', J("analysis_0am.json", "adaptation", "panel_K", "claude-opus-4.7", "slope"), J("analysis_0am.json", "adaptation", "panel_K", "claude-opus-4.7", "ci")),
                   ('Gemini adaptation slope', J("analysis_0am.json", "adaptation", "panel_K", "gemini-2.5-flash", "slope"), J("analysis_0am.json", "adaptation", "panel_K", "gemini-2.5-flash", "ci")),
                   ('DeepSeek adaptation slope', J("analysis_0am.json", "adaptation", "panel_K", "deepseek-chat-v3.1", "slope"), J("analysis_0am.json", "adaptation", "panel_K", "deepseek-chat-v3.1", "ci"))],
         outcome="adaptation slopes near 0 or negative; agents do not track the warranted re-testing",
         status="not yet in paper", limits="NK only, 20 landscapes per K."),
    dict(id="0am smokes", amendment="0am, 0am.2", tags=["smoke0am_gb1scr", "smoke0am_phoqscr", "smoke0am_nk3",
                                                        "smoke0am2_gb1scr", "smoke0am2_gb1real", "smoke0am2_phoqscr",
                                                        "smoke0am2_nk3"],
         analysis=[], question="Whether the 0am panels run cleanly before launch.",
         headline=[], outcome="first smoke failed (canary, out-of-alphabet); second passed under 0am.2/0am.3",
         status="not yet in paper", limits="One campaign per cell."),
    dict(id="0an smokes (F0, F1, F2)", amendment="0an", tags=["smoke0an_f0_control", "smoke0an_f1_ledger",
                                                              "smoke0an_f2_menu"],
         analysis=["menu_usage_smoke0an_f2_menu.json", "options_0an.json", "plan_0an.json", "openrouter_prices_0an.json"],
         question="Whether the 0an tools run cleanly, and how much the menu is used.",
         headline=[("Opus new names taken from the menu",
                    J("menu_usage_smoke0an_f2_menu.json", "anthropic/claude-opus-4.7", "new_from_menu_share")),
                   ("Opus menu suggestions viable",
                    J("menu_usage_smoke0an_f2_menu.json", "anthropic/claude-opus-4.7", "viable_share"))],
         outcome="gate failed on F2 cost and F3 slot loss; F2 resized to Opus n = 30 (0an.1)",
         status="not yet in paper", limits="Two campaigns per model."),
    dict(id="0an F3 cap smokes", amendment="0an, 0an.1, 0an.2", tags=["smoke0an_f3_cap", "smoke0an1_f3_cap"],
         analysis=["f3_smokes_descriptive.json", "lost_rounds_smoke0an1_f3_cap.json",
                   "capped_replies_smoke0an_f3_cap.json", "capped_replies_smoke0an1_f3_cap.json",
                   "resmoke_f3_check_0an1.json", "scan_false_slot_lost.json"],
         question="Whether blocking re-tests redirects agents to useful exploration.",
         headline=[("rejections over grid Blind mean, lowest",
                    J("f3_smokes_descriptive.json", "over_grid_blind", "rejections", "min")),
                   ("rejections over grid Blind mean, highest",
                    J("f3_smokes_descriptive.json", "over_grid_blind", "rejections", "max"))],
         outcome="withdrawn as a causal arm (0an.2); descriptive: more new names, mostly non-viable, readings fell",
         status="not reported: no longer cited after review changes 96 to 99", limits="One or two campaigns per model; two prompt versions; refusals hidden in 0an.1."),
    dict(id="0an panel (F0, F1, F2)", amendment="0an, 0an.1", tags=["gen_0an_f0_control", "gen_0an_f1_ledger",
                                                                     "gen_0an_f2_menu"],
         analysis=["analysis_0an.json", "readout_0an.md"],
         question="Whether a ledger or a menu of new candidates removes the re-testing.",
         headline=[('F2 Opus share change, points', J("analysis_0an.json", "cells", "F2 menu|Opus", "d_share"), J("analysis_0an.json", "cells", "F2 menu|Opus", "d_share_ci")),
                   ('F2 Gemini share change, points', J("analysis_0an.json", "cells", "F2 menu|Gemini", "d_share"), J("analysis_0an.json", "cells", "F2 menu|Gemini", "d_share_ci")),
                   ('F2 DeepSeek share change, points', J("analysis_0an.json", "cells", "F2 menu|DeepSeek", "d_share"), J("analysis_0an.json", "cells", "F2 menu|DeepSeek", "d_share_ci")),
                   ('F1 Opus share change, points', J("analysis_0an.json", "cells", "F1 ledger|Opus", "d_share"), J("analysis_0an.json", "cells", "F1 ledger|Opus", "d_share_ci")),
                   ('F1 Gemini share change, points', J("analysis_0an.json", "cells", "F1 ledger|Gemini", "d_share"), J("analysis_0an.json", "cells", "F1 ledger|Gemini", "d_share_ci")),
                   ('F1 DeepSeek share change, points', J("analysis_0an.json", "cells", "F1 ledger|DeepSeek", "d_share"), J("analysis_0an.json", "cells", "F1 ledger|DeepSeek", "d_share_ci")),
                   ('F1 Gemini pick change', J("analysis_0an.json", "cells", "F1 ledger|Gemini", "d_pick"), J("analysis_0an.json", "cells", "F1 ledger|Gemini", "d_pick_ci"))],
         outcome="F2 reduces re-testing in all three models; F1 no effect (Opus re-tests more); labels in analysis_0an.json",
         status="main text", limits="Grid landscape only; Opus n = 30 in F2; controls F0 and Panel A0."),
    dict(id="0an pick split and exploration", amendment="(descriptive)", tags=[],
         analysis=["decompose_0an.json"],
         question="Whether each arm's pick change comes from what agents found or from what they nominated.",
         headline=[('F1 Gemini exploration part', J("decompose_0an.json", "F1 ledger|Gemini", "exploration_part"), J("decompose_0an.json", "F1 ledger|Gemini", "exploration_ci")),
                   ('F1 Gemini selection part', J("decompose_0an.json", "F1 ledger|Gemini", "selection_part"), J("decompose_0an.json", "F1 ledger|Gemini", "selection_ci")),
                   ('F1 Opus exploration part', J("decompose_0an.json", "F1 ledger|Opus", "exploration_part"), J("decompose_0an.json", "F1 ledger|Opus", "exploration_ci")),
                   ('F2 Opus exploration part', J("decompose_0an.json", "F2 menu|Opus", "exploration_part"), J("decompose_0an.json", "F2 menu|Opus", "exploration_ci")),
                   ('F2 Opus selection part', J("decompose_0an.json", "F2 menu|Opus", "selection_part"), J("decompose_0an.json", "F2 menu|Opus", "selection_ci")),
                   ('F2 Gemini exploration part', J("decompose_0an.json", "F2 menu|Gemini", "exploration_part"), J("decompose_0an.json", "F2 menu|Gemini", "exploration_ci")),
                   ('F2 Gemini selection part', J("decompose_0an.json", "F2 menu|Gemini", "selection_part"), J("decompose_0an.json", "F2 menu|Gemini", "selection_ci")),
                   ('F2 DeepSeek exploration part', J("decompose_0an.json", "F2 menu|DeepSeek", "exploration_part"), J("decompose_0an.json", "F2 menu|DeepSeek", "exploration_ci")),
                   ('F2 DeepSeek selection part', J("decompose_0an.json", "F2 menu|DeepSeek", "selection_part"), J("decompose_0an.json", "F2 menu|DeepSeek", "selection_ci"))],
         outcome="see results/readout_0an.md", status="appendix",
         limits="Descriptive; paired by seed with the concurrent controls."),
    dict(id="0an.5 Opus menu top-up", amendment="0an.5", tags=["gen_0an5_f2_menu_opus"],
         analysis=["same_config_0an5.json", "opus_topup_0an5.json"],
         question="Whether Opus's menu results hold at n = 60 (decided after seeing n = 30).",
         headline=[('Opus share change at n = 60, points', J("opus_topup_0an5.json", "60", "d_share"), J("opus_topup_0an5.json", "60", "d_share_ci")),
                   ('Opus own minus list viability, rounds matched, n = 60', J("opus_topup_0an5.json", "60", "viability", "own_std_minus_list", "diff"), J("opus_topup_0an5.json", "60", "viability", "own_std_minus_list", "ci")),
                   ('Opus selection part at n = 60', J("opus_topup_0an5.json", "60", "selection_part"), J("opus_topup_0an5.json", "60", "selection_ci"))],
         outcome="n = 60 agrees with n = 30 (reduces); list against own resolves for Opus",
         status="main text", limits="Follow-up decided after seeing the n = 30 result."),
    dict(id="0an.4 model-guided scripted reference", amendment="0an.4", tags=[],
         analysis=["model_guided_0an4.json"],
         question="What a policy that learns the landscape from its own readings achieves under the grid's rules.",
         headline=[('pick at k = 1 with confirmation', J("model_guided_0an4.json", "grid", "confirm|k=1", "shrinkage")),
                   ('its standard error', J("model_guided_0an4.json", "grid", "confirm|k=1", "shrinkage_se")),
                   ('re-testing share at that best, %', J("model_guided_0an4.json", "grid", "confirm|k=1", "share")),
                   ('re-testing share at that best over slots not lost, %', J("model_guided_0an4.json", "grid", "confirm|k=1", "share_nonlost")),
                   ('pick at k = 1 without confirmation', J("model_guided_0an4.json", "grid", "no-confirm|k=1", "shrinkage")),
                   ('Panel K = 3 pick', J("model_guided_0an4.json", "panel_k", "3", "shrinkage")),
                   ('Panel K = 3 guessing yardstick', J("model_guided_0an4.json", "panel_k", "3", "guessing_yardstick_mean"))],
         outcome=("peaks at k = 1 with confirmation, between the guessing and informed references; its lead grows with "
                  "K. Its best share, 37.6% (20 points of it confirmation), stands beside the 23.78% guessing "
                  "yardstick as a second reference; the yardstick stays"),
         status="main text", limits="One scripted design; Panel K at 75 seeds per landscape."),
    dict(id="0an.6 Menu on scrambled GB1", amendment="0an.6",
         tags=["smoke0an6_gb1_menu", "smoke0an6_gb1_control", "gen_0an6_gb1_menu", "gen_0an6_gb1_control"],
         analysis=["analysis_0an6.json"],
         question="Whether the Menu's effect on re-testing holds on real protein data.",
         headline=[('Gemini share change, points', J("analysis_0an6.json", "cells", "Gemini", "d_share"), J("analysis_0an6.json", "cells", "Gemini", "d_share_ci")),
                   ('DeepSeek share change, points', J("analysis_0an6.json", "cells", "DeepSeek", "d_share"), J("analysis_0an6.json", "cells", "DeepSeek", "d_share_ci")),
                   ('Opus share change, points (non-concurrent control)', J("analysis_0an6.json", "cells", "Opus", "d_share"), J("analysis_0an6.json", "cells", "Opus", "d_share_ci")),
                   ('Gemini pick change', J("analysis_0an6.json", "cells", "Gemini", "d_pick"), J("analysis_0an6.json", "cells", "Gemini", "d_pick_ci")),
                   ('DeepSeek pick change', J("analysis_0an6.json", "cells", "DeepSeek", "d_pick"), J("analysis_0an6.json", "cells", "DeepSeek", "d_pick_ci")),
                   ('Opus pick change (descriptive)', J("analysis_0an6.json", "cells", "Opus", "d_pick"), J("analysis_0an6.json", "cells", "Opus", "d_pick_ci")),
                   ('Opus distinct candidates with the Menu', J("analysis_0an6.json", "cells", "Opus", "distinct")),
                   ('Opus distinct candidates without it (0am)', J("analysis_0an6.json", "cells", "Opus", "partner_distinct")),
                   ('Gemini control pick, 0an.6', J("analysis_0an6.json", "crosschecks", "control_reproduces_0am", "Gemini", "pick_0an6")),
                   ('Gemini control pick, 0am', J("analysis_0an6.json", "crosschecks", "control_reproduces_0am", "Gemini", "pick_0am")),
                   ('DeepSeek control pick, 0an.6', J("analysis_0an6.json", "crosschecks", "control_reproduces_0am", "DeepSeek", "pick_0an6")),
                   ('DeepSeek control pick, 0am', J("analysis_0an6.json", "crosschecks", "control_reproduces_0am", "DeepSeek", "pick_0am")),
                   ('Gemini control nominee is the start or a neighbour', J("analysis_0an6.json", "crosschecks", "control_reproduces_0am", "Gemini", "nominee_start_or_neighbour_0an6")),
                   ('DeepSeek control nominee is the start or a neighbour', J("analysis_0an6.json", "crosschecks", "control_reproduces_0am", "DeepSeek", "nominee_start_or_neighbour_0an6")),
                   ('Gemini Menu picks higher, of 60 seeds', J("analysis_0an6.json", "crosschecks", "sign_counts", "Gemini", "menu_higher")),
                   ('DeepSeek Menu picks higher, of 60 seeds', J("analysis_0an6.json", "crosschecks", "sign_counts", "DeepSeek", "menu_higher")),
                   ('Opus Menu picks higher, of 30 seeds', J("analysis_0an6.json", "crosschecks", "sign_counts", "Opus", "menu_higher")),
                   ('campaigns whose nominee beats their best measured', J("analysis_0an6.json", "crosschecks", "nominee_le_best", "exceed")),
                   ('Gemini different nominees over 60 Menu campaigns', J("analysis_0an6.json", "crosschecks", "distinct_nominees", "Gemini", "distinct")),
                   ('DeepSeek different nominees over 60 Menu campaigns', J("analysis_0an6.json", "crosschecks", "distinct_nominees", "DeepSeek", "distinct"))],
         outcome=("reduces in all three models (Opus's interval crosses -10; its control is 0am's, non-concurrent); "
                  "picks rise for Gemini and DeepSeek; the control reproduces 0am's; no nominee beats its campaign's "
                  "best; nominees are spread; the Menu reads no true value"),
         status="main text", limits="One protein, scrambled names; Opus's control is non-concurrent."),
    dict(id="0an.7 main run", amendment="0an.7",
         tags=["gen_0an7_%s_%s%s" % (m, a, r) for m in ("sol", "gem") for a in ("grid_blind", "gb1_blind", "gb1_menu")
               for r in ("", "_rerun", "_cont")],
         analysis=["analysis_0an7.json", "references_0an7.json"],
         question="How current reasoning models (GPT-6.1 Sol, Gemini 3.1 Pro) re-test, against our models and the references.",
         headline=[('Sol grid share over the budget, %', J("analysis_0an7.json", "cells", "sol|grid_blind", "share_budget"), J("analysis_0an7.json", "cells", "sol|grid_blind", "share_budget_ci")),
                   ('Gemini grid share over the budget, %', J("analysis_0an7.json", "cells", "gem|grid_blind", "share_budget"), J("analysis_0an7.json", "cells", "gem|grid_blind", "share_budget_ci")),
                   ('Sol GB1 Blind share, %', J("analysis_0an7.json", "cells", "sol|gb1_blind", "share_budget"), J("analysis_0an7.json", "cells", "sol|gb1_blind", "share_budget_ci")),
                   ('Gemini GB1 Blind share, %', J("analysis_0an7.json", "cells", "gem|gb1_blind", "share_budget"), J("analysis_0an7.json", "cells", "gem|gb1_blind", "share_budget_ci")),
                   ('Sol grid pick', J("analysis_0an7.json", "cells", "sol|grid_blind", "pick"), J("analysis_0an7.json", "cells", "sol|grid_blind", "pick_ci")),
                   ('Gemini grid pick', J("analysis_0an7.json", "cells", "gem|grid_blind", "pick"), J("analysis_0an7.json", "cells", "gem|grid_blind", "pick_ci")),
                   ('Sol minus F0 Gemini 2.5 Flash, grid share, points', J("analysis_0an7.json", "cells", "sol|grid_blind", "comparators", "0an F0 control|gemini-2.5-flash", "paired", "d_share_budget"), J("analysis_0an7.json", "cells", "sol|grid_blind", "comparators", "0an F0 control|gemini-2.5-flash", "paired", "d_share_budget_ci")),
                   ('Gemini minus F0 Gemini 2.5 Flash, grid share, points', J("analysis_0an7.json", "cells", "gem|grid_blind", "comparators", "0an F0 control|gemini-2.5-flash", "paired", "d_share_budget"), J("analysis_0an7.json", "cells", "gem|grid_blind", "comparators", "0an F0 control|gemini-2.5-flash", "paired", "d_share_budget_ci")),
                   ('Gemini minus F0 Gemini 2.5 Flash, grid selection shortfall', J("analysis_0an7.json", "cells", "gem|grid_blind", "comparators", "0an F0 control|gemini-2.5-flash", "paired", "d_selection_shortfall"), J("analysis_0an7.json", "cells", "gem|grid_blind", "comparators", "0an F0 control|gemini-2.5-flash", "paired", "d_selection_shortfall_ci")),
                   ('Gemini nominees with one reading, grid', J("analysis_0an7.json", "cells", "gem|grid_blind", "nominee_one_reading")),
                   ('Sol Menu minus Blind on GB1, share, points', J("analysis_0an7.json", "menu_minus_blind", "sol", "d_share_budget"), J("analysis_0an7.json", "menu_minus_blind", "sol", "d_share_budget_ci")),
                   ('Gemini Menu minus Blind on GB1, share, points', J("analysis_0an7.json", "menu_minus_blind", "gem", "d_share_budget"), J("analysis_0an7.json", "menu_minus_blind", "gem", "d_share_budget_ci")),
                   ('Gemini calls above 16,000 reasoning tokens', J("analysis_0an7.json", "reasoning_heavy_calls", "gem", "logged_above_16000")),
                   ('Gemini largest reasoning tokens in one call', J("analysis_0an7.json", "reasoning_heavy_calls", "gem", "logged_max")),
                   ('Sol Menu minus Blind on GB1, pick', J("analysis_0an7.json", "menu_minus_blind", "sol", "d_pick"), J("analysis_0an7.json", "menu_minus_blind", "sol", "d_pick_ci")),
                   ('Gemini Menu minus Blind on GB1, pick', J("analysis_0an7.json", "menu_minus_blind", "gem", "d_pick"), J("analysis_0an7.json", "menu_minus_blind", "gem", "d_pick_ci")),
                   ('Gemini spend by credit balance, $', J("analysis_0an7.json", "spend_reconciliation", "gem_by_balance")),
                   ('Sol recorded spend, $', J("analysis_0an7.json", "spend_reconciliation", "recorded", "sol"))],
         outcome=("both re-test far less than our earlier models; on the grid Sol sits above the band's top and Gemini "
                  "below its bottom, with picks level with F0; the Menu has no effect for Sol, and for Gemini a small "
                  "reduction, no effect on picks"),
         status="main text", limits="Reasoning models at minimal effort; one landscape family per arm."),
    dict(id="A1 counterfactual confirmation round", amendment="(descriptive)", tags=[],
         analysis=["confirm_counterfactual_0an7.json"],
         question=("Simulated on the agents' own grid traces: how much of the selection shortfall a final round of "
                   "re-measuring the top candidates would recover."),
         headline=[('Gemini 3.1 Pro, k = 4, pick change', J("confirm_counterfactual_0an7.json", "Gemini 3.1 Pro", "k", "4", "d_vs_agent"), J("confirm_counterfactual_0an7.json", "Gemini 3.1 Pro", "k", "4", "d_vs_agent_ci")),
                   ('Gemini 3.1 Pro, k = 3, pick change', J("confirm_counterfactual_0an7.json", "Gemini 3.1 Pro", "k", "3", "d_vs_agent"), J("confirm_counterfactual_0an7.json", "Gemini 3.1 Pro", "k", "3", "d_vs_agent_ci")),
                   ('Gemini 3.1 Pro, k = 4, share of its selection loss against F0 recovered', J("confirm_counterfactual_0an7.json", "Gemini 3.1 Pro", "k", "4", "recovered_share_of_selection_loss_vs_f0")),
                   ('Gemini 3.1 Pro, k = 3, share of its own selection loss recovered', J("confirm_counterfactual_0an7.json", "Gemini 3.1 Pro", "k", "3", "recovered_share_of_selection_shortfall")),
                   ('Gemini 3.1 Pro, shrinkage re-pick without the round', J("confirm_counterfactual_0an7.json", "Gemini 3.1 Pro", "repick_minus_agent"), J("confirm_counterfactual_0an7.json", "Gemini 3.1 Pro", "repick_minus_agent_ci")),
                   ('Gemini 3.1 Pro, re-testing share after the change, %', J("confirm_counterfactual_0an7.json", "Gemini 3.1 Pro", "k", "4", "share_after")),
                   ('Sol, k = 1, pick change', J("confirm_counterfactual_0an7.json", "GPT-6.1 Sol", "k", "1", "d_vs_agent"), J("confirm_counterfactual_0an7.json", "GPT-6.1 Sol", "k", "1", "d_vs_agent_ci")),
                   ('F0 DeepSeek, k = 1, pick change', J("confirm_counterfactual_0an7.json", "DeepSeek V3.1 (F0)", "k", "1", "d_vs_agent"), J("confirm_counterfactual_0an7.json", "DeepSeek V3.1 (F0)", "k", "1", "d_vs_agent_ci")),
                   ('F0 Gemini 2.5 Flash, k = 1, pick change', J("confirm_counterfactual_0an7.json", "Gemini 2.5 Flash (F0)", "k", "1", "d_vs_agent"), J("confirm_counterfactual_0an7.json", "Gemini 2.5 Flash (F0)", "k", "1", "d_vs_agent_ci"))],
         outcome=("a quarter of Gemini 3.1 Pro's selection loss at best, below the gate of half; nothing for Sol; "
                  "small gains for the F0 models, which already confirm"),
         status="main text",
         limits="A simulation on the agents' own traces; it drops the agent's round-15 exploration; every campaign rebuilt exactly."),
    dict(id="A2 Sol GB1 Blind, one nominee", amendment="(descriptive)", tags=[],
         analysis=["gb1_sensitivity_0an7.json"],
         question="Whether Sol's GB1 Blind lead over guessing rests on FSRM, nominated in 12 of 30 campaigns.",
         headline=[('pick minus guessing, as registered', J("gb1_sensitivity_0an7.json", "versions", "as registered (seed bootstrap)", "pick_minus_guessing"), J("gb1_sensitivity_0an7.json", "versions", "as registered (seed bootstrap)", "pick_minus_guessing_ci")),
                   ('pick minus guessing, cluster bootstrap by nominee', J("gb1_sensitivity_0an7.json", "versions", "cluster bootstrap by nominee", "pick_minus_guessing"), J("gb1_sensitivity_0an7.json", "versions", "cluster bootstrap by nominee", "pick_minus_guessing_ci")),
                   ('pick minus guessing, FSRM collapsed to one', J("gb1_sensitivity_0an7.json", "versions", "FSRM collapsed to one (seed bootstrap)", "pick_minus_guessing"), J("gb1_sensitivity_0an7.json", "versions", "FSRM collapsed to one (seed bootstrap)", "pick_minus_guessing_ci")),
                   ('Menu minus Blind pick, cluster bootstrap by nominee', J("gb1_sensitivity_0an7.json", "versions", "cluster bootstrap by nominee", "menu_minus_blind"), J("gb1_sensitivity_0an7.json", "versions", "cluster bootstrap by nominee", "menu_minus_blind_ci")),
                   ('Menu minus Blind pick, FSRM collapsed to one', J("gb1_sensitivity_0an7.json", "versions", "FSRM collapsed to one (seed bootstrap)", "menu_minus_blind"), J("gb1_sensitivity_0an7.json", "versions", "FSRM collapsed to one (seed bootstrap)", "menu_minus_blind_ci")),
                   ('FSRM true value', J("gb1_sensitivity_0an7.json", "top_nominee_true"))],
         outcome="'Sol beats guessing on GB1' holds as registered only; it does not survive clustering by nominee or collapsing FSRM",
         status="appendix", limits="30 campaigns, 10 distinct nominees; guessing's own error added in quadrature."),
    dict(id="Wellocate baseline scorecard (B3, B4)", amendment="(benchmark)", tags=[],
         analysis=["wellocate_scorecard.json"],
         question="What scripted baselines score on each Wellocate split, through the new API, and how fast it runs.",
         headline=[('paper grid, guessing at k*, pick', J("wellocate_scorecard.json", "splits", "nk:paper", "baselines", "guessing at k*", "pick", "mean"), J("wellocate_scorecard.json", "splits", "nk:paper", "baselines", "guessing at k*", "pick", "ci")),
                   ('paper grid, guessing at k*, share, %', J("wellocate_scorecard.json", "splits", "nk:paper", "baselines", "guessing at k*", "share_budget", "mean"), J("wellocate_scorecard.json", "splits", "nk:paper", "baselines", "guessing at k*", "share_budget", "ci")),
                   ('paper grid, informed at k*, pick', J("wellocate_scorecard.json", "splits", "nk:paper", "baselines", "informed at k*", "pick", "mean"), J("wellocate_scorecard.json", "splits", "nk:paper", "baselines", "informed at k*", "pick", "ci")),
                   ('paper grid, guessing at k*, share over slots not lost, %', J("wellocate_scorecard.json", "splits", "nk:paper", "baselines", "guessing at k*", "share_nonlost", "mean")),
                   ('paper grid, model-guided, share over slots not lost, %', J("wellocate_scorecard.json", "splits", "nk:paper", "baselines", "model-guided", "share_nonlost", "mean")),
                   ('paper grid, model-guided, share, %', J("wellocate_scorecard.json", "splits", "nk:paper", "baselines", "model-guided", "share_budget", "mean"), J("wellocate_scorecard.json", "splits", "nk:paper", "baselines", "model-guided", "share_budget", "ci")),
                   ('paper GB1, guessing at k*, pick', J("wellocate_scorecard.json", "splits", "gb1:paper", "baselines", "guessing at k*", "pick", "mean"), J("wellocate_scorecard.json", "splits", "gb1:paper", "baselines", "guessing at k*", "pick", "ci")),
                   ('GB1 test, best scripted share, %', J("wellocate_scorecard.json", "splits", "gb1:test", "best_scripted", "share_budget")),
                   ('NK test, best scripted share, %', J("wellocate_scorecard.json", "splits", "nk:test", "best_scripted", "share_budget")),
                   ('episodes per second, one core', J("wellocate_scorecard.json", "throughput", "episodes_per_s"))],
         outcome=("the paper's references reproduce through the API; the best scripted share is about one slot in four "
                  "on NK and under 1% on GB1 and PhoQ, so the right share depends on the landscape"),
         status="main text", limits="Scripted policies only; the simple confirmation policy is not tuned."),
    dict(id="Wellocate noise sweep (B9, B10)", amendment="(benchmark; CV 0.3 and 0.6 a design sweep)", tags=[],
         analysis=["wellocate_noise_sweep.json"],
         question="How the best re-testing share moves with noise, per track, under the grid rule and the risk-free rule.",
         headline=[('grid, guessing at k = 0, selection loss, low noise', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "low", "guessing", "0", "selection_shortfall", "mean"), J("wellocate_noise_sweep.json", "lands", "grid", "levels", "low", "guessing", "0", "selection_shortfall", "ci")),
                   ('grid, guessing at k = 0, selection loss, assay noise', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "assay", "guessing", "0", "selection_shortfall", "mean"), J("wellocate_noise_sweep.json", "lands", "grid", "levels", "assay", "guessing", "0", "selection_shortfall", "ci")),
                   ('grid, guessing at k = 0, selection loss, high noise', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "high", "guessing", "0", "selection_shortfall", "mean"), J("wellocate_noise_sweep.json", "lands", "grid", "levels", "high", "guessing", "0", "selection_shortfall", "ci")),
                   ('grid, guessing at k = 0, lost slots, assay noise', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "assay", "guessing", "0", "lost_slots", "mean")),
                   ('grid, guessing at k = 1, lost slots, assay noise', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "assay", "guessing", "1", "lost_slots", "mean")),
                   ('grid, k* under the grid rule, low', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "low", "kstar")),
                   ('grid, k* under the risk-free rule, low', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "low", "kstar_riskfree")),
                   ('grid, k* under the grid rule, assay', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "assay", "kstar")),
                   ('grid, k* under the risk-free rule, assay', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "assay", "kstar_riskfree")),
                   ('grid, k* under the grid rule, high', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "high", "kstar")),
                   ('grid, k* under the risk-free rule, high', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "high", "kstar_riskfree")),
                   ('grid, k* under the grid rule, cv0.3', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "cv0.3", "kstar")),
                   ('grid, k* under the risk-free rule, cv0.3', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "cv0.3", "kstar_riskfree")),
                   ('grid, k* under the grid rule, cv0.6', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "cv0.6", "kstar")),
                   ('grid, k* under the risk-free rule, cv0.6', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "cv0.6", "kstar_riskfree")),
                   ('grid, best scripted share at CV 0.3, %', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "cv0.3", "best_scripted", "share_budget", "mean")),
                   ('GB1, k* under the grid rule, assay', J("wellocate_noise_sweep.json", "lands", "GB1", "levels", "assay", "kstar")),
                   ('GB1, k* under the grid rule, cv0.3', J("wellocate_noise_sweep.json", "lands", "GB1", "levels", "cv0.3", "kstar")),
                   ('GB1, k* under the grid rule, cv0.6', J("wellocate_noise_sweep.json", "lands", "GB1", "levels", "cv0.6", "kstar")),
                   ('GB1, first noise level where k* exceeds 0, times assay noise', J("wellocate_noise_sweep.json", "lands", "GB1", "crossover", "grid rule", "times_assay")),
                   ('PhoQ, k* under the grid rule, assay', J("wellocate_noise_sweep.json", "lands", "PhoQ", "levels", "assay", "kstar")),
                   ('PhoQ, k* under the grid rule, cv0.3', J("wellocate_noise_sweep.json", "lands", "PhoQ", "levels", "cv0.3", "kstar")),
                   ('PhoQ, k* under the grid rule, cv0.6', J("wellocate_noise_sweep.json", "lands", "PhoQ", "levels", "cv0.6", "kstar")),
                   ('PhoQ, first noise level where k* exceeds 0, times assay noise', J("wellocate_noise_sweep.json", "lands", "PhoQ", "crossover", "grid rule", "times_assay")),
                   ('GB1, best scripted share at assay noise, %', J("wellocate_noise_sweep.json", "lands", "GB1", "levels", "assay", "best_scripted", "share_budget", "mean")),
                   ('PhoQ, CV 0.3, times assay noise', J("wellocate_noise_sweep.json", "lands", "PhoQ", "levels", "cv0.3", "times_assay")),
                   ('PhoQ, CV 0.6, times assay noise', J("wellocate_noise_sweep.json", "lands", "PhoQ", "levels", "cv0.6", "times_assay")),
                   ('GB1, CV 0.6, times assay noise', J("wellocate_noise_sweep.json", "lands", "GB1", "levels", "cv0.6", "times_assay")),
                   ('GB1, CV 0.6, guessing at k = 1, pick', J("wellocate_noise_sweep.json", "lands", "GB1", "levels", "cv0.6", "guessing", "1", "pick", "mean"), J("wellocate_noise_sweep.json", "lands", "GB1", "levels", "cv0.6", "guessing", "1", "pick", "ci")),
                   ('GB1, CV 0.6, guessing at k = 0, pick', J("wellocate_noise_sweep.json", "lands", "GB1", "levels", "cv0.6", "guessing", "0", "pick", "mean"), J("wellocate_noise_sweep.json", "lands", "GB1", "levels", "cv0.6", "guessing", "0", "pick", "ci")),
                   ('grid, risk-free rule, assay noise, pick at k = 1', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "assay", "riskfree", "1", "pick", "mean"), J("wellocate_noise_sweep.json", "lands", "grid", "levels", "assay", "riskfree", "1", "pick", "ci")),
                   ('grid, risk-free rule, assay noise, pick at k = 0', J("wellocate_noise_sweep.json", "lands", "grid", "levels", "assay", "riskfree", "0", "pick", "mean"), J("wellocate_noise_sweep.json", "lands", "grid", "levels", "assay", "riskfree", "0", "pick", "ci"))],
         outcome=("at assay noise the landscape sets the split: k* = 1 on the grid, 0 on GB1 and PhoQ; noise raises the cost "
                  "of skipping confirmation, and re-testing starts to pay on PhoQ at about 4 times assay noise and on GB1 at 8"),
         status="main text", limits="Scripted policies. CV 0.3 and 0.6 are a design sweep, which gates nothing."),
    dict(id="A1 exploratory: last two rounds replaced", amendment="(descriptive, exploratory)", tags=[],
         analysis=["confirm_counterfactual_0an7_r2.json"],
         question="Exploratory and non-gating. The A1 simulation with the last two rounds (8 slots) replaced by confirmation.",
         headline=[('Gemini 3.1 Pro, k = 3, pick change', J("confirm_counterfactual_0an7_r2.json", "Gemini 3.1 Pro", "k", "3", "d_vs_agent"), J("confirm_counterfactual_0an7_r2.json", "Gemini 3.1 Pro", "k", "3", "d_vs_agent_ci")),
                   ('Gemini 3.1 Pro, k = 3, share of its selection loss against F0 recovered', J("confirm_counterfactual_0an7_r2.json", "Gemini 3.1 Pro", "k", "3", "recovered_share_of_selection_loss_vs_f0")),
                   ('Gemini 3.1 Pro, k = 3, share of its own selection loss recovered', J("confirm_counterfactual_0an7_r2.json", "Gemini 3.1 Pro", "k", "3", "recovered_share_of_selection_shortfall")),
                   ('Sol, k = 1, pick change', J("confirm_counterfactual_0an7_r2.json", "GPT-6.1 Sol", "k", "1", "d_vs_agent"), J("confirm_counterfactual_0an7_r2.json", "GPT-6.1 Sol", "k", "1", "d_vs_agent_ci"))],
         outcome="exploratory: two final rounds recover about as much as one, a little over a quarter for Gemini 3.1 Pro",
         status="appendix", limits="A simulation on the agents' own traces. Exploratory; it gates nothing."),
    dict(id="headline figure data: five models on the grid", amendment="(descriptive)", tags=[],
         analysis=["paper_figdata.json"],
         question="Re-testing share, pick, exploration loss and selection loss for the five models, with intervals.",
         headline=[('Opus 4.7, re-testing share, %', J("paper_figdata.json", "models", "Opus 4.7", "share_budget", "mean"), J("paper_figdata.json", "models", "Opus 4.7", "share_budget", "ci")),
                   ('Opus 4.7, share over slots not lost, %', J("paper_figdata.json", "models", "Opus 4.7", "share_nonlost", "mean"), J("paper_figdata.json", "models", "Opus 4.7", "share_nonlost", "ci")),
                   ('Opus 4.7, median reasoning tokens per call', J("paper_figdata.json", "models", "Opus 4.7", "reasoning_tokens_median")),
                   ('Opus 4.7, largest reasoning tokens in one call', J("paper_figdata.json", "models", "Opus 4.7", "reasoning_tokens_max")),
                   ('Opus 4.7, final pick', J("paper_figdata.json", "models", "Opus 4.7", "pick", "mean"), J("paper_figdata.json", "models", "Opus 4.7", "pick", "ci")),
                   ('Opus 4.7, exploration loss', J("paper_figdata.json", "models", "Opus 4.7", "exploration_shortfall", "mean"), J("paper_figdata.json", "models", "Opus 4.7", "exploration_shortfall", "ci")),
                   ('Opus 4.7, selection loss', J("paper_figdata.json", "models", "Opus 4.7", "selection_shortfall", "mean"), J("paper_figdata.json", "models", "Opus 4.7", "selection_shortfall", "ci")),
                   ('Gemini 2.5 Flash, re-testing share, %', J("paper_figdata.json", "models", "Gemini 2.5 Flash", "share_budget", "mean"), J("paper_figdata.json", "models", "Gemini 2.5 Flash", "share_budget", "ci")),
                   ('Gemini 2.5 Flash, share over slots not lost, %', J("paper_figdata.json", "models", "Gemini 2.5 Flash", "share_nonlost", "mean"), J("paper_figdata.json", "models", "Gemini 2.5 Flash", "share_nonlost", "ci")),
                   ('Gemini 2.5 Flash, median reasoning tokens per call', J("paper_figdata.json", "models", "Gemini 2.5 Flash", "reasoning_tokens_median")),
                   ('Gemini 2.5 Flash, largest reasoning tokens in one call', J("paper_figdata.json", "models", "Gemini 2.5 Flash", "reasoning_tokens_max")),
                   ('Gemini 2.5 Flash, final pick', J("paper_figdata.json", "models", "Gemini 2.5 Flash", "pick", "mean"), J("paper_figdata.json", "models", "Gemini 2.5 Flash", "pick", "ci")),
                   ('Gemini 2.5 Flash, exploration loss', J("paper_figdata.json", "models", "Gemini 2.5 Flash", "exploration_shortfall", "mean"), J("paper_figdata.json", "models", "Gemini 2.5 Flash", "exploration_shortfall", "ci")),
                   ('Gemini 2.5 Flash, selection loss', J("paper_figdata.json", "models", "Gemini 2.5 Flash", "selection_shortfall", "mean"), J("paper_figdata.json", "models", "Gemini 2.5 Flash", "selection_shortfall", "ci")),
                   ('DeepSeek V3.1, re-testing share, %', J("paper_figdata.json", "models", "DeepSeek V3.1", "share_budget", "mean"), J("paper_figdata.json", "models", "DeepSeek V3.1", "share_budget", "ci")),
                   ('DeepSeek V3.1, share over slots not lost, %', J("paper_figdata.json", "models", "DeepSeek V3.1", "share_nonlost", "mean"), J("paper_figdata.json", "models", "DeepSeek V3.1", "share_nonlost", "ci")),
                   ('DeepSeek V3.1, median reasoning tokens per call', J("paper_figdata.json", "models", "DeepSeek V3.1", "reasoning_tokens_median")),
                   ('DeepSeek V3.1, largest reasoning tokens in one call', J("paper_figdata.json", "models", "DeepSeek V3.1", "reasoning_tokens_max")),
                   ('DeepSeek V3.1, final pick', J("paper_figdata.json", "models", "DeepSeek V3.1", "pick", "mean"), J("paper_figdata.json", "models", "DeepSeek V3.1", "pick", "ci")),
                   ('DeepSeek V3.1, exploration loss', J("paper_figdata.json", "models", "DeepSeek V3.1", "exploration_shortfall", "mean"), J("paper_figdata.json", "models", "DeepSeek V3.1", "exploration_shortfall", "ci")),
                   ('DeepSeek V3.1, selection loss', J("paper_figdata.json", "models", "DeepSeek V3.1", "selection_shortfall", "mean"), J("paper_figdata.json", "models", "DeepSeek V3.1", "selection_shortfall", "ci")),
                   ('GPT-6.1 Sol, re-testing share, %', J("paper_figdata.json", "models", "GPT-6.1 Sol", "share_budget", "mean"), J("paper_figdata.json", "models", "GPT-6.1 Sol", "share_budget", "ci")),
                   ('GPT-6.1 Sol, share over slots not lost, %', J("paper_figdata.json", "models", "GPT-6.1 Sol", "share_nonlost", "mean"), J("paper_figdata.json", "models", "GPT-6.1 Sol", "share_nonlost", "ci")),
                   ('GPT-6.1 Sol, median reasoning tokens per call', J("paper_figdata.json", "models", "GPT-6.1 Sol", "reasoning_tokens_median")),
                   ('GPT-6.1 Sol, largest reasoning tokens in one call', J("paper_figdata.json", "models", "GPT-6.1 Sol", "reasoning_tokens_max")),
                   ('GPT-6.1 Sol, final pick', J("paper_figdata.json", "models", "GPT-6.1 Sol", "pick", "mean"), J("paper_figdata.json", "models", "GPT-6.1 Sol", "pick", "ci")),
                   ('GPT-6.1 Sol, exploration loss', J("paper_figdata.json", "models", "GPT-6.1 Sol", "exploration_shortfall", "mean"), J("paper_figdata.json", "models", "GPT-6.1 Sol", "exploration_shortfall", "ci")),
                   ('GPT-6.1 Sol, selection loss', J("paper_figdata.json", "models", "GPT-6.1 Sol", "selection_shortfall", "mean"), J("paper_figdata.json", "models", "GPT-6.1 Sol", "selection_shortfall", "ci")),
                   ('Gemini 3.1 Pro, re-testing share, %', J("paper_figdata.json", "models", "Gemini 3.1 Pro", "share_budget", "mean"), J("paper_figdata.json", "models", "Gemini 3.1 Pro", "share_budget", "ci")),
                   ('Gemini 3.1 Pro, share over slots not lost, %', J("paper_figdata.json", "models", "Gemini 3.1 Pro", "share_nonlost", "mean"), J("paper_figdata.json", "models", "Gemini 3.1 Pro", "share_nonlost", "ci")),
                   ('Gemini 3.1 Pro, median reasoning tokens per call', J("paper_figdata.json", "models", "Gemini 3.1 Pro", "reasoning_tokens_median")),
                   ('Gemini 3.1 Pro, largest reasoning tokens in one call', J("paper_figdata.json", "models", "Gemini 3.1 Pro", "reasoning_tokens_max")),
                   ('Gemini 3.1 Pro, final pick', J("paper_figdata.json", "models", "Gemini 3.1 Pro", "pick", "mean"), J("paper_figdata.json", "models", "Gemini 3.1 Pro", "pick", "ci")),
                   ('Gemini 3.1 Pro, exploration loss', J("paper_figdata.json", "models", "Gemini 3.1 Pro", "exploration_shortfall", "mean"), J("paper_figdata.json", "models", "Gemini 3.1 Pro", "exploration_shortfall", "ci")),
                   ('Gemini 3.1 Pro, selection loss', J("paper_figdata.json", "models", "Gemini 3.1 Pro", "selection_shortfall", "mean"), J("paper_figdata.json", "models", "Gemini 3.1 Pro", "selection_shortfall", "ci"))],
         outcome="older models re-test most and lose through exploration; Gemini 3.1 Pro re-tests least and loses through selection",
         status="main text", limits="Grid, Blind prompt; each model from the arm the 0an.7 readout compares; intervals only."),
    dict(id="GB1 Blind re-testing across models (descriptive)", amendment="(descriptive)", tags=[],
         analysis=["analysis_0an6.json", "analysis_0an7.json"],
         question="How much each model re-tests on scrambled GB1, beside the best scripted share there; not paired across landscapes.",
         headline=[('Gemini 2.5 Flash GB1 Blind share, %, 0an.6 control', J("analysis_0an6.json", "cells", "Gemini", "partner_share")),
                   ('Gemini 2.5 Flash GB1 Blind distinct candidates, 0an.6 control', J("analysis_0an6.json", "cells", "Gemini", "partner_distinct")),
                   ('DeepSeek V3.1 GB1 Blind share, %, 0an.6 control', J("analysis_0an6.json", "cells", "DeepSeek", "partner_share")),
                   ('DeepSeek V3.1 GB1 Blind distinct candidates, 0an.6 control', J("analysis_0an6.json", "cells", "DeepSeek", "partner_distinct")),
                   ('Opus 4.7 GB1 Blind share, %, earlier 0am control', J("analysis_0an6.json", "cells", "Opus", "partner_share")),
                   ('Opus 4.7 GB1 Blind distinct candidates, earlier 0am control', J("analysis_0an6.json", "cells", "Opus", "partner_distinct")),
                   ('Sol GB1 Blind distinct candidates', J("analysis_0an7.json", "cells", "sol|gb1_blind", "distinct")),
                   ('Gemini 3.1 Pro GB1 Blind distinct candidates', J("analysis_0an7.json", "cells", "gem|gb1_blind", "distinct")),
                   ('Gemini 3.1 Pro GB1 Blind exploration loss', J("analysis_0an7.json", "cells", "gem|gb1_blind", "exploration_shortfall")),
                   ('Gemini 3.1 Pro GB1 Blind selection loss', J("analysis_0an7.json", "cells", "gem|gb1_blind", "selection_shortfall"))],
         outcome="every model re-tests far more than the best scripted share on GB1; Gemini 3.1 Pro's GB1 loss is exploration",
         status="appendix", limits="Different landscapes, seeds and runs; descriptive and not paired. Opus 4.7's control is from 0am."),
    dict(id="Panel c: reasoning on, grid Blind (exploratory)", amendment="(exploratory)", tags=[],
         analysis=["analysis_0an7.json"],
         question="How much Opus 4.7 and Gemini 2.5 Flash re-test on the grid with reasoning on, in the exploratory Panel c.",
         headline=[('Opus 4.7 Panel c Blind share, %', J("analysis_0an7.json", "cells", "gem|grid_blind", "comparators", "Panel c|claude-opus-4.7", "share_budget"), J("analysis_0an7.json", "cells", "gem|grid_blind", "comparators", "Panel c|claude-opus-4.7", "share_budget_ci")),
                   ('Gemini 2.5 Flash Panel c Blind share, %', J("analysis_0an7.json", "cells", "gem|grid_blind", "comparators", "Panel c|gemini-2.5-flash", "share_budget"), J("analysis_0an7.json", "cells", "gem|grid_blind", "comparators", "Panel c|gemini-2.5-flash", "share_budget_ci"))],
         outcome="with reasoning on, both still re-test most of their slots",
         status="main text", limits="Exploratory; the prompt differs only by the truthful re-ask line, at medium reasoning effort; 35 to 40 campaigns."),
    dict(id="attractor basins (descriptive)", amendment="(descriptive)", tags=[],
         analysis=["basins.json", "basins_variants.json"],
         question="Where the start sits in each landscape's basins, and whether campaigns nominate from the start's basin.",
         headline=[('grid peaks', J("basins.json", "landscapes", "grid", "peaks")),
                   ('scrambled GB1 peaks', J("basins.json", "landscapes", "GB1", "peaks")),
                   ('scrambled PhoQ peaks', J("basins.json", "landscapes", "PhoQ", "peaks")),
                   ('Wu et al. 2016 GB1 peaks, complete sequence space', J("basins.json", "wu2016", "peaks_complete_space")),
                   ('GB1 start basin peak rank', J("basins.json", "landscapes", "GB1", "start_basin_peak_rank")),
                   ('GB1 start to its basin peak, letter changes', J("basins.json", "landscapes", "GB1", "start_to_peak_changes")),
                   ('GB1 start basin share of viable variants', J("basins.json", "landscapes", "GB1", "start_basin_share")),
                   ('grid start basin peak rank', J("basins.json", "landscapes", "grid", "start_basin_peak_rank")),
                   ('GB1 Blind Gemini 2.5 Flash nominee in start basin', J("basins.json", "arms", "GB1 Blind", "Gemini 2.5 Flash", "nominee_in_start_basin"), J("basins.json", "arms", "GB1 Blind", "Gemini 2.5 Flash", "nominee_in_start_basin_ci")),
                   ('GB1 Blind DeepSeek V3.1 nominee in start basin', J("basins.json", "arms", "GB1 Blind", "DeepSeek V3.1", "nominee_in_start_basin"), J("basins.json", "arms", "GB1 Blind", "DeepSeek V3.1", "nominee_in_start_basin_ci")),
                   ('GB1 Blind Opus 4.7 nominee in start basin', J("basins.json", "arms", "GB1 Blind", "Opus 4.7", "nominee_in_start_basin"), J("basins.json", "arms", "GB1 Blind", "Opus 4.7", "nominee_in_start_basin_ci")),
                   ('GB1 Blind GPT-6.1 Sol nominee in start basin', J("basins.json", "arms", "GB1 Blind", "GPT-6.1 Sol", "nominee_in_start_basin"), J("basins.json", "arms", "GB1 Blind", "GPT-6.1 Sol", "nominee_in_start_basin_ci")),
                   ('GB1 Blind Gemini 3.1 Pro nominee in start basin', J("basins.json", "arms", "GB1 Blind", "Gemini 3.1 Pro", "nominee_in_start_basin"), J("basins.json", "arms", "GB1 Blind", "Gemini 3.1 Pro", "nominee_in_start_basin_ci"))],
         outcome=("on scrambled GB1 the start lies in the global peak's basin; the over-confirming models mostly nominate from it, "
                  "far below its peak; the models that explore leave it more often, for basins with lower peaks"),
         status="not reported: the descriptive basins appendix was cut in review change 115", limits="Descriptive; steepest ascent over viable variants only; landscapes, seeds and runs are not paired."),
    dict(id="0an.7 smokes", amendment="0an.7", tags=["smoke0an7_grid_blind", "smoke0an7_gb1_blind", "smoke0an7_gb1_menu"],
         analysis=["smoke_0an7_report.json", "smoke_detail_0an7.json", "analysis_0an7_smoke.json"],
         question="Whether GPT-6.1 Sol and Gemini 3.1 Pro run the design cleanly, and at what cost.",
         headline=[], outcome="format clean, none abandoned; Gemini's grid campaigns lost 14 and 12 slots to rejections",
         status="not yet in paper", limits="Two campaigns per arm per model."),
    dict(id="audit: reasoning text used as the answer", amendment="0an.7 note", tags=[],
         analysis=["audit_reasoning_fallback.json"],
         question="Where the harness used a model's reasoning text as its answer before the 0an.7 fix.",
         headline=[("calls read", J("audit_reasoning_fallback.json", "calls_read")),
                   ("calls meeting the rule", J("audit_reasoning_fallback.json", "tags_with_suspects", "panelc"))],
         outcome="one call, in Panel c (a lost slot); no reported number changes",
         status="appendix", limits="The rule reads the last attempt's tokens of each logged call."),
    dict(id="0an.7 step 1: frontier model probes", amendment="0an.7", tags=[],
         analysis=["probe_0an7.json", "probe_0an7_extra.json", "project_0an7.json"],
         question="Which current models can run the design, at what reasoning setting and cost.",
         headline=[("Gemini 3.1 Pro projected cost, high case, $",
                    J("project_0an7.json", "models", "google/gemini-3.1-pro-preview", "high (Opus 4.7 pattern)")),
                   ("GPT-6.1 Sol projected cost, high case, $",
                    J("project_0an7.json", "models", "openai/gpt-6.1-sol", "high (Opus 4.7 pattern)")),
                   ("Gemini 3.1 Pro reasoning tokens per call at minimal",
                    J("project_0an7.json", "models", "google/gemini-3.1-pro-preview", "reasoning"))],
         outcome="neither GPT-6.1 Sol nor Gemini 3.1 Pro can turn reasoning off; both run at minimal, as reasoning models",
         status="not yet in paper", limits="Probes only; no campaign has run."),
    dict(id="0an re-nomination by simple rules", amendment="(descriptive)", tags=[],
         analysis=["renominate_0an.json"],
         question="Whether a simple selection rule turns an arm's better exploration into better picks.",
         headline=[('F2 Opus, highest mean, pick change', J("renominate_0an.json", "F2 menu|Opus", "highest mean", "d"), J("renominate_0an.json", "F2 menu|Opus", "highest mean", "ci")),
                   ('F2 Gemini, highest mean, pick change', J("renominate_0an.json", "F2 menu|Gemini", "highest mean", "d"), J("renominate_0an.json", "F2 menu|Gemini", "highest mean", "ci")),
                   ('F2 Gemini, shrinkage, pick change', J("renominate_0an.json", "F2 menu|Gemini", "shrinkage", "d"), J("renominate_0an.json", "F2 menu|Gemini", "shrinkage", "ci")),
                   ('F2 DeepSeek, shrinkage, pick change', J("renominate_0an.json", "F2 menu|DeepSeek", "shrinkage", "d"), J("renominate_0an.json", "F2 menu|DeepSeek", "shrinkage", "ci"))],
         outcome="partly: Opus and Gemini gain under simple rules, DeepSeek does not; F1 and F5 drops persist",
         status="not yet in paper", limits="Re-nomination of the agents' own readings; Opus F2 at n = 30."),
    dict(id="0an F2 menu check", amendment="(descriptive)", tags=[],
         analysis=["menu_check_0an.json", "menu_usage_gen_0an_f2_menu.json"],
         question="Whether agents take new names from the list although their own are viable more often.",
         headline=[('list names viable, DeepSeek', J("menu_check_0an.json", "deepseek/deepseek-chat-v3.1", "list", "rate"), J("menu_check_0an.json", "deepseek/deepseek-chat-v3.1", "list", "ci")),
                   ('own minus list, rounds matched, DeepSeek', J("menu_check_0an.json", "deepseek/deepseek-chat-v3.1", "own_std_minus_list", "diff"), J("menu_check_0an.json", "deepseek/deepseek-chat-v3.1", "own_std_minus_list", "ci")),
                   ('own minus list, rounds matched, Gemini', J("menu_check_0an.json", "google/gemini-2.5-flash", "own_std_minus_list", "diff"), J("menu_check_0an.json", "google/gemini-2.5-flash", "own_std_minus_list", "ci")),
                   ('own minus list, rounds matched, Opus', J("menu_check_0an.json", "anthropic/claude-opus-4.7", "own_std_minus_list", "diff"), J("menu_check_0an.json", "anthropic/claude-opus-4.7", "own_std_minus_list", "ci"))],
         outcome="holds for Gemini and DeepSeek after matching rounds; not established for Opus",
         status="not yet in paper", limits="Own names are a self-selected minority (83 to 515 per model)."),
    dict(id="0an.3 F5 structure", amendment="0an.3", tags=["smoke0an3_f5_structure", "gen_0an_f5_structure"],
         analysis=["structure_facts_0an3.json", "analysis_0an.json"],
         question="Whether agents re-test because they lack knowledge of the problem's structure.",
         headline=[('F5 Opus share change, points', J("analysis_0an.json", "cells", "F5 structure|Opus", "d_share"), J("analysis_0an.json", "cells", "F5 structure|Opus", "d_share_ci")),
                   ('F5 Gemini share change, points', J("analysis_0an.json", "cells", "F5 structure|Gemini", "d_share"), J("analysis_0an.json", "cells", "F5 structure|Gemini", "d_share_ci")),
                   ('F5 DeepSeek share change, points', J("analysis_0an.json", "cells", "F5 structure|DeepSeek", "d_share"), J("analysis_0an.json", "cells", "F5 structure|DeepSeek", "d_share_ci")),
                   ("viable among a viable candidate's neighbours", J("structure_facts_0an3.json", "viable_rate_among_neighbours_of_viable"))],
         outcome="no effect on re-testing in all three models; with F2 reducing, the bottleneck reads as producing candidates",
         status="main text", limits="Grid landscape only; Opus n = 30; one wording of the structure."),
    dict(id="GB1 Menu: gap to the guessing rule closed", amendment="(descriptive)", tags=[],
         analysis=["menu_gap_0an6.json"],
         question=("For the two models that explored least, the share of the gap between their GB1 Blind pick and the "
                   "guessing rule's that their Menu pick closed (the basins table's means)."),
         headline=[("Gemini 2.5 Flash, gap closed, %", J("menu_gap_0an6.json", "models", "Gemini 2.5 Flash", "gap_closed_pct")),
                   ("DeepSeek V3.1, gap closed, %", J("menu_gap_0an6.json", "models", "DeepSeek V3.1", "gap_closed_pct"))],
         outcome="the Menu closed about three quarters of the gap for Gemini 2.5 Flash and about 70% for DeepSeek V3.1",
         status="not reported: no longer cited after review changes 96 to 99", limits="Unpaired means, as in the basins table; Figure 5 gives the paired change."),
    # PhoQ panel: pending until its analysis exists; tags are listed so its campaign files always belong to a row.
    dict(id="0an.8 smokes", amendment="0an.8",
         tags=["smoke0an8_%s" % m for m in ("opus", "flash", "deepseek", "sol", "gem")],
         analysis=["analysis_0an8_smoke.json"],
         question="Whether the PhoQ Blind arm runs cleanly for all five models, and what it will cost.",
         headline=[("projected main run, $", J("smoke_0an8_report.json", "projected_total")),
                   ("smoke cost by campaign records, $", J("smoke_0an8_report.json", "smoke_recorded_cost")),
                   ("smoke cost by credit balance, $", J("smoke_0an8_report.json", "smoke_cost_by_balance"))],
         outcome=("gate failed on one line, Sol's bare reply IAKT, which the primary parser read; under 0an.8 note 2 "
                  "a bare single valid token counts as agreement, the gate passes, and the main run is approved"),
         status="not yet in paper", limits="Smoke-sized; operational only."),
    dict(id="0an.8 PhoQ Blind, five models", amendment="0an.8",
         tags=["gen_0an8_%s_phoq_blind%s" % (m, r) for m in ("opus", "flash", "deepseek", "sol", "gem")
               for r in ("", "_rerun")] + ["gen_0an8_sol_phoq_blind_cont", "gen_0an8_sol_phoq_blind_cont_rerun", "gen_0an8_sol_phoq_blind_fin"],
         analysis=["analysis_0an8.json", "references_0an8.json"],
         question="Whether each model's re-testing on GB1 holds on a second real protein, scrambled PhoQ.",
         headline=PQ_HEADLINE,
         outcome=("the named claim extends to PhoQ for all five models: every interval lies above the best scripted "
                  "share (0.00%, the informed rule at k = 0) and above the guessing rule's 1.03%; Sol's arm finished "
                  "under notes 3 and 4 after provider overloads"),
         status="main text",
         limits="One more protein, scrambled names, GB1's noise model; the best scripted share on PhoQ is zero."),
    dict(id="0an.8 descriptive: three landscapes side by side", amendment="(descriptive)", tags=[],
         analysis=["landscapes_0an8.json"],
         question=("Each model's re-testing share, final pick and single-reading nominees on the grid, GB1 and PhoQ, "
                   "beside each landscape's best scripted policy and guessing rule."),
         headline=LS_HEADLINE,
         outcome=("every model re-tests more than the best scripted policy on GB1 and PhoQ; Gemini 3.1 Pro's nominee had "
                  "one reading in 78%, 93% and 97% of campaigns on the three landscapes"),
         status="main text", limits="The arms differ in seeds and run across landscapes; not paired across them."),
    dict(id="0an.8 descriptive: picks paired with the guessing rule on the agents' seeds", amendment="(descriptive)",
         tags=[], analysis=["landscapes_0an8.json"],
         question="Each model's pick minus the guessing rule's on the same campaign seeds, on GB1 and PhoQ.",
         headline=LS_PAIRED,
         outcome=("on PhoQ DeepSeek V3.1 and Gemini 3.1 Pro pick worse than the guessing rule and the other three are "
                  "level; on GB1 every model but Sol picks worse"),
         status="main text", limits="Descriptive, not registered; 30 to 60 pairs per model."),
    dict(id="0an.8 descriptive: Sol's PhoQ lead grouped by nominee", amendment="(descriptive)", tags=[],
         analysis=["landscapes_0an8.json"],
         question="Whether Sol's PhoQ lead over the guessing rule rests on one repeated nominee, as on GB1 (Appendix E).",
         headline=LS_SOL,
         outcome="the lead holds as registered only; grouped by nominee or with IAQT counted once its interval crosses zero",
         status="appendix", limits="Descriptive, not registered; 30 campaigns, 13 distinct nominees."),
    dict(id="B11 Run A: PPO policy trained on the grid, tested on grid, GB1 and PhoQ", amendment="B11 (registered)",
         tags=[], analysis=["b11_test_A.json", "b11_curves.json"],
         question=("Whether a small PPO policy trained on the grid train split only beats its untrained initialisation "
                   "and random ordering on nk:test (learnable) and on gb1:test and phoq:test (transfer); "
                   "spec/B11_PREREGISTRATION.md."),
         headline=[("B11 A %s, trained minus %s" % (_sp, _n), J("b11_test_A.json", "splits", _sp, "comparisons",
                                                               "vs " + _n, "mean"),
                    J("b11_test_A.json", "splits", _sp, "comparisons", "vs " + _n, "ci"))
                   for _sp in ("nk:test", "gb1:test", "phoq:test") for _n in ("initialisation", "random")] +
                  [("B11 A %s, trained pick" % _sp, J("b11_test_A.json", "splits", _sp, "table", "trained", "pick",
                                                       "mean")) for _sp in ("nk:test", "gb1:test", "phoq:test")] +
                  [("B11 A %s, trained re-testing share, %%" % _sp, J("b11_test_A.json", "splits", _sp, "table",
                                                                     "trained", "share", "mean"))
                   for _sp in ("nk:test", "gb1:test", "phoq:test")],
         outcome=("learnable and transfer criteria met: beats its initialisation and random ordering on nk:test, "
                  "gb1:test and phoq:test, every seed positive, also at the Bonferroni level"),
         status="main text",
         limits="Three seeds; checkpoints chosen on nk:validation; below the best scripted policy on all three landscapes."),
    dict(id="B11 Run B: PPO policy trained on grid + GB1, tested on PhoQ", amendment="B11 (registered)",
         tags=[], analysis=["b11_test_B.json", "b11_curves.json"],
         question=("Whether a small PPO policy trained on the grid and GB1 train splits beats its untrained "
                   "initialisation and random ordering on phoq:test (spec/B11_PREREGISTRATION.md)."),
         headline=[("B11 B phoq:test, trained minus %s" % _n, J("b11_test_B.json", "splits", "phoq:test", "comparisons",
                                                               "vs " + _n, "mean"),
                    J("b11_test_B.json", "splits", "phoq:test", "comparisons", "vs " + _n, "ci"))
                   for _n in ("initialisation", "random")] +
                  [("B11 B phoq:test, trained minus %s, seed %d" % (_n, _i),
                    J("b11_test_B.json", "splits", "phoq:test", "comparisons", "vs " + _n, "per_seed", _i))
                   for _n in ("initialisation", "random") for _i in range(3)] +
                  [("B11 B phoq:test, trained pick", J("b11_test_B.json", "splits", "phoq:test", "table", "trained",
                                                        "pick", "mean")),
                   ("B11 B phoq:test, trained re-testing share, %", J("b11_test_B.json", "splits", "phoq:test",
                                                                      "table", "trained", "share", "mean"))],
         outcome=("transfer criterion not met: beats its initialisation on phoq:test in all three seeds, but not "
                  "random ordering (+0.033, 95% interval -0.008 to +0.074; seed 2 negative)"),
         status="appendix",
         limits="Three seeds; every seed's selected checkpoint is update 50 of 1,500."),
    dict(id="B11 robustness analyses (post-hoc): the LLM campaigns' landscapes against B11's training and validation splits",
         amendment="B11 robustness analyses (post-hoc)", tags=[], analysis=["b11_robustness_contamination.json"],
         question=("Whether a landscape the grid, GB1 (scrambled and real) or PhoQ LLM arms used is in any B11 "
                   "training or validation split, by name, by built content, or (grid) by its sorted fitness table; "
                   "spec/B11_ROBUSTNESS.md."),
         headline=[("%s landscape in a B11 training or validation split (1 = yes)" % _a,
                    J("b11_robustness_contamination.json", "arms", _a, "in_train_or_validation"))
                   for _a in ("grid", "gb1_scrambled", "gb1_real", "phoq_scrambled")] +
                  [("grid landscape in Run A's training or validation split (1 = yes)",
                    J("b11_robustness_contamination.json", "grid_contaminated"))],
         outcome=("no LLM arm's landscape is in a B11 training or validation split by any test, and no arm's campaign "
                  "seeds fall in a split's seed range; the grid rows are not marked CONTAMINATED"),
         status="appendix",
         limits="Post-hoc. Scrambles of one protein share its fitness values by design; the check is by name and content."),
    dict(id="B11 robustness analyses (post-hoc): Run A and the scripted policies at three noise levels on nk:test",
         amendment="B11 robustness analyses (post-hoc)", tags=[], analysis=["b11_robustness_noise.json"],
         question=("How Run A's pick and re-testing share, and the scripted policies' best k, move when the noise CV is "
                   "halved (0.0365) or doubled (0.146) from the training noise (0.073); all 1,500 nk:test episodes; "
                   "spec/B11_ROBUSTNESS.md."),
         headline=[(("B11 noise %s, " % _lv) + label, J("b11_robustness_noise.json", "levels", _lv, *path),
                    J("b11_robustness_noise.json", "levels", _lv, *(path[:-1] + ("ci",))))
                   for _lv in ("low", "assay", "high") for label, path in (
                       ("Run A pick", ("policies", "Run A", "pick", "mean")),
                       ("Run A re-testing share, %", ("policies", "Run A", "share", "mean")),
                       ("Run A minus random, pick", ("comparisons", "Run A minus random", "pick", "mean")),
                       ("Run A minus the best scripted policy (informed k=1), pick",
                        ("comparisons", "Run A minus best scripted (informed k=1)", "pick", "mean")))] +
                  [("B11 noise, Run A re-testing share, %s minus assay, %%" % _lv,
                    J("b11_robustness_noise.json", "share_change_vs_assay", "Run A, %s minus assay" % _lv, "mean"),
                    J("b11_robustness_noise.json", "share_change_vs_assay", "Run A, %s minus assay" % _lv, "ci"))
                   for _lv in ("low", "high")],
         outcome=("Run A beats random ordering at every noise level and stays below the best scripted policy (informed "
                  "k=1) at every level; its re-testing share stays between 9.0% and 9.3% across a fourfold change in "
                  "noise; the best k is 1 for both rules at every level, except guessing at high noise (k=2, ahead of "
                  "k=1 by 0.009 with an interval that spans zero)"),
         status="main text",
         limits=("Post-hoc. Scripted nominations are told the true noise CV; Run A sees noise only through repeat "
                 "readings. One landscape family.")),
    dict(id="B11 robustness analyses (post-hoc): Run A and the scripted policies on the LLM campaigns' own episodes",
         amendment="B11 robustness analyses (post-hoc)", tags=[], analysis=["b11_robustness_llm.json"],
         question=("How Run A's three networks and the scripted policies (k chosen on validation, as in B11) compare with "
                   "each LLM on that LLM's own (landscape, campaign seed) pairs, at the campaigns' settings: the grid, "
                   "scrambled GB1, real GB1 and scrambled PhoQ arms; spec/B11_ROBUSTNESS.md."),
         headline=[("B11 on %s's %s episodes, Run A minus the LLM, pick" % (_m, _a),
                    J("b11_robustness_llm.json", "arms", _a, "models", _m, "run_a_minus_llm", "pick", "mean"),
                    J("b11_robustness_llm.json", "arms", _a, "models", _m, "run_a_minus_llm", "pick", "ci"))
                   for _a, _ms in (("grid", ("Opus 4.7", "Gemini 2.5 Flash", "DeepSeek V3.1", "GPT-6.1 Sol",
                                             "Gemini 3.1 Pro")),
                                   ("gb1_scrambled", ("Opus 4.7", "Gemini 2.5 Flash", "DeepSeek V3.1", "GPT-6.1 Sol",
                                                      "Gemini 3.1 Pro")),
                                   ("gb1_real", ("Opus 4.7", "Gemini 2.5 Flash", "DeepSeek V3.1")),
                                   ("phoq_scrambled", ("Opus 4.7", "Gemini 2.5 Flash", "DeepSeek V3.1", "GPT-6.1 Sol",
                                                       "Gemini 3.1 Pro")))
                   for _m in _ms],
         outcome=("Run A's pick is above all five LLMs on the grid; on scrambled GB1 it is above Flash and DeepSeek and "
                  "below GPT-6.1 Sol, with intervals spanning zero for Opus 4.7 and Gemini 3.1 Pro; on real GB1 it is "
                  "below Opus 4.7 and above Flash and DeepSeek; on PhoQ it is above Opus 4.7, DeepSeek and Gemini 3.1 "
                  "Pro, with intervals spanning zero for Flash and Sol. Run A re-tests less than every LLM on every arm. "
                  "The grid landscape is clean by the contamination check"),
         status="main text",
         limits=("Post-hoc. 30 to 120 campaigns per LLM; the scripted policies' k comes from B11 validation, and real "
                 "GB1 uses GB1's validation k.")),
    dict(id="B11 robustness analyses part 2 (post-hoc): every B11 comparison under a two-level cluster bootstrap",
         amendment="B11 robustness analyses part 2 (post-hoc)", tags=[], analysis=["b11_cluster_bootstrap.json"],
         question=("Whether the registered and published B11 intervals survive resampling landscapes and then episodes "
                   "within landscape (10,000 draws), and how the three seeds spread (t-interval over seeds); "
                   "spec/B11_ROBUSTNESS_2.md item 1."),
         headline=[("B11 cluster: %s" % _n, J("b11_cluster_bootstrap.json", "by_name", _k, "mean"),
                    J("b11_cluster_bootstrap.json", "by_name", _k, "cluster_interval"))
                   for _n, _k in (
                       ("A nk:test trained minus initialisation", "b11_test_A.json | nk:test, trained minus initialisation, pick"),
                       ("A nk:test trained minus random", "b11_test_A.json | nk:test, trained minus random, pick"),
                       ("A nk:test trained minus guessing", "b11_test_A.json | nk:test, trained minus guessing, pick"),
                       ("A nk:test trained minus informed", "b11_test_A.json | nk:test, trained minus informed, pick"),
                       ("A gb1:test trained minus initialisation", "b11_test_A.json | gb1:test, trained minus initialisation, pick"),
                       ("A gb1:test trained minus random", "b11_test_A.json | gb1:test, trained minus random, pick"),
                       ("A gb1:test trained minus guessing", "b11_test_A.json | gb1:test, trained minus guessing, pick"),
                       ("A phoq:test trained minus initialisation", "b11_test_A.json | phoq:test, trained minus initialisation, pick"),
                       ("A phoq:test trained minus random", "b11_test_A.json | phoq:test, trained minus random, pick"),
                       ("A phoq:test trained minus informed", "b11_test_A.json | phoq:test, trained minus informed, pick"),
                       ("B phoq:test trained minus initialisation", "b11_test_B.json | phoq:test, trained minus initialisation, pick"),
                       ("B phoq:test trained minus random", "b11_test_B.json | phoq:test, trained minus random, pick"),
                       ("noise low, Run A minus random", "b11_robustness_noise.json | low, Run A minus random, pick"),
                       ("noise high, Run A minus random", "b11_robustness_noise.json | high, Run A minus random, pick"))] +
                  [("B11 cluster: grid, Run A minus %s" % _m,
                    J("b11_cluster_bootstrap.json", "by_name", "b11_robustness_llm.json | grid, %s, Run A minus the LLM, pick" % _m,
                      "mean"),
                    J("b11_cluster_bootstrap.json", "by_name", "b11_robustness_llm.json | grid, %s, Run A minus the LLM, pick" % _m,
                      "cluster_interval"))
                   for _m in ("Opus 4.7", "Gemini 2.5 Flash", "DeepSeek V3.1", "GPT-6.1 Sol", "Gemini 3.1 Pro")],
         outcome=("every registered Run A criterion (versus initialisation and random, on nk, gb1 and phoq test) keeps an "
                  "interval above zero, by cluster bootstrap and by the t-interval over seeds; two of 96 comparisons "
                  "now cross zero, Run A minus the guessing rule on nk:test and on phoq:test"),
         status="main text",
         limits="Post-hoc. Three seeds; the LLM arms and real landscapes have one landscape, so their bootstrap is over episodes."),
    dict(id="B11 robustness analyses part 2 (post-hoc): stress tests of the assay model",
         amendment="B11 robustness analyses part 2 (post-hoc)", tags=[], analysis=["b11_stress.json"],
         question=("Whether heavy re-testing (k = 3 or 4) matches or beats the best moderate setting (k = 0 to 2) under "
                   "a per-round batch factor (SD 5% or 10%), a noise floor of 2% of the maximum, 2% failed-well outliers, "
                   "or 2% three-fold spikes, on nk:test and gb1:test, 1,500 episodes each; spec/B11_ROBUSTNESS_2.md item 4."),
         headline=[("B11 stress %s %s, %s" % (_sp, _c, _lab), J("b11_stress.json", "splits", _sp, _c, *_path),
                    J("b11_stress.json", "splits", _sp, _c, *(_path[:-1] + ("ci",))))
                   for _sp in ("nk:test", "gb1:test") for _c in ("none", "batch5", "batch10", "floor", "zeros", "spikes")
                   for _lab, _path in (
                       ("Run A minus random, pick", ("run_a_minus_random", "pick", "mean")),
                       ("informed heavy minus moderate, pick", ("heavy_vs_moderate", "informed", "heavy_minus_moderate",
                                                                 "mean")),
                       ("guessing heavy minus moderate, pick", ("heavy_vs_moderate", "guessing", "heavy_minus_moderate",
                                                                 "mean")))],
         outcome=("heavy re-testing matches the best moderate setting in one condition only: three-fold spikes on "
                  "nk:test, where informed k = 3 is the best scripted policy (k = 3 minus k = 2: +0.027, interval "
                  "spanning zero) and guessing k = 3 is level with k = 2; there Run A's lead over random falls to +0.088. "
                  "Under batch effects, the larger floor and failed-well outliers, and under spikes on gb1:test, heavy "
                  "re-testing stays below the best moderate setting; k = 4 is below the best in every condition"),
         status="main text",
         limits="Post-hoc. Two landscape families; no policy models batch effects or outliers; Run A runs zero-shot."),
    dict(id="B11 robustness analyses part 2 (post-hoc): Run A and the scripted policies on unscrambled GB1 and PhoQ",
         amendment="B11 robustness analyses part 2 (post-hoc)", tags=[], analysis=["b11_real_landscapes.json"],
         question=("How Run A's networks (zero-shot) and the scripted policies do on GB1 and PhoQ under their own amino-acid "
                   "names, 1,500 episodes each (gb1:transfer_real, phoq:transfer_real); spec/B11_ROBUSTNESS_2.md item 3."),
         headline=[("B11 real %s, %s" % (_sp, _lab), J("b11_real_landscapes.json", "sets", _sp + " 15x4", *_path),
                    J("b11_real_landscapes.json", "sets", _sp + " 15x4", *(_path[:-1] + ("ci",))))
                   for _sp in ("gb1:transfer_real", "phoq:transfer_real") for _lab, _path in (
                       ("Run A minus random, pick", ("run_a_minus_random", "pick", "mean")),
                       ("Run A minus the best scripted policy, pick", ("run_a_minus_best", "pick", "mean")),
                       ("informed heavy minus moderate, pick", ("heavy_vs_moderate", "informed", "heavy_minus_moderate",
                                                                 "mean")))],
         outcome=("as on the scrambled test splits: Run A is above random ordering and below the best scripted policy on "
                  "both, the best k is 0 for both rules, and heavy re-testing stays below the best moderate setting"),
         status="main text",
         limits="Post-hoc. One landscape each, so the intervals resample episodes only."),
    dict(id="B11 robustness analyses part 2 (post-hoc): what Run A and Run B re-test, extend and nominate",
         amendment="B11 robustness analyses part 2 (post-hoc)", tags=[], analysis=["b11_behaviour.json"],
         question=("Replaying the registered test episodes with the orders read back from the oracle's history: the "
                   "re-testing share by round, what a re-test targets, the parent rank of new candidates, and how the "
                   "nominee compares with the highest mean reading and the shrinkage nominee; spec/B11_ROBUSTNESS_2.md "
                   "item 2."),
         headline=[("B11 behaviour %s, nominee minus shrinkage nominee, pick" % _r,
                    J("b11_behaviour.json", "runs", _r, "pick_cost_vs_shrinkage", "mean"),
                    J("b11_behaviour.json", "runs", _r, "pick_cost_vs_shrinkage", "ci"))
                   for _r in ("A nk:test", "A gb1:test", "A phoq:test", "B nk:test", "B gb1:test", "B phoq:test")] +
                  [("B11 behaviour A %s seed %s, re-tests that retry a failed well" % (_sp, _sd),
                    J("b11_behaviour.json", "runs", "A " + _sp, "seeds", _sd, "retest_rank", "retry_after_failure"))
                   for _sp in ("nk:test", "gb1:test") for _sd in ("0", "1", "2")] +
                  [("B11 behaviour %s, mean over seeds, %s" % (_r, _f),
                    J("b11_behaviour.json", "runs", _r, "mean_over_seeds", _f))
                   for _r in ("A nk:test", "A gb1:test", "A phoq:test", "B nk:test", "B gb1:test", "B phoq:test")
                   for _f in ("retest_share", "retry_after_failure", "same_round_replicate", "retests_of_top3",
                              "top3_retests_pct_of_slots", "parent_top1", "parent_top3", "nominee_is_shrinkage")],
         outcome=("most of Run A's re-testing retries failed wells (74% to 88% of its re-tests for seeds 0 and 1) or "
                  "repeats a candidate read earlier the same round; Run B re-tests top-ranked candidates and climbs to "
                  "about 80% re-testing by round 15. On gb1:test Run A's nominee is the highest mean reading only 23% to "
                  "84% of the time and costs 0.714 against the shrinkage nominee"),
         status="main text",
         limits="Post-hoc. A re-test's rank is taken at the start of its round; replacement orders see later readings."),
    dict(id="B11 robustness analyses part 2 (post-hoc): zero-shot on held-out ruggedness and other budgets",
         amendment="B11 robustness analyses part 2 (post-hoc)", tags=[], analysis=["b11_zero_shot.json"],
         question=("How Run A's networks and the scripted policies do on held-out K = 2 and K = 3 grids "
                   "(nk:test_ood_k2, nk:test_ood_k3) and on nk:test at budgets of 10 x 4, 20 x 4 and 4 x 24, 1,500 "
                   "episodes each; the scripted k scales with slots per round; spec/B11_ROBUSTNESS_2.md item 5."),
         headline=[("B11 zero-shot %s, %s" % (_set, _lab), J("b11_zero_shot.json", "sets", _set, *_path),
                    J("b11_zero_shot.json", "sets", _set, *(_path[:-1] + ("ci",))))
                   for _set in ("nk:test_ood_k2 15x4", "nk:test_ood_k3 15x4", "nk:test 10x4", "nk:test 20x4",
                                "nk:test 4x24") for _lab, _path in (
                       ("Run A minus random, pick", ("run_a_minus_random", "pick", "mean")),
                       ("Run A minus the best scripted policy, pick", ("run_a_minus_best", "pick", "mean")),
                       ("informed heavy minus moderate, pick", ("heavy_vs_moderate", "informed", "heavy_minus_moderate",
                                                                 "mean")))],
         outcome=("Run A's lead over random ordering shrinks with ruggedness (K = 2 +0.177; K = 3 +0.040, interval "
                  "spanning zero) and holds at every budget; at 4 x 24, with features outside their trained range, Run "
                  "A is level with the best scripted policy. Heavy re-testing stays below the best moderate setting in "
                  "every set"),
         status="main text",
         limits=("Post-hoc. Zero-shot: Run A was trained at K = 1 and 15 x 4; the model-guided policy is not rescaled "
                 "at 4 x 24.")),
    dict(id="B11 robustness analyses part 2 (post-hoc): Run B with a larger exploration bonus",
         amendment="B11 robustness analyses part 2 (post-hoc)", tags=[], analysis=["b11_B_ent05.json", "b11_cluster_bootstrap.json"],
         question=("Whether Run B, retrained with an entropy bonus five times the registered one (three seeds, every other "
                   "setting registered, the registered selection and test code), still collapses into heavy re-testing, "
                   "and whether it then meets the transfer criterion on phoq:test; spec/B11_ROBUSTNESS_2.md item 6."),
         headline=[("B11 Run B ablation %s, trained minus %s, pick" % (_sp, _n),
                    J("b11_cluster_bootstrap.json", "by_name", "b11_B_ent05.json | %s, trained minus %s, pick" % (_sp, _n),
                      "mean"),
                    J("b11_cluster_bootstrap.json", "by_name", "b11_B_ent05.json | %s, trained minus %s, pick" % (_sp, _n),
                      "cluster_interval"))
                   for _sp in ("phoq:test", "gb1:test", "nk:test") for _n in ("initialisation", "random")] +
                  [("B11 Run B ablation %s, trained re-testing share, %%" % _sp,
                    J("b11_B_ent05.json", "splits", _sp, "table", "trained", "share", "mean"))
                   for _sp in ("phoq:test", "gb1:test", "nk:test")] +
                  [("B11 Run B ablation, end of training, %s" % _f,
                    J("b11_B_ent05.json", "end_of_training", "training_curves", _f))
                   for _f in ("order_entropy", "nominate_entropy", "val_share")] +
                  [("B11 registered Run B, end of training, %s" % _f,
                    J("b11_B_ent05.json", "end_of_training", "registered_run_b_curves", _f))
                   for _f in ("order_entropy", "nominate_entropy", "val_share")],
         outcome=("it does not collapse: it re-tests about 3% of its budget, its order head stays near 5.9 nats where the "
                  "registered run fell to about 1.1, and it meets the registered transfer criterion on phoq:test (every "
                  "seed positive, also at the Bonferroni level). The registered Run B's heavy re-testing is a sensitivity "
                  "to the exploration bonus"),
         status="appendix",
         limits="Post-hoc. Three seeds; one changed setting."),
    dict(id="B11 robustness analyses part 2 (post-hoc): Run A replication, seeds 3 to 7",
         amendment="B11 robustness analyses part 2 (post-hoc)", tags=[], analysis=["b11_replication_A.json", "b11_cluster_bootstrap.json"],
         question=("Whether five more seeds of Run A, trained and tested exactly as registered, replicate seeds 0 to 2 on "
                   "nk:test, gb1:test and phoq:test; spec/B11_ROBUSTNESS_2.md item 7."),
         headline=[("B11 Run A seeds 3-7 %s, trained minus %s, pick" % (_sp, _n),
                    J("b11_cluster_bootstrap.json", "by_name", "b11_replication_A.json | %s, trained minus %s, pick"
                      % (_sp, _n), "mean"),
                    J("b11_cluster_bootstrap.json", "by_name", "b11_replication_A.json | %s, trained minus %s, pick"
                      % (_sp, _n), "cluster_interval"))
                   for _sp in ("nk:test", "gb1:test", "phoq:test") for _n in ("initialisation", "random", "guessing")] +
                  [("B11 Run A seeds 3-7 %s, trained re-testing share, %%" % _sp,
                    J("b11_replication_A.json", "splits", _sp, "table", "trained", "share", "mean"))
                   for _sp in ("nk:test", "gb1:test", "phoq:test")],
         outcome=("replicates seeds 0 to 2: every one of the five seeds beats its initialisation and random ordering on all "
                  "three test splits, and the registered criteria hold at the Bonferroni level; level with the guessing "
                  "rule on the grid"),
         status="appendix",
         limits="Post-hoc. The registered configuration; the original result rests on seeds 0 to 2."),
    dict(id="B11 robustness analyses part 2 (post-hoc): Run A seeds 0 to 7 pooled, shares and entropies",
         amendment="B11 robustness analyses part 2 (post-hoc)", tags=[], analysis=["b11_phase2_pooled.json"],
         question=("Run A's eight seeds pooled on nk:test, gb1:test and phoq:test against initialisation, random ordering "
                   "and the guessing rule, with cluster intervals; the Phase 2 runs' re-testing shares with cluster "
                   "intervals; and the last logged order- and nominate-head entropy of every B11 run."),
         headline=[("B11 Run A seeds 0-7 pooled %s, trained minus %s, pick" % (_sp, _n),
                    J("b11_phase2_pooled.json", "pooled_seeds_0_7", _sp, "trained minus %s, pick" % _n, "mean"),
                    J("b11_phase2_pooled.json", "pooled_seeds_0_7", _sp, "trained minus %s, pick" % _n, "ci"))
                   for _sp in ("nk:test", "gb1:test", "phoq:test") for _n in ("initialisation", "random", "guessing")] +
                  [("B11 Run A seeds 0-7 pooled %s, trained re-testing share, %%" % _sp,
                    J("b11_phase2_pooled.json", "pooled_seeds_0_7", _sp, "trained re-testing share, %", "mean"),
                    J("b11_phase2_pooled.json", "pooled_seeds_0_7", _sp, "trained re-testing share, %", "ci"))
                   for _sp in ("nk:test", "gb1:test", "phoq:test")] +
                  [("B11 %s, end-of-training %s" % (_r, _f.replace("_", " ")),
                    J("b11_phase2_pooled.json", "end_of_training", _r, _f))
                   for _r in ("Run A seeds 0-2 (registered)", "Run A seeds 3-7", "Run B (registered)",
                              "Run B, entropy_coef 0.05") for _f in ("order_entropy", "nominate_entropy")],
         outcome=("the eight seeds beat their initialisation and random ordering on all three test splits; against the "
                  "guessing rule the pooled interval includes zero on the grid, lies below zero on GB1 and sits just above "
                  "zero on PhoQ, where one seed of eight is below zero"),
         status="not reported: computed for the authors' review; the paper reports seeds 0 to 2 and 3 to 7 separately",
         limits="Post-hoc. Seeds 0 to 2 were registered; seeds 3 to 7 were trained after the registered test."),
    dict(id="landscape shares: GB1 and PhoQ viable shares, the grid slice's neighbours",
         amendment="paper review 2026-10-10", tags=[], analysis=["landscape_shares.json"],
         question=("The share of GB1's and PhoQ's 160,000 variants above each viability threshold (GB1 fitness > 0.1, "
                   "PhoQ > 1.0), each wild type's fitness, and how many of the grid's best candidate's one-letter "
                   "neighbours in Figure 3(b)'s slice are viable."),
         headline=[("GB1 share above the viability threshold, %", J("landscape_shares.json", "gb1", "viable_pct")),
                   ("GB1 wild type's fitness", J("landscape_shares.json", "gb1", "wild_type_fitness")),
                   ("PhoQ share above the viability threshold, %", J("landscape_shares.json", "phoq", "viable_pct")),
                   ("PhoQ wild type's fitness", J("landscape_shares.json", "phoq", "wild_type_fitness")),
                   ("PhoQ share at least as fit as the wild type, %",
                    J("landscape_shares.json", "phoq", "at_least_wild_type_pct")),
                   ("grid slice: the best candidate's one-letter neighbours shown",
                    J("landscape_shares.json", "grid_slice", "neighbours_shown")),
                   ("grid slice: of those, viable", J("landscape_shares.json", "grid_slice", "neighbours_viable")),
                   ("grid slice: viable share of its cells, %",
                    J("landscape_shares.json", "grid_slice", "slice_viable_pct")),
                   ("start slice: viable cells", J("landscape_shares.json", "start_slice", "viable_cells")),
                   ("start slice: cells", J("landscape_shares.json", "start_slice", "cells")),
                   ("start slice: viable share of its cells, %", J("landscape_shares.json", "start_slice", "viable_pct")),
                   ("start slice: the start's row and column, cells",
                    J("landscape_shares.json", "start_slice", "row_column_neighbours")),
                   ("start slice: the start's row and column, viable",
                    J("landscape_shares.json", "start_slice", "row_column_viable")),
                   ("start slice: its best candidate's value", J("landscape_shares.json", "start_slice", "best_value")),
                   ("the start's neighbours off its slice", J("landscape_shares.json", "start_slice", "off_slice_neighbours")),
                   ("the start's viable neighbours off its slice",
                    J("landscape_shares.json", "start_slice", "off_slice_viable"))],
         outcome=("GB1 7.20% and PhoQ 6.97% above their thresholds; 20 of the 38 neighbours are viable. GB1's wild "
                  "type reads 1.0, so its cutoff is a tenth of the wild type; PhoQ's reads 3.29, and 5.22% of PhoQ "
                  "variants are at least as fit as it. The slice through the start GDIF has 16 of 400 viable, 4 of 38 "
                  "in GDIF's row and column, best MDIF at 7.011; 20 of GDIF's 24 viable neighbours lie off it"),
         status="main text",
         limits="Shares are over all 160,000 variants, including GB1's 10,639 unmeasured variants, which read zero."),
    dict(id="neighbour clustering: viable neighbours of viable, good and start candidates",
         amendment="paper review 2026-10-10", tags=[], analysis=["landscape_shares.json"],
         question=("Do good candidates cluster? On the grid, scrambled GB1 and scrambled PhoQ, the share of each viable "
                   "candidate's 76 one-letter neighbours that are viable, over all viable candidates, over the top 10% "
                   "by true value, and for the start, against the landscape's viable share."),
         headline=[h for _k, _lab in (("grid", "grid"), ("gb1_scrambled", "scrambled GB1"), ("phoq_scrambled", "scrambled PhoQ"))
                   for h in (("%s, viable share, %%" % _lab, J("landscape_shares.json", "clustering", _k, "viable_pct")),
                             ("%s, viable neighbours of viable candidates, pooled, %%" % _lab,
                              J("landscape_shares.json", "clustering", _k, "all_viable", "pooled_viable_neighbour_pct")),
                             ("%s, viable neighbours of viable candidates, mean, %%" % _lab,
                              J("landscape_shares.json", "clustering", _k, "all_viable", "mean_viable_neighbour_pct")),
                             ("%s, viable neighbours of the top 10%%, pooled, %%" % _lab,
                              J("landscape_shares.json", "clustering", _k, "top_viable", "pooled_viable_neighbour_pct")),
                             ("%s, viable neighbours of the top 10%%, mean, %%" % _lab,
                              J("landscape_shares.json", "clustering", _k, "top_viable", "mean_viable_neighbour_pct")),
                             ("%s, the start's viable neighbours" % _lab,
                              J("landscape_shares.json", "clustering", _k, "start", "viable_neighbours")),
                             ("%s, the start's viable neighbours, %%" % _lab,
                              J("landscape_shares.json", "clustering", _k, "start", "viable_neighbour_pct")))] +
                  [("one-letter neighbours per candidate", J("landscape_shares.json", "clustering", "grid",
                                                             "neighbours_per_candidate"))],
         outcome=("good candidates cluster on all three: 7.00% of each landscape is viable, but 25.8% (grid), 45.9% "
                  "(GB1) and 37.6% (PhoQ) of a viable candidate's neighbours are, and 39.4%, 62.0% and 46.4% of a "
                  "top-10% candidate's; the start has 24, 32 and 50 viable neighbours of 76"),
         status="not yet in paper",
         limits="Scrambling relabels letters within each position, so neighbourhoods are the published landscapes' own."),
    dict(id="start check: the scripted rules from 50 random viable starts",
         amendment="review handover 3 (post-hoc)", tags=[], analysis=["start_robustness.json", "start_robustness_summary.json"],
         question=("Whether the scripted rules' best re-test setting k*, their re-testing share and their pick depend on the "
                   "start: 50 viable starts drawn at random on the grid, scrambled GB1 and scrambled PhoQ, each run on "
                   "the paper split's 1,500 campaign seeds, against the paper's own start."),
         headline=[h for _l, _lab in (("grid", "grid"), ("gb1_scrambled", "scrambled GB1"), ("phoq_scrambled", "scrambled PhoQ"))
                   for _r in ("guessing", "informed", "model-guided")
                   for h in (("%s, %s, the paper start's k*" % (_lab, _r),
                              J("start_robustness_summary.json", "landscapes", _l, "rules", _r, "paper_kstar")),
                             ("%s, %s, random starts with the paper start's k*, %%" % (_lab, _r),
                              J("start_robustness_summary.json", "landscapes", _l, "rules", _r, "same_kstar_as_paper_pct")),
                             ("%s, %s, re-testing share at each start's k*, median, %%" % (_lab, _r),
                              J("start_robustness_summary.json", "landscapes", _l, "rules", _r, "share_at_own_kstar", "median")),
                             ("%s, %s, pick at each start's k*, median" % (_lab, _r),
                              J("start_robustness_summary.json", "landscapes", _l, "rules", _r, "pick_at_own_kstar", "median")),
                             ("%s, %s, random starts with the paper start's k*" % (_lab, _r),
                              J("start_robustness_summary.json", "landscapes", _l, "rules", _r, "same_kstar_as_paper")))] +
                  [("random starts per landscape", J("start_robustness_summary.json", "n_random_starts")),
                   ("grid, guessing, re-testing share at each start's k*, min, %",
                    J("start_robustness_summary.json", "landscapes", "grid", "rules", "guessing", "share_at_own_kstar", "min")),
                   ("grid, guessing, re-testing share at each start's k*, max, %",
                    J("start_robustness_summary.json", "landscapes", "grid", "rules", "guessing", "share_at_own_kstar", "max")),
                   ("grid, model-guided, re-testing share at the paper start's k*, min, %",
                    J("start_robustness_summary.json", "landscapes", "grid", "rules", "model-guided", "share_at_paper_kstar", "min")),
                   ("grid, model-guided, re-testing share at the paper start's k*, max, %",
                    J("start_robustness_summary.json", "landscapes", "grid", "rules", "model-guided", "share_at_paper_kstar", "max")),
                   ("grid, model-guided, pick lost at the paper start's k*, max",
                    J("start_robustness_summary.json", "landscapes", "grid", "rules", "model-guided", "pick_lost_at_paper_kstar", "max")),
                   ("grid, model-guided, pick lost at the paper start's k*, median",
                    J("start_robustness_summary.json", "landscapes", "grid", "rules", "model-guided", "pick_lost_at_paper_kstar",
                      "median"))],
         outcome="see results/start_robustness_summary.json; reported to the authors, review handover 3",
         status="not yet in paper",
         limits=("Post-hoc. Scripted rules only. The informed rule takes no start, so its results are the same from every "
                 "start by construction (checked).")),
    dict(id="reference one reading: Table 1's scripted rows",
         amendment="paper review 2026-10", tags=[], analysis=["reference_one_reading.json"],
         question=("For each landscape's best scripted rule and guessing rule (Table 1's reference rows), the share of the "
                   "1,500 reference campaigns whose final pick had exactly one reading."),
         headline=[("%s, %s, nominees with one reading, %%" % (_land, _row),
                    J("reference_one_reading.json", _land, _row, "one_reading_pct"))
                   for _land in ("grid", "GB1", "PhoQ") for _row in ("best scripted", "guessing rule")],
         outcome=("re-testing once a round, the grid's rules pick a candidate with one reading in under 2% of campaigns; "
                  "without re-tests, on GB1 and PhoQ, in 99% to 100%"),
         status="appendix",
         limits="Rerun through Wellocate on the paper splits; each rerun reproduces its row's pick and share exactly."),
    dict(id="scripted rules at their best setting: Table 1's rows",
         amendment="paper review 2026-10", tags=[], analysis=["scripted_rules_best.json"],
         question=("The guessing, informed and model-guided rules on the grid, GB1 and PhoQ, each at the re-test setting "
                   "with the highest mean pick on the 1,500 reference campaigns: the setting, the re-testing share and the "
                   "pick."),
         headline=[h for _land in ("grid", "GB1", "PhoQ") for _r in ("guessing", "informed", "model-guided")
                   for h in (("%s, %s rule, best setting k" % (_land, _r),
                              J("scripted_rules_best.json", _land, "rules", _r, "k")),
                             ("%s, %s rule, re-testing share, %%" % (_land, _r),
                              J("scripted_rules_best.json", _land, "rules", _r, "share_budget")),
                             ("%s, %s rule, final pick" % (_land, _r),
                              J("scripted_rules_best.json", _land, "rules", _r, "pick")))],
         outcome=("the informed rule picks best on the grid (8.00) and PhoQ (2.63), the guessing rule on GB1 (6.09); the "
                  "model-guided rule is best at k = 1 on the grid and k = 0 on GB1 and PhoQ"),
         status="main text",
         limits=("Read from existing sweeps, nothing rerun. The model-guided sweep on GB1 and PhoQ is the post-hoc start "
                 "check's row for the paper's start; the reference runs used k = 1 there, and the two agree at k = 1.")),
    dict(id="top spread: the best candidates in units of assay noise", amendment="(descriptive)", tags=[],
         analysis=["top_spread.json"],
         question=("How tightly each landscape's best candidates are bunched, in units of the reading noise at the top at "
                   "assay noise: the best value minus the 10th best, and minus the 90th percentile of the viable values, "
                   "each over CV x best value, on the grid, scrambled GB1 and scrambled PhoQ."),
         headline=[h for _l in ("grid", "GB1", "PhoQ")
                   for h in (("%s, best minus 10th best, noise SDs" % _l, J("top_spread.json", _l, "ten_best_in_sd")),
                             ("%s, best minus the viable 90th percentile, noise SDs" % _l,
                              J("top_spread.json", _l, "top_tenth_in_sd")))],
         outcome=("the grid's ten best lie within a third of one reading's noise of the best; GB1's span about three "
                  "noise SDs and PhoQ's about seven, so one reading tells GB1's and PhoQ's leaders apart and not the "
                  "grid's"),
         status="main text",
         limits="Descriptive. Scrambled GB1 and PhoQ hold the same values as the real landscapes (checked)."),
]

# Result files that need no row (inputs, manifests, plans, checks), so the coverage rule can skip them.
NOT_ANALYSES = re.compile(r"^(grid_.*|findings)\.json$")


def get(obj, path):
    for p in path:
        obj = obj[p]
    return obj


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True, text=True).stdout.strip()


def n_per_cell(tags):
    cells = collections.Counter()
    for t in tags:
        p = os.path.join(RES, "grid_%s_campaigns.jsonl" % t)
        if not os.path.exists(p):
            continue
        for l in open(p):
            if l.strip():
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                cells[(t, r.get("condition"), r.get("model"))] += 1
    if not cells:
        return None
    v = sorted(cells.values())
    return dict(cells=len(v), min=v[0], max=v[-1], campaigns=sum(v))


def where(keys):
    """Main text if any key is printed outside the appendix, appendix if only there, else not in paper."""
    import paper_files as PF
    files = PF.parts()

    def has(rel, k):
        txt = open(os.path.join(PF.PAPER, rel)).read()
        return re.search(r"(?<![\d.])%s(?![\d])" % re.escape(k.replace(",", "{,}")), txt) or \
            re.search(r"(?<![\d.])%s(?![\d])" % re.escape(k), txt)
    if any(has(n, k) for n in files["main"] for k in keys):
        return "main text"
    if any(has(n, k) for n in files["appendix"] for k in keys):
        return "appendix"
    return "not yet in paper"


def build():
    import verify_paper_numbers as VP
    comp = VP.computed()
    rows, problems = [], []
    for spec in ROWS:
        heads = []
        for h in spec["headline"]:
            name, src = h[0], h[1]
            if src[0] == "verifier":
                val, ref = comp[src[1]][1], "verify_paper_numbers.computed()[%r]" % src[1]
            else:
                val, ref = get(json.load(open(os.path.join(RES, src[1]))), src[2]), "%s %s" % (src[1], src[2])
            row = dict(name=name, value=round(float(val), 6), source=ref)
            if len(h) > 2:                      # an interval, read from its own source like the value
                lo, hi = get(json.load(open(os.path.join(RES, h[2][1]))), h[2][2])
                row["ci"] = [round(float(lo), 6), round(float(hi), 6)]
            heads.append(row)
        out = spec["outcome"]
        if isinstance(out, tuple):
            out = "registered label `%s`" % get(json.load(open(os.path.join(RES, out[1]))), out[2])
        launch = ""
        for t in spec["tags"]:
            m = os.path.join(RES, "grid_%s_manifest.json" % t)
            if os.path.exists(m):
                launch = (json.load(open(m)).get("git_commit") or "")[:7]
                break
        files = [os.path.join("results", f) for f in spec["analysis"]]
        analysis_commit = git("log", "-1", "--format=%h", "--", *files) if files else ""
        vkeys = [h[1][1] for h in spec["headline"] if h[1][0] == "verifier"]
        if vkeys and spec["status"] in ("main text", "appendix", "not yet in paper"):
            found = where(vkeys[:1])
            if found != spec["status"]:
                problems.append("%s: status says %r, its numbers are printed in: %s" % (spec["id"], spec["status"], found))
        rows.append(dict(id=spec["id"], amendment=spec["amendment"], question=spec["question"], tags=spec["tags"],
                         analysis_files=files, launch_commit=launch, analysis_commit=analysis_commit,
                         n_per_cell=n_per_cell(spec["tags"]), headline=heads, outcome=out,
                         paper_status=spec["status"], limits=spec["limits"], pending=bool(spec.get("pending"))))
    # Coverage: every analysis file and every campaign tag belongs to a row.
    cited = {f for s in ROWS for f in s["analysis"]}
    for p in sorted(glob.glob(os.path.join(RES, "*.json"))):
        b = os.path.basename(p)
        if b.startswith("analysis_") and b not in cited:
            problems.append("results/%s belongs to no row" % b)
    tags = {t for s in ROWS for t in s["tags"]}
    for p in sorted(glob.glob(os.path.join(RES, "grid_*_campaigns.jsonl"))):
        t = os.path.basename(p)[len("grid_"):-len("_campaigns.jsonl")]
        if t not in tags:
            problems.append("campaign tag %s belongs to no row" % t)
    return rows, problems



def compare(rows, old):
    bad = []
    prev = {r["id"]: r for r in old.get("rows", [])}
    for r in rows:
        if r["pending"]:
            continue
        o = prev.get(r["id"])
        if o is None:
            bad.append("%s: no row in the committed findings.json" % r["id"])
            continue
        for k in ("n_per_cell", "paper_status", "outcome"):
            if r[k] != o.get(k):
                bad.append("%s: %s is %r, committed %r" % (r["id"], k, r[k], o.get(k)))
        oh = {h["name"]: (h["value"], h.get("ci")) for h in o.get("headline", [])}
        for h in r["headline"]:
            if oh.get(h["name"]) != (h["value"], h.get("ci")):
                bad.append("%s: %s is %s %s, committed %s" % (r["id"], h["name"], h["value"], h.get("ci"),
                                                             oh.get(h["name"])))
    return bad


def check():
    rows, problems = build()
    old = json.load(open(os.path.join(RES, "findings.json")))
    return problems + compare(rows, old)


def main():
    if "--check" in sys.argv:
        bad = check()
        print("findings: %s" % ("all rows match their sources" if not bad else "%d problem(s)" % len(bad)))
        for b in bad:
            print("  " + b)
        return 1 if bad else 0
    rows, problems = build()
    json.dump(dict(generated_by="scripts/findings.py", rows=rows), open(os.path.join(RES, "findings.json"), "w"),
              indent=1)
    counts = collections.Counter(r["paper_status"] for r in rows)
    print("%d rows; %s" % (len(rows), dict(counts)))
    for p in problems:
        print("PROBLEM " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
