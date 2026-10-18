# Results log

Every measurement on this project, with the script that produced it and where the output lives.
**Append here as part of any run, never afterwards.** The paper is written from this file.

Rule: a result that exists only in a chat transcript or in `/tmp` does not exist. On
2026-09-27 an audit found nine files holding headline results living only in `/tmp`, including
the ablation ladder that located Step 2's entire finding, and the seed-stability script that
backed CHALLENGES C2 had never been saved at all and had to be rewritten from scratch. That is
the same provenance failure this project keeps finding in its own inputs.


> **RESOLVED 2026-09-27. THE CLOCK RESULT IS VERIFIED, see rows 47 and 50.** The re-parse audit
> (`scripts/reparse_audit.py`, `results/step8_reparse_audit.json`, committed at 1048126) shows every
> pre-fix experiment's crossing round holding within its pooled standard error, largest shift 0.05 to
> 0.10 against standard errors of 0.40 to 1.26, with old-versus-new parser disagreement of 0 to 1.8%
> on the GB1 logs. The bug was specific to the NK landscape. The flag below is kept unedited because
> the reasoning is the record of how the check was specified before its result was known.
>
> **UNVERIFIED PENDING RE-PARSE, flagged 2026-09-27.** Every behavioural number below that was
> measured before the tiered-parser fix may be affected. The old parser accepted `:` as a separator,
> so a model's analysis preamble matched as proposals, and the substituted sequences are mostly
> ALREADY-MEASURED variants. That inflates the replication fraction, and inflates it MORE as the
> history grows, which is exactly the dependent variable of the clock and crossing-round results.
> The GB1 pilot, the length experiment (10/15/30) and the slots experiment (2/4/8) all ran on the old
> parser. **The turn-counter and crossing-round results are UNVERIFIED** until
> `scripts/reparse_audit.py` reports the old-versus-new comparison. If the crossing rounds hold
> within their standard errors the clock result stands; if not, the length experiment is re-run on NK.

| # | Date | What | Script | Output | Headline |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-09-26 | Data download, hash pinning | `scripts/download_data.py` | README table | PhoQ 1,857,322 B, GB1 2,939,733 B; two SHA256 recorded |
| 2 | 2026-09-26 | Ten data assertions | `tests/test_landscapes.py` | test output | 160,000 rows each; pools 11,146 and 11,522 |
| 3 | 2026-09-27 | Reference table reproduction | `spec/thresh.py` verbatim | CHALLENGES C1 | All 24 cells exact to 3 dp, at `fail=0.15` |
| 4 | 2026-09-27 | Seed-base stability | `scripts/seed_stability.py` | `results/step2_seed_stability.txt` | Cells stable 0-4 SE; argmax FLIPS at base 4000 on PhoQ r4.0 and GB1 r2.0 |
| 5 | 2026-09-27 | **Ablation ladder** | `scripts/ablation_ladder.py` | CHALLENGES C4 | Exploration scope is the ONLY deviation that matters; it moves cells 26-88% and kills PhoQ r2.0 |
| 6 | 2026-09-27 | Falsifications F1-F6 | `scripts/falsify.py` | `results/step2_falsifications.txt` | F1 mechanism survives; F3 scoped to high noise; F6 sigma unit circular |
| 7 | 2026-09-27 | Main + reproduction tables | `scripts/main_tables.py` | `results/step2_main_tables.txt` | N=5000: r2.0 n.s. on both; r4.0 +7.50% and +11.99%, both significant |
| 8 | 2026-09-27 | Mutation tests | `scripts/mutation_test.py`, `..._focused.py` | CHALLENGES C11, C15 | 11 of 12 caught; survivor hangs, covered structurally |
| 9 | 2026-09-27 | R3 dead-fraction denominators | inline, see below | this file | Four distinct quantities: 68.1 / 93.0 / 62.3 / 93.3 on PhoQ |
| 10 | 2026-09-27 | R1, R2 reconciliations | `scripts/reconcile.py` | `results/step3_reconciliations.txt` | R1 reconciled at 0.98 SE; R2 pure sample size |
| 11 | 2026-09-27 | Screen endpoints | `scripts/budget_control.py` | `results/step3_budget_control.txt` | q=1 recovers pool-restricted, q=0 recovers verbatim thresh.py, 0.0-2.3 SE, argmax agrees 5/6 |
| 12 | 2026-09-27 | **BUDGET CONTROL (decisive)** | `scripts/budget_control.py` | `results/step3_budget_control.txt` | **NEGATIVE.** Screen precision acts only through effective budget. At r2.0 the effect inverts (k=0, P=1.00); at r4.0 it survives but is flat in q (GB1 +11.1% at every q, P=1.00) |

## Standing numbers, with provenance

