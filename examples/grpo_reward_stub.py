#!/usr/bin/env python3
"""A GRPO-style reward stub for Wellocate's text mode. It trains nothing.

For one episode (a split and a seed) a group of G complete trajectories is rolled out from the same start. Each
trajectory's reward is the true value of its nominee, the environment's terminal reward. The group-relative
advantage is each reward minus the group mean, over the group's standard deviation. A real trainer would sample
the replies from the policy being trained; here a toy sampler stands in, so the script runs with no model.

Usage: python3 examples/grpo_reward_stub.py [--group 8]
"""
import argparse, os, random, re, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wellocate import Wellocate  # noqa: E402


def toy_sampler(prompt, rng):
    """Stands in for the policy: answers in the required format with random single-letter changes."""
    alphabet = re.search(r"\(([A-Z]{20})\)", prompt).group(1)
    if "ANSWER: XXXX" in prompt:
        seen = re.findall(r"^\s+\d+\s+([A-Z]{4})\s+-?\d", prompt, re.M)
        return "ANSWER: %s\nREASON: highest reading" % (rng.choice(seen) if seen else "AAAA")
    n = int(re.findall(r"Reply with exactly (\d+) line", prompt)[-1])
    anchor = re.search(r'The reference point is "([A-Z]{4})"', prompt).group(1)
    out = []
    for _ in range(n):
        s = list(anchor)
        s[rng.randrange(4)] = rng.choice(alphabet)
        out.append("%s | a guess" % "".join(s))
    return "\n".join(out)


def rollout(sampler, landscape, split, seed, rng):
    env = Wellocate(landscape, split, seed=seed)
    done, reward = False, 0.0
    while not done:
        _obs, reward, done, _info = env.act_text(sampler(env.prompt(), rng))
    return reward


def group_advantages(rewards):
    m, s = statistics.mean(rewards), statistics.pstdev(rewards)
    return [(r - m) / s if s > 0 else 0.0 for r in rewards]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", type=int, default=8)
    a = ap.parse_args()
    rng = random.Random(0)
    rewards = [rollout(toy_sampler, "gb1", "gb1:train", 0, rng) for _ in range(a.group)]
    for r, adv in zip(rewards, group_advantages(rewards)):
        print("reward %.3f  advantage %+.2f" % (r, adv))


if __name__ == "__main__":
    main()
