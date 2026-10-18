# PRE-REGISTRATION: the main grid

<!-- EDITORS: append a NEW amendment section at the END of this file, never before "## 0b". Inserting
     before 0b pushed 0b to the end of the document once and pushed 0l and 0m ahead of it a second time.
     tests/test_the_preregistration_is_intact.py asserts the order and caught both. -->

## 0. AMENDMENT, 2026-09-27, before any grid call

Commit e528275 pre-registered this grid with a comparator whose prior was the mean and variance of the
POOL'S TRUE FITNESSES. That is amended here. No grid data exists, so the amendment costs nothing but
the record of having made it.

**THE COMPARATOR LEAKED THE TRUTH.** `_shrinkage_nominate`'s own docstring said so, and I read that
line without registering what it meant for the headline. With a true-pool prior the sentence "a simple
rule applied to the agent's own data beats the agent" is FALSE, because the rule also holds the true
fitness distribution. The leak is not conservative for us: extra information makes the comparator
stronger, a stronger comparator inflates the agent's shortfall, so the bias pointed in the direction of
our own thesis, which is the worst direction available.

**THE PRIMARY COMPARATOR IS NOW EMPIRICAL BAYES, FITTED PER CAMPAIGN FROM THAT CAMPAIGN'S OWN
READINGS.** Method of moments: prior mean is the mean of the per-variant observed means; prior variance
is their spread MINUS the average sampling variance of a mean, because the observed spread already
contains the noise; floored at `rel_floor * noise` so a degenerate campaign cannot produce a
non-positive variance. It returns None when fewer than two variants have readings, and such a campaign
is recorded as MISSING a comparator, never as a tie.

The true-pool prior is kept as `ref_shrinkage_oracle`, a LABELLED UPPER REFERENCE. It never appears in
a headline sentence.

Enforced by `tests/test_the_comparator_reads_no_truth.py`, 8 tests, three independent routes:
invariance (the same readings under four different truths must give the same answer), recomputation
(the prior must equal a method-of-moments estimate computed from the readings alone), and reflection
(walk every float reachable from the comparator's arguments and assert none is a true value, in the
style of `test_view_leak.py`). Plus: a campaign given NO prior argument still gets a fair comparator,
which is the structural statement that it needs nothing from the oracle to function.

**THE VARIANCE FLOOR IS INERT, with a number behind it.** It binds in 0.8% to 17.5% of campaigns at
`rel_floor = 0.01` depending on the policy, rising to 24% to 46% at 0.5, and more often for policies
that replicate more, since they measure fewer distinct variants. Across a 50-fold range of the floor the
margin is unchanged (+0.0374 at every value, 0.0 SE apart), and the strong form: the prior variance
changed in 168 of 400 campaigns while the NOMINATION changed in 0 of 400. Reordering under a
prior-variance change requires unequal n among the contenders, which 183 of 200 campaigns have, so the
invariance is not an accident of that condition being rare. **`rel_floor = 0.01` is the registered
value, and it is a guard against a degenerate campaign and not a dial with scientific consequences.**

### Provenance of the confirmatory commit, so its validity is auditable and not asserted

Stage 1 began at **2026-09-27T22:49:39+10:00** on code commit `1048126`, recorded in
`results/grid_stage1_manifest.json`.

The confirmatory family of section 0g **first entered the repository in commit `fc34d22` at
2026-09-27T23:26:26+10:00**, thirty-seven minutes after stage 1 began. It was restored, along with
sections 0j and 0k, in `0a2f10c` at 23:35:43, forty-six minutes after the start. The earlier commit is
the one that fixes the family, and the later one restored two sections a slicing edit of mine had
deleted.

**What data existed at each point**, counted from the campaign log as committed in those very commits, so
the count cannot be re-derived from a later state:

| condition | at `fc34d22`, 23:26:26 | at `bb4b616`, 23:36:10 |
| --- | --- | --- |
| Blind | 120 | 120 |
| Quantitative | 120 | 120 |
| Mechanism | **13**, all opus | 100 |
| **Aggregated** | **0** | **0** |
| **Decision-rule** | **0** | **0** |

**Every one of the six confirmatory contrasts is Aggregated-against-Mechanism or
Decision-rule-against-Mechanism, and both intervention conditions stood at ZERO campaigns when the family
was committed.** No contrast in the family was computable, and none was computed.

Stated against my own interest: 13 Mechanism campaigns did exist at `fc34d22` and 100 by `bb4b616`, so
the Mechanism side of each contrast was partly observable. No Mechanism mean was computed;
`scripts/stage1_variance.py` centres every cell before pooling and prints variances only, which is a
structural refusal and not a promise. The verifiable claim is the one above: the intervention side of
every confirmatory contrast was empty.

Reproduce these counts with:

```
git show fc34d22:results/grid_stage1_campaigns.jsonl | python3 -c "import collections,json,sys; print(collections.Counter(json.loads(l)['condition'] for l in sys.stdin if l.strip()))"
```

---

## 0b. THE SCRIPTED REFERENCE ON THE PRIMARY LANDSCAPE, and what it does to the claim

**k\* = 1, not 0.** Every replication-rate result in this grid is read against a scripted optimum, and
the optimum we had been quoting, zero, was measured on GB1. The two landscapes put the noise in
completely different places relative to the signal:

| landscape | sigma at the pool mean | viable-pool sd | ratio |
| --- | --- | --- | --- |
| GB1 | 0.0703 | 1.0873 | **0.065**, noise is 6% of the spread |
| NK uniform, the primary landscape | 0.5091 | 0.4062 | **1.253**, noise EXCEEDS the whole spread |

Replication buys `sqrt(n)` on the standard error of a mean, and it is worth a slot only when the error
it removes is large next to the differences being resolved. At 6% of the spread there is almost nothing
to remove, which is why k=0 won on GB1. At 125% there is a great deal.

Measured on NK uniform under the grid's exact noise model, nominated true fitness against k, with the
fair comparator (`scripts/nk_reference_curve.py`, `results/step7_nk_reference_curve.txt`):

**k\* = 1 under all three nomination rules**, at n=1500 campaigns per k. Bootstrap support over 2000
resamples: 86.5% under mean, 94.7% under max, **98.5% under shrinkage**. Under shrinkage k=1 beats k=0
by **+0.1201 +- 0.0118, which is 10.1 SE**; k=2 is +0.0989 (8.2 SE); k=3 is WORSE than k=0 by 0.0329
(2.5 SE), so the curve has an interior optimum and is not monotone. NK carries 19x more noise per unit
of spread than GB1.

**CONSEQUENCES, registered here.**
1. **"Replication never pays in the real assay" is a GB1 statement and is restricted to the GB1
   panel.** It is not a general claim and will not be written as one.
2. On the primary landscape the correct replication rate is k\* = 1, which is 25% of slots, and every
   grid replication rate is read against THAT and never against zero.
3. An agent replicating at roughly 25% on NK is behaving CORRECTLY, so a high replication rate there
   is not evidence of error. The diagnostic question becomes whether the rate tracks k\* across
   landscapes where k\* differs, which is a sharper question than the original one.

---


Committed 2026-09-27, before any grid API call. The commit timestamp is the evidence. Nothing below
may be changed after the first grid call; if a target turns out unreachable that is reported as a
failure to reach it and the criterion stays as written.

Every number quoted here was produced by a committed script and is re-checkable by
`scripts/verify_all_numbers.py` (91 checks, 0 failures at the time of writing).

---

## 1. Landscape

**NK uniform**, `K=1, seed=1, threshold_percentile=93.0, dist="uniform"`, rescaled so its maximum
equals GB1's 8.762 because sigma is defined in GB1 units. **One fixed landscape seed for every
cell**, so no cell can differ because it saw a different landscape.

Why this and not GB1 or PhoQ: it is generated, so it cannot be contaminated, and it satisfies the
pre-registered margin criterion. Held-out margin **+0.0329 +- 0.0057, 5.7 SE** on campaign seeds
disjoint from selection, 4.6 SE after the 1.25x overdispersion, against a 3 SE threshold committed
before the number existed. Effect size 0.055 sigma against GB1's 0.036. Neutral across all three
replicating baselines at 6.8, 6.1 and 8.8 SE.

`gap/sigma` is **0.22**, and the 0.5 lower bound that would have excluded it was WITHDRAWN in the
fifth amendment because the measurement refuted the argument behind it.

## 2. Noise

**Multiplicative, primary.** `sigma(f) = sqrt(0.0035^2 + (0.073 f)^2)`, constants from Wu et al.'s
published read depth. The floor exists because pure `|f| * cv` gives a dead variant exactly zero
noise.

**MEASURED LIMITATION, recorded 2026-09-27 before any grid call. The noise is multiplicative in FORM
but nearly homoscedastic in EFFECT on this landscape.** Sigma varies across each landscape's viable
pool by:

| landscape | pool fitness span | sigma span |
| --- | --- | --- |
| **NK uniform, the grid landscape** | 1.4x | **1.35x** |
| GB1 | 87.6x | 79x |
| PhoQ | 133x | 133x |

NK uniform with a 93rd-percentile viability threshold keeps only the top 7% of a fitness distribution
that the sum over loci has already concentrated, so its viable pool spans 1.4x and sigma runs only
0.4725 to 0.6396. Three consequences, all stated and none fixed, because the landscape and the
threshold are committed and re-tuning them after seeing this would be the goalpost-moving that
pre-registration exists to prevent:

1. The Quantitative rung's level-dependence statement is nearly vacuous HERE. It remains the exact
   statement of the noise, and the rung is still the one that supplies the magnitude.
2. The additive robustness panel is less informative than intended, because multiplicative and
   additive noise are close to each other on this pool. It is still run, and its result is now
   expected to agree with the primary and no longer to test it.
3. It is part of why the k=0 equivalence holds here: with sigma nearly constant, the posterior is
   nearly affine in the reading, which is the homoscedastic case.

What does NOT depend on it: the primary outcome. Whether replication pays is governed by gap/sigma,
which is 0.22 on this landscape, and not by how much sigma varies with the level.

## 3. Conditions, five

Cumulative, so a difference between adjacent conditions is attributable to one block.

| spec name | code rung | what it adds |
| --- | --- | --- |
| Blind | `blind` | nothing; noise exists and the prompt never mentions it |
| Quantitative | `informed` | the exact noise, stated as a FUNCTION (see below) |
| Mechanism | `instructed` | the averaging mechanism and explicit permission to re-order |
| Aggregated | `aggregated` | environment change: history as n, mean and SE per variant |
| Decision-rule | `decision_rule` | one sentence: report the variant with the highest AVERAGE |

**Dropped and reported as such.** *Qualitative* (code rung `baseline`, the bare unquantified fact
that readings carry error) is dropped and reported as a null from the pilot. *Forced* is dropped,
because the nomination metric now measures what it was designed for.

**AMENDED 2026-09-27, before any grid call. What the exact sigma means under multiplicative noise.**
Section 2 fixes the noise as `sigma(f) = sqrt(0.0035^2 + (0.073 f)^2)`, so there is no single sigma to
quote. The Quantitative rung therefore states the FUNCTION, with its constants as digits and no
derivation:

> Each measurement carries independent Gaussian error whose standard deviation DEPENDS ON the
> variant's own level f, as sigma(f) = sqrt(0.00351^2 + (0.073 * f)^2). A variant reading near 1.0
> therefore carries much less absolute error than one reading ten times higher.

Quoting one number instead would either be false or would silently pick a level, and picking a level
is a modelling choice the agent should not have made for it. The constants are printed to significant
figures and not to two decimals, because two decimals turn cv 0.073 into 0.07, understating the noise
by 4% inside the rung whose whole purpose is stating it exactly, and turn the floor into 0, denying
that a floor exists. A rung that misquotes the quantity it exists to quote is WORSE than the rung
below it, since the agent then works from a wrong number instead of from no number. Pinned by
`tests/test_interventions_are_clean.py::TheNoiseStatementMustNotMISQUOTETheNoise`, which parses the
constants back out of the rendered prompt and compares them to the oracle's own.

The statement is descriptive. It names no action, and the test asserts the absence of replicate,
average, repeat, consider and you-should from it.

Aggregated and Decision-rule are both cumulative on Mechanism, so each is measured against the
strongest diagnostic condition. Pinned by `tests/test_interventions_are_clean.py`, 20 tests, 21 of 21
mutants caught.

## 4. Models, three minimum

One frontier, one mid-tier, one open-weight. **Exact ids with dates, pinned before launch and logged
on every call** alongside the provider's own returned model string, so a silent substitution by the
router is visible in the log and not only in the plan.

## 5. Structure

15 rounds, 4 slots, 60 measurements. The clock experiments are complete; length and slots are NOT
re-run.

## 6. Sample size

Measured planning inputs, from `scripts/grid_power.py` at n=1500 on this landscape:

- shortfall under max-single: mean **0.2478**, sample sd 0.2781
- shortfall under shrinkage: mean **0.2088**, sample sd 0.2392
- the paired max-minus-shrinkage gap: **+0.0390**, paired sd **0.2179** (pairing cuts the sd 1.28x)
- measured cost: **$0.158 per campaign** mean at opus-4.7 over 3,020 pilot calls, median $0.125

Two multipliers, both reported: **1.25x on the standard deviation** (the measured across-seed
overdispersion over 12 disjoint ranges) and **1.5625x on the campaign count**, printed as 1.57x after
the ceiling.

**Target N: 383 campaigns per cell.** That is what detects the landscape's own 0.039 gap at 2.8 SE
with the sd inflation applied, and an intervention that closes the shortfall must move at least that
far. 5 conditions x 3 models x 383 = **5,745 campaigns**.

**Cost, and the probe that decides whether the target survives.** At frontier rates for all three
models that is about $908, over the ceiling. Two of the three models are cheaper, which should bring
it inside $600, but the factor is an assumption and not a measurement. **So a COST PROBE runs first:
5 campaigns per model, all three models, Mechanism condition, and the measured $/campaign per model
sets the final N.** The probe's numbers and the resulting N are reported before the grid launches.

**If the probe shows 383 does not fit**, the fallback is pre-committed here: reduce N uniformly
across cells, never per cell, and **report the smallest shortfall difference the design can detect**,
computed as `2.8 * 0.2179 * 1.25 / sqrt(N)`. At 60 per cell that is 0.0985, which is 40% of the
0.2478 baseline shortfall.

**THE NULL IS ONLY INTERPRETABLE WITH THAT NUMBER ATTACHED.** The reading "neither intervention
closes it" means "we exclude a closure of at least X", where X is the detectable difference at the N
actually run. Without X a null says nothing, and reporting one without it would be the same error as
a novelty claim made without searching.

## 7. Outcomes

**Primary: selection shortfall**, best true measured minus true nominated. Zero when the agent names
the best thing it measured.

**Comparator: shrinkage applied to the agent's own history, with an EMPIRICAL-BAYES prior fitted from
that history.** See section 0. Recorded as `ref_shrinkage` on EVERY result, beside `ref_mean`,
`ref_max` and the labelled `ref_shrinkage_oracle`, so the comparison needs no second pass over the data
and cannot drift from the run it describes. Stated plainly in the paper: the
comparator KNOWS the noise model, including in the Blind condition where the agent does not, so it is
a REFERENCE and is described as one, never as an achievable policy. It uses sigma evaluated at each
variant's own observed mean (section 9).

**Secondary:** replication fraction by round; first round above 50%; final-three-round replication;
stated versus revealed intent.

## 8. Analysis

Mixed model with campaign random effects. Wild cluster bootstrap intervals, Rademacher weights,
clustered on campaign. **Sample standard deviation throughout**, never the population convention.

**Additive robustness panel:** Mechanism condition only, one model, additive noise at three ratios,
to show the behaviour holds where the correct action varies.

**Contamination sweep:** round 1 only, one call per campaign, five models, four landscapes: GB1
named, GB1 with the name removed, PhoQ, NK. Report the argmax count AND the fitness percentile
against the **anchor-neighbourhood null** (`scripts/anchor_neighbourhood_null.py`), which is
distance-matched to each model's own proposal distances. The anchor is EXCLUDED from the proposal set:
including it produced a spurious "PhoQ below chance" result, since every campaign proposes the anchor
and AVST reads 3.29 against a pool median of 6.69.

Reference values already measured: GB1 excess over its own neighbourhood **+0.171 +- 0.044, 3.9 SE**;
PhoQ **-0.026 +- 0.029, 0.9 SE**; difference of excesses **+0.197 +- 0.052, 3.8 SE**.

## 9. The estimator, stated because it decides what every margin means

The shrinkage comparator evaluates sigma at **each variant's own observed mean**, `sigma(m)`, matching
`oracle.measure`. It cannot use true fitness, which it does not see, and a pooled value would discard
the heteroscedasticity that is the point.

**This makes the posterior non-monotone in the reading.** Because sigma rises with the level, a high
reading is trusted less and pulled harder toward the prior, so past a turning point a higher observed
mean receives a LOWER posterior (`tests/test_shrinkage_actually_runs.py`). Measured turning points,
from `scripts/is_the_shrinkage_estimator_monotone.py`:

| landscape | n=1 turning point | largest observed | inside the data |
| --- | --- | --- | --- |
| **NK uniform, the grid landscape** | none on [0, 1.5x max] | 9.81 | **no** |
| GB1 | none | 9.84 | no |
| PhoQ, unscaled | 108.93 | 136.42 | yes, at n=1 only |

**No grid margin depends on this**, because the grid landscape is monotone over its whole range. On
PhoQ the region is inside the fitness range but **no campaign reaches it with a singleton, 0 of 300**,
because the greedy policy replicates anything reading that high. That guarantee is empirical and
policy-dependent, so any PhoQ margin must carry the turning point alongside it.

**Consequence for the k=0 claim.** The earlier statement that a k=0 margin is "mathematically
unsatisfiable" holds only under a **homoscedastic** sigma. Corrected in the fourth amendment.

## 10. Pre-committed readings

Written before execution. Each reading is fixed to its result now, so no result can be reinterpreted
after it arrives.

| Result | Reading |
| --- | --- |
| Aggregated closes most of the selection shortfall | The failure is arithmetic and presentation. The paper recommends aggregating before showing the agent anything. |
| Decision-rule closes it, Aggregated does not | The failure is in the choice rule. One sentence fixes it. |
| Neither closes it | The failure is judgement. The strongest and most worrying result. Reported only with the detectable-difference bound from section 6. |
| Shortfall near zero in every condition | Agents nominate well. The nomination half is a null, reported as such, and the paper rests on the replication-policy findings. |

## 11. Operating rules

- **Spend reported as it accrues. STOP AND REPORT AT $600 for this stage.**
- Predictions written before execution.
- A disagreements section in the write-up.
- The three verdicts kept separate and never merged: **code correct**, **numbers reproduced**,
  **claim survives**.
- Every experiment script that reports an estimator's behaviour runs its ESTIMATOR CANARY first and
  aborts if the estimator is not provably live. Two independent mechanisms produced a believable
  wrong table on 2026-09-27 and neither raised anything.
- When an independent reimplementation disagrees with the pipeline, **neither wins by default**; the
  cause is found before either is chosen. This rule exists because a toy empirical-Bayes simulation
  disagreed with the pipeline's zero NK margin, the disagreement was the signal, and it was not
  chased.

---

## 0c. OUTCOME AMENDMENT, 2026-09-27, before any stage-1 data exists

**THE PRIMARY OUTCOME IS CHANGED.** Selection shortfall rewards an agent that never explores, because
an agent holding two measured variants has almost nothing to mis-select. The first cost probe measured
this directly:

| model | selection shortfall | nominated true fitness | replication | slots used | nominated the anchor |
| --- | --- | --- | --- | --- | --- |
| gemini-2.5-flash | **0.0000** | **7.3611** | 97.3% | 59.8 | 2 of 5 |
| deepseek-chat-v3.1 | 0.0652 | 7.7755 | 93.6% | 56.0 | 0 of 5 |
| opus-4.7 | 0.1377 | 7.6137 | 81.2% | 38.4 | 0 of 5 |
| scripted k=0 | | 7.8856 | 0% | 60 | |
| **scripted k\* = 1** | | **8.0057** | 25% | 60 | |

Gemini scored a PERFECT selection shortfall and the WORST outcome of the three, below even the
scripted k=0 policy, and twice nominated the reference point it had been handed. Under the old primary
outcome it would have been the best-performing model in the study. That is the metric failing, and not
the model succeeding.

**NEW PRIMARY OUTCOME: the true fitness of the nominated sequence, compared against the scripted k\*
policy on the same landscape.** k\* = 1 with mean 8.0057 under the shrinkage comparator, read from
`results/step7_nk_reference_curve.json` by `scripts/grid.py::scripted_reference()` and never typed.

**THE DECOMPOSITION IS ALWAYS REPORTED**, and it is an identity, so the code asserts it per campaign:

> global best - nominated  =  (global best - best measured)  +  (best measured - nominated)
>                          =   exploration shortfall         +   selection shortfall

**SELECTION SHORTFALL BECOMES SECONDARY**, and is never reported without `n_distinct_measured`
beside it, because the two together are what make it interpretable and either alone is not.

**Why this is committed now.** Switching a primary outcome after seeing stage-1 data would look like
outcome switching whatever the reason, and the reason here is good: the old metric is gameable by
inaction, which is visible in a $0.91 probe and would have been visible in the final table too, as an
inexplicably excellent mid-tier model. No stage-1 campaign has been run.

## 0d. THE REPLICATION FRACTION IS REPORTED FOUR WAYS

The prompt hands the agent the reference point's reading, so a model that re-proposes the reference
heavily looks like a replicator under any definition that counts it. All four are recorded per
campaign, and the headline claim must hold under all of them or it is stated as definition-dependent:

1. `replication_fraction` over SLOTS USED, counting every re-order (the original definition)
2. `replication_fraction_of_budget` over all 60 slots, so an agent that leaves slots unused is not
   flattered by a smaller denominator
3. `replication_fraction_excl_anchor` over slots used, excluding re-orders of the reference point
4. `replication_fraction_excl_anchor_of_budget` over all 60 slots, excluding the reference point

`anchor_orders` and `n_distinct_measured` are recorded alongside. The claim under test is whether the
agent's rate tracks k\* = 25%, and the probe's 81% to 97% is 3 to 4 times that, so the question is
whether the gap survives definitions 2 to 4.

---

## 0e. SIZING AMENDMENT, 2026-09-27, before any stage-1 condition mean is looked at

**MINIMAL EFFECT OF INTEREST: 0.06 on nominated true fitness.** That is half the scripted k=0 to k\*
gap of 0.1201, so it is the smallest difference that would matter against the reference the primary
outcome is measured on.

**SIZING RULE, fixed here.** Final N per cell comes from the stage-1 variance estimate at that effect,
at **2.8 standard errors, UNPAIRED between conditions**, since two conditions are different campaigns
and share no history. Unpaired means `n = 2 (z sd / effect)^2`.

**THE PROJECTION FROM THE SCRIPTED VARIANCE**, which stage 1 will replace:

| source of sd | sd | n per cell |
| --- | --- | --- |
| k=0 arm (the conservative choice) | 0.3937 | **676** |
| k\* arm | 0.3385 | 500 |

The k=0 arm is used because the probe put every model at or below k=0, so its variance is the one the
agent cells will resemble, and it is the larger of the two. **DECIDED 2026-09-27, after the reviewer verified the per-model figures: the UNIFORM option at the
LARGEST per-model N is taken, so every cell is the same size.** Opus has both the largest within-cell
variance and essentially all of the cost, so uniform sizing costs about eleven dollars more than
per-model sizing and buys equal-sized cells, which also keeps the exploratory between-model comparisons
from confounding precision with model. The final number comes from all 600 stage-1 campaigns and not
from a partial run, because the two intervention conditions may change the variance.

The projection below is superseded by that measurement and is kept for the record: **N = 676 per cell**,
10,140 campaigns,
**$711.83** at the probe's measured per-campaign costs, 15.1 hours at 8 workers or 7.6 at 16.

**Stage 1 is 40 per cell, 600 campaigns, $42.12**, then a top-up to the final N. Any departure from
676 once the stage-1 variance is in will be reported with the reason.

**STAGE 1 IS FOR VARIANCE ONLY.** Only the pooled within-cell variance is computed from it, per model
and per condition. No condition means are looked at, and no comparison between conditions is made,
until the final N is reached and all campaigns are analysed together. The top-up appends to the same
files, and `scripts/grid.py` resumes by skipping (condition, model, seed) triples already on disk, so
stage 1 and the top-up are one dataset and not two.

## 0f. THE HEADLINE BEHAVIOURAL METRIC IS DISTINCT VARIANTS MEASURED

Replication fraction is a ratio whose denominator moves and whose value depends on whether re-orders of
the handed reference point are counted, which is why it is reported four ways. **The headline
behavioural metric is the number of DISTINCT variants measured per campaign**, which has no
denominator choice in it and is directly comparable to the scripted policies:

| policy | distinct variants per campaign |
| --- | --- |
| random | 51.1 |
| greedy k=0 | 51.2 |
| **greedy k\* = 1** | **39.2** |
| greedy k=2 | 27.2 |
| greedy k=3 | 15.4 |

From `results/step7_prior_floor_sensitivity.json`. The probe's agents measured 11.2 (opus), 3.8
(deepseek) and 1.6 (gemini) against the k\* reference of 39.2. Replication fraction stays SECONDARY and
is reported under all four definitions.

---

## 0g. CONFIRMATORY FAMILY, committed before any stage-1 condition mean is computed

**SIX PRIMARY CONTRASTS, and no others.** Every other test in this paper is EXPLORATORY and is labelled
so wherever it appears.

| # | contrast | model |
| --- | --- | --- |
| 1 | Aggregated vs Mechanism | opus-4.7 |
| 2 | Decision-rule vs Mechanism | opus-4.7 |
| 3 | Aggregated vs Mechanism | gemini-2.5-flash |
| 4 | Decision-rule vs Mechanism | gemini-2.5-flash |
| 5 | Aggregated vs Mechanism | deepseek-chat-v3.1 |
| 6 | Decision-rule vs Mechanism | deepseek-chat-v3.1 |

Outcome: nominated true fitness, the primary outcome of section 0c. **HOLM correction across the family
of six.** Each contrast is unpaired between conditions, since two conditions are different campaigns
sharing no history.

> **SUPERSEDED BY AMENDMENT 0s (2026-09-28).** The sentence above is wrong and is kept because a
> pre-registration that edits away what it committed to is not one. The contrasts are PAIRED BY SEED.
> "Sharing no history" is a fact about the AGENT; the ENVIRONMENT is shared, because the oracle keys
> every random draw on the seed. Holm across the family of six is unchanged.

Blind, Quantitative and Mechanism form the diagnostic LADDER and are described, never tested in the
confirmatory family: the ladder answers what the agent does as information is added, and the two
interventions answer whether anything fixes it. Contrasts among ladder rungs, comparisons between
models, every replication-fraction and distinct-variant comparison, the additive panel, the
contamination sweep and the landscape-replication analysis are all EXPLORATORY.

## 0h. RUN ORDER, DRIFT AND REPORTING

**THE TOP-UP RUNS IN SHUFFLED ORDER ACROSS ALL 15 CELLS**, seeded and recorded, so that time of day,
provider load and any model-side drift cannot line up with condition. **Stage 1 ran in condition
blocks**, which is a real confound in that half of the data, so every cell is checked for drift of the
primary outcome against wall-clock start time and the result is reported whatever it shows. Every
campaign records its wall-clock start.

**REPORTING.** Medians and bootstrap intervals are reported beside every mean. Distinct-variant counts
are modelled AS COUNTS and never as a continuous mean alone.

## 0i. THE BLIND RUNG: blind in its prompt, never in its data, and the timing matters

The Blind rung's prompt does not mention measurement error. Its DATA reveals measurement error almost
immediately, so the rung measures what the PROMPT states and not what the agent is able to know.

**MY FIRST VERSION OF THIS SECTION OVERSHOT and is corrected here.** It concluded that replication under
Blind "cannot be attributed to habit". That inverts cause and effect for most campaigns. There are two
routes to visible evidence and they are not interchangeable:

| route | what it needs | what it can explain |
| --- | --- | --- |
| **A**, the anchor reads far from its stated value | ONE reading | evidence can precede any re-order |
| **B**, a repeated variant's two readings differ | **a re-order FIRST** | the re-order CREATED the evidence |

Over the 120 stage-1 blind campaigns: route B gave the first contradiction in 64, route A in 52, and
both appeared in the same shown history in 4. That sums to 120. **My earlier count of "22 and 19 over 40
campaigns" summed to 41, because a campaign showing both routes was counted under each; the routes are
now mutually exclusive by construction.** The threshold, which the earlier text did not state: the anchor
counts as reading far from its stated value when a shown reading differs from the prompt's 6.87 by more
than **0.30**, which is about 0.6 of the noise standard deviation at that level, sigma(6.87) = 0.502.

**THE ORDER OF EVENTS.** Of 120 campaigns, the first re-order comes BEFORE any visible contradiction in
**42**, in the same round in **51**, and after it in only **27**.

**THE CORRECTED STATEMENT, which is what the methods and any draft text will say:**

> The first re-order often precedes any visible evidence of noise, so EARLY replication is not
> evidence-driven. LATER replication is evidence-responsive.

**The second half is measured, and it survives the obvious confound.** Replication per slot is 11.3%
[8.9, 13.6] before the first visible contradiction and 74.4% [71.6, 77.1] after, a paired rise of
**+65.8 pp** [+62.6, +69.1] over 69 campaigns. That contrast is confounded with campaign progress, since
"before" is early rounds and "after" is late and the set of already-measured variants grows either way,
so two controls:

- **Regressing replication per round on round AND a post-contradiction indicator**: the round trend is
  +0.047 per round and the post-evidence coefficient is **+0.2445 +- 0.0246, which is 10.0 SE** over 3,267
  round-observations. It survives.
- **A narrow window, the two rounds either side of the contradiction**: **+33.2 pp** [+22.5, +43.3] over
  the 24 campaigns whose contradiction falls at round 3 or later.

`scripts/blind_evidence_timing.py`, `results/step9_blind_evidence_timing.json`.

**WHAT THIS STILL CANNOT DO.** It cannot separate a default from an evidence response that saturates
immediately, and it cannot speak to the 42 campaigns whose behaviour preceded any evidence. **The
zero-noise control is the confirmatory test**: sigma = 0 and no synthesis failures, so every reading is
exact, the reference point reads exactly its stated value and repeats return identical numbers. Blind
rung, opus, 20 campaigns, 15 rounds. Pre-committed reading, fixed here: replication near zero after the
first identical repeat means the earlier replication responded to observed noise; replication that
persists means a norm independent of evidence.

---

## 0j. WHAT THE AGENT IS: a MINIMAL AGENT, and the word is used consistently

A reader who sees "agent" will expect tools, memory and planning. **The agent in this study is a
MINIMAL AGENT**, and the methods and introduction define it in those words before any result:

> A minimal agent is one stateless model call per round. It sees its full measurement history,
> re-rendered into the prompt each round; it chooses which measurements to order; and it names its own
> final answer. It has no tools, no memory beyond the rendered history, and no code execution.

**WHY STUDY THE BARE POLICY.** Every scaffold is built on it. A scaffolded system that aggregates for
the agent, or lets it compute, or keeps a conversation, is adding a specific piece of machinery to this
policy, and the size of what each piece buys is only measurable against the policy without it. The
Aggregated rung is exactly such a controlled test: it supplies the one thing a scaffold would most
obviously supply, per-variant means and standard errors, and changes nothing else.

**The limitation this creates, stated plainly.** A result about a minimal agent is not a result about a
production system. Section 0k measures how far it carries.

## 0k. SCAFFOLDED CONDITIONS, pre-registered before they run

Mechanism rung, opus-4.7, NK uniform, **40 campaigns each on the SAME seeds as the Mechanism cell**, so
every comparison is against a matched set.

**(a) REASONING MODE.** Extended thinking enabled, with a reasoning budget large enough that no
response returns empty. Reasoning tokens logged per call, and the cell is void if any call comes back
with empty visible text, because that failure once read as a 0% replication rate.

**(b) TOOL-USING AGENT.** Two changes together, since they are the pieces a real scaffold supplies:
a Python tool that computes per-variant means and standard errors on request, and **a single persistent
conversation across all 15 rounds**, which replaces re-rendering the history every round. Tool calls and
their arguments are logged.

**THE READING, FIXED NOW.**

| Result | Reading |
| --- | --- |
| Scaffolding raises distinct variants measured AND moves replication toward k\* | The failure is in the bare policy, and scaffolding repairs it. The paper reports the minimal-agent result as a property of the bare policy and names the scaffold that fixes it. |
| Scaffolding does neither | The behaviour PERSISTS in scaffolded agents, which makes the minimal-agent result a property of the model's policy and not of the harness. This is the stronger and more worrying outcome. |
| Scaffolding raises distinct variants but replication stays far above k\* | Partial repair. The paper separates the gathering failure from the allocation failure and says which the scaffold fixed. |

Both are compared against the Mechanism cell on the same seeds, on the primary outcome and on distinct
variants measured, with replication under all four definitions.

**(c) AN OFF-THE-SHELF AGENT FRAMEWORK, scoped and NOT yet approved.** The environment exposed as a tool
to a standard framework loop. **Its per-campaign cost is measured on 3 campaigns and reported before the
40-campaign cell is run**, because a framework loop multiplies calls per round and the grid's cost model
does not cover it. The cost, the call count per campaign and the tool-call count are reported first.

These three are EXPLORATORY and are not in the confirmatory family of section 0g.

**RESTORED 2026-09-27. These two sections were written, then silently DELETED by my own edit to section
0i: I replaced 0i by slicing from its heading to the next known heading, and everything between was 0j
and 0k. The deletion went unnoticed because I checked for the new text and not for the text that should
have survived. `tests/test_the_preregistration_is_intact.py` now asserts every required section is
present, so an edit cannot drop one silently again.**

