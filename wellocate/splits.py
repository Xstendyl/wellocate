"""Frozen splits: which landscapes and which campaign seeds each split may use.

A split is a family and a name, written "gb1:test". It lists landscape instances and a range of campaign seeds.
Episode i of a split runs on instance i mod (number of instances) with campaign seed start + i, so every
instance is visited in turn and every episode has its own seed. The campaign seed keys the noise and the
failures, so disjoint seed ranges give disjoint draws.

  nk     train, validation and test use disjoint NK seeds at K = 1; test_ood_k2 and test_ood_k3 hold
         rougher landscapes out; paper is the paper's grid (K = 1, seed 1) on the references' 1,500 seeds.
  gb1    train, validation and test use disjoint scramble seeds; transfer_real holds the real amino-acid
  phoq   names out; paper is the paper's scramble on the references' seeds.
A scramble changes only the names, so a bio test split tests unseen names of the same protein. Training on
one protein and testing on the other is the cross-protein test.

Disjointness is checked across every split except "paper", whose seeds are the published ones by design.
The manifest is wellocate/splits.json; its sha256 is in wellocate/splits.sha256 and is checked on load.
Each held-out instance also carries the sha256 of its built landscape (landscapes.content_sha256), which
`python3 -m wellocate.splits --verify` rebuilds and compares. All splits are public. A hidden test server
is future work.

Usage: python3 -m wellocate.splits --verify          (rebuild every held-out landscape and compare its hash)
       python3 -m wellocate.splits --build           (write the manifest; only when changing the splits)
"""
import collections
import hashlib
import json
import os
import sys

from wellocate import landscapes as LS

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "splits.json")
DIGEST = os.path.join(HERE, "splits.sha256")
PAPER_SEED0, PAPER_N = 8_200_000, 1500


def _design():
    """The split design. Only --build reads this; everything else reads the frozen manifest."""
    d = collections.OrderedDict()
    d["nk"] = collections.OrderedDict([
        ("train", (["nk/K1/seed%d" % s for s in range(100_000, 100_400)], 100_000_000, 100_000)),
        ("validation", (["nk/K1/seed%d" % s for s in range(200_000, 200_010)], 200_000_000, 1500)),
        ("test", (["nk/K1/seed%d" % s for s in range(300_000, 300_020)], 300_000_000, 1500)),
        ("test_ood_k2", (["nk/K2/seed%d" % s for s in range(400_000, 400_020)], 400_000_000, 1500)),
        ("test_ood_k3", (["nk/K3/seed%d" % s for s in range(410_000, 410_020)], 410_000_000, 1500)),
        ("paper", (["nk/K1/seed1"], PAPER_SEED0, PAPER_N)),
    ])
    for j, (fam, paper_scramble) in enumerate((("gb1", 20261003), ("phoq", 20261004))):
        o = 10_000_000 * (j + 1)
        d[fam] = collections.OrderedDict([
            ("train", (["%s/scramble:%d" % (fam, s) for s in range(1_000_000 + 100_000 * j,
                                                                    1_000_400 + 100_000 * j)], 100_000_000 + o, 100_000)),
            ("validation", (["%s/scramble:%d" % (fam, s) for s in range(2_000_000 + 100_000 * j,
                                                                         2_000_010 + 100_000 * j)], 200_000_000 + o, 1500)),
            ("test", (["%s/scramble:%d" % (fam, s) for s in range(3_000_000 + 100_000 * j,
                                                                   3_000_020 + 100_000 * j)], 300_000_000 + o, 1500)),
            ("transfer_real", (["%s/real" % fam], 500_000_000 + o, 1500)),
            ("paper", (["%s/scramble:%d" % (fam, paper_scramble)], PAPER_SEED0, PAPER_N)),
        ])
    return d