These are the numbers any draft may quote. Anything not here needs a row added above first.

### The landscapes

| | PhoQ | GB1 | source |
| --- | --- | --- | --- |
| rows | 160,000 | 160,000 | result 2 |
| pool, > 1.0 and > 0.1 | 11,146 (6.97%) | 11,522 (7.20%) | result 2 |
| global pool max | 133.594 | 8.762 | result 2 |
| pool median | 6.689 | 0.509 | result 9 |
| exact zeros | 108,989 (68.1%) | 40,116 (25.1%) | result 2 |

### The dead fraction, four different quantities (result 9)

| definition | PhoQ | GB1 |
| --- | --- | --- |
| (a) exact zeros / 160,000 | 68.1% | 25.1% |
| (b) below viability threshold / 160,000 | 93.0% | 92.8% |
| (c) non-viable in a VIABLE sequence's 76-shell | **62.3%** | **53.8%** |
| (d) non-viable in an ARBITRARY sequence's 76-shell | 93.3% | 93.1% |

**The paper carries (c).** Exploration walks the shell of a champion, which is viable by
construction, so (c) is the rate a campaign faces. (b) and (d) agree because (b) is just the
arbitrary-sequence rate; they overstate the difficulty by 1.5x on PhoQ because they average
over a region the campaign never enters, and viability is spatially correlated (Hamming-1
autocorrelation 0.264 on PhoQ, 0.403 on GB1).

**This matters for a claim already in the decisions log.** Its Gate 2 justification reads "93%
of neighbours are dead". That is quantity (b)/(d), the arbitrary-sequence rate, applied to a
sentence about exploring a champion's neighbourhood, where the correct figure is (c) = 62.3%.
The Gate 2 conclusion may still hold; its stated reason uses the wrong denominator.

### Sigma units (result 6, F6)

| calibrating policy | PhoQ | GB1 |
| --- | --- | --- |
| random from pool | **5.807** | **0.557** |
| greedy k=0, pool-restricted | 4.865 | 0.428 |
| greedy k=1, pool-restricted | 5.581 | 0.388 |
| greedy k=0, unrestricted | 4.156 | 0.435 |
| *inherited (4.24 / 0.42)* | *matches unrestricted greedy* | |

The inherited unit is CIRCULAR: calibrated under the policy being judged, and under the
exploration rule BUILD_SPEC forbids. No final number may be labelled in the inherited unit.

### Gate 2, from the decisions log (not independently reproduced)

PhoQ: free proposal 30.5, random sampling 37.6, pool-restricted 41.6 (+11% over random).
GB1: pool-restricted 6.33 (+31%). `gate2.py` is absent, so these are quoted, not verified.

| 13 | 2026-09-27 | **STEP 4.0 ANCHOR GATE (decisive)** | `scripts/anchor_noise.py` | `results/step4_anchor.txt` | **FAILS.** Real GB1 sits at ratio 0.32-0.87 from published depth and r=0.97. Ratio 4.0 needs 6-12x more noise |
| 14 | 2026-09-27 | Pool-threshold sensitivity of the unit | inline, see below | this file | A tighter pool RAISES the PhoQ unit (6.26 to 12.07), halving PhoQ ratios. GB1 unit insensitive (0.52-0.60) |

| 15 | 2026-09-27 | **ORDER-STATISTICS GATE** | `scripts/order_stats_gate.py` | `results/step4_order_stats.txt` | Premise REFUTED: adjacent gaps GROW toward the top, 380x on GB1 and 3,280x on PhoQ. Effective ratio FALLS on convergence (0.58 to 0.51). Exposes a 33x fork in the unit definition |

