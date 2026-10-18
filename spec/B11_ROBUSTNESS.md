# B11 robustness: two post-hoc analyses

**POST-HOC.** Both analyses were decided after the registered B11 test (`results/b11_test_A.json`,
`results/b11_test_B.json`) was run and read. Neither changes a registered outcome, and every number from them is
labelled post-hoc. Nothing here writes `results/b11_test_*.json`. Run C (a noise-varied PPO run) is dropped and
replaced by these analyses.

Code: `wellocate/examples/ppo_robustness.py`. CPU only, at most four worker processes.

## The networks

Run A's three selected checkpoints, the networks of `results/b11_test_A.json`: `training/out/b11/A_s{0,1,2}`,
checkpoints at updates 850, 600 and 100. Each file's sha256 must equal the `best_sha256` recorded in
`results/b11_test_A.json`, or the script aborts. A network acts as in the registered test (`ppo.Policy`, sampled
actions, keyed generators, `public(obs)`: no oracle view). It learns about noise only from repeat readings.

## Scripted policies

`wellocate.baselines`: random, the guessing rule at k = 0 to 4, the informed rule at k = 0 to 4, and the model-guided
policy (k = 1 with confirmation). Scripted policies nominate with the shrinkage rule, which is told the episode's
true noise CV (`scorecard.run_episode`). The best scripted policy at a setting is the one with the highest mean pick
among the eleven non-random policies on the same episodes (Wellocate's definition, `wellocate/scorecard.py`).

## Measures

Per episode: pick (the nominee's true value) and re-testing share (re-tests over the 60-slot budget,
`share_budget`), plus distinct candidates and lost slots. A collapsed scripted episode (fewer than two measured
candidates) is recorded as missing and left out of every comparison that uses it.

Run A's mean is over its three seeds. A paired difference involving Run A is computed as in the registered test
(`ppo.beats`): per seed, the mean paired difference over episodes, then the mean over seeds, with a 95% interval
from one resample of episodes shared by all seeds (10,000 resamples). A paired difference between two scripted
policies uses the same episode bootstrap. Each comparison has its own fixed bootstrap key, written to the output.

## 1. Noise robustness

**Episodes.** `nk:test`, all 1,500 (20 landscapes, campaign seeds 300,000,000 to 300,001,499), at noise CV 0.0365
(low), 0.073 (assay, the training noise) and 0.146 (high). Every other setting is Wellocate's default: 15 rounds of
4 slots. The network's action key is the registered test's (5001) at every noise level, so the three levels differ
only in the noise.

**Canary.** At 0.073 the script must reproduce `results/b11_test_A.json` for `nk:test` episode by episode: the
three trained networks, random, guessing k = 1, informed k = 2 and model-guided, pick and share. Any mismatch aborts
before anything is written.

**Outputs** (`results/b11_robustness_noise.json`), per noise level:

- every policy's mean pick and mean share with 95% intervals (Run A's: per seed and over seeds, `ppo.table`);
- Run A minus random, and Run A minus the best scripted policy at that level: pick and share, paired 95% intervals;
- for the guessing and the informed rule, the best k by mean pick, and each other k minus the best k: pick and share,
  paired 95% intervals;
- Run A's share at low and at high noise minus its share at assay noise, paired 95% intervals; the same for the
  best scripted policy at assay noise;
- per-episode pick and share for every policy (Run A per seed).

## 2. The LLM campaigns, replayed

**Contamination check, first.** For each landscape an LLM arm below used, the check asks whether it is in a B11
training or validation split: by instance name, and by built content (`landscapes.content_sha256`) against every
instance of `nk:train`, `nk:validation`, `gb1:train`, `gb1:validation`, `phoq:train` and `phoq:validation`. For the
grid it also compares the sorted table of fitness values, which a relabelling cannot change. It also reports whether
the arm's campaign seeds fall in a training or validation seed range. Written to
`results/b11_robustness_contamination.json` and reported before the grid arm is replayed. If the grid landscape is in
`nk:train` or `nk:validation` by any test, every grid row of the output is marked CONTAMINATED.

**Arms and episodes.** Each LLM campaign's own (landscape, campaign seed), Blind condition, campaigns dropped for
transport fallbacks left out (`scripts/analyse_0an7.rows_of`, as published):

| arm | Wellocate instance | LLM campaigns (tags) | seeds |
|---|---|---|---|
| grid | `nk/K1/seed1` | the paper's five-model grid arm (`scripts/basins.py`, "grid Blind") | 300,000 to 300,119 |
| gb1_scrambled | `gb1/scramble:20261003` | the paper's five-model GB1 arm (`scripts/basins.py`, "GB1 Blind") | 11,000,000 to 11,000,059 |
| gb1_real | `gb1/real` | panel R (`scripts/analyse_0am.py`: `gen_r_gb1real`, `gen_r_gb1real_top`), three models | 11,000,000 to 11,000,059 |
| phoq_scrambled | `phoq/scramble:20261004` | the paper's five-model PhoQ arm (`scripts/landscapes_0an8.py`) | 17,000,000 to 17,000,029 |

Not replayed: smoke and canary tags, prompt variants (Menu, Mechanism, ledger, structure, wording), the 0am grid
tags and panel R's scrambled-GB1 and PhoQ campaigns. Every policy plays each distinct (landscape, seed) of an arm
once, and is joined to each LLM on that LLM's seeds.

**Settings.** The campaigns' own: noise CV 0.073, 15 rounds of 4 slots, 15% failures. The script reads every
replayed tag's manifest and aborts if any differs from Wellocate's setting.

**Policies.** Random; the guessing and the informed rule at the k chosen on validation in B11 (recorded in
`results/b11_test_A.json`: grid from `nk:validation`; GB1 and PhoQ from `gb1:validation` and `phoq:validation`;
`gb1_real` uses `gb1:validation`); the model-guided policy; Run A's three networks (action keys 6001 grid, 6002
gb1_scrambled, 6003 gb1_real, 6004 phoq_scrambled).

**Canaries.** Wellocate's landscape for each arm equals the harness's (`repdef.envs`: table, pool, start and draw
keys) and carries the manifest's label; each LLM campaign's recorded global best equals that landscape's. The
guessing rule reproduces `results/yardsticks_0am.json`'s first-seed rows wherever that file has them. Each LLM's
mean pick and share equal the published cell (`results/landscapes_0an8.json` for grid, GB1 and PhoQ;
`results/analysis_0am.json` for `gb1_real`). Any mismatch aborts.

**Outputs** (`results/b11_robustness_llm.json`): one table per arm. For each LLM, on its own campaigns: the LLM's
mean pick and share, and each policy's (Run A over its three seeds), with 95% intervals, and Run A minus the LLM,
pick and share, paired 95% intervals. Per-episode pick and share for every policy and LLM. The grid table carries the
contamination verdict.
