#!/usr/bin/env python3
"""Generate results/PAPER_CANDIDATES.md, the ranked main findings, from results/findings.json.

The ranking, claims, placement and figure for each finding are set here; every number comes from findings.json. --check regenerates the file in memory and fails if the committed one differs or if a
row or headline it quotes no longer exists; tests/test_findings.py runs it.

Usage: python3 scripts/paper_candidates.py [--check]
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
OUT = os.path.join(RES, "PAPER_CANDIDATES.md")

# (claim, [(row id, [headline names])], placement, figure or table), ranked by how much each carries the story.
CANDIDATES = [
    ("Current models misallocate measurements in both directions: the older three re-test most of their budget, the "
     "newest re-tests far less than a simple rule and often picks on a single reading.",
     [("headline figure data: five models on the grid", ["Gemini 2.5 Flash, re-testing share, %", "DeepSeek V3.1, re-testing share, %", "Opus 4.7, re-testing share, %",
              "GPT-6.1 Sol, re-testing share, %", "Gemini 3.1 Pro, re-testing share, %"]),
      ("0an.7 main run", ["Gemini nominees with one reading, grid"]),
      ("scripted yardsticks", ["guessing share at k*, %"]),
      ("0an.4 model-guided scripted reference", ["re-testing share at that best, %"])],
     "main text", "Fig. 1 (headline, all five models)"),
    ("On the grid no model's final pick beats a one-line guessing rule.",
     [("headline figure data: five models on the grid", ["Opus 4.7, final pick", "Gemini 2.5 Flash, final pick", "DeepSeek V3.1, final pick", "GPT-6.1 Sol, final pick",
              "Gemini 3.1 Pro, final pick"]),
      ("scripted yardsticks", ["guessing policy pick at k*", "informed policy pick at k*"])],
     "main text", "Fig. 1 (right panel)"),
    ("The loss comes from opposite places: older models lose through exploration, the newest through selection.",
     [("headline figure data: five models on the grid", ["Gemini 2.5 Flash, exploration loss", "Gemini 2.5 Flash, selection loss", "Gemini 3.1 Pro, exploration loss",
              "Gemini 3.1 Pro, selection loss"])],
     "main text", "Fig. 3"),
    ("A ledger of readings or a note on the landscape's structure leaves re-testing unchanged; a list of untried "
     "candidates cuts it in every older model.",
     [("0an panel (F0, F1, F2)", ["F1 Opus share change, points", "F2 Gemini share change, points", "F2 DeepSeek share change, points"]),
      ("0an.3 F5 structure", ["F5 Opus share change, points"]),
      ("0an.5 Opus menu top-up", ["Opus share change at n = 60, points"])],
     "main text", "Table 1"),
    ("On real protein data the list lifts the older models' picks; the newest models barely move.",
     [("0an.6 Menu on scrambled GB1", ["Gemini pick change", "DeepSeek pick change"]),
      ("0an.7 main run", ["Sol Menu minus Blind on GB1, share, points", "Gemini Menu minus Blind on GB1, share, points",
                          "Gemini Menu minus Blind on GB1, pick"])],
     "main text", "Fig. 4 (a, b); Table 1"),
    ("A final confirmation round, simulated on the agents' own campaigns, recovers about a quarter of Gemini 3.1 "
     "Pro's selection loss and nothing for Sol.",
     [("A1 counterfactual confirmation round", ["Gemini 3.1 Pro, k = 3, pick change", "Sol, k = 1, pick change"]),
      ("0an.7 main run", ["Gemini minus F0 Gemini 2.5 Flash, grid selection shortfall"])],
     "main text", "Fig. 4 (c)"),
    ("The right re-testing share depends on the landscape and the noise: one re-test a round on the grid, almost none "
     "on GB1 and PhoQ until noise is four to eight times the assay's.",
     [("Wellocate noise sweep (B9, B10)", ["grid, guessing at k = 0, selection loss, low noise",
                                           "grid, guessing at k = 0, selection loss, high noise",
                                           "PhoQ, first noise level where k* exceeds 0, times assay noise",
                                           "GB1, first noise level where k* exceeds 0, times assay noise"])],
     "main text", "Fig. 5"),
    ("Wellocate reproduces the paper's references exactly through its own interface.",
     [("Wellocate baseline scorecard (B3, B4)", ["paper grid, guessing at k*, pick", "paper grid, informed at k*, pick",
                                                 "episodes per second, one core"])],
     "main text", "Table 2"),
    ("Older models keep re-testing when every reading is exact.",
     [("zero-noise panel", ["lowest zero-noise level, %", "highest zero-noise level, %"])],
     "appendix", "Fig. zero-noise (appendix)"),
    ("Sol's lead over the guessing rule on GB1 does not survive grouping by nominee.",
     [("A2 Sol GB1 Blind, one nominee", ["pick minus guessing, as registered", "pick minus guessing, cluster bootstrap by nominee"])],
     "appendix", "Appendix E"),
]

FIGURES = [
    ("Fig. 1 (headline)", "Re-testing share for all five models against the band of scripted references, with the final "
     "pick beside it against the guessing and informed rules.", "headline figure data; scripted yardsticks; 0an.4"),
    ("Fig. 2", "The environment with the lab counterpart of each part: wells, assay, failed assay, the variant taken "
     "forward.", "design constants"),
    ("Fig. 3", "Exploration loss against selection loss per model, with the guessing rule: the two failure directions.",
     "headline figure data; Wellocate scorecard"),
    ("Fig. 4", "The fixes: the Menu on GB1 for old and new models, and the simulated confirmation round.",
     "0an.6; 0an.7; A1"),
    ("Fig. 5", "The guessing rule's pick against re-tests per round at five noise levels, per track, under both rejection "
     "rules.", "Wellocate noise sweep"),
]


def fmt(h):
    v = "%g" % h["value"]
    return "%s %s%s" % (h["name"], v, " [%g, %g]" % tuple(h["ci"]) if h.get("ci") else "")


def build():
    rows = {r["id"]: r for r in json.load(open(os.path.join(RES, "findings.json")))["rows"]}
    L = ["# Paper candidates", "",
         "Generated by `python3 scripts/paper_candidates.py` from `results/findings.json`. The ranking, claims,",
         "placement and figures are editorial; every number is read from the findings rows, which read the analysis",
         "files. Intervals are 95%. No paper text has been edited.", "",
         "| rank | claim | headline numbers | findings row | placement | figure or table |", "|---|---|---|---|---|---|"]
    for i, (claim, refs, place, fig) in enumerate(CANDIDATES, 1):
        nums, ids = [], []
        for rid, names in refs:
            if rid not in rows:
                raise SystemExit("REFUSED: findings row %r does not exist" % rid)
            heads = {h["name"]: h for h in rows[rid]["headline"]}
            for n in names:
                if n not in heads:
                    raise SystemExit("REFUSED: row %r has no headline %r" % (rid, n))
                nums.append(fmt(heads[n]))
            ids.append(rid)
        L.append("| %d | %s | %s | %s | %s | %s |" % (i, claim, "; ".join(nums), "; ".join(ids), place, fig))
    L += ["", "## Proposed figures", ""]
    for name, what, src in FIGURES:
        L.append("- **%s.** %s Data: %s." % (name, what, src))
    return "\n".join(L) + "\n"


def main():
    text = build()
    if "--check" in sys.argv:
        same = os.path.exists(OUT) and open(OUT).read() == text
        print("paper candidates: %s" % ("match findings.json" if same else "DIFFER from findings.json; regenerate"))
        return 0 if same else 1
    open(OUT, "w").write(text)
    print("wrote %s (%d candidates, %d figures)" % (os.path.relpath(OUT, ROOT), len(CANDIDATES), len(FIGURES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