| 16 | 2026-09-27 | Step 5 pilot, Opus 4.7 | `scripts/pilot.py` | `results/pilot_opus47.txt`, `..._calls.jsonl` | 368 calls, $2.44. Round-1 global-max proposal in 11 of 20 campaigns. Replication 49-74%, slope nearly flat |
| 17 | 2026-09-27 | **COLD RECALL PROBE** | `scripts/recall_probe.py` | `results/recall_probe.jsonl` | 10 calls, $0.11. **GB1 contaminated in 3 of 5 models; PhoQ clean in all 5** |
| 18 | 2026-09-27 | **THE MARGIN CRITERION WAS NEVER MEASURED.** `_shrinkage_nominate` answered an unusable sigma with `best_by_mean()`, and every multiplicative-noise caller passes the scalar `sigma=0.0` | `repdef/campaign.py`, `tests/test_shrinkage_actually_runs.py` | `results/step6_mutation_core.txt` | Every margin ever labelled `shrinkage - max-single` was `mean - max-single`, **including GB1's reference**. Fixed with a callable sigma derived from the oracle's own formula; the fallback is now `UnusableSigma`. 8 of 8 core mutants caught |
| 19 | 2026-09-27 | **THE VERDICTS SWAP** once the estimator runs, 7 distributions, n=1500 | `scripts/nk_confirm.py` (part 1) | `results/step6_nk_confirm.txt/.json` | **NK uniform +0.0317, 5.7 SE, PASS** (was 0.1 SE fail). **NK exponential +0.0051, 1.2 SE, fail** (was the chosen 4.4 SE winner). GB1 reference +0.0144, 4.6 SE. 6 of 7 pass, so **tail weight is not the discriminator** and the heavy-tail story was an artifact |
| 20 | 2026-09-27 | **HELD-OUT margin** for uniform NK on disjoint seeds | `scripts/nk_confirm.py` (part 2) | same | **+0.0329 +- 0.0057, 5.7 SE**, 4.6 SE after the 1.25x overdispersion. Threshold 3 SE was committed before the number existed. Held-out is slightly LARGER than selection, which is what no selection bias looks like. Uniform is the ORIGINAL pre-registered generator, so there is no searched family to discount |
| 20b | 2026-09-27 | **EFFECT SIZE, not only significance** | same | same | margin/sigma(champion): **uniform NK 0.055 vs GB1 0.036**. The gap band FAILS at 0.22 against the required 0.5-1.5, and the argument behind the lower bound is refuted by this measurement |
| 21b | 2026-09-27 | **NEUTRALITY**, with a malformed criterion corrected on mathematical grounds | `scripts/nk_confirm.py` (part 3) | same | With no replication, n is constant so the shrinkage posterior mean is a strictly increasing affine function of the single reading and CANNOT move an argmax: a k=0 margin is impossible for every landscape. The 3 replicating baselines pass at 6.8, 6.1, 8.8 SE |
| 21 | 2026-09-27 | **POWER on the margin**, overdispersion-inflated | `scripts/nk_confirm.py` (part 4) | same | Sized on the measured 1.25x across-seed sd, which is 1.56x on campaign count |
| 22 | 2026-09-27 | **PHOQ ROUND-1 ENRICHMENT DIAGNOSTIC** (the test cold recall does not replace) | `scripts/phoq_enrichment.py` | `results/step6_phoq_enrichment.json`, `step6_phoq_round1_calls.jsonl` | **PhoQ CLEAN: 0 of 20 campaigns name TEMH, against GB1's 11 of 20 under the identical one-ask rule.** $0.087. GB1's 1,584x is robust to the re-ask question: all 20 first asks were 4-slot |
| 23 | 2026-09-27 | **POWERED round-1 prior diagnostics**, because 0 of 20 is a weak bound | `scripts/round1_prior_diagnostics.py` | `results/step6_round1_prior_diagnostics.json` | **Mean fitness percentile 0.714 GB1 vs 0.414 PhoQ, diff +0.300 +- 0.057, 5.3 SE.** PhoQ sits BELOW chance. 0/20 alone admits enrichment up to 388x at 95%, so the argmax indicator is not what licenses PhoQ. MEAN Hamming (1.77 vs 1.64) separates NOTHING and an earlier draft of mine claimed it did |
| 24 | 2026-09-27 | **TEMPERATURE 0 IS NOT DETERMINISTIC** on this provider | `scripts/temperature_zero_is_not_deterministic.py` | `results/step6_temperature_zero_determinism.json` | Pairwise agreement 0.265 on byte-identical prompts; 3 of 4 repeated prompts returned different proposal sets. `llm.py`'s claim that temperature 0 excludes sampling noise was FALSE and is corrected where it lives |
| 25 | 2026-09-27 | **THE TWO INTERVENTIONS BUILT**: aggregated history, decision rule | `repdef/prompts.py`, `tests/test_interventions_are_clean.py` | `results/step6_mutation_interventions.txt` | 20 tests, **21 of 21 mutants caught**. Two gaps found by the mutants and not by me: an abstract landscape keeping the amino-acid alphabet, and one keeping a real GB1 sequence as its reference |
| 26b | 2026-09-27 | **A CONCURRENT MUTATION RUN DESTROYED A FIX AND THE NEXT EXPERIMENT REPORTED FROM REVERTED CODE** | `repdef/mutate.py`, `scripts/mutation_test.py` | `results/step6_mutation_core.txt` | The old harness snapshotted every file ONCE at import and restored from that after each mutant, so a fix written while it ran was overwritten silently. It also crashed on a 600s timeout leaving a mutant in the working tree. Now: per-mutant snapshot, `ConcurrentEdit` refusal, a hang recorded as its own outcome, and one implementation instead of two. `scripts/nk_confirm.py` gained an ESTIMATOR CANARY that aborts unless shrinkage is provably live |
| 26c | 2026-09-27 | **AN EQUIVALENT MUTANT had been reported as MISSED** | `scripts/mutation_test.py` | same | Removing the slot-budget break is behaviourally identical, verified over 40 configurations, because `rounds*slots == slots_total` exactly makes the break unreachable. "No test catches this" and "there is nothing to catch" are different states; reporting the second as the first sends someone to write a test that cannot exist. Replaced with a mutant that genuinely overspends, and the new budget test catches it |
| 26 | 2026-09-27 | **THE MUTATION HARNESS WAS BROKEN** and it certifies every other test | `repdef/mutate.py`, `tests/test_the_mutation_harness_is_not_fooled.py` | n/a, 6 tests | Apple's Python sets `sys.pycache_prefix`, so bytecode lives OUTSIDE the tree and every `__pycache__` cleanup deleted nothing. A same-length edit inside one mtime tick is served stale, so the suite ran against UNMUTATED code and a test with no capacity was certified as having capacity. Three guards, canary being the one that generalises |

