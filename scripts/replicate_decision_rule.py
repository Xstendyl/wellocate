#!/usr/bin/env python3
"""Out-of-sample replication of the one confirmatory contrast that survived Holm correction.

DeepSeek V3.1, Mechanism against Decision-rule, on 120 unused seeds, through the current harness with the
follow-up runs' caps and settings; the pre-registration fixes the outcome, the exclusions and the reading rule.
Before launching it collects every campaign seed recorded in any results file, every range a run manifest
declares, and every integer seed base in the code (each taken to cover a million seeds), and refuses if the
planned range touches any of them.

Usage:
  python3 scripts/replicate_decision_rule.py                 # check the seeds, print the launch, spend nothing
  set -a; . ./.env; set +a; python3 scripts/replicate_decision_rule.py --run
"""
import glob, gzip, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = "replication_dsdr"
MODEL = "deepseek/deepseek-chat-v3.1"
CONDITIONS = ("Mechanism", "Decision-rule")
SEED0, N = 6_100_000, 120
BUDGET_USD = 4.0
SPAN = 1_000_000                     # how far a seed base written in code is assumed to reach
# The DeepSeek follow-up run's settings, read from results/grid_topup_deepseek_manifest.json, except seeds, N and budget.
TOPUP = dict(workers=3, max_tokens=6000, max_reasks=3, temperature=0.0, noise="multiplicative",
             credit_floor=50.0)
ORDER_SEED = 20260930


def seeds_in_results():
    """Every campaign seed any results file records, from campaign rows and from call rows."""
    out = set()
    for p in glob.glob(os.path.join(ROOT, "results", "**", "*.jsonl"), recursive=True):
        for line in open(p, errors="replace"):
            if '"seed"' in line or '"campaign_seed"' in line:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                for k in ("seed", "campaign_seed"):
                    if isinstance(r.get(k), int):
                        out.add(r[k])
    for p in glob.glob(os.path.join(ROOT, "results", "**", "*.jsonl.gz"), recursive=True):
        with gzip.open(p, "rt", errors="replace") as fh:
            for line in fh:
                m = re.search(r'"campaign_seed":\s*(\d+)', line)
                if m:
                    out.add(int(m.group(1)))
    return out


def ranges_in_manifests():
    """[seed0, seed0 + campaigns_per_cell) for every run manifest, including campaigns that never wrote."""
    out = []
    for p in glob.glob(os.path.join(ROOT, "results", "**", "*manifest*.json"), recursive=True):
        try:
            d = json.load(open(p))
        except ValueError:
            continue
        if isinstance(d, dict) and isinstance(d.get("seed0"), int) and isinstance(d.get("campaigns_per_cell"), int):
            out.append((d["seed0"], d["seed0"] + d["campaigns_per_cell"], os.path.relpath(p, ROOT)))
    return out


def bases_in_code():
    """Every integer of four or more digits on a line of tracked code that mentions a seed."""
    files = subprocess.run(["git", "ls-files", "scripts", "repdef", "tests", "independent_check"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    out = {(0, "sweep default seed0=0")}
    for f in files:
        if not f.endswith(".py") or f.endswith("replicate_decision_rule.py"):
            continue
        for i, line in enumerate(open(os.path.join(ROOT, f), errors="replace"), 1):
            if "seed" in line.lower():
                for m in re.finditer(r"(?<![\w.])(\d[\d_]{3,})(?![\w.])", line):
                    out.add((int(m.group(1).replace("_", "")), "%s:%d" % (f, i)))
    return sorted(out)


def check_seeds():
    planned = set(range(SEED0, SEED0 + N))
    used = seeds_in_results()
    hit = sorted(planned & used)
    if hit:
        raise SystemExit("REFUSED: planned seeds already used in results: %s" % hit[:5])
    for lo, hi, src in ranges_in_manifests():
        if lo < SEED0 + N and SEED0 < hi:
            raise SystemExit("REFUSED: planned seeds overlap %s's range [%d, %d)" % (src, lo, hi))
    for base, src in bases_in_code():
        if base < SEED0 + N and SEED0 < base + SPAN:
            raise SystemExit("REFUSED: planned seeds fall within %d of the seed base %d at %s"
                             % (SPAN, base, src))
    below = max((s for s in used if s < SEED0), default=None)
    above = min((s for s in used if s >= SEED0 + N), default=None)
    print("seeds %d to %d are new: %d recorded seeds checked (nearest %s below, %s above), %d manifest "
          "ranges, %d seed bases in code at a %d-seed reach"
          % (SEED0, SEED0 + N - 1, len(used), below, above, len(ranges_in_manifests()),
             len(bases_in_code()), SPAN))


def command():
    return [sys.executable, "-B", os.path.join(ROOT, "scripts", "grid.py"),
            "--campaigns", str(N), "--conditions", ",".join(CONDITIONS), "--models", MODEL,
            "--seed0", str(SEED0), "--tag", TAG, "--stage", "replication", "--budget-usd", str(BUDGET_USD),
            "--workers", str(TOPUP["workers"]), "--max-tokens", str(TOPUP["max_tokens"]),
            "--max-reasks", str(TOPUP["max_reasks"]), "--temperature", str(TOPUP["temperature"]),
            "--noise", TOPUP["noise"], "--credit-floor", str(TOPUP["credit_floor"]),
            "--shuffle", "--order-seed", str(ORDER_SEED)]


def main():
    check_seeds()
    cmd = command()
    print("launch: " + " ".join(os.path.relpath(c, ROOT) if c.startswith(ROOT) else c for c in cmd[1:]))
    if "--run" not in sys.argv:
        print("dry: nothing launched. Re-run with --run.")
        return 0
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
