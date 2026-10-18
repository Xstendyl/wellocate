#!/usr/bin/env python3
"""Write spec/PROMPT_SNAPSHOT.txt: a SHA256 for every rendered prompt the harness can produce.

Run it only when a prompt change is deliberate. The prompt contract test fails until the snapshot matches.
"""
import hashlib, io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_prompt_contract import rendered, SNAP  # noqa: E402

R = rendered()
lines = ["# SHA256 of every rendered prompt: rung|noise|kind. Regenerate with",
         "# scripts/snapshot_prompts.py and show the diff. %d prompts." % len(R)]
for k in sorted(R):
    lines.append("%s  %s|%s|%s" % (hashlib.sha256(R[k].encode()).hexdigest(), k[0], k[1], k[2]))
io.open(SNAP, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("wrote %s with %d prompt hashes" % (os.path.relpath(SNAP, ROOT), len(R)))