### Contamination (results 16, 17). THE HEADLINE RESULT

Round-1 enrichment on GB1, Opus 4.7, correct denominator (round 1 gives FOUR draws, not 60):

| quantity | value |
| --- | --- |
| P(global max in 4 uniform draws from 11,522) | 0.035% |
| observed at round 1 | 11 of 20 = 55% |
| **enrichment** | **1,584x** |
| top-10 enrichment | 14.1% against 0.087% = **162x** |

Cold probe, no data in the prompt at all:

| model | GB1 | PhoQ |
| --- | --- | --- |
| claude-opus-4.7 | **FWAA exact**, self-reports recall | wrong |
| gemini-3.1-pro-preview | **FWAA exact**, self-reports recall | wrong |
| gpt-5.5 | **recalls raw read counts (13,031 / 4,582)** | no parse |
| deepseek-v4-flash | does not know | no parse |
| mistral-nemo | wrong, **falsely claims recall** | wrong |

A model's self-report on contamination is worthless in both directions. **PhoQ is BUILD_SPEC's
primary landscape and appears clean**, so the design may survive by dropping GB1.

### The fifth denominator defect (result 15)

Two defensible sigma units, differing by 33x, on the same top-60 candidate set:

| unit | GB1 value | real GB1 ratio | question it answers |
| --- | --- | --- | --- |
| top1-top2 gap (what the project uses) | 0.71681 | **0.65** | can noise take the crown from the best candidate I hold? No, 1.97 sigma |
| median adjacent gap | 0.02178 | **~17** | can noise reorder the candidates I hold? Yes, 0.06 sigma |

Whether the noise-obscured regime exists is a definitional choice, not a property of the assay or
the landscape. Every table must state which unit it uses.

### Published-source provenance (results 13, 14)

GB1, Wu et al. 2016 eLife 5:e16965:

| published | our file | agrees |
| --- | --- | --- |
| 149,361 measured of 160,000 | 160,000 rows, 10,639 zero-filled | yes |
| 19.7% of measured are lethal | 29,477 / 149,361 = 19.7% | exactly |
| max fitness 8.76, WT = 1 | 8.762 | yes |
| input 89,075,246 reads, selected 45,587,128 | n/a | depth for the noise estimate |
| `count_input < 10` filtered | n/a | explains the 10,639 |
| Pearson r = 0.97 vs prior independent data | n/a | basis of noise Method 2 |

PhoQ, Podgornaia & Laub 2015 Science 347:673:

| published | our file | agrees |
| --- | --- | --- |
| 1,659 functional variants (1.04%) | pool at > 1.0 holds 11,146 (6.97%) | **NO, 6.7x more permissive** |
| two-step selection, binary functional call | continuous scores 0 to 133.594 | no per-variant noise published |

The 1,659th highest value in our file is 14.18, so the published functional call sits near a
threshold of 14.2 and not 1.0. **The design space the experiment restricts to is not the
published functional set.** This is a methods defect independent of the noise question.

### The surviving claim (result 12), now gated by result 13

* Replication pays at HIGH measurement noise. Ratio 4.0, both landscapes, argmax k=1 at
  bootstrap P=1.00, robust to the budget control. GB1 +11.1% +- 1.3; PhoQ about +11 to +13%.
* At ratio 2.0 replication does NOT pay under equal budget; it loses decisively.
* The reference table's crossing at ratio 2.0 was an artefact of unfiltered exploration,
  located to one line by the ablation ladder (result 5).
* Screen precision is NOT a second axis. The realized replication fraction identity
  `k / (k + (4-k)p)` accounts for the raw gradient: measured rep.frac at k=1 runs 0.23 at q=1
  to 0.33-0.39 at q=0.

