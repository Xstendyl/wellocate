"""Additional landscapes (GB1, PhoQ, relabelled variants and fresh NK landscapes) built with the main grid's rules.

Each uses the same viability cut (93rd percentile), the same maximum value (8.762), and the same choice of
reference and example strings, so only the landscape changes. Relabelled landscapes map the amino acids to
the letters A to T per position and key random draws on the source string, so arms pair by seed.
"""
import functools
import statistics as st

from repdef import landscape as L
from repdef import rng as R
from repdef.nk import NKLandscape

AA = L.AA
ABSTRACT = "ABCDEFGHIJKLMNOPQRST"
PCT = 93.0
GB1_MAX = 8.762
# One seed per relabelled landscape, so the GB1 and PhoQ letter maps are independent.
SCRAMBLE_SEEDS = {"gb1": 20261003, "phoq": 20261004}
# 20 fresh NK landscapes per K, N = 4. Seed ranges are disjoint across K and exclude seed 1, used by the grid.
PANEL_K = (0, 1, 2, 3)
PANEL_K_N = 20
PANEL_K_SEEDS = {k: tuple(range(7000 + 100 * k, 7000 + 100 * k + PANEL_K_N)) for k in PANEL_K}
NAMES = ("gb1_scrambled", "gb1_real", "phoq_scrambled", "nk")


def scramble(seed):
    """Four independent bijections from the amino acids onto A to T, one per position."""
    return tuple(dict(zip(AA, R.shuffled(ABSTRACT, "scramble", seed, i))) for i in range(4))


def relabel(seq, maps):
    return "".join(maps[i][c] for i, c in enumerate(seq))


def grid_pool(fit, pct=PCT):
    """The grid's viability rule, exactly as `NKLandscape` applies it. Returns (threshold, pool)."""
    vals = sorted(fit.values())
    thr = vals[min(len(vals) - 1, int(pct / 100.0 * len(vals)))]
    return thr, frozenset(s for s, v in fit.items() if v > thr)


def reference_point(fit, pool, alphabet):
    """`grid.reference_point` with the alphabet as a parameter."""
    med = st.median([fit[s] for s in pool])
    anchor = min(sorted(pool), key=lambda s: (abs(fit[s] - med), s))
    h1 = sorted(anchor[:i] + c + anchor[i + 1:] for i in range(4) for c in alphabet if c != anchor[i])
    return anchor, h1[0], fit[anchor]


class Env(object):
    """One landscape as a campaign sees it: the values, the pool, the prompt's facts, and the draw key."""

    __slots__ = ("name", "label", "prompt_landscape", "alphabet", "fit", "pool", "ps", "prior",
                 "anchor", "example", "reading", "rng_key", "source_of", "global_best", "top10",
                 "threshold", "meta")

    def __init__(self, name, label, prompt_landscape, alphabet, fit, pool, threshold, anchor, example,
                 rng_key=None, source_of=None, meta=None):
        self.name, self.label, self.prompt_landscape = name, label, prompt_landscape
        self.alphabet, self.fit, self.pool, self.threshold = alphabet, fit, pool, threshold
        self.ps = tuple(sorted(pool))
        vals = [fit[s] for s in pool]
        self.prior = (st.mean(vals), st.variance(vals))
        self.anchor, self.example, self.reading = anchor, example, fit[anchor]
        self.rng_key = rng_key
        # display string -> source string, for logging what a relabelled order really was.
        self.source_of = source_of
        self.global_best = max(vals)
        self.top10 = tuple(sorted(pool, key=lambda s: (-fit[s], s))[:10])
        self.meta = dict(meta or {})

    def source(self, seq):
        return seq if self.source_of is None else self.source_of.get(seq, seq)

    def describe(self):
        """What a manifest records about this landscape. No values beyond the few the prompt states."""
        d = dict(name=self.name, label=self.label, prompt_landscape=self.prompt_landscape,
                 alphabet=self.alphabet, pool=len(self.pool), space=len(self.fit),
                 threshold=self.threshold, anchor=self.anchor, anchor_source=self.source(self.anchor),
                 anchor_reading=self.reading, example=self.example,
                 example_source=self.source(self.example), example_viable=self.example in self.pool,
                 global_best=self.global_best, top10=list(self.top10),
                 top10_source=[self.source(s) for s in self.top10],
                 draws_keyed_on_source=self.rng_key is not None)
        d.update(self.meta)
        return d