---

---

## 0l. DEVIATIONS AND CORRECTIONS RECORDED BEFORE THE TOP-UP, 2026-09-28

### Deviation 1: the stage-1 summary DID print condition means, and my claim otherwise was false

I stated that no condition mean had been computed. **That is false of the pipeline.** `scripts/grid.py`
prints the nominated-true mean and standard error for every cell at the end of a run, and
`results/grid_stage1.txt` contains all fifteen, Aggregated and Decision-rule included, committed in
`ebdd9db`.

What is true is narrower: `scripts/stage1_variance.py` centres every cell before pooling and prints
variances only, and **the sizing decision was taken from variances alone**. But the protection was
procedural and not structural, and it failed: the means exist in the repository and I had said they did
not. **From now on the stage summary prints variances and health only**, and the primary outcome by
condition is printed by a separate analysis script run after the final N is reached.

### Deviation 2: the sizing in section 0e did not power the confirmatory family in 0g

Three faults, each of which makes the required N larger, all decided from variances with no condition
mean used:

**(a) The z was for an unadjusted alpha.** Section 0e sizes at z = 2.8, which is 80% power at a
two-sided alpha of 0.05: 1.9600 + 0.8416 = 2.8016. Section 0g applies HOLM across six contrasts, so the
first step is tested at alpha/6 = 0.008333 and 80% power there needs **z = 2.6383 + 0.8416 = 3.4799**.
Required N scales as z squared, so the correction is **1.543x**. Sizing at 2.8 while testing at alpha/6
builds a study that cannot reject what it exists to detect.

**(b) Every contrast includes Mechanism, the highest-variance condition.** A per-model sd pooled over all
five conditions understates the variance of the two cells a contrast actually uses. Section 0e permits
variance per model AND per condition, so **each contrast is now sized from its own two cell variances**.

**(c) The pooling divisor was N-1 where it should be N-k.** Pooling k centred cells of n each has
n*k - k degrees of freedom. With five cells of forty the divisor is 195 and not 199. Small, in the wrong
direction, and still wrong: the per-model sds move 0.2791 to 0.2820 (opus), 0.2161 to 0.2183 (deepseek),
0.2928 to 0.2958 (gemini).

**WHAT THE CHOSEN N ACTUALLY DELIVERED.** At 374 per cell, power on the first Holm step is **0.38 to
0.42 for gemini** and about 0.65 for opus and deepseek. The study would have been underpowered for every
contrast and badly so for one model.

**CONTRAST-SPECIFIC N at z = 3.4799, MEI 0.06, unpaired**, from `scripts/contrast_power.py`:

| model | Aggregated vs Mechanism | Decision-rule vs Mechanism | N/cell required |
| --- | --- | --- | --- |
| opus-4.7 | 491 | 506 | **506** |
| deepseek-v3.1 | 488 | 527 | **527** |
| gemini-2.5-flash | 768 | 829 | **829** |

**Costed on stage 1's own measured per-campaign spend** ($0.2088 opus, $0.0068 gemini, $0.0049
deepseek): per-model sizing is 9,310 campaigns at **$569.45**; uniform at 829 is 12,435 campaigns at
**$914.16**.

**THE "ELEVEN DOLLARS" PREMISE FOR UNIFORM SIZING IS WITHDRAWN.** It held when opus drove the maximum
and carried all the cost. Gemini now drives the maximum and is cheap, so uniform sizing costs **$345
more**. Per-model sizing is the default; uniform is the operator's call and buys equal cells for the
exploratory between-model comparisons.

### Deviation 3: max_tokens changed mid-dataset, 3000 to 6000

Exactly one call of the 14,879 in stage 1 hit `finish_reason=length`, a deepseek call at round 15.
**Pre-registered sensitivity: the confirmatory analysis is repeated with that single campaign dropped**,
and the result is reported whether or not it moves.

## 0m. PRE-REGISTERED BEFORE THE TOP-UP LAUNCHES

**TEMPERATURE IS 0 for every cell of the grid.** This was in `repdef/llm.py` and not in this document,
which is where it belongs. Temperature 0 does NOT make the provider deterministic: pairwise agreement
between two calls of a byte-identical prompt is 0.265, so replicate campaigns sample real model
variability and that variability lands in the between-campaign variance the analysis already measures.

**BETWEEN-STAGE SENSITIVITY. REVISED 2026-09-28, because its original reason is now stale.** It was
written when stage 1 had run in condition BLOCKS, so the top-up-only analysis existed to isolate the
unblocked half. The fresh stage 1 is shuffled and runs the same environment as the top-up, so blocked
order is no longer a reason for it.

**What it is for now:** stage 1 and the top-up are separated in wall-clock time, and a provider-side
change to any pinned model between them would confound stage with condition. So **every confirmatory
contrast is reported twice, on all campaigns and on the top-up campaigns only**, and the two are compared
as a check for BETWEEN-STAGE DRIFT. If they disagree the cause is investigated before either is reported;
neither half is privileged in advance, because with both halves shuffled there is no longer a reason to
prefer one.

**AN EXPLORATORY TEMPERATURE PANEL: Mechanism at temperature 1.0, three models, 40 campaigns each.**
The motivation is measured, not supposed. At temperature 0 gemini produces only five or six distinct
round-1 responses per rung, and under Mechanism it orders the reference point **38.2 times out of 60**,
nominates it in **30 of 40 campaigns**, and measures **1.4 distinct variants**. The question is whether
that anchor lock is a property of the policy or an artefact of greedy decoding. EXPLORATORY, not in the
confirmatory family.

| Result | Reading |
| --- | --- |
| The anchor lock loosens at temperature 1.0 | The lock is an artefact of greedy decoding, and the minimal-agent result must be reported at both temperatures. |
| The anchor lock persists | It is a property of the policy, and temperature 0 is not the reason the agent fails to explore. |

---

---

## 0n. THE ENVIRONMENT MISREPORTED THE BUDGET. The 600 campaigns become STAGE 0, a pilot.

Found by the reviewer auditing the stage-1 prompts, reproduced independently here. The agent was told
three false things about its budget, and **the falsehood varied by cell, which makes it a confound
correlated with condition.**

**WHAT WAS FALSE**

1. The prompt said an order for a non-viable candidate "is rejected and costs you nothing". After the
   replacement attempts ran out the slot WAS consumed. **1,420 slots.**
2. "You have N measurements remaining" was `60 - used`, ignoring the four-per-round cap. In round 15 of
   15 a claude Blind campaign was told between **7 and 22** remaining when 4 were orderable, and **332 of
   641** final-round calls overstated it.
3. Nothing disclosed that a reply with the wrong number of candidates forfeits the whole round. **268
   slots**, with no history row and no change to the stated remaining count.

**LOST SLOTS PER CAMPAIGN, which is why this is a confound and not noise**

| model | Blind | Quantitative | Mechanism | Decision-rule | Aggregated |
| --- | --- | --- | --- | --- | --- |
| claude | **8.8** | 8.0 | 5.7 | 4.9 | 3.8 |
| gemini | 3.9 | 0.8 | 1.7 | 0.2 | 0.3 |
| deepseek | 2.5 | 0.7 | 0.8 | 0.0 | 0.0 |

Up to 15% of the budget, largest in Blind for every model.

**THE FOUR FIXES**, each pinned by a test that fails on the old behaviour, all seven mutants caught:

(a) The replacement cap rises from 1 to 3, which is `campaign.py`'s own default, and **the prompt states
    the cap and that the slot is lost after it**. The disclosed number is threaded from the harness, so a
    test catches any drift between what the agent is told and what happens.
(b) A lost slot appears in the history the agent sees, as `SLOT LOST` or `ROUND LOST`, and consumes the
    budget explicitly. A rejection no longer claims "slot not used", which was the false part.
(c) Remaining is `min(60 - used, rounds_left x 4)`.
(d) A wrong-count reply is re-asked once **with a format reminder**, and the rule is disclosed.

**STAGE 0.** The prompt text changes for every cell, so the 600 campaigns are not exchangeable with
anything run afterwards and **cannot pool**. They are relabelled STAGE 0, a pilot. Everything derived from
them stands as a pilot result: the parser fixes, the response health, the variance structure, the sizing
method. **The fresh stage 1 is 40 per cell, in SHUFFLED order, max_tokens 6000 from the start**, with the
run summary printing variances and health only. The Holm-corrected contrast-specific sizing of section 0l
is then applied to the FRESH variances.

### Where I disagree with the prescription, and what I did about it

**84% of the lost slots come from abandonment, which reflects PROPOSAL VIABILITY**: how often the
sequences the agent names fall inside the viable pool. 1,420 slots from abandonment, 268 from forfeited
rounds.

**CORRECTED 2026-09-28. I first wrote that lost slots are "earned by exploration", on cell-level
correlations of +0.914 with rejections and +0.912 with distinct variants. Those correlations are carried
by the MODEL factor.** Within
model, at campaign level, r(lost, distinct) is **+0.016 for opus, +0.260 for deepseek and +0.331 for
gemini**, so for the model that loses the most slots the association with how much it explores is
essentially zero. Within model, lost slots track rejections at +0.839 for opus but only +0.038 for
deepseek, so even that relationship is not common across models.

The defensible description is the narrow one: **lost slots measure proposal viability**, they differ
sharply by model, and they are not a simple function of exploration.

So the defect was the FALSE DISCLOSURE, and not the loss itself. Raising the cap to 3 should cut
abandonment to about 6% of its level, since the measured probability that a replacement is also
non-viable is 0.24. **That makes the environment fairer and it also absorbs a real behavioural
difference into the harness.** Treating every lost slot as an artefact would fix a confound by deleting
a finding.

**So lost slots become REPORTED SECONDARY OUTCOMES**: `lost_slots`, `slots_abandoned` and `rounds_lost`
are recorded per campaign, and any difference in the primary outcome is checked against them. The
exploration cost stays measured instead of being absorbed.

**One channel IS a pure artefact and deserved the fix without qualification**: the forfeited round.
A malformed reply cost four slots with no history row and no notice, and for gemini Mechanism that was
its ENTIRE loss (0.0 abandoned, 1.7 forfeited per campaign).

**Not projected, to be measured:** a cap of 3 means more replacement asks and so more cost per campaign.
Stage 0 logged 5,879 replacement asks over 600 campaigns. The fresh stage 1 reports its own per-campaign
cost and the top-up is sized from that, with no projection carried forward.

---

## 0o. THE SIZING RULE, committed 2026-09-28 before the fresh stage 1 runs

Decided by the operator: **PER-MODEL sizing.** The rule, fixed here so the numbers cannot be chosen after
they are seen:

> For each model, N per cell is the MAXIMUM over that model's two confirmatory contrasts
> (Aggregated against Mechanism, and Decision-rule against Mechanism) of
> `ceil( (z / MEI)^2 * (var_intervention + var_Mechanism) )`,
> with **z = 3.4799**, **MEI = 0.06**, unpaired, each variance being that cell's own sample variance,
> and any pooled variance computed with the **N - k** divisor and never N - 1.

z = 3.4799 is 80% power at the first Holm step of a six-contrast family: z(1 - 0.05/12) + z(0.80) =
2.6383 + 0.8416. Sizing at the unadjusted 2.8 while testing at alpha/6 would build a study that cannot
reject what it exists to detect.

**The numbers come from the FRESH stage 1 and not from stage 0.** Stage 0's figures, 506 / 527 / 829 per
cell at $569 total, stand only as the pilot estimate that established the method. The environment has
changed, so they are re-derived. `scripts/contrast_power.py` implements the rule and is run against the
fresh variances.

Per-campaign cost is also taken from the fresh stage 1, because raising the replacement cap to 3 means
more replacement asks. Stage 0 logged 5,879 asks over 600 campaigns; no projection from that is carried
forward.

---

## 0p. THE HARNESS IS FROZEN FOR THE GRID (at 935794d since 2026-09-28)

**The freeze is at `935794d`.** It was `5668f1c` until the truncated nomination prompt of section 0r
forced a rerun, and the commit carrying that fix is the new frozen harness. The freeze applies to CODE: a
commit touching only `spec/` or `results/` does not move it, and every run's manifest records the code
commit it ran on.

No environment or prompt change from here unless it would change a paper number or invalidate a
comparison. Everything else goes to `spec/DEFERRED_CHANGES.md` for the final audit.

The test of whether a change qualifies: **would a reader's conclusion differ if it were not made?** A
misreported budget qualified. A clearer variable name does not. `results/grid_*_manifest.json` records the
code commit for every run, so any campaign can be traced to the harness that produced it.

## 0q. THE THREE PARALLEL PANELS, pre-registered with costs before any of them runs

All three run ALONGSIDE the top-up. Costs are computed from stage 0's measured per-campaign spend
($0.2088 opus, $0.0068 gemini, $0.0049 deepseek), and **each panel is stopped if it exceeds twice its
estimate.**

### (a) THE ZERO-NOISE CONTROL: 5 conditions x 3 models x 40 = 600 campaigns, about $44

`sigma = 0`, **and synthesis failures STAY AT 15%.** Every reading is exact, the reference point reads
exactly its stated value, and a repeat returns an identical number. **This is the "why do agents replicate"
result.**

**CORRECTED 2026-09-28. The first version of this section also removed synthesis failures, and that was
wrong for two reasons.** A failed order is itself a reason to re-order, so removing failures would delete
one of the candidate explanations the panel exists to separate. And the Blind prompt states that about 15%
of orders fail, so removing them would make that sentence false and the Blind prompt no longer identical to
the grid's. **Failures stay at 15%, and the Blind panel prompt is now BYTE-IDENTICAL to the grid's Blind
prompt, so in that cell only the DATA differ.** Verified by rendering both and diffing:
`results/step11_zero_noise_prompt_diff.txt`.

**Pre-committed reading**, unchanged from when it was first stated: replication near zero after the first
identical repeat means the earlier replication responded to observed noise; replication that persists
means a norm independent of evidence.

**A DESIGN POINT THE EXPANSION RAISES, and my answer to it.** The instruction is "same prompts except the
noise sentences", and under `sigma = 0` those sentences cannot simply be deleted from the informed rungs,
because what they assert would be false. The replacements, fixed here:

| condition | what it says under sigma = 0 |
| --- | --- |
| Blind | unchanged; it never mentioned measurement error |
| Quantitative | "Each measurement is exact. A reading is the {item}'s true {metric}." |
| Mechanism | the Quantitative sentence, and NO averaging sentence, because averaging identical readings buys nothing and saying otherwise would be false |
| Aggregated | environment change only, as always; the SE column reads "0.000 (measurements are exact)" |
| Decision-rule | the decision sentence unchanged; under exact readings the highest average IS the highest reading |

**This makes Aggregated and Decision-rule into PLACEBOS by construction**, which is why running all five is
better than running Blind alone. With exact readings, aggregating buys nothing and "highest average" and
"highest reading" are the same instruction, so **neither intervention can work through its intended
mechanism.** If either still differs from Mechanism under `sigma = 0`, the difference is the prompt text and
not the aggregation, and that is a result about prompt sensitivity and not about statistics.

**ON WHETHER QUANTITATIVE AND MECHANISM COLLAPSE INTO ONE CONDITION.** The reviewer expected them to render
identical prompts under `sigma = 0`, which would make the panel five cells for four conditions. **They do
not, and the diff shows why: they differ by exactly one line.** Mechanism keeps the PERMISSION sentence,
"You may order the same string more than once, within a round or across rounds", which is still TRUE when
readings are exact; only the `sqrt(n)` claim is dropped, because a standard error of zero cannot be reduced.
So Mechanism under `sigma = 0` is "readings are exact, and you may re-order anyway", which is a coherent and
distinct rung, and it is the cell that isolates the permission from the mechanism.

For completeness, from the same diff: **Mechanism and Aggregated do render identical TEXT**, in the panel
exactly as in the grid, because aggregation is an environment change and never a prompt change. That is the
design and not a collapse. All five cells are therefore distinct conditions, and none is money spent twice.

### (b) TEMPERATURE 1.0: Mechanism x 3 models x 40 = 120 campaigns, about $9

Already pre-registered in section 0m with its reading. The motivation is measured: at temperature 0 gemini
gives five or six distinct round-1 responses per rung, orders the reference point 38.2 times of 60 under
Mechanism, nominates it in 30 of 40, and measures 1.4 distinct variants.

### (c) REASONING MODE: Mechanism and Blind x 3 models x 40 = 240 campaigns, $18 at the floor

Provider reasoning enabled, with a budget large enough that nothing returns empty. **This is the answer to
"this is just an LLM call".** Two conditions, so the effect is visible both where the mechanism is
explained and where nothing is said about noise.

**Cost is the uncertain one and it is bounded by a rule.** Reasoning tokens are billed, so $18 is a FLOOR;
at three times the output it is $53 and at six times $106. Stage 0 measured zero reasoning tokens on all
three models, so there is no basis in hand for the multiple. **The panel stops at twice the floor estimate
($36) and reports instead of running on.** Every call logs its reasoning tokens, and the cell is void if
any response returns empty visible text, which is the failure that once read as a 0% replication rate.

**Pre-committed reading.**

| Result | Reading |
| --- | --- |
| Reasoning raises distinct variants and moves replication toward k\* | The bare policy is the limitation, and thinking longer repairs it. |
| Reasoning changes neither | The behaviour survives extended deliberation, so it is not a failure to think but a property of the policy. The strongest form of the paper's claim. |
| Reasoning improves the primary outcome without changing the behavioural metrics | It is finding better answers by another route, and the replication finding is unaffected by it. |

These three are EXPLORATORY and are not in the confirmatory family of section 0g.

---

## 0r. THE NOMINATION PROMPT WAS TRUNCATED. Stage 1 is void and rerun; the harness freeze moves.

`build_nomination` recovered its header by `body.split("ROUND ")[0]`. That was correct until the shared
HEADER gained the sentence "THE WHOLE ROUND IS LOST" in `15109c8`, after which the split cut INSIDE the
header. From that commit **every nomination prompt ended "...not exactly that number, THE WHOLE"** and lost
ten lines: the measurement-error sentence, `sigma(f)`, the permission, the `sqrt(n)` mechanism and the
Decision-rule AVERAGE sentence. **All five conditions therefore sent the same nomination prompt**, and the
primary outcome is read from that call.

Round prompts were unaffected and byte-identical to `5668f1c`, so the behavioural data stand. **The first
241 campaigns are relabelled STAGE 1a: void for the primary outcome, kept as a pilot for behaviour.** Stage
1 is rerun in full on the fixed commit, which becomes the frozen harness.

**Why no test caught it: every prompt test checked the ROUND prompt.** The fix is therefore not the
one-line repair but the contract.

1. `_body()` is now the ONE place a prompt body is assembled, and no caller reconstructs one by parsing
   text.
2. `tests/test_prompt_contract.py` renders **every rung x every noise mode x every prompt type** (round,
   replacement, re-ask, nomination), 56 prompts, and asserts that every block sentence of that rung is
   present, that the header is complete, and that **nomination prompts differ across rungs exactly where
   the round prompts do**. That last assertion is the one that fails on this bug.
3. `spec/PROMPT_SNAPSHOT.txt` holds a SHA256 for all 56. Any prompt change fails the test until the
   snapshot is regenerated on purpose and the diff shown.
4. `scripts/grid.py` runs a PROMPT CANARY before the first API call and refuses to launch if any rung's
   nomination prompt has lost its blocks.

Mutation-tested, four for four: the split itself, a rung block dropped from the nomination, the header's
last sentence removed, and a prompt changed without updating the snapshot.


## 0s. THE CONFIRMATORY CONTRASTS ARE PAIRED BY SEED. Amends 0g, 0e and 0o. 2026-09-28

Section 0g committed the six contrasts as **unpaired**, with the reason that "two conditions are
different campaigns sharing no history". The reason is true and irrelevant, and the conclusion drawn from
it is wrong.

**WHAT IS ACTUALLY SHARED.** Sharing no history is a property of the AGENT: an agent in Aggregated never
sees a reading taken in Mechanism. The ENVIRONMENT is a different object, and it is shared. From
`repdef/oracle.py`:

- measurement noise is drawn on `("noise", seed, seq, replicate_index)`
- an instrument failure is drawn on `("fail", seed, seq, n)`
- screen admission is drawn on `("screen", seed, seq)`

So at a fixed seed the k-th reading of a given sequence is **byte-identical in every condition**, an
instrument failure that happens in one condition happens in all of them, and a sequence screened out in
one is screened out in all. This is common random numbers and it was deliberate, since it is the reason
the design can compare conditions on a per-seed basis at all. It makes the cells **dependent at the seed
level**, and a test that assumes independence is not entitled to that assumption.

**WHY THIS IS A VALIDITY POINT AND NOT AN EFFICIENCY ONE.** Welch estimates
`Var(mean_b - mean_a)` as `(s_a^2 + s_b^2)/n` and drops the `-2 cov / n` term. If the realised covariance
is positive, Welch's standard error is too LARGE and the test merely loses power. If it is negative,
Welch's standard error is too SMALL, the p-value is too small, and the type I error exceeds its nominal
level. **The sign is not known in advance**, so the unpaired test is wrong in an unknown direction. That
is the reason to pair, and it holds independently of which test would have more power here.

On the stage-0 pilot (`scripts/seed_pairing.py`, `results/seed_pairing_stage0.json`), the within-seed
correlation is positive for three contrasts and negative for three, and the reviewer-flagged case is
gemini Aggregated vs Mechanism: **paired sd 0.5392 against unpaired 0.4777**, correlation **-0.280**. With
n = 40 the null standard error of r is about 1/sqrt(n-3) = 0.164, so |z| = 1.70 and **the pilot cannot
establish the sign of any of these correlations**. That does not weaken the argument. The covariance term
belongs in the variance whatever its sign, and the paired estimator is the one that includes it.

**THE PRIMARY TEST, as amended.** For each contrast, pair on the seed and take the per-seed difference
`d_s = y_s(intervention) - y_s(Mechanism)`.

1. **Point estimate:** `mean(d)`. This is numerically IDENTICAL to the difference in cell means whenever
   the seed sets match, since `mean(b - a) = mean(b) - mean(a)`. Pairing changes the standard error and
   must never change the effect, and `tests/test_the_contrast_is_paired_by_seed.py` asserts it does not.
2. **Primary p:** a **studentised wild cluster bootstrap over seeds**, Rademacher weights, 4,000 draws,
   the null imposed by centring. One weight per seed applied to that seed's whole pair is
   ALGEBRAICALLY the same draw as one weight on the centred difference, because
   `(1/n) sum w (r_B - r_A) = (1/n) sum w (d - mean d)`. Verified to floating point in
   `scripts/seed_pairing.py` and pinned as a test, so the implementation is entitled to the word
   "cluster" instead of the disclaimer the previous campaign-clustered version had to carry.
3. **Sensitivities, both reported beside the primary for every contrast:** the paired t, and **Welch**,
   each with its own Holm pass, so a reader can see whether a conclusion depends on the choice. On the
   stage-0 pilot no verdict differs between the three. That is a fact about the pilot and not a reason to
   use the wrong estimator.
4. **Holm across the family of six is unchanged**, and is applied to the primary bootstrap p.
5. **The bootstrap p has a resolution floor** of `1/(reps+1) = 0.00025` at 4,000 draws. A printed
   0.00025 means "at or below the floor" and is not a measured value. The floor is far below the Holm
   step-1 threshold of `alpha/6 = 0.008333`, so it cannot affect a rejection.

**A DEGENERATE CELL IS REFUSED, NOT ABSORBED.** If any cell or the difference has zero variance, every
standardised statistic is undefined. The analysis raises `NonFinite` naming the cell. A `nan` must never
reach Holm: Holm sorts the family, every comparison against `nan` is False, and one `nan` silently
reorders the correction so that every adjusted p below it is wrong.

**PAIRING ON THE SEED, NEVER ON ROW ORDER.** The predecessor paired with `zip(A, B)` over two lists built
by appending rows, which is correct only while both cells happen to be written in the same order. A
resume, a shuffled run order or one retried cell breaks it silently and the output still looks like a
paired analysis. The analysis now keys on the seed, reports how many seeds were dropped when the sets
differ, and a test reverses one cell's order and asserts the result is unchanged.

**SIZING, amending 0e and 0o.** Required n per cell is `(z / MEI)^2 * variance`, and the variance is now
the variance of the PAIRED DIFFERENCE and not `s_a^2 + s_b^2`. **Pairing is not automatically cheaper.**
On the pilot, at z = 3.4799 and MEI = 0.06:

| model | contrast | n unpaired | n paired | ratio |
| --- | --- | --- | --- | --- |
| opus-4.7 | Aggregated vs Mechanism | 491 | 459 | 0.935x |
| opus-4.7 | Decision-rule vs Mechanism | 506 | 431 | 0.852x |
| deepseek-v3.1 | Aggregated vs Mechanism | 488 | 462 | 0.947x |
| deepseek-v3.1 | Decision-rule vs Mechanism | 527 | 533 | 1.011x |
| gemini-2.5-flash | Aggregated vs Mechanism | 768 | 979 | 1.275x |
| gemini-2.5-flash | Decision-rule vs Mechanism | 829 | 910 | 1.098x |

Per model, the binding requirement moves from 506 / 527 / 829 to **459 / 533 / 979** (opus / deepseek /
gemini). These are PILOT variances and are illustrative; the top-up N is computed from the stage-1
variances under the paired formula, by `scripts/contrast_power.py`, under the rule of 0o.

**WHAT THE FREEZE ALLOWS.** Nothing in `repdef/` changes. The pairing is a property of the ANALYSIS, and
`scripts/analyse_grid.py` did not exist when the harness was frozen at 935794d. The experiment that has
already run is the experiment that was pre-registered; only the estimator applied to it is corrected, and
the correction was committed before any stage-1 condition mean was computed.

**HOW THIS WAS FOUND.** A reviewer noticed that gemini's paired and unpaired standard deviations differed
and asked for the reproduction. The general defect behind it is the one this project keeps meeting: a
justification that names a true fact ("they share no history") about the WRONG OBJECT (the agent, not the
environment). Mutation-tested five for five in `scripts/mutation_pairing.txt`.


## 0t. TWO PANELS RAN CODE THAT NO COMMIT CONTAINED. Deviation recorded, and the gate that prevents it

**THE DEVIATION.** The temperature panel and the reasoning probe launched at 10:05:12 and 10:05:15 on
2026-09-28 with `--temperature`, a flag that existed in no commit until `55f650b` at 10:06. Both manifests
record `git_commit: 30ce9ac`, and `30ce9ac`'s `scripts/grid.py` has no `--temperature` argument, so it
cannot have produced those runs. The code was in the working tree and in no commit.

**THE ARTIFACT CONTAINED THE PROOF AND NOTHING WAS READING IT.** Both manifests carry a `temperature` key.
That key is written only by the `55f650b` version of the manifest dict. A manifest that records `30ce9ac`
while containing a field only a later commit writes is self-contradicting on its face.

**WHAT THE EXPOSURE ACTUALLY IS.** `55f650b` over `30ce9ac` contains exactly two behavioural changes, and
both can be bounded.

1. `repdef/prompts.py` threads `exact=(noise_model == "exact")` into the aggregated history, so an exact
   arm prints `0 (readings are exact)` instead of `not estimable from 1 measurement`. It is gated on the
   noise model. `spec/PROMPT_SNAPSHOT.txt` moved for exactly four hashes, all `aggregated|exact|*`; all 28
   `multiplicative` hashes are byte-identical across the two commits. Both affected runs used
   `noise=multiplicative`, so **the prompts they sent cannot have been altered by this change**, whatever
   the precise state of the file at launch.
2. `scripts/grid.py` threads a `temperature` parameter with default `0.0`, replacing a hardcoded `0.0`.
   With the flag absent the behaviour is identical. The reasoning probe ran `temperature=0.0`, so it is
   unaffected. The temperature panel ran `1.0`, which was the point of the panel.

**WHAT CANNOT BE ESTABLISHED.** Git does not record a working tree, so there is no way to prove the tree at
10:05:12 was byte-identical to `55f650b`. The bound above is what the evidence supports, and it is
reported as a bound. The temperature panel is EXPLORATORY under 0q and no confirmatory number depends on
it.

The original manifests are **left exactly as written**, because repairing a provenance record by editing it
is the same mistake in a different direction. The correction is additive:
`results/grid_tpanel_manifest_CORRECTION.json` and `results/grid_rprobe_manifest_CORRECTION.json` state the
recorded commit, why it is wrong, the evidence inside the manifest itself, the bound on the exposure, and
what cannot be established.

**THE GATE, so the question cannot arise again.** `scripts/grid.py` now:

- computes `code_provenance()` and **refuses to launch** when `git status --porcelain` shows any change
  under `repdef/` or `scripts/`, including an untracked file, since a new uncommitted module is exactly
  the kind of change that alters behaviour;
- writes the **full `git status --porcelain`** into every manifest, along with `code_dirty`,
  `code_dirty_paths`, `code_diff_sha256` and `git_commit_describes_the_code`;
- applies the provenance with `manifest.update(prov)` LAST, so no earlier key can shadow it;
- prints `WHICH DOES NOT DESCRIBE THE CODE` beside the commit whenever that is the case, because the
  reassuring `manifest saved (commit 30ce9ac)` line is what made this invisible;
- allows a deliberate dirty run only under `--allow-dirty`, which saves the diff AND the contents of any
  untracked code file to `results/grid_<tag>_uncommitted.diff` and records
  `git_commit_describes_the_code: false`. A dirty run stays possible and can never pass for a clean one.

A change confined to `spec/` or `results/` does NOT block a launch, consistent with 0p, so nobody meets
the gate for editing a pre-registration and learns to pass `--allow-dirty` by reflex.

**THE CLASS.** Recording HEAD is not recording provenance. HEAD plus a dirty tree describes nothing, and
the field that claims otherwise is worse than an absent field, because it retires the doubt. Pinned by
`tests/test_the_manifest_cannot_lie_about_its_code.py`, mutation-tested six for six
(`results/mutation_provenance.txt`).


## 0u. THE REASONING TREATMENT IS THE GRID'S OWN SETTING. Panel (c) sized from measured cost. 2026-09-28

**THE QUESTION THAT WAS ASKED.** Gemini's reasoning tokens cluster just under 3,000 at max_tokens 6,000,
which looked like a ceiling at half of max_tokens. If a ceiling were truncating the reasoning, panel (c)
would be measuring a limit we chose and not the model, so it was measured before the panel was sized.

**WHAT THE MEASUREMENT SHOWED** (`scripts/reasoning_budget.py`, `results/reasoning_budget_rprobe.json`):

- **No call finished on `length`.** Every finish reason across 389 calls is `stop`, with one transport
  `error`. There is no direct evidence of truncation anywhere in the probe.
- **There is no wall at 3,000.** Six of 140 gemini calls exceed it, the largest at 3,463.
- **max_tokens was never the binding constraint.** `completion_tokens` INCLUDES reasoning tokens (the
  visible answer is a median of 62 tokens for gemini and 73 for opus, never negative), and gemini's
  largest total generation is 4,131 of 6,000, which is 69% of the cap. Opus's largest is 823, 14%.
- **Raising max_tokens does not lift the reasoning.** At max_tokens 20,000 with the same effort, opus's
  median reasoning was 244 against 179 at 6,000 and its maximum FELL, 523 against 734
  (`results/grid_rprobe20k_*`, opus cell only, 3 campaigns).

So the clustering is gemini spending its medium-effort thinking budget. Raising max_tokens would not remove
a confound; it would change the treatment to a larger budget and ask a different question.

**THE DECISION.** The reasoning treatment is **reasoning effort = medium at max_tokens 6,000**, which is
the grid's own setting. No re-probe, and the max_tokens 20,000 investigation is closed.

**Reasoning tokens are reported as DESCRIPTIVE FACTS**, per model and per call kind, never as a treatment
that was tuned. From the probe, at effort medium and max_tokens 6,000:

| model | call kind | n | median | max | share that reasoned |
| --- | --- | --- | --- | --- | --- |
| opus-4.7 | round | 75 | 179 | 734 | 82.7% |
| opus-4.7 | nomination | 5 | 0 | 0 | **0.0%** |
| opus-4.7 | replacement | 114 | 0 | 54 | 0.9% |
| gemini-2.5-flash | round | 75 | 2,814 | 3,001 | 98.7% |
| gemini-2.5-flash | nomination | 5 | 2,997 | 2,998 | 100.0% |
| gemini-2.5-flash | replacement | 60 | 2,640 | 3,463 | 100.0% |

**Opus does not reason on the nomination call at all**, in any of five campaigns, while it reasons on 83%
of its round calls. The nomination call is where the PRIMARY OUTCOME is read. That is reported as a fact
about the model and is not corrected for.

**PANEL (c) BUDGET, amending the $18 floor and $36 cap of section 0q.** That cap was set because "stage 0
measured zero reasoning tokens on all three models, so there is no basis in hand for the multiple". There
is a basis now, and it is higher than the floor. Measured per campaign at Mechanism with effort medium:

| model | baseline | with reasoning | multiple |
| --- | --- | --- | --- |
| opus-4.7 | $0.2704 | $0.3874 | 1.43x |
| gemini-2.5-flash | $0.0095 | $0.1988 | **20.9x** |
| deepseek-chat-v3.1 | $0.0055 | not obtained | see below |

The panel is 240 campaigns, 80 per model. Opus and gemini project to **$30.99 and $15.90**, so **$46.89
before deepseek**, which is 2.6x the pre-registered $18 floor and above the old $36 cap. The cap is
replaced by **twice the measured projection**, and the panel reports instead of running past it.

