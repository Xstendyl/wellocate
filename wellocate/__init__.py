"""Wellocate: a benchmark and RL environment for spending a fixed, noisy assay budget.

    from wellocate import Wellocate, evaluate, baselines
    env = Wellocate("gb1", "gb1:test", seed=0)
"""
from wellocate.env import Wellocate, Observation, NOISE_PRESETS, NOISE_FLOOR, shrinkage_nominee  # noqa: F401
from wellocate.landscapes import TRACKS  # noqa: F401
from wellocate.scorecard import evaluate, references  # noqa: F401
from wellocate import baselines, splits  # noqa: F401