def _relabelled(name, source_name, scramble_seed, prompt_landscape="abstract"):
    ls = L.load(source_name)
    factor = GB1_MAX / max(ls.fitness.values())
    src = {s: v * factor for s, v in ls.fitness.items()}
    thr, pool = grid_pool(src)
    anchor, example, _r = reference_point(src, pool, AA)
    maps = scramble(scramble_seed)
    fit = {relabel(s, maps): v for s, v in src.items()}
    if len(fit) != len(src):
        raise AssertionError("the relabelling is not a bijection: %d strings became %d"
                             % (len(src), len(fit)))
    key = {relabel(s, maps): s for s in src}
    meta = dict(source=source_name, scale_factor=factor, scramble_seed=scramble_seed,
                letter_maps=["".join(m[a] for a in AA) for m in maps],
                letter_maps_read_as="position i maps the amino acids %s, in that order, to these letters"
                                    % AA)
    return Env(name, "%s_s%d_p%.1f" % (name, scramble_seed, PCT), prompt_landscape, ABSTRACT, fit,
               frozenset(relabel(s, maps) for s in pool), thr, relabel(anchor, maps),
               relabel(example, maps), rng_key=key, source_of=key, meta=meta)


@functools.lru_cache(maxsize=None)
def gb1_scrambled():
    return _relabelled("gb1_scrambled", "gb1", SCRAMBLE_SEEDS["gb1"])


@functools.lru_cache(maxsize=None)
def phoq_scrambled():
    return _relabelled("phoq_scrambled", "phoq", SCRAMBLE_SEEDS["phoq"])


@functools.lru_cache(maxsize=None)
def gb1_real():
    """GB1 under its own amino-acid names and the protein-engineering framing (the `gb1_bio` terms)."""
    ls = L.load("gb1")
    factor = GB1_MAX / max(ls.fitness.values())
    fit = {s: v * factor for s, v in ls.fitness.items()}
    thr, pool = grid_pool(fit)
    anchor, example, _r = reference_point(fit, pool, AA)
    return Env("gb1_real", "gb1_real_p%.1f" % PCT, "gb1_bio", AA, fit, pool, thr, anchor, example,
               meta=dict(source="gb1", scale_factor=factor))


@functools.lru_cache(maxsize=None)
def nk(k, seed):
    """A fresh NK landscape built exactly as the grid builds K=1 seed=1."""
    land = NKLandscape(k=k, seed=seed, threshold_percentile=PCT, dist="uniform")
    factor = GB1_MAX / max(land.fitness.values())
    fit = {s: v * factor for s, v in land.fitness.items()}
    anchor, example, _r = reference_point(fit, land.pool, ABSTRACT)
    return Env("nk", "nk_uniform_k%d_s%d_p%.1f" % (k, seed, PCT), "abstract", ABSTRACT, fit, land.pool,
               land.threshold * factor, anchor, example,
               meta=dict(source="nk", nk_k=k, nk_seed=seed, scale_factor=factor))


def panel_k_index(offset):
    """Which of a K's 20 landscapes campaign offset i runs on (cycling every 20 offsets), so models pair by seed."""
    return offset % PANEL_K_N


def panel_k_env(k, offset):
    return nk(k, PANEL_K_SEEDS[k][panel_k_index(offset)])


def env_for(name, offset=0, nk_k=None):
    """The landscape a campaign at seed offset `offset` runs on."""
    if name == "gb1_scrambled":
        return gb1_scrambled()
    if name == "gb1_real":
        return gb1_real()
    if name == "phoq_scrambled":
        return phoq_scrambled()
    if name == "nk":
        if nk_k not in PANEL_K:
            raise ValueError("the nk landscape needs nk_k in %s, got %r" % (PANEL_K, nk_k))
        return panel_k_env(nk_k, offset)
    raise ValueError("unknown 0am landscape %r; known: %s" % (name, ", ".join(NAMES)))


def all_envs(name, nk_k=None):
    """Every distinct landscape a run of this name can use."""
    if name == "nk":
        return [nk(nk_k, s) for s in PANEL_K_SEEDS[nk_k]]
    return [env_for(name)]


def round1_orders(history, env):
    """Every string ordered in round 1, in order, rejected ones included, and what it tells about prior
    knowledge: how many distinct members of the landscape's true top 10 were ordered, and whether the
    global best was."""
    seqs = [h.seq for h in history if h.round == 1 and h.seq != "----"]
    top = set(env.top10)
    return dict(round1_orders=seqs,
                round1_orders_source=[env.source(s) for s in seqs] if env.source_of else None,
                round1_top10_distinct=len(set(seqs) & top),
                round1_top10_any=bool(set(seqs) & top),
                round1_global_best=env.top10[0] in set(seqs))