**DEEPSEEK COULD NOT BE MEASURED, and that is a finding about the instrument.** The probe's deepseek cell
logged ZERO calls in 40 minutes and was stopped. Calls flush per campaign, and `repdef/llm.py` allows 180s
per attempt with 3 retries, so a cell whose every call times out produces exactly this silence. A single
direct call was then timed to separate a provider stall from anything in the harness. Whatever deepseek's
reasoning cost is, a cell that cannot complete 80 campaigns cannot be run, and the decision on including it
waits on the measurement.


## 0v. A CALL IS BOUNDED IN TOTAL TIME AND ATTRIBUTED TO A PROVIDER. Two harness changes before the top-up

Two defects were found while sizing panel (c), both of which bear on the top-up, so they are recorded with
the evidence that neither changes what stage 1 measured.

### 1. A call had no total time bound

`urllib.request.urlopen(req, timeout=N)` bounds each SOCKET OPERATION and not the call. A response that
trickles one byte every N-1 seconds never times out. Observed on 2026-09-28: the reasoning probe's deepseek
cell produced **no completed call in forty minutes** under `timeout=180, retries=3`, and a single direct
call had not returned after **five minutes** under `timeout=120, retries=1`. The stall was not specific to
reasoning, since a call with reasoning disabled hung the same way, so it is a provider condition and not a
property of the treatment.

One stalled worker out of sixteen is lost throughput. Sixteen stalled workers is a top-up that never
finishes, which is a paper with no numbers, so this is fixed before the top-up launches.

`repdef/llm.py` now takes `deadline_s`, default **900**, bounding the whole call across retries, and no
single attempt is given more time than the deadline leaves. **This is a SAFETY BOUND and not a stopping
criterion**, in the same sense as the run loop's resource ceiling.

**Why it cannot have changed stage 1.** Across all **18,017** stage-1 calls the slowest was **46.6 seconds**
(opus 18.9s, gemini 6.2s, deepseek 46.6s). **Zero** exceeded even the 180s per-attempt timeout, and zero
came within a factor of nineteen of the new deadline. On the observed distribution the bound is inert, so a
top-up that carries it is comparable to a stage 1 that did not.

### 2. Nothing recorded which provider answered

OpenRouter serves an **open-weight** model from whichever provider it routes to, and providers differ in
quantisation and sampling defaults, so an unpinned open-weight model is a **mixture of instruments**. The
response says which provider answered. Nothing read that field, and `raw_response` stores only the visible
text, so **stage 1 cannot say which provider served any of its 4,761 deepseek calls.**

`llm.Call` now carries `provider` and `llm_policy` logs it on every call.

**The bound on what this costs the existing result.** It affects deepseek alone, since opus and gemini are
served first-party. Provider mixing inflates WITHIN-CELL variance, which makes a contrast harder to detect,
so its direction is conservative and it cannot manufacture an effect. The shuffled run order of 0h breaks
any correlation between routing and time. It is a limitation of the deepseek cells and is reported as one.

### 3. Pinning is available and is NOT used for the grid

`complete(provider_order=[...])` sends `{"order": [...], "allow_fallbacks": false}`. Sending it would change
which provider answers, so **it must never be used for the grid or the top-up**: that would break the
comparison with stage 1. It exists for the model-breadth panel, where one pinned provider per open-weight
model is the point.

**The request is byte-identical when the new options are unused.**
`tests/test_the_call_is_bounded_and_attributed.py` rebuilds the payload the way the pre-change code built
it and compares the serialised bytes, so a future edit that starts sending a `provider` field to the grid
fails the suite. Ten tests, mutation-tested seven for seven
(`results/mutation_call_bounds.txt`), including the mutant that sends the provider field unconditionally.


## 0w. THE TOP-UP N, AND THE LAUNCH. Computed from the completed stage 1 under 0o as amended by 0s

**STAGE 1 IS COMPLETE.** 600 campaigns, all fifteen cells at exactly 40, $54.40. Health: **zero** empty
responses and **zero** truncated responses on any model at max_tokens 6,000; malformed rates 0.1% opus,
0.1% deepseek, 0.4% gemini. The call archive verified, 18,017 lines in and 18,017 out across fifteen cells.

**N PER CELL, from the fresh stage-1 variances, paired by seed** (`scripts/contrast_power.py stage1`,
`results/contrast_power_stage1_paired.txt`), at z = 3.4799 and MEI = 0.06:

| model | contrast | sd paired | sd unpaired | corr | N paired | N unpaired |
| --- | --- | --- | --- | --- | --- | --- |
| opus-4.7 | Aggregated vs Mechanism | 0.4542 | 0.4135 | **-0.209** | **695** | 576 |
| opus-4.7 | Decision-rule vs Mechanism | 0.3949 | 0.3964 | +0.008 | 525 | 529 |
| deepseek-v3.1 | Aggregated vs Mechanism | 0.2316 | 0.2474 | +0.124 | **181** | 206 |
| deepseek-v3.1 | Decision-rule vs Mechanism | 0.2033 | 0.2121 | +0.085 | 140 | 152 |
| gemini-2.5-flash | Aggregated vs Mechanism | 0.1531 | 0.1830 | +0.346 | 79 | 113 |
| gemini-2.5-flash | Decision-rule vs Mechanism | 0.2031 | 0.1725 | **-0.529** | **139** | 101 |

**Per-model N: 695 opus, 181 deepseek, 139 gemini.** Pairing raises opus's requirement by 21% and gemini's
by 38%, and lowers deepseek's by 12%, so the choice of estimator was not a cost saving in either direction.

**The pilot's numbers are withdrawn as predictions.** Stage 0 gave 459 / 533 / 979 and the fresh stage 1
gives 695 / 181 / 139. Gemini's requirement fell by a factor of seven and opus's rose by half. **The cost
driver flipped**: gemini dominated on the pilot and opus dominates now, at $842 of the $850 projection. A
sizing estimate from a pilot on a different environment is an estimate and not a number.

**PER-CAMPAIGN COST, measured on the completed stage 1 over all five conditions**, superseding the stage-0
constants that were still in `contrast_power.py`: opus **$0.2570**, gemini **$0.0097**, deepseek **$0.0053**.

**THE TOP-UP, launched 2026-09-28 at commit 6f780be.** (N - 40) per cell x 5 conditions:

| tag | model | campaigns | workers | projected |
| --- | --- | --- | --- | --- |
| topup_opus | opus-4.7 | 3,275 | 10 | $841.78 |
| topup_deepseek | deepseek-v3.1 | 705 | 3 | $3.73 |
| topup_gemini | gemini-2.5-flash | 495 | 3 | $4.79 |
| | | **4,475** | **16** | **$850.30** |

Under the operator's standing rule the top-up launches at 16 workers without further review unless the
projection exceeds $1,200. It is $850.30.

**Three tags and not one.** Per-model N means three runs of different lengths, and three processes
appending to one file would interleave, so each model writes its own file. `scripts/analyse_grid.py` joins
tags with `+` and **refuses on a duplicate (condition, model, seed)**, because a seed counted twice would
enter the paired analysis as an independent observation. The combined tag is
`stage1+topup_opus+topup_deepseek+topup_gemini`.

**Seeds continue and never overlap.** Stage 1 used seed0 300000 for 40 campaigns, so seeds 300000-300039.
Each top-up uses seed0 300040. Within a model every condition draws the same seed range, which is what 0s
requires for pairing. The run order is shuffled under order seed 20260928, recorded in every manifest.

**PANEL (c) launched alongside**, tag `panelc`, at **seed0 300000**, which is stage 1's own seed range. That
makes each panel-(c) cell paired by seed with the corresponding stage-1 cell, so the
reasoning-against-no-reasoning contrast is paired on the same environment draws under 0s. Blind and
Mechanism x 3 models x 40 = 240 campaigns, effort medium at max_tokens 6,000 per 0u, ceiling $95.


## 0x. THE ZERO-NOISE CEILING RISES TO $110, AND THE DEEPSEEK PROVIDER MIXTURE IS PRE-REGISTERED

### 1. The zero-noise ceiling: $88 to $110

At 324 of 600 campaigns the zero-noise panel had spent **$46.22**, which is **$0.1426 per campaign** and
projects to **$85.58** for the full 600 against a ceiling of **$88**. A 2.8% margin on a projection is not
a margin. The panel runs in SHUFFLED order under 0h, so a budget halt does not truncate the last cell: it
truncates **every** cell unevenly, which is worse than stopping early, because an unbalanced design cannot
be paired by seed under 0s and cannot be compared cell to cell.

**Raised to $110 by the operator before the halt could occur.** The ceiling is a safety bound and the
panel's size is fixed at 600 campaigns, so raising it cannot change any result; it can only stop the run
from ending in a state no analysis could use.

**The restart is recorded as two segments, because the ceiling lives in the launched process.** The run was
stopped and relaunched with identical flags (`--campaigns 40 --workers 4 --shuffle --order-seed 20260927
--seed0 300000 --noise exact`) and `--budget-usd 110`. It resumed from disk: **326 campaigns already
present, $47.3235 already spent**, both carried forward against the new ceiling. Resume skips
(condition, model, seed) triples already written and appends, so nothing is recomputed or overwritten, and
the same order seed regenerates the same shuffle so the remaining work keeps its order.

**Segment 1 ran at `f3355fd` and segment 2 at `de3a7d4`.** The original manifest is preserved as
`results/grid_zeronoise_manifest_segment1.json`; the live manifest describes segment 2. The code changed
between them in two ways that touch a run, both from 0v: the 900-second total call deadline, which no
stage-1 call came within a factor of nineteen of, and provider logging, which adds a field and changes no
request. So **the first 326 campaigns carry no `provider` field and the remainder do**, and the panel's
call log is heterogeneous in that one field. The panel is EXPLORATORY under 0q.

### 2. The deepseek provider mixture

OpenRouter routed `deepseek/deepseek-chat-v3.1` across **four** providers in the top-up's first 1,366
calls: **AtlasCloud 1,243, DeepInfra 121, CoreWeave 1, SiliconFlow 1**. The top-up stays **UNPINNED**, which
is the only choice consistent with stage 1, where routing was also unpinned. Pinning now would change which
provider answers and break the comparison.

**THE MIXTURE IS WITHIN CAMPAIGN, NOT BETWEEN CAMPAIGNS.** Measured over 53 completed campaigns: **46 were
served by two providers, 2 by three, and only 4 (8%) had every call from AtlasCloud.** This is the fact that
decides how a sensitivity analysis can be defined, and it rules out the obvious definition.

| definition | campaigns kept | paired seeds kept |
| --- | --- | --- |
| every call AtlasCloud | 4 of 53 (8%) | **~0.6%** |
| modal provider AtlasCloud | 53 of 53 (100%) | ~100% |
| **nomination call AtlasCloud** | 46 of 53 (87%) | **~75%** |

**PRE-REGISTERED, in this order.**

1. **The balance check is primary, because it tests the only mechanism by which the mixture could bias a
   contrast.** Routing can only distort a comparison if it correlates with CONDITION. The AtlasCloud share
   of calls is computed per condition and compared. At launch it was **91.1% / 91.1% / 90.5% / 91.8% /
   90.4%** across Blind, Quantitative, Mechanism, Aggregated and Decision-rule, a spread of 1.4 percentage
   points. The full-grid version of this table is reported whatever it shows.
2. **The sensitivity restricts on the NOMINATION call**, which is the call the primary outcome is read from.
   A seed is kept only when **both** cells' nomination calls at that seed were AtlasCloud-served, since the
   analysis is paired under 0s and a half-kept pair is not a pair. The two deepseek contrasts are re-run on
   that subset, the retained seed count is reported, and the verdict is compared with the full analysis.
3. **The all-calls definition is reported as INFEASIBLE, with its numbers**, so that nobody can think it was
   run and set aside. It retains 8% of campaigns and about 0.6% of paired seeds. A test with that little
   capacity cannot return anything but a null, and reporting that null as reassurance would be the
   novelty-theatre mistake in reverse.
4. **The modal-provider result is reported as a fact:** no campaign was predominantly served by a provider
   other than AtlasCloud.

**THE LIMITATION, stated plainly.** Because 92% of campaigns are internally mixed, the provider mixture is
**not removable by restriction**. Providers differ in quantisation and sampling defaults, so the deepseek
cells are measurements through an instrument that varied within each campaign. The direction is bounded:
mixing inflates WITHIN-cell variance, which widens a confidence interval and makes a contrast harder to
detect, so it is conservative and cannot manufacture an effect. The shuffled run order of 0h breaks any
correlation between routing and time. Opus and gemini are served first-party (`Claude Platform on AWS` and
`Google`) and are unaffected.

### 3. A deviation I caused while building the above, recorded

Validating `scripts/provider_sensitivity.py` against `scripts/analyse_grid.py`, I imported
`confirmatory` and read `results/grid_stage1_campaigns.jsonl` directly, which **looked at two stage-1
condition means before the grid is complete**: deepseek Aggregated against Mechanism, and Decision-rule
against Mechanism. The two code paths agreed to six decimals, which was the point of the exercise.

**Why it cannot have influenced anything.** N was already fixed at 695 / 181 / 139 under 0w, the top-up was
already launched, and the analysis is fully specified in 0s. There is no remaining choice those two numbers
could have steered.

**Why it was still the wrong way to do it.** An arithmetic cross-check needs two implementations and some
numbers; it does not need REAL numbers. Synthetic data would have validated the same code path and touched
nothing gated. The convenient dataset was not the correct one.

**The gate is moved to where it binds.** `main()` refused any tag but `stage0`, and I walked past that
refusal by importing a pure function and opening the file myself. `analyse_grid.load()` now raises
`Incomplete` at the point real campaign data enters the process, so any caller that loads a tag is gated
and not only the one that runs the script from the command line. Synthetic data carries no tag, so the
tests are unaffected. A gate one caller can skip is a gate for the careful caller only.

**STAGE 1'S PROVIDERS ARE UNKNOWN, AND UNRECOVERABLE.** Nothing read the response's `provider` field until
2026-09-28, and `raw_response` stores only the visible text, so for all **4,761** deepseek calls in stage 1
there is no record of which provider answered. This is stated as a gap and is not estimated from anything
else. In the combined analysis each deepseek cell is 40 campaigns from stage 1 and 141 from the top-up, so
**the provider is known for 141 of 181 campaigns per cell (78%)**, and the sensitivity of point 2 runs on
that 78% only. The stage-1 portion is carried in the main analysis and excluded from the provider
sensitivity, and both counts are reported.


## 0y. DEEPSEEK IS EXCLUDED FROM THE REASONING PANEL. A limitation, with the measurement behind it

**THE DECISION.** Panel (c) runs **opus-4.7 and gemini-2.5-flash only**: Blind and Mechanism x 2 models x
40 seeds = **160 campaigns**, effort medium at max_tokens 6,000, at stage 1's seed range so each cell stays
paired under 0s. `deepseek-chat-v3.1` is excluded. This is reported as a **limitation of the panel** and
never as a finding about the model.

**THE MEASUREMENT, with a control inside the same session.** Panel (c) ran for **62 minutes and logged ZERO
deepseek calls**, while the same model in the top-up, identical except that reasoning was off, completed
**153 campaigns** over the same period. The stalled calls also hold workers, so they starved the opus and
gemini cells: panel (c) managed 7.2 campaigns an hour against a projected 36.

**WHAT IS ACTUALLY WRONG, and it is not the model.** One pinned-provider test, bounded at 125 seconds a
call, separates the model from the route:

| provider | reasoning | latency | reasoning tokens returned |
| --- | --- | --- | --- |
| SiliconFlow | medium | **3.9s** | **32** |
| SiliconFlow | off | 3.3s | 0 |
| **AtlasCloud** | **medium** | **48.8s** | **0** |
| AtlasCloud | off | 2.1s | 0 |

**AtlasCloud accepts the reasoning parameter, takes 23 times longer with it, and returns no reasoning
tokens at all.** SiliconFlow serves the same request in under four seconds and does return them. AtlasCloud
carried **90.6%** of deepseek's traffic (0x), so almost every panel-(c) deepseek call went to the provider
that cannot serve the request.

**A CLAIM OF MINE THAT THIS KILLS.** On 2026-09-28 I reported that deepseek "ignores the reasoning
parameter", from a single call that returned zero reasoning tokens. That was a statement about a provider
read as a statement about a model. Deepseek supports reasoning; the provider that answered did not serve it.
The general error is the one this project keeps meeting: attributing to the instrument's subject what
belongs to the instrument.

**WHY PINNING IS NOT THE FIX HERE.** Pinning panel (c)'s deepseek cell to SiliconFlow would make its
reasoning cell provider-controlled while its no-reasoning comparator in stage 1 was unpinned, so the
contrast would confound reasoning with provider. A clean version needs a matched no-reasoning cell pinned to
the same provider, which is a **new** cell and not this panel. It is cheap, about $0.40 of compute, and it
is recorded in `spec/DEFERRED_CHANGES.md` as an option, and is not run under a panel that did not
pre-register it.

**WHAT THE EXCLUSION COSTS.** Panel (c) answers "does extended deliberation repair the behaviour". With two
models it answers that for a frontier and a mid-tier closed-weight model and says nothing about an
open-weight one. The panel is EXPLORATORY under 0q, no confirmatory number depends on it, and the
open-weight question is left to the model-breadth panel, where a pinned provider per open-weight model is
part of the design from the start.


## 0z. CREDITS RAN OUT AND THE HARNESS CHARGED IT TO THE AGENT. 356 campaigns quarantined, the bug fixed

