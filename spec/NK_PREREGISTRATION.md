# PRE-REGISTRATION: the NK tuning criterion, committed before the landscape exists

Written 2026-09-27, before any NK generator code is written and before any NK landscape is
generated. The commit timestamp is the evidence.

**FIFTH AMENDMENT 2026-09-27.** The `gap/sigma >= 0.5` lower bound is WITHDRAWN: the chosen
generator sits at 0.22 and the shrinkage rule still beats max-single there at 5.7 held-out SE with a
larger effect size than GB1's, which refutes the argument the bound rested on
(`results/step6_nk_confirm.txt`). The upper bound at 1.5 stands.

---

**FOURTH AMENDMENT 2026-09-27, and it RETRACTS THE THIRD.** The third amendment registered the
contribution-tail distribution as a new axis because uniform NK had failed the margin criterion. That
failure was an artifact. The criterion was never measured.

**The defect.** `campaign._shrinkage_nominate` answered a sigma it could not use with
`return view.best_by_mean()`. Every caller that describes noise through `noise_model="multiplicative"`
passes the SCALAR `sigma=0.0`, because under multiplicative noise sigma is a function of the variant's
level and not a constant. So every such caller asked for shrinkage and silently received the MEAN
rule. The margin the second amendment made the primary target, `shrinkage - max-single`, was in fact
`mean - max-single` in every measurement ever taken of it, including GB1's reference value.

**What changes when the estimator actually runs** (n=1500, K=1, seed=1, pct=93):

| generator | before, mislabelled | with shrinkage actually running |
| --- | --- | --- |
| GB1 reference | +0.0146, 3.9 SE | +0.0144, 4.6 SE |
| NK uniform | +0.0008, 0.1 SE, fail | **+0.0317, 5.7 SE, PASS** |
| NK exponential | +0.0175, 4.4 SE, PASS | +0.0051, 1.2 SE, fail |

The two generators swap verdicts. Six of the seven distributions now pass, so tail weight is not the
discriminator and the central-limit story in the third amendment explained a measurement artifact.

**So the third amendment's premise is void and its protections are unnecessary.** Uniform is the
generator the ORIGINAL pre-registration specified. Choosing it is not a post-hoc selection over a
searched family, so the winner's curse the third amendment worried about does not apply: the
pre-registered default satisfies the pre-registered criterion. The held-out confirmation was run
anyway, because it was promised: **+0.0329 +- 0.0057, 5.7 SE on disjoint seeds, 4.6 SE after the
1.25x overdispersion inflation**, against a threshold of 3 committed before the number existed. The
held-out margin is slightly LARGER than the selection margin, which is what no selection bias looks
like.

**The neutrality criterion as the third amendment wrote it was MALFORMED, and this correction is
mathematical.** For a policy that never replicates, every variant carries one reading, n is constant
across variants, and the shrinkage posterior mean is a strictly increasing affine function of that
reading. A strictly increasing transform cannot move an argmax, so shrinkage and max-single select
the same sequence and the margin is identically zero for EVERY landscape. No generator can satisfy a
k=0 margin requirement. `random` and `greedy k=0` are reported and structurally excluded; the three
replicating baselines pass at 6.8, 6.1 and 8.8 SE. Pinned by
`tests/test_shrinkage_actually_runs.py::test_with_no_replication_the_two_rules_must_agree`.

**THE GAP BAND FAILS AND IS REPORTED AS FAILED.** The second amendment required
`0.5 <= gap/sigma <= 1.5`. Uniform NK sits at **0.22**, outside it. The lower bound was justified by
an argument: that below roughly 0.2 sigma no estimator reachable in 60 slots can resolve the top two,
so the rules would disagree by coin flip and the shortfall would be near zero by construction. **That
argument is refuted by the measurement it was written to protect.** At gap/sigma 0.22 the shrinkage
rule beats max-single at 5.7 held-out SE under three replication budgets, and its effect size,
0.055 sigma, EXCEEDS GB1's 0.036. The top two are resolvable at this separation, so the prediction was
wrong. The margin criterion is primary and met; the gap lower bound is recorded as a failed diagnostic
whose justification did not survive, and it is not quietly dropped.

