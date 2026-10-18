"""Load a fitness landscape, build its viable pool, and verify the data file by SHA256.

The data files have 160,000 rows because unmeasured variants are filled with zero; these
fills are never in the viable pool. The hash check ensures the constants used downstream
match the file loaded.
"""

import csv
import hashlib
import os

AA = "ACDEFGHIKLMNPQRSTVWY"
AA_SET = frozenset(AA)
SITES = 4

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Expected files and hashes, from the HuggingFace mirror pinned in scripts/download_data.py.
EXPECTED = {
    "phoq": {
        "file": "phoq.csv",
        "sha256": "6669ffb8093630278c55310aea479136c44f4aa91bd065ea30f13769c1f203b1",
        "bytes": 1_857_322,
        "rows": 160_000,
        "max_fitness": 133.594,
        "exact_zeros": 108_989,
        "viability_threshold": 1.0,
        "viable_pool": 11_146,
    },
    "gb1": {
        "file": "gb1.csv",
        "sha256": "98b8b4e73c18967b8dc076443bf620915f5f27d99630f512ac3ee5f121552c41",
        "bytes": 2_939_733,
        "rows": 160_000,
        "max_fitness": 8.762,
        "exact_zeros": 40_116,
        "viability_threshold": 0.1,
        "viable_pool": 11_522,
    },
}


class LandscapeError(Exception):
    """Raised when a file is not the landscape the constants were measured against."""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Landscape(object):
    """A full fitness table plus the viable subset an agent may propose from."""

    __slots__ = ("name", "path", "fitness", "pool", "threshold", "sha256", "n_rows")

    def __init__(self, name, path, fitness, threshold, digest, n_rows):
        self.name = name
        self.path = path
        self.fitness = fitness                 # dict[str, float], the full table
        self.threshold = threshold
        self.sha256 = digest
        self.n_rows = n_rows
        # Strict inequality: viable means fitness above the threshold.
        self.pool = frozenset(v for v, f in fitness.items() if f > threshold)

    @property
    def exact_zeros(self):
        return sum(1 for f in self.fitness.values() if f == 0.0)

    @property
    def max_fitness(self):
        return max(self.fitness.values())

    @property
    def min_fitness(self):
        return min(self.fitness.values())

    def __len__(self):
        return len(self.fitness)

    def __repr__(self):
        return "Landscape(%s, n=%d, pool=%d, thresh=%g)" % (
            self.name, len(self.fitness), len(self.pool), self.threshold)


def _parse(path):
    """Read `variant,fitness` rows into a dict. Raises on any malformed row instead of skipping it."""
    fitness = {}
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header != ["variant", "fitness"]:
            raise LandscapeError("%s: expected header ['variant','fitness'], got %r"
                                 % (os.path.basename(path), header))
        for lineno, row in enumerate(reader, start=2):
            if len(row) != 2:
                raise LandscapeError("%s line %d: expected 2 fields, got %d"
                                     % (os.path.basename(path), lineno, len(row)))
            variant, raw = row[0], row[1]
            if len(variant) != SITES or not set(variant) <= AA_SET:
                raise LandscapeError(
                    "%s line %d: %r is not %d characters over %s"
                    % (os.path.basename(path), lineno, variant, SITES, AA))
            if variant in fitness:
                raise LandscapeError("%s line %d: duplicate variant %r"
                                     % (os.path.basename(path), lineno, variant))
            try:
                fitness[variant] = float(raw)
            except ValueError:
                raise LandscapeError("%s line %d: fitness %r is not a number"
                                     % (os.path.basename(path), lineno, raw))
    return fitness


def load(name, data_dir=None, verify=True):
    """Load a landscape by name ('phoq' or 'gb1').

    `verify=True` refuses a file whose SHA256 does not match the expected one."""
    if name not in EXPECTED:
        raise LandscapeError("unknown landscape %r; known: %s"
                             % (name, ", ".join(sorted(EXPECTED))))
    spec = EXPECTED[name]
    path = os.path.join(data_dir or DATA_DIR, spec["file"])
    if not os.path.exists(path):
        raise LandscapeError("%s is missing. Run: python3 scripts/download_data.py" % path)
    digest = sha256(path)
    if verify and digest != spec["sha256"]:
        raise LandscapeError(
            "%s is not the file the constants were measured against.\n"
            "  expected sha256 %s\n  got      sha256 %s\n"
            "The mirror has changed. Do NOT proceed: re-derive the constants."
            % (path, spec["sha256"], digest))
    fitness = _parse(path)
    return Landscape(name, path, fitness, spec["viability_threshold"], digest, len(fitness))


def load_all(data_dir=None, verify=True):
    return {n: load(n, data_dir, verify) for n in sorted(EXPECTED)}
