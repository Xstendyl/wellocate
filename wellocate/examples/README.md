# Wellocate examples

## B11: a policy trained with PPO through the released interface

`ppo.py` trains a small neural policy (not a language model) with PPO, on CPU. It acts only through
`Wellocate.step` and `Wellocate.nominate`, and reads the observation with its `view` removed. The design, the
settings and the success criteria are registered in `spec/B11_PREREGISTRATION.md`.

Reproduce one run and seed (about 6 to 9 hours on one CPU core; needs `torch` and `numpy`):

```
python3 wellocate/examples/ppo.py time                    # throughput only, no learning
python3 wellocate/examples/ppo.py train --run A --seed 0  # grid train only
python3 wellocate/examples/ppo.py train --run B --seed 0  # grid train plus GB1 train scrambles
```

Checkpoints, the training log and `summary.json` go to `training/out/b11/<run>_s<seed>/`. A seed fixes the
network's initialisation, the action sampling and the order of training landscapes, so a rerun with the same seed
gives the same weights. `tests/test_b11_ppo_policy.py` checks that.