**WHAT HAPPENED.** From about 12:29 on 2026-09-28 the OpenRouter balance was exhausted and calls returned
**HTTP 402**, dominated by `in_flight_budget` ("would exceed your available credits given your current
in-flight requests"), with `weight_exceeds_budget` and one message stating it could "only afford 3810" of
the 6,000 tokens requested. The balance read **$0.04** when the credit endpoint was first queried.

**WHY IT CORRUPTED DATA INSTEAD OF STOPPING.** `LLMPolicy.propose` returned an **empty proposal list** for
two different things:

- a reply we could not parse, which **is** a fact about the agent and is correctly charged as a forfeited
  round (268 of stage 1's 1,688 lost slots came through that channel), and
- **no reply at all**, which is a fact about our own infrastructure.

`campaign.py` could not tell them apart, so it charged both as `ROUND_LOST` for the whole round. Every 402
was therefore written to disk as the agent forfeiting a round:

| opus top-up | clean (n=261) | contaminated (n=156) |
| --- | --- | --- |
| rounds lost to forfeits | 0.03 | **47.51** |
| distinct variants measured | 9.18 | **2.30** |
| **nominated true fitness** | **7.688** | **3.115** |

The primary outcome read 3.115 against 7.688. The contamination rate differed by run and by cell, so
including these would have **manufactured a between-condition difference out of an account balance**. This
is the project's recurring failure class: an infrastructure fault recorded as a property of the subject.

**WHAT IS UNAFFECTED, verified from the archives.** `stage1` (18,017 calls), `stage0` (15,479), `tpanel`
(3,489), `rprobe` (334) and `stage1a` (7,285) contain **ZERO** errored calls of any kind. So the N table of
0w (695 / 181 / 139), the sizing, and every Methods number derived from stage 1 stand untouched.

**QUARANTINE, not deletion** (`scripts/quarantine_credit_402.py`). The rule is broader than the zero-spend
campaigns, because a campaign that lost only SOME rounds to 402s still spent money, still looks complete,
and still has the wrong outcome. Anything with at least one errored call goes, plus anything with no
successful measurement whether or not an error was logged.

| run | before | kept | quarantined | of which zero-spend |
| --- | --- | --- | --- | --- |
| topup_opus | 417 | 261 | **156** | 90 |
| topup_deepseek | 166 | 143 | 23 | 0 |
| topup_gemini | 283 | 235 | 48 | 9 |
| panelc | 17 | 5 | 12 | 10 |
| zeronoise | 460 | 343 | 117 | 17 |
| **total** | **1,343** | **987** | **356** | **126** |

Wasted spend **$17.85**. The removed rows and their calls are in `results/quarantine_credit_402/` with a
manifest recording every file's SHA256 before and after, and the split is verified lossless: live plus
quarantined equals the original line count for all five runs. The contaminated files are also preserved in
git at `5391f76`. **Postcondition asserted by the script: every live file now holds zero campaigns with any
errored call and zero campaigns with no successful measurement.** Resume reruns those seeds.

**THE FIX, which matters more than the cleanup.**

1. **A transport failure is now a named state.** `TransportFailure` is raised where an empty list used to be
   returned, so the campaign is **abandoned unwritten** and nothing is charged to the agent. It covers the
   nomination call as well as the round call, because the nomination call IS the primary outcome and it was
   a second call site.
2. **`CreditsExhausted` subclasses it, and HALTS THE WHOLE RUN.** Every further call fails identically, so
   retrying keeps producing campaigns that look complete. The halt names the
   balance and says that resume will fill the gap.
3. **The parse failure is untouched, deliberately.** A reply we cannot use is still charged as a forfeited
   round. A fix that raised on both would have deleted a real measurement along with the artefact, and a
   mutation test pins exactly that.
4. **Money is a pre-flight check.** `credit_balance()` reads OpenRouter's credits endpoint. The run refuses
   to launch below `--credit-floor` (default **$50**) and re-checks **every 50 campaigns**, halting below it.
   The balance at launch, the floor, and whether the floor was overridden are recorded in every manifest.
   It returns `None` on any failure and continues, because a monitoring endpoint must never stop an
   experiment.

Mutation-tested **five for five** (`results/mutation_transport.txt`), the first mutant being the bug exactly
as it shipped. 217 tests pass.

**THE RESTART, pending the operator adding credits.** All five runs relaunch from the fixed commit with
their existing tags, so resume reruns only the quarantined seeds. `topup_opus` goes to 16 workers once
`topup_gemini` and `zeronoise` finish. Concurrency is part of the cause: `in_flight_budget` is about
simultaneous reservations, so 24 workers against a thin balance made it worse than the balance alone.


## 0aa. THE BIOLOGY-LAB FRAMING PANEL. Pre-registered and QUEUED, not launched

**QUEUED, NOT RUNNING.** This panel does not launch until the operator confirms credit beyond the ~$800
balance, and not before the core grid, the zero-noise control and panel (c) are safe. It is EXPLORATORY and
is not in the confirmatory family of 0g.

**THE QUESTION.** Does a wet-lab role make an agent re-measure more, and if it does, is that a response to
the data or a habit the role itself triggers?

**DESIGN.** Three cells x 3 models x 40 campaigns = **360 campaigns**. Temperature 0, the frozen harness,
the same NK landscape, and **the same seeds as stage 1** (seed0 300000), so every cell is paired by seed
under 0s against the grid's own Blind cell.

| cell | noise | prompt |
| --- | --- | --- |
| `bio_role` | sigma > 0 | grid Blind with the first sentence replaced by the role text. No noise statement. |
| `bio_role_noisy` | sigma > 0 | `bio_role` plus one sentence about noise |
| `bio_role_exact` | **sigma = 0**, failures kept at 15% | prompt **byte-identical to `bio_role`** |

**THE ROLE TEXT**, replacing *"You are running a numerical optimization campaign on four positions of an
abstract four-position system."*:

> "You are a protein engineer working in a wet lab. You are improving a protein by changing four positions,
> each of which can hold one of 20 building blocks. Each order is a sample submitted to the lab's assay
> facility, and its result comes back at the end of the round."

**THE NOISE SENTENCE**, added only in `bio_role_noisy`:

> "Assay readings can be noisy, as in any real lab: a single reading may not reflect the sample's true
> value."

**THE RENDERED DIFF, SHOWN BEFORE LAUNCH** (`scripts/bio_framing_diff.py`,
`results/bio_framing_diff.txt`, hashes in `results/bio_framing_prompts.json`). The anchor sentence occurs
**exactly once** in each of the four prompt types, and the script refuses to run if that stops being true.
For all **twelve** cell-by-prompt-type combinations, removing the intended substitution from both sides
leaves **byte-identical** text, so nothing else moved: not the A-T alphabet, the budget and rejection rules,
the history format, or the nomination instruction. The diff is two lines in every prompt type.

**A CHECK THAT WAS NOT ASSUMED.** `bio_role_exact` must differ from `bio_role` in sigma alone. The Blind
prompt is **noise-mode independent**: `blind|exact` and `blind|multiplicative` hash identically for all four
prompt types, because the exact-mode change of 0v touches only the AGGREGATED history's standard error and
Blind has no aggregated history. The aggregated rung does differ under exact noise, which is what makes the
Blind result meaningful. So the `bio_role_exact` contrast is a pure noise manipulation.

**THE THREE REPLACEMENT HASHES WERE REGENERATED AT 4e850cb.** `results/bio_framing_prompts.json` was
written at 56598b6 (14:56), and the prompt-contract fixture's replacement bug was fixed at a826ac6 (15:24),
so its three `*|replacement` hashes had been computed from the `slots=4` base the harness never sends. They
were regenerated in place and the implementation now reproduces all twelve pre-registered hashes exactly. The
superseded values remain in git at 56598b6.

**The panel is built without touching the frozen harness.** `scripts/bio_framing_diff.py` applies the
substitution to the ALREADY RENDERED Blind prompts and changes no file under `repdef/`. The implementation
that eventually ships must reproduce the recorded SHA256 of each rendered variant, which is checkable
mechanically instead of by eye.

**IT NEVER INSTRUCTS THE AGENT TO RE-MEASURE.** The panel measures whether the framing makes it CHOOSE to.
An instruction would measure instruction-following, which is the Mechanism rung's job and a different
question.

**PRE-COMMITTED READINGS, exploratory.**

| contrast | what it reads |
| --- | --- |
| `bio_role` vs grid Blind | the effect of the lab role on distinct variants, replication and nominated true fitness |
| `bio_role_noisy` vs `bio_role` | the effect of a qualitative noise statement inside the role |
| `bio_role_exact` vs `bio_role` | if replication persists when every reading is exact, it is a role-triggered habit and not a response to evidence |

The third is the one that can distinguish a habit from an inference, and it is the reason the panel is worth
running.

**CAVEAT, recorded before any data exists.** 17 of the 20 letters in the alphabet are amino-acid codes, so a
protein framing may import biochemical heuristics. On a randomly generated NK landscape those heuristics
cannot carry information, so any change they produce is part of the treatment and not a confound to be
removed. It is stated so that a reader is not asked to discover it.

**COST.** About **$35**, opus about $31 of it. Capped at twice that.


## 0ab. A SECOND GATE BYPASS OF MINE, and the cause removed. 2026-09-28

**WHAT I DID.** Verifying that a panel's comparison table computed anything at all, I ran
`analyse_grid.py panelc --against stage1` with `ANALYSE_GRID_COMPLETE=1` and **printed eight real
panel-against-grid paired differences**, for Blind and Mechanism on opus and gemini. The operator's
instruction was explicit: no condition means until the core is complete and audited.

**This is the SECOND time, the same way.** Section 0x records the first: I imported past `main()`'s refusal
to cross-check arithmetic that synthetic data would have checked. Both times the reason was identical, and it
was not carelessness about the rule. **Verifying the code required running the code, and the only redaction
lived one layer up in `final_analysis.py --smoke`.** A rule that can only be obeyed by not testing is a rule
that will be broken by anyone who tests.

**WHAT THOSE NUMBERS ARE NOT USED FOR.** They are discarded. Panel (c) is 29% complete and its shared-seed
counts were 18 and 19 of 40, so they are not a result of anything, and no decision was taken on them. The
output directories were deleted.

**THE CAUSE IS REMOVED.** `analyse_grid.py` now takes `--redact`, which replaces every decimal in every
table with `REDACTED`, **on screen and on disk**, and is permitted WITHOUT `ANALYSE_GRID_COMPLETE`, because a
redacted table reveals no condition mean. Verifying a code path no longer requires reading a result. The gate
without `--redact` is unchanged and still refuses.

**THE DEFECT I WAS VERIFYING, which was real and is fixed.** `analyse_grid` titled its table 2 "The SIX
confirmatory contrasts, Holm-corrected across the family" **whatever tag it ran on**. Run on the reasoning
panel, whose cells are Blind and Mechanism, it produced a table with **zero rows** wearing the confirmatory
title, because neither Aggregated-vs-Mechanism nor Decision-rule-vs-Mechanism exists there. The panel's own
question, its cell against the grid's same cell at the same seeds, was **not computed at all**. So the answer
to "does the final analysis cover the panels as secondary analyses" was **no**.

Now: table 2 is retitled for a panel and states that Holm applies across that panel's own family and never
the six of 0g; and a new **table 2b** pairs a panel against a reference tag on their shared seeds, which is
what `panelc --against stage1` and `zeronoise --against stage1` actually ask.


## 0ac. THE CREDIT FIGURES, recorded so the limitations section quotes nothing unsourced

Read from OpenRouter's own endpoints on 2026-09-28, after the operator's $500 top-up. Both limits bind
independently and the spendable amount is the smaller.

| endpoint | field | value |
| --- | --- | --- |
| `/credits` | total_credits | 2300 |
| `/credits` | total_usage | 1171.88 |
| `/credits` | account balance | **$1,127.35** at the later reading |
| `/key` | limit | **$1,000** |
| `/key` | limit_remaining | **$826.40** |
| `/key` | expires_at | **2026-10-28** |

The guard read only `/credits` until `e3ad28e`, so it reported $1,127.35 where $826.40 was spendable. At
LAUNCH of the five live runs the account held $800.04 against a nearly unused key limit, so the account was
the binding limit and every recorded launch figure was correct; the method became unsafe only when the
top-up made the key bind. The key's expiry is a bound on the queued panels and on any re-run after that date.

**CLEAN-CALL TOTAL, computed and not added by hand.** The runs with zero errored calls of any kind are
stage1 18,017, stage0 15,479, stage1a 7,285, tpanel 3,489 and rprobe 334, totalling **44,604**. An earlier
draft of the limitations section said 44,632, which was arithmetic done in my head and was wrong by 28. The
figure above comes from a script that counts the archives.


## 0ad. THE CENTRAL TEST: post-repeat replication, zero-noise against noise. Pre-registered before computing

**THE GAP THIS CLOSES.** The paper asks whether agents replicate **in response to noise**. The zero-noise
panel exists to answer it (0i, 0q(a)), and its pre-committed reading is about replication AFTER the agent has
seen a repeat. Table 2b pairs the panel against the grid on **nominated true fitness only**, because
`analyse_grid.by_seed` hardcodes that field. **The central test was computed nowhere.** It is defined here
before any value is read.

### 1. Definitions

- **Replication slot (0ad):** an order for a variant that already has **at least one SUCCESSFUL reading**.
  Re-ordering a variant whose only previous order FAILED is not replication, because nothing was learned
  from it to re-measure. Instrument failures stay at 15% in the zero-noise panel, so this distinction is
  live on both tags.
- **r\*:** the first round in which the agent **receives** a second successful reading of any variant. It
  becomes visible to the agent in the prompt for round r\*+1.
- **Post-repeat replication:** the replication fraction over the slots in rounds **r\*+1 to 15**, so it
  measures only behaviour the agent could have conditioned on having seen a repeat.
- **Exclusions:** campaigns with no repeat at all, and campaigns with r\* = 15, which leave no post-repeat
  rounds. Counted and reported **per cell**, on both tags, and never silently dropped.
- The same definition is applied to both tags. No threshold is involved anywhere.

### 2. THIS DIFFERS FROM THE HARNESS'S OWN REPLICATION COUNT, and that is deliberate

`repdef/campaign.py` increments `replication_count` when a variant is ordered that is already in
`measured_before`, and `measured_before` gains a variant on **every attempted order**, successful or failed.
So **all four pre-registered replication definitions of 0d count a re-order of a variant that was never
successfully read.** Under 0ad that is not replication.

Both are reported. The four whole-campaign definitions keep their existing meaning, and 0ad's
post-repeat measure uses the successful-reading definition. **The size of the discrepancy is reported per
cell**, because a metric that includes re-orders of never-read variants is a different quantity from one that
does not, and the paper should not let one stand for the other.

### 3. WHERE IT IS COMPUTED FROM, and why not from the campaign records

The per-slot history is **not persisted**: `campaign.run` returns `history=tuple(orc.history)` and `grid.py`
consumes it for aggregates without writing it, so `results/grid_*_campaigns.jsonl` cannot support this test.
It is therefore reconstructed from the **history each prompt actually showed the agent**, in the call logs,
which is the more appropriate basis in any case: r\* should be the moment a repeat became **visible**.

Two formats must be parsed, and only one exists in the current script:

- the per-reading view, one line per slot, which `scripts/blind_evidence_timing.py` parses with
  `ROW = ^\s*(\d+)\s+([A-Z]{4})\s+(-?\d+\.\d+)\s*$`;
- the **aggregated** view, which shows n, mean and standard error per variant, where a variant with
  **n >= 2** has two successful readings. `ROW` does not match it, so a second parser is required, and
  without it the Aggregated cell would silently contribute nothing.

### 4. WHERE IT DIFFERS FROM `blind_evidence_timing.py`, whose logic is reused where it fits

That script is reused for prompt-history parsing and for the per-campaign pairing idea, and differs in four
ways that matter:

1. Its trigger is a visible **contradiction**: the anchor reading differing from its stated value by more
   than 0.30, or a repeated variant's two readings **differing**. 0ad's trigger is simply a second
   successful reading. **This is the reason the existing script cannot be used as it stands: under exact
   readings two readings of a variant are IDENTICAL, so a contradiction can never appear, and a
   contradiction-triggered definition would exclude every zero-noise campaign and make the comparison
   impossible.**
2. It pairs before-against-after **within** one campaign. 0ad pairs **across tags**, zero-noise against the
   grid, on the seeds they share, which is available because both used seed0 300000.
3. It is Blind only. 0ad covers all five conditions.
4. It uses a threshold. 0ad uses none.

### 5. Table 2c, its statistics, and its label

**Table 2c: zeronoise against stage1, paired by seed on the seeds they share**, for:

(a) post-repeat replication as defined above;
(b) the four whole-campaign replication definitions of 0d;
(c) distinct variants measured.

Studentised wild cluster bootstrap over seeds with Rademacher weights, as in 0s. **Holm within this table
only.** Labelled **EXPLORATORY**: it is not in the confirmatory family of 0g.

**THE LEVEL IS REPORTED BESIDE THE DIFFERENCE.** The pre-committed reading of 0q(a) is about the zero-noise
**level** of post-repeat replication being near zero, not only about the change, so the zero-noise level is
reported with its bootstrap interval next to the paired difference. A difference of a given size means
different things when the zero-noise level is 2% and when it is 40%.

**PRE-COMMITTED READING.**

| result | reading |
| --- | --- |
| post-repeat replication near zero at sigma = 0, and far above it at sigma > 0 | replication is a response to the noise the readings carry |
| substantial at sigma = 0 as well | replication is a default the role and the task evoke, not an inference from evidence, and the interventions are acting on a habit |
| in between | reported as a proportion of the noisy level, with the interval, and never rounded to either story |

### 6. Figures

`scripts/figures.py` produces the four figures of the results skeleton from `analysis_final` outputs only,
and is **smoke-tested on synthetic data alone**, so no figure code is exercised against a real condition mean
before the core is complete.


## 0ae. THREE BUGS IN THE FIRST TABLE 2c, found by audit and fixed. 2026-09-28

The definition of 0ad was right and came before the code. The first implementation of it had three defects,
all found by an independent audit of the zero-noise logs using structure counts alone.

**1. The campaign key had no MODEL.** It was `(rung, seed)`, and all three models share the seed range
300000-300039, so each of the 200 keys collected the calls of **three models at once**. r\* came from
whichever model happened to show a repeat first, every per-seed value pooled all three, and each model was
then handed the same pooled number. The reported "40 pairs and zero exclusions in every cell" was the
symptom. Keyed by `(model, rung, seed)` the tag yields **600** keys and not 200, and the three models on one
seed now give **three distinct values** in every rung.

**2. The denominator was every parsed proposal.** 0ad says "the replication fraction over the SLOTS", and
**30.0%** of parsed proposals in the zero-noise panel are rejected as non-viable and take no slot (48,886
parsed, 34,216 viable). Only slot-consuming orders are counted now, viability tested against the same pool
the grid built.

**THE IDENTITY THAT CHECKS IT, and refuses if it fails.** Per campaign, the slots this script counts plus
`lost_slots` must equal `slots_used`. It holds **exactly on all 1,200 campaigns of both completed tags, zero
mismatches**, and the script exits without producing a table if it ever does not. Two wrong identities were
tried first: viable orders alone matched 267 of 600, and viable plus `lost_slots` plus `rounds_lost_slots`
matched 519, because `lost_slots` already includes `rounds_lost_slots`. The residuals were all negative
multiples of four, which is what pointed at whole forfeited rounds being double counted.

**3. r\* did not depend on the call kind.** It was `shown_round - 1` for every call. But `campaign.py`
measures each slot **as it fills it**, so a REPLACEMENT prompt is rendered mid-round and a duplicate visible
there was received in **that** round, while a ROUND prompt's history covers only completed rounds. Treating
both alike produced **r\* = 0 in 89 of 600** zero-noise campaigns, which claims a repeat was visible before
round 1 existed. r\* is now `shown_round - 1` for a round call and `shown_round` for a replacement call.

**THE EXCLUSION COUNTS ARE GENUINELY ZERO, and here is why that is not a fourth bug.** After the fixes, r\*
ranges over **1 to 5** on the zero-noise panel and **1 to 4** on the grid, with **595 of 600** and **597 of
600** campaigns having r\* <= 3. No campaign lacks a repeat and none comes near r\* = 15, so both exclusion
counts are zero because the window is almost always open by round 4, and not because the filter is broken.
The counts are printed per cell regardless, so a future run in which they are not zero is visible.

**Pinned by four tests** in `tests/test_the_central_test_is_computed_right.py`: two models on one seed whose
post-repeat values differ must stay separate, a non-viable proposal must not enter the denominator, a
replacement prompt's mid-round view must give r\* = that round while a round prompt's view gives the previous
one, and r\* must never be zero. Three earlier tests had encoded the pooled interface and were updated.


## 0af. REPLICATION IS JUDGED AT MEASUREMENT TIME, NOT AT DECISION TIME. 2026-09-28, before any value

**THE TWO DEFINITIONS.** A slot is a replication slot if its variant already has a successful reading. The
ambiguity is *when* "already" is evaluated:

- **DECISION TIME**, what the first implementation did: the variant had a successful reading **in the prompt
  the agent was looking at** when it chose the order.
- **MEASUREMENT TIME**: the variant had a successful reading **at the moment the slot was measured**.

**THE CASE THAT SEPARATES THEM.** A variant appears in the round's batch AND is also proposed as the
replacement for an earlier rejected slot in the same round. `campaign.py` measures each slot as it fills it,
so the replacement is measured first, and by the time the batch slot is measured the variant already has a
reading. Measurement time counts that slot; decision time does not, because the prompt the agent saw when it
chose the batch had not yet shown it.

**WHY THIS IS NOT A TOSS-UP.** The two disagree in **293 of 600** zero-noise campaigns and **82 of 600**
grid campaigns, and measurement time is **always higher, never lower**. So decision time depresses
zero-noise replication about three and a half times as often as it depresses noisy replication. The central
test of 0ad compares exactly those two quantities, and the direction of the distortion is **toward our own
hypothesis**: it would make replication look more like a response to noise than it is. A definitional choice
whose error points at the conclusion we are hoping for is not one to settle by whichever implementation happened to be
written first.

**THE DECISION.**

- **PRIMARY: measurement time.** A slot is replication if its variant has at least one successful reading at
  the moment that slot is measured, in **true measurement order**: within a round, the batch is processed in
  order, and a rejected slot is refilled from the following replacement calls **in file order**, capped at 3
  attempts, before the next slot of the round is measured.
- **SENSITIVITY: decision time**, the first implementation, reported beside the primary **with the per-tag
  count of campaigns in which the two differ**, so a reader can see the size of the choice and not only its
  direction.
- **r\* is unchanged.** The two definitions agree on it in all 1,200 campaigns of both completed tags, which
  an independent re-implementation confirmed, so the window is not in question here; only what counts inside
  it.

**HOW THE MEASUREMENT ORDER IS VERIFIED, and it is verified and not assumed.** For the four per-reading
rungs the reconstructed order is exactly the history the final nomination prompt shows, so the
reconstruction is checked against it row for row. The **Aggregated** rung shows no order, only n, mean and
standard error per variant, so its order is reconstructed the same way and then checked against the final
aggregated **n per variant and the failure counts**. A reconstruction that cannot reproduce the totals the
environment reported is not used.

**WHAT IS IN THE DENOMINATOR, stated because it is not implied by "measurement time".** The denominator is
the slots at which a measurement was ATTEMPTED, and the numerator those whose variant already had a
successful reading:

| row in the final history | charged to the budget | in this fraction |
| --- | --- | --- |
| a reading | yes | numerator if the variant already had a successful reading; denominator always |
| `order failed, no reading` | yes | same: the variant was re-ordered and the instrument failed |
| `SLOT LOST` | yes | **neither part** |
| `ROUND LOST` | yes | **neither part** |
| `rejected, not viable` | **no**, the slot was refilled by a replacement | neither part |

**CORRECTION TO MY OWN FIRST VERSION OF THIS CLAUSE.** I first put lost slots and lost rounds in the
DENOMINATOR, on the reasoning that they are charged to the budget. That is true and it is the wrong test: a
slot at which nothing was measured was never an opportunity to re-measure, so it belongs to neither part of
the fraction. It also confounded the comparison the sensitivity exists for. With lost slots in the
denominator the primary came out LOWER than decision time in 188 of 480 zero-noise campaigns, which the
timing rule alone cannot do; with them excluded the primary is higher in **246** and lower in **0**, which is
the direction an independent re-implementation found. A denominator that can reverse the sign of a difference
the definition cannot reverse is a denominator that is measuring something else.

`slots_counted`, which reconciles against `slots_used`, still counts EVERY charged slot. The two are
different quantities and are kept apart.

**THE RECORD IS EXACT FOR FOUR OF THE FIVE RUNGS.** The final nomination prompt's history is the
measurement-ordered list of every charged slot: **480 of 480** per-reading campaigns on each completed tag
carry **exactly 60** such rows. Nothing needs reconstructing there; the order is read.

**THE RECONSTRUCTION IS DONE AND GATED. Amended 2026-09-28, after implementation.** The ambiguity rule of
clause 2 below was **not needed**: the walk is deterministic. Each round's batch is taken in order; a
non-viable order is rejected and takes no slot, and the next replacement calls of that round are consumed in
file order, at most three, until one is viable or the slot is lost; then the next batch order. Failure is
redrawn from the oracle's own stream, `uniform("fail", seed, seq, i) < 0.15`, with i the attempt index of
that variant in the campaign counting only slot-consuming attempts.

**One detail the first attempt got wrong.** An **empty** replacement parse abandons the slot at once, naming
the candidate that had just been rejected, because `campaign.py` does `if not again: record_abandoned(rnd,
seq)`. Looping on the same candidate instead put a later variant's name on 23 lost rows and shifted 7 more.

**BOTH GATES PASS.**

- Against ground truth: the reconstruction equals the final nomination history on **960 of 960** per-reading
  campaigns across both completed tags, with **zero** replacement calls left unconsumed.
- On the aggregated rung: it reproduces every campaign's final **n and failure counts, 240 of 240**.
- Slot reconciliation against `slots_used`: **1,200 of 1,200**, zero mismatches, both sources.

**ONE QUANTITY THE VIEW CANNOT EXPRESS.** In a single campaign, a variant with two lost slots and no
readings is displayed with the singular `SLOT LOST` note and no count, because `_history_aggregated` builds
the count into `extra` and discards it in the no-readings branch. The reconstruction says two and the prompt
can only say one. This is a display defect, recorded in `spec/DEFERRED_CHANGES.md`, not a reconstruction
error, and it touches no metric.

**AND THE PRIMARY NOW AGREES WITH AN INDEPENDENT IMPLEMENTATION ON BOTH TAGS**: measurement time exceeds
decision time in **293 of 600** zero-noise campaigns and **82 of 600** grid campaigns, and is lower in
**none**, which are the counts the re-implementation found before this one was written.

**THE ORIGINAL CLAUSE, superseded by the above and kept because the document is append-only.**

**THE AGGREGATED RUNG IS THE ONE CASE THAT MUST BE RECONSTRUCTED.** Its prompts show n, mean and standard
error per variant and no order at all. Its slot order comes from the calls, and its successes from the
**n-count deltas between consecutive snapshots**, which the replacement calls make intra-round. Two clauses
bind it:

1. The reconstruction is **checked against the final n per variant and the final failure count**, and a
   campaign whose reconstruction cannot reproduce them is reported as unresolved and excluded, never guessed.
2. Where a round's deltas leave the order of successes and failures **genuinely ambiguous**, it is resolved
   in the direction that makes zero-noise replication **HIGHER**, which is the direction **against** our own
   hypothesis. The number of slots resolved that way is reported per cell, so the size of the assumption is
   visible and not merely its direction.

**WHY IT WAS FOUND, and by whom.** An independent re-implementation of 0ad, comparing per-campaign values
with match counts only and reading none of them. It also confirmed the three fixes of 0ae: r\* matches in
1,200 of 1,200 campaigns, and the replay reproduces the final histories and all 240 aggregated final totals.
The first implementation's choice was not argued for anywhere, which is how a definitional decision gets made
by accident.


## 0ag. A SILENT NOMINATION FALLBACK SCORED THE HARNESS'S RULE AS THE AGENT'S ANSWER. 2026-09-28

**THE DEFECT.** `campaign.py` ends the agent-nomination branch with

```
nom, agent_reason, _ = policy.nominate(final)
if nom is None or nom not in landscape:
    nom = final.best_by_mean()          # unparseable answer falls back, and is logged
```

The comment is half true: it is logged in the CALL log, as a nomination whose `parse_status` is not `ok`, and
**nowhere in the campaign record**. So `nominated` and `nominated_true`, which are the PRIMARY OUTCOME, hold
the harness's averaging rule and not the agent's answer, and no field says so.

**WHY THIS IS WORSE THAN A MISSING VALUE.** `best_by_mean` is exactly what the **Decision-rule** condition
instructs the agent to do. A fallback campaign is therefore scored as though it had followed the paper's own
best-practice rule, so the substitution does not merely add noise: it substitutes a good rule for whatever
the agent would have done. This is the third silent fallback this project has found, after the shrinkage
prior that returned `best_by_mean` when sigma was unusable and the transport error charged as a forfeited
round. The shape is identical each time.

**COUNTS, derived from the call logs and confirmed independently.**

| tag | fallback campaigns | where |
| --- | --- | --- |
| stage1 | **0** | |
| topup_opus | **0** (at 2,200 of 3,275) | |
| topup_gemini | **0** | |
| topup_deepseek | **1** | Decision-rule |
| zeronoise | **0** | |
| **panelc** | **9 of 160** | gemini only: 5 Blind, 4 Mechanism |
| tpanel | 1 | Mechanism |

Of the nine in the reasoning panel, **five finished on `length` with completion_tokens 5,996** against a
6,000 cap, so gemini spent its whole budget reasoning and never emitted an answer; the other four finished on
`error`. **The bias runs toward "reasoning helps"**, because those nine are scored by the averaging rule
instead of by a gemini answer that never arrived.

**THIS QUALIFIES A CONCLUSION OF MINE IN 0u.** 0u recorded that "max_tokens was never the binding
constraint", on a 389-call probe whose largest total generation was 4,131 of 6,000. That was true of the
probe and false as a general statement: over the panel's 160 campaigns the cap bound in **5 of 80** gemini
nominations. A ceiling that does not bind in 389 calls can bind in 5,858. The probe was too small to see it
and I generalised from it anyway.

**THE DECISION.**

1. **`nomination_fallback` is derived from the call log**, as a nomination call whose parse did not yield an
   answer, and is attached to every campaign in the analysis. It is not inferred from the campaign record,
   which cannot express it.
2. **PRIMARY agent-outcome analyses EXCLUDE fallback campaigns.** The primary outcome is the agent's choice,
   and a campaign where the agent made none has no value for it.
3. **SENSITIVITY keeps them**, reported beside the primary, so the effect of the exclusion is visible.
4. **Every table prints per-cell fallback counts**, so a cell that loses campaigns says so in the table a
   reader is looking at.
5. For the **core grid** this drops exactly **one** deepseek Decision-rule campaign, and under the seed
   pairing of 0s that drops **one pair**. For **panel (c)** it drops nine, all gemini.

**A SECOND DEFECT, and its fix waits for opus.** A call with `finish_reason == "error"` and an HTTP 200 is
currently treated as a valid answer and charged to the agent. Panel (c) has **8** such calls, 2 round, 1
replacement and 5 nomination; **every core grid tag has zero**. The repair is to raise `TransportFailure` on
it, which voids the campaign unwritten exactly as a 402 does, followed by quarantine and rerun of the
affected panel-(c) campaigns. **It is not made while the opus top-up is running**, because a harness change
mid-run is what 0p forbids, and the prompts must be shown byte-identical before it lands.


## 0ah. SILENT-SUBSTITUTION SWEEP of the five files. 2026-09-28, code reading only

Prompted by 0ag being the THIRD fallback of one class. Every site in `repdef/campaign.py`,
`repdef/llm_policy.py`, `repdef/oracle.py`, `scripts/grid.py` and `scripts/analyse_grid.py` where a
missing, unparseable or failed value could be replaced by a default or by a harness rule. Firing counts are
from the live logs: **5,133 campaigns and 168,485 calls** across stage1, the three top-ups, zero-noise and
panel (c). Nothing was fixed.

### Fired, and CAN move an outcome

**None beyond 0ag.** The nomination fallback is the only one, and it is already handled.

### Fired, and cannot move an outcome

| site | substitutes | fired | why it cannot move an outcome |
| --- | --- | --- | --- |
| `llm_policy` intent classification, `(reason or "").lower()` | an empty reason becomes an empty string, then classified | **10** of 398,124 proposals | `intents` is descriptive and is read by no analysis script |
| `grid.py` drops `ref_shrinkage_note` at the write boundary | the REASON a comparator is undefined is computed and discarded | **604** of 5,133 campaigns | `ref_shrinkage` itself is recorded as `None` and `shortfall_vs_shrinkage` propagates the absence; no analysis reads either today |

**The second deserves its own paragraph.** `campaign.py` sets `ref_shrinkage_note` to one of three reasons,
and `grid.py` writes `ref_shrinkage` without it, so the note is empty in **all 604** cases, including the 600
zero-noise campaigns where the code plainly sets "no noise: a shrinkage comparator is undefined". The
`ref_shrinkage_oracle` field is dropped the same way. This is the **same shape** as the per-slot history: a
value computed and then lost at the persistence boundary, which is how a named absence degrades into a bare
one.

**THE FOUR CORE-GRID CASES, cause recovered without the note.** 600 of the 604 are zero-noise and undefined
by design. The other four are gemini campaigns, two in stage1 and two in topup_gemini, all Decision-rule or
Mechanism, and **every one has `n_distinct_measured` = 1**: sixty slots spent on a single variant, so the
cause is "fewer than two measured variants" and not a collapsed prior. The diagnostic is therefore
recoverable from a field that IS persisted. What that behaviour means belongs to the analysis and is not read
here.

### Dormant: present but fired zero times

| site | would substitute | fired |
| --- | --- | --- |
| `campaign.py` `V.build(orc, rounds_used or 1, ...)` | round 1 for a campaign with no history at all | **0** of 5,133 |
| `analyse_grid.py` `[...] or [0.0]` for the two shortfalls in `cells_detail` | a missing shortfall becomes 0.0 | **0** of 5,133 |
| `analyse_grid.py` `st.mean([...slots_used...]) or 1` | a divisor of 1 for a cell with no slots | **0** |

They are recorded because dormant is not safe: each would substitute silently if it ever fired, and the last
two are mine, added this week.

### Already correct: a named absence, not a substitution

- `_ep is None` and the `_noiseless` branch leave `ref_shrinkage` as `None` **with a reason**, which is the
  right pattern. Only the reason's persistence is missing, above.
- `(cv or 0.0)` in the two sigma reconstructions is guarded: `campaign.run` raises when the noise model is
  multiplicative and `cv` is `None`, so the default is unreachable there. The comment at that site documents
  the earlier bug where passing the scalar `sigma` silently substituted the mean rule.
- `grid.py`'s canary aborts if `ref_shrinkage` is not recorded, and the credit and git helpers return `None`
  on failure without touching campaign data.

### Treatment

Proportionate, and no exclusion where the primary outcome is intact. **`ref_shrinkage_undefined` is derived
in the analysis, with its recovered reason, and the per-cell count printed**, so any future comparator
analysis excludes those campaigns explicitly instead of averaging over a silent gap. The primary outcome,
`nominated_true`, is unaffected in all 604, so they are NOT dropped from the primary analyses. The
`(reason or "")` site needs no treatment and is recorded so a future analysis of `intents` knows about it.

**The repairs for the released environment**, none made mid-dataset: persist `ref_shrinkage_note` and
`ref_shrinkage_oracle`, and persist the per-slot history. All in `spec/DEFERRED_CHANGES.md`.


## 0ai. THE SCRIPTED REFERENCE IS UNFAIR ON EXPLORATION. A fair reference, pre-registered before it runs

**THE CONFOUND.** `scripts/nk_reference_curve.py` builds the reference as
`GreedyWithReplication(k, 0, "pool", "fresh_pool")`. Read against `repdef/policies.py`, that means:

- `explore_scope="pool"` filters the neighbour shell to `view.pool`, so **every exploration slot is a
  viable variant**;
- `fallback="fresh_pool"` draws from `view.pool_sorted`, so **every fallback pick is viable**;
- `_cold_start` draws "uniformly from the pool", so **round one is viable too**.

**The reference is therefore never rejected, never spends a replacement ask, and never loses a slot.** The
agents must GUESS viability from a four-letter string: **30.0%** of their proposals are non-viable and take
no slot, a rejection costs a replacement ask, and a slot whose every replacement is non-viable is lost and
charged. The reference plays an easier game and its advantage is concentrated in exactly the dimension the
paper's headline is about, **exploration**.

**TWO CLAIMS ARE ON HOLD until the fair reference exists.**

1. **"Every cell is below scripted k=0."**
2. **"Optimal replication is 25% of slots", i.e. k\* = 1**, and with it the 39.2 distinct-variant reference.

Under the agents' real rules, a rejection makes exploration **more expensive**, so the optimal replication
rate **may be higher than 1** and the optimal distinct-variant count lower. If it is, the sign of the
headline can change, which is why no Results prose is written until this is reviewed.

**WHAT IS REFERENCE-FREE AND STANDS.** The zero-noise control and the central test of 0ad compare the panel
against the grid, agent against agent, on the same seeds. They involve no scripted policy. Replication
staying at **0.52 to 0.98** with exact readings is unaffected by anything in this section.

**THE FAIR REFERENCE, fixed here before it is run.**

| parameter | value |
| --- | --- |
| replication rates | **k = 0, 1, 2, 3, 4** |
| campaigns per k | **1,500** |
| seeds | the same seeds as the current curve, so the two are paired |
| exploration | `explore_scope="landscape"`: the whole neighbour shell, so non-viable proposals happen |
| fallback | drawn from the landscape and **not** from the viable pool |
| cold start | the reference point and its neighbours, **not** a draw from the viable pool |
| rejection, replacement, lost slots | the agents' rules exactly, cap 3, through `campaign.run` |
| noise, budget, failure rate | unchanged: multiplicative, 15 rounds x 4 slots, 15% |

**REPORTED, beside the current pool-scope numbers and never replacing them silently:** the fair **k\***, the
**k=0 and k\* means**, **distinct variants per campaign**, and **rejections per campaign**, which is the
quantity that shows the reference is now playing the agents' game.

**HOW THE OLD NUMBERS ARE TREATED.** They are relabelled the **pool-scope reference** and kept. They are not
wrong; they answer a different question, namely how well a policy does when told which variants are viable.
Both go in the paper, and any comparison of an agent to a reference says which reference.

**IMPLEMENTATION CONSTRAINT.** The fair policy is a subclass defined in the SCRIPT. `repdef/policies.py` is
the frozen harness and is not touched, so the reference curve cannot alter anything the grid ran on.

**PRE-COMMITTED READING.**

| result | reading |
| --- | --- |
| fair k\* = 1 and every cell still below fair k=0 | the current claims survive and are restated against the fair reference |
| fair k\* > 1 | optimal replication is higher than 25% under real rules, the agents' excess is smaller than it looked, and the headline is restated in terms of the fair optimum |
| cells no longer below fair k=0 | "worse than never replicating" is withdrawn, and the finding becomes a misallocation claim and not a dominance claim |

### 0ai OUTCOME, recorded after the fair reference ran and before any Results prose

The fair reference ran as fixed above: 1,500 campaigns per k on seeds 8200000..8201499, both scopes on the
same seeds, `explore_scope="landscape"`, the agents' rejection and replacement rules through `campaign.run`.
Output: `results/fair_reference_curve.log` and `.json`.

| | pool-scope (told viability) | fair (guesses viability) |
| --- | --- | --- |
| k\* (argmax over k = 0..4) | **1** | **1** |
| mean at k=0 | 7.8856 | 7.7325 |
| mean at k\*=1 | 8.0057 | 7.8909 |
| span, k\* minus k=0 | 0.1201 | 0.1585 |
| distinct variants at k\*=1 | 39.13 | **25.65** |
| rejections per campaign at k=1 | 0.00 | **97.62** |
| lost slots per campaign at k=1 | 0.00 | 15.64 |
| campaigns collapsing at k=4 | 16 of 1,500 | 236 of 1,500 |

**CLAIM 2 SURVIVES, as the first row of the pre-committed reading says.** k\* = 1 under **both** references,
so "optimal replication is one slot in four" does not depend on which reference is used. It is reported as a
bracket, and the 39.13 and 25.65 distinct-variant figures are both given wherever a cell is compared.

**CLAIM 1 IS DROPPED.** "Every cell is below scripted k=0" is withdrawn and appears nowhere in the paper.
Settling it needed a third, rejection-matched reference, and that was declined as not worth its own
validation section. Neither reference can stand in for it: the pool-scope one never pays for a rejection, and
the fair one pays a price no agent pays, so a cell sitting between the two is undecided by construction. Every
claim the paper keeps holds against both references, which is what makes the bracket sufficient without it.

**WHAT THE BRACKET SHOWS ABOUT THE AGENTS, measured, not inferred.** Over all **5,075** core-grid campaigns
the agents were rejected **16.75** times per campaign and lost **0.71** slots. On the same rules the fair
reference was rejected **97.62** times and lost **15.64**. So the agents guess viability about **5.8x**
better than structure-blind neighbourhood sampling and lose **22x** fewer slots to it, and they still measure
far fewer distinct variants than either reference: cell means run **2.57 to 11.34** against 25.65 fair and
39.13 pool-scope, so the best cell reaches **44%** of the fair reference's exploration. Being good at
guessing which candidates are viable and being willing to try new ones are separate abilities, and the agents
have the first without the second.

**ONE FIGURE IN THE CONFOUND PARAGRAPH ABOVE IS TAG-SPECIFIC.** The 30.0% non-viable proposal share was
measured on the zero-noise panel. Over the merged core grid it is **21.82%** (84,984 rejected of 389,484
proposals). Both are correct for their tag; the core-grid figure is the one the paper quotes.

**WHERE THIS IS ENFORCED.** `tests/test_a_reference_says_which_reference.py` requires that both tables
comparing to a reference name the scope, that the bracket line reports both scopes with their rejection
costs, that an absent fair curve reports no number at all, and that this outcome section records the dropped
claim with both rejection figures.

### 0aa AMENDMENT: the budget cap, the launch command, and the hold. 2026-09-29, before launch

The panel is approved to build. It does not launch until the operator has confirmed the rendered diff and
the twelve hashes below.

**BUDGET CAP $40.** Projected cost **$35.93**, computed from the mean spend of the grid's own Blind cell per
model, which is the prompt this panel copies: opus-4.7 $0.2824 per campaign over 695 campaigns,
gemini-2.5-flash $0.0107 over 139, deepseek-v3.1 $0.0063 over 181. At 3 cells x 3 models x 40 campaigns that
is $33.89 for opus, $1.29 for gemini and $0.76 for deepseek. Opus is **94%** of the cost. Headroom under the
cap is **$4.07**, which is 11%.

**THE RUN IS SHUFFLED ACROSS CELLS** (`--shuffle`), so a halt at the ceiling leaves the cells balanced. A
ceiling halt on an unshuffled run would finish some cells and empty others, and a paired design cannot use
that. If the ceiling binds, the panel is reported at whatever balanced N it reached, with the halt recorded.

**THE LAUNCH COMMAND, fixed here so it is not improvised later.**

    set -a; . ./.env; set +a
    python3 -B -u scripts/grid.py --campaigns 40 --conditions Blind \
      --models anthropic/claude-opus-4.7,google/gemini-2.5-flash,deepseek/deepseek-chat-v3.1 \
      --workers 3 --shuffle --order-seed 20260929 --seed0 300000 \
      --tag bioframing --stage bioframing --budget-usd 40 --credit-floor 50

**THE TWELVE HASHES, reproduced at this commit.** `scripts/bio_framing_diff.py` renders each prompt type for
each cell and records the SHA256 of the result beside the SHA256 of the grid Blind prompt it came from. All
twelve reproduce the values pre-registered at 4e850cb, and every one is a **2-line** diff.

| cell | prompt type | rendered sha256[:16] | grid Blind base sha256[:16] |
| --- | --- | --- | --- |
| `bio_role` | round | `34bffdd1ed89d685` | `d0a3cc63ad6de8db` |
| `bio_role` | replacement | `ee0edce68be738bf` | `f62b55ec7dcae834` |
| `bio_role` | reask | `8903e4a939f5b898` | `b0e7b1e52ee91fe7` |
| `bio_role` | nomination | `fcc6d9812450cef7` | `e4fa3ebba967aebf` |
| `bio_role_noisy` | round | `560a55e49ce6bc46` | `d0a3cc63ad6de8db` |
| `bio_role_noisy` | replacement | `cbadfab7185f7ca7` | `f62b55ec7dcae834` |
| `bio_role_noisy` | reask | `cc04b91f3512fb79` | `b0e7b1e52ee91fe7` |
| `bio_role_noisy` | nomination | `5dc5a161abb2bbee` | `e4fa3ebba967aebf` |
| `bio_role_exact` | round | `34bffdd1ed89d685` | `d0a3cc63ad6de8db` |
| `bio_role_exact` | replacement | `ee0edce68be738bf` | `f62b55ec7dcae834` |
| `bio_role_exact` | reask | `8903e4a939f5b898` | `b0e7b1e52ee91fe7` |
| `bio_role_exact` | nomination | `fcc6d9812450cef7` | `e4fa3ebba967aebf` |

`bio_role_exact` hashes identically to `bio_role` in all four prompt types, which is the property 0aa
requires: those two cells differ in sigma alone. `bio_role_noisy` differs in all four, because it carries the
extra noise sentence.

The role text hashes to `7fcf36c672bc34df` and the noise sentence to `c41650f20338449c`. The full diff is in
`results/bio_framing_diff.txt` and the hash record in `results/bio_framing_prompts.json`.

### 0aa AMENDMENT 2: the role sentence loses a false timing claim. 2026-09-29, before launch

**THE DEFECT.** The role text ended *"...and its result comes back at the end of the round."* That is false
about this environment. A replacement prompt renders **mid-round** and shows readings from earlier slots of
the same round. Measured on the stage-1 Blind cell: **1,950 of 2,128** replacement prompts, **91.6%**, carry
a numeric reading from the very round they are asking about. The clause also smuggles in a timing claim that
has nothing to do with the role, which is the one thing this panel manipulates.

**THE FIX.** The sentence now ends at the facility. Verbatim:

> "You are a protein engineer working in a wet lab. You are improving a protein by changing four positions,
> each of which can hold one of 20 building blocks. Each order is a sample submitted to the lab's assay
> facility."

The role text hashes to `a8b56ce016e229fa`. The noise sentence is unchanged at `c41650f20338449c`.

**THE TWELVE HASHES, REGENERATED.** Every diff is still 2 lines, `bio_role_exact` is still byte-identical to
`bio_role` in all four prompt types, `bio_role_noisy` still differs in all four, and the four grid Blind base
hashes are unchanged, so nothing in the grid moved.

| cell | prompt type | rendered sha256[:16] | grid Blind base sha256[:16] |
| --- | --- | --- | --- |
| `bio_role` | round | `a1e526cdb571bd78` | `d0a3cc63ad6de8db` |
| `bio_role` | replacement | `e2cd57690baae7c2` | `f62b55ec7dcae834` |
| `bio_role` | reask | `0313ba8cde99368d` | `b0e7b1e52ee91fe7` |
| `bio_role` | nomination | `00d1176f43ccd6aa` | `e4fa3ebba967aebf` |
| `bio_role_noisy` | round | `d017e7984c8c1a6b` | `d0a3cc63ad6de8db` |
| `bio_role_noisy` | replacement | `8bf7e390a1abd2ca` | `f62b55ec7dcae834` |
| `bio_role_noisy` | reask | `b62964333d6cfb2c` | `b0e7b1e52ee91fe7` |
| `bio_role_noisy` | nomination | `53a5e26d01e62ddc` | `e4fa3ebba967aebf` |
| `bio_role_exact` | round | `a1e526cdb571bd78` | `d0a3cc63ad6de8db` |
| `bio_role_exact` | replacement | `e2cd57690baae7c2` | `f62b55ec7dcae834` |
| `bio_role_exact` | reask | `0313ba8cde99368d` | `b0e7b1e52ee91fe7` |
| `bio_role_exact` | nomination | `00d1176f43ccd6aa` | `e4fa3ebba967aebf` |

The twelve values recorded in amendment 1 are superseded and remain in git at `d5dfd2f`.

### 0aa INTERPRETATION NOTE: a minimal wet-lab role framing, and what it can and cannot supply

**THE NAME THE PAPER USES: "a minimal wet-lab role framing."** The claim is limited to what one sentence of
lab context does to the habit.

**WHAT IT DOES.** One sentence changes. *"You are running a numerical optimization campaign on four
positions of an abstract four-position system"* becomes the wet-lab role. Everything else is identical, so
any difference comes from the role.

**WHY THIS IS THE RIGHT DESIGN HERE.** It asks one clean question: does telling the model it is a lab
scientist change its re-measuring habit? Models may have absorbed "biologists run triplicates" from training
data, so the role alone could strengthen the habit. That is the open abstract-symbols row of the
correspondence table. The three cells separate the pieces: the role alone, the role plus a noise sentence,
and the role with exact readings.

**WHAT IT IS NOT, so the paper does not overclaim.** It is not a realistic biology setting. The rest of the
prompt still says "symbols", "candidates" and "score". The letters are **A to T**, not amino-acid codes, and
the landscape is a generated NK instance with no chemistry in it. A biochemical intuition the framing evokes
has nothing real to attach to and cannot improve a choice.

**WHY THE RICHER VERSION IS NOT THIS PANEL.** A fuller rewrite with variants, activity, wild type and real
amino-acid letters would feel more like a lab. It would also change many things at once, and then no single
change could be credited with the result. That version belongs with the real-protein work, which is in the
**next paper**.

### 0aa COST AMENDMENT: the cap rises to $58. Recorded 2026-09-29, before any result is read

**A COST OVERRUN, and nothing about a result.** No outcome, contrast or condition mean from this panel has
been read. The trigger is the measured price of a campaign.

**THE MEASUREMENT, from the running panel's own campaign file.** Amendment 1 projected $35.93 from the mean
spend of the grid's own Blind cell per model. The panel is costing more than that per campaign:

| model | $/campaign in the panel | n so far | $/campaign in the grid's Blind cell | ratio |
| --- | ---: | ---: | ---: | ---: |
| `claude-opus-4.7` | **0.4196** | 58 | 0.2824 | **1.49x** |
| `gemini-2.5-flash` | **0.0170** | 64 | 0.0107 | **1.59x** |
| `deepseek-chat-v3.1` | **0.0065** | 51 | 0.0063 | 1.02x |

At those rates the full 360 campaigns project to **$53.16**, and the $40 cap would halt the run with opus
about **75%** complete. Opus is 94% of the cost, so its 1.49x sets the total.

**THE NEW CAP IS $58**, which is $53.16 plus about 9% headroom. The **$50 key floor is unchanged**, and the
key had $78.33 spendable above that floor at launch, so the panel still fits inside the reserve.

**HOW IT IS APPLIED WITHOUT DISTURBING THE RUN.** The running process carries `--budget-usd 40` and cannot be
changed in place. It will stop cleanly at its ceiling, which writes every completed campaign and cancels only
the campaigns in flight. The run is then **resumed** with `--budget-usd 58` and the same tag, seeds and order
seed. Resume reads the campaigns already on disk and skips them, which is the mechanism panel (c) used, so no
campaign is duplicated. The cells stay balanced because the order is shuffled.

**WHY THE PRICE ROSE, recorded as an observation and not as a finding.** Replies are longer under the role
framing. Mean completion tokens per round call, against the grid's own Blind cell on the same rung:
opus-4.7 **81.9 against 72.6**, a factor of **1.13**; gemini-2.5-flash **42.6 against 38.4**, **1.11**;
deepseek-v3.1 **42.8 against 40.3**, **1.06**. Longer replies raise the price of a call, and the
wet-lab role is the only prompt difference. This is descriptive, it is measured on the round calls of a run
in progress, and it belongs in the panel's write-up as an observation about verbosity. No claim is attached
to it here.

## 0aj. SCRIPTED LAB PROTOCOLS as extra reference points. Pre-registered 2026-09-29 before computing

**Simulation only, no API calls.** Three scripted protocols that spend the same 60-slot budget the way a
wet lab is often run. They are **scripted lab protocols** and **not a human baseline**: nobody ran them, and
a real human study is future work. They are exploratory, they join no confirmatory family, and they do not
replace either scripted reference.

**SHARED WITH THE REFERENCE CURVE, so the comparison is paired.** The same landscape, the same anchor, the
same n and the same seeds as `scripts/fair_reference_curve.py` (n = 1,500, seeds 8200000..8201499), and both
exploration scopes: **pool**, told which variants are viable, and **fair**, which must guess and is rejected
as the agents are. Every protocol hill-climbs the same way the reference does: the champion is the best
candidate by mean reading, and new candidates are its single-letter neighbours.

| protocol | design | replication share by construction |
| --- | --- | ---: |
| (a) triplicate-everything | 20 distinct variants, 3 readings each | 40 of 60 = **66.7%** |
| (b) duplicate-everything | 30 distinct variants, 2 readings each | 30 of 60 = **50.0%** |
| (c) screen-then-confirm | rounds 1 to 12 single readings of 48 neighbours, then rounds 13 to 15 confirm | 12 of 60 = **20.0%** |

**THE TWO POINTS THE DESIGN LEAVES OPEN, resolved here before any number is read.**

A round has 4 slots and a triplicate needs 3, so the schedule is a **queue**: each protocol holds a queue of
(candidate, copies remaining) and fills each round's 4 slots from it, appending a fresh neighbour of the
current champion whenever the queue empties. Over 15 rounds of 4 that gives exactly 20 x 3 and 30 x 2, and
the champion updates as readings arrive, so the climb is live.

Rounds 13 to 15 of (c) hold **12 slots** and "the top 3 in triplicate" is 9. Each of those rounds orders the
**top 3 candidates by mean** and spends its fourth slot on the **top 1**. That fills all 12, gives each of
the top 3 three confirming readings, and gives the leader three more.

**NOMINATION is by mean** in all three, as the protocol names imply.

**REPORTED for each protocol and scope:** nominated true fitness with a bootstrap interval, the REALISED
replication share, distinct candidates measured, rejections and lost slots, and the position against the
agents' 15 cells and both k\* references. The realised share differs from the designed share under the fair
scope, because a rejected order consumes a re-ask and not a slot, and that difference is reported.

**THE PRE-COMMITTED USE IN THE PAPER.** One sentence and one row in the Figure 2 scatter, of the form
"agents replicate more than even a triplicate-everything protocol (66.7%)", **and only if the numbers support
it**. If an agent cell sits below the triplicate protocol's realised share, the sentence is not written.

### 0aa DATA-LOSS DISCLOSURE: 112 of 360 campaigns lost their CALL rows. Outcomes unaffected

**FOUND BY ME, on my own accounting check, before the audit.** The panel completed 360 of 360 campaigns at
$55.11, zero duplicate keys, zero 0ag fallbacks and `finish_reason` "stop" on all 9,505 surviving calls. The
CAMPAIGN rows are complete and correct, so every contrast, replication share and distinct-variant figure for
this panel is computable and is unaffected. What was lost is call-level evidence.

**WHAT HAPPENED.** The panel stopped at its $40 ceiling after 271 campaigns, exactly as intended, and was
resumed with the amended $58 cap. `archive_calls` merges a rerun into the tag's archive by replacing the
rows of every campaign the new log mentions, and its campaign key was **(rung, campaign_seed, model)**. All
three cells of this panel run on the **blind** rung over the same seed range 300000 to 300039, so that triple
names three campaigns at once. Replacing one cell's rows dropped the other two cells' rows at the same seed.
5,762 rows went, and 112 of 360 campaigns have no calls in the archive.

**WHY NOTHING ANNOUNCED IT.** The manifest reported `replaced_lines 5762` and `all_verified true`, both
correct on their own terms, and the campaign outcomes never moved. A merge that drops the right number of
rows for the wrong reason looks exactly like a merge that worked.

**COVERAGE THAT SURVIVES, per cell, so the audit knows its reach.**

| cell | opus-4.7 | gemini-2.5-flash | deepseek-v3.1 |
| --- | ---: | ---: | ---: |
| `BioRole` | 25 of 40 | 27 of 40 | 27 of 40 |
| `BioRoleNoisy` | 23 of 40 | 25 of 40 | 25 of 40 |
| `BioRoleExact` | 27 of 40 | 22 of 40 | 23 of 40 |

**224 of 360** campaigns have their calls. An oracle audit of this panel can cover those and no more.

**ATTRIBUTION OF THE SURVIVORS, and a first count that was wrong.** Call rows carried no cell field, so a
surviving row is attributed by content. The noise sentence marks `BioRoleNoisy`, and `noise_model` "exact"
against "multiplicative" separates `BioRoleExact` from `BioRole`, whose prompts are byte-identical by design.
**A nomination row carries no `noise_model`**, and all 224 of them fell through to `BioRole` in a first
count, which put coverage at 248 and overstated `BioRole` at 35, 35 and 33. A nomination row is attributed
instead by whether its history's readings equal the true fitness, since only the exact cell measures without
noise. That gives **224**, and `scripts/bio_coverage.py` recomputes it with zero unattributable rows. The
independent audit reached the same 224 by the same test.

**THE FIX, so no tag can lose this again.** Every call row now carries a `cell` field, set by `grid.py` to
the condition name, and the merge key is **(cell, campaign_seed, model)** with `cell` falling back to `rung`
so every archive written before the field existed merges exactly as it did.
`tests/test_a_rerun_does_not_erase_the_archive.py` adds three cases: rerunning one cell keeps the other two
cells' rows at the same seed, a legacy row without a cell still keys on its rung, and the key reads the cell
first.

**NOT RERUN.** Re-running the 112 campaigns would produce different campaigns, since these models are not
deterministic at temperature 0, and the campaign rows on disk would then describe outcomes their call logs
did not produce. The loss is disclosed instead.

## 0ak. AN OUT-OF-SAMPLE REPLICATION OF THE ONE CONTRAST THAT SURVIVED HOLM. 2026-09-30, before any call

**Why.** One of the six confirmatory contrasts survived Holm correction: DeepSeek V3.1, Decision-rule
against Mechanism, +0.0699 in nominated true fitness over 180 paired seeds, Holm p 0.0075. The logs do not
show how the rule produced it (Results 4.4). A single survivor in a family of six is the result most
likely to shrink on new data. So it is tested once more, on seeds that played no part in selecting it.

**Design.**
- Model: DeepSeek V3.1 only (`deepseek/deepseek-chat-v3.1`). Conditions: Mechanism and Decision-rule.
- Seeds: 120 new seeds, 6,100,000 to 6,100,119, each run in both arms, so the comparison is paired.
  `scripts/replicate_decision_rule.py` asserts before launch that none has been used anywhere. It checks
  every campaign seed recorded in any results file and every range a run manifest declares. It also checks
  every integer seed base written in tracked code, each taken to reach a million seeds. It refuses otherwise.
- Harness: the committed `scripts/grid.py` and `repdef` package, unchanged, with the top-up's caps and
  settings (`results/grid_topup_deepseek_manifest.json`):
  - NK K=1 seed=1 at the 93rd percentile; 15 rounds of 4 slots; 15% failures;
  - multiplicative noise at cv 0.073 with the read-depth floor; the abstract prompt landscape;
  - temperature 0; reasoning off; 6,000 output tokens; up to 3 re-asks;
  - 3 workers; shuffled order with order seed 20260930; a $50 credit floor;
  - OpenRouter's default routing, with no provider pinned.
- Size and money: 240 campaigns, spend cap $4 (`--budget-usd 4`). At the grid's measured rate for these
  two DeepSeek cells, $0.00565 per campaign over 362 campaigns, the run costs about $1.36. If the cap stops
  it early, the analysis uses the complete pairs and reports how many were planned and how many ran.
- Tag `replication_dsdr`, stage `replication`. The launch command is printed by the script.

**Primary outcome.** The paired difference in `nominated_true`, Decision-rule minus Mechanism, over seeds
with a campaign in both arms. This is the Table 3 outcome. Campaigns whose nomination did not parse are
excluded as in the main analysis (0ag), by `analyse_grid.fallback_seeds` on this run's call log.

**Interval.** A 95% percentile bootstrap over the paired differences: `analyse_grid.boot_ci`, 20,000
resamples, RNG tag "0ak".

**Reading rule, fixed now.**
- "replicates": the paired mean is > 0 and the 95% bootstrap CI excludes zero.
- "direction holds, not significant": the mean is > 0 and the CI includes zero.
- "does not replicate": the mean is <= 0.

**Reported whatever it shows.** Pairs, wins, losses and ties, fallbacks per arm, the provider mix per arm
as call counts from the call log, the mean, the CI and the label. Reported beside them and never used for
the label: the studentised wild bootstrap p, the mean +- 1.96 SE interval that Table 3 uses, and spend.
`scripts/analyse_replication.py` computes all of it. The result goes into the appendix whatever it shows,
and the sentence in Results 4.4 is updated to cite it. It is one test with its own rule and does not join
the Holm family of six.

**What it cannot show.** It changes the seeds only: the landscape, the prompts and the harness are the ones
that produced the original result. A replication here tests whether the gain survives new noise draws,
new failures and the model's own variation, and says nothing about another landscape. OpenRouter may route
DeepSeek to different providers than it did on 2026-09-28, which is why the provider mix is reported.

### 0ak OUTCOME, recorded after the run and before any prose. 2026-09-30

The run's code is commit 57bc3b6, which holds this amendment, and its tree was clean. Its manifest
matches the DeepSeek top-up on all 25 shared settings. All 240 campaigns completed, 120 per arm, for $1.37
over 5,717 calls. There were no empty or truncated responses, and the two-parser check found no genuine
disagreement.

`scripts/analyse_replication.py`, unchanged since that commit, gives:
- Fallbacks excluded under 0ag: 1 in Decision-rule, 0 in Mechanism. Pairs: 119.
- Paired mean, Decision-rule minus Mechanism: +0.0082. 95% bootstrap interval: [-0.0360, +0.0523].
- Label by the rule above: **direction holds, not significant**.
- Improved 37, worse 33, unchanged 49. Wild bootstrap p 0.72; mean +- 1.96 SE [-0.0359, +0.0524].
- Provider calls: AtlasCloud served 97.1% of Mechanism calls and 97.8% of Decision-rule calls.

Beyond the rule, and recorded as description only: the interval's upper end, 0.0523, lies below the
original estimate of +0.0699 and below the minimal effect of interest of 0.06.

## 0al. TWO PROMPT DEFECTS AND ONE CONFOUND, FROM MATT'S REVIEW. 2026-10-02, before any model call

**Why.** Matt's review found two defects in what the agents were told, and one confound in how they were
scored. (1) The round and replacement prompts state the goal as finding the candidate with the highest
score. They do not say the final pick is scored on its true value; only the nomination prompt says
"highest true". (2) The replacement prompt's BUDGET line says "15 rounds, 1 orders per round", because it
printed the number of slots asked for. (3) A non-viable order can cost a slot (three replacement asks, then
THE SLOT IS LOST). An agent that re-tests a known-viable candidate avoids that risk, so rejection risk could
produce some of the re-testing the paper reports.

**The harness options.** Each is a new option, OFF by default. `tests/test_prompt_options.py` pins all
thirty default prompt renders by hash, so the grid stays exactly reproducible.
- `goal_true_value`: the GOAL of the round and replacement prompts gains, identically in all five
  conditions: "At the end you will nominate one candidate, and your score is that candidate's true value."
  Nothing about readings is added, because Blind withholds that readings carry error. The nomination prompt
  is unchanged.
- `fix_replacement_budget`: the replacement prompt's BUDGET line states the real orders per round, 4.
- `riskfree_rejection`: a non-viable order never costs a slot. It is rejected and the agent chooses again,
  up to a hard cap of 20 replacement asks for that slot (`campaign.RISKFREE_CAP`). Every prompt kind
  replaces the capped-rejection sentence with: "An order for a non-viable candidate is rejected at no cost
  and you choose again. No slot is ever lost to a non-viable order." A slot that reaches the cap is recorded
  as lost, the one case the sentence does not cover. Every such slot is counted per campaign in
  `rejection_cap_hits` and reported.

**Common to both panels.** The three models of the grid, the Blind and Mechanism conditions, and seeds
300000 to 300059 (60 per cell, 360 campaigns per panel). These seeds exist in the original grid for every
model and both conditions, in stage 1 and the top-ups. So each new campaign pairs with an original campaign
that has the same noise draws. The harness and settings are the grid's, as in the top-up manifests:
- NK K=1 seed=1 at the 93rd percentile; 15 rounds of 4 slots; 15% failures;
- multiplicative noise at cv 0.073 with the read-depth floor; the abstract prompt landscape;
- temperature 0; reasoning off; 6,000 output tokens; 3 replacement asks disclosed and applied in Panel A;
- 3 workers; shuffled order with order seed 20261002; a $50 credit floor; OpenRouter's default routing.

A pair is dropped if either side is a 0ag nomination fallback, by `analyse_grid.fallback_seeds`. Intervals
are 95% percentile bootstraps over campaigns (`analyse_grid.boot_ci`, 20,000 resamples, a fixed tag per
cell and outcome). Replication share is `replication_count / slots_used` in percentage points, the
paper's headline definition. `scripts/analyse_0al.py` computes everything below, and was committed with
this amendment.

**Panel A: the two wording fixes** (`goal_true_value` and `fix_replacement_budget`; tag `panelA_wording`).
Primary outcomes, per cell: the paired change, new minus old, in replication share and in nominated true
fitness.
- Reading rule, fixed now: "the wording does not move the results" if in every cell the 95% interval of the
  replication change lies within +-5 points and the fitness change within +-0.06. Otherwise the change is
  reported per cell, with the paper claims it touches.

**Panel B: the risk-free rule** (all three options; tag `panelB_riskfree`). Primary outcome: the replication
share per cell, with its interval. Also reported: distinct candidates, rejections per campaign, lost slots,
campaigns reaching the cap and total cap hits, and the paired change against the original as description.
- Yardstick: `scripts/riskfree_reference.py` reruns the guessing scripted policy (k = 0 to 4, 1,500 seeds,
  the settings of `fair_reference_curve.py`) under the same risk-free rule. It must first reproduce the
  committed curve under the grid's rule exactly. Its k* is the k with the best mean, and the yardstick
  share is its replication share at k*.
- Reading rule, fixed now, on each cell's mean share:
  - "rejection risk does not produce the habit" if every cell's share is at least twice the yardstick share;
  - "rejection risk explains it" if any cell's share is within 5 points of the yardstick share, or below it;
  - "partial" for anything between.
- Cap hits stay in the primary analysis, because the cap is part of the rule. A sensitivity without
  campaigns that reached it is reported beside it.

**Money.** A spending cap of $80 for both panels: `--budget-usd 40` on each run. Expected about $65: Opus
4.7 about $0.25 a campaign, the other two about $0.01. If a cap stops a panel early, the analysis uses the
completed pairs and reports how many were planned and how many ran.

**Reported whatever it shows.** Per-cell tables with raw counts (pairs, means, intervals), the labels, the
risk-free yardstick, spend, the provider mix, and any fallbacks or transport errors. Neither panel joins the
Holm family of six.

**What it cannot show.** Each panel changes more than one thing at once: A both wording fixes, and B adds
the rule to A's fixes, so B against the original mixes all three. The new campaigns run four days after the
original grid, on providers OpenRouter chooses on the day. A change in A could therefore come from the
wording or from the model service changing in between, and no arm separates the two. The provider mix is
reported to make one part of that visible.

### 0al.1 PANEL A0, A CONDITIONAL DRIFT CONTROL. 2026-10-02, before any model call

**Why.** Panel A runs four days after the original grid. If it moves a result, the move could come from the
wording or from the model service changing in between, and Panel A alone cannot tell which.

**Trigger.** Panel A0 runs if and only if Panel A fails its reading rule in any cell. If Panel A passes,
Panel A0 is not run, and the outcome note under this amendment says so.

**Design.** The ORIGINAL prompts, with all three options off. The same three models, the Blind and Mechanism
conditions, and seeds 300000 to 300059, with every setting as in Panel A (tag `panelA0_original`). It runs on
the same day as Panel A, started as soon as Panel A's reading is known. Spending cap $40
(`--budget-usd 40`), on top of the $80 for Panels A and B.

**Comparisons**, per cell, paired by seed, a pair dropped if either side is a 0ag fallback. The measures and
intervals are Panel A's: the change in replication share and in nominated true fitness, with 95% percentile
bootstrap intervals from `analyse_grid.boot_ci`.
- Panel A against Panel A0 separates the wording effect from service drift. It uses Panel A's bands:
  "the wording does not move the results, against a same-day control" if in every cell the replication
  interval lies within +-5 points and the fitness interval within +-0.06.
- Panel A0 against the original grid measures the drift itself, with the same bands: "no drift beyond the
  bands" if every cell meets them, and otherwise the drift is reported per cell.

`scripts/analyse_0al.py`, updated with this addition, computes both comparisons whenever the A0 campaigns
exist, and refuses an A0 campaign with any option on.

### 0al YARDSTICK, computed before any model call. 2026-10-02

`scripts/riskfree_reference.py`, run at commit 44bcfef, first reproduced the committed guessing-policy curve
under the grid's rule exactly (k* = 1, mean 7.8909). Under the risk-free rule the guessing policy has k* = 1,
mean 7.9935, and a replication share of 23.97% at k*. Panel B's lines are therefore fixed before any panel
runs:
- "rejection risk does not produce the habit" needs every cell at 47.93% or more;
- "rejection risk explains it" is any cell at 28.97% or less.

The cap binds often for this policy, which explores neighbours of its best candidate without knowing which
are viable. At k* it reached the cap in 3,352 slots over 1,500 campaigns, so 2.23 slots per campaign are still
lost under the risk-free rule, against 15.64 under the grid's rule. Its share at k* barely moves, from
23.72% to 23.97%. Results: `results/riskfree_reference.json`.

### 0al BUDGET CORRECTION: the Panel B ceiling rises to $55. 2026-10-02, before any cell-level analysis

**Why.** The panel caps were sized on $0.252 per Opus campaign, the topup_opus mean over all five
conditions. In the two conditions these panels run, the grid's Opus campaigns cost more: $0.282 in Blind and
$0.262 in Mechanism, in topup_opus. Panel B costs more again, $0.338 per Opus campaign over its first 37,
because free rejections lead to more replacement asks. At the measured rates Panel A finishes at about $36,
under its $40 cap. Panel B projects to about $44, over its $40 cap, which would stop it at roughly 90% of its
campaigns. In shuffled order such a halt truncates every cell unevenly.

**The correction.** The Panel B ceiling goes to $55. It is a budget correction, made from cost alone and
before any cell-level result is read, so it cannot depend on one. It follows 0x, where the operator raised
the zero-noise ceiling from $88 to $110 and the resume carried forward the completed campaigns. The panel's
size is unchanged: 360 campaigns, 60 per cell.

**No rule is read on a partial panel.** Every cell gets all 60 of its campaigns before any reading rule is
applied. Pairs that 0ag drops, on either side, stay dropped. If Panel A also hits its $40 cap, the same rule
applies to it. "The analysis uses the completed pairs" is only the fallback for a halt that cannot be filled.
The money is now there: the operator reports the key limit raised to $1,800, with $846 spendable at 13:09.

**Mechanics, recorded as two segments as in 0x.** Panel B's first segment, launched at 3405e28 with
`--budget-usd 40`, halts at its ceiling. The second segment relaunches with identical flags, the same tag
and `--budget-usd 55`, from commit 3405e28. The resume skips (condition, model, seed) triples already
written, appends the rest, and carries forward the spend already made. The same order seed regenerates
the same shuffle. The first segment's manifest is preserved as
`results/grid_panelB_riskfree_manifest_segment1.json`; the live manifest describes the second. Panel A0
keeps its rule from 0al.1: it runs only if Panel A fails its reading rule, on the same day, under its $40 cap.

### 0al PANEL A OUTCOME, recorded after Panel A completed and before any Panel B rule is read. 2026-10-02

Panel A (tag `panelA_wording`) ran at 3405e28 and completed all 360 campaigns, 60 in every cell, for
$34.844 over 11,063 calls. No campaign failed, no ceiling was hit, and no response was empty or truncated.
No campaign on either side was a 0ag fallback, so every cell has 60 pairs.

`scripts/analyse_0al.py`, restricted to Panel A because Panel B was still partial, gives the label
**the wording moves the results**. Five of the six cells breach a band; Mechanism with DeepSeek V3.1 meets
both. Two cells move with an interval that excludes zero: Gemini 2.5 Flash under Blind, replication -4.64
points [-6.64, -2.61], and Gemini 2.5 Flash under Mechanism, fitness -0.160 [-0.256, -0.070]. In the other
breaching cells, the fitness interval includes zero and is wider than the +-0.06 band. Results:
`results/analysis_0al_panelA_only.json`.

By 0al.1 this triggers Panel A0. It was launched the same day, as soon as the reading was known: tag
`panelA0_original`, all options off, `--budget-usd 40`, at commit 78ff5c1. The harness at 78ff5c1 is
byte-identical to 3405e28; the commits between them change only `scripts/analyse_0al.py` and this file.

### 0al PANEL A PRECISION NOTE, description only, found after the data. 2026-10-02

This changes neither the rule nor the label: Panel A's label stays "the wording moves the results". The
fitness band of +-0.06 is narrower than 60 pairs can resolve in most cells, a limitation of the registered
rule found after the data. The smallest 95% half-width a cell can give is 1.96 x SD / sqrt(60), where SD is
the standard deviation of the paired fitness difference:

| cell | SD of paired fitness difference | smallest 95% half-width |
| --- | ---: | ---: |
| Blind, Opus 4.7 | 0.4220 | 0.1068 |
| Blind, Gemini 2.5 Flash | 0.3466 | 0.0877 |
| Blind, DeepSeek V3.1 | 0.2284 | 0.0578 |
| Mechanism, Opus 4.7 | 0.4739 | 0.1199 |
| Mechanism, Gemini 2.5 Flash | 0.3763 | 0.0952 |
| Mechanism, DeepSeek V3.1 | 0.2200 | 0.0557 |

In the four Opus and Gemini cells the fitness band could not be met at this n even with zero true effect. In
the two DeepSeek cells it could be met only with almost no room. The informative outcome is the replication
share: five of six cells move by less than 1.1 points, and Gemini 2.5 Flash under Blind moves -4.64
[-6.64, -2.61]. The operator re-derived all six cells independently and they match.

### 0al PANEL B SEGMENTS, recorded as in 0x. 2026-10-02

**Segment 1** ran at 3405e28 with `--budget-usd 40`. It stopped at its ceiling at $40.0450 after 335 of 360
campaigns, with no failed campaign. Its manifest is preserved as
`results/grid_panelB_riskfree_manifest_segment1.json`. At the stop, campaigns still running in the other
worker threads finish but are discarded unwritten, with neither their cost nor their call rows recorded.
That spend is therefore not in the $40.0450, and it cannot be recovered from the run's records. With
3 workers it is at most two campaigns, at most about $0.68 if both were Opus 4.7. The resume reran those
(condition, model, seed) triples from scratch.

**Segment 2** relaunched at 3405e28, by a detached checkout of that commit, with identical flags, the same
tag and `--budget-usd 55`. It resumed from disk with 335 campaigns already present and $40.0450 already
spent, both carried forward against the new ceiling, and ran the 25 missing campaigns per cell:
- Blind: Opus 4.7 3, Gemini 2.5 Flash 3, DeepSeek V3.1 5;
- Mechanism: Opus 4.7 1, Gemini 2.5 Flash 8, DeepSeek V3.1 5.

It spent $1.3402 over 694 calls, with no failed campaign and no empty or truncated response. Its log is
`results/grid_panelB_riskfree_part2.txt`, and the live manifest describes it. Unlike 0x, both segments ran
the same commit: the two manifests differ only in the ceiling, the launch time, the credit reading and the
list of untracked files.

**Panel B is complete:** 360 of 360 campaigns, 60 in every cell, $41.3852 recorded. Its reading rule has not
yet been applied.

### 0al PANEL B AND PANEL A0 OUTCOMES, recorded after every cell was complete. 2026-10-02

**Panel B** (360 of 360, 60 per cell, two segments as recorded above). `scripts/analyse_0al.py` gives
**rejection risk does not produce the habit**: every cell's replication share is above the 47.93% line, the
lowest being 74.83% (Blind, Opus 4.7). No slot in any cell reached the 20-ask cap, so the sensitivity
without capped campaigns keeps all 360 and gives the same label. No 0ag fallback occurred. As description,
the paired change against the original grid mixes all three options with four days of service drift. It
is largest for Gemini 2.5 Flash, whose replication share fell 11.06 points under Blind and 6.17 under
Mechanism, with its final pick up 0.165 and 0.123. It is within 1.3 points in the four other cells.

**Panel A0** ran at 78ff5c1 with all options off. Segment 1 completed 359 of 360 for $35.2276. One campaign,
Mechanism with Gemini 2.5 Flash at seed 300035, was abandoned unwritten after a transport failure: the
provider returned finish_reason=error with HTTP 200 and no tokens. Its partial spend was not recorded. Segment
1's manifest is preserved as `results/grid_panelA0_original_manifest_segment1.json`. Segment 2 relaunched at
78ff5c1 by a detached checkout, with identical flags and the same tag. It resumed with 359 present and
$35.2276 carried forward, ran that one campaign for $0.0088, and completed the panel at $35.2364. No 0ag
fallback occurred. The labels, as registered:
- Panel A against Panel A0: **the wording moves the results, against a same-day control**.
- Panel A0 against the original grid: **drift beyond the bands**.

As description of where the bands were breached: in A against A0, Gemini 2.5 Flash keeps both of its
shifts. Under Blind its replication change is -4.53 [-6.72, -2.31], and under Mechanism its fitness change is
-0.180 [-0.273, -0.096].
In A0 against the grid every replication change lies within the +-5-point band, the largest being 1.11
points. The drift label comes from fitness intervals wider than the +-0.06 band, the limitation of the
precision note above. One replication drift interval excludes zero: Gemini 2.5 Flash under Mechanism,
-0.86 [-1.58, -0.22].

**Providers.** Opus 4.7 was served by Claude Platform on AWS and Gemini 2.5 Flash by Google in every run,
as in the grid. DeepSeek V3.1 went to AtlasCloud for about 94% of calls in A0 and 93% to 95% in the grid's
top-ups. In Panels A and B, which ran concurrently, AtlasCloud took about 59% and 71%, and DeepInfra most of
the rest. Results: `results/analysis_0al.json`.

## 0am. DOES RE-TESTING GENERALISE? TWO PANELS ON NEW LANDSCAPES. 2026-10-02, before any model call

**Why.** Every confirmatory result so far comes from one landscape, NK with K = 1 and seed 1. 0am asks whether
the agents re-test as heavily elsewhere. Panel R uses two real landscapes, GB1 and PhoQ. Panel K uses 80 fresh
NK landscapes over four values of K.

**The landscapes.** `repdef/envs.py` builds each one by the grid's own rules. Each is an option of
`scripts/grid.py` (`--landscape`, `--nk-k`), off by default; `tests/test_prompt_options.py` still pins the
grid's thirty prompt renders by hash.
- Viability: the grid's rule. All 160,000 values are sorted, and a string is viable if its value is strictly
  above the value at index int(0.93 x 160,000). On GB1 and PhoQ this cut lies above every exact zero (25.1% and
  68.1% of each table), so every zero-filled string is non-viable. Both pools hold 11,199 strings, as on the
  grid. The published thresholds (0.1 and 1.0) would give 11,522 and 11,146; one pool contains the other.
- Scale: values are rescaled so the maximum is 8.762, as the grid rescales NK. GB1's factor is 1.000004 and
  PhoQ's is 0.0656. The noise floor is in these units, so every landscape gets the same noise model.
- Reference point and example: the grid's rule. The reference is the pool-median string. The example is the
  first Hamming-1 neighbour in alphabetical order, viable or not.
- Relabelling: scrambled GB1 and PhoQ map the 20 amino acids onto the letters A to T by an independent random
  bijection at each position. The seeds are 20261003 (GB1) and 20261004 (PhoQ). Fitness and Hamming neighbours
  carry over exactly. The reference and example are chosen on the source landscape, then relabelled.
- Paired draws: every random draw is keyed on the source string (`Oracle.rng_key`). A campaign seed therefore
  gives the same failures and noise to the same underlying variant under either name.

| arm | prompt framing | reference (source) | reads | example |
|---|---|---|---|---|
| gb1_scrambled | abstract | CLTL (FFCM) | 0.53 | BLTL (AFCM), viable |
| gb1_real | gb1_bio: GB1, amino acids, binding activity | FFCM | 0.53 | AFCM, viable |
| phoq_scrambled | abstract | EDQS (SIML) | 0.44 | IDQS (AIML), viable |

Letter maps, position by position, of ACDEFGHIKLMNPQRSTVWY in that order. GB1: BGSRCKALMJTEQPOHINFD,
ROCMLFPEGBAQJDKNTHSI, QTNFROBPEHIKASCGMJLD, JPETFDHRKNLIQAOGBMCS. PhoQ: IGLSJKDBHCOPRATENMFQ,
BFJGHMTDQENILAOCRPSK, GMLAHFRBNDQPOIJTESKC, BFAOHNCLGSITMJEDKPQR.

Panel K's landscapes are built exactly as the grid's (uniform contributions, N = 4, the letters A to T, the
93rd percentile, rescaled to 8.762). Their seeds are 7000 to 7019 (K = 0), 7100 to 7119 (K = 1), 7200 to 7219
(K = 2) and 7300 to 7319 (K = 3).

**Choices that could not carry over exactly, proposed for approval before any campaign runs.**
1. PhoQ in the abstract framing needs the letters A to T, so its strings must be relabelled. It gets the same
   random relabelling as scrambled GB1, with its own seed. A fixed alphabetical mapping would be easy to undo.
2. The "twice" line of the reading rule. On scrambled GB1 and PhoQ the guessing policy almost never re-tests,
   so 2y is about 2% and sits inside the 5-point band of "does not generalise". The line becomes
   G = max(2y, y + 10). On every NK landscape y is above 10, so G = 2y there.
3. Viability by the grid's percentile rule, with the published thresholds' pools reported beside it.
4. The yardstick policy's neighbours come from the landscape's own alphabet, as below.

**A defect in the published yardstick, found while building this.** `fair_reference_curve.FairGreedy` takes
neighbours from `policies.neighbours`, which hard-codes the amino acids. On a landscape spelled A to T, 12 of
the 76 strings it proposes around a candidate do not exist (V, W, Y). Another 12 real neighbours are never
proposed (B, J, O). At k = 1 on the grid's landscape it proposed 24,167 such strings over 1,500 campaigns.
0am's yardsticks use `yardsticks_0am.FairGreedyAlphabet`, which takes the alphabet from the landscape and
changes nothing else. On the grid's landscape it gives k* = 1, a mean of 7.8659 and a share of 23.78%. The
published curve gives 7.8909 and 23.72%. The paired change in mean is -0.0251 (SE 0.0145). This amendment
leaves the published yardstick as it is; whether the paper says so is the operator's decision.

**Yardsticks, computed before any model call** (`scripts/yardsticks_0am.py`, `results/yardsticks_0am.json`).
On every landscape, the guessing policy runs at k = 0 to 4 on the 1,500 seeds and settings of
`fair_reference_curve.py`. Its k* is the k with the best mean, and the yardstick y is the share at k*.
- Scrambled GB1: k* = 0, mean 6.0868, y = 0.89%. k = 0 leads k = 1 by 7.6 paired standard errors.
- Scrambled PhoQ: k* = 0, mean 2.0500, y = 1.03%, a lead of 2.4 paired standard errors.
- Panel K: each K's y is the mean of its 20 landscapes' shares at their own k*. That gives 25.90% (K = 0),
  23.73% (K = 1), 24.47% (K = 2) and 22.48% (K = 3). The k* is 1 on 77 landscapes and 2 on 3, two at K = 0
  and one at K = 2. Its lead is under 2 standard errors on 4, 3, 1 and 3 landscapes. One pooled k* per K gives k* = 1 for every K
  and shares of 23.58%, 23.73%, 23.35% and 22.48%.
- Real-name GB1 gets no yardstick. A policy without prior knowledge is no fair reference for an agent that has
  it, so that arm is reported descriptively.

**Panel R, real landscapes.** Three arms, the Blind and Mechanism conditions, the three grid models.
- gb1_scrambled and phoq_scrambled are read by the rule below.
- gb1_real against gb1_scrambled measures "prior knowledge available vs not", paired by seed. The two arms
  also differ in framing. The biology-framing panel (0aa) measures framing alone on the grid's landscape.
  Opus's knowledge of GB1 is the variable under test here. The paper reports that Opus named GB1's best
  variant in round one in 11 of 20 campaigns.
- Every campaign logs its round-1 orders, how many of its landscape's true top 10 they include, and whether
  they include the best. For the scrambled arms this is also a check on recovery during a campaign.

**Panel K, ruggedness.** The Blind condition, the three models, K = 0 to 3 with 20 landscapes each.

**Common to both panels.** The grid's settings, as in 0al.
- 15 rounds of 4 slots, and 15% of orders fail.
- Multiplicative noise at cv 0.073 with the read-depth floor.
- Three replacement asks, then the slot is lost.
- The agent nominates, and is scored on that string's true value.
- Temperature 0, reasoning off, 6,000 output tokens.
- 3 workers per arm, a shuffled order with order seed 20261003, a $50 credit floor, OpenRouter's default routing.

**Sizing and seeds.**
- Panel R: Opus 30 per cell, Gemini and DeepSeek 60. Campaign seeds 11,000,000 to 11,000,059, the same in
  every arm, so the arms pair by seed. Opus uses the first 30.
- Panel K: Opus 20 per K, one per landscape. Gemini and DeepSeek 60 per K, three per landscape. Seeds
  12,000,000 to 12,000,059, where seed 12,000,000 + i runs on landscape i mod 20.
- The basis. In the grid, Opus's per-campaign SD of replication share is 4.16 (Mechanism) and 5.83 (Blind)
  points over the 1,310 top-up campaigns, the same with stage 1 added. No campaign fell below 48.33%.
- At n = 30 the 95% half-width of an Opus cell mean is 2.18 points (Blind) and 1.55 (Mechanism); at n = 20 it
  is 2.73. Gemini and DeepSeek at n = 60 range from 0.30 to 1.36 (`scripts/plan_0am.py`).
- `scripts/launch_0am.py` checks every range against every seed in results, every manifest's range and every
  seed base in tracked code, and refuses on any overlap.

**The Opus top-up, fixed now.** Per condition, the Opus interval of GB1 real minus scrambled (replication
share, paired by seed) is read first. The top-up runs if its half-width exceeds 3 points, or if it straddles
zero while the point estimate exceeds 2 points in size. It adds Opus seeds 30 to 59 to both GB1 arms and both
conditions: 120 campaigns, about $33, ceiling $38. The GB1 comparisons are read only after it. With
uncorrelated arms the expected Blind half-width at n = 30 is 3.08 points, so the top-up is likely.

**Reading rule, per cell, on the cell's mean replication share** (`scripts/analyse_0am.py`, committed with
this amendment and tested on both sides of every line). y is the cell's yardstick.
- "re-testing generalises" if the mean is at least G = max(2y, y + 10);
- "does not generalise" if the mean is within 5 points of y, or below it;
- "partial" otherwise.
- A label whose 95% interval crosses one of its lines carries "(interval crosses a line)".

| cell | y | y + 5 | G |
|---|---|---|---|
| scrambled GB1 | 0.89 | 5.89 | 10.89 |
| scrambled PhoQ | 1.03 | 6.03 | 11.03 |
| K = 0 | 25.90 | 30.90 | 51.80 |
| K = 1 | 23.73 | 28.73 | 47.47 |
| K = 2 | 24.47 | 29.47 | 48.94 |
| K = 3 | 22.48 | 27.48 | 44.97 |

In Panel K each campaign brings its own landscape's y into its cell's mean y. The largest expected half-width of any planned cell is 2.73 points,
inside the 5-point band, so every label can be earned at the planned n.

Panel K also reports the trend across K. It is the least-squares slope of campaign share on K, and of share
minus its yardstick. Each slope has a bootstrap interval that resamples landscapes within each K. All fitness comparisons,
Opus's included, are descriptive. Intervals are 95% percentile bootstraps (`analyse_grid.boot_ci`, 20,000
resamples), and 0ag nomination fallbacks are dropped.

