"""The landscapes Wellocate runs on, in two tracks.

  bio      scrambled GB1 and scrambled PhoQ: two deep mutational scans of four protein positions, each with
           160,000 measured variants (Wu et al. 2016; Podgornaia and Laub 2015). The amino-acid names are
           replaced by the letters A to T through a random bijection at each position, recorded by its seed.
           Fitness and Hamming neighbours carry over exactly. The scramble stops a model answering from a
           published landscape it may have memorised. The real names are kept as held-out transfer tests.
  sandbox  generated NK landscapes (Kauffman and Weinberger 1989) built by the paper's grid rules, for
           controlled studies: ruggedness K is a parameter and a fresh landscape is one seed away.

Every landscape is built by `repdef.envs`, the code the paper ran, so it carries the grid's viability rule
(the top 7% of the 160,000 strings), its scale (maximum 8.762) and its reference point (the pool median).
An instance is named by a short string: "gb1/scramble:20261003", "gb1/real", "nk/K1/seed1".
"""
import collections
import functools
import hashlib

from repdef import envs as EV
from repdef import landscape as L

TRACKS = collections.OrderedDict([("bio", ("gb1", "phoq")), ("sandbox", ("nk",))])
FAMILY_TRACK = {f: t for t, fs in TRACKS.items() for f in fs}
REAL_PROMPT = {"gb1": "gb1_bio", "phoq": "phoq_bio"}


@functools.lru_cache(maxsize=None)
def _phoq_real():
    """PhoQ under its own amino-acid names, built as `repdef.envs.gb1_real` builds GB1."""
    ls = L.load("phoq")
    factor = EV.GB1_MAX / max(ls.fitness.values())
    fit = {s: v * factor for s, v in ls.fitness.items()}
    thr, pool = EV.grid_pool(fit)
    anchor, example, _r = EV.reference_point(fit, pool, EV.AA)
    return EV.Env("phoq_real", "phoq_real_p%.1f" % EV.PCT, "phoq_bio", EV.AA, fit, pool, thr, anchor, example,
                  meta=dict(source="phoq", scale_factor=factor))


@functools.lru_cache(maxsize=8)
def _scrambled(family, seed):
    if family == "gb1" and seed == EV.SCRAMBLE_SEEDS["gb1"]:
        return EV.gb1_scrambled()
    if family == "phoq" and seed == EV.SCRAMBLE_SEEDS["phoq"]:
        return EV.phoq_scrambled()
    return EV._relabelled("%s_scrambled" % family, family, seed)


@functools.lru_cache(maxsize=8)
def _nk(k, seed):
    # EV.nk keeps every landscape it builds; the bounded cache here calls the function it wraps, so a run over
    # the 400 training landscapes holds at most 8 at a time.
    return EV.nk(k, seed) if (k, seed) == (1, 1) else EV.nk.__wrapped__(k, seed)


def instance(name):
    """The `repdef.envs.Env` for an instance name."""
    family, _, rest = name.partition("/")
    if family in ("gb1", "phoq"):
        if rest == "real":
            return EV.gb1_real() if family == "gb1" else _phoq_real()
        if rest.startswith("scramble:"):
            return _scrambled(family, int(rest.split(":", 1)[1]))
    if family == "nk" and rest.startswith("K"):
        k, s = rest.split("/")
        return _nk(int(k[1:]), int(s[len("seed"):]))
    raise ValueError("unknown landscape instance %r" % (name,))


def content_sha256(env):
    """A hash of everything a campaign on this landscape depends on: every string, its value to 9 decimals,
    its viability, the reference point and the draw key. Two builds that hash alike run alike."""
    h = hashlib.sha256()
    for s in sorted(env.fit):
        h.update(("%s %.9f %d %s\n" % (s, env.fit[s], s in env.pool,
                                       env.rng_key[s] if env.rng_key else s)).encode())
    h.update(("anchor %s example %s\n" % (env.anchor, env.example)).encode())
    return h.hexdigest()
