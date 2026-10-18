# Wellocate

When an AI agent runs experiments, each measurement is slow, costly and noisy. A high reading can mean a good
candidate or a lucky draw. With a fixed budget the agent keeps choosing between trying something new and
re-testing something that looks good. Wellocate measures that choice.

It is a simulated assay campaign with known true values: 15 rounds of 4 measurements, noisy readings, failed
orders, and a final pick scored on its true value. This repository holds the environment and everything behind
the paper *Explore or Confirm? LLM Agents Misallocate Measurements Under Noise*.

## What we found

We ran five language models as simple agents on a generated landscape and on two real protein landscapes, GB1
and PhoQ, with the amino-acid names scrambled so no model can answer from memory.

- **Models get the split wrong in both directions.** Opus 4.7, Gemini 2.5 Flash and DeepSeek V3.1 spend most of
  their budget re-testing, three to four times what the best scripted strategy spends. Gemini 3.1 Pro re-tests too
  little and usually picks a candidate it measured only once. On the generated landscape every model ends with
  a worse final pick than a basic scripted strategy.
- **Over-testers run out of ideas.** Giving them a short list of untried candidates cuts their re-testing
  sharply, and on GB1 two of them then pick much better. A tidy summary of their readings, or a description of
  the landscape, barely changes their behaviour.
- **The under-tester needs checks throughout the campaign.** Re-testing its top candidates in a final round
  wins back only about a quarter of what it loses by picking the wrong one.
- **The right split depends on the landscape and the noise.** On the generated landscape the best fixed strategy
  re-tests one slot in four. On the proteins it barely re-tests at the real assay's noise, and re-testing pays
  only at much higher noise. A fixed rule cannot be best everywhere, so an agent has to learn when to confirm.
- **A small trained policy already beats the models.** A policy trained with reinforcement learning on generated
  landscapes only picks better than all five models on their own grid campaigns, and it carries over to both
  proteins.

## What Wellocate measures

Two numbers explain most of an agent's result:

- **Re-testing share**: the fraction of the budget spent re-measuring candidates already measured, set against
  the best scripted share for the same landscape and noise.
- **Where the final pick falls short**: *exploration loss*, when the agent never measured a good enough
  candidate, and *selection loss*, when it measured a better candidate and nominated a worse one.

| in the lab | in Wellocate |
| --- | --- |
| an assay well | a slot: 15 rounds of 4, 60 in all |
| a failed assay | a failed order: about 15% fail, and the slot is spent |
| a variant that cannot work | a rejected candidate: most of the space does not work |
| replicate variability | noise on every reading, 7.3% of the true value by default, from the GB1 scan |
| the variant taken forward | the nominee, scored on its true value |

## Use it

```bash
git clone https://github.com/Xstendyl/wellocate.git && cd wellocate
python3 scripts/download_data.py      # the two protein landscapes
python3 scripts/quickstart.py         # two scripted strategies on one campaign
```

```python
from wellocate import Wellocate, evaluate, baselines

env = Wellocate("gb1", "gb1:test", seed=0)   # also "phoq" and "nk"; step(), nominate()
print(evaluate(baselines.guessing(0), "bio:test", n=100))
```

Language models get the exact prompts from the paper through `env.prompt()` and `env.act_text(reply)`. The splits
are fixed: train, validation and test sets of scrambled proteins and generated landscapes, with the real protein
names and rougher landscapes held out.

Reference results on the test splits, mean final pick with the re-testing share in brackets:

| split | random | guessing rule | informed rule | model-guided rule | best scripted share |
|---|---|---|---|---|---|
| `gb1:test` | 3.35 (0%) | 6.11 (1%) | 5.95 (0%) | 5.35 (35%) | 0.9% |
| `phoq:test` | 1.50 (0%) | 2.08 (1%) | 2.67 (0%) | 1.88 (37%) | 0.0% |
| `nk:test` | 7.51 (0%) | 7.94 (24%) | 8.01 (23%) | 7.97 (38%) | 23.3% |

The guessing rule must guess which candidates work, as the agents do. The informed rule is told which ones
work. The model-guided rule picks new candidates from a simple model of its own readings.

## Reproducing the paper

Every number in the paper is recomputed from the committed logs, and the check fails on any mismatch:

```bash
python3 scripts/verify_paper_numbers.py
```

The study was pre-registered; Appendix D of the paper lists what was registered, and `spec/` holds the
registration.

## Citation

```bibtex
@misc{karim2026wellocate,
  title  = {Explore or Confirm? {LLM} Agents Misallocate Measurements Under Noise},
  author = {Karim, Abdul and Keon, Matt},
  year   = {2026},
  url    = {https://github.com/Xstendyl/wellocate}
}
```

## Licence

The code is under `LICENSE` (MIT). The results, the paper and the study documents are under `LICENSE-DATA`
(CC BY 4.0). The two protein landscapes are third-party data and are not distributed here.