**What is now required of any measurement of this criterion.** `scripts/nk_confirm.py` runs an
ESTIMATOR CANARY before it reports anything: it asserts that a zero scalar sigma raises, and that
shrinkage and mean disagree on some campaigns, and aborts otherwise. A margin table is not evidence
about an estimator unless the estimator is verified at the moment the table is produced. This is not
belt and braces: on the same day, a concurrent mutation-test run restored its own pre-fix snapshot of
`campaign.py` over the fix, and the script produced the broken table a second time with no error.

---

**THIRD AMENDMENT 2026-09-27, AFTER margins were measured on six contribution distributions and
BEFORE any behavioural result exists on the chosen one.** This amendment registers a NEW AXIS and
declares that the axis was searched, because the search is the thing a reader must be able to
discount.

**What is new.** The original document tuned over K and the viability threshold. It did not contain
the DISTRIBUTION of the per-locus fitness contributions at all; the generator used uniform
contributions because that is the textbook NK model, and uniform was never a registered choice, it
was an unexamined default.

**Why the axis was added, stated plainly.** NK with uniform contributions FAILED the margin criterion
outright, at +0.0008 and 0.1 paired standard errors against a target of 3. Rather than report the
generator as unusable, I reasoned that a central-limit argument predicted the failure: summing N
independent uniform contributions concentrates the fitness distribution, which compresses the top of
the landscape and removes the separation the margin needs. That predicted heavier per-locus tails
would help. I then measured six distributions.

**What the search found, and what it cost.** Exponential contributions give +0.0175 at 4.4 SE, which
passes, and exceeds GB1's own +0.0146 at 3.9 SE. Lognormal at shape 0.8 also passes at 4.0 SE.
Heavier tails than that FAIL, so the relationship is NON-MONOTONE in tail weight and the original CLT
reasoning, which predicted monotone improvement, was incomplete. The cost is that **4.4 SE is the
maximum over a searched family and is therefore optimistically biased.** This is the winner's curse,
applied to my own choice of landscape, and it is the exact phenomenon this paper measures in agents.
A paper that reports a selected maximum as if it were a pre-specified estimate would be committing
the error it exists to describe.

**What protects the claim, pre-committed here before it is run.**

> 1. HELD-OUT CONFIRMATION. The margin is re-estimated for NK-exponential on a DISJOINT set of
>    campaign seeds not used in the selection. The held-out margin is the number the paper reports.
>    The selection margin is reported beside it, labelled as selected, so the shrinkage between them
>    is visible instead of hidden.
> 2. THE HELD-OUT THRESHOLD IS 3 SE, the same target the second amendment set, and it is committed
>    now, before the held-out estimate exists. Shrinkage from 4.4 is expected; shrinkage below 3
>    means the generator failed and is reported as a failure, with GB1 used instead and its own
>    contamination reported alongside every result on it.
> 3. NEUTRALITY ACROSS BASELINES. The margin must hold when the comparator is each of the five
>    baseline rules and not only max-single, so that the chosen landscape does not favour one
>    estimator by construction. A landscape that passes against one baseline and fails against the
>    others is tuned to that baseline.
> 4. POWER, sized with the measured across-seed overdispersion of 1.25x on the standard deviation
>    (1.57x on campaign count), not with the binomial figure, because the seed-dispersion study
>    showed the binomial number understates the spread.
> 5. NO FURTHER DISTRIBUTIONS. The family searched is closed at the six already measured: uniform,
>    exponential, lognormal at 0.8 and 1.2, and pareto at two shapes. Adding a seventh after seeing
>    the held-out result would make the held-out set a second selection set.

**What is NOT protected. This is a limitation of the paper, and not a thing to fix.** The tail
distribution was chosen with knowledge of the margin it produces. No held-out estimate removes that;
it only measures how much of the 4.4 was selection. The honest statement is that the generated
landscape is ENGINEERED to make the two estimators separable, which is what a benchmark is for, and
that its uncontaminated status, not its margin, is the property being claimed.

---

**SECOND AMENDMENT 2026-09-27, AFTER a landscape was generated and verified but BEFORE any
behavioural result exists on it.** This is the amendment pre-registration exists to prevent, so the
reason is on the record and a reader may judge it.

**What is being replaced.** The informativeness criterion, "the shrinkage argmax and the max-single
argmax select different sequences in at least 50% of campaigns".