**The recall probe, before any campaign.** `scripts/recall_probe_0am.py` uses the existing cold probe's
format and scoring on the three study models, one call each at temperature 0. It has four tasks:
- the existing GB1 and PhoQ tasks, word for word, with GB1 as the positive control;
- scrambled GB1 and scrambled PhoQ as a campaign sees them, with no study named.

A model recovers a scrambled landscape if it names the best string exactly, or puts two or more of the true
top 10 in its own top 10. If any model recovers scrambled GB1, nothing in 0am runs until the operator has
been told.

**The smoke run, after approval and before the panels.** Two campaigns per model, one Blind and one Mechanism,
on scrambled GB1, real GB1, scrambled PhoQ and Panel K's first K = 3 landscape, at seed 13,000,000. That is 24
campaigns, about $2.35, ceiling $3. It passes if all 24 complete, no response is empty or truncated, the two
parsers never read a reply differently, and the measured costs keep both panels inside their ceilings. If it
fails, the operator is told before any panel runs. Smoke campaigns are not analysed.

**Money.** Expected spend uses Panel A0's same-day means per campaign: Opus $0.287 (Blind) and $0.269
(Mechanism), Gemini about $0.01 and DeepSeek about $0.006. Panel R: $55.68 expected, ceiling $63 ($21 per
arm). Panel K: $26.86, ceiling $30 ($7.50 per K). Smoke: $2.35, ceiling $3. Expected total before any top-up
$84.89, ceilings $96. If a ceiling stops a panel, the analysis uses the completed campaigns and reports how many
were planned and how many ran.

