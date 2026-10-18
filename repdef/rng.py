"""Counter-based randomness: each draw is a hash of its own coordinates, not a position in a stream.

Noise and synthesis failure for the n-th measurement of sequence s are keyed on (seed, s, n), so
every policy in a campaign sees the same reading for the same measurement and arms stay paired.
Policy decisions such as cold starts and exploration shuffles are keyed the same way.
"""

import hashlib
import math

_TWO64 = float(1 << 64)


def _u64(*parts):
    """A 64-bit digest of the given coordinates. Each part is length-prefixed, so different splits cannot collide."""
    h = hashlib.blake2b(digest_size=8)
    for p in parts:
        if isinstance(p, int):
            p = p.to_bytes(8, "big", signed=True)
        elif isinstance(p, str):
            p = p.encode("ascii")
        h.update(len(p).to_bytes(2, "big"))
        h.update(p)
    return int.from_bytes(h.digest(), "big")


def uniform(*parts):
    """A draw in [0, 1)."""
    return _u64(*parts) / _TWO64


def normal(*parts):
    """A standard normal draw, Box-Muller from two independent sub-hashes.

    u1 is clamped at 2^-64, the smallest value uniform() can return, to avoid log(0)."""
    u1 = uniform("bm1", *parts)
    u2 = uniform("bm2", *parts)
    if u1 <= 0.0:
        u1 = 1.0 / _TWO64
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def shuffled(items, *parts):
    """A deterministic permutation keyed on `parts`, independent of call order.

    Fisher-Yates driven by keyed draws, applied to a copy of `items`."""
    out = list(items)
    n = len(out)
    for i in range(n - 1, 0, -1):
        j = _u64("fy", i, *parts) % (i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def choice(items, *parts):
    """One keyed selection. Returns None for an empty sequence."""
    seq = items if isinstance(items, (list, tuple)) else list(items)
    if not seq:
        return None
    return seq[_u64("ch", *parts) % len(seq)]


def sample_without_replacement(items, n, *parts):
    """`n` distinct items, keyed. Returns fewer than n only when the input is smaller."""
    seq = items if isinstance(items, (list, tuple)) else list(items)
    if n >= len(seq):
        return shuffled(seq, *parts)
    # Partial Fisher-Yates: O(n) draws rather than a full permutation.
    out = list(seq)
    top = len(out) - 1
    picked = []
    for i in range(n):
        j = i + (_u64("swor", i, *parts) % (top - i + 1))
        out[i], out[j] = out[j], out[i]
        picked.append(out[i])
    return picked
