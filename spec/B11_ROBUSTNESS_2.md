# B11 robustness, part 2: post-hoc analyses and two training runs

**POST-HOC.** Everything here was decided after the registered B11 test (`results/b11_test_A.json`,
`results/b11_test_B.json`) and the first robustness analyses (`spec/B11_ROBUSTNESS.md`) were read. No registered
outcome changes. Every number is labelled post-hoc. Nothing writes `results/b11_test_*.json`. CPU only, on the Mac
mini, at most about ten processes. Committed before any run below.

Code: `wellocate/examples/ppo_robustness2.py`, plus the environment options below. Per-episode rows of every run are
saved.

## Shared definitions

- **Policies.** Random; the guessing rule and the informed rule at k = 0 to 4; the model-guided policy (k = 1 with
  confirmation); Run A's three registered networks (hash-checked against `results/b11_test_A.json`), zero-shot.
  "Best scripted" is the highest mean pick among the eleven non-random scripted policies on the same episodes.
  "Moderate" is k = 0 to 2; "heavy" is k = 3 and 4 (about 70% and 93% re-testing).
- **Run A's paired differences** follow the registered test (`ppo.beats`): per seed the mean paired difference,
  then the mean over seeds.
- **Cluster bootstrap.** 10,000 draws. Each draw resamples the split's landscapes with replacement, then each
  chosen landscape's episodes with replacement. Run A's three seeds are kept, as registered, and seed variation is
  reported separately: the three per-seed means, their range, and a t-interval over seeds (t at 2 degrees of freedom,
  4.303). A split with one landscape (the real landscapes, the LLM arms) has an episode bootstrap only, and says so.
- **Action keys.** Run A uses the registered test key of the split it plays (5001 nk, 5002 gb1, 5003 phoq) in every
  condition, so the action random numbers are the same across conditions. New splits: 5011 gb1:transfer_real, 5012
  phoq:transfer_real, 5021 nk:test_ood_k2, 5022 nk:test_ood_k3. Bootstrap keys are written to each output.

## Environment options (off by default)

Added to Wellocate through a subclass of the oracle in `wellocate/stress.py`; `repdef/` is unchanged. With every
option off, Wellocate's draws and rows are identical to today's, which a test checks against the registered rows.
Each option draws from its own keyed random stream, so it never shifts an existing draw.

- `batch_sd`: each round draws one factor `1 + batch_sd * z`, z standard normal keyed on (campaign seed, round),
  that multiplies every reading of that round, on top of the per-reading noise.
- `noise_floor`: the additive floor of `sigma(f) = sqrt(floor^2 + (f * CV)^2)`. Default 0.0035.
- `outlier_rate` and `outlier_kind`: a reading becomes an outlier with this probability, keyed on (campaign seed,
  sequence, attempt). Kind `zero` returns a failed-well value, `floor * |z|`; kind `spike` returns 3 times the
  noisy reading.

The scripted shrinkage nominee is told the condition's CV and floor. No policy models batch effects or outliers.

## Phase 1: re-analysis and evaluation (no training)

**1. Cluster-bootstrap table.** Every comparison in `results/b11_test_A.json`, `results/b11_test_B.json`,
`results/b11_robustness_noise.json` and `results/b11_robustness_llm.json`, recomputed from their per-episode rows:
the registered or published interval next to the cluster-bootstrap interval, plus the seed-level mean, range and
t-interval. Any interval that now crosses zero is flagged. Output `results/b11_cluster_bootstrap.json`.

**2. Behaviour replay.** Run A's and Run B's three networks each replay nk:test, gb1:test and phoq:test, 1,500
episodes, with logging. The replay must first reproduce every registered row exactly, or the script aborts. For
each, it reports:
- the re-testing share by round, 1 to 15;
- each re-test's rank by current mean reading, at the time of the order;
- each new candidate's parent rank, where the parent is the highest-ranked measured candidate one letter away, or the
  start;
- how often the nominee is the highest current mean reading, and how often it is the shrinkage nominee on the same
  final readings;
- the pick cost of any difference.

Output `results/b11_behaviour.json`; trajectories are kept in the per-episode files.

**3. Real landscapes.** `gb1:transfer_real` and `phoq:transfer_real`, 1,500 episodes each, every policy. The
registered comparators take their k from `gb1:validation` and `phoq:validation`, as registered. Output
`results/b11_real_landscapes.json`.

**4. Stress tests.** nk:test and gb1:test, 1,500 episodes each, every policy, at noise CV 0.073 in these
conditions:

| condition | setting |
|---|---|
| none | today's environment (also the canary: must equal the registered rows) |
| batch 5% | `batch_sd=0.05` |
| batch 10% | `batch_sd=0.10` |
| floor | `noise_floor=0.17524`, 2% of the landscape maximum. Phase 0 found no replicate data to estimate it from |
| zeros | `outlier_rate=0.02`, `outlier_kind=zero` |
| spikes | `outlier_rate=0.02`, `outlier_kind=spike` |

Cheaper replicates (a re-test costing half a slot) are not expressible, because a slot is the oracle's unit of
budget, and are skipped.

Per condition and landscape:
- the best k of each rule, and its re-testing share;
- k = 3 and k = 4 minus the best k of the same rule, with paired cluster-bootstrap intervals;
- Run A minus random, and Run A minus the best scripted policy.

The report names explicitly every condition, if any, in which k = 3 or 4 matches or beats the best of k = 0 to 2;
"matches" means the paired interval includes zero. Output `results/b11_stress.json`.

**5. Zero-shot generalisation.**
- **Held-out ruggedness:** `nk:test_ood_k2` and `nk:test_ood_k3`, 1,500 each, default budget.
- **Budgets:** 10 × 4, 20 × 4 and 4 × 24 on nk:test, 1,500 each. A smoke episode at 4 × 24 runs first.
- **k grid at 4 × 24:** the scripted k scales with slots per round, to k ∈ {0, 6, 12, 18, 24}.
- **Out-of-range features:** Run A's features scaled by the training budget are reported as out of range where they
  are: `slots_left/4` and `chosen_retests/4` at 4 × 24, and `len(means)/60` at 20 × 4.

Same comparisons as item 4. Output `results/b11_zero_shot.json`.

## Phase 2: training (overnight)

**6. Run B ablation.** Three seeds (0, 1, 2) of Run B's registered configuration with one change: `entropy_coef`
0.05, where the registered value is 0.01. Checkpoints go to `training/out/b11_rb2/B_s{0,1,2}`.
- **Selection:** the registered rule.
- **Test:** the registered test code, extended with seed and output-path parameters that default to today's
  behaviour, on phoq:test, gb1:test and nk:test.
- **Output:** `results/b11_B_ent05.json`.
- **Reported:** the order-head and nominate-head entropy curves, and whether Run B still collapses into heavy
  re-testing.

**7. Run A replication.** Five more seeds (3 to 7) of Run A's registered configuration, with checkpoints at
`training/out/b11/A_s{3..7}`. The registered code selects and tests them. Output `results/b11_replication_A.json`,
reported next to seeds 0 to 2. Started only if the total stays under about ten processes.