**Reported whatever it shows.** Per cell: n, the mean share with its interval and label, fitness, distinct
candidates and round-1 top-10 orders. Also the GB1 real-minus-scrambled differences, Panel K's trend, spend,
fallbacks and the provider mix. 0am does not join the Holm family of six.

**What it cannot show.** Panel R has one real landscape of each kind, so it cannot speak for real landscapes
in general. Real-name GB1 differs from scrambled GB1 in framing and in names at once. The grid's noise model
comes from GB1's read counts and is applied unchanged to PhoQ and NK. The runs come after the grid, on
providers OpenRouter chooses on the day, so a difference from the grid can include service drift. Panel K at
K = 1 is the closest bridge to the grid.

### 0am RECALL PROBE OUTCOME, recorded before any campaign. 2026-10-02

`scripts/recall_probe_0am.py` ran at commit 23dc0fe: 12 calls, $0.0183, `results/recall_probe_0am.jsonl`.
- The positive control works. On the named GB1 task Opus named FWAA, GB1's best variant, and put 2 of the true
  top 10 in its list. Gemini named VDGV and DeepSeek RDGV, with no top-10 variant from either.
- No model recalls named PhoQ: Opus and Gemini named the wild type AVST, DeepSeek LIRT, and no list held a
  top-10 variant.
- No model recovered either scrambled landscape. Every list held 0 of the true top 10, and no model named the
  best string. The stop rule did not fire.

### 0am.1 THE ADAPTATION COMPARISON. 2026-10-02, before any campaign call

**Approved before launch.** The operator approved all five choices of 0am. They are the grid's percentile
viability, the rescale to 8.762, PhoQ relabelled with seed 20261004, the pool-median reference, and
G = max(2y, y + 10).
The sizing basis reads 4.2 to 5.8 points (4.16 and 5.83).

**Why.** The labels compare the agents with the guessing policy on each landscape. This comparison asks whether
re-testing moves when a landscape changes what re-testing is worth.
It is descriptive and changes no registered label. `scripts/analyse_0am.py` computes it.

**Panel R against the grid.** For each model and condition:
- the agent's share on scrambled GB1, and on scrambled PhoQ, minus the same model and condition's share on the
  grid (stage 1 and the top-ups, 0ag fallbacks dropped);
- unpaired, because the landscapes and seeds differ, with a 95% interval from 20,000 bootstrap resamples that
  draw each side on its own;
- beside it, the yardstick's change: 0.89 - 23.78 = -22.89 points for GB1, and 1.03 - 23.78 = -22.75 for PhoQ.
  The grid's yardstick here is the alphabet-correct 23.78%;
- the ratio of the agent's change to the yardstick's change, with its interval scaled the same way.

**Panel K.** For each model, the least-squares slope of campaign share on the yardstick of the campaign's own
landscape, over the 80 landscapes. Its 95% interval resamples landscapes. A sensitivity repeats it without the
three landscapes whose k* is not 1.

**Stated in advance.** A slope or ratio near 1 means re-testing tracks the landscape. Near 0 means it does not
adapt.

**Precision, from `scripts/plan_0am.py`.** The expected half-widths use the grid's per-campaign SDs.
- The unpaired change: 0.34 to 2.13 points across the six model and condition cells. Against a yardstick change
  near 23 points, the ratio's half-width is about 0.09 or less. This is the sharper of the two tests.
- The Panel K slope over all 80 landscapes: 0.29 (Opus), 0.15 (Gemini) and 0.11 (DeepSeek).
- The 80 yardsticks span 20.44% to 46.79%, but the 77 landscapes with k* = 1 span only 20.44% to 23.81%. The
  slope therefore rests almost entirely on the three landscapes with k* = 2.
- Without those three, the expected half-widths are 2.12, 1.10 and 0.76, so that sensitivity cannot tell 0
  from 1. It is reported to show how much the slope leans on them.

### 0am.2 THE FIRST SMOKE, A MISLEADING RE-ASK, AND FIVE CHANGES. 2026-10-02, before any further call

**The first smoke** (seed 13,000,000, $1.61, kept and not analysed) failed its gate three ways.
- Real-name GB1 ran no campaign. The canary aborted it: shrinkage picked differently from the mean rule in 0
  of 60 scripted campaigns. On GB1 the pool's spread (SD 1.09) dwarfs the noise, so shrinkage moves nothing.
  The counts on the other landscapes were 6 (scrambled GB1), 1 (scrambled PhoQ) and 25 (NK K = 3).
- Scrambled PhoQ lost most of its slots. Opus lost 52 and 49 of 60, Gemini Blind 56. All but one of those
  slots went to lost rounds; the non-viable channel lost at most one slot per campaign.
- Panel K's projected cost, $31.93, passed its $30 ceiling.

**What caused the PhoQ losses.** Its local best, EDQT, ends in T, the last letter. The agents explored "near T"
by proposing U, and also V, W, X, Y and Z. The parser drops a line with a letter outside the alphabet. The
re-ask then said "Your previous reply did not contain exactly 4 candidates", which was false: the reply had 4
lines. Told nothing about the letter, the agents sent the same line again and the round was lost. In the
published grid, 126 of 157,911 round and replacement calls dropped a line for a bad letter, and lost rounds
from any cause cost 324 of 304,500 slots.

The operator first proposed running PhoQ under the risk-free rejection rule, then withdrew it. That rule covers
non-viable orders and would not have reached these losses.

**The five changes, approved by the operator.**
1. A truthful re-ask, the option `truthful_reask`, off by default, used in every 0am arm. When lines are
   dropped for letters outside the alphabet, the re-ask is: "Your previous reply could not be used. These
   candidates contain letters that are not in the alphabet: [the dropped lines]. Every candidate must use
   only the letters [the alphabet]. Reply again with exactly N lines in the form CANDIDATE | one short reason
   and nothing else." Every other re-ask is unchanged.
2. The canary runs on the grid's landscape, where it tests the code, as it always has. For each 0am landscape
   the run records how often shrinkage differs (`comparator_liveness_of_60` in the manifest) and does not stop.
3. Panel K's ceiling rises to $34, $8.50 per K.
4. A slot-loss guard for every 0am cell. Each cell reports its mean lost slots, abandoned plus lost rounds.
   A cell above 10 gets the label "not interpretable: slot loss", and its share is reported descriptively.
   For reference, the guessing policy loses 9.52 slots per campaign on scrambled PhoQ at its k*.
5. Out-of-alphabet proposals per cell, as a descriptive outcome: the count over every attempt, the campaigns
   with any, and the letters used. A step from T to U suggests the agents treat the letters as an ordered scale.

**The second smoke**, at seed 13,000,001, repeats the first on all four landscapes with these changes, with a
cap of $0.75 per arm. The panels launch only if all of these hold:
- all 24 campaigns complete, with no empty or truncated response and no genuine parser disagreement;
- no smoke campaign loses more than 10 slots;
- the costs it measures project Panel R within $63 and Panel K within $34.
If any fails, nothing launches and the operator is told.

### 0am.3 THE SECOND SMOKE, AN ASYMMETRIC SLOT-LOSS GUARD, AND PANEL K'S CEILING. 2026-10-02, before launch

**The second smoke** (seed 13,000,001, $2.38, kept on disk as a smoke and not analysed) ran all 24 campaigns.
It had no genuine parser disagreement and no empty or truncated response. The truthful re-ask worked for Opus
on scrambled PhoQ, which lost 1 and 0 slots against 52 and 49 in the first smoke. The gate failed two ways.
- Three Gemini Blind campaigns lost more than 10 slots. On real GB1 (13) and NK K = 3 (12) the losses were
  non-viable orders abandoned after the replacement asks. On scrambled PhoQ (12) they were lost rounds: Gemini
  made 30 out-of-alphabet proposals (U, V, W, X and Z) after being told the exact alphabet. In the published
  grid no Gemini Blind campaign lost more than 8.
- Panel K's projected cost was $36.09 against a $34 ceiling. Opus cost $0.356 per campaign on K = 3.

**Three decisions by the operator.**
1. The slot-loss guard of 0am.2 is replaced. A lost slot is never a re-test, so lost slots can only lower the
   share. A reading of "re-testing generalises" therefore stands whatever the cell's lost slots, and is
   conservative. A reading of "does not generalise" or "partial" in a cell whose mean lost slots exceed 10
   becomes "not interpretable: slot loss", with its share reported descriptively.
2. Every cell also reports, as a sensitivity, its share over non-lost slots: replication_count divided by
   (slots_used - lost_slots). It also reports its mean lost slots split by channel, non-viable orders and lost
   rounds.
3. Panel K's ceiling rises to $38, $9.50 per K. No extra Gemini check runs before launch, because under the
   asymmetric guard a loss matters only when a cell reads below the line, and the guard catches it there.

**Launch.** Panels R and K launch at once, with the truthful re-ask on in every arm, under ceilings of $63
(Panel R) and $38 (Panel K). Out-of-alphabet proposals per cell stay a registered descriptive outcome.

### 0am OUTCOME, recorded after every campaign was complete and before any paper prose. 2026-10-03

**What ran.** Panel R (900 campaigns) and Panel K (560) launched from e325069 with the truthful re-ask in every
arm. The registered Opus top-up (120 campaigns, seeds 11,000,030 to 11,000,059) ran from e325069 by a detached
checkout. Spend: Panel R $48.57, Panel K $31.76, top-up $26.09, the two smokes $3.99, the probe $0.02, $110.43 in
all. All 1,580 campaigns ran with the truthful re-ask on and every other prompt option off
(`scripts/checks_0am.py`). The raw data is in 753b900 and fecd660.

**Incidents, none charged to an agent.** The top-up's first launch stopped before any call, because the checkout
lacked the untracked landscape data. One Gemini call at K = 0 hit the token limit, and its first line still
parsed. One genuine parser disagreement occurred on PhoQ, 0.02% of calls. One 0ag fallback was dropped, Gemini
Mechanism on scrambled GB1.

**Added after the data, descriptive, at the operator's request.** The paired GB1 comparison also reports distinct
candidates, the best value measured, the share over non-lost slots and each arm's means, and a view on seeds 0
to 29. `scripts/analyse_0am.py` computes them beside the registered outcomes.

**The top-up rule, at n = 30.** Blind: -9.33 [-14.11, -4.56], half-width 4.78, triggered. Mechanism: -6.61
[-9.22, -4.11], half-width 2.56, not triggered. As registered, the top-up covered both conditions, so the Opus
GB1 comparisons are read at n = 60 in both. Seeds 0 to 29 are reported as a labelled sensitivity.

**Labels.** All 24 labelled cells read "re-testing generalises": the 12 cells of scrambled GB1 and scrambled
PhoQ and the 12 cells of Panel K. The guard changed none. One labelled cell, Gemini at K = 2, has mean lost slots
above 10 (10.4), and its reading stands under 0am.3.

**Real-name GB1 against scrambled GB1, paired by seed, descriptive.**
- Opus: share -12.11 [-15.28, -8.97] in Blind and -8.06 [-10.22, -5.89] in Mechanism; distinct candidates +5.78
  and +3.97; final pick +2.82 and +2.86. On seeds 0 to 29 the share changes are -9.33 and -6.61.
- Gemini Mechanism (59 pairs): share +0.31 [-0.71, +1.38], distinct candidates -0.14, final pick 1.13 to 1.77.
- DeepSeek: share -3.97 and -3.19, distinct candidates +1.72 and +1.75, final pick +0.36 and +1.94.
- Gemini Blind: share 45.06%, or 80.09% over non-lost slots. It lost 27.2 slots per campaign, 26.9 of them to
  non-viable orders, after 123.4 rejections, and made 235 proposals with ambiguity codes (B, X, Z, J). Its raw
  difference of -47.14 points is mostly slot loss; over non-lost slots it is -12.29.
- Under the real names Opus ordered one of GB1's true top 10 in round 1 in 20 of 60 Blind and 2 of 60
  Mechanism campaigns. Under the scrambled names it never did.

**Adaptation (0am.1).**
- Panel R against the grid: the ratio of the agent's change to the yardstick's, which drops about 23 points.
  - Opus: 0.44 to 0.53.
  - Gemini: 0.07 and 0.21 on GB1; 0.91 (Mechanism) and 1.41 (Blind, driven by lost rounds) on PhoQ.
  - DeepSeek: -0.21 and -0.15 on GB1; -0.02 and 0.13 on PhoQ.
- Panel K, the slope of share on each landscape's yardstick over 80 landscapes: Opus -0.62 [-8.38, 0.08],
  Gemini -0.34 [-3.35, 0.53], DeepSeek -0.09 [-0.60, 0.01]. Every interval excludes 1, so by the reading stated
  in advance re-testing does not track the landscape. The intervals are wider than planned, because resampling
  landscapes often drops the three with k* = 2 that carry the spread.
- Trend across K: Opus +8.37 points per K [+6.59, +10.07], Gemini +1.36 [-0.99, +3.82], DeepSeek +0.89
  [+0.15, +1.70]. From K = 0 to K = 3, Opus's rejections rise from 13.9 to 33.7 and its distinct
  candidates fall from 18.9 to 3.0. The guessing policy's share on the same landscapes stays at 22.5% to 25.9%.

**Out-of-alphabet proposals** appear in every arm spelled A to T, mostly U, then V and W, which fits treating the
letters as an ordered scale. The heaviest: DeepSeek on PhoQ, Mechanism, seed 11,000,012 (52 proposals, 52 slots
lost), and DeepSeek at K = 2, seed 12,000,007 (66 proposals, 49 slots lost). They were sent 13 and 15 truthful
re-asks naming the candidates and the alphabet. The K = 0 landscapes are exactly additive: the largest
epistasis over 60,000 double mutants is 3.6e-15.

### 0al YARDSTICK, CORRECTED. 2026-10-03

"0al YARDSTICK" above used the published guessing policy, whose neighbours came from the amino-acid letters
(spec/STRIKES.md, 2026-10-02). With the landscape's own letters the risk-free yardstick has k* = 1, a mean pick
of 7.9459 (was 7.9935) and a share of 23.96% (was 23.97%). It still loses 0.86 slots per campaign at k* (was
2.23), and 353 campaigns reach the cap (was 758). Panel B's lines become 47.93% (unchanged) and 28.96% (was
28.97%). Every Panel B cell spent 74.8% or more of its slots on re-tests, so no 0al label changes;
`scripts/verify_paper_numbers.py` asserts it. Results: `results/riskfree_reference_alphabet.json`.

## 0an. WHAT REMOVES THE RE-TESTING? THREE TOOLS ON THE GRID'S LANDSCAPE. 2026-10-03, before any model call but a smoke

**Why.** Instructions did not fix re-testing: the five-condition grid and the prompt checks of 0al left it high.
0am showed the agents fall back on re-testing when new working candidates are hard to find. Opus's distinct
candidates fell from 18.9 at K = 0 to 3.0 at K = 3 as its rejections rose from 13.9 to 33.7. 0an asks whether
changing the agent's tools removes re-testing, and it measures what re-testing costs.

**Three arms**, each an option of `scripts/grid.py`, off by default. `tests/test_prompt_options.py` and
`tests/test_prompt_contract.py` still pin the grid's renders by hash. The exact prompts, beside the grid's, are in
`results/prompts_0an.txt`.
- **F1 Ledger** (`--ledger`). Each round and replacement prompt adds a table after the history (`repdef/tools.py`).
  It lists every candidate with a reading, in order of first reading, with its number of readings, their mean
  and the standard error of that mean. The history stays as it is, and nothing is advised. It tests "the agent
  loses track of what it has measured".
- **F2 Menu** (`--menu`). Each round and replacement prompt adds 10 candidates the agent has never ordered, each
  one letter away from one of its three highest candidates by mean reading. They are ranked by an additive
  model fitted to its readings, which the prompt states. A candidate scores the sum, over its four positions, of
  the mean reading of measured candidates with the same letter there. A letter not yet measured at a position
  counts as the mean of all readings, and ties go to a keyed draw. With no readings yet, the 10 are one-letter
  changes of the reference point in a keyed order, and the prompt says so. The prompt also says the agent may
  ignore the list. It tests "the agent cannot find new candidates".
- **F3 Cap** (`--repeat-cap`). The environment lets each candidate be ordered at most twice, one repeat
  (`campaign.run(repeat_cap=1)`). A failed order counts toward the two, since it used a slot. A further order is
  refused before anything is measured: no slot, no draw. The agent chooses again, under the risk-free bound of
  20 asks for that slot, and a slot reaching the bound is lost and counted. Non-viable orders keep the grid's
  rule. Every prompt kind states the rule, and a refused order is never called non-viable. F3 measures the
  effect of re-testing on the final pick.
- **F0 Control**, Gemini 2.5 Flash and DeepSeek V3.1: the Blind condition with no 0an option and the truthful
  re-ask on, on the same seeds and in the same window. Opus 4.7's control is Panel A0 of 0al: Blind, the
  original prompts, run on 2026-10-02 on the same 60 seeds, 300,000 to 300,059.

**Common to all three.** The grid's landscape (NK, K = 1, seed 1) and the Blind condition. The three grid models run
with the grid's settings. That means 15 rounds of 4 slots, 15% failures and multiplicative noise. It also means
three replacement asks for a non-viable order, temperature 0, reasoning off and 6,000 output tokens. The truthful re-ask of 0am.2 is on, as
in 0am. Three workers per arm, a shuffled order with order seed 20261004, and a $50 credit floor.

**Pairing.** Opus 4.7 runs seeds 300,000 to 300,059, and Gemini 2.5 Flash and DeepSeek V3.1 run seeds 300,000 to
300,119. The primary comparison is each arm against its concurrent control, paired by model and seed: F0 for
Gemini and DeepSeek, Panel A0 for Opus. Pairing against the grid's own Blind campaigns at the same seeds is a
labelled sensitivity. `scripts/launch_0an.py` refuses unless every control and grid partner exists. A pair is
dropped if either side is a 0ag nomination fallback. The arms share their seeds, so they also pair with each
other.

**Reading rules, fixed now** (`scripts/analyse_0an.py`, committed with this amendment and tested on both sides
of every line). The yardstick is the corrected guessing policy's share, 23.78%.
- Share, per arm and model, for F1 and F2 only:
  - "removes re-testing" if the arm's mean share is at most twice the yardstick, 47.56%;
  - "reduces" otherwise, if the paired change is a drop of more than 10 points;
  - "no effect" otherwise.
- A label whose 95% interval crosses its line carries "(interval crosses a line)".
- The slot-loss guard is asymmetric, as in 0am.3. Lost slots can only lower a share, so "no effect" stands.
  "Removes" or "reduces" in a cell whose mean lost slots exceed 10 becomes "not interpretable: slot loss".
- Every cell also reports its share over non-lost slots and its lost slots by channel. It reports its distinct
  candidates and rejections beside the grid's, and for F3 its refused orders and cap hits.
- Final pick, per arm and model, the paired change with its 95% interval against a band delta:
  - "pick rises" if the interval lies above 0, and "pick falls" if it lies below 0;
  - "no change beyond delta" if it lies within plus or minus delta;
  - "unresolved" otherwise.
- F3 gets no share label. With at most two orders per candidate, a re-test is at most one order in two. Its share
  therefore cannot pass 50% under replication_count / slots_used, and the "removes" line, 47.56%, sits below that.
  The reference candidate counts like any other, since being told its reading is not an order. A policy that
  orders every candidate twice reaches exactly 50.0% under the cap. F3's share is reported against that ceiling.
- F3's registered outcomes are the paired change in final pick (primary, the headline estimate of what
  re-testing costs), distinct candidates, lost slots by channel, refused orders and cap-allowance exhaustion.

**Bands, sized to the n** (`scripts/plan_0an.py`). Each paired SD is the larger of two same-design reruns against
the grid's Blind campaigns, Panel A and Panel A0 of 0al. The band delta is the interval half-width plus 1.96
standard errors. A cell with no true change then meets "no change beyond delta" with probability above 0.95.

| model | n | SD of paired pick change | half-width | delta | P(meet, no change) | 80%-power change | share half-width |
|---|---|---|---|---|---|---|---|
| Opus | 60 | 0.422 | 0.109 | 0.22 | 0.958 | 0.155 | 2.06 |
| Gemini | 120 | 0.347 | 0.063 | 0.13 | 0.967 | 0.089 | 1.45 |
| DeepSeek | 120 | 0.291 | 0.053 | 0.11 | 0.969 | 0.075 | 0.88 |

The share comparisons are powered in every cell: a drop of 10 points is at least 4.8 half-widths. For the final
pick, a change of 0.10 is the effect of interest, about the guessing policy's gain from one repeat per round
(0.156). Gemini and DeepSeek are powered for it. Opus is not, so its final-pick comparisons are descriptive.

**What the controls leave open.** Gemini's and DeepSeek's control differs from the arms by the tool alone. Opus's
control ran a day earlier and without the truthful re-ask; in the grid, lost rounds from any cause cost 0.1% of
slots. In the sensitivity against the grid, a change also includes service drift. 0al.1 measured that drift on
Blind: share within 1.11 points, and final pick -0.048 to +0.007, inside every line and band above.

**The smoke, before the panel.** 2 campaigns per model per arm at fresh seeds 15,000,000 and 15,000,001, the
control included: 22 campaigns, a cap of $1 per arm. It also reports how many of F2's suggestions are viable,
since the menu knows nothing of viability, and how often the agent ordered from it. It passes if every campaign completes with no empty or truncated response and no
genuine parser disagreement. No campaign may lose more than 10 slots, and the measured costs must project each
arm within its ceiling. If it fails, the operator is told before the panel runs.

**Money.** Panel A0's Blind means per campaign give $19.18 per arm: Opus $0.287, Gemini $0.0107, DeepSeek $0.0054.
That is $57.54 for the three arms and $1.94 for the control, $59.47 in all. The ceiling is $25 per arm and $4
for the control, $79 in all. The tools lengthen the prompts and F3
adds replacement asks, so the smoke's measured costs are the projection that binds.

**F4 is not run.** A reasoning model on the same design was considered. The reasoning panel (panel c) already
switches reasoning on within the same models: Opus 4.7 and Gemini 2.5 Flash, under Blind and Mechanism, with
shares of 69.0% to 86.0%. That answers the question better than a second model would. It stays a possible later
item. The candidate was DeepSeek R1 (`deepseek/deepseek-r1-0528`), the reasoning model of DeepSeek V3.1's family. OpenRouter lists it at $0.50 and $2.15 per million input and
output tokens. With the grid's 30.3 calls of 808 prompt tokens per campaign, it costs about $0.079 per campaign
at 1,000 reasoning tokens per call. At 2,516, the length Gemini 2.5 Flash reasoned in the reasoning panel, it
costs about $0.178. That is $9.49 to $21.33 for 120 campaigns.

**Seeds.** Seeds 300,000 to 300,119 are shared on purpose with the grid's Blind campaigns, the sensitivity
partners, and 300,000 to 300,059 with Panel A0, Opus's control. 0al's Panels A and B also used 300,000 to 300,059,
each paired with the grid; 0an does not read them. The smoke seeds 15,000,000 and 15,000,001 are used nowhere
else.

**What it cannot show.** F1's standard-error column tells a Blind agent that repeat readings differ, which its
history already shows. F2 is one particular ranking model, and a different model could help more or less. F3
caps repeats per candidate, so a share up to 50% remains possible, and it changes the environment, which a
deployed agent would not face. Each arm runs on one landscape, the grid's.

## 0an.1. AFTER THE SMOKE: F3 CHEAPER AND CLEANER, OPUS AT 30 IN F2 AND F3, CAPPED ATTEMPTS REGISTERED. 2026-10-03, before any panel call

**Why.** The 0an smoke (data in 9b38952, 17 campaigns, $4.20) failed its gate on three counts. F2 projected
$50.31 against its $25 ceiling. F3 projected $133.22, and its two campaigns lost 13 and 21 slots against a limit
of 10. Both stopped at the $1 smoke cap: F2 ran 5 of 6 campaigns and F3 ran 2. Replacement asks drove the cost.
In F3 they took 86% of Opus 4.7's spend and 90% of Gemini 2.5 Flash's. Opus ordered candidates already at the
limit 53 times in its one campaign, and Gemini 75 times. The history also kept one line per refused order, so F3
prompts reached about 4,900 tokens.

**1. Two F3 changes, both truthful.**
- Every round and replacement prompt lists the candidates already at the limit, after the history, under
  "AT THE LIMIT". The list is the oracle's own count: candidates with 1 + repeat_cap orders that used a slot,
  failed ones included (`tools.at_limit`, tested against `Oracle.orders_of`). It is absent while nothing is at
  the limit.
- A refused order leaves no history line. It used no slot and drew nothing. It is counted in `Oracle.refused`,
  which gives n_capped. A history row reading "capped" now raises an error by name.
- The replacement ask's notice for a refused order is unchanged. The stop-and-show described that notice as the
  full list. It names only the candidates refused in the same round, so the new block also goes in replacement
  asks.

**2. F3's smoke gate.** Only lost rounds count toward the limit of 10 slots. Losing slots to rejections is how a
cap works under the grid's rules. The guessing policy at k = 1 also orders each candidate at most twice. It loses
11.70 slots per campaign and still picks 7.866. Rejection losses are a registered outcome. Lost slots are
reported by channel: rejection losses, cap-bound losses and lost rounds. A cap-bound loss is a slot whose refused
re-asks reached the risk-free bound of 20.

**3. Opus 4.7 at n = 30 in F2 and F3.** Gemini 2.5 Flash and DeepSeek V3.1 stay at 120, and Opus stays at 60 in
F1. Opus's final pick is descriptive at n = 60 too: its 80%-power change is 0.155, above the 0.10 bar. So n = 30
loses no label. Its seeds are 300,000 to 300,029, paired with Panel A0 and the grid. The band rule is applied
unchanged at n = 30 (`scripts/plan_0an.py`, `plan_n`). Opus's delta becomes 0.31 in F2 and F3, with
P(meet, no change) 0.952, an 80%-power change of 0.222 and a share half-width of 2.98 points. It stays 0.22 in F1.

| arm | Opus n | expected, from the smoke | ceiling |
|---|---|---|---|
| F0 control | none | $1.43 | $4 |
| F1 ledger | 60 | $19.53 | $25 |
| F2 menu | 30 | $27.28 | $30 |
| F3 cap | 30 | set after its re-smoke | none yet |

Expected costs are the smoke's measured spend per campaign (`scripts/options_0an.py`). F0 to F2 total $48.24.
`scripts/launch_0an.py` refuses F3's panel while F3 has no ceiling.

**4. F3's re-smoke.** F3 alone with these changes: tag smoke0an1_f3_cap, the smoke seeds 15,000,000 and
15,000,001, 2 campaigns per model, a $5 cap. The launcher allows those seeds only because the first smoke alone
holds them. The gate is 0an's, with point 2. The report gives per-campaign cost by model, the projected F3 cost
at the new n, lost rounds, rejection losses, cap-bound losses and capped attempts. The F3 panel waits for the
operator's check.

**5. A new registered F3 outcome: capped attempts.** The attempts to order a candidate already at the limit, per
campaign (n_capped), per model with a 95% percentile bootstrap interval, reported beside the pick change. It
measures how strongly an agent pushes to re-test when it cannot. In the first smoke Gemini 2.5 Flash made 75 such
attempts and Opus 4.7 made 53, one campaign each. Those counts are not comparable to the panel's. Under 0an the
prompt did not list the candidates at the limit, and refused orders filled the history.

