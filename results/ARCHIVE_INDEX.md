# Call archive index

Every call the harness made is one JSONL row carrying `prompt` and `raw_response`.
The committed form is one gzip per (condition, model) cell under
`results/grid_<tag>_calls/`, with that directory's `MANIFEST.json` holding each
cell's line count and SHA256. Regenerate and verify this file with
`python3 scripts/archive_index.py`; `--check-only` verifies without writing.

410,047 calls in 74 tags, 58.0 MB compressed, all committed to git. No LFS.

| tag | what it is | cells | calls | MB | prompt+response | manifest |
|---|---|---:|---:|---:|---|---|
| `bioframing` | biology-framing panel (0aa), three role and noise cells on the Blind rung | 3 | 9,505 | 1.27 | yes | `e5347defe6333d37` |
| `gen_0an5_f2_menu_opus` | 0an.5 Opus menu top-up, seeds 300030-300059 | 1 | 1,671 | 0.29 | yes | `7c58c4f3691a9ce0` |
| `gen_0an6_gb1_control` | 0an.6 panel, concurrent no-tool control on scrambled GB1 (Gemini, DeepSeek) | 2 | 3,691 | 0.40 | yes | `83c425efd5e03909` |
| `gen_0an6_gb1_menu` | 0an.6 panel, Menu on scrambled GB1 (Opus n = 30) | 3 | 6,693 | 1.13 | yes | `900962547ed29569` |
| `gen_0an7_gem_gb1_blind` | 0an.7 main run, Gemini 3.1 Pro, GB1 scrambled Blind | 1 | 1,412 | 0.34 | yes | `b272647ddda2753c` |
| `gen_0an7_gem_gb1_menu` | 0an.7 main run, Gemini 3.1 Pro, GB1 scrambled Menu | 1 | 1,445 | 0.36 | yes | `9a730d703d41af85` |
| `gen_0an7_gem_gb1_menu_cont` | 0an.7 main run, Gemini 3.1 Pro, GB1 scrambled Menu, continuation of unrun seeds | 1 | 140 | 0.03 | yes | `ec0459552c95b959` |
| `gen_0an7_gem_grid_blind` | 0an.7 main run, Gemini 3.1 Pro, grid Blind | 1 | 5,288 | 1.31 | yes | `3bc243875a1adfc6` |
| `gen_0an7_gem_grid_blind_rerun` | 0an.7 main run, Gemini 3.1 Pro, grid Blind, re-run of abandoned seeds | 1 | 256 | 0.07 | yes | `740da769aaddcce1` |
| `gen_0an7_sol_gb1_blind` | 0an.7 main run, GPT-6.1 Sol, GB1 scrambled Blind | 1 | 1,408 | 0.28 | yes | `4cf797063f7d7841` |
| `gen_0an7_sol_gb1_menu` | 0an.7 main run, GPT-6.1 Sol, GB1 scrambled Menu | 1 | 1,356 | 0.30 | yes | `5c618b3690003e10` |
| `gen_0an7_sol_grid_blind` | 0an.7 main run, GPT-6.1 Sol, grid Blind | 1 | 3,465 | 0.70 | yes | `c1bc6b1c44c72088` |
| `gen_0an8_deepseek_phoq_blind` | 0an.8 main run, DeepSeek V3.1, scrambled PhoQ Blind, seeds 17,000,000 to 17,000,029 | 1 | 598 | 0.10 | yes | `3650a3055ef6f1dd` |
| `gen_0an8_flash_phoq_blind` | 0an.8 main run, Gemini 2.5 Flash, scrambled PhoQ Blind, seeds 17,000,000 to 17,000,029 | 1 | 635 | 0.09 | yes | `e180eeb2f0569b92` |
| `gen_0an8_gem_phoq_blind` | 0an.8 main run, Gemini 3.1 Pro, scrambled PhoQ Blind, seeds 17,000,000 to 17,000,029 | 1 | 1,041 | 0.24 | yes | `a732b8c5decbe7da` |
| `gen_0an8_opus_phoq_blind` | 0an.8 main run, Opus 4.7, scrambled PhoQ Blind, seeds 17,000,000 to 17,000,029 | 1 | 852 | 0.13 | yes | `a86aae4e83ead96e` |
| `gen_0an8_sol_phoq_blind` | 0an.8 main run, GPT-6.1 Sol, scrambled PhoQ Blind, seeds 17,000,000 to 17,000,029 | 1 | 802 | 0.16 | yes | `8dbdced178db4044` |
| `gen_0an8_sol_phoq_blind_cont` | 0an.8 note 3: GPT-6.1 Sol's continuation, the 13 seeds its stopped arm left unrun | 1 | 304 | 0.07 | yes | `482d46cc08e7ab02` |
| `gen_0an8_sol_phoq_blind_fin` | 0an.8 note 4: GPT-6.1 Sol's last 8 seeds, under the transport amendment (--provider-retry) | 1 | 558 | 0.12 | yes | `1e2662293bea5a1a` |
| `gen_0an8_sol_phoq_blind_rerun` | 0an.8 main run, GPT-6.1 Sol, scrambled PhoQ Blind, re-run of abandoned seeds | 1 | 73 | 0.02 | yes | `3816db422af022e6` |
| `gen_0an_f0_control` | 0an panel, F0 concurrent control (Gemini, DeepSeek), seeds 300000-300119 | 2 | 7,802 | 0.92 | yes | `97a62484479f34a8` |
| `gen_0an_f1_ledger` | 0an panel, F1 ledger | 3 | 10,548 | 1.44 | yes | `b7cb4e8841ad952a` |
| `gen_0an_f2_menu` | 0an panel, F2 menu (Opus n = 30) | 3 | 15,803 | 2.64 | yes | `e3d5aaa568399ce0` |
| `gen_0an_f5_structure` | 0an.3 panel, F5 structure (Opus n = 30) | 3 | 11,157 | 1.45 | yes | `5c51932b5a2c705c` |
| `gen_k0` | 0am Panel K: NK K = 0, 20 landscapes, Blind | 3 | 4,686 | 0.63 | yes | `afe80d75e9517013` |
| `gen_k1` | 0am Panel K: NK K = 1, 20 landscapes, Blind | 3 | 5,967 | 0.74 | yes | `00eb7f50619255ee` |
| `gen_k2` | 0am Panel K: NK K = 2, 20 landscapes, Blind | 3 | 7,657 | 0.97 | yes | `030bf1bd6e324dd3` |
| `gen_k3` | 0am Panel K: NK K = 3, 20 landscapes, Blind | 3 | 7,188 | 0.87 | yes | `f1347273f6d24be0` |
| `gen_r_gb1real` | 0am Panel R: GB1 under its real names, Blind and Mechanism, three models | 6 | 14,197 | 2.02 | yes | `df0934fbcef02de1` |
| `gen_r_gb1real_top` | 0am registered Opus top-up to n = 60, real-name GB1, run from e325069 | 2 | 1,585 | 0.26 | yes | `c3915c304a61b5e4` |
| `gen_r_gb1scr` | 0am Panel R: scrambled GB1, Blind and Mechanism, three models | 6 | 8,563 | 1.07 | yes | `8f32e14d17e1987a` |
| `gen_r_gb1scr_top` | 0am registered Opus top-up to n = 60, scrambled GB1, run from e325069 | 2 | 1,988 | 0.28 | yes | `89c8bd69e7434ec3` |
| `gen_r_phoqscr` | 0am Panel R: scrambled PhoQ, Blind and Mechanism, three models | 6 | 6,524 | 0.97 | yes | `ce99d3d4ce97009d` |
| `panelA0_original` | 0al.1 Panel A0: same-day drift control, original prompts, two segments (0al notes) | 6 | 11,113 | 1.47 | yes | `d0b6b3f1732a5571` |
| `panelA_wording` | 0al Panel A: goal_true_value + fix_replacement_budget, Blind and Mechanism, seeds 300000-300059 | 6 | 11,063 | 1.47 | yes | `9173f46b67ec124a` |
| `panelB_riskfree` | 0al Panel B: all three 0al options incl. riskfree_rejection, two segments (0al notes) | 6 | 11,462 | 1.58 | yes | `f540322162ed155f` |
| `panelc` | reasoning panel (c), reasoning effort medium | 4 | 5,852 | 0.92 | yes | `09e8dc2a887f9f71` |
| `probe` | pre-grid smoke probe | 3 | 336 | 0.05 | yes | `cb3f1ebe89b9cf41` |
| `probe2` | pre-grid smoke probe | 3 | 341 | 0.05 | yes | `a6a0077093c5b360` |
| `probe3` | pre-grid smoke probe | 3 | 337 | 0.05 | yes | `a3094fbc699df32f` |
| `replication_dsdr` | pre-registered replication (0ak), DeepSeek V3.1, Mechanism vs Decision-rule, new seeds | 2 | 5,717 | 0.89 | yes | `74fa5117b40d10d3` |
| `rprobe` | reasoning cost probe, used to set panel (c)'s ceiling | 2 | 334 | 0.06 | yes | `f5ba4de3be2e0003` |
| `rprobe20k` | reasoning probe at a raised token budget | 1 | 112 | 0.02 | yes | `f49a2c9421589112` |
| `smoke0am2_gb1real` | 0am second smoke (0am.2), real-name GB1 | 6 | 195 | 0.04 | yes | `741aeb66a3decdd6` |
| `smoke0am2_gb1scr` | 0am second smoke (0am.2), scrambled GB1 | 6 | 200 | 0.04 | yes | `21f5a200940dcd1d` |
| `smoke0am2_nk3` | 0am second smoke (0am.2), NK K = 3 | 6 | 279 | 0.04 | yes | `94be1ca8e2d6d683` |
| `smoke0am2_phoqscr` | 0am second smoke (0am.2), scrambled PhoQ | 6 | 132 | 0.03 | yes | `e2191859e67ff36f` |
| `smoke0am_gb1scr` | 0am first smoke, scrambled GB1 (failed: the real-GB1 canary; see 0am.2) | 6 | 182 | 0.03 | yes | `8eaf77a2f1d8f62f` |
| `smoke0am_nk3` | 0am first smoke, NK K = 3 | 6 | 234 | 0.04 | yes | `16bd143e88d4dba0` |
| `smoke0am_phoqscr` | 0am first smoke, scrambled PhoQ (out-of-alphabet rounds lost; see 0am.2) | 6 | 113 | 0.03 | yes | `e520caa4cd7b2bd4` |
| `smoke0an1_f3_cap` | 0an.1 F3 re-smoke (F3 withdrawn in 0an.2; descriptive) | 3 | 2,015 | 0.25 | yes | `740148c060fbb601` |
| `smoke0an3_f5_structure` | 0an.3 smoke, F5 structure | 3 | 267 | 0.04 | yes | `d23ce9bcf11bcae7` |
| `smoke0an6_gb1_control` | 0an.6 smoke, no-tool control on scrambled GB1 | 2 | 102 | 0.02 | yes | `7b333b64af034512` |
| `smoke0an6_gb1_menu` | 0an.6 smoke, Menu on scrambled GB1 | 3 | 230 | 0.05 | yes | `cbc9f52a708564ae` |
| `smoke0an7_gb1_blind` | 0an.7 smoke, GPT-6.1 Sol and Gemini 3.1 Pro at minimal effort, GB1 scrambled Blind | 2 | 207 | 0.05 | yes | `e510dc019f353e46` |
| `smoke0an7_gb1_menu` | 0an.7 smoke, GPT-6.1 Sol and Gemini 3.1 Pro at minimal effort, GB1 scrambled Menu | 2 | 162 | 0.04 | yes | `f5b467530485cad5` |
| `smoke0an7_grid_blind` | 0an.7 smoke, GPT-6.1 Sol and Gemini 3.1 Pro at minimal effort, grid Blind | 2 | 297 | 0.07 | yes | `776bf5a852e4e850` |
| `smoke0an8_deepseek` | 0an.8 smoke, DeepSeek V3.1, scrambled PhoQ Blind, seeds 18,000,000 and 18,000,001 | 1 | 32 | 0.01 | yes | `3df34bf77d65194a` |
| `smoke0an8_flash` | 0an.8 smoke, Gemini 2.5 Flash, scrambled PhoQ Blind, seeds 18,000,000 and 18,000,001 | 1 | 40 | 0.01 | yes | `6c348aff0a77ed18` |
| `smoke0an8_gem` | 0an.8 smoke, Gemini 3.1 Pro, scrambled PhoQ Blind, seeds 18,000,000 and 18,000,001 | 1 | 67 | 0.02 | yes | `e6e31fe5f00bfb1a` |
| `smoke0an8_opus` | 0an.8 smoke, Opus 4.7, scrambled PhoQ Blind, seeds 18,000,000 and 18,000,001 | 1 | 60 | 0.01 | yes | `4082207ecdf815a6` |
| `smoke0an8_sol` | 0an.8 smoke, GPT-6.1 Sol, scrambled PhoQ Blind, seeds 18,000,000 and 18,000,001 | 1 | 130 | 0.03 | yes | `55a0df3171a59e4f` |
| `smoke0an_f0_control` | 0an smoke, F0 control (Gemini, DeepSeek) | 2 | 99 | 0.02 | yes | `525f019859f788db` |
| `smoke0an_f1_ledger` | 0an smoke, F1 ledger | 3 | 209 | 0.03 | yes | `07b750a94fd2136e` |
| `smoke0an_f2_menu` | 0an smoke, F2 menu | 3 | 292 | 0.05 | yes | `cfe47278e9131b5b` |
| `smoke0an_f3_cap` | 0an smoke, F3 cap (F3 withdrawn in 0an.2; descriptive) | 2 | 313 | 0.06 | yes | `63ee725c02ae1827` |
| `stage0` | first stage-1 attempt, ABANDONED: the nomination prompt was truncated in every cell (build_nomination split inside the shared header). Kept because the deviations appendix cites these prompts as the evidence for that defect | 15 | 15,479 | 2.22 | yes | `0f51aa6d6bf06d9a` |
| `stage1` | stage 1 of the core grid, 5 conditions x 3 models x 40 campaigns | 15 | 18,017 | 2.38 | yes | `9d1f990627cc47fc` |
| `stage1a` | second stage-1 attempt, superseded after the aggregated-history fix | 15 | 7,285 | 0.97 | yes | `5494334df1bab9d9` |
| `topup_deepseek` | core grid top-up to the pre-registered N, deepseek | 5 | 19,052 | 2.67 | yes | `f762c7ad38be4159` |
| `topup_gemini` | core grid top-up to the pre-registered N, gemini | 5 | 14,729 | 1.67 | yes | `a5f44e442d4de4d8` |
| `topup_opus` | core grid top-up to the pre-registered N, opus | 5 | 111,188 | 15.27 | yes | `df28b1988d54d0f4` |
| `tpanel` | temperature panel (b), temperature 1.0 | 3 | 3,489 | 0.54 | yes | `3fcefe0cf57e0179` |
| `zeronoise` | zero-noise control panel, sigma = 0 | 15 | 23,426 | 3.05 | yes | `a1345b875e38358e` |

The `manifest` column is the first 16 hex of the SHA256 of that tag's cell digests
in name order, so one short string changes if any cell in the tag changes.

Raw plain logs are gitignored by `results/grid_*_calls.jsonl`, because stage 1's
reached 55 MB at 406 of 600 campaigns and the top-up would pass GitHub's 100 MB hard
limit. The release copy of the archive goes to Zenodo with the paper.

## Verification

Every gzip re-read, every SHA256 and line count matches the manifest its run
wrote, and every tag with a plain call log on disk has an archive directory.
