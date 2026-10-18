# Panel (c) check: reasoning effort medium, after the finish_reason reruns

Regenerate with `python3 scripts/panelc_check.py`. Every figure is recomputed from
`results/grid_panelc_campaigns.jsonl`, `results/grid_stage1_campaigns.jsonl` and the panel's call
archive. Nothing is read from a table in `results/analysis_final/`.

Panel (c) holds **160 campaigns** in 4 cells and **5852 archived calls**.
Finish reasons over every call in the panel: **stop** 5838, **length** 14.
No call reports `finish_reason == "error"`, which the repair now raises on.

## Per cell

`pairs` is seeds present in both panel (c) and stage 1. `0ag` is campaigns excluded because the
nomination did not parse and the harness substituted its own averaging rule. `used` is what every
paired figure below is computed on.

| condition | model | panel n | stage-1 n | pairs | 0ag | used | 0ag finish reasons |
|---|---|---:|---:|---:|---:|---:|---|
| Blind | claude-opus-4.7 | 40 | 40 | 40 | 0 | 40 | none |
| Blind | gemini-2.5-flash | 40 | 40 | 40 | 5 | 35 | length 4, stop 1 |
| Mechanism | claude-opus-4.7 | 40 | 40 | 40 | 0 | 40 | none |
| Mechanism | gemini-2.5-flash | 40 | 40 | 40 | 4 | 36 | length 4 |

### Primary outcome, paired by seed

Nominated true fitness, panel (c) minus stage 1. Interval is the paired normal interval. `wild p` is
the studentised wild cluster bootstrap over seeds with 20000 draws, and Holm runs across these four rows
only.

| condition | model | used | diff | SE | 95% CI | wild p | Holm p | reject at .05 |
|---|---|---:|---:|---:|---|---:|---:|---|
| Blind | claude-opus-4.7 | 40 | -0.0987 | 0.0438 | [-0.1845, -0.0129] | 0.03135 | 0.03135 | YES |
| Blind | gemini-2.5-flash | 35 | -0.2630 | 0.0489 | [-0.3588, -0.1672] | 0.00005 | 0.00020 | YES |
| Mechanism | claude-opus-4.7 | 40 | -0.2016 | 0.0694 | [-0.3376, -0.0655] | 0.00660 | 0.01320 | YES |
| Mechanism | gemini-2.5-flash | 36 | -0.2241 | 0.0557 | [-0.3332, -0.1149] | 0.00015 | 0.00045 | YES |

### The mechanism: replication share and distinct variants, same pairs

Both are paired on the same seeds as the primary outcome. Replication share is over slots used.

| condition | model | repl share panel | repl share stage 1 | delta (SE) | distinct panel | distinct stage 1 | delta (SE) |
|---|---|---:|---:|---|---:|---:|---|
| Blind | claude-opus-4.7 | 69.0% | 76.5% | -7.46 pp (1.40) | 14.00 | 10.30 | +3.70 (0.64) |
| Blind | gemini-2.5-flash | 81.8% | 94.2% | -12.38 pp (1.27) | 10.09 | 2.97 | +7.11 (0.63) |
| Mechanism | claude-opus-4.7 | 72.7% | 82.5% | -9.88 pp (0.96) | 12.15 | 8.40 | +3.75 (0.56) |
| Mechanism | gemini-2.5-flash | 86.0% | 95.7% | -9.68 pp (0.79) | 7.42 | 2.58 | +4.83 (0.41) |

### 0ag sensitivity: the same comparison with all nine excluded campaigns put back

`summary.json`'s `contrasts_with_fallbacks` covers the confirmatory family, and panel (c) has no
confirmatory contrast of its own, so the sensitivity for this comparison is computed here. Every
cell uses all 40 paired seeds. In a kept campaign the nomination is whatever `best_by_mean()`
returned, which is the Decision-rule instruction applied by the harness.

| condition | model | n | diff | SE | 95% CI | wild p | Holm p | reject at .05 | primary diff |
|---|---|---:|---:|---:|---|---:|---:|---|---:|
| Blind | claude-opus-4.7 | 40 | -0.0987 | 0.0438 | [-0.1845, -0.0129] | 0.03135 | 0.03135 | YES | -0.0987 |
| Blind | gemini-2.5-flash | 40 | -0.2528 | 0.0459 | [-0.3427, -0.1628] | 0.00005 | 0.00020 | YES | -0.2630 |
| Mechanism | claude-opus-4.7 | 40 | -0.2016 | 0.0694 | [-0.3376, -0.0655] | 0.00660 | 0.01320 | YES | -0.2016 |
| Mechanism | gemini-2.5-flash | 40 | -0.2338 | 0.0515 | [-0.3347, -0.1329] | 0.00005 | 0.00020 | YES | -0.2241 |

### What the extra exploration cost, and where the outcome went

Reasoning lowered the replication share and raised the distinct-variant count in every cell, and the
primary outcome still fell. Three quantities separate the ways that can happen. Best measured is the
true value of the best candidate the agent actually measured, so a fall means the wider search
returned worse candidates. Selection shortfall is best measured minus nominated, so a rise means the
agent held a better reading and did not nominate it. Rejections and lost slots say what the wider
search cost in budget.

| condition | model | selection shortfall panel | stage 1 | delta (SE) | rejections delta (SE) | lost slots delta |
|---|---|---:|---:|---|---|---:|
| Blind | claude-opus-4.7 | 0.1096 | 0.0710 | +0.0386 (0.0235) | +7.38 (1.57) | +0.62 |
| Blind | gemini-2.5-flash | 0.1041 | 0.0189 | +0.0852 (0.0309) | -0.86 (1.62) | +0.11 |
| Mechanism | claude-opus-4.7 | 0.0889 | 0.0818 | +0.0071 (0.0270) | +8.03 (1.12) | +1.40 |
| Mechanism | gemini-2.5-flash | 0.0698 | 0.0074 | +0.0624 (0.0213) | +1.56 (0.88) | +0.69 |

### The excluded seeds, named

- Blind / gemini-2.5-flash: 300021, 300023, 300027, 300034, 300035
- Mechanism / gemini-2.5-flash: 300018, 300022, 300023, 300039

A sensitivity keeping the 0ag campaigns is in `results/analysis_final/panelc/summary.json` under
`contrasts_with_fallbacks`.

### What this file does not settle

The arithmetic above is stated without a reading. Three things it cannot decide on its own. The
comparison is unpaired in treatment even though it is paired in seed, because stage 1 ran at a
different time with a different token budget. Panel (c) covers two of the five conditions, so no
ladder-wide claim follows from it. And the two gemini cells drop 5 and 4 campaigns under 0ag, which
the sensitivity addresses but does not remove.

