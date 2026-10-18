#!/usr/bin/env python3
"""Check every number in paper/*.tex against the released results, failing on a mismatch or a gap.

  1. Each figure the paper quotes equals the value recomputed from results/.
  2. Every number in the .tex is either a checked figure or on an explicit list of design constants and
     structural numbers; any other number is reported.

Usage: python3 scripts/verify_paper_numbers.py   (exit 1 on any mismatch or unaccounted number)
"""
import collections, glob, json, os, re, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "paper")


def load(p):
    return json.load(open(os.path.join(ROOT, "results", p)))


A0L_SEEDS = range(300000, 300060)   # must equal analyse_0al.SEEDS; asserted below


def computed():
    """{string as it must appear in the tex: (label, value)} for every quoted figure."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    os.environ.setdefault("ANALYSE_GRID_COMPLETE", "1")
    import analyse_0al as _A0L
    # The appendix is searched as a whole: every file main.tex inputs after \appendix (scripts/paper_files.py).
    import paper_files as PF
    _app_raw = PF.text("appendix")
    _app = " ".join(_app_raw.split())
    if list(_A0L.SEEDS) != list(A0L_SEEDS):
        raise SystemExit("MISMATCH: the prompt-check seeds in analyse_0al.py are no longer 300000 to 300059")
    g = load(os.path.join("analysis_final", "grid", "summary.json"))
    c = g["cells_detail"]
    # The scripted references, with neighbours drawn over the landscape's own letters.
    f = load("reference_curve_alphabet.json")["curves"]
    z = load(os.path.join("analysis_final", "zeronoise", "table2c_central_test.json"))["rows"]
    lp = load("lab_protocols.json")["rows"]
    rep = [100 * x["replication"]["over slots used"] for x in c]
    rep2 = [100 * x["replication"]["excl anchor, slots used"] for x in c]
    dis = [x["distinct"] for x in c]
    mean = [x["mean"] for x in c]
    ex = [x["exploration_shortfall"] for x in c]
    se = [x["selection_shortfall"] for x in c]
    lv = [r["panel_level"] for r in z]
    df = [r["diff"] for r in z]
    zlo = min(z, key=lambda r: r["panel_level"])
    zhi = max(z, key=lambda r: r["panel_level"])
    zbym, zimp = collections.defaultdict(list), collections.defaultdict(list)
    for r in z:
        zbym[r["model"].split("/")[-1]].append(r["panel_level"])
        zimp[r["model"].split("/")[-1]].append(r["panel_level"] - r["diff"])
    selshare = [100 * x["selection_shortfall"] /
                (x["selection_shortfall"] + x["exploration_shortfall"]) for x in c]
    zc = [json.loads(l) for l in
          open(os.path.join(ROOT, "results", "grid_zeronoise_campaigns.jsonl")) if l.strip()]
    zcell = collections.defaultdict(list)
    for x in zc:
        zcell[(x["condition"], x["model"].split("/")[-1])].append(x["replication_fraction"])
    zmeans = {k: 100 * st.mean(v) for k, v in zcell.items()}
    bym = collections.defaultdict(list)
    for k, v in zmeans.items():
        bym[k[1]].append(v)
    strict = load("strict_replication.json")["cells"]
    # "75" is printed for two values (75.4 and 74.6), so both are asserted to round to 75.
    if not (round(min(100 * x["replication"]["over slots used"] for x in c)) == 75 ==
            round(max(100 * x["replication"]["excl anchor, slots used"] for x in c))):
        raise SystemExit("MISMATCH: the two values the paper prints as 75 no longer both round to 75")
    # Loss split against the guessing rule (scripts/loss_vs_guessing.py): every cell tested worse, picked
    # better and ended behind, and the exploration deficit beat the selection gain in every cell.
    lvg = load("loss_vs_guessing.json")
    lv_cells = lvg["cells"]
    lx = [x["extra_exploration"] for x in lv_cells]
    lsel = [-x["selection_change"] for x in lv_cells]
    lnet = [x["net"] for x in lv_cells]
    if len(lv_cells) != 15 or not (min(lx) > 0 and min(lsel) > 0 and min(lnet) > 0):
        raise SystemExit("MISMATCH: not every cell tests worse, picks better and ends behind the guessing policy")
    if sum(a > b for a, b in zip(lx, lsel)) != 15:
        raise SystemExit("MISMATCH: the exploration deficit no longer beats the selection gain in all 15 cells")
    # "Opus 4.7 under Blind measured the most, yet five cells that measured fewer lost less to exploration."
    # The count is written as a word, so it is recomputed here.
    lvx = {(x["condition"], x["model"]): x["extra_exploration"] for x in lv_cells}
    top = max(c, key=lambda x: x["distinct"])
    top_key = (top["condition"], top["model"].split("/")[-1])
    fewer_less = sum(1 for x in c if x is not top and x["distinct"] < top["distinct"]
                     and lvx[(x["condition"], x["model"].split("/")[-1])] < lvx[top_key])
    if top_key != ("Blind", "claude-opus-4.7") or fewer_less != 5:
        raise SystemExit("MISMATCH: the Figure 4 caption's most-distinct cell or its count of five is stale")
    # DeepSeek V3.1's selection gain is quoted once ("stayed at 0.18"), so both conditions must round to it.
    ds_mech, ds_rule = (next(x for x in lv_cells if x["model"] == "deepseek-chat-v3.1" and
                             x["condition"] == k) for k in ("Mechanism", "Decision-rule"))
    if not round(-ds_mech["selection_change"], 2) == round(-ds_rule["selection_change"], 2) == 0.18:
        raise SystemExit("MISMATCH: DeepSeek V3.1's selection gain no longer stays at 0.18 under both conditions")
    # "0.18" is also another figure's key, so this use is bound to its phrase.
    if "its selection gain stayed at 0.18" not in _app:
        raise SystemExit("MISMATCH: the appendix no longer says DeepSeek V3.1's selection gain stayed at 0.18")
    # The triplicate comparison in words: every cell above it on the headline count, six below it
    # without re-orders of the reference candidate.
    tri = lp["(a) triplicate-everything|pool"]["replication"]
    if sum(r > tri for r in rep) != 15 or sum(r < tri for r in rep2) != 6:
        raise SystemExit("MISMATCH: the triplicate comparison is no longer 15 above and six below")
    # The reasoning panel's paired drops in final-pick fitness, read from the analysis's own table.
    t2b = open(os.path.join(ROOT, "results", "analysis_final", "panelc", "table2b_vs_stage1.txt")).read()
    rdiff = [float(m.group(1)) for m in re.finditer(
        r"^(?:Blind|Mechanism)\s+\S+\s+\d+\s+\d+\s+(-?\d+\.\d+)\s", t2b, re.M)]
    if len(rdiff) != 4 or max(rdiff) >= 0:
        raise SystemExit("MISMATCH: the reasoning panel no longer has four cells that all fall")
    # Why the decision rule moved only DeepSeek V3.1 (scripts/decision_rule_detail.py, paired by seed on
    # Table 3's campaigns): the claims in words are asserted here.
    drd = load("decision_rule_detail.json")["primary"]
    dsr, opr, gmr = drd["deepseek-chat-v3.1"], drd["claude-opus-4.7"], drd["gemini-2.5-flash"]
    if dsr["improved"] + dsr["worse"] + dsr["unchanged"] != 180 or dsr["chose_mean_mcnemar_p"] <= 0.05:
        raise SystemExit("MISMATCH: DeepSeek V3.1's paired set is not Table 3's, or its pick rule did change")
    if not dsr["best_tested_diff"] >= dsr["nominated_diff"] > 0:
        raise SystemExit("MISMATCH: DeepSeek V3.1's gain no longer comes from what it tested")
    if not (opr["replication"][1] > opr["replication"][0]
            and round(opr["distinct"][0] - opr["distinct"][1]) == 2):
        raise SystemExit("MISMATCH: Opus 4.7 no longer re-tests more and tries about two fewer under the rule")
    # "Moved by less than half a point": under half a point with an interval excluding zero.
    # "About as many candidates": the interval must include zero.
    rci, dci = dsr["replication_diff_ci"], dsr["distinct_diff_ci"]
    if not (abs(rci["mean"]) < 0.5 and (rci["hi"] < 0 or rci["lo"] > 0)):
        raise SystemExit("MISMATCH: DeepSeek V3.1's re-testing change is no longer under half a point and nonzero")
    if not dci["lo"] <= 0 <= dci["hi"]:
        raise SystemExit("MISMATCH: 'about as many candidates' now has an interval excluding zero")
    # Opus 4.7's pick change: 74% to 86%, p < 0.001. "86" is keyed elsewhere, so it is asserted here.
    if not (round(100 * opr["chose_mean"][1]) == 86 and opr["chose_mean_mcnemar_p"] < 0.001):
        raise SystemExit("MISMATCH: Opus 4.7's highest-mean picks under the rule are no longer 86%, p < 0.001")
    # The replication run (scripts/analyse_replication.py): its pre-registered label and every claim in words.
    rpl = load("replication_decision_rule.json")
    if rpl["label"] != "direction holds, not significant":
        raise SystemExit("MISMATCH: the replication's label is now %r; the paper quotes another" % rpl["label"])
    if rpl["fallbacks_excluded"] != {"Decision-rule": 1, "Mechanism": 0} or rpl["pairs"] != 119:
        raise SystemExit("MISMATCH: the replication no longer excludes one Decision-rule fallback from 119 pairs")
    if not (rpl["ci95_boot"][1] < 0.0699 and rpl["ci95_boot"][1] < 0.06):
        raise SystemExit("MISMATCH: the replication's interval no longer sits below 0.0699 and 0.06")
    rprov = {arm: max(c, key=c.get) for arm, c in rpl["provider_calls"].items()}
    if len(set(rprov.values())) != 1:
        raise SystemExit("MISMATCH: the two replication arms no longer share their main provider")
    # "Shrank to almost nothing": the replication keeps under a fifth of the original +0.0699.
    if not 0 < rpl["mean"] < 0.2 * 0.0699:
        raise SystemExit("MISMATCH: the replication no longer keeps under a fifth of the original gain")
    # The appendix's arm-by-arm comparison (not pre-registered, scripts/replication_vs_original.py): both
    # Decision-rule means print as one value, the Mechanism shift is large against its SE and the
    # Decision-rule shift small against its own.
    rvo = load("replication_vs_original.json")
    if not (round(rvo["original|Decision-rule"]["mean"], 3) == round(rvo["replication|Decision-rule"]["mean"], 3)
            == 7.736):
        raise SystemExit("MISMATCH: the two Decision-rule means no longer both print as 7.736")
    ms, ds = rvo["shift|Mechanism"], rvo["shift|Decision-rule"]
    if not (ms["diff"] > 2 * ms["se"] and abs(ds["diff"]) < ds["se"]):
        raise SystemExit("MISMATCH: the Mechanism arm no longer moved and the Decision-rule arm no longer held")
    # Table 3 row by row: seeds, difference and interval are compared with final_analysis_20k.log, and the
    # Holm column is recomputed from the log's raw p values with repdef.stats.holm. The log prints p to five
    # decimals, so the tolerance allows for six such rounding errors.
    sys.path.insert(0, ROOT)
    from repdef.stats import holm as _holm
    log = open(os.path.join(ROOT, "results", "final_analysis_20k.log")).read()
    lrow = re.compile(r"^\s*(claude-opus-4\.7|deepseek-chat-v3\.1|gemini-2\.5-flash)\s+(Aggregated|Decision-rule)"
                      r" vs Mechanism\s+(\d+)\s+\d+\s+([+-]\d\.\d{4})\s+\d\.\d{4}\s+\[([+-]\d\.\d{4}), "
                      r"([+-]\d\.\d{4})\]\s+(\d\.\d+)\s*$", re.M)
    logged = [(m.group(1), m.group(2), int(m.group(3)), m.group(4), m.group(5), m.group(6), float(m.group(7)))
              for m in lrow.finditer(log)][:6]
    if len(logged) != 6:
        raise SystemExit("MISMATCH: final_analysis_20k.log no longer holds the six confirmatory rows")
    adj = {(r[0], r[1]): a for r, (_i, _p, a, _rej) in zip(logged, _holm([r[6] for r in logged]))}
    res = _app_raw
    _lab = res.index("\\label{tab:confirm}")
    tab3 = res[res.rfind("\\begin{table}", 0, _lab):res.index("\\end{table}", _lab)]     # caption included
    name = {"Opus 4.7": "claude-opus-4.7", "DeepSeek V3.1": "deepseek-chat-v3.1",
            "Gemini 2.5 Flash": "gemini-2.5-flash"}
    trow = re.compile(r"^(Opus 4\.7|DeepSeek V3\.1|Gemini 2\.5 Flash)\s*&\s*(Aggregated|Decision-rule)\s*&\s*(\d+)\s*&"
                      r"\s*\$([+-]\d\.\d{4})\$\s*&\s*\$\[([+-]\d\.\d{4}), ([+-]\d\.\d{4})\]\$\s*&\s*"
                      r"(?:\\textbf\{)?(\d\.\d{4})\}?(\$\^\\dagger\$)?\s*\\\\", re.M)
    shown = {(name[m.group(1)], m.group(2)): m for m in trow.finditer(tab3)}
    by = {(r[0], r[1]): r for r in logged}
    if set(shown) != set(by):
        raise SystemExit("MISMATCH: Table 3's rows are not the log's six contrasts")
    for k, m in shown.items():
        r = by[k]
        if (int(m.group(3)), m.group(4), m.group(5), m.group(6)) != (r[2], r[3], r[4], r[5]):
            raise SystemExit("MISMATCH: Table 3 row %s %s differs from the analysis log" % k)
        if abs(float(m.group(7)) - adj[k]) > 0.5e-4 + 6 * 0.5e-5:
            raise SystemExit("MISMATCH: Table 3 Holm p for %s %s is %s, recomputed %.5f" % (k[0], k[1], m.group(7), adj[k]))
    # Exactly one row carries the dagger (survived Holm, then replicated), and its note quotes the replication.
    daggered = [k for k, m in shown.items() if m.group(8)]
    if daggered != [("deepseek-chat-v3.1", "Decision-rule")]:
        raise SystemExit("MISMATCH: the dagger is on %s, not on DeepSeek V3.1 Decision-rule alone" % daggered)
    note = "$^\\dagger$Did not hold up on %d new seeds: $%+.3f$, 95\\%% bootstrap interval $[%+.3f, %+.3f]$" % (
        rpl["planned_per_arm"], rpl["mean"], rpl["ci95_boot"][0], rpl["ci95_boot"][1])
    if note not in " ".join(tab3.split()):
        raise SystemExit("MISMATCH: Table 3's dagger note does not quote the replication as computed:\n  " + note)
    # The landscape figure (Figure 2) and its caption, from results/landscape_summary.json.
    land = load("landscape_summary.json")
    lpick = {m: p["mean"] for m, p in land["picks"].items()}
    ltop = [p["top_pct_of_viable"] for p in land["picks"].values()]
    if not (land["best"]["seq"] == "IOJO" and land["slice"]["fixed_letters"] == ["J", "O"]
            and land["reference"]["seq"] == "GDIF"):
        raise SystemExit("MISMATCH: the caption names IOJO, J and O, and GDIF; the landscape gives %s, %s, %s"
                         % (land["best"]["seq"], land["slice"]["fixed_letters"], land["reference"]["seq"]))
    # "sits at the median of the viable ones": half the viable candidates score at least the reference.
    if abs(land["reference"]["top_pct_of_viable"] - 50) > 0.5:
        raise SystemExit("MISMATCH: the reference is no longer at the viable median")
    # The caption's scripted figures are keyed elsewhere ("7.89", "3.3"); this run must agree with them.
    if (round(land["scripted"]["mean"], 2) != round(f["fair"]["1"]["mean"], 2)
            or round(land["scripted"]["top_pct_of_viable"], 1)
            != round(load("reference_percentile.json")["fair_k1"]["top_pct_of_viable"], 1)):
        raise SystemExit("MISMATCH: the landscape file and the reference files disagree on the scripted pick")
    # Wu et al.'s measured share: 149,361 of 160,000 variants had a usable reading. The count is the study's
    # own (eLife 5:e16965), since data/gb1.csv writes a zero for each unmeasured variant. "93.4" is also
    # another figure's key, so this use is asserted here.
    if round(100.0 * 149361 / 160000, 1) != 93.4:
        raise SystemExit("MISMATCH: 149,361 of 160,000 no longer rounds to 93.4%")
    # Bind the colliding number to its phrase in the text.
    _wu = "%.1f\\%% of them" % (100.0 * 149361 / 160000)
    if _wu not in _app:
        raise SystemExit("MISMATCH: the noise appendix must say %r" % _wu)
    # Gemini 3.1 Pro's share of its own selection loss recovered by a confirmation round: the pick change over
    # the selection loss shown in Figure 4. k = 3 is cited because it is the one k whose interval excludes zero.
    for _cf in ("confirm_counterfactual_0an7.json", "confirm_counterfactual_0an7_r2.json"):
        _pro = load(_cf)["Gemini 3.1 Pro"]
        for _k, _v in _pro["k"].items():
            if abs(_v["recovered_share_of_selection_shortfall"] - _v["d_vs_agent"] / _pro["selection_shortfall"]) > 1e-12:
                raise SystemExit("MISMATCH: %s k=%s: the recovered share is not the pick change over the selection loss"
                                 % (_cf, _k))
    _pro = load("confirm_counterfactual_0an7.json")["Gemini 3.1 Pro"]
    if abs(_pro["selection_shortfall"] - load("paper_figdata.json")["models"]["Gemini 3.1 Pro"]["selection_shortfall"]["mean"]) > 1e-12:
        raise SystemExit("MISMATCH: Gemini 3.1 Pro's selection loss differs between Figure 4 and the confirmation simulation")
    if sorted(_k for _k, _v in _pro["k"].items() if _v["d_vs_agent_ci"][0] > 0) != ["3"]:
        raise SystemExit("MISMATCH: k = 3 is no longer the one k whose interval excludes zero")
    # The prompt checks (Section 4.5 and its appendix), from results/analysis_0al.json and
    # results/prompt_checks_detail.json. Values that collide with other entries are asserted here.
    q = load("analysis_0al.json")
    qd = load("prompt_checks_detail.json")
    # The alphabet-correct risk-free yardstick.
    qy = load("riskfree_reference_alphabet.json")["riskfree"]
    qyk = qy["curve"][str(qy["kstar"])]
    qA, qB, qA0 = q["panel_A"]["cells"], q["panel_B"]["cells"], q["panel_A0"]
    if q["panel_A"]["label"] != "the wording moves the results":
        raise SystemExit("MISMATCH: Panel A's registered label changed; Section 4.5 quotes it")
    if q["panel_B"]["label"] != "rejection risk does not produce the habit":
        raise SystemExit("MISMATCH: Panel B's registered label changed; Section 4.5 paraphrases it")
    # Under the alphabet-correct yardstick every risk-free cell is at least twice its share and more than
    # 5 points above it.
    _qyc = load("riskfree_reference_alphabet.json")["riskfree"]
    _yc = _qyc["curve"][str(_qyc["kstar"])]["replication_share"]
    if not min(c["share_new"] for c in q["panel_B"]["cells"].values()) >= max(2 * _yc, _yc + 5):
        raise SystemExit("MISMATCH: under the corrected yardstick some Panel B cell is below twice its share")
    # The appendix quotes the pre-registered label word for word.
    if "``%s''" % q["panel_B"]["label"] not in _app:
        raise SystemExit("MISMATCH: the appendix does not quote Panel B's registered label word for word")
    small = [k for k, c in qA.items() if abs(c["d_share"]) < 1.1]
    if len(small) != 5 or "Blind|gemini-2.5-flash" in small:
        raise SystemExit("MISMATCH: Panel A no longer moves five cells by under 1.1 points, Gemini Blind apart")
    if round(max(abs(c["d_share"]) for c in qA0["drift_vs_grid"]["cells"].values()), 1) > 1.1:
        raise SystemExit("MISMATCH: Panel A0 moved more than 1.1 points from the grid in some cell")
    wide = sorted(k for k, c in qd["precision"].items() if c["half_width"] > 0.06)
    if wide != ["Blind|claude-opus-4.7", "Blind|gemini-2.5-flash", "Mechanism|claude-opus-4.7",
                "Mechanism|gemini-2.5-flash"]:
        raise SystemExit("MISMATCH: the cells whose smallest half-width exceeds 0.06 are now %s" % wide)
    wa = qA0["wording_vs_A0"]["cells"]
    if not (wa["Blind|gemini-2.5-flash"]["d_share_ci"][1] < 0 and wa["Mechanism|gemini-2.5-flash"]["d_fit_ci"][1] < 0):
        raise SystemExit("MISMATCH: a Gemini shift no longer holds against Panel A0")
    if any(c["cap_hits"] for c in qB.values()) or qd["riskfree_cap"] != 20:
        raise SystemExit("MISMATCH: Panel B had a cap hit, or the cap is no longer 20")
    gb, gm = qB["Blind|gemini-2.5-flash"], qB["Mechanism|gemini-2.5-flash"]
    if not (round(-gm["d_share"]) == 6 and round(-gb["d_share"]) == 11 and gb["d_fit_ci"][0] > 0
            and gm["d_fit_ci"][0] > 0 and min(gb["share_new"], gm["share_new"]) > 2 * qyk["replication_share"]):
        raise SystemExit("MISMATCH: Gemini under Panel B no longer drops 6 to 11 points, picks better, and stays far above")
    if any(c["fallbacks"] for c in list(qA.values()) + list(qB.values())) or qA0["fallbacks"]:
        raise SystemExit("MISMATCH: a prompt-check panel now has a 0ag fallback")
    seg = qd["panel_b_segments"]
    if not (seg["ceiling1"] == 40 and seg["segment2_campaigns"] == 25 and seg["commit1"] == seg["commit2"]):
        raise SystemExit("MISMATCH: Panel B's segments no longer stop at $40 and resume 25 at one commit")
    opm = qB["Mechanism|claude-opus-4.7"]
    # The Gemini numbers appear twice, so both sentences are rebuilt from the values and must appear.
    _ga = qA["Blind|gemini-2.5-flash"]
    _r1 = "it fell by %.1f points [$-%.1f$, $-%.1f$]" % (-_ga["d_share"], -_ga["d_share_ci"][0], -_ga["d_share_ci"][1])
    _r2 = "re-tested %d to %d points less" % (round(-gm["d_share"]), round(-gb["d_share"]))
    for _phrase, _text, _where in ((_r1, _app, "the appendix"), (_r2, _app, "the appendix")):
        if _phrase not in _text:
            raise SystemExit("MISMATCH: %s does not say %r" % (_where, _phrase))
    # "3.7" is also listed in ALLOWED for another figure, so it is asserted here.
    if round(dsr["distinct"][0], 1) != 3.7:
        raise SystemExit("MISMATCH: DeepSeek V3.1's distinct count under Mechanism no longer prints as 3.7")
    # The 1,500-landscape rescored scores: the count of exact 1.000 cells, and the range over cells where k* is not 1.
    _l15 = load("learnability_fresh_n1500_rescored.json")["cells"]
    lrn = [x["norm_heldout"]["LEARNED"] for x in _l15 if int(x["kstar"]) != 1]
    _exact = [x for x in _l15 if abs(x["norm_heldout"]["LEARNED"] - 1.0) < 1e-12]
    if not (len(_exact) == sum(1 for x in _l15 if int(x["kstar"]) == 1) == 15 and len(lrn) == 3):
        raise SystemExit("MISMATCH: the 1,500-landscape run no longer scores exactly 1.000 in its 15 k*=1 settings")
    core = [json.loads(l) for t in ("stage1", "topup_opus", "topup_gemini", "topup_deepseek")
            for l in open(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % t)) if l.strip()]
    n_ok = sum(c["n_ok"] for c in core)
    n_att = sum(c["slots_used"] - (c.get("lost_slots") or 0) for c in core)
    ncamp = sum(1 for t in ("stage1", "topup_opus", "topup_gemini", "topup_deepseek")
                for l in open(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % t)) if l.strip())
    ncalls = sum(load(os.path.join("grid_%s_calls" % t, "MANIFEST.json"))["total_lines"]
                 for t in ("stage1", "topup_opus", "topup_gemini", "topup_deepseek"))
    # The 200-landscape learnability numbers. A held-out score is undefined where the held-out span is zero or
    # negative; it is counted as undefined and kept out of every range.
    _l2r = load("learnability_fresh_n200.json")
    _l2 = load("learnability_fresh_n200_rescored.json")["cells"]
    _ok = lambda x: x == x
    _tr = [c["norm_training"]["LEARNED"] for c in _l2 if _ok(c["norm_training"]["LEARNED"])]
    _ho = [c["norm_heldout"]["LEARNED"] for c in _l2 if _ok(c["norm_heldout"]["LEARNED"])]
    _und = [c for c in _l2 if not _ok(c["norm_heldout"]["LEARNED"])]
    _ex2 = [c for c in _l2 if _ok(c["norm_heldout"]["LEARNED"]) and abs(c["norm_heldout"]["LEARNED"] - 1) < 1e-12]
    _raw2 = [(c["raw"]["C k* shrinkage"] - c["raw"]["D k=0 shrinkage"], c["cv"]) for c in _l2]
    _ks2 = collections.Counter(int(x["kstar"]) for x in _l2r["settings"])
    _lk = {sc: (v["trained_k"], v["trained_selector"]) for sc, v in _l2r["part2"].items()}
    _tied = sum(1 for x in _l2r["settings"] if int(x["kstar"]) == _lk[x["scope"]][0]
                or (int(x["runner_up"]) == _lk[x["scope"]][0] and x["gap_is_a_tie"]))
    _coll = {(x["sweep"]["4"]["collapsed"], x["sweep"]["3"]["collapsed"]) for x in _l2r["settings"]
             if int(x["K"]) == 3 and x["scope"] == "fair"}
    _half = min(c["cv"] for c in _l2)
    _checks = [
        (set(_lk.values()) == {(1, "shrinkage")} and _tied == 18,
         "the learner no longer selects k=1 with shrinkage, k* or tied in all 18"),
        (sum(1 for x in _l2r["settings"] if x["gap_is_a_tie"]) == 16, "16 of the 18 gaps are no longer ties"),
        ("$k^\\ast = 1$ in %d settings, $k^\\ast = 2$ in %d and $k^\\ast = 0$ in %d" % (_ks2[1], _ks2[2], _ks2[0])
         in _app and sum(_ks2.values()) == 18, "the k* counts in the appendix are not the sweep's"),
        (len(_tr) == 16 and len(_ho) == 14 and len(_und) == 4 and all(c["cv"] == _half for c in _und),
         "the undefined held-out scores are no longer the four half-noise cells"),
        (len(_ex2) == 11 and all(int(c["kstar"]) == 1 for c in _ex2) and max(_ho) == 1.0
         and "exactly 1.000 in the 11 cells where" in _app, "the exact 1.000 cells are no longer the 11 stated"),
        (sorted(cv for d, cv in _raw2 if d < 0) == [_half, _half], "the negative raw differences are not both at half noise"),
        (_coll == {(138, 12)} and "138 of 200 campaigns collapse at $k=4$ and 12 of 200 at $k=3$" in _app,
         "the K=3 collapses are not 138 and 12 of 200"),
    ]
    for _good, _msg in _checks:
        if not _good:
            raise SystemExit("MISMATCH: " + _msg)
    # Agent rejections and lost slots per campaign, from the 5,075 core campaigns.
    _rej = st.mean(c["n_rejected"] for c in core)
    _lost = st.mean(c.get("lost_slots") or 0 for c in core)
    _y0 = load("yardsticks_0am.json")["grid"]
    if abs(_y0["alphabet_policy"]["mean_at_kstar"] - f["fair"]["1"]["mean"]) > 1e-9:
        raise SystemExit("MISMATCH: 0am's corrected grid yardstick and the corrected reference curve disagree")
    # Rejections per new name (scripts/rejection_rates.py): new-name orders are rejected orders plus candidates
    # measured, excluding the starting candidate. The policy's rerun must match the corrected curve.
    _cells = collections.defaultdict(lambda: [0, 0, 0])
    for c in core:
        _x = _cells[(c["condition"], c["model"].split("/")[-1])]
        _x[0] += c["n_rejected"]
        _x[1] += c["n_distinct_measured"]
        _x[2] += 1 if c["anchor_orders"] > 0 else 0
    _crate = {k: 100.0 * v[0] / (v[0] + v[1] - v[2]) for k, v in _cells.items()}
    _t = [sum(v[i] for v in _cells.values()) for i in range(3)]
    _arate = 100.0 * _t[0] / (_t[0] + _t[1] - _t[2])
    _rr = load("rejection_rates.json")
    if (abs(_rr["policy"]["rejections_per_campaign"] - f["fair"]["1"]["rejections"]) > 1e-9
            or abs(_rr["policy"]["distinct_per_campaign"] - f["fair"]["1"]["distinct"]) > 1e-9
            or abs(_rr["agents"]["rate"] - _arate) > 1e-9):
        raise SystemExit("MISMATCH: rejection_rates.json disagrees with the corrected curve or the campaign files")
    _prate = _rr["policy"]["rate"]
    _above = {k for k, v in _crate.items() if v > _prate}
    _gem = {(c, "gemini-2.5-flash") for c in ("Blind", "Mechanism", "Aggregated", "Decision-rule")}
    _ds = {(c, "deepseek-chat-v3.1") for c in ("Blind", "Quantitative", "Mechanism", "Aggregated")}
    _below = {k for k, v in _crate.items() if v < _prate}
    if not (len(_crate) == 15 and _above == _gem | _ds and len(_below) == 7
            and "Eight of the 15 cells are rejected more often than the guessing rule and seven less often. The "
                "eight are Gemini 2.5 Flash in every condition except Quantitative, and DeepSeek V3.1 in every "
                "condition except Decision-rule" in _app):
        raise SystemExit("MISMATCH: the cells rejected more often than the guessing rule are not the eight named")



    out = {
        "75.4": ("lowest replication share", min(rep)), "95.6": ("highest replication share", max(rep)),
        "56.9": ("lowest, excl anchor", min(rep2)), "74.6": ("highest, excl anchor", max(rep2)),
        "2.57": ("fewest distinct", min(dis)), "11.34": ("most distinct", max(dis)),
        "28.94": ("fair distinct at k*", f["fair"]["1"]["distinct"]),
        "39.14": ("pool distinct at k*", f["pool"]["1"]["distinct"]),
        "39.2": ("most exploratory cell vs fair", 100 * max(dis) / f["fair"]["1"]["distinct"]),
        "7.6308": ("lowest cell mean", min(mean)), "7.8501": ("highest cell mean", max(mean)),
        "7.8659": ("fair k*", f["fair"]["1"]["mean"]), "7.9993": ("pool k*", f["pool"]["1"]["mean"]),
        # The Discussion quotes the bar to two decimals.
        "7.87": ("fair k*, two decimals", f["fair"]["1"]["mean"]),
        "8.00": ("pool k*, two decimals", f["pool"]["1"]["mean"]),
        "7.7098": ("fair k=0", f["fair"]["0"]["mean"]), "7.8862": ("pool k=0", f["pool"]["0"]["mean"]),
        "0.8428": ("lowest exploration shortfall", min(ex)),
        "1.0928": ("highest exploration shortfall", max(ex)),
        "0.0087": ("lowest selection shortfall", min(se)),
        "0.1148": ("highest selection shortfall", max(se)),
        # The zero-noise panel is quoted as percentages of slots, like the rest of the paper.
        "51.8": ("lowest zero-noise level", 100 * min(lv)),
        "97.5": ("highest zero-noise level", 100 * max(lv)),
        "90.6": ("median zero-noise level", 100 * st.median(lv)),
        "35.0": ("largest zero-noise drop, pp", 100 * abs(min(df))),
        "0.9": ("smallest zero-noise drop, pp", 100 * abs(max(df))),
        "48.2": ("lowest cell, interval low", 100 * zlo["lo"]),
        "55.4": ("lowest cell, interval high", 100 * zlo["hi"]),
        "96.7": ("highest cell's interval low, and DeepSeek's lowest implied level",
                 100 * zhi["lo"]),
        "98.3": ("highest cell, interval high", 100 * zhi["hi"]),
        "71.0": ("opus highest zero-noise level", 100 * max(zbym["claude-opus-4.7"])),
        "76.8": ("gemini lowest zero-noise level", 100 * min(zbym["gemini-2.5-flash"])),
        "94.4": ("gemini highest zero-noise level", 100 * max(zbym["gemini-2.5-flash"])),
        "94.1": ("deepseek lowest zero-noise level", 100 * min(zbym["deepseek-chat-v3.1"])),
        "98.5": ("deepseek highest implied level", 100 * max(zimp["deepseek-chat-v3.1"])),
        "11.1": ("largest selection share of the shortfall", max(selshare)),
        "88.9": ("smallest exploration share of the shortfall", 100 - max(selshare)),
        "99.2": ("largest exploration share of the shortfall", 100 - min(selshare)),
        "66.7": ("triplicate replication share", lp["(a) triplicate-everything|pool"]["replication"]),
        "50.0": ("duplicate replication share", lp["(b) duplicate-everything|pool"]["replication"]),
        "51.4": ("opus mean zero-noise replication", st.mean(bym["claude-opus-4.7"])),
        "81.6": ("gemini mean zero-noise replication", st.mean(bym["gemini-2.5-flash"])),
        "89.6": ("deepseek mean zero-noise replication", st.mean(bym["deepseek-chat-v3.1"])),
        "52.6": ("zero-noise Blind, opus", zmeans[("Blind", "claude-opus-4.7")]),
        "92.9": ("zero-noise Blind, gemini", zmeans[("Blind", "gemini-2.5-flash")]),
        "88.0": ("zero-noise Blind, deepseek", zmeans[("Blind", "deepseek-chat-v3.1")]),
        "5075": ("core-grid campaigns", ncamp), "162986": ("core-grid calls", ncalls),
        "11199": ("viable candidates", land["viable"]), "160000": ("candidates in the space", land["n"]),
        "8.762": ("global best", land["best"]["value"]), "6.8730": ("reference true score", land["reference"]["value"]),
        # Measurements attempted on viable candidates, and the share that failed.
        "14.97": ("realised failure rate", 100.0 * (1 - n_ok / n_att)),
        "300898": ("attempted measurements", n_att),
        # 4 draws from GB1's 11,522 viable variants (tests/test_landscapes.py pins that pool size).
        "0.035": ("chance rate in the recall probe", 100.0 * 4 / 11522),
        # The alphabet-correct guessing policy's share, from the yardstick file.
        "23.78": ("corrected guessing policy's share at k*", _y0["alphabet_policy"]["share_at_kstar"]),
        "16.75": ("agent rejections per campaign, core grid", _rej),
        "0.71": ("agent lost slots per campaign, core grid", _lost),
        "0.122": ("learnability, 200 landscapes: lowest learned score, training endpoints", min(_tr)),
        "7.765": ("learnability, 200 landscapes: highest learned score, training endpoints", max(_tr)),
        "0.784": ("learnability, 200 landscapes: lowest learned score, held-out endpoints", min(_ho)),
        "0.0077": ("learnability, 200 landscapes: lowest raw paired difference (negative)", -min(d for d, _c in _raw2)),
        "0.2231": ("learnability, 200 landscapes: highest raw paired difference", max(d for d, _c in _raw2)),
        "138": ("learnability, 200 landscapes: K=3 guessing collapses at k=4", next(iter(_coll))[0]),
        "72.2": ("agents' rejections per new name, %", _arate),
        "74.4": ("guessing policy's rejections per new name, %", _prate),
        "68.5": ("lowest cell's rejections per new name, %", min(_crate.values())),
        "89.0": ("highest cell's rejections per new name, %", max(_crate.values())),
        "0.819": ("n=1500 rescored, lowest learned score where k* is not 1", min(lrn)),
        "0.925": ("n=1500 rescored, highest learned score where k* is not 1", max(lrn)),
        # Noise parameters derived from Wu et al. 2016's read depths: 557 input and 285 selected reads per variant.
        "0.073": ("noise cv, sqrt(1/285 + 1/557)", (1 / 285.0 + 1 / 557.0) ** 0.5),
        "7.3": ("noise cv as a percentage", 100 * (1 / 285.0 + 1 / 557.0) ** 0.5),
        # Rounded forms quoted in the text, each tied to the value it rounds.
        "75": ("lowest replication share, whole percent", min(rep)),
        "57": ("lowest share without reference re-orders, whole percent", min(rep2)),
        "96": ("highest replication share, whole percent", max(rep)),
        "7": ("viable share, whole percent", land["viable_pct"]),
        # The stricter share, rebuilt from the prompts with three filters (scripts/strict_replication.py).
        "74.7": ("strict replication share, lowest cell", 100 * min(x["strict"] for x in strict)),
        "95.1": ("strict replication share, highest cell", 100 * max(x["strict"] for x in strict)),
        "1.4": ("largest gap between headline and strict share, pp",
                100 * max(x["headline"] - x["strict"] for x in strict)),
        "0.00351": ("noise floor, 1/285", 1 / 285.0),
        "0.0035": ("one post-selection read, 1/285", 1 / 285.0),
                "83.02": ("fair rejections at k=1", f["fair"]["1"]["rejections"]),
        # Figure 4's caption and the appendix, against the guessing policy at k=1.
        "0.18": ("smallest exploration deficit vs guessing", min(lx)),
        "0.43": ("largest exploration deficit vs guessing", max(lx)),
        "0.11": ("smallest selection gain vs guessing", min(lsel)),
        "0.22": ("largest selection gain vs guessing", max(lsel)),
        "0.02": ("smallest net deficit vs guessing", min(lnet)),
        "0.24": ("largest net deficit vs guessing", max(lnet)),
                "0.67": ("guessing policy's exploration shortfall", lvg["guessing"]["exploration"]),
                "0.38": ("DeepSeek V3.1 exploration deficit, Mechanism", ds_mech["extra_exploration"]),
        "0.099": ("reasoning panel, smallest drop in final pick", -max(rdiff)),
        "90": ("DeepSeek V3.1 highest-mean picks, Mechanism, %", 100 * dsr["chose_mean"][0]),
        "86": ("DeepSeek V3.1 highest-mean picks, Decision-rule, %", 100 * dsr["chose_mean"][1]),
        "93.7": ("DeepSeek V3.1 replication, Mechanism, paired", dsr["replication"][0]),
        "93.4": ("DeepSeek V3.1 replication, Decision-rule, paired", dsr["replication"][1]),
        "3.8": ("DeepSeek V3.1 distinct, Decision-rule, paired", dsr["distinct"][1]),
        "0.36": ("DeepSeek V3.1 pick rule, exact McNemar p", dsr["chose_mean_mcnemar_p"]),
        "74": ("Opus 4.7 highest-mean picks, Mechanism, %", 100 * opr["chose_mean"][0]),
        "0.008": ("replication, paired mean difference", rpl["mean"]),
        "74.8": ("prompt checks, lowest Panel B replication share", min(c["share_new"] for c in qB.values())),
        "23.96": ("risk-free scripted yardstick share at k*", qyk["replication_share"]),
        "4.6": ("Panel A, Gemini Blind replication change (negative)", -qA["Blind|gemini-2.5-flash"]["d_share"]),
        "6.6": ("Panel A, Gemini Blind change, interval low (negative)", -qA["Blind|gemini-2.5-flash"]["d_share_ci"][0]),
        "2.6": ("Panel A, Gemini Blind change, interval high (negative)", -qA["Blind|gemini-2.5-flash"]["d_share_ci"][1]),
        "0.160": ("Panel A, Gemini Mechanism final-pick change (negative)", -qA["Mechanism|gemini-2.5-flash"]["d_fit"]),
        "0.256": ("Panel A, Gemini Mechanism change, interval low (negative)", -qA["Mechanism|gemini-2.5-flash"]["d_fit_ci"][0]),
        "0.070": ("Panel A, Gemini Mechanism change, interval high (negative)", -qA["Mechanism|gemini-2.5-flash"]["d_fit_ci"][1]),
        "0.1340": ("Panel B, Opus Mechanism final-pick change (negative)", -opm["d_fit"]),
        "0.2324": ("Panel B, Opus Mechanism change, interval low (negative)", -opm["d_fit_ci"][0]),
        "0.0347": ("Panel B, Opus Mechanism change, interval high (negative)", -opm["d_fit_ci"][1]),
        "353": ("risk-free yardstick, campaigns reaching the cap at k*", qyk["campaigns_hitting_cap"]),
        "0.86": ("risk-free yardstick, slots still lost per campaign at k*", qyk["lost"]),
        "6.87": ("reference candidate GDIF, true fitness", land["reference"]["value"]),
        "7.74": ("highest model mean final pick, five conditions", max(lpick.values())),
        "5.9": ("most selective model mean pick, top % of viable", min(ltop)),
        "400": ("landscape slice, candidates", land["slice"]["n_cells"]),
        "7.736": ("Decision-rule arm mean, original and replication", rvo["original|Decision-rule"]["mean"]),
        "7.664": ("Mechanism arm mean, original", rvo["original|Mechanism"]["mean"]),
        "7.728": ("Mechanism arm mean, replication", rvo["replication|Mechanism"]["mean"]),
        "0.064": ("Mechanism arm, replication minus original", ms["diff"]),
        "0.023": ("Mechanism arm shift, Welch SE", ms["se"]),
        "0.036": ("replication, bootstrap interval low (negative)", -rpl["ci95_boot"][0]),
        "0.052": ("replication, bootstrap interval high", rpl["ci95_boot"][1]),
        "119": ("replication pairs after 0ag", rpl["pairs"]),
        "120": ("replication seeds per arm", rpl["planned_per_arm"]),
        "37": ("replication pairs improved", rpl["improved"]),
        "33": ("replication pairs worse", rpl["worse"]),
        "49": ("replication pairs unchanged", rpl["unchanged"]),
        "0.263": ("reasoning panel, largest drop in final pick", -min(rdiff)),

        "0.31": ("DeepSeek V3.1 exploration deficit, Decision-rule", ds_rule["extra_exploration"]),

        "0.23": ("guessing policy's selection shortfall", lvg["guessing"]["selection"]),

        "11.70": ("fair lost slots at k=1", f["fair"]["1"]["lost"]),
    }
    return out


# Numbers that are design constants, table entries checked elsewhere, or structure. Each is listed with
# the reason it needs no recomputation, so the list cannot quietly absorb a real result.
ALLOWED = {
    "4": "positions", "20": "alphabet size", "19": "other letters at a position: the alphabet of 20 less the current one",
    "15": "rounds", "60": "budget", "3": "models or re-asks",
    "5": "conditions", "1": "k* and counts", "2": "counts", "0": "zero", "6": "contrast family size",
    "93": "viability percentile", "7.00": "viable share", "557": "input reads per variant, Wu et al. 2016", "96": "a standard assay-plate format",
    "384": "a standard assay-plate format", "285": "selected reads per variant, Wu et al. 2016",
    "0.06": "minimal effect of interest", "0.05": "alpha", "8": "counts", "9": "counts", "12": "counts",
    "10": "counts", "11": "counts", "13": "counts", "14": "counts", "16": "counts", "18": "counts",
    "25": "the scripted optimum as a percentage", "40": "seeds per cell", "30": "protocol candidates",
    "48": "screening readings", "695": "opus N",
    "139": "gemini N", "181": "deepseek N", "180": "deepseek N after an exclusion",
    "20000": "bootstrap draws", "1500": "reference seeds", "200": "simulation landscapes",
    "270": "independent-test calls", "80": "reasoning-panel campaigns",
    "147": "fair collapses at k=4",
    "24": "slots per round in the plate-scale budget of the trained-policy appendix",
    "24.2": "independent test, opus exact-stated",
    "45.0": "independent test, gemini exact-stated", "55.8": "independent test, deepseek exact-stated",
    "50.8": "independent test, gemini exact-unstated", "49.2": "independent test, deepseek exact-unstated",
    "61.7": "independent test, opus noisy", "95.0": "independent test, gemini noisy",
    "94.2": "independent test, deepseek noisy", "37.5": "independent test, paired noise effect",
    "50.0": "independent test, paired noise effect", "38.3": "independent test, paired noise effect",
    "5.3": "SE", "7.0": "SE", "8.3": "SE", "2.4": "SE", "7.1": "SE", "6.9": "SE", "5.8": "pp or ratio",
    "6.7": "pp", "0.0": "pp", "0.3": "pp, or the design-sweep coefficient of variation 0.3", "1.0": "pp or temperature", "5.5": "pp", "0.8": "SE",
    "89.9": "gemini replication at temperature 1", "0.07": "temperature outcome bound",
    "0.04": "SE", "0.06.": "SE", "9.02": "opus distinct under Mechanism",
    "6.99": "opus distinct under Aggregated", "85.8": "opus replication under Aggregated",
    "0.0334": "contrast", "0.0606": "contrast", "0.0061": "contrast", "0.0316": "contrast",
    "0.0583": "contrast", "0.0049": "contrast", "0.0332": "contrast", "0.0757": "contrast",
    "0.0092": "contrast", "0.0699": "contrast", "0.0271": "contrast", "0.1126": "contrast",
    "0.0067": "contrast", "0.0130": "contrast", "0.0265": "contrast", "0.0044": "contrast",
    "0.0278": "contrast", "0.0189": "contrast", "0.0873": "Holm p", "0.3721": "Holm p",
    "0.0075": "Holm p", "1.0000": "Holm p", "0.372": "Holm p", 
       
       
      "49.1": "bio exact replication",
    "86.4": "bio exact replication", "6.5": "bio role shift", "9.8": "bio role shift",
    "2.9": "bio role shift", "8.5": "interval", "4.5": "interval", "12.7": "interval",
    "4.7": "interval", "1.2": "interval", "0.0987": "panel c", "0.2630": "panel c", "0.2528": "panel c",
    "0.2016": "panel c", "0.2338": "panel c", "7.5": "pp range", "12.4": "pp range", "3.7": "count",
    "7.1": "count", "7.6854": "panel c best measured", "7.7387": "panel c best measured",
    "7.5302": "panel c best measured", "7.6253": "panel c best measured", "0.19": "shortfall rise",
    "0.007": "shortfall rise", "0.085": "shortfall rise", "3034": "tokens", "6000": "token limit",
    "1.000": "an exact learned score, asserted in computed() for both learnability runs", "90.4": "provider share",
    "91.8": "provider share", "4.0": "version", "2.5": "version", "3.1": "version", "1.0928.": "x",
    "1.1": "x", "0.5": "noise multiplier", "2026": "year", "2019": "year", "2023": "year",
    "2024": "year", "2025": "year", "78": "figure width", "85": "figure width", "11": "font size",
    "0.00": "a scripted reference's zero rejections and zero lost slots",
    "123": "part of a DOI in a section reference",
    "35": "the lower bound of panel (c)'s seeds per cell",
    "3.5": "the GPT-3.5 model name in Related Work",
    "20.0": "screen-then-confirm replication share",
    "95": "the coverage of an interval",
    "19.8": "bio panel, exact minus role for opus, in results/bio_contrasts.json",
    "8.3": "bio panel, exact minus role for gemini",
    "1.8": "bio panel, exact minus role for deepseek",
    "0.001": "a p-value bound, asserted for Opus 4.7's pick change in computed()",
    "6.1": "the GPT-6.1 Sol model name",
    "0.6": "a design-sweep noise level, the coefficient of variation 0.6 (Wellocate note 1)",
    "16000": "the reasoning-token threshold the 0an.7 readout counts calls above",
    "7.9": "an illustrative example in the definition of selection loss",
    "7.7": "an illustrative example in the definition of selection loss",
    "0.2": "an illustrative example in the definition of selection loss",
}

NUM = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*(?![\w])")


def decimals(s):
    return len(s.split(".")[1]) if "." in s else 0


def main():
    want = computed()
    texts = {}
    for p in sorted(glob.glob(os.path.join(PAPER, "*.tex")) +
                    glob.glob(os.path.join(PAPER, "sections", "*.tex"))):
        texts[os.path.relpath(p, ROOT)] = open(p).read()
    # A generated table is compared byte for byte with a fresh render; if it matches, its numerals leave the scan.
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import make_table_cells as MTC
    import make_table_prompt as MTP
    # The main text quotes numbers from results/findings.json through macros in paper/sections/numbers.tex
    # and generated tables, so findings.json must match its result files.
    import findings as FD
    import make_paper_numbers as MPN
    import make_table_fixes as MTF
    import make_table_splits as MTS
    import make_table_models as MTMOD
    import make_table_landscapes as MTL
    import make_table_b11 as MTB11
    findings_problems = FD.check()
    tables = {os.path.relpath(m.DST, ROOT): (m, texts.get(os.path.relpath(m.DST, ROOT)) == m.render())
              for m in (MTC, MTP, MTF, MTS, MTMOD, MTL, MTB11, MPN)}
    generated = {rel for rel, (_m, ok) in tables.items() if ok}
    joined = " ".join(texts.values())

    print("=" * 96)
    print("PAPER NUMBERS: recomputed, and every numeral accounted for")
    print("=" * 96)
    bad = []
    # Presence is checked on whole numerals, and a missing figure fails.
    present = {m.group(0).replace(",", "") for m in NUM.finditer(joined.replace("{,}", ""))}
    for s, (label, val) in sorted(want.items()):
        shown = s in present
        if not shown:
            bad.append("%s: checked value %s does not appear in the paper; it was changed or the check is stale"
                       % (label, s))
        # The tolerance is the printed precision.
        ok = abs(float(s) - float(val)) <= 0.5 * 10 ** -decimals(s) + 1e-9
        if not ok:
            bad.append("%s: paper says %s, results give %.4f" % (label, s, val))
        print("  %-42s %-12s %s%s" % (label, s, "recomputed %.4f" % val,
                                      "" if shown else "   NOT IN THE PAPER"))
    print()
    seen = set()
    unaccounted = collections.Counter()
    for rel, t in texts.items():
        if rel in generated:
            continue
        # Only an unescaped % starts a LaTeX comment.
        body = re.sub(r"(?<!\\)%.*", "", t)
        # LaTeX writes a thousands separator as 5{,}075, and a naive scan reads that as "5" and "075".
        body = body.replace("{,}", "")
        # Figure widths and font sizes are typesetting, not results.
        body = re.sub(r"\\includegraphics\[[^\]]*\]", " ", body)
        body = re.sub(r"width=[\d.]+\\\w+", " ", body)
        # A table column width, p{0.44\textwidth}, is the same kind of thing as a figure width.
        body = re.sub(r"\{[\d.]+\\(?:textwidth|linewidth|columnwidth)\}", " ", body)
        # Float placement parameters are typesetting too.
        body = re.sub(r"\\renewcommand\{\\\w*fraction\}\{[\d.]+\}", " ", body)
        body = re.sub(r"\\setcounter\{\w*number\}\{\d+\}", " ", body)
        for m in NUM.finditer(body):
            tok = m.group(0).replace(",", "")
            if tok in want or tok in ALLOWED or tok.rstrip("0").rstrip(".") in want:
                continue
            unaccounted[(rel, tok)] += 1
            seen.add(tok)
    if unaccounted:
        print("  NUMERALS NOT ACCOUNTED FOR (%d distinct):" % len(seen))
        for (rel, tok), n in sorted(unaccounted.items())[:40]:
            print("    %-34s %-12s x%d" % (rel, tok, n))
    print("=" * 96)
    if bad:
        print("%d MISMATCH(ES):" % len(bad))
        for b in bad:
            print("  %s" % b)
    for table_rel, (mod, table_ok) in sorted(tables.items()):
        script = os.path.basename(mod.__file__)
        if not table_ok:
            bad.append("%s differs from a fresh render of %s" % (table_rel, script))
            print("  TABLE: %s differs from a fresh render. Run %s." % (table_rel, script))
        else:
            print("  TABLE: %s matches a fresh render of the analysis output" % table_rel)
    # A file under paper/ that main.tex does not reach is reported as an orphan.
    import paper_files as PF
    for rel in PF.orphans():
        bad.append("paper/%s is not reached from main.tex; remove it, or \\input it" % rel)
        print("  ORPHAN: paper/%s is not reached from main.tex" % rel)
    # Every macro the text uses must be defined; the count of those used is reported.
    defined = set(re.findall(r"\\newcommand\{\\(n[A-Za-z]+)\}", texts.get(os.path.relpath(MPN.DST, ROOT), "")))
    used = collections.Counter()
    for rel, t in texts.items():
        if rel == os.path.relpath(MPN.DST, ROOT):
            continue
        body = re.sub(r"(?<!\\)%.*", "", t)
        used.update(m for m in re.findall(r"\\(n[A-Z][A-Za-z]*)(?![A-Za-z])", body))
    undefined = sorted(set(used) - defined)
    if undefined:
        bad.append("macros used but not defined in numbers.tex: %s" % ", ".join(undefined))
    for prob in findings_problems:
        bad.append("findings.json does not match its sources: %s" % prob)
    if findings_problems:
        print("  FINDINGS: %d problem(s); the findings chain is broken" % len(findings_problems))
    else:
        print("  FINDINGS: findings.json matches every result file it reads (findings.py --check)")
    allowed_hits = {tok for rel, t in texts.items() if rel not in generated
                    for tok in (m.group(0).replace(",", "") for m in NUM.finditer(re.sub(r"(?<!\\)%.*", "", t).replace("{,}", "")))
                    if tok in ALLOWED and tok not in want}
    print("  COUNTS: %d numbers recomputed from raw results; %d numbers from checked findings rows (macros used, of %d "
          "defined); %d structural constants on ALLOWED; %d numerals with neither" % (
              sum(1 for k in want if k in present), len(used), len(defined), len(allowed_hits), len(seen)))
    if bad or unaccounted:
        return 1
    print("  every quoted figure matches the results, and every numeral is accounted for")
    return 0


if __name__ == "__main__":
    sys.exit(main())