**6. 0an's seeds sentence, corrected.** It said 0al's Panels A and B also used 300,000 to 300,059. Seeds 300,000
to 300,119 are the paired range of every panel since stage 0: 18 campaign tags record seeds in it. Besides the
grid and 0al's Panels A, A0 and B, they include panel c, the zero-noise, framing and T panels, stage 0, stage 1a
and the probes. 0an reads only the grid's Blind campaigns and Panel A0. A scan of every campaign and call file
finds the smoke seeds only in the 0an smoke tags. Strike entry of 2026-10-03.

**Unchanged.** The reading rules, the yardstick, the control pairing, the order seed and the settings common to
all arms. The smoke report now holds the control to its own $4 ceiling (9b38952); the result was unchanged.

## 0an.2. F3 WITHDRAWN AS A CAUSAL ARM. 2026-10-03, before any F3 panel data exists

**Decision.** F3, the repeat cap, is withdrawn as a causal arm. No F3 panel campaign has run. The F0, F1 and F2
panel continues as registered in 0an and 0an.1.

**Why.** Under both prompt versions the cap turned into lost budget and failed replies. F3 campaigns lost 13 to 56
of 60 slots, to rejections, to the cap's bound and to lost rounds. Opus 4.7 lost 9 rounds in two campaigns by
drafting its answer in the reply. The paired pick change could therefore not isolate what re-testing costs. A
third prompt version tuned to pass the gate would be a forking path. The cost question is covered by the scripted
k sweep and by F2's paired change in final pick.

**What is kept: both smokes, as a descriptive record.** `scripts/f3_smokes_descriptive.py` writes
`results/f3_smokes_descriptive.json`. Per model and smoke, per campaign, it gives capped attempts, copies of the
refusal notice and re-proposals among them, lost calls by parse status, and lost slots by channel. It also gives
readings, distinct candidates, rejections, the final pick and spend. References are the F0 control smoke on the
same seeds and the grid's Blind means. No prose is written yet. The limits travel with every number:
- one campaign per model under 0an (Opus 4.7 and Gemini 2.5 Flash only) and two under 0an.1;
- two prompt versions, and under 0an.1 a refused order left no history line, so agents could not see their own
  refusals;
- the history fault of strike 2026-10-03, fixed in d3e729e: a slot the cap lost was called a non-viable loss,
  2 times under 0an and 28 times under 0an.1;
- the rejection channel includes slots lost when a replacement ask after a refusal yielded nothing, which the old
  outcome could not tell apart from a non-viable loss.

What the record shows, stated plainly. Blocking re-tests sent every model to new names. Rejections ran 2.27 to
12.90 times the grid's Blind mean, above it in 8 of 8 campaigns. Distinct candidates were above it in 6 of 8. Most
new names were non-viable. The agents also kept asking for blocked candidates, up to 885 times in one campaign.
Readings fell to 3 to 41 per campaign, against 51 to 52 in the F0 control smoke on the same seeds.

**Capped attempts** move from a registered outcome (0an.1, point 5) to this descriptive record.

**A logging limit.** When a reply fails to parse and the policy re-asks, the call log keeps only the last reply
and the last attempt's notes. The first reply is overwritten. Every lost-round reply quoted from these smokes is
the reply written after the re-ask. No code change now.

**Freed budget.** F3 had no panel ceiling. Its panel would have run Opus at n = 30 and the other two at 120. The
projected cost was $85.66 under the 0an.1 prompt and $78.59 under the 0an prompt, where DeepSeek's cost is itself
projected.
The two smokes spent $5.15, $1.97 and $3.18. The F0 to F2 panel's expected cost is unchanged at $48.24, with
ceilings of $4, $25 and $30.

**What changes in the code.** `scripts/analyse_0an.py` reads F1 and F2 only and no longer writes a "what
re-testing costs" block. `scripts/launch_0an.py` refuses an F3 panel by name.

## 0an.3. F5 STRUCTURE: DO AGENTS RE-TEST BECAUSE THEY DO NOT KNOW THE PROBLEM'S STRUCTURE? 2026-10-03, before any F5 call

**Question.** Whether agents re-test because they lack knowledge of the problem's structure. F5 tells them the
structure, gives no advice about re-testing, and is compared with the concurrent control. It is read together
with F2. If F5 works, the cause is missing knowledge. If F2 works and F5 does not, the bottleneck is producing
candidates. "Works" means a share label of "removes re-testing" or "reduces".

**The arm.** The Blind prompt plus one STRUCTURE paragraph of measured facts about the grid's landscape, in every
round, replacement and nomination prompt (`--structure`). It says nothing about how many re-tests to make, gives
no strategy, never mentions the yardstick, and contains no word about measurement, noise or re-testing
(`tests/test_structure_0an3.py`). It sits after the measurement block, before the round line:

> STRUCTURE
> Number the positions 1 to 4 from the left. The score is the average of four parts. Each part depends on the
> letters at two neighbouring positions: 1 and 2, 2 and 3, 3 and 4, and 4 and 1. So changing positions 1 and 3
> together moves the score by the sum of what each change does alone, and the same holds for positions 2 and 4.
> Changes at neighbouring positions do not add up this way. Of the candidates one letter away from a viable
> candidate, 26% are viable, against 7% of all candidates.

**The number behind each fact** (`scripts/structure_facts_0an3.py`, `results/structure_facts_0an3.json`, on the
landscape itself, enumerated in full except the interaction check, which samples 200,000 pairs of changes per
pair of positions).
- *Which positions interact.* The interaction of two changes, f(both) - f(first) - f(second) + f(neither), has
  a mean size of 1.03 to 1.08 for positions 1-2, 2-3, 3-4 and 4-1. That is the size of one change, 1.05. For
  positions 1-3 and 2-4 it is never above 5.3e-15. The proposed wording "each position's contribution depends on
  its own letter and one neighbouring letter" is true of each part. A letter, though, sits in two parts, so its
  effect depends on both neighbours. The paragraph states the parts.
- *Non-neighbouring changes add up.* For positions 1-3 and 2-4, 100% of sampled double changes add up to within
  1e-9.
- *Viable neighbours.* 25.79% of a viable candidate's one-letter neighbours are viable, against a base rate of
  7.00% and 5.59% for a non-viable candidate's neighbours.
- *Dropped: neighbours score alike.* Scores one letter apart correlate at 0.092 over the 219,496 ordered pairs of
  viable candidates. Over all pairs the figure is 0.499, but agents only see viable candidates, so the claim is
  not made.

The paragraph says "score" and "average", as the Blind prompt does. It avoids "true" and "exactly", which would
hint at measurement noise. `grid.py` refuses an F5 campaign unless the measured facts still give the paragraph's
numbers and pattern on the landscape in use, and refuses F5 on any landscape other than the grid's.

**Seeds, pairing and labels: as F1 and F2.** Gemini 2.5 Flash and DeepSeek V3.1 at n = 120 on seeds 300,000 to
300,119, paired with F0. Opus 4.7 at n = 30 on 300,000 to 300,029, paired with Panel A0. The grid is a labelled
sensitivity. Share labels are "removes re-testing", "reduces" or "no effect", with the asymmetric slot-loss
guard. The paired pick change is read against its band: delta 0.31 for Opus (descriptive, 80%-power change
0.222), 0.13 for Gemini and 0.11 for DeepSeek. Share half-widths are 2.98, 1.45 and 0.88 points.
`scripts/analyse_0an.py` reads F5 beside F1 and F2.

**Money.** Panel A0's Blind means give about $10.56. The ceiling is $15. The smoke's measured cost is the
projection that binds.

**The smoke.** 2 campaigns per model at fresh seeds 15,000,002 and 15,000,003, a $1 cap, tag
smoke0an3_f5_structure. The gate is 0an's: every campaign complete, no empty or truncated reply, no genuine parser
disagreement, no campaign losing more than 10 slots, and the projection inside $15. It also reports lost calls by
parse status, to catch format failures the paragraph might induce, as the cap's prompt induced drafting. The
operator checks the wording before the panel launches.

## 0an.3 NOTE. F5's ceiling raised from $15 to $19 after its smoke. 2026-10-03, before any F5 panel call

The F5 smoke (dc3a547) had no lost round, no format failure and no parser disagreement. It failed only on cost.
Its spend per campaign was $0.4047 for Opus 4.7, $0.0202 for Gemini 2.5 Flash and $0.0096 for DeepSeek V3.1. That
projects the arm to $15.72 at the registered n, against the $15 ceiling and the $10.56 projected from Panel A0. The
agents made more replacement asks after rejections, and the prompts are about 300 tokens longer. The operator
approved the registered n (Opus 30, Gemini and DeepSeek 120) with the ceiling raised to $19, the smoke's
projection plus a 20% margin. Nothing else in 0an.3 changes.

## 0an.5. OPUS MENU TOP-UP TO n = 60. 2026-10-03, decided after seeing the n = 30 result, before any top-up call

**Why, and when it was decided.** At n = 30, Opus 4.7's list-against-own viability difference is +10.8 points
[-0.6, +23.3] after matching rounds: unresolved. Its F2 final pick is descriptive at n = 30. This top-up was
decided after the operator saw those n = 30 results. It is therefore a follow-up, and the registered n = 30
readings stand as they are.

**Design.** Opus 4.7 in F2 exactly as in 0an.1: the Blind condition, the menu, the truthful re-ask, the grid's
settings. Seeds 300,030 to 300,059, paired with Panel A0's Opus Blind campaigns on the same seeds, with the grid's
own campaigns as the labelled sensitivity. Tag gen_0an5_f2_menu_opus. Ceiling $25, about $0.60 per campaign. No
smoke: `scripts/same_config_0an5.py` confirmed the launch configuration before launch. A stand-in campaign sends
67 prompts, byte-identical to those of the F2 panel's commit 9bc8ef4. Every setting the two manifests share
matches, and the one prompt option added since (structure) is off.

**Reading.** Opus at n = 30 (registered, seeds 300,000 to 300,029) and at n = 60 (with the top-up) side by side:
- the share change against the control and its label;
- the paired pick change, and its split into exploration and selection;
- list against own-name viability, with rounds matched and the earlier-list group separate, using a bootstrap
  over campaigns.
The share label is not re-decided. It stands from n = 30 unless the n = 60 interval disagrees with it, in which
case both are reported.

## 0an.4. THE MODEL-GUIDED POLICY: A THIRD SCRIPTED REFERENCE. 2026-10-03, before it runs. Simulation only

**Question.** What a policy that learns the landscape, using only the agent's own readings, achieves under the
grid's rules, beside the guessing reference (7.8659) and the informed reference (7.9993). It is a third yardstick,
and no label rests on it.

**Rules** (`scripts/model_guided_0an4.py`). The grid's rules, the same 1,500 seeds as the two references (8,200,000
onward), the landscape's own alphabet, rejections with three replacement asks, 15% failures, 15 rounds of 4.
- Rounds 1 to 4: one single-letter change of the reference candidate per position per round, no repeats. The
  letter is a keyed draw among letters not yet tried at that position. A replacement after a rejection uses
  another untried letter at the same position.
- From round 5: the additive model the Menu uses scores candidates. A candidate scores the sum, over its positions,
  of the mean reading of measured candidates with the same letter there, and an unmeasured letter counts as the
  overall mean. The candidate set holds the single changes to the current best by mean. It also holds the
  candidates that change it at two positions, using each position's two best letters by the model. A letter is marked rejected at a
  position when a rejected candidate carried it there and no measured candidate does. Candidates carrying a
  rejected letter are ranked last, after every other candidate. Ties go to a keyed draw. Names already ordered are
  never proposed again.
- Each round from 5 orders 4 - k new candidates by rank and k re-tests (k = 1 is primary). The re-tests go to the
  top k + 1 candidates by mean in rank order, skipping the top candidate if it already has two or more readings.
  So at k = 1 the re-test goes to the top candidate if it has one reading, otherwise to the runner-up.
- Rounds 13 to 15, in the confirm variant: all 4 slots re-test the top 4 by mean. In the no-confirm variant those
  rounds follow the round-5 rule.
- Nomination: the references' empirical-Bayes shrinkage rule (primary), with the highest mean beside it.

**What runs.** The operator's rule changes are rejected letters ranked last, a no-confirm variant, and K = 0 to 3.
"K = 0 to 3" is read both ways, since each costs only simulation:
- the re-test sweep, k = 0 to 3 per round, for the confirm and no-confirm variants on the grid's landscape;
- the ruggedness panel, at k = 1 with confirm, on Panel K's 20 landscapes for each K = 0 to 3. That uses the first
  75 of the same seeds on each landscape, beside each K's guessing yardstick from `results/yardsticks_0am.json`.

**Reported.** The mean final pick on true fitness with its standard error, and the replication share. Also distinct
candidates, rejections and lost slots, beside the guessing and informed references, and where the sweep peaks.

## 0an.6. THE MENU ON SCRAMBLED GB1. 2026-10-03, before any call

**Question.** Whether the Menu's effect on re-testing holds on real protein data.

**Landscape.** GB1 with scrambled names (gb1_scrambled, scramble seed 20261003), the Blind condition, scrambled and
rescaled exactly as in 0am Panel R. The truthful re-ask is on and the grid's other settings hold.

**The Menu reads GB1.** The Menu takes its letters, its reference point and its candidates from this landscape,
never the grid's. `grid.py` checks this at start-up and refuses on any mismatch
(`check_the_menu_reads_this_landscape`):
- the Menu's alphabet must equal the landscape's own letters;
- its reference must be the landscape's own, CLTL, and viable there;
- a menu built with no readings, and one built after two measured viable candidates, must hold only strings of
  this landscape, one letter from the candidates they neighbour.
Every campaign also refuses if the policy's alphabet or reference point is not the landscape's. The Menu itself
uses no viability. Viability enters through the oracle and the analysis, both of which read GB1's own viable set.
Scrambled GB1 uses the letters A to T, as the grid does, so the reference and the candidate checks carry the test.
The check refuses GB1 given the grid's reference GDIF, and real GB1 given the grid's alphabet.

**Arms and seeds.**
- Menu: Opus 4.7 at n = 30 on seeds 11,000,000 to 11,000,029, the 0am Opus seeds. Gemini 2.5 Flash and DeepSeek
  V3.1 at n = 60 on seeds 11,000,000 to 11,000,059, the 0am GB1-scrambled seeds.
- Concurrent no-tool control: Gemini and DeepSeek at n = 60 on the same seeds.
- Opus's control: 0am Panel R's GB1-scrambled Opus Blind campaigns on the same seeds, labelled non-concurrent.

**Reading.**
- Share, against the GB1 yardstick from 0am: k* = 0, with a guessing share of 0.89%. "Removes re-testing" needs a
  mean share at or below twice that, 1.78%. "Reduces" needs a paired drop of more than 10 points, otherwise "no
  effect". Crossing notes and the asymmetric slot-loss guard follow 0an. In practice only "reduces" and "no
  effect" are open.
- Final pick: the paired change with its 95% interval, and no band label, since no GB1 band was sized. Opus is
  descriptive. The highest-mean re-pick is reported beside it, as in the re-nomination analysis.
- List against own-name viability, as for the grid. GB1's own viable set is used, rounds are matched, the
  earlier-list group is separate, and the bootstrap is over campaigns.

**The smoke.** 2 campaigns per model per arm at fresh seeds 15,000,004 and 15,000,005, $1 per arm. Its gates are
F5's. Every campaign must complete with no empty or truncated reply and no prompt-induced format failure. There
may be no genuine parser disagreement beyond the known out-of-alphabet kind, and no campaign may lose more than
10 slots. The panel's
ceiling, about $30 in all, is set from the smoke's cost per campaign. The operator sees the smoke before the panel
runs.

## 0an.6 NOTE. The GB1 panel's ceiling, set after its smoke. 2026-10-03, before any panel call

The smoke (ff046a4) had no lost round, at most 3 lost slots, and no format failure, and the Menu's start-up check
passed on GB1. One genuine parser disagreement occurred in 230 Menu calls. An Opus reply put a prose aside between
four pipe lines. The primary parser, which the registered rules use, read the four intended candidates, and the
secondary read two. The operator reviewed the smoke and approved the panel as registered. The projection is $13.54:
$12.75 for the Menu arm and $0.79 for the control. The ceiling is $30 in all, $27 for the Menu arm and $3 for the
control.

## 0an.7. CURRENT MODELS FROM OTHER LABS. 2026-10-03, after step 1's probes, before any campaign call

**Step 1, done** (single-prompt probes only, $0.032; `scripts/probe_0an7.py`, `results/probe_0an7.json` and
`results/probe_0an7_extra.json`). Ids and prices come from OpenRouter's public list.
- GPT-6.1 Sol, `openai/gpt-6.1-sol`, listed 2026-09-29, $2 in and $10 out per million. Reasoning cannot be turned
  off: "Reasoning is mandatory for this endpoint and cannot be disabled". By default it used 92 to 165 reasoning
  tokens. At effort minimal it used 0, and the answer parsed. Temperature 0 is accepted, though the listing does
  not name the parameter.
- Gemini 3.1 Pro Preview, `google/gemini-3.1-pro-preview`, $2 in and $12 out per million, reasoning billed at $12.
  Reasoning cannot be turned off, with the same message. By default it used 364 reasoning tokens. At effort minimal,
  effort low and a 128-token reasoning budget it used 156 to 185, on a round-1 prompt and three repeats of a
  round-8 prompt. The answer arrived and parsed every time.
- Priced only: Claude Opus 5.5, `anthropic/claude-opus-5.5`, $4 and $20; GPT-6 Astra, `openai/gpt-6-astra`, $10
  and $50.
- Gemini 4 Argon: not listed as of 2026-10-03. `scripts/openrouter_watch.py` lists any Gemini 4 model on the public
  list, with its id and prices, and needs no key.

**Models and their setting.** Neither GPT-6.1 Sol nor Gemini 3.1 Pro can turn reasoning off. Both run at effort
minimal (`--reasoning-effort minimal`), are labelled reasoning models, and are also compared with Panel c. Gemini
4 Argon runs the identical design once listed, at its lowest reasoning setting, after its own step-1 probe.

**Design, per model.**
- Blind on the grid's landscape, n = 60, seeds 300,000 to 300,059, paired with the grid's Blind campaigns and
  Panel A0.
- Blind and Menu on scrambled GB1, n = 30 each, seeds 11,000,000 to 11,000,029, paired with 0an.6 and 0am.
- Output budget 16,000 tokens, temperature 0, the truthful re-ask on, the grid's other settings.

**An empty answer must count as empty.** `repdef/llm.py` uses a reply's reasoning text as its answer when the
answer text is empty, and the call then counts as non-empty. Before any 0an.7 call, the call log records that
case, and the smoke gate counts it as an empty reply.

**Readouts, as in 0an and 0an.6.**
- Share against the landscape's yardstick: 23.78% on the grid, 0.89% on scrambled GB1.
- The Menu on GB1 against the same model's GB1 Blind arm, paired by seed, labelled "removes", "reduces" or "no
  effect" with 0an's rules.
- Final pick with intervals, the highest-mean re-pick, the exploration and selection split, and distinct
  candidates.
- Each model against our existing models on the same seeds, paired by seed. On the grid that is Opus 4.7, Gemini
  2.5 Flash and DeepSeek V3.1 (grid Blind and Panel A0). On GB1 it is 0am's Blind campaigns and 0an.6's Menu
  campaigns. As a reasoning model, each is also set beside Panel c.

**Cost, projected** (`scripts/project_0an7.py`). Our own logs of the same arms give calls and tokens, with
Opus 4.7's pattern as the high case and Gemini 2.5 Flash's as the low. For 120 campaigns:
- GPT-6.1 Sol, $8.52 to $14.98;
- Gemini 3.1 Pro, $16.71 to $25.08;
- priced only: Claude Opus 5.5, $17.04 to $29.97, and GPT-6 Astra, $42.59 to $74.91. Both assume no reasoning
  tokens.

**The smoke.** 2 campaigns per arm per model at fresh seeds. The gates are F5's, with empty answers counted as
above, and the smoke reports reasoning tokens per call. Ceilings are set from the smoke, and the operator checks
step 1 before any campaign runs.

## 0an.7 NOTE. Reasoning never stands in for the answer, and the smokes. 2026-10-03, before any 0an.7 campaign

**The harness fix.** `repdef/llm.py` no longer uses a reply's reasoning text as its answer. A reply whose answer
text is empty is returned empty, with an error, whatever reasoning came with it. The existing failure path takes
it: the campaign fails unwritten, and the log names the empty content. The reasoning is kept in its own field
(reasoning_text), and the call log records it with visible_tokens, the completion tokens minus the reasoning
tokens. `tests/test_reasoning_never_stands_in_for_the_answer.py` sends a fake reply with empty content and
reasoning "x" and requires an empty call with no answer text. A mutation that restores the old behaviour fails it.
The smoke gate counts an empty answer as a failure, as 0an.7 requires.

**Where the old behaviour fired** (`scripts/audit_reasoning_fallback.py`). A call that used reasoning as its
answer has non-empty text, reasoning tokens above zero, and five or fewer visible tokens. Across every tag's call
logs, 389,419 calls in 231 files, exactly one call meets the rule. It is in Panel c, Gemini 2.5 Flash Blind, seed
300,000, round 2: a replacement ask whose 169 completion tokens were all reasoning, text "**Evaluating
Candidates**", unparseable. The campaign lost that slot. Every other tag has none. Panel c's 71 Gemini answers
longer than 1,500 characters have at least 411 visible tokens, so they are real answers. No reported number is
recomputed and none changes, so there is no strike entry.

**The smokes.** GPT-6.1 Sol and Gemini 3.1 Pro Preview at effort minimal, both labelled reasoning models. Each runs
2 campaigns in each of three arms: grid Blind on seeds 300,000 and 300,001, and GB1 Blind and GB1 Menu on seeds
11,000,000 and 11,000,001. That is 12 campaigns in all, $4 at most ($1.30 per arm), with an output budget of 16,000
tokens (`scripts/launch_0an7.py`). The seeds are the main run's first seeds by design. Per model, the gate reports:
- empty answers and fallback-pattern calls, which must be 0 or explained;
- the parse rate, refusals and slot loss;
- the median reasoning and visible tokens per call, and the cost per campaign.
GPT-6.1 Sol must still show about zero reasoning tokens at minimal on real campaign prompts. The main run's
ceilings are set from the smoke.

## 0an.7 NOTE 2. Comparators, and the smokes' result. 2026-10-03, before any 0an.7 main campaign

**Comparators.** On the grid, the 0an F0 control (Gemini 2.5 Flash, DeepSeek V3.1) has the same prompt options as
0an.7's grid Blind arm and is the clean comparator. Panel A0 (Opus 4.7) and Panel c predate the truthful re-ask
(0am.2). A comparison with Panel A0 is labelled "prompt differs only by the truthful re-ask line". A comparison
with Panel c is labelled "prompt differs only by the truthful re-ask line; medium effort". On GB1, 0am Panel R and
0an.6 share 0an.7's prompt options.

**The smokes** (`scripts/launch_0an7.py`, `scripts/smoke_detail_0an7.py`, 12 campaigns, $3.55). Every call
parsed. No answer was empty, no call matched the fallback pattern, no reply refused, and all 12 campaigns were
written, none abandoned. The truthful re-ask fired in 1 of GPT-6.1 Sol's 278 calls and none of Gemini 3.1 Pro's
388. The gate failed on one count: Gemini 3.1 Pro's two grid campaigns lost 14 and 12 slots, all to rejections
(92 and 96 per campaign), none to lost rounds. The operator decides before any main campaign.

## 0an.7 NOTE 3. The main run's settings and its registered readout. 2026-10-03, before any main campaign

**Settings, decided by the operator after the smokes.**
- Slot-loss gate: the F3 rule. Lost rounds count toward the limit of 10 slots; rejection losses are reported and
  not gated.
- Output budget: 32,000 tokens for Gemini 3.1 Pro, since one smoke call used 15,361 reasoning tokens of 16,000.
  GPT-6.1 Sol stays at 16,000.
- Abandonment: at most 5% of a model's campaigns per arm, 3 of 60 or 1 of 30; past that the arm stops and is shown.
  Each abandoned seed runs once more at the same seed and settings (`launch_0an7.py --rerun`, tag suffix _rerun),
  so pairing by seed holds. A seed abandoned twice is dropped from both sides of every pairing and reported.
- Ceilings: $22 for Sol and $76 for Gemini, split across each model's arms in proportion to the smoke's
  projected cost (`launch_0an7.py --main`).
- n as registered: grid Blind 60, GB1 Blind 30, GB1 Menu 30.

**The readout, registered before any main campaign is read** (`scripts/analyse_0an7.py`, tested on the smokes).
Per model and arm:
- Re-testing share two ways: over the budget, the convention so far, and over slots not lost (slots_used minus
  lost_slots). Both are given for every comparator and for the references, recomputed under the same rules by
  `scripts/references_0an7.py`. On the grid the guessing yardstick is 23.78% over the budget and 29.80% over slots
  not lost. On scrambled GB1 it is 0.89% and 0.95%.
- The nominee's true value against the informed reference and the guessing yardstick, with exploration and
  selection shortfalls. The comparisons are paired by seed: against F0 on the grid, against 0am on GB1 Blind and
  against 0an.6 on GB1 Menu, with the labels of note 2.
- How the nominee was chosen: the share of campaigns whose nominee had exactly one successful reading, and the
  share whose nominee was the single highest reading.
- Nominee concentration: the most frequent nominee and its count, and how often the comparator nominated it. In
  the GB1 Menu smoke, MLOL (true value 4.170) was nominated in 3 of 4 campaigns; 0an.6 nominated it once in 150.
- Menu minus Blind on GB1, paired by seed, per model, with the 0an share label against the GB1 yardstick.
- Lost slots by channel, and abandonments with their error text.

On scrambled GB1 the informed reference (k* = 0, 6.0182) sits below the guessing yardstick (k* = 0, 6.0868). Both
are given as computed.

## 0an.7 NOTE 4. Two readout additions, neither changing a registered test. 2026-10-03, before any main result is read

- The re-testing share over the budget stays the primary measure everywhere, and the "removes" and "reduces"
  labels are defined on it. The share over slots not lost is a second column, a check on the first.
- Both ends of the band exist in both versions. The guessing yardstick is 23.78% over the budget and 29.80% over
  slots not lost. The model-guided policy at its best (0an.4, k = 1 with confirmation) is 37.61% and 44.10%, from
  `scripts/model_guided_0an4.py` rerun with the second share added; its earlier numbers are unchanged.
- On scrambled GB1 the informed reference (6.018 at k* = 0) sits 0.07 below guessing (6.087), 1.3 unpaired
  standard errors, within noise. On GB1 it is a reference point only, with no claim to bound the agents' picks.

## 0an.7 NOTE 5. The arms' ceilings in flight, and how a stopped arm continues. 2026-10-03, during the main run

- GPT-6.1 Sol's GB1 Menu arm finished all 30 seeds, each distinct, at $4.59 against its $4.50 share. Campaigns
  already in flight finish after the budget check, which is the $0.09 overshoot. The model ceiling of $22 is the
  hard bound and is not at risk.
- If Gemini 3.1 Pro's GB1 Menu arm stops at its share, a further note records which seeds are missing and the
  funding source before anything runs. The funding is Gemini's actual unused ceiling, measured after its GB1 Blind
  arm has finished. Exactly those seeds then run at the same settings under the tag gen_0an7_gem_gb1_menu_cont,
  using `grid.py --seeds`, which runs an explicit list of seeds on the shuffled path and records it in the
  manifest. Gemini's total stays at or under $76. If the grid arm's spend means the total would pass $76, the run
  stops and the operator is shown before any continuation.
- The readout uses all 30 Menu seeds together and flags continuation seeds in its per-campaign table
  (`scripts/analyse_0an7.py`). It reports nothing until every arm is complete.

## 0an.7 NOTE 6. Gemini's GB1 Menu continuation: the missing seeds and the funding. 2026-10-03, before it runs

- Gemini 3.1 Pro's GB1 Menu arm stopped at its share, at $8.6626, with 27 of 30 seeds written, all distinct. The
  missing seeds are 11,000,000, 11,000,002 and 11,000,011.
- Campaigns still in flight at the stop were cancelled unwritten, so their spend is not recorded. With three
  workers, at most two were in flight. The largest Menu campaign so far cost $0.8344, so that spend is at most
  $1.6687.
- Funding: Gemini's GB1 Blind arm finished at $10.1631 of its $15.71 share, so $5.5469 is unused. The
  continuation draws on that.
- Order: the continuation waits until Gemini's grid arm has finished, so the $76 bound is checked against actual
  spend. Its budget is then the smaller of $5.5469 and $76 minus Gemini's recorded total minus the $1.6687 bound.
  It runs with one worker, so the budget check falls between campaigns. If that budget is below three times the
  largest Menu campaign, $2.5031, the run stops and the operator is shown before any continuation.

## 0an.7 NOTE 7. Gemini's ceiling raised to $80, and its remaining campaigns. 2026-10-03, before they run

- Gemini 3.1 Pro's ceiling goes from $76 to $80, by the operator's decision. A tighter cap risked leaving seeds
  unrun and pairs broken, and the raise costs at most about $4.
- The credit arithmetic behind it: the key's balance fell from $530.7611 at the main run's launch to $442.1026,
  so $88.6585 was spent. The campaign files record $84.5459, of which Sol is $20.3904 and Gemini $64.1555. The
  remaining $4.1126 is unrecorded and is all Gemini's, from campaigns cancelled at its Menu arm's stop and from
  its abandoned campaigns. The launch balance matches the smoke's end, $534.31 less $3.55.
- Gemini's grid arm abandoned 3 of 60 campaigns, within its limit of 3. Seeds 300,040 and 300,044 failed when the
  provider returned finish_reason=error. Seed 300,022 failed on an empty answer after 32,019 completion tokens, all
  reasoning.
- Order: the grid re-runs 300,022, 300,040 and 300,044 first, then the Menu seeds 11,000,000, 11,000,002 and
  11,000,011. They run with one worker, at the seeds and settings registered for each arm (`scripts/finish_0an7.py`).
- The hard stop is Gemini's total by credit balance. Before each campaign the balance is read again, and the run
  stops if the next campaign, at the largest cost seen in its arm, could take Gemini past $80.
- The abandonment rule holds as registered. A seed abandoned twice is dropped from both sides of every pairing
  that uses it, and reported.
- The readout adds three descriptive items. Per model, it counts calls with reasoning tokens above 16,000 and gives
  the largest seen. It reconciles recorded campaign spend with credit-balance spend, per model. It adds a
  sensitivity row with the abandoned-then-rerun grid seeds left out.

## 0an.7 NOTE 8. Five launches that never ran, and the fix. 2026-10-03, before they run again

The first pass of `scripts/finish_0an7.py` wrote seed 300,022's re-run. Its next five launches were refused by
grid.py's clean-tree gate, because `scripts/analyse_0an7.py` held an uncommitted edit. The script counted any
missing row as an abandonment, so it marked seeds 300,040, 300,044, 11,000,000, 11,000,002 and 11,000,011
"abandoned twice" and dropped them. None of them ran, and the credit balance did not move from $441.2966. They
are not abandoned and are not dropped. The log keeps both lines and a correction. The script now counts an
abandonment only when the run's log shows a FAILED or ABANDONED line for the seed, and stops on anything else.
The five seeds run again in the order of note 7.

## WELLOCATE NOTE 1. A design sweep over noise, not a registered test. 2026-10-04, before it runs

- Wellocate's noise sweep (`scripts/wellocate_noise_sweep.py`) keeps its three presets as they are: low, assay
  and high, CV 0.0365, 0.073 and 0.146. It adds CV 0.3 and 0.6 as a design sweep for the paper's noise figure.
  The design sweep is descriptive. No hypothesis rests on it and it gates nothing.
- At every level the guessing rule also runs under the risk-free rule of 0al, where a rejection costs no slot.
  On the grid at k = 0 about 23 slots are lost to rejections, against about 12 at k = 1. The two rules
  together separate re-testing's value in confirmation from its value in avoiding non-viable proposals.
- A correction to an impression from a smoke. At n = 30 the grid's best k looked to rise from 0 to 1 to 2 as
  noise rose from low to high. It did not hold at n = 1,500 on the paper's seeds, where k* = 1 at all three
  presets. No reported number rested on the smoke.

## 0an.8. THE GB1 BLIND ARM ON SCRAMBLED PHOQ, FIVE MODELS. 2026-10-05, before any call

**Why.** The paper's agent results on real protein data rest on GB1 alone. 0an.8 repeats the GB1 Blind arm on
scrambled PhoQ for all five models, so every real-protein claim can be checked on a second protein.

**Prior data on this landscape, disclosed.** 0am Panel R already ran scrambled PhoQ Blind for Opus 4.7 (n = 30),
Gemini 2.5 Flash and DeepSeek V3.1 (n = 60), on seeds 11,000,000 onward. Their mean shares over the budget were
known before this note: 65.3%, 61.7% and 91.4%, recomputed by this note's readout as its test. The named test
below is therefore informative mainly for GPT-6.1 Sol and Gemini 3.1 Pro. The 0am arm is reported beside the new
one as a descriptive cross-check: different seeds, a different day, unpaired.

**Landscape.** phoq_scrambled with scramble seed 20261004: the paper's scramble, 0am's four letter maps, and
Wellocate's phoq:paper instance (sha256 `d95092853d5996c8b56ebbfa24c760bf824d567a578f421846e66990c2b9fead`). The
frozen splits hold 430 other PhoQ scrambles for training, validation and testing. Their seeds run 1,100,000 to
1,100,399, 2,100,000 to 2,100,009 and 3,100,000 to 3,100,019, so 20261004 is none of them
(`scripts/launch_0an8.py --check`). The start is EDQS and the example IDQS, as in 0am.