def build():
    splits = collections.OrderedDict()
    for fam, ss in _design().items():
        for name, (insts, seed0, n) in ss.items():
            entry = collections.OrderedDict(family=fam, track=LS.FAMILY_TRACK[fam], instances=insts,
                                            campaign_seed_start=seed0, episodes=n)
            if name != "train":
                entry["instance_sha256"] = {i: LS.content_sha256(LS.instance(i)) for i in insts}
            splits["%s:%s" % (fam, name)] = entry
            print("built %s:%s, %d instance(s)" % (fam, name, len(insts)), flush=True)
    doc = collections.OrderedDict(
        version=1, note=("Episode i runs on instances[i % len(instances)] with campaign seed "
                         "campaign_seed_start + i. Built by python3 -m wellocate.splits --build."),
        splits=splits)
    problems = check_disjoint(doc)
    if problems:
        raise SystemExit("REFUSED: splits overlap:\n  " + "\n  ".join(problems))
    text = json.dumps(doc, indent=1) + "\n"
    open(MANIFEST, "w").write(text)
    open(DIGEST, "w").write(hashlib.sha256(text.encode()).hexdigest() + "  splits.json\n")


def check_disjoint(doc):
    out, seen_inst, seen_seed = [], {}, []
    for sid, e in doc["splits"].items():
        if sid.endswith(":paper"):
            continue
        for i in e["instances"]:
            if i in seen_inst:
                out.append("instance %s is in %s and %s" % (i, seen_inst[i], sid))
            seen_inst[i] = sid
        lo, hi = e["campaign_seed_start"], e["campaign_seed_start"] + e["episodes"]
        for olo, ohi, osid in seen_seed:
            if lo < ohi and olo < hi:
                out.append("campaign seeds of %s and %s overlap" % (sid, osid))
        seen_seed.append((lo, hi, sid))
    paper = {i for sid, e in doc["splits"].items() if sid.endswith(":paper") for i in e["instances"]}
    for i in paper & set(seen_inst):
        out.append("the paper's instance %s is also in %s" % (i, seen_inst[i]))
    for lo, hi, sid in seen_seed:
        if lo < PAPER_SEED0 + PAPER_N and PAPER_SEED0 < hi:
            out.append("campaign seeds of %s overlap the paper's" % sid)
    return out


def load():
    with open(MANIFEST) as f:
        text = f.read()
    with open(DIGEST) as f:
        want = f.read().split()[0]
    got = hashlib.sha256(text.encode()).hexdigest()
    if got != want:
        raise RuntimeError("wellocate/splits.json does not match its frozen sha256 (%s, expected %s)" % (got, want))
    return json.loads(text, object_pairs_hook=collections.OrderedDict)


def names():
    return list(load()["splits"])


def episodes(split, n=None):
    """[(instance name, campaign seed)] for the first n episodes of a split (all of them when n is None)."""
    e = load()["splits"].get(split)
    if e is None:
        raise ValueError("unknown split %r; known: %s" % (split, ", ".join(names())))
    n = e["episodes"] if n is None else int(n)
    if n > e["episodes"]:
        raise ValueError("split %s has %d episodes, %d asked for" % (split, e["episodes"], n))
    k = len(e["instances"])
    return [(e["instances"][i % k], e["campaign_seed_start"] + i) for i in range(n)]


def verify(only_first=False):
    doc, bad = load(), []
    for sid, e in doc["splits"].items():
        for i, h in list(e.get("instance_sha256", {}).items())[:1 if only_first else None]:
            if LS.content_sha256(LS.instance(i)) != h:
                bad.append("%s: %s rebuilt to a different landscape" % (sid, i))
    return check_disjoint(doc) + bad


if __name__ == "__main__":
    if "--build" in sys.argv:
        build()
    elif "--verify" in sys.argv:
        b = verify()
        print("splits: %s" % ("every held-out landscape rebuilds to its frozen hash; no overlap" if not b
                              else "%d problem(s)\n  " % len(b) + "\n  ".join(b)))
        sys.exit(1 if b else 0)
