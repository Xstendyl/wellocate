# B11 pre-registration: a trained policy and its transfer to real proteins

Registered 2026-10-06, before any training run, in the commit that adds the training code
(`wellocate/examples/ppo.py`) and its tests (`tests/test_b11_ppo_policy.py`). This file is append-only: a change
after training starts is a dated amendment below, with its reason.

## Question

Two questions. The first is whether Wellocate is learnable through its released interface. The second is whether a
policy trained on simulated landscapes does better on real protein landscapes it never trained on.

## The policy

A small neural network trained with PPO. It is not a language model.

- **What it sees.** Wellocate's `Observation` with its `view` field removed, because the view holds the oracle's
  pool of viable candidates. That leaves the history of (round, candidate, outcome, reading), the budget, the
  reference point, its stated reading and the alphabet. It never sees a true value.
- **What it can do.** Each order picks one entry from a candidate set built from the history:
  - a re-test of any candidate ordered before and not rejected;
  - a single-letter substitution of the reference point, or of one of the 8 candidates with the highest mean
    reading, that has not been ordered;
  - a random action, which orders a candidate drawn uniformly from the whole space among those not yet ordered.

  So every candidate can be ordered. A round's slots are filled one at a time without repeats. At the end, a second
  head nominates one measured candidate.
- **Features.** Every feature is scale-free: readings over the stated reference reading, z-scores against the
  reference, and ranks within the episode. That lets a policy trained on the grid act on a protein.
- **Network.** Three MLPs with two hidden layers of 64 (tanh): an order head, a nominate head and a critic on 11
  global features.

## Training

- **Reward.** The nominee's true value over the landscape's best true value, given once at the end of the episode.
  It is the training signal only; the policy never observes it. There is no shaping.
- **PPO settings** (`CONFIG` in the code):
  - 32 episodes per update, from 4 landscapes with 8 episodes each;
  - 4 epochs, minibatches of 256 decisions, Adam at a learning rate of 3e-4, clip 0.2;
  - GAE with gamma 1 and lambda 0.95;
  - entropy coefficient 0.01, value coefficient 0.5, gradient norm clipped at 0.5.
- **Budget.** 1,500 updates (48,000 episodes), or 11.5 hours of wall clock, whichever comes first. The brief's
  limit is 12 hours per run.
- **Runs.** Each run trains with seeds 0, 1 and 2. A seed sets the network's initialisation, the action sampling
  and the order in which training landscapes are visited.
  - **Run A** trains on `nk:train` only.
  - **Run B** trains on `nk:train` plus `gb1:train`, with each update's 4 landscapes split 2 and 2.

  Every run uses the assay noise preset and the standard rules: 15 rounds, 4 slots, 15% failures and up to 3
  replacements.
- **Hardware.** CPU only, one thread per run. The six runs train in parallel.

## Validation and checkpoint choice

- **When.** Every 50 updates, and at the last update.
- **Validation episodes.** The first 200 episodes of each validation split: `nk:validation` for Run A;
  `nk:validation` and `gb1:validation` for Run B.
- **Actions.** Sampled from the policy, with generators keyed on the split and the episode. Every checkpoint
  therefore meets the same random numbers.
- **Score.** The mean over the run's validation splits of the mean pick over the landscape's best.
- **Choice.** The checkpoint with the highest score; a tie goes to the earliest. Its SHA-256 is recorded. The test
  data play no part in the choice.

## Test (once per run, after all three seeds have trained)

- **Episodes.** All 1,500 episodes of each test split:
  - Run A: `nk:test`, `gb1:test` and `phoq:test`;
  - Run B: `phoq:test`.

  Run A never trains on GB1 or PhoQ. Run B never sees PhoQ in any form.
- **Policies, on the same episodes:**
  - the selected checkpoint of each seed;
  - that seed's untrained initialisation (`init.pt`, saved before the first update);
  - random ordering;
  - the guessing rule;
  - the informed rule;
  - the model-guided policy (k = 1, with confirmation).

  The trained and untrained networks sample their actions with the same keyed generators, so they meet the same
  random numbers on each episode.
- **Scripted settings.** The scripted policies nominate with the registered shrinkage rule, as in
  `wellocate.scorecard`. The guessing and informed rules run at k = 0 to 4. The k reported for each family is the
  one with the highest mean pick on that family's validation episodes; every k is also listed.
- **Outcome measure.** The final pick (the nominee's true value), in the landscape's own units, paired by test
  episode.

## Pre-registered success

**"Policy beats X on a test split."** Both of these hold:

1. The mean over the three seeds of the paired difference in pick (trained minus X) is above zero, with a 95%
   bootstrap interval that excludes zero. The interval resamples test episodes 10,000 times with a keyed
   generator, applying the same resample to all three seeds.
2. Each seed's own mean paired difference is above zero.

X is the seed's own untrained initialisation, or random ordering.

**The criteria.**
- **Learnable.** Run A beats its initialisation and random ordering on `nk:test`.
- **Transfer.** Run A beats its initialisation and random ordering on `gb1:test` and on `phoq:test`. Run B does so
  on `phoq:test`.

**Reporting.**
- Each of the eight comparisons is reported on its own, with its interval.
- Whether each also holds at the Bonferroni level for eight comparisons (a 99.375% interval) is reported beside it.
- Matching or beating the scripted strategies is reported, but it is not required.
- Every result is reported either way. If transfer fails, the report says that the task is learnable within a family
  and that transfer needs mixed training.

## Report

- (a) **Learning curves:** validation score and validation pick against training updates and episodes, per seed.
- (b) **Test table per run and landscape:**
  - columns: pick, re-testing share, exploration loss and selection loss;
  - rows: each policy above;
  - intervals: 95% over episodes per seed, and across seeds by a two-level bootstrap (seeds, then episodes).
- (c) **Adaptation.** Whether the trained policy's re-testing share differs between the grid and the two proteins,
  and whether that difference follows the best scripted policy's.
- (d) **Cost.** Wall clock and episodes used per run and seed.

Raw numbers come first.

## Not changed after training starts

The policy, its features, the reward, the PPO settings, the budget, the validation episodes and score, and the
test episodes and criteria above. A crashed run restarts from scratch with the same seed (the tests check that a
seed reproduces), and the crash is recorded here. The test evaluation code is committed before the test is run, and
it implements this file.