| 27 | 2026-09-27 | **4a. WHICH SIGMA the fixed shrinkage estimator uses, and where its posterior peaks** | `scripts/is_the_shrinkage_estimator_monotone.py` | `results/step6_shrinkage_monotonicity.txt/.json` | Sigma at each variant's OWN observed mean, matching `oracle.measure`. That makes the posterior NON-MONOTONE: past a turning point a higher reading gets a LOWER posterior. **NK uniform (the grid landscape) and GB1 are monotone over their whole range; PhoQ turns at 108.93 unscaled, inside its range, at n=1 only.** No campaign reaches it with a singleton, 0 of 300, because greedy replicates anything reading that high. So the k=0 claim holds only under HOMOSCEDASTIC sigma |
| 28 | 2026-09-27 | **4b. AST audit for the silent-fallback bug CLASS** | `scripts/audit_silent_fallbacks.py` | printed | 15 guards return a computed value on bad input, 7 in the core library. **Exactly one was a real instance of the class** (the shrinkage fallback, fixed). `sample_without_replacement` is unreachable past its bound because the caller passes `min(need, len(cand))`; the three `(0.0, 0.0)` campaign returns need all 60 slots to fail, p=3.7e-50, a dead branch. Measured, not assumed |
| 29 | 2026-09-27 | **4b. Inventory of every shrinkage call site by noise model** | `scripts/audit_shrinkage_callers.py` | `results/step6_shrinkage_caller_audit.txt` | 12 sites: 10 multiplicative (pre-fix output void, all regenerated), **2 additive with a real scalar sigma whose output STANDS** (`falsify.py` F3, `sweep.py`). My first two drafts of this audit silently skipped `falsify.py`, once because `nomination=rule` is not a literal and once because the file-level pre-filter looked for `nomination="shrinkage"`. The same "skip counted as clean" defect the audit was written to find |
| 30 | 2026-09-27 | **4c. The two tests that would have caught it on day one** | `tests/test_shrinkage_actually_runs.py` | 9 tests | On a constructed history with unequal replicate counts, shrinkage must differ from max-mean. On a constructed heteroscedastic case, shrinkage must differ from max-single. Both are landscape-free and seed-free. The canary now also fails if shrinkage and mean agree on 100% of campaigns in ANY replicating cell |
| 31 | 2026-09-27 | **4d. THE PERCENTILE AGAINST THE RIGHT NULL, and a second correction to it** | `scripts/anchor_neighbourhood_null.py` | `results/step6_anchor_neighbourhood_null.txt/.json` | My 0.714/0.414 pair INCLUDED THE ANCHOR, proposed by all 20 campaigns; AVST reads 3.29 against a pool median of 6.69, so counting it dragged PhoQ down and produced a "below chance" story that was an artifact. Anchor excluded: GB1 0.729, **PhoQ 0.535 which is ABOVE 0.5**. Against a distance-matched neighbourhood null: **GB1 excess +0.171 +- 0.044 (3.9 SE), PhoQ -0.026 +- 0.029 (0.9 SE), difference of excesses +0.197 +- 0.052 (3.8 SE)**. The claim survives at 3.8 SE and not 5.3 |
| 32 | 2026-09-27 | **6. Grid power on the SELECTION SHORTFALL, and measured cost** | `scripts/grid_power.py` | `results/step6_grid_power.txt/.json` | Shortfall under max-single 0.2478 (sd 0.2781), under shrinkage 0.2088; paired gap +0.0390, paired sd 0.2179, pairing cuts the sd 1.28x. **383 campaigns/cell detects the 0.039 gap at 2.8 SE with the 1.25x inflation**, giving 5,745 campaigns. Measured cost **$0.158/campaign** over 3,020 pilot calls. A cost probe sets the final N, and any reduced N must publish its detectable difference: at 60/cell that is 0.0985, 40% of the baseline shortfall |
| 33 | 2026-09-27 | **THE GRID IS PRE-REGISTERED** | `spec/GRID_PREREGISTRATION.md` | committed before any grid call | Landscape, noise, five conditions with the dropped two named, models, structure, sample size with both multipliers, primary and secondary outcomes, analysis, the estimator statement, the four pre-committed readings, and the $600 stop |
| 34 | 2026-09-27 | **THE COMPARATOR WAS READING THE TRUTH.** Its prior was the pool's TRUE mean and variance | `repdef/campaign.py`, `tests/test_the_comparator_reads_no_truth.py` | 8 tests | With a true-pool prior "a simple rule on the agent's own data beats the agent" is FALSE. Not conservative: a stronger comparator INFLATES the agent's shortfall, so the bias pointed at our own thesis. Now empirical Bayes fitted per campaign from its own readings; the oracle prior survives as a LABELLED upper reference. Three test routes: invariance under 4 truths, recomputation from readings alone, reflection over every reachable float |
| 35 | 2026-09-27 | **The variance floor is INERT**, with the strong form | `scripts/prior_floor_sensitivity.py` | `results/step7_prior_floor_sensitivity.txt/.json` | Binds 0.8-17.5% at rel_floor=0.01, 24-46% at 0.5, more for policies that replicate more. Margin +0.0374 at every floor. **Prior variance changed in 168 of 400 campaigns; NOMINATION changed in 0 of 400**, while 183 of 200 have top-two contenders with unequal n, the condition reordering requires. rel_floor=0.01 registered |
| 36 | 2026-09-27 | **k\* = 1 ON THE PRIMARY LANDSCAPE, NOT 0** | `scripts/nk_reference_curve.py` | `results/step7_nk_reference_curve.txt/.json` | The k=0 optimum was a GB1 result. sigma at the pool mean over the pool's own sd: GB1 0.065, **NK 1.253**, so NK carries 19x more noise per unit of spread. n=1500 per k: k=0 7.8856, **k=1 8.0057 (+0.1201 +- 0.0118, 10.1 SE)**, k=2 +0.0989, k=3 WORSE than k=0. k\*=1 under all three rules, bootstrap 86.5/94.7/**98.5%**. "Replication never pays" is restricted to the GB1 panel |
| 37 | 2026-09-27 | **COST PROBE 1**, 15 campaigns, $0.9063, 336 calls | `scripts/grid.py --probe` | `results/grid_probe.txt`, `grid_probe_calls.jsonl` | Malformed 62% opus, 14% deepseek, 1% gemini. **Zero empty, zero truncated, zero reasoning tokens on all three**, so the fake-null mode is absent on this endpoint. Measured cost/campaign: opus $0.2146, gemini $0.0057, deepseek $0.0042, so full power N=383 is ~$430 of a $3,300 budget |
| 38 | 2026-09-27 | **THE PARSER WAS PUNISHING EXPLORATION**, found by the $0.91 probe | `repdef/llm_policy.py` | same | `parse` rejected B/J/O/U/X/Z as "ambiguity codes, not residues", which is true of proteins and FALSE of the generated landscape whose alphabet is the first 20 letters. **55 of 56 opus wrong_count calls carried a bad-alphabet note and opus had emitted exactly 4 lines on every one**; the parser kept 163 of 224 lines. So the alphabet bug was essentially the WHOLE malformed rate, and `wrong_count` was masking it because the count runs after the filter. Alphabet now comes from the landscape; new status `alphabet_then_wrong_count` |
| 39 | 2026-09-27 | **PRIMARY OUTCOME CHANGED: selection shortfall is gameable by not exploring** | `spec/GRID_PREREGISTRATION.md` section 0c | committed before stage 1 | Gemini scored selection shortfall **0.0000** with the **WORST** nominated fitness (7.3611, below scripted k=0 at 7.8856) and nominated the handed reference point twice in five campaigns. Under the old metric it would have been the best model in the study. New primary: nominated true fitness against scripted k\*. Decomposition asserted per campaign. Selection shortfall secondary, never without n_distinct beside it |
| 40 | 2026-09-27 | **Replication reported FOUR ways** | `scripts/grid.py` | same | Over slots used and over all 60 slots, each with and without re-orders of the reference point, since the prompt hands the agent that reading. The 81-97% against k\*=25% must survive all four or it is stated as definition-dependent |
| 41 | 2026-09-27 | **THE PARSER WAS SUBSTITUTING OPUS'S REASONING FOR ITS DECISION** | `repdef/llm_policy.py` | `results/grid_probe2*`, `grid_probe3*` | The old pattern accepted `:` `-` `,` as separators, so opus's analysis preamble ("- GDKF: readings 8.142, 7.282 -> mean ~7.35") matched as a proposal. 14 calls parsed 8-13 proposals from a request for 4, and since propose() takes the FIRST n_slots, **the orders placed were the first four sequences mentioned in the reasoning**. Three tiers, strictest first: a reply using the requested pipe format anywhere has ONLY its pipe lines counted. Effect on the headline: opus nominated fitness **7.4773 -> 7.8710** |
| 42 | 2026-09-27 | **PROBE 3: response health resolved** | `scripts/grid.py --probe --workers 5` | `results/grid_probe3.txt` | Malformed 62/14/1% -> **1/1/0%**. Slots used opus 55.4 (92%), deepseek 59.8, gemini 60.0. Opus's residual loss is ABANDONMENT after re-asks into non-viable space (16.6 rejections/campaign), which is the 7%-viable environment working as designed and not a harness fault. Zero empty, zero truncated, zero reasoning tokens throughout |
| 43 | 2026-09-27 | **DIAGNOSTIC, NOT A RESULT: the primary outcome on n=5 per model** | same | same | Scripted k=0 7.8856, k\*=1 8.0057. opus 7.8710, deepseek 7.6911, gemini 7.3611 (vs k*: -0.13, -0.31, -0.64). **n=5 per model, SEs 0.06 to 0.20, so these are DIAGNOSTICS for sizing and health and are NOT quotable as results**. Decomposition: exploration 0.82/1.07/1.40 against selection 0.073/0.000/0.000, so **the deficit is exploration by an order of magnitude**. Distinct variants measured per campaign: opus 11.2, deepseek 3.8, **gemini 1.6**. Identity checked on all 15 campaigns, 0 violations |
| 44 | 2026-09-27 | **DIAGNOSTIC, NOT A RESULT: replication four ways on n=5** | same | same | Four definitions. **n=5 per model, a DIAGNOSTIC and not a result.** Strictest (excluding re-orders of the handed reference point, over all 60 slots): opus 63.0%, deepseek 55.7%, gemini 44.3%, against k\*=25%. Loosest (over slots used, counting the anchor) gives 79-97%. The gap survives every definition; the MAGNITUDE is definition-dependent and is reported per definition |
| 45 | 2026-09-27 | **PARSER HARDENING, three layers** | `repdef/llm_policy.py`, `tests/test_parser_fixtures.py` | 135 tests | (1) The parser REFUSES TO GUESS: more proposals than requested is `ambiguous` and is re-asked, never truncated; the round then spends no slots. Two live truncations removed, including `[:n_slots]` in propose and `[:4]` in nominate which turned "GDIFX" into "GDIF". (2) A SECOND INDEPENDENT PARSER (`parse_b`, reads only the final block of pipe lines) runs on every call; any probe disagreement blocks launch and >1% in a grid cell pauses it. (3) A 17-case golden fixture corpus, plus a deterministic 20-calls-per-model spot-check dump |
| 46 | 2026-09-27 | **THE SECOND PARSER WOULD HAVE CAUGHT THE PREAMBLE BUG** | `scripts/reparse_audit.py` + the gate | `results/step8_reparse_audit.json` | Disagreement between the recorded parse and the independent parser: **31% on the original probe**, 4% on probe2 (alphabet fixed, preamble live), **0% on probe3** (tiered). On the pre-fix GB1 logs it is 0-4% |
| 47 | 2026-09-27 | **RE-PARSE AUDIT: the clock result STANDS** | `scripts/reparse_audit.py` | same | All 12 pre-fix experiments' crossing rounds hold within pooled SEs; largest shift 0.10 against SEs of 0.40 to 1.26. Old-vs-new parser disagreement 0-4% on GB1 logs, because the preamble habit appeared where opus reasoned about unfamiliar letters and its GB1 replies used the pipe format. Replication shifts are small (opus47 74.6% to 73.5%). **The turn-counter result is VERIFIED** |
| 48 | 2026-09-27 | **The fixture corpus caught a bug I wrote the same hour** | `tests/test_parser_fixtures.py` | 135 tests | Adding a "format tier" note made `notes` always non-empty, so the `bad_alphabet if notes else unparseable` branch mislabelled EVERY unparseable reply as an alphabet failure. Caught within minutes of the corpus existing, which is the argument for having one |
| 49 | 2026-09-27 | **SIZING COMMITTED before any condition mean** | `spec/GRID_PREREGISTRATION.md` 0e, 0f | committed | Minimal effect of interest **0.06** (half the k=0 to k* gap). Unpaired, 2.8 SE. From the conservative k=0 arm sd 0.3937, **N=676 per cell**, 10,140 campaigns, **$711.83**, 15.1h at 8 workers. Stage 1 is 40/cell for VARIANCE ONLY. Headline behavioural metric becomes **distinct variants measured**, against the scripted k\* reference of **39.2** |
| 50 | 2026-09-27 | **THE CLOCK, recomputed at n=20 under ONE definition** | `scripts/clock_verify.py` | `results/step8_clock_verify.json` | **Crossing round is "at least half", never "more than half"**, since a round's replication fraction is a multiple of 1/S so ">half" means 100% at S=2 and 62.5% at S=8. Cell means at 20 per length: 4.85, 5.35, 4.55. **Campaign-level OLS slope -0.0238 +- 0.0248** over all 60 campaigns. Absolute clock (predicts 0) sits **1.0 SE** away, CONSISTENT; pacing against the budget (predicts 0.357 from the length-15 cell) **15.4 SE**, rejected; rounds remaining (predicts 1) **41.3 SE**, rejected. Supersedes the n=5 figure of +0.011 +- 0.086 with distances 0.1/4.6/11.5, which used 5 campaigns per length, the pre-fix parser and the ">half" threshold. **Every competing hypothesis is now rejected by a wider margin**. A weighted 3-point fit to the cell means (weights 1/SE^2) gives -0.0273 +- 0.0266 with distances 1.0/14.5/38.7; the paper quotes the campaign-level fit, which needs no weighting choice, and the two agree on every verdict. **My first explanation of that difference was WRONG**: I attributed it to the committed parse values, which give -0.0212 +- 0.0257, a coincidence of similar magnitude and a different computation |
| 51 | 2026-09-27 | **The old ">half" numbers, for the record** | same | same | The n=5 logs give 6.20, 6.20, 6.40 under ">half" and 5.00, 5.00, 4.40 under ">=half". The two definitions differ by roughly one round, which is why only one may appear in the paper |
## Opened by this session

