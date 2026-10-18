#!/usr/bin/env python3
"""Fetch the two fitness landscapes from a pinned URL; the loader checks their SHA256.

The experiment's constants (viable pool sizes, sigma units, noise ratios) were measured on these files.
Other mirrors, such as CLADE's measured-variants-only files, have a different row count and will fail the tests.

Usage:  python3 scripts/download_data.py [--force]
"""

import argparse
import hashlib
import os
import sys
import urllib.request

BASE = ("https://huggingface.co/datasets/soldatmat/"
        "CZAI_Summer_School-MLDE_landscapes/resolve/main/")

# Expected byte counts; a mismatch means the mirror changed, so the download stops.
FILES = {
    "phoq.csv": ("PhoQ_fitness_full.csv", 1_857_322),
    "gb1.csv":  ("GB1_fitness_full.csv",  2_939_733),
}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(local, remote, force=False):
    dest = os.path.join(DATA_DIR, local)
    if os.path.exists(dest) and not force:
        print("  %-10s exists, skipping (use --force to refetch)" % local)
        return dest
    url = BASE + remote
    print("  %-10s <- %s" % (local, url))
    req = urllib.request.Request(url, headers={"User-Agent": "repdef/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        body = r.read()
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, dest)          # never leave a half file where the loader can read it
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="refetch even if present")
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    print("Downloading landscapes into %s" % DATA_DIR)
    bad = []
    for local, (remote, want_bytes) in FILES.items():
        path = fetch(local, remote, args.force)
        got = os.path.getsize(path)
        flag = "OK" if got == want_bytes else "** MISMATCH **"
        print("     %-10s %10d bytes (expected %10d)  %s" % (local, got, want_bytes, flag))
        print("     sha256 %s" % sha256(path))
        if got != want_bytes:
            bad.append((local, got, want_bytes))

    if bad:
        print("\nSTOP. The mirror has changed since 2026-09-26:")
        for local, got, want in bad:
            print("  %s: %d bytes, expected %d" % (local, got, want))
        print("Every measured constant was derived against the expected files. Do not")
        print("proceed: re-derive the constants against what is actually available.")
        return 1
    print("\nBoth files match the byte counts recorded on 2026-09-26.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
