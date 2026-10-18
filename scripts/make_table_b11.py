#!/usr/bin/env python3
"""Write paper/sections/table_b11.tex: the appendix tables for the policy trained in Wellocate.

Every number is read from the results/b11_*.json files: the pre-registered test, its cluster-bootstrap intervals
and the post-hoc robustness runs. scripts/verify_paper_numbers.py compares this file with render() and fails on
any difference.

Usage: python3 scripts/make_table_b11.py --write-paper
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import paper_write                                                   # noqa: E402

DST = os.path.join(ROOT, "paper", "sections", "table_b11.tex")
RES = os.path.join(ROOT, "results")
SPLITS = (("nk:test", "grid"), ("gb1:test", "GB1"), ("phoq:test", "PhoQ"))
COND = (("none", "none"), ("batch5", "batch 5\\%"), ("batch10", "batch 10\\%"), ("floor", "floor"),
        ("zeros", "failed wells"), ("spikes", "spikes"))


def load(name):
    return json.load(open(os.path.join(RES, name)))


def num(v, d=2, signed=False):
    s = ("%." + str(d) + "f") % abs(v)
    neg = v < 0 and float(s) != 0
    return ("$-$" if neg else ("$+$" if signed else "")) + s


def ci(c, d=2):
    lo, hi = c.get("ci") or c.get("cluster_interval")
    return "%s [%s, %s]" % (num(c["mean"], d, True), num(lo, d), num(hi, d))


def kname(name, slots=4):
    rule, k = name.split(" k=")
    return "%s %s" % (rule, k)


def table(label, caption, cols, head, rows, size="\\footnotesize", sep="3pt"):
    out = ["\\begin{table}[htbp]", "\\centering", size, "\\setlength{\\tabcolsep}{%s}" % sep, "\\caption{%s}" % caption,
           "\\label{%s}" % label,
           "\\begin{tabular}{%s}" % cols, "\\toprule", head + " \\\\", "\\midrule"]
    out += [r + " \\\\" if not r.startswith("\\") else r for r in rows]
    out += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return out


def registered():
    a, b, cl = load("b11_test_A.json"), load("b11_test_B.json"), load("b11_cluster_bootstrap.json")["by_name"]
    c = lambda f, sp, n: cl["%s | %s, trained minus %s, pick" % (f, sp, n)]
    rows = []
    lab = {"initialisation": "minus initialisation", "random": "minus random", "guessing": "minus guessing rule",
           "informed": "minus informed rule", "model-guided": "minus model-guided"}
    rows.append("trained pick & " + " & ".join(num(a["splits"][sp]["table"]["trained"]["pick"]["mean"])
                                                for sp, _ in SPLITS) +
                " & " + num(b["splits"]["phoq:test"]["table"]["trained"]["pick"]["mean"]))
    rows.append("re-testing share (\\%) & " + " & ".join(num(a["splits"][sp]["table"]["trained"]["share"]["mean"], 1)
                                                        for sp, _ in SPLITS) +
                " & " + num(b["splits"]["phoq:test"]["table"]["trained"]["share"]["mean"], 1))
    for n in ("initialisation", "random", "guessing", "informed", "model-guided"):
        rows.append(lab[n] + " & " + " & ".join(ci(c("b11_test_A.json", sp, n)) for sp, _ in SPLITS) + " & " +
                    ci(c("b11_test_B.json", "phoq:test", n)))
    return table("tab:b11reg",
                 "The registered test of the trained policy, 1{,}500 episodes per split, as a mean over three seeds. "
                 "Run A trained on generated landscapes only; Run B on generated landscapes and scrambled GB1, tested on "
                 "PhoQ. Differences are in final pick, with 95\\% intervals from a two-level bootstrap that resamples "
                 "landscapes and then episodes (post-hoc; the registered intervals resample episodes only).",
                 "lrrrr", " & Run A, grid & Run A, GB1 & Run A, PhoQ & Run B, PhoQ", rows, "\\small", "1.5pt")


def robustness():
    """One table for the grid-trained policy under every post-hoc change: noise, stress, real names, held-out
    ruggedness and budgets. Rows that repeat the pre-registered test (assay noise, no stress) are left out."""
    cl = load("b11_cluster_bootstrap.json")["by_name"]
    nz, stv = load("b11_robustness_noise.json")["levels"], load("b11_stress.json")["splits"]
    real, zero = load("b11_real_landscapes.json")["sets"], load("b11_zero_shot.json")["sets"]
    rows = []

    def row(group, cond, pick, share, rand, best):
        rows.append("%s & %s & %s & %s & %s & %s" % (group, cond, num(pick), num(share, 1), ci(rand), ci(best)))

    for i, (lv, name) in enumerate((("low", "noise halved (3.65\\%)"), ("high", "noise doubled (14.6\\%)"))):
        L = nz[lv]
        row("noise, grid" if i == 0 else "", name, L["policies"]["Run A"]["pick"]["mean"],
            L["policies"]["Run A"]["share"]["mean"], cl["b11_robustness_noise.json | %s, Run A minus random, pick" % lv],
            cl["b11_robustness_noise.json | %s, Run A minus best scripted (%s), pick" % (lv, L["best_scripted"])])
    for sp, land in (("nk:test", "grid"), ("gb1:test", "GB1")):
        rows.append("\\midrule")
        for i, (cond, cname) in enumerate(c for c in COND if c[0] != "none"):
            b = stv[sp][cond]
            row("stress, %s" % land if i == 0 else "", cname, b["policies"]["Run A"]["pick"]["mean"],
                b["policies"]["Run A"]["share"]["mean"], b["run_a_minus_random"]["pick"], b["run_a_minus_best"]["pick"])
    for group, d, keys in (("real names", real, (("gb1:transfer_real 15x4", "GB1"), ("phoq:transfer_real 15x4", "PhoQ"))),
                           ("held-out grids", zero, (("nk:test_ood_k2 15x4", "$K=2$"), ("nk:test_ood_k3 15x4", "$K=3$"))),
                           ("budgets, grid", zero, (("nk:test 10x4", "10 rounds of 4"), ("nk:test 20x4", "20 rounds of 4"),
                                                    ("nk:test 4x24", "4 rounds of 24")))):
        rows.append("\\midrule")
        for i, (key, name) in enumerate(keys):
            b = d[key]
            row(group if i == 0 else "", name, b["policies"]["Run A"]["pick"]["mean"],
                b["policies"]["Run A"]["share"]["mean"], b["run_a_minus_random"]["pick"], b["run_a_minus_best"]["pick"])
    return table("tab:b11robust",
                 "The trained policy (Run A, without retraining) under every change after the registered test, "
                 "1{,}500 episodes per row, at assay noise unless the row changes it. Rows that would repeat "
                 "Table~\\ref{tab:b11reg} are left out. The last two columns are Run A's pick minus random ordering and "
                 "minus the best scripted rule at its best number of re-tests, on the same episodes. Stress: each round's "
                 "readings share one multiplicative factor with this standard deviation (batch), or get an additive noise floor of 2\\% of the "
                 "landscape maximum (floor). In the other two, 2\\% of readings are replaced by a near-zero value (failed wells) or by three "
                 "times the reading (spikes). Real names: GB1 and PhoQ under their amino-acid names. At 4 rounds of 24 the "
                 "scripted rules' re-tests scale with the slots per round, and two of Run A's input features exceed the "
                 "range seen in training. Intervals as in Table~\\ref{tab:b11reg}; under real names, one landscape each, "
                 "they resample episodes only.",
                 "llrrrr", "change & condition & pick & share (\\%) & minus random & minus best scripted rule", rows,
                 "\\scriptsize")


def stress():
    """The scripted rules under the stress conditions that keep their best setting."""
    d = load("b11_stress.json")["splits"]
    rows, base = [], {}
    for sp, land in (("nk:test", "grid"), ("gb1:test", "GB1")):
        base[land] = {r: d[sp]["none"]["best_k"][r]["best"].split("=")[1] for r in ("guessing", "informed")}
        for cond, cname in COND:
            if cond in ("none", "spikes"):
                continue
            cells = []
            for rule in ("guessing", "informed"):
                k = d[sp][cond]["best_k"][rule]
                three, four = k["cost"]["k=3 minus best"], k["cost"]["k=4 minus best"]
                if three["ci"][1] >= 0 or four["ci"][1] >= three["ci"][0]:
                    raise SystemExit("REFUSED: the caption says three re-tests stay below the best and four lower "
                                     "still; %s %s %s does not" % (land, cname, rule))
                cells += ["%s (%s\\%%)" % (k["best"].split("=")[1], num(k["share"], 0)), ci(three)]
            rows.append("%s & %s & %s" % (land, cname, " & ".join(cells)))
        rows.append("\\midrule")
    if any(len(set(b.values())) != 1 for b in base.values()):
        raise SystemExit("REFUSED: the caption gives one best setting per landscape for both rules")
    return table("tab:b11stress",
                 "The guessing and informed rules under the stress conditions of Table~\\ref{tab:b11robust} "
                 "that keep their best number of re-tests, 1{,}500 episodes per landscape and condition, at assay "
                 "noise. Without stress their best is %s re-test a round on the grid and %s on GB1. Best k is the best "
                 "number of re-tests a round, with its re-testing share. Three minus best is the pick of three re-tests "
                 "a round minus that of the best, with intervals as in Table~\\ref{tab:b11reg}. Four re-tests a round "
                 "are lower still in every row."
                 % (base["grid"]["guessing"], base["GB1"]["guessing"]),
                 "llrrrr", "landscape & condition & guessing, best k & guessing, three minus best & informed, best k & "
                           "informed, three minus best", rows[:-1], "\\scriptsize")


def llm():
    d, cl = load("b11_robustness_llm.json")["arms"], load("b11_cluster_bootstrap.json")["by_name"]
    rows, names = [], {"grid": "grid", "gb1_scrambled": "GB1, scrambled", "gb1_real": "GB1, real names",
                       "phoq_scrambled": "PhoQ, scrambled"}
    for arm in ("grid", "gb1_scrambled", "gb1_real", "phoq_scrambled"):
        for label, M in d[arm]["models"].items():
            rows.append("%s & %s & %d & %s (%s\\%%) & %s (%s\\%%) & %s" % (
                names[arm], label, M["campaigns"], num(M["llm"]["pick"]["mean"]), num(M["llm"]["share"]["mean"], 0),
                num(M["policies"]["Run A"]["pick"]["mean"]), num(M["policies"]["Run A"]["share"]["mean"], 0),
                ci(cl["b11_robustness_llm.json | %s, %s, Run A minus the LLM, pick" % (arm, label)])))
        rows.append("\\midrule")
    return table("tab:b11llm",
                 "The trained policy (Run A, without retraining) on each language model's own campaigns, the same "
                 "landscape, campaign seeds, noise and budget. Pick, with re-testing share; the last column is Run A's "
                 "pick minus the model's, paired by campaign, with a 95\\% bootstrap interval over campaigns. Each of "
                 "these landscapes is outside the training and validation splits.",
                 "llrrrr", "landscape & model & campaigns & model & Run A & Run A minus model", rows[:-1], "\\scriptsize")


def behaviour():
    d = load("b11_behaviour.json")["runs"]
    rows = []
    for run in ("A", "B"):
        for sp, land in SPLITS:
            b = d["%s %s" % (run, sp)]
            m = b["mean_over_seeds"]
            rows.append("Run %s & %s & %s & %s & %s & %s & %s & %s & %s" % (
                run, land, num(m["retest_share"], 1), num(100 * m["retry_after_failure"], 0),
                num(100 * m["same_round_replicate"], 0), num(100 * m["retests_of_top3"], 0),
                num(100 * m["parent_top3"], 0), num(100 * m["nominee_is_shrinkage"], 0),
                ci(b["pick_cost_vs_shrinkage"])))
        rows.append("\\midrule")
    return table("tab:b11behaviour",
                 "What the trained policies do on the test splits, as a mean over three seeds. Share: "
                 "re-tests as a share of the budget. The next three columns split the re-tests: retries of an order "
                 "that failed, repeats of a candidate first read earlier the same round, and re-tests of one of the "
                 "three candidates with the highest mean reading. Parent: new candidates one letter from one of those "
                 "three. Nominee: how often it is the registered selection rule's nominee, and its pick minus that nominee's.",
                 "llrrrrrrr", "run & split & share (\\%) & retries (\\%) & same round (\\%) & top three (\\%) & "
                              "parent (\\%) & nominee (\\%) & pick cost", rows[:-1], "\\scriptsize")


def phase2():
    cl = load("b11_cluster_bootstrap.json")["by_name"]
    # Seeds 0 to 2 of the grid-trained policy are in the pre-registered test table; this one adds the reruns.
    files = (("b11_replication_A.json", None), ("b11_test_B.json", ("phoq:test",)), ("b11_B_ent05.json", None))
    data = {f: load(f) for f, _o in files}
    curves = load("b11_curves.json")
    rows = []
    for sp, land in SPLITS:
        cells_r, cells_s, cells_n = [], [], []
        for f, only in files:
            if only and sp not in only:
                cells_r += ["--"]; cells_s += ["--"]; cells_n += ["--"]
                continue
            c = cl["%s | %s, trained minus random, pick" % (f, sp)]
            per = c["seed"]["per_seed"]
            cells_r.append(ci(c))
            cells_s.append(num(data[f]["splits"][sp]["table"]["trained"]["share"]["mean"], 1))
            cells_n.append("%d of %d" % (sum(1 for x in per if x > 0), len(per)))
        rows += ["%s: minus random & %s" % (land, " & ".join(cells_r)),
                 "%s: re-testing share (\\%%) & %s" % (land, " & ".join(cells_s)),
                 "%s: seeds above random & %s" % (land, " & ".join(cells_n))]
    end = lambda run, f: sum(curves["%s_s%d" % (run, sd)]["points"][-1][f] for sd in (0, 1, 2)) / 3
    for f, lab in (("order_entropy", "order-head entropy, nats"), ("nominate_entropy", "nominate-head entropy, nats")):
        rows.append("%s & %s & %s & %s" % (
            lab, num(data["b11_replication_A.json"]["end_of_training"]["training_curves"][f]),
            num(end("B", f)), num(data["b11_B_ent05.json"]["end_of_training"]["training_curves"][f])))
    return table("tab:b11phase2",
                 "Five more seeds of Run A (three to seven), trained and tested as registered. Beside them, Run B "
                 "retrained with an entropy bonus five times the registered one, tested with the registered code on all "
                 "three test splits. Run B trains on the grid and GB1, so only PhoQ tests its transfer. Differences in final "
                 "pick against random ordering, with intervals as in "
                 "Table~\\ref{tab:b11reg}. Entropies are at the end of training: means over the last updates, averaged "
                 "over seeds.",
                 "lrrr", " & Run A, seeds 3 to 7 & Run B, registered & Run B, larger bonus", rows,
                 "\\scriptsize", "2pt")


def render():
    out = ["% Generated by scripts/make_table_b11.py from results/b11_*.json. Do not edit by hand;",
           "% scripts/verify_paper_numbers.py regenerates it and fails on any difference.", ""]
    out += registered() + robustness()
    # the tallest tables last, so the float pages pack without large gaps
    out += behaviour() + phase2() + llm() + stress()
    return "\n".join(out)


def main(argv=None):
    return paper_write.run(__file__, DST, render, argv)


if __name__ == "__main__":
    sys.exit(main())