* **Every margin measured before 2026-09-27 is void** and must be recomputed if it is quoted
  anywhere. The estimator named in the criterion was not the estimator running.
* **The gap band fails at 0.22** on the chosen generator, and the argument behind its lower bound is
  refuted by the margin that bound was meant to protect. Reported as a failed diagnostic.
* **No experiment script may report a margin without its estimator canary.** Two independent
  mechanisms produced a broken table on the same day, neither of which raised anything.
* **When an independent reimplementation disagrees with the pipeline, neither wins by default.** A
  toy empirical-Bayes simulation disagreed with the pipeline's zero NK margin two hours before the
  report. The disagreement was the signal and it was not chased. Standing rule from now on.
* **The percentile statistic has now been corrected TWICE**, once for its null and once for including
  the anchor. Any future use must exclude the anchor and carry the distance-matched null.
* **The grid's N is set by budget, so its null carries a detectable-difference bound.** Without that
  bound "neither intervention closes the shortfall" says nothing.
* **Every result measured at temperature 0 carries unquantified sampling noise** (result 24). The
  magnitude 0.265 rests on four repeated prompts and is an existence proof, not an estimate. A
  proper characterisation would repeat one prompt 30 times.
* **The distance-4 shape difference is 1.9 SE, suggestive and not significant.** It is a mechanism
  consistent with the percentile result, not independent evidence for it.