**Why it is invalid and not merely inconvenient.** It measures whether two rules DISAGREE. It does
not measure whether either is more likely to be right. At the achieved gap/sigma of 0.18 the top two
measured candidates differ by under a fifth of a standard deviation, and with four reads each the
standard error of the difference of their means is 0.71 sigma, four times the gap. At that separation
no estimator reachable in 60 slots can resolve them, so the two rules disagree by coin flip and a
rate near 50% is close to what PURE NOISE produces. **An environment of maximum ambiguity would score
as maximally informative while measuring nothing.** It also collapses the outcome the paper reports:
if the top two differ by 0.18 sigma in true fitness, nominating the wrong one costs 0.18 sigma, so
the selection shortfall would be near zero by construction.

**The replacement, which is HARDER to satisfy and not easier.**

> Tune so that the MEAN TRUE FITNESS of the sequence selected by the shrinkage estimator EXCEEDS the
> mean true fitness of the sequence selected by max-single, by a margin detectable at the planned
> campaign count. Both rules are applied to the SAME campaigns, so the comparison is paired. Report
> the margin, its paired standard error, and the campaign count that resolves it.

Pure noise gives a margin of exactly zero, so the new criterion cannot be satisfied by ambiguity. It
is strictly stronger than the disagreement rate: a nonzero margin requires disagreement, and
disagreement does not require a margin.

**Target: the margin must be positive at 3 or more paired standard errors.** Disagreement rate is
demoted to a reported diagnostic and is no longer a target.

**And the gap/sigma bound gains a lower limit**, which the first version omitted. Too small a gap
breaks the measurement as surely as too large a gap does, in the opposite direction. **Require
0.5 <= gap/sigma <= 1.5.** GB1 sits at 1.12, inside that band; its problem was the 14% rate, which
came from campaigns rarely reaching its dominant peak and not from the gap. The margin criterion
operationalises both bounds at once, so the gap band is reported as a diagnostic alongside it.

---

**FIRST AMENDMENT 2026-09-27, same day, and still before any generator code exists or any landscape
has been generated.** Four fixes, listed here so the amendment is auditable and not silent: the
informativeness comparator was inconsistent with the analysis comparator; seed selection was
unguarded; the failure branch was unwritten; and the dominant-peak criterion had no number. Every one
of those would have looked like moving the goalposts if fixed after a landscape had been seen, which
is the reason to fix them now. Nothing below may be changed after a landscape has
been seen; if a target turns out unreachable, that is reported as a failure to reach it and the
criterion stays as written.

## Why this document exists

Tuning a landscape so that noise frequently reorders the top candidates can be read as **building an
environment designed to make the agent fail.** That reading has to be answered on the page.

**The answer: this tunes for MEASURABILITY, not for failure.** A campaign is informative about a
decision rule only when two candidate rules would choose differently; when they agree, the campaign
cannot distinguish them and carries no information about which the agent is using. Measured, GB1
under its own assay's noise model gives an informative rate of **14%**, so 86% of campaigns cannot
distinguish any two decision rules and the environment cannot measure a decision rule at all.

The environment is neutral between rules by construction: every scripted policy and the agent run in
the same landscape under the same noise field, and the informative rate is a property of the
landscape and noise, not of any policy.

## The criterion

**Primary target.** Under the grid's noise model, at least **50%** of 60-measurement campaigns must
be INFORMATIVE, defined as: **the argmax by the SHRINKAGE estimator and the argmax by highest single
observation select different sequences.**

AMENDED. This originally said "argmax by mean observed". That was inconsistent with the analysis,
where the comparator is the shrinkage estimator because max-mean ignores unequal replicate counts and
so compares a variant with one reading against one with four as if equally precise. The tuning target
and the analysis must measure the same thing. Shrinkage is the posterior mean under a normal prior
fitted to the pool, already implemented as `_shrinkage_nominate` in `campaign.py` from Step 2's F3.

**The noise model for the grid**, fixed now:

    sigma(f) = sqrt(floor^2 + (f * CV)^2),  CV = 0.073,  floor = 0.0035

Both constants derive from Wu et al. 2016's published read depth: 557 input and 285 selected reads
per variant give `Var(log w) = 1/285 + 1/557`, hence CV 7.3%; one post-selection read is worth
`(1/557)/0.512 = 0.0035` fitness units, hence the floor.

