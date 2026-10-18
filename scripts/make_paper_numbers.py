#!/usr/bin/env python3
"""Write paper/sections/numbers.tex: one LaTeX macro per number the main text quotes from results/findings.json.

scripts/verify_paper_numbers.py regenerates this file and fails if the copy in paper/ differs, so a macro cannot
drift from its findings row. Numbers the verifier recomputes from raw results are not routed through here.

Usage: python3 scripts/make_paper_numbers.py
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "paper", "sections", "numbers.tex")
HEAD = "headline figure data: five models on the grid"
MODELS = [("Opus", "Opus 4.7"), ("Flash", "Gemini 2.5 Flash"), ("Deep", "DeepSeek V3.1"), ("Sol", "GPT-6.1 Sol"),
          ("Pro", "Gemini 3.1 Pro")]

# (macro, findings row, headline name, part, format). part: value, ci. format: see fmt().
MACROS = []
for short, name in MODELS:
    MACROS += [("nShare%s" % short, HEAD, "%s, re-testing share, %%" % name, "value", "f1"),
               ("nShare%sci" % short, HEAD, "%s, re-testing share, %%" % name, "ci", "f1"),
               ("nShare%sint" % short, HEAD, "%s, re-testing share, %%" % name, "value", "f0"),
               ("nNonlost%s" % short, HEAD, "%s, share over slots not lost, %%" % name, "value", "f1"),
               ("nNonlost%sci" % short, HEAD, "%s, share over slots not lost, %%" % name, "ci", "f1"),
               ("nPick%s" % short, HEAD, "%s, final pick" % name, "value", "f3"),
               ("nPick%sci" % short, HEAD, "%s, final pick" % name, "ci", "f3"),
               ("nExpl%s" % short, HEAD, "%s, exploration loss" % name, "value", "f2"),
               ("nExpl%sci" % short, HEAD, "%s, exploration loss" % name, "ci", "f2"),
               ("nSel%s" % short, HEAD, "%s, selection loss" % name, "value", "f2"),
               ("nSel%sci" % short, HEAD, "%s, selection loss" % name, "ci", "f2")]
# The reference range on the grid, rounded.
MACROS += [("nGuessShareInt", "scripted yardsticks", "guessing share at k*, %", "value", "f0"),
           ("nBandHiInt", "0an.4 model-guided scripted reference", "re-testing share at that best, %", "value", "f0")]
# Scrambled PhoQ, Blind condition, five models.
PQ = "0an.8 PhoQ Blind, five models"
for short, name in MODELS:
    MACROS += [("nPqN%s" % short, PQ, "%s, PhoQ campaigns" % name, "value", "f0"),
               ("nPqShare%s" % short, PQ, "%s, PhoQ re-testing share, %%" % name, "value", "f1"),
               ("nPqShare%sci" % short, PQ, "%s, PhoQ re-testing share, %%" % name, "ci", "f1"),
               ("nPqNonlost%s" % short, PQ, "%s, PhoQ share over slots not lost, %%" % name, "value", "f1"),
               ("nPqNonlost%sci" % short, PQ, "%s, PhoQ share over slots not lost, %%" % name, "ci", "f1"),
               ("nPqPick%s" % short, PQ, "%s, PhoQ final pick" % name, "value", "f3"),
               ("nPqPick%sci" % short, PQ, "%s, PhoQ final pick" % name, "ci", "f3"),
               ("nPqLead%s" % short, PQ, "%s, PhoQ pick minus the guessing rule" % name, "value", "s2"),
               ("nPqLead%sci" % short, PQ, "%s, PhoQ pick minus the guessing rule" % name, "ci", "s2"),
               ("nPqExpl%s" % short, PQ, "%s, PhoQ exploration loss" % name, "value", "f2"),
               ("nPqExpl%sci" % short, PQ, "%s, PhoQ exploration loss" % name, "ci", "f2"),
               ("nPqSel%s" % short, PQ, "%s, PhoQ selection loss" % name, "value", "f3"),
               ("nPqSel%sci" % short, PQ, "%s, PhoQ selection loss" % name, "ci", "f3"),
               ("nPqDistinct%s" % short, PQ, "%s, PhoQ distinct candidates" % name, "value", "f1"),
               ("nPqOneReading%s" % short, PQ, "%s, PhoQ nominees with one reading, %%" % name, "value", "f0"),
               ("nPqTop%s" % short, PQ, "%s, PhoQ top nominee count" % name, "value", "f0")]
for short, name in MODELS[:3]:
    MACROS += [("nPqOamN%s" % short, PQ, "%s, 0am PhoQ Blind campaigns" % name, "value", "f0"),
               ("nPqOamShare%s" % short, PQ, "%s, 0am PhoQ Blind share, %%" % name, "value", "f1"),
               ("nPqOamShare%sci" % short, PQ, "%s, 0am PhoQ Blind share, %%" % name, "ci", "f1"),
               ("nPqOamPick%s" % short, PQ, "%s, 0am PhoQ Blind pick" % name, "value", "f2"),
               ("nPqOamPick%sci" % short, PQ, "%s, 0am PhoQ Blind pick" % name, "ci", "f2")]
MACROS += [("nPqBestShare", PQ, "PhoQ best scripted share, %", "value", "f2"),
           ("nPqBestPick", PQ, "PhoQ best scripted pick (informed rule, k = 0)", "value", "f2"),
           ("nPqGuessShare", PQ, "PhoQ guessing rule share at k* = 0, %", "value", "f2"),
           ("nPqGuessPick", PQ, "PhoQ guessing rule pick at k* = 0", "value", "f3"),
           ("nPqMgShare", PQ, "PhoQ model-guided share, %", "value", "f2"),
           ("nPqMgPick", PQ, "PhoQ model-guided pick", "value", "f3"),
           ("nPqSpend", PQ, "panel spend by credit balance, smoke included, $", "value", "f2"),
           ("nPqSpendRecorded", PQ, "panel spend by campaign records, smoke included, $", "value", "f2")]
# Descriptive rows: three landscapes side by side, picks paired with the guessing rule, and Sol's PhoQ lead
# grouped by nominee.
LSR, PRR, SOR = ("0an.8 descriptive: three landscapes side by side",
                 "0an.8 descriptive: picks paired with the guessing rule on the agents' seeds",
                 "0an.8 descriptive: Sol's PhoQ lead grouped by nominee")
MACROS += [("nGbNOpus", LSR, "GB1, Opus 4.7, campaigns", "value", "f0"),
           ("nPqFlashLostRounds", PQ, "Gemini 2.5 Flash, PhoQ slots lost to incomplete rounds per campaign", "value", "f1"),
           ("nGbOneReadingPro", LSR, "GB1, Gemini 3.1 Pro, nominees with one reading, %", "value", "f0"),
           ("nGridOneReadingPro", LSR, "grid, Gemini 3.1 Pro, nominees with one reading, %", "value", "f0")]
# The grid's scripted rules, the same measure (results/reference_one_reading.json): the informed rule is the grid's
# best scripted rule, both at one re-test a round.
ROR = "reference one reading: Table 1's scripted rows"
MACROS += [("nGridOneReadingInf", ROR, "grid, best scripted, nominees with one reading, %", "value", "f0"),
           ("nGridOneReadingGuess", ROR, "grid, guessing rule, nominees with one reading, %", "value", "f0")]
for short, name in MODELS:
    for land, tag in (("GB1", "Gb"), ("PhoQ", "Pq")):
        MACROS += [("nPair%s%s" % (tag, short), PRR, "%s, %s, pick minus the guessing rule, paired by seed" % (land, name),
                    "value", "s2"),
                   ("nPair%s%sci" % (tag, short), PRR, "%s, %s, pick minus the guessing rule, paired by seed" % (land, name),
                    "ci", "s2")]
for key, label in (("Reg", "as registered"), ("Nom", "grouped by nominee"), ("Once", "top nominee counted once"),
                   ("OnceNom", "top nominee once, grouped by nominee")):
    MACROS += [("nPqSolLead%s" % key, SOR, "Sol PhoQ lead over the guessing rule, %s" % label, "value", "s2"),
               ("nPqSolLead%sci" % key, SOR, "Sol PhoQ lead over the guessing rule, %s" % label, "ci", "s2")]
MACROS += [("nPqSolDistinctNominees", SOR, "Sol PhoQ distinct nominees", "value", "f0")]
R7, A1, A1b, A2 = "0an.7 main run", "A1 counterfactual confirmation round", "A1 exploratory: last two rounds replaced", \
    "A2 Sol GB1 Blind, one nominee"
SC, NS, MG = "Wellocate baseline scorecard (B3, B4)", "Wellocate noise sweep (B9, B10)", "0an.4 model-guided scripted reference"
MACROS += [
    ("nBandHi", MG, "re-testing share at that best, %", "value", "f2"),
    ("nProOneReading", R7, "Gemini nominees with one reading, grid", "value", "pct0"),
    ("nProHeavyCalls", R7, "Gemini calls above 16,000 reasoning tokens", "value", "f0"),
    ("nProMaxReasoning", R7, "Gemini largest reasoning tokens in one call", "value", "thou"),
    ("nSolMenuShare", R7, "Sol Menu minus Blind on GB1, share, points", "value", "s1"),
    ("nSolMenuShareci", R7, "Sol Menu minus Blind on GB1, share, points", "ci", "s1"),
    ("nProMenuShare", R7, "Gemini Menu minus Blind on GB1, share, points", "value", "s1"),
    ("nProMenuShareci", R7, "Gemini Menu minus Blind on GB1, share, points", "ci", "s1"),
    ("nSolMenuPick", R7, "Sol Menu minus Blind on GB1, pick", "value", "s2"),
    ("nSolMenuPickci", R7, "Sol Menu minus Blind on GB1, pick", "ci", "s2"),
    ("nProMenuPick", R7, "Gemini Menu minus Blind on GB1, pick", "value", "s2"),
    ("nProMenuPickci", R7, "Gemini Menu minus Blind on GB1, pick", "ci", "s2"),
    ("nAoneProKthree", A1, "Gemini 3.1 Pro, k = 3, pick change", "value", "s3"),
    ("nAoneProKthreeci", A1, "Gemini 3.1 Pro, k = 3, pick change", "ci", "s3"),
    ("nAoneSolKone", A1, "Sol, k = 1, pick change", "value", "s3"),
    ("nAoneSolKoneci", A1, "Sol, k = 1, pick change", "ci", "s3"),
    ("nAtwoProKthree", A1b, "Gemini 3.1 Pro, k = 3, pick change", "value", "s3"),
    ("nAtwoProKthreeci", A1b, "Gemini 3.1 Pro, k = 3, pick change", "ci", "s3"),
    ("nAtwoProRecovered", A1b, "Gemini 3.1 Pro, k = 3, share of its selection loss against F0 recovered", "value", "pct0"),
    # Against Gemini 3.1 Pro's own selection loss, as in Figures 4 and 5d: one and two final rounds at k = 3.
    ("nAoneProRecoveredKthree", A1, "Gemini 3.1 Pro, k = 3, share of its own selection loss recovered", "value", "pct0"),
    ("nAtwoProRecoveredOwn", A1b, "Gemini 3.1 Pro, k = 3, share of its own selection loss recovered", "value", "pct0"),
    ("nSolGbLeadReg", A2, "pick minus guessing, as registered", "value", "s2"),
    ("nSolGbLeadRegci", A2, "pick minus guessing, as registered", "ci", "s2"),
    ("nSolGbLeadClu", A2, "pick minus guessing, cluster bootstrap by nominee", "value", "s2"),
    ("nSolGbLeadCluci", A2, "pick minus guessing, cluster bootstrap by nominee", "ci", "s2"),
    ("nSolGbLeadCol", A2, "pick minus guessing, FSRM collapsed to one", "value", "s2"),
    ("nSolGbLeadColci", A2, "pick minus guessing, FSRM collapsed to one", "ci", "s2"),
    ("nEpisodesPerSec", SC, "episodes per second, one core", "value", "f0"),
    ("nAuditCalls", "audit: reasoning text used as the answer", "calls read", "value", "thou"),
    ("nAuditHits", "audit: reasoning text used as the answer", "calls meeting the rule", "value", "f0"),
    ("nSplitFlashExpl", "0an pick split and exploration", "F2 Gemini exploration part", "value", "s2"),
    ("nSplitFlashExplci", "0an pick split and exploration", "F2 Gemini exploration part", "ci", "s2"),
    ("nSplitFlashSel", "0an pick split and exploration", "F2 Gemini selection part", "value", "s2"),
    ("nSplitFlashSelci", "0an pick split and exploration", "F2 Gemini selection part", "ci", "s2"),
    ("nSplitDeepExpl", "0an pick split and exploration", "F2 DeepSeek exploration part", "value", "s2"),
    ("nSplitDeepExplci", "0an pick split and exploration", "F2 DeepSeek exploration part", "ci", "s2"),
    ("nSplitDeepSel", "0an pick split and exploration", "F2 DeepSeek selection part", "value", "s2"),
    ("nSplitDeepSelci", "0an pick split and exploration", "F2 DeepSeek selection part", "ci", "s2"),
    ("nSplitOpusSel", "0an.5 Opus menu top-up", "Opus selection part at n = 60", "value", "s2"),
    ("nSplitOpusSelci", "0an.5 Opus menu top-up", "Opus selection part at n = 60", "ci", "s2"),
    ("nAoneDeepKone", A1, "F0 DeepSeek, k = 1, pick change", "value", "s3"),
    ("nAoneDeepKoneci", A1, "F0 DeepSeek, k = 1, pick change", "ci", "s3"),
    ("nAoneFlashKone", A1, "F0 Gemini 2.5 Flash, k = 1, pick change", "value", "s3"),
    ("nAoneFlashKoneci", A1, "F0 Gemini 2.5 Flash, k = 1, pick change", "ci", "s3"),
    ("nAoneProKfour", A1, "Gemini 3.1 Pro, k = 4, pick change", "value", "s3"),
    ("nAoneProKfourci", A1, "Gemini 3.1 Pro, k = 4, pick change", "ci", "s3"),
    ("nAoneProRepick", A1, "Gemini 3.1 Pro, shrinkage re-pick without the round", "value", "s3"),
    ("nAoneProRepickci", A1, "Gemini 3.1 Pro, shrinkage re-pick without the round", "ci", "s3"),
    ("nAoneProShareAfter", A1, "Gemini 3.1 Pro, re-testing share after the change, %", "value", "f1"),
    ("nAtwoSolKone", A1b, "Sol, k = 1, pick change", "value", "s3"),
    ("nAtwoSolKoneci", A1b, "Sol, k = 1, pick change", "ci", "s3"),
    ("nSolGbMenuClu", A2, "Menu minus Blind pick, cluster bootstrap by nominee", "value", "s2"),
    ("nSolGbMenuCluci", A2, "Menu minus Blind pick, cluster bootstrap by nominee", "ci", "s2"),
    ("nSolGbMenuCol", A2, "Menu minus Blind pick, FSRM collapsed to one", "value", "s2"),
    ("nSolGbMenuColci", A2, "Menu minus Blind pick, FSRM collapsed to one", "ci", "s2"),
    ("nFsrmTrue", A2, "FSRM true value", "value", "f3"),
    ("nGemSpend", R7, "Gemini spend by credit balance, $", "value", "f2"),
    ("nSolSpend", R7, "Sol recorded spend, $", "value", "f2"),
    ("nGridSelLow", NS, "grid, guessing at k = 0, selection loss, low noise", "value", "f2"),
    ("nGridSelLowci", NS, "grid, guessing at k = 0, selection loss, low noise", "ci", "f2"),
    ("nGridSelAssay", NS, "grid, guessing at k = 0, selection loss, assay noise", "value", "f2"),
    ("nGridSelAssayci", NS, "grid, guessing at k = 0, selection loss, assay noise", "ci", "f2"),
    ("nGridSelHigh", NS, "grid, guessing at k = 0, selection loss, high noise", "value", "f2"),
    ("nGridSelHighci", NS, "grid, guessing at k = 0, selection loss, high noise", "ci", "f2"),
    ("nGridLostKzero", NS, "grid, guessing at k = 0, lost slots, assay noise", "value", "f0"),
    ("nGridLostKone", NS, "grid, guessing at k = 1, lost slots, assay noise", "value", "f0"),
    ("nGridShareCvThree", NS, "grid, best scripted share at CV 0.3, %", "value", "f1"),
    ("nPhoqCross", NS, "PhoQ, first noise level where k* exceeds 0, times assay noise", "value", "f0"),
    ("nGbCross", NS, "GB1, first noise level where k* exceeds 0, times assay noise", "value", "f0"),
    ("nPhoqTimesLow", NS, "PhoQ, CV 0.3, times assay noise", "value", "f0"),
    ("nPhoqTimesHigh", NS, "PhoQ, CV 0.6, times assay noise", "value", "f0"),
    ("nGbTimesHigh", NS, "GB1, CV 0.6, times assay noise", "value", "f0"),
    ("nGbHighKone", NS, "GB1, CV 0.6, guessing at k = 1, pick", "value", "f2"),
    ("nGbHighKoneci", NS, "GB1, CV 0.6, guessing at k = 1, pick", "ci", "f2"),
    ("nGbHighKzero", NS, "GB1, CV 0.6, guessing at k = 0, pick", "value", "f2"),
    ("nGbHighKzeroci", NS, "GB1, CV 0.6, guessing at k = 0, pick", "ci", "f2"),
    ("nGridRfKone", NS, "grid, risk-free rule, assay noise, pick at k = 1", "value", "f2"),
    ("nGridRfKoneci", NS, "grid, risk-free rule, assay noise, pick at k = 1", "ci", "f2"),
    ("nGridRfKzero", NS, "grid, risk-free rule, assay noise, pick at k = 0", "value", "f2"),
    ("nGridRfKzeroci", NS, "grid, risk-free rule, assay noise, pick at k = 0", "ci", "f2"),
    ("nBandNonlostLo", SC, "paper grid, guessing at k*, share over slots not lost, %", "value", "f2"),
    ("nBandNonlostHi", SC, "paper grid, model-guided, share over slots not lost, %", "value", "f2"),
    ("nPanelcOpus", "Panel c: reasoning on, grid Blind (exploratory)", "Opus 4.7 Panel c Blind share, %", "value", "f0"),
    ("nPanelcFlash", "Panel c: reasoning on, grid Blind (exploratory)", "Gemini 2.5 Flash Panel c Blind share, %", "value", "f0"),
    ("nGbPaperBest", NS, "GB1, best scripted share at assay noise, %", "value", "f1"),
    ("nGbShareFlash", "GB1 Blind re-testing across models (descriptive)", "Gemini 2.5 Flash GB1 Blind share, %, 0an.6 control", "value", "f1"),
    ("nGbDistinctFlash", "GB1 Blind re-testing across models (descriptive)", "Gemini 2.5 Flash GB1 Blind distinct candidates, 0an.6 control", "value", "f1"),
    ("nGbShareDeep", "GB1 Blind re-testing across models (descriptive)", "DeepSeek V3.1 GB1 Blind share, %, 0an.6 control", "value", "f1"),
    ("nGbDistinctDeep", "GB1 Blind re-testing across models (descriptive)", "DeepSeek V3.1 GB1 Blind distinct candidates, 0an.6 control", "value", "f1"),
    ("nGbShareOpus", "GB1 Blind re-testing across models (descriptive)", "Opus 4.7 GB1 Blind share, %, earlier 0am control", "value", "f1"),
    ("nGbDistinctOpus", "GB1 Blind re-testing across models (descriptive)", "Opus 4.7 GB1 Blind distinct candidates, earlier 0am control", "value", "f1"),
    ("nGbShareSol", R7, "Sol GB1 Blind share, %", "value", "f1"),
    ("nGbDistinctSol", "GB1 Blind re-testing across models (descriptive)", "Sol GB1 Blind distinct candidates", "value", "f1"),
    ("nGbSharePro", R7, "Gemini GB1 Blind share, %", "value", "f1"),
    ("nGbDistinctPro", "GB1 Blind re-testing across models (descriptive)", "Gemini 3.1 Pro GB1 Blind distinct candidates", "value", "f1"),
    ("nGbExplPro", "GB1 Blind re-testing across models (descriptive)", "Gemini 3.1 Pro GB1 Blind exploration loss", "value", "f2"),
    ("nGbSelPro", "GB1 Blind re-testing across models (descriptive)", "Gemini 3.1 Pro GB1 Blind selection loss", "value", "f2"),
    ("nGbBestShare", SC, "GB1 test, best scripted share, %", "value", "f1"),
    ("nNkBestShare", SC, "NK test, best scripted share, %", "value", "f1"),
]


# A policy trained in Wellocate: the pre-registered test with cluster-bootstrap intervals, and the post-hoc
# robustness analyses.
B11A = "B11 Run A: PPO policy trained on the grid, tested on grid, GB1 and PhoQ"
B11CL = "B11 robustness analyses part 2 (post-hoc): every B11 comparison under a two-level cluster bootstrap"
B11RL = "B11 robustness analyses part 2 (post-hoc): Run A and the scripted policies on unscrambled GB1 and PhoQ"
B11ST = "B11 robustness analyses part 2 (post-hoc): stress tests of the assay model"
B11ZS = "B11 robustness analyses part 2 (post-hoc): zero-shot on held-out ruggedness and other budgets"
B11BH = "B11 robustness analyses part 2 (post-hoc): what Run A and Run B re-test, extend and nominate"
for mac, name, f in (("RandGrid", "A nk:test trained minus random", "f2"), ("RandGb", "A gb1:test trained minus random", "f2"),
                     ("RandPq", "A phoq:test trained minus random", "f2"),
                     ("InitGrid", "A nk:test trained minus initialisation", "f2"),
                     ("InitGb", "A gb1:test trained minus initialisation", "f2"),
                     ("InitPq", "A phoq:test trained minus initialisation", "f2"),
                     ("GuessGrid", "A nk:test trained minus guessing", "s2"),
                     ("BestGb", "A gb1:test trained minus guessing", "s2"),
                     ("BestPq", "A phoq:test trained minus informed", "s2"),
                     ("RandLow", "noise low, Run A minus random", "f2"), ("RandHigh", "noise high, Run A minus random", "f2"),
                     ("BRandPq", "B phoq:test trained minus random", "s2"),
                     ("LlmOpus", "grid, Run A minus Opus 4.7", "f2"), ("LlmFlash", "grid, Run A minus Gemini 2.5 Flash", "f2"),
                     ("LlmDeep", "grid, Run A minus DeepSeek V3.1", "f2"), ("LlmSol", "grid, Run A minus GPT-6.1 Sol", "f2"),
                     ("LlmPro", "grid, Run A minus Gemini 3.1 Pro", "f2")):
    MACROS += [("nPol%s" % mac, B11CL, "B11 cluster: %s" % name, "value", f),
               ("nPol%sci" % mac, B11CL, "B11 cluster: %s" % name, "ci", f)]
for mac, sp in (("RealGb", "gb1:transfer_real"), ("RealPq", "phoq:transfer_real")):
    MACROS += [("nPol%s" % mac, B11RL, "B11 real %s, Run A minus random, pick" % sp, "value", "f2"),
               ("nPol%sci" % mac, B11RL, "B11 real %s, Run A minus random, pick" % sp, "ci", "f2")]
for mac, sp, c, lab, f in (("RandBatch", "nk:test", "batch10", "Run A minus random, pick", "f2"),
                           ("RandSpike", "nk:test", "spikes", "Run A minus random, pick", "f2"),
                           ("SpikeHeavy", "nk:test", "spikes", "informed heavy minus moderate, pick", "s2"),
                           ("SpikeHeavyGuess", "nk:test", "spikes", "guessing heavy minus moderate, pick", "s2")):
    MACROS += [("nPol%s" % mac, B11ST, "B11 stress %s %s, %s" % (sp, c, lab), "value", f),
               ("nPol%sci" % mac, B11ST, "B11 stress %s %s, %s" % (sp, c, lab), "ci", f)]
for mac, st, lab, f in (("RandKtwo", "nk:test_ood_k2 15x4", "Run A minus random, pick", "s2"),
                        ("RandKthree", "nk:test_ood_k3 15x4", "Run A minus random, pick", "s2"),
                        ("RandShort", "nk:test 10x4", "Run A minus random, pick", "f2"),
                        ("RandPlate", "nk:test 4x24", "Run A minus random, pick", "f2"),
                        ("BestPlate", "nk:test 4x24", "Run A minus the best scripted policy, pick", "s2")):
    MACROS += [("nPol%s" % mac, B11ZS, "B11 zero-shot %s, %s" % (st, lab), "value", f),
               ("nPol%sci" % mac, B11ZS, "B11 zero-shot %s, %s" % (st, lab), "ci", f)]
B11EN = "B11 robustness analyses part 2 (post-hoc): Run B with a larger exploration bonus"
B11RP = "B11 robustness analyses part 2 (post-hoc): Run A replication, seeds 3 to 7"
MACROS += [("nPolEntRandPq", B11EN, "B11 Run B ablation phoq:test, trained minus random, pick", "value", "f2"),
           ("nPolEntRandPqci", B11EN, "B11 Run B ablation phoq:test, trained minus random, pick", "ci", "f2"),
           ("nPolEntSharePq", B11EN, "B11 Run B ablation phoq:test, trained re-testing share, %", "value", "f1"),
           ("nPolEntOrderH", B11EN, "B11 Run B ablation, end of training, order_entropy", "value", "f1"),
           ("nPolBOrderH", B11EN, "B11 registered Run B, end of training, order_entropy", "value", "f1"),
           ("nPolRepRandGrid", B11RP, "B11 Run A seeds 3-7 nk:test, trained minus random, pick", "value", "f2"),
           ("nPolRepRandGridci", B11RP, "B11 Run A seeds 3-7 nk:test, trained minus random, pick", "ci", "f2"),
           ("nPolRepGuessGrid", B11RP, "B11 Run A seeds 3-7 nk:test, trained minus guessing, pick", "value", "s2"),
           ("nPolRepGuessGridci", B11RP, "B11 Run A seeds 3-7 nk:test, trained minus guessing, pick", "ci", "s2")]
MACROS += [("nPolShare", B11A, "B11 A nk:test, trained re-testing share, %", "value", "f1"),
           ("nPolParentTop", B11BH, "B11 behaviour A nk:test, mean over seeds, parent_top1", "value", "pct0"),
           ("nPolParentTopThree", B11BH, "B11 behaviour A nk:test, mean over seeds, parent_top3", "value", "pct0"),
           ("nPolLeadRetest", B11BH, "B11 behaviour A nk:test, mean over seeds, top3_retests_pct_of_slots", "value", "f1"),
           ("nPolRetry", B11BH, "B11 behaviour A nk:test, mean over seeds, retry_after_failure", "value", "pct0"),
           ("nPolSameRound", B11BH, "B11 behaviour A nk:test, mean over seeds, same_round_replicate", "value", "pct0")]
# Section 2's scripted rules on the grid, GB1's share above its viability threshold, and Figure 3(b)'s counts.
LSH = "landscape shares: GB1 and PhoQ viable shares, the grid slice's neighbours"
MACROS += [("nGuessShare", "scripted yardsticks", "guessing share at k*, %", "value", "f2"),
           ("nGuessPick", "scripted yardsticks", "guessing policy pick at k*, two decimals", "value", "f2"),
           ("nInformedPick", "scripted yardsticks", "informed policy pick at k*", "value", "f2"),
           ("nMgPick", MG, "pick at k = 1 with confirmation", "value", "f2"),
           ("nGbViable", LSH, "GB1 share above the viability threshold, %", "value", "f1"),
           ("nSliceNbrs", LSH, "grid slice: the best candidate's one-letter neighbours shown", "value", "f0"),
           ("nSliceNbrsViable", LSH, "grid slice: of those, viable", "value", "f0"),
           ("nSliceViablePct", LSH, "grid slice: viable share of its cells, %", "value", "f0")]
# Figure 3(c), the slice through the start. Its best candidate's sequence is in results/landscape_shares.json.
MACROS += [("nStartSliceViable", LSH, "start slice: viable cells", "value", "f0"),
           ("nStartSliceCells", LSH, "start slice: cells", "value", "f0"),
           ("nStartSliceViablePct", LSH, "start slice: viable share of its cells, %", "value", "f0"),
           ("nStartRowCol", LSH, "start slice: the start's row and column, cells", "value", "f0"),
           ("nStartRowColViable", LSH, "start slice: the start's row and column, viable", "value", "f0"),
           ("nStartSliceBest", LSH, "start slice: its best candidate's value", "value", "f3"),
           ("nStartOffSlice", LSH, "the start's neighbours off its slice", "value", "f0"),
           ("nStartOffSliceViable", LSH, "the start's viable neighbours off its slice", "value", "f0")]
# Post-hoc start check: the scripted rules from 50 random viable starts, read from
# results/start_robustness_summary.json.
SRB = "start check: the scripted rules from 50 random viable starts"
MACROS += [("nStartsRandom", SRB, "random starts per landscape", "value", "f0"),
           ("nStartGuessShareMinGrid", SRB, "grid, guessing, re-testing share at each start's k*, min, %", "value", "f1"),
           ("nStartGuessShareMaxGrid", SRB, "grid, guessing, re-testing share at each start's k*, max, %", "value", "f1"),
           ("nStartMgShareMinGrid", SRB, "grid, model-guided, re-testing share at the paper start's k*, min, %", "value", "f1"),
           ("nStartMgShareMaxGrid", SRB, "grid, model-guided, re-testing share at the paper start's k*, max, %", "value", "f1"),
           ("nStartMgPickLostMaxGrid", SRB, "grid, model-guided, pick lost at the paper start's k*, max", "value", "f3"),
           ("nStartMgPickLostMedGrid", SRB, "grid, model-guided, pick lost at the paper start's k*, median", "value", "f3")]
for short, lab in (("Grid", "grid"), ("Gb", "scrambled GB1"), ("Pq", "scrambled PhoQ")):
    for rshort, rule in (("Guess", "guessing"), ("Inf", "informed"), ("Mg", "model-guided")):
        MACROS += [("nStartSameK%s%s" % (short, rshort), SRB, "%s, %s, random starts with the paper start's k*" % (lab, rule),
                    "value", "f0")]
# How tightly each landscape's ten best candidates are bunched, in noise SDs at assay noise (Section 4).
TSP = "top spread: the best candidates in units of assay noise"
MACROS += [("nTopSpreadGrid", TSP, "grid, best minus 10th best, noise SDs", "value", "f2"),
           ("nTopSpreadGb", TSP, "GB1, best minus 10th best, noise SDs", "value", "f2"),
           ("nTopSpreadPq", TSP, "PhoQ, best minus 10th best, noise SDs", "value", "f2")]
# Whether good candidates cluster.
NBC = "neighbour clustering: viable neighbours of viable, good and start candidates"
MACROS += [("nNbrPer", NBC, "one-letter neighbours per candidate", "value", "f0")]
for short, lab in (("Grid", "grid"), ("Gb", "scrambled GB1"), ("Pq", "scrambled PhoQ")):
    MACROS += [("nViablePct%s" % short, NBC, "%s, viable share, %%" % lab, "value", "f2"),
               ("nNbrViable%s" % short, NBC, "%s, viable neighbours of viable candidates, pooled, %%" % lab, "value", "f1"),
               ("nNbrViableTop%s" % short, NBC, "%s, viable neighbours of the top 10%%, pooled, %%" % lab, "value", "f1"),
               ("nStartNbrs%s" % short, NBC, "%s, the start's viable neighbours" % lab, "value", "f0"),
               ("nStartNbrsPct%s" % short, NBC, "%s, the start's viable neighbours, %%" % lab, "value", "f1")]


def fmt(v, f):
    """f0..f3: fixed decimals; s1..s3: fixed decimals with a sign; pct0: a fraction as a whole percentage;
    thou: a whole number with a LaTeX thousands separator. A minus sign is set as $-$."""
    if f == "pct0":
        return "%.0f" % (100 * v)
    if f == "thou":
        return "{:,.0f}".format(v).replace(",", "{,}")
    d = int(f[1])
    s = ("%." + str(d) + "f") % abs(v)
    if f[0] == "s":
        return ("$-$" if v < 0 and float(s) != 0 else "$+$") + s
    return ("$-$" if v < 0 and float(s) != 0 else "") + s


def lookup(rows, rid, name):
    if rid not in rows:
        raise SystemExit("REFUSED: findings row %r does not exist" % rid)
    heads = {h["name"]: h for h in rows[rid]["headline"]}
    if name not in heads:
        raise SystemExit("REFUSED: findings row %r has no headline %r" % (rid, name))
    return heads[name]


def render():
    rows = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "results", "findings.json")))["rows"]}
    lines = ["% Generated by scripts/make_paper_numbers.py from results/findings.json. Do not edit by hand;",
             "% scripts/verify_paper_numbers.py checks findings.json against its sources, regenerates this file and",
             "% fails on any difference."]
    for macro, rid, name, part, f in MACROS:
        h = lookup(rows, rid, name)
        if part == "ci":
            if not h.get("ci"):
                raise SystemExit("REFUSED: %r / %r has no interval" % (rid, name))
            text = "[%s, %s]" % (fmt(h["ci"][0], f), fmt(h["ci"][1], f))
        else:
            text = fmt(h["value"], f)
        lines.append("\\newcommand{\\%s}{%s}%% %s | %s" % (macro, text, rid, name.replace("%", "\\%")))
    return "\n".join(lines) + "\n"


def macro_list():
    """Each macro's name and rendered value, one per line, for an author choosing names (--list)."""
    out = []
    for line in render().splitlines():
        m = re.match(r"\\newcommand\{\\(\w+)\}\{(.*)\}%", line)
        if m:
            out.append("%-24s %s" % ("\\" + m.group(1), m.group(2)))
    return "\n".join(out) + "\n"


def main(argv=None):
    # Writes paper/ only with --write-paper (scripts/paper_write.py); any other argument is refused.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import paper_write as PW
    return PW.run(__file__, DST, render, argv, lister=macro_list)


if __name__ == "__main__":
    sys.exit(main())