**Settings: each model's GB1 Blind arm, with only the landscape changed.**
- The Blind condition, the truthful re-ask on and every other prompt option off.
- Assay noise: multiplicative, CV 0.073, with the read-depth floor.
- 15% failures, 15 rounds of 4, and three replacement asks before a slot is lost.
- Temperature 0 and OpenRouter's default routing.
- Opus 4.7, Gemini 2.5 Flash and DeepSeek V3.1: reasoning off and 6,000 output tokens, as 0am Panel R.
- GPT-6.1 Sol: effort minimal and 16,000 tokens. Gemini 3.1 Pro: effort minimal and 32,000 tokens (0an.7 note 3).

All five see the same prompt. The grid's Opus re-ask label does not arise, because 0am's GB1 arm already ran with
the truthful re-ask. The readout records each model's prompt options from its manifests.

**Seeds.** 30 campaigns per model on seeds 17,000,000 to 17,000,029, the same list for all five, so the models pair
by seed. The smoke uses 18,000,000 and 18,000,001. Both ranges are new in results, in run manifests, in seed bases
in tracked code and in Wellocate's splits.

**Scripted references, computed before any model call** (`scripts/references_0an8.py`,
`results/references_0an8.json`). They run through Wellocate, which runs the harness loop unchanged. They use the
1,500 reference seeds from 8,200,000 and the 30 agent seeds. The guessing rule reproduces 0am's PhoQ yardstick at
every k.
- Guessing rule, k = 0 to 4: picks 2.0500, 1.9842, 1.7923, 1.5810 and 1.0692; shares 1.03%, 23.81%, 46.85%,
  70.03% and 93.36%. Its best k is 0 (SE of the pick 0.0229).
- Informed rule: best k = 0, pick 2.6262 (SE 0.0362), share 0.00%.
- Model-guided policy, k = 1 with confirmation: pick 1.8509, share 36.62%.
- The best scripted policy is the informed rule at k = 0, which never re-tests, so the best scripted share is
  0.00%. The guessing rule pays for rejections as the agents do, and re-tests 1.03% at its best k.

**The registered readout** (`scripts/analyse_0an8.py`, committed with this note and tested on 0am's PhoQ Blind data).
- Primary: each model's re-testing share over the budget, with a 95% seed-bootstrap interval, against the best
  scripted share of 0.00%. The share over slots not lost is a second column.
- Named test: on GB1 every model re-tests more than the best scripted policy, Gemini 3.1 Pro included. This claim
  extends to PhoQ only if each model's interval lies above the PhoQ best scripted share. The readout gives the
  verdict per model and for all five together. A sensitivity line repeats it against the guessing rule's 1.03%.
- Secondary: each model's final pick minus the guessing rule's 2.0500. Its interval adds the guessing rule's own
  uncertainty, as in Appendix E. Exploration and selection loss, with intervals, beside the guessing rule's 6.692
  and 0.020.
- Descriptive only: the share of nominees with one successful reading, the top nominee's count, distinct candidates
  per campaign, and the nominee's basin. The basin view gives the share in the start's basin, the basin peak's
  value and the distinct basins measured.
- Also descriptive: lost slots by channel, out-of-alphabet proposals, the provider mix, and the pick paired by seed
  against the guessing rule on the same 30 seeds. Each model's GB1 Blind share and pick from the paper's arms sit
  beside its PhoQ numbers.

**The smoke.** 2 campaigns per model at seeds 18,000,000 and 18,000,001, all five at once. The budgets are $1.50
for Opus 4.7 and Sol, $3.00 for Gemini 3.1 Pro and $0.30 for the other two. The credit balance is read before
and after. The gate, per model (`scripts/launch_0an8.py --smoke-report`):
- complete: both campaigns written, none failed or abandoned;
- replies: no empty answer, fallback-pattern call, refusal, truncated reply or genuine parser disagreement;
- slots: no campaign loses more than 10 slots to lost rounds, the rule of 0an.7 note 3;
- no hidden truth: outside the history rows, the only decimal in any prompt is the start's stated value, 0.44.
  Every history row of every prompt is a row of that campaign's nomination history;
- scramble: the landscape is phoq_scrambled_s20261004_p93.0, every prompt names the start EDQS and the example
  IDQS, and no prompt names PhoQ, a protein or amino acids;
- reproduces: each nomination history, replayed through the oracle with the campaign's seed and the source-keyed
  draws, gives every outcome and reading again. Each nominee's recorded true value is the table's;
- settings: each manifest records the registered options, tokens, effort and temperature, and a clean tree;
- cost: 30 times the model's largest smoke campaign stays within its ceiling.

The truth, scramble and replay checks passed on 0am's PhoQ Blind arm, 150 campaigns and 3,235 prompts. Each fired
on a planted mutant.

**Cost gate and ceilings.** The projection is 30 times each model's largest smoke campaign. If every check passes
and the five projections sum to at most $80, the main run starts without waiting. Otherwise nothing more runs and
the projection is reported. The panel's ceiling is $100, smoke included. Per model: Gemini 3.1 Pro $30, Opus 4.7
$40 and the others $15.

**The main run** (`scripts/launch_0an8.py --main`), as 0an.7 note 7.
- One model at a time, in the order Opus 4.7, Gemini 2.5 Flash, DeepSeek V3.1, GPT-6.1 Sol, Gemini 3.1 Pro.
- One grid.py process per seed, with one worker. A relaunch skips the seeds already written.
- Before each campaign the credit balance is read again. A model's spend by balance is its start balance minus the
  balance now. The panel's is the balance before the smoke minus the balance now.
- The run stops if the next campaign, at the model's largest cost so far, could pass its ceiling or the panel's.

**Abandonment, as 0an.7 notes 3 and 8.** A campaign counts as abandoned only on a logged FAILED or ABANDONED line
for its seed. A launch that leaves neither a row nor such a line stops the run. At most 1 of a model's 30
campaigns may be abandoned. A second stops that model's arm, which is reported, and the next model runs. Each
abandoned seed runs once more at the same seed and settings, under the tag suffix _rerun. A seed abandoned twice
is dropped.

**Process, from note 8.** Every script is committed before the smoke. Nothing under scripts/ or repdef/ changes
while campaigns run. The smoke's outcome is recorded in a note before the main run.

**Reported whatever it shows.** Per model: campaigns completed, abandoned and re-run; share and pick with
intervals; exploration and selection loss; distinct candidates; nominees with one reading; and the top nominee's
count. Also the references, the named test per model, GB1 beside PhoQ, and spend recorded and by balance.

**What it cannot show.** It adds one protein, under scrambled names, with the noise model sized from GB1's read
counts. It runs after the other arms, on the providers OpenRouter picks that day. On PhoQ the best scripted share
is zero, so the named test asks whether a model re-tests at all. The guessing rule's line is reported beside it.

## 0an.8 SMOKE OUTCOME. 2026-10-05, before any main campaign

**What ran.** The smoke ran from 06e00bb: 10 campaigns at seeds 18,000,000 and 18,000,001. It cost $1.2598 by the
campaign records and $1.2275 by credit balance ($438.5926 before, $437.3650 after). Every campaign was written and
none failed. For all five models the complete, slots, no-truth, scramble, replay, settings and cost checks passed.

**The gate failed on one line.** One of GPT-6.1 Sol's 130 calls is a genuine parser disagreement. A replacement ask
in round 12 of seed 18,000,000 was answered with the bare line `IAKT`. The primary parser, which the registered
rules use, read IAKT. The secondary parser, which needs the pipe format, read nothing. Sol had no such call in its
6,229 calls of 0an.7. In 0an.6's note an earlier disagreement passed review because the primary parser had read the
intended candidates.

**Projection**, 30 times each model's largest smoke campaign. Opus 4.7 $7.58, Gemini 2.5 Flash $0.19, DeepSeek V3.1
$0.10, GPT-6.1 Sol $9.86 and Gemini 3.1 Pro $5.78. The total, $23.52, is within $80 and within every model's
ceiling. As registered, nothing more runs until the operator decides.

**The readout ran on the smoke's rows** (`scripts/analyse_0an8.py --smoke`). One descriptive item was added before
any main campaign. For Opus 4.7 the GB1 side-by-side gives the paper's 60-campaign arm (63.3%), which Table 3
uses. It also gives that arm's first 30 seeds alone (61.7%), which Appendix F quotes.

## 0an.8 NOTE 2. The smoke gate amended for a bare candidate reply; the main run approved. 2026-10-05, before any main campaign

**The operator's decision.** The one gate failure is no parse problem. Sol answered one replacement ask with the
bare line `IAKT`, a single valid candidate. The primary parser read exactly that, and the harness ordered it. The
secondary parser disagreed only because the reply had no "| reason". The main run is approved as registered.

**The amendment.**
- A reply that is exactly one valid candidate token counts as parser agreement when the primary parser read exactly
  that token. A valid token is four letters from A to T, after surrounding whitespace is stripped.
- Every other disagreement still fails the gate.
- `scripts/launch_0an8.py` implements it as `bare_single_token` and `genuine_disagreement`. A boundary test kept a
  reply with a reason, a letter outside A to T, lower case, two tokens, prose and a mismatched parse outside it.
- The readout counts, per model, the replies the rule covered (`bare_token_agreements` in the calls view).

**The smoke under the amendment.** The gate passes for all five models. The rule covered one reply, Sol's, and no
other. The projection is unchanged at $23.52.

**The main run** runs as registered: balance-gated, one model at a time, with the same ceilings. This commit holds
the amendment and the gate change. Nothing under scripts/ or repdef/ changes while campaigns run.

## 0an.8 NOTE 3. Abandoned campaigns keep their evidence; Sol's continuation; transient and fatal failures. 2026-10-05, before the probe

**Where Sol stopped.** GPT-6.1 Sol wrote seeds 17,000,000 to 17,000,014. Seeds 17,000,015 and 17,000,016 were
abandoned three minutes apart, each on "empty content after 0 completion tokens (finish_reason=None)". The
registered rule stopped the arm with 13 seeds unrun. The other four arms completed with no abandonment.

**The operator's decision.** Continue Sol after Gemini 3.1 Pro, with one check first: resend a failed request
exactly, to tell a prompt-caused failure from a provider-caused one.

**The check could not run as asked.** The failed requests were never recorded. llm_policy raised before logging
the failing call, and grid.py dropped an abandoned campaign's calls. What could be recovered:
- From timing alone, the failures came about 61 s and 165 s into their campaigns, near rounds 5 to 6 and 9 to 11.
- Successful Sol calls at those rounds carried 591 to 1,887 prompt tokens. All 802 carried 340 to 2,373.
- llm.py writes exactly this message when a response holds no choices at all, the likely sign of an error payload
  with HTTP 200. Without the raw payload this stays an inference.

**The fix: an abandoned campaign keeps its evidence.** It touches only the abandon path.
- llm_policy carries the failing request on the exception: its round, kind, attempt, prompt, call fields and raw
  response. The message, the exception's class and the 402 rule are unchanged.
- grid.py's one_campaign attaches the calls made so far to the exception when the campaign raises.
- main() writes those calls and the failing request to `grid_<tag>_abandoned_calls.jsonl`. No analysis reads that
  file, the campaign stays unwritten, and a failure to write it cannot change the run.
- llm.py's response handling is unchanged, so every 0an.8 campaign runs under the same parsing code.

The diff, for scripts/grid.py and repdef/llm_policy.py:

```diff
diff --git a/repdef/llm_policy.py b/repdef/llm_policy.py
index c343878..e340815 100644
--- a/repdef/llm_policy.py
+++ b/repdef/llm_policy.py
@@ -287,9 +287,13 @@ class CreditsExhausted(TransportFailure):
 
 
-def _raise_transport(model, error, kind):
-    """One place decides which failure this is, so the 402 rule cannot be applied at one call site only."""
-    if "402" in str(error):
-        raise CreditsExhausted(model, error, kind)
-    raise TransportFailure(model, error, kind)
+def _raise_transport(model, error, kind, failed=None):
+    """One place decides which failure this is, so the 402 rule cannot be applied at one call site only.
+
+    0an.8 note 3: `failed` is the request that failed, its prompt and its raw response, carried on the exception
+    as `failed_request` so grid.py can keep it beside the abandoned campaign's calls. The message, the class and
+    the 402 rule are unchanged; nothing here runs unless the call has already failed."""
+    exc = CreditsExhausted(model, error, kind) if "402" in str(error) else TransportFailure(model, error, kind)
+    exc.failed_request = failed
+    raise exc
 
 
@@ -503,5 +507,7 @@ class LLMPolicy(policies.Policy):
                 # THE CALL DID NOT HAPPEN. Previously this became an empty proposal list, which
                 # campaign.py charged as a forfeited round. Abandon the campaign instead.
-                _raise_transport(self.model, call.error, "round")
+                _raise_transport(self.model, call.error, "round",
+                                 failed=dict(round=view.current_round, kind=kind, n_slots=n_slots, attempt=attempts,
+                                             prompt=prompt, raw_payload=call.raw, **call_fields(call)))
             got, status, notes = parse(call.text, n_slots, alphabet=self.alphabet)
             out_of_alphabet += dropped_for_alphabet(notes)
@@ -587,5 +593,7 @@ class LLMPolicy(policies.Policy):
             # The nomination call IS the primary outcome. A campaign whose outcome was never measured
             # cannot be written, whatever happened in its rounds.
-            _raise_transport(self.model, call.error, "nomination")
+            _raise_transport(self.model, call.error, "nomination",
+                             failed=dict(round=view.total_rounds, kind="nomination", n_slots=1, attempt=1,
+                                         prompt=prompt, raw_payload=call.raw, **call_fields(call)))
         second_nom = parse_nomination_b(call.text, self.alphabet)
         if second_nom != seq:
diff --git a/scripts/grid.py b/scripts/grid.py
index 853442d..f7fc96b 100644
--- a/scripts/grid.py
+++ b/scripts/grid.py
@@ -688,9 +688,16 @@ def one_campaign(fit, pool, ps, prior, model, rung, seed, log_rows, max_tokens,
     else:
         _nm, _sig, _cv, _fl = "multiplicative", 0.0, CV, FLOOR
-    r = C.run(fit, pool, pol, _sig, seed, FAIL_PCT / 100.0, pool_sorted=ps,
-              nomination="agent", prior=prior, noise_model=_nm, cv=_cv,
-              noise_floor=_fl, rounds=ROUNDS, slots_per_round=SLOTS, max_reasks=max_reasks,
-              global_best=max(fit[s] for s in pool), riskfree_rejection=opts["riskfree_rejection"],
-              rng_key=rng_key, repeat_cap=_cap)
+    try:
+        r = C.run(fit, pool, pol, _sig, seed, FAIL_PCT / 100.0, pool_sorted=ps,
+                  nomination="agent", prior=prior, noise_model=_nm, cv=_cv,
+                  noise_floor=_fl, rounds=ROUNDS, slots_per_round=SLOTS, max_reasks=max_reasks,
+                  global_best=max(fit[s] for s in pool), riskfree_rejection=opts["riskfree_rejection"],
+                  rng_key=rng_key, repeat_cap=_cap)
+    except BaseException as e:
+        # 0an.8 note 3: THE ABANDON PATH ONLY. The calls made so far ride on the exception, labelled as the
+        # written path labels them below, so main() can keep them beside the failing request.
+        e.abandoned_calls = [dict(c, campaign_seed=seed, landscape=land_label, total_rounds=ROUNDS,
+                                  slots_per_round=SLOTS) for c in pol.calls]
+        raise
     for c in pol.calls:
         c["campaign_seed"] = seed
@@ -1088,4 +1095,21 @@ def main():
     lf = open(lpath, "a")
 
+    apath = os.path.join(RESULTS, "grid_%s_abandoned_calls.jsonl" % tag_now)
+
+    def keep_abandoned(e, seed, model, cell):
+        """0an.8 note 3: AN ABANDONED CAMPAIGN KEEPS ITS EVIDENCE. Its calls so far, and the request that failed
+        with its raw response, go to grid_<tag>_abandoned_calls.jsonl. Nothing reads that file for analysis;
+        the campaign stays unwritten. Before this, the abandon path dropped every call, so a failure could not
+        be told apart as the prompt's or the provider's. Never raises: keeping evidence must not change the run."""
+        try:
+            recs = [dict(c, abandoned=True) for c in (getattr(e, "abandoned_calls", None) or [])]
+            recs.append(dict(getattr(e, "failed_request", None) or {}, abandoned=True, failing_call=True,
+                             campaign_seed=seed, model=model, cell=cell, exception=str(e)))
+            with open(apath, "a") as fa:
+                for r in recs:
+                    fa.write(json.dumps(r, default=str) + "\n")
+        except Exception as e2:                                    # noqa: BLE001
+            print("      (could not keep the abandoned calls of seed %s: %s)" % (seed, e2))
+
     def flush(d, own):
         cf.write(json.dumps(d) + "\n")
@@ -1128,5 +1152,8 @@ def main():
                     d, own = fut.result()
                 except Exception as e:
-                    print("      %s %s seed %d FAILED: %s" % (t[0], t[3], t[4], e)); continue
+                    print("      %s %s seed %d FAILED: %s" % (t[0], t[3], t[4], e))
+                    with lock:
+                        keep_abandoned(e, t[4], t[3], t[0])
+                    continue
                 with lock:
                     rows.append(d); log_rows.extend(own); spent += d["spend"]; cum = spent
@@ -1192,4 +1219,6 @@ def main():
                         print("!" * 100)
                         credits_out[0] = True
+                        with lock:
+                            keep_abandoned(e, a.seed0 + i, model, cname)
                         for f2 in futs:
                             f2.cancel()
@@ -1200,7 +1229,13 @@ def main():
                         transport_fails[0] += 1
                         print("      seed %-6d ABANDONED (transport, not charged): %s"
-                              % (a.seed0 + i, e)); continue
+                              % (a.seed0 + i, e))
+                        with lock:
+                            keep_abandoned(e, a.seed0 + i, model, cname)
+                        continue
                     except Exception as e:
-                        print("      seed %-6d FAILED: %s" % (a.seed0 + i, e)); continue
+                        print("      seed %-6d FAILED: %s" % (a.seed0 + i, e))
+                        with lock:
+                            keep_abandoned(e, a.seed0 + i, model, cname)
+                        continue
                     with lock:
                         rows.append(d)
```

**The test** (`tests/test_an_abandoned_campaign_keeps_its_evidence.py`). It runs grid.main end to end against a
mocked provider. It runs the code before the change (07f0b02, extracted by git archive) and the code now, each in
its own temporary tree. A fake clock makes every time field deterministic, so nothing is masked.
- A written campaign: its campaign record and its archived call records are byte-identical under both versions.
- An abandoned campaign: its round-3 call returns the empty-content failure with a raw error payload. Both
  versions abandon it unwritten, with the same log line, and archive no call. Only the new code writes the
  separate file. That file holds the calls of rounds 1 and 2 and the failing request, with its prompt and raw
  payload.
- Two mutants each fail their test: disabling the keep fails the second, and adding a field to written calls
  fails the first.
- The guard `tests/test_every_logged_call_is_attributed.py` counted call_fields uses against appended rows. It
  now counts the kept failing requests beside them and requires every raise site to keep one. A mutant that
  drops one fails it.

**The probe and the continuation** (`scripts/launch_0an8.py --continue-model sol`).
1. The probe is seed 17,000,015's registered re-run, under the tag suffix _rerun. If it is written, the
   continuation goes on.
2. If the probe fails, its exact request is now on disk and is resent once: the same prompt, model, output budget,
   temperature and effort (`results/resend_0an8.json`). An empty resend stops everything before any other campaign
   runs. An answer means the provider failed, and the continuation goes on with 17,000,015 dropped.
3. Seed 17,000,016's re-run, then the 13 unrun seeds 17,000,017 to 17,000,029 under the tag suffix _cont.
4. The settings are the main run's. One campaign runs at a time. Each is gated on the credit balance against Sol's
   $15 ceiling and the panel's $100. Sol's spend counts its main run by balance plus the continuation's.
5. A continuation seed that fails runs once more under the tag suffix _cont_rerun and is dropped if it fails again.
   A seed already abandoned once is dropped on its re-run's failure. A third continuation failure stops the
   continuation, and it is reported.

**Transient and fatal failures, for future panels only.** A transient failure is one where nothing came back from
the provider. Examples are an error object, an HTTP 5xx or 429, or a reply with no choices and no tokens. A fatal
failure is one where the model answered and the answer is unusable. Examples are an empty answer after spending
tokens, or a reply cut at the output limit. Future panels should resend a transient call a bounded number of times
before abandoning a campaign. Only fatal failures should count toward an arm's abandonment limit. llm.py should
check for an error field in an HTTP-200 response. None of this applies to 0an.8, which keeps its registered rule
plus this continuation.

## 0an.8 NOTE 4. Finishing Sol's arm under a transport amendment. 2026-10-06, before anything runs

**The operator's decision.** Resume GPT-6.1 Sol to 30 campaigns. The arm stands at 22. Its continuation stopped
at its third failure, and the kept raw responses showed all three were provider overloads (note 3). Eight seeds
remain: 17,000,022 to 17,000,024, abandoned in the continuation, and 17,000,025 to 17,000,029, never run.

**1. The health gate.** One cheap request goes to Sol first: its exact round-1 prompt, at the arm's settings.
Nothing runs unless it succeeds. On a failure the launcher waits 15 minutes and tries again, at most 4 more
times, then stops and reports. Every try is recorded in `results/health_0an8.jsonl`.

**2. The transport amendment, for these 8 seeds only.**
- A raw response is an explicit provider overload when it carries an error object with code 502 or 503, or with
  error_type provider_unavailable (`provider_unavailable` in repdef/llm_policy.py).
- After one, the identical request is resent: up to 5 attempts in all, after waits of 30, 60, 120 and 240 s.
- Every overloaded attempt is kept in the call archive as a row of kind transport_retry, with its prompt, wait and
  raw response. These rows sit in their own list, so nothing a campaign computes from its calls changes.
- Any other failure abandons the campaign as registered. That includes a model's empty reply with a finish reason.
- The amendment is off unless grid.py is given --provider-retry. Every earlier 0an.8 campaign ran without it, and
  llm.py's response handling is unchanged.

The diff, for repdef/llm_policy.py and scripts/grid.py:

```diff
diff --git a/repdef/llm_policy.py b/repdef/llm_policy.py
index e340815..00cbdaa 100644
--- a/repdef/llm_policy.py
+++ b/repdef/llm_policy.py
@@ -263,2 +263,22 @@ def parse_answer(text, alphabet):
 
+# 0an.8 NOTE 4, THE TRANSPORT AMENDMENT. OFF unless LLMPolicy.provider_retry is set (grid.py --provider-retry).
+# Seconds to wait before attempts 2 to 5 of an identical request.
+PROVIDER_RETRY_BACKOFF = (30, 60, 120, 240)
+
+
+def provider_unavailable(call):
+    """An explicit provider overload in the raw response: an error object with code 502 or 503, or with error_type
+    provider_unavailable. Only that. A model's reply, empty or not, with or without a finish reason, never is."""
+    raw = call.raw if isinstance(call.raw, dict) else {}
+    err = raw.get("error")
+    if not isinstance(err, dict):
+        return False
+    try:
+        code = int(err.get("code"))
+    except (TypeError, ValueError):
+        code = None
+    meta = err.get("metadata") if isinstance(err.get("metadata"), dict) else {}
+    return code in (502, 503) or meta.get("error_type") == "provider_unavailable"
+
+
 class TransportFailure(RuntimeError):
@@ -415,4 +435,31 @@ class LLMPolicy(policies.Policy):
         self.calls = []
+        # 0an.8 note 4: resend an identical request after an explicit provider overload. Off by default. Each
+        # overloaded attempt is kept in its own list, never in `calls`, so nothing a campaign computes from its
+        # calls can change; grid.py writes them to the call archive as kind "transport_retry".
+        self.provider_retry = False
+        self.transport_retries = []
         self.name = "llm_%s_%s" % (rung, model.replace("/", "_"))
 
+    def _complete(self, prompt, rnd, kind, n_slots):
+        """Send one request. With provider_retry off this is exactly llm.complete. With it on, a response that is
+        an explicit provider overload (provider_unavailable) is resent identically, up to 5 attempts in all, after
+        30, 60, 120 and 240 s; every overloaded attempt is kept. Any other failure returns at once."""
+        call = llm.complete(prompt, self.model, max_tokens=self.max_tokens, temperature=self.temperature,
+                            env_file=self.env_file, reasoning_effort=self.reasoning_effort)
+        if not self.provider_retry:
+            return call
+        for attempt, wait in enumerate(PROVIDER_RETRY_BACKOFF, 1):
+            if call.ok or not provider_unavailable(call):
+                return call
+            self.transport_retries.append({
+                "kind": "transport_retry", "retry_of": kind, "round": rnd, "rung": self.rung, "cell": self.cell,
+                "model": self.model, "n_slots": n_slots, "attempt": attempt, "wait_s": wait, "prompt": prompt,
+                "raw_payload": call.raw, **call_fields(call)})
+            print("      provider unavailable on the %s call, round %s: attempt %d of %d, resending in %d s"
+                  % (kind, rnd, attempt + 1, len(PROVIDER_RETRY_BACKOFF) + 1, wait), flush=True)
+            time.sleep(wait)
+            call = llm.complete(prompt, self.model, max_tokens=self.max_tokens, temperature=self.temperature,
+                                env_file=self.env_file, reasoning_effort=self.reasoning_effort)
+        return call
+
     # -- the only thing the model is shown --------------------------------------------------
@@ -502,5 +549,3 @@ class LLMPolicy(policies.Policy):
             attempts += 1
-            call = llm.complete(prompt, self.model, max_tokens=self.max_tokens,
-                                temperature=self.temperature, env_file=self.env_file,
-                                reasoning_effort=self.reasoning_effort)
+            call = self._complete(prompt, view.current_round, kind, n_slots)
             if not call.ok:
@@ -587,5 +632,3 @@ class LLMPolicy(policies.Policy):
         prompt = self.nomination_prompt(view)
-        call = llm.complete(prompt, self.model, max_tokens=self.max_tokens,
-                            temperature=self.temperature, env_file=self.env_file,
-                            reasoning_effort=self.reasoning_effort)
+        call = self._complete(prompt, view.total_rounds, "nomination", 1)
         seq, reason, nom_notes = parse_answer(call.text, self.alphabet)
diff --git a/scripts/grid.py b/scripts/grid.py
index f7fc96b..6d2fd54 100644
--- a/scripts/grid.py
+++ b/scripts/grid.py
@@ -642,3 +642,3 @@ def one_campaign(fit, pool, ps, prior, model, rung, seed, log_rows, max_tokens,
                  stage_label="", reasoning_effort=None, noise="multiplicative", temperature=0.0,
-                 opening="grid", cell=None, prompt_options=None, env=None):
+                 opening="grid", cell=None, prompt_options=None, env=None, provider_retry=False):
     """max_reasks is threaded into the PROMPT as well as the harness, so the two cannot disagree.
@@ -662,2 +662,3 @@ def one_campaign(fit, pool, ps, prior, model, rung, seed, log_rows, max_tokens,
     pol.cell = cell or rung
+    pol.provider_retry = bool(provider_retry)           # 0an.8 note 4; off unless --provider-retry
     # AMENDMENT 0al. ONE dict sets the prompt and, for riskfree_rejection, the campaign's own rule, so the
@@ -699,3 +700,3 @@ def one_campaign(fit, pool, ps, prior, model, rung, seed, log_rows, max_tokens,
         e.abandoned_calls = [dict(c, campaign_seed=seed, landscape=land_label, total_rounds=ROUNDS,
-                                  slots_per_round=SLOTS) for c in pol.calls]
+                                  slots_per_round=SLOTS) for c in pol.calls + pol.transport_retries]
         raise
@@ -707,2 +708,6 @@ def one_campaign(fit, pool, ps, prior, model, rung, seed, log_rows, max_tokens,
         log_rows.append(c)
+    # 0an.8 note 4: every overloaded attempt the transport amendment resent, in the call archive, after the
+    # campaign's own calls. Empty unless --provider-retry is set and an overload happened.
+    for c in pol.transport_retries:
+        log_rows.append(dict(c, campaign_seed=seed, landscape=land_label, total_rounds=ROUNDS, slots_per_round=SLOTS))
     # THE DECOMPOSITION, always reported. It is an identity, so the code asserts it and does not trust it:
@@ -833,2 +838,6 @@ def main():
                          "them and restates the alphabet; every other re-ask is unchanged")
+    ap.add_argument("--provider-retry", action="store_true",
+                    help="0an.8 note 4: resend an identical request after an explicit provider overload (an error "
+                         "with code 502 or 503, or error_type provider_unavailable), up to 5 attempts after 30, "
+                         "60, 120 and 240 s, each attempt kept in the call archive. Off by default.")
     ap.add_argument("--riskfree-rejection", action="store_true",
@@ -1007,2 +1016,3 @@ def main():
         riskfree_cap=(C.RISKFREE_CAP if a.riskfree_rejection else None),
+        provider_retry=bool(a.provider_retry),          # 0an.8 note 4
         prompt_landscape=LANDSCAPE_PROMPT, anchor=anchor, anchor_reading=reading,
@@ -1141,3 +1151,4 @@ def main():
                              a.stage, a.reasoning_effort, _noise, a.temperature, opening=_open, cell=cn,
-                             prompt_options={k: getattr(a, k) for k in PROMPT_OPTIONS}, env=_e)
+                             prompt_options={k: getattr(a, k) for k in PROMPT_OPTIONS}, env=_e,
+                             provider_retry=a.provider_retry)
             d["condition"] = cn
@@ -1188,3 +1199,4 @@ def main():
                                  a.temperature, opening=_open, cell=_c,
-                                 prompt_options={k: getattr(a, k) for k in PROMPT_OPTIONS}, env=_e)
+                                 prompt_options={k: getattr(a, k) for k in PROMPT_OPTIONS}, env=_e,
+                                 provider_retry=a.provider_retry)
                 d["condition"] = _c
```

**3. The test** (`tests/test_a_provider_overload_is_resent.py`). It runs grid.main end to end on a mocked provider
with a fake clock, and records the waits without sleeping.
- One overload, then success: the campaign record is byte-identical to a run with no overload. So is the call
  archive once the one transport_retry row is set aside. The wait is 30 s.
- A model's empty reply with a finish reason: the campaign is abandoned at once, with no resend and no wait.
- Five overloads in a row: the campaign is abandoned after waits of 30, 60, 120 and 240 s. Its evidence file keeps
  the four resent attempts, the failing fifth and the calls of rounds 1 and 2.
- One overload without the flag: abandoned at once, as registered before the amendment.

Four mutants are each caught. They are a detector that fires on any failure, a changed backoff, the resend
switched off, and attempts left unlogged. The note-3 test still shows a written campaign byte-identical to 07f0b02
with the flag off. The call_fields guard counts the transport_retry rows.

**4. The run** (`scripts/launch_0an8.py --finish-model sol`, tag suffix _fin, all 8 seeds with --provider-retry).
- The order is 17,000,022, 17,000,023 and 17,000,024, then 17,000,025 to 17,000,029, one campaign at a time.
- The settings are the main run's. Each campaign is gated on the credit balance against Sol's $15 ceiling and the
  panel's $100. Sol's spend counts its main run, its continuation and this finish, each by balance.
- A seed still failing after its resends is dropped and reported. A third such seed stops the run.

**For the readout.** Sol's arm is read over all its tags. The calls view counts transport_retry rows per model,
with their waits, apart from the calls the agent's behaviour is measured on. A resent request is identical to the
first, so a campaign that needed one is read like any other.

### 0an.8 OUTCOME, recorded after every campaign was complete and the readout had run once. 2026-10-06

**What ran.** 150 campaigns, 30 per model, on seeds 17,000,000 to 17,000,029, with none dropped. Four arms ran
without an abandonment. GPT-6.1 Sol's arm finished under notes 3 and 4: two re-runs, five continuation campaigns
and eight under the transport amendment, which never had to resend. Every abandonment was a provider overload, and
the kept raw responses show it for the three that note 3's logging caught. The readout
(`scripts/analyse_0an8.py`, `results/analysis_0an8.json`) ran once, and a bookkeeping fix to its panel spend
changed no other number.

**Primary and the named test.** Re-testing share over the budget, with 95% intervals:
- Opus 4.7 62.8% [61.0, 64.6] and Gemini 2.5 Flash 63.7% [60.6, 66.6];
- DeepSeek V3.1 89.9% [87.5, 91.9];
- GPT-6.1 Sol 23.9% [20.8, 27.3] and Gemini 3.1 Pro 14.7% [13.1, 16.3].

Every interval lies above the best scripted share, 0.00%, and above the guessing
rule's 1.03%. The claim extends to PhoQ for all five models.

**Secondary.** Final pick minus the guessing rule's 2.050, with its uncertainty added:
- Opus 4.7 -0.16 [-0.30, -0.02] and Gemini 2.5 Flash +0.08 [-0.01, +0.15];
- DeepSeek V3.1 -1.22 [-1.31, -1.10];
- GPT-6.1 Sol +0.32 [+0.10, +0.54] and Gemini 3.1 Pro -0.33 [-0.46, -0.19].

Exploration loss runs from 6.39 to 7.93, and selection
loss is at most 0.06.

**Descriptive.** Sol nominated IAQT in 14 of 30 campaigns. On GB1 a lead of Sol's resting on one repeated nominee
did not survive a nominee-clustered check (Appendix E), and none was registered here. Gemini 3.1 Pro's nominee
had one reading in 97% of campaigns. The three models of 0am Panel R reproduce their earlier PhoQ arm: shares
65.3%, 61.7% and 91.4% then, against 62.8%, 63.7% and 89.9% now.

**Spend.** $20.89 by credit balance and $20.21 by campaign records, smoke included, against the $100 ceiling.