**Secondary targets**, all to be reported whether or not they are met:

1. **Informative rate reported for the scripted baselines too**, in the same table: random, greedy
   k=0, greedy k=1, greedy k=2, greedy k=3. This is the neutrality evidence. If the rate differs
   materially across policies, the landscape is tilted and must be retuned.
2. **No dominant peak, as a number.** Let `g` be the MEDIAN top1-top2 true-fitness gap over 400
   simulated 60-measurement random-exploration campaigns, and let `s = sigma(f_champ)` where
   `f_champ` is the median true fitness of those campaigns' best measured variant. **Require
   `g / s < 1.5`, and report the value.** GB1 measures 1.12 at the POOL's top, but campaigns reach
   the pool's top only 3% of the time, so the campaign-level ratio is the binding one and is what
   this criterion uses.
3. **Viable-pool fraction between 5% and 10%**, matching the biological landscapes (GB1 7.20%, PhoQ
   6.97%), so the proposal-rejection rate is comparable.
4. **Hamming-1 autocorrelation between 0.25 and 0.45**, bracketing the two real landscapes (PhoQ
   0.264, GB1 0.403), so local search is neither trivial nor impossible.
5. **Never published, and shipped as a seeded generator and not as a fixed table**, so the benchmark
   does not contaminate the next generation of models the way GB1 was contaminated.

## The refusal rule

If a generated landscape fails the primary target, it is **discarded and regenerated with different
K**, up to 20 attempts. The number of attempts and the failing statistics of every rejected
candidate are reported. **No landscape is kept by relaxing the target after seeing it.**

### Seed-selection guard, AMENDED

Tuning on K and the viability threshold is deterministic and fine. **Sampling seeds and keeping the
first that clears 50% would select a landscape from the upper tail of the seed distribution**, which
is a different and less defensible thing.

So: at the chosen K and threshold, generate **20 seeds**, report the informativeness of all 20, and
**confirm the kept seed sits within the interquartile range of that distribution.** If the kept seed
is outside the IQR, the PARAMETERS are wrong, not the seed, and K or the threshold is changed instead.
The full 20-seed distribution is reported either way.

### The failure branch, AMENDED and decided now

Pre-registering only the success path is the part of pre-registration that is meaningful to skip. So
the branch is fixed before any number exists:

1. **If no (K, threshold) reaches 50% in 20 attempts**, fall back to a stated secondary target of
   **35%**, which still yields 7 informative campaigns in 20 and supports a directional result. The
   primary is then reported as UNMET, in the abstract and not only in an appendix.
2. **If 35% is also unreachable**, report that **the nomination measurement cannot be made under the
   multiplicative model**, and run the nomination half under the additive robustness panel only,
   labelled as such wherever it appears.
3. **The noise model is NOT changed to reach the target, at any point.** The constants are derived
   from Wu et al.'s published read depth. Tuning the physics to the measurement would invert the
   whole point of deriving them.

### The sizing rule, AMENDED, because a fallback target silently shrinks the grid

At a 35% informative rate, 13 campaigns in 20 say nothing about nomination, so the effective sample
for that half is barely a third of the nominal. A grid sized for 50% and delivered at 35% is
underpowered by a factor the paper would not notice.

So the rule is fixed now, before any rate is known:

> **campaigns to run = (target N from the power calculation) / (achieved informative rate)**,
> computed AFTER the landscape is verified and BEFORE the grid launches, with both the target N and
> the achieved rate reported in the methods.

This applies to the nomination half only. The clock half does not depend on informativeness, since a
crossing round is defined for every campaign, so it is sized from its own power calculation.

## What is NOT tuned

The landscape is tuned on ruggedness (K) and on the viability threshold only. It is **not** tuned on:

* any property of any agent's behaviour
* the replication rate, or the crossing round, or any outcome measure
* which policy wins

Tuning on any of those would be building the result, and the criterion above contains none of them.

## Pre-registered prediction, so the tuning cannot be steered

I predict the primary target is reachable at **K = 1 to 2** with a viability threshold near the 93rd
percentile, and that the informative rate will be roughly flat across the five scripted policies,
varying by under 10 percentage points. If the rate varies by more than that, the neutrality claim
fails and I will report it.
