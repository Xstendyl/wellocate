#!/usr/bin/env python3
"""Restart-safe runner for the Wellocate scorecard and noise sweep. Scripted, no model calls.

Each chunk (one policy on one split at one noise preset, every episode, through the step API) is written to
results/wellocate_partial/<split>__<policy>__<noise>.jsonl through a temporary file and an atomic rename. Its
trailer gives the episode count, the sha256 of the row lines and the sha256 of the code its numbers depend on. On
start, every chunk with a matching trailer is skipped, so a rerun resumes where it stopped and a code change
recomputes what it touches. Noise keys are the presets (low, assay, high) and "cv0.3", "cv0.6"; a "_riskfree"
policy suffix runs the risk-free rule. When every chunk is complete, the build step writes
results/wellocate_scorecard.json and results/wellocate_noise_sweep.json.

Usage: python3 scripts/wellocate_chunks.py [--procs N] [--status] [--build-only]
"""
import argparse, glob, hashlib, json, os, sys, time
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
PARTIAL = os.path.join(ROOT, "results", "wellocate_partial")

SCORECARD_SPLITS = ["gb1:test", "phoq:test", "nk:test", "nk:test_ood_k2", "nk:test_ood_k3", "gb1:transfer_real",
                    "phoq:transfer_real", "nk:paper", "gb1:paper"]
SCORECARD_POLICIES = (["guessing_k%d" % k for k in range(5)] + ["informed_k%d" % k for k in range(5)]
                      + ["model_guided", "random", "confirmation_4"])
SWEEP_SPLITS = ["nk:paper", "gb1:paper", "phoq:paper"]
SWEEP_POLICIES = (["guessing_k%d" % k for k in range(5)] + ["confirmation_%d" % c for c in (4, 8, 12)]
                  + ["guessing_k%d_riskfree" % k for k in range(5)])
# The three presets, then a design sweep at CV 0.3 and 0.6 (Fig. 5), which is not a pre-registered test.
PRESETS = ("low", "assay", "high", "cv0.3", "cv0.6")


def noise_value(key):
    """A preset name passes through; "cv0.3" is the coefficient of variation 0.3."""
    return key if key in ("low", "assay", "high") else float(key[2:])


def chunks():
    want = [(s, p, "assay") for s in SCORECARD_SPLITS for p in SCORECARD_POLICIES]
    want += [(s, p, n) for s in SWEEP_SPLITS for n in PRESETS for p in SWEEP_POLICIES]
    return sorted(set(want), key=lambda c: (c[0], c[2], c[1]))


def code_sha256():
    files = sorted(glob.glob(os.path.join(ROOT, "wellocate", "*.py")) + glob.glob(os.path.join(ROOT, "repdef", "*.py"))
                   + [os.path.join(ROOT, "wellocate", "splits.json")]
                   + [os.path.join(ROOT, "scripts", f) for f in ("fair_reference_curve.py", "yardsticks_0am.py",
                                                                 "model_guided_0an4.py")])
    h = hashlib.sha256()
    for f in files:
        h.update(os.path.relpath(f, ROOT).encode())
        with open(f, "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()


def path_of(chunk):
    split, policy, noise = chunk
    return os.path.join(PARTIAL, "%s__%s__%s.jsonl" % (split.replace(":", "-"), policy, noise))


def factory(policy):
    """(policy factory, environment options). A "_riskfree" suffix runs the policy under the risk-free rule."""
    if policy.endswith("_riskfree"):
        return factory(policy[:-len("_riskfree")])[0], dict(riskfree_rejection=True)
    return _factory(policy), {}


def _factory(policy):
    from wellocate import baselines as B
    if policy == "model_guided":
        return B.model_guided(1, True)
    if policy == "random":
        return B.random()
    for prefix, make in (("guessing_k", B.guessing), ("informed_k", B.informed), ("confirmation_", B.confirmation)):
        if policy.startswith(prefix):
            return make(int(policy[len(prefix):]))
    raise ValueError("unknown policy %r" % policy)


def read(chunk, code=None, n=None):
    """The chunk's rows if its file is complete and verified, else None."""
    p = path_of(chunk)
    if not os.path.exists(p):
        return None
    try:
        with open(p) as f:
            lines = f.read().splitlines()
        trailer = json.loads(lines[-1])
        body = lines[:-1]
        ok = (trailer.get("complete") is True and trailer["n"] == len(body)
              and trailer["rows_sha256"] == hashlib.sha256("\n".join(body).encode()).hexdigest()
              and (code is None or trailer["code_sha256"] == code) and (n is None or trailer["n"] == n)
              and [trailer["split"], trailer["policy"], trailer["noise"]] == list(chunk))
        return [json.loads(l)["row"] for l in body] if ok else None
    except (ValueError, KeyError, IndexError):
        return None


def run_chunk(args):
    chunk, code = args
    from wellocate import scorecard as S, splits as SP
    split, policy, noise = chunk
    t0 = time.time()
    eps = SP.episodes(split)
    make, kw = factory(policy)
    rows = S.run(make, split, None, noise=noise_value(noise), **kw)
    body = [json.dumps(dict(i=i, instance=eps[i][0], seed=eps[i][1], row=r), sort_keys=True) for i, r in enumerate(rows)]
    trailer = dict(complete=True, split=split, policy=policy, noise=noise, n=len(body),
                   rows_sha256=hashlib.sha256("\n".join(body).encode()).hexdigest(), code_sha256=code,
                   seconds=round(time.time() - t0, 1))
    tmp = path_of(chunk) + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(body) + "\n" + json.dumps(trailer) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path_of(chunk))
    return chunk, trailer["seconds"]


def status(code):
    from wellocate import splits as SP
    allc = chunks()
    done = [c for c in allc if read(c, code, SP.load()["splits"][c[0]]["episodes"]) is not None]
    return allc, done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--build-only", action="store_true")
    a = ap.parse_args()
    os.makedirs(PARTIAL, exist_ok=True)
    for t in glob.glob(os.path.join(PARTIAL, "*.tmp")):
        os.remove(t)                                   # a chunk interrupted mid-write; it reruns below
    code = code_sha256()
    allc, done = status(code)
    print("chunks: %d of %d complete and verified (code %s)" % (len(done), len(allc), code[:12]), flush=True)
    if a.status:
        return 0
    todo = [c for c in allc if c not in set(done)]
    if todo and not a.build_only:
        t0 = time.time()
        with Pool(a.procs) as pool:
            for k, (chunk, secs) in enumerate(pool.imap_unordered(run_chunk, [(c, code) for c in todo]), 1):
                print("chunk %d of %d done (%d of %d overall): %s %s %s, %.0f s, %.0f s elapsed"
                      % (k, len(todo), len(done) + k, len(allc), chunk[0], chunk[1], chunk[2], secs, time.time() - t0),
                      flush=True)
        allc, done = status(code)
    if len(done) != len(allc):
        print("REFUSED to build: %d of %d chunks complete" % (len(done), len(allc)), flush=True)
        return 1
    import wellocate_scorecard as WS
    import wellocate_noise_sweep as WN
    WS.build(read)
    WN.build(read)
    print("built results/wellocate_scorecard.json and results/wellocate_noise_sweep.json from %d chunks" % len(allc),
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