* **The two interventions are BUILT but not RUN.** No behavioural number exists for either.
* **`aggregated` shows SE from n=2 as a point estimate.** An SE on two readings is itself very noisy,
  and the intervention presents it without that caveat. Whether this matters is an empirical question
  the aggregated cell will answer.

## What is still missing

* `gate2.py` does not exist. Its numbers above are unverified.
* The full (q x ratio x k) sweep is NOT run, and is now not planned: the budget control came
  back negative, so the q axis is one-dimensional.
* **No number in any deliverable has yet been relabelled into a recalibrated sigma unit.** This
  is the next unavoidable job before any draft quotes a ratio.
* The exploration/selection decomposition is computed per campaign but not yet tabulated.
* 4.1 to 4.4 are NOT run. Step 4.0 came back negative and the brief says stop on that.
* **PhoQ has no noise anchor.** It is the primary landscape. A source with per-variant PhoQ
  replicate data is the one remaining route to a real target regime.
* **One unit definition must be chosen and applied everywhere**, given the 33x fork in result 15.
  SETTLED: the random-calibrated top1-top2 gap, 0.557 GB1 and 5.807 PhoQ, now in code as
  SIGMA_UNIT with the circular inherited values kept as SIGMA_UNIT_INHERITED.
* **NO behavioural number from result 16 may be quoted.** Its "blind" cell was BUILD_SPEC's
  baseline: the line "Readings are subject to measurement error" was in the shared header, so
  rung 1 as specified had not been run. Fixed; the ladder is now five strictly cumulative rungs.
* ~~The in-campaign round-1 diagnostic has not been run on PhoQ~~ **CLOSED, result 22.** PhoQ is
  clean at round 1 (0 of 20). Cold recall and in-context proposal were indeed different tests, and
  they happen to agree here; the agreement is a finding and not something the probe established.
* **The r = 0.97 noise estimate is WITHDRAWN.** It is a cross-study comparison on singles and
  doubles, not a replicate correlation, and a wide fitness range inflates Pearson mechanically.
  The Poisson route (sigma = 0.364, ratio 0.65) is what stands.
* **Prior art: Dai et al., Batch Bayesian Optimization for Replicable Experimental Design,
  NeurIPS 2023 (arXiv:2311.01195).** Formalises adaptive replication allocation under
  heteroscedastic noise with no-regret guarantees. The NORMATIVE half of this project is
  substantially solved. I did not search for this before characterising optimal replication, which
  violates the standing rule to search before any novelty-adjacent claim. BTS-RED becomes the
  upper baseline the agent is measured against.
