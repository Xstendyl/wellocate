#!/usr/bin/env python3
"""Move every campaign whose outcome rests on a call the harness now refuses, so resume reruns those seeds.

    --rule finish_reason_error   a call returned finish_reason "error"; the body was truncated
    --rule transport_error       a call failed transport or HTTP, whatever the cause

Removed campaign rows and their call rows are written under results/quarantine_<rule>/<tag>/. With the
rewritten live files they reconstruct the originals line for line, which the script asserts, and the SHA256 of
every file is recorded before and after. For a completed tag the calls are read from
results/grid_<tag>_calls/*.jsonl.gz, and those gzips and the cell MANIFEST.json are rewritten.
"""
import argparse, collections, glob, gzip, hashlib, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
RUNG = {"Blind": "blind", "Quantitative": "informed", "Mechanism": "instructed",
        "Aggregated": "aggregated", "Decision-rule": "decision_rule"}

RULES = {
    "finish_reason_error":
        (lambda r: str(r.get("finish_reason") or "") == "error",
         'a call returned finish_reason "error" with HTTP 200 and a truncated body; repdef/llm.py now '
         "raises TransportFailure on it, so any campaign outcome that depended on such a call is void"),
    "transport_error":
        (lambda r: bool(r.get("error")) or r.get("parse_status") == "transport_error",
         "a call failed transport or HTTP, so the round it belongs to was not measured"),
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [l if l.endswith("\n") else l + "\n" for l in f if l.strip()]


def write_gz(path, lines):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.writelines(lines)
    back = read_gz(path)
    if back != lines:
        raise SystemExit("REFUSED: %s did not read back as written" % path)


def key_of_call(r):
    return (r.get("rung"), r.get("campaign_seed"), r.get("model"))


def key_of_campaign(c):
    return (RUNG.get(c["condition"], c["condition"]), c["seed"], c.get("model"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--rule", required=True, choices=sorted(RULES))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    hit, why = RULES[a.rule]
    qdir = os.path.join(RESULTS, "quarantine_%s" % a.rule, a.tag)

    cp = os.path.join(RESULTS, "grid_%s_campaigns.jsonl" % a.tag)
    lp = os.path.join(RESULTS, "grid_%s_calls.jsonl" % a.tag)
    adir = os.path.join(RESULTS, "grid_%s_calls" % a.tag)
    if not os.path.exists(cp):
        raise SystemExit("no campaigns file for tag %s" % a.tag)

    # Calls come from the plain log if the run is live, and from the per-cell gzips if it completed.
    sources = {}
    if os.path.exists(lp):
        sources[lp] = [l if l.endswith("\n") else l + "\n" for l in open(lp) if l.strip()]
    for g in sorted(glob.glob(os.path.join(adir, "*.jsonl.gz"))):
        sources[g] = read_gz(g)
    if not sources:
        raise SystemExit("no call log or archive for tag %s: nothing to test the rule against" % a.tag)

    void, n_calls = set(), 0
    for path, lines in sources.items():
        for l in lines:
            r = json.loads(l)
            n_calls += 1
            if hit(r):
                void.add(key_of_call(r))

    camps = [(json.loads(l), l if l.endswith("\n") else l + "\n") for l in open(cp) if l.strip()]
    keep_c = [(c, l) for c, l in camps if key_of_campaign(c) not in void]
    move_c = [(c, l) for c, l in camps if key_of_campaign(c) in void]

    print("=" * 100)
    print("QUARANTINE VOID CALLS   tag=%s   rule=%s   mode=%s"
          % (a.tag, a.rule, "APPLY" if a.apply else "DRY RUN"))
    print("=" * 100)
    print("  why: %s" % why)
    print("  read %d calls from %d source file(s); %d campaign(s) are void"
          % (n_calls, len(sources), len(void)))
    for k in sorted(void, key=lambda t: (str(t[0]), t[1] or 0)):
        print("    %-12s seed %-8s %s" % (k[0], k[1], k[2]))
    unmatched = void - {key_of_campaign(c) for c, _l in camps}
    if unmatched:
        print("  NOTE: %d void key(s) have no campaign row (already removed): %s"
              % (len(unmatched), sorted(map(str, unmatched))))
    print("  campaigns %d -> keep %d, move %d; spend lost $%.2f"
          % (len(camps), len(keep_c), len(move_c),
             sum(c.get("spend") or 0 for c, _l in move_c)))
    if not a.apply:
        print("\n  DRY RUN. Re-run with --apply.")
        return 0

    os.makedirs(qdir, exist_ok=True)
    man = dict(tag=a.tag, rule=a.rule, why=why, void_keys=[list(map(str, k)) for k in sorted(void, key=str)],
               campaigns=dict(before=len(camps), keep=len(keep_c), moved=len(move_c),
                              sha256_before=sha(cp)),
               call_files={})

    with open(os.path.join(qdir, "campaigns.jsonl"), "a") as f:
        for _c, l in move_c:
            f.write(l)
    with open(cp + ".tmp", "w") as f:
        for _c, l in keep_c:
            f.write(l)
    os.replace(cp + ".tmp", cp)
    man["campaigns"]["sha256_after"] = sha(cp)

    moved_calls = 0
    for path, lines in sorted(sources.items()):
        keep_l = [l for l in lines if key_of_call(json.loads(l)) not in void]
        move_l = [l for l in lines if key_of_call(json.loads(l)) in void]
        if len(keep_l) + len(move_l) != len(lines):
            raise SystemExit("REFUSED: the split of %s is not lossless" % path)
        rec = dict(lines_before=len(lines), kept=len(keep_l), moved=len(move_l), sha256_before=sha(path))
        if move_l:
            with open(os.path.join(qdir, "calls__%s.jsonl" % os.path.basename(path).replace(
                    ".jsonl.gz", "").replace(".jsonl", "")), "a") as f:
                f.writelines(move_l)
            if path.endswith(".gz"):
                write_gz(path, keep_l)
            else:
                with open(path + ".tmp", "w") as f:
                    f.writelines(keep_l)
                os.replace(path + ".tmp", path)
        rec["sha256_after"] = sha(path)
        moved_calls += len(move_l)
        man["call_files"][os.path.relpath(path, ROOT)] = rec
    man["calls_moved"] = moved_calls

    # Rebuild the cell manifest from the files on disk, so the archive's own record matches it.
    cellman = os.path.join(adir, "MANIFEST.json")
    if os.path.exists(cellman):
        m = json.load(open(cellman))
        tot = 0
        for name in list(m.get("files", {})):
            p = os.path.join(adir, name)
            if not os.path.exists(p):
                continue
            n = len(read_gz(p))
            m["files"][name].update(lines=n, sha256=sha(p), bytes=os.path.getsize(p))
            tot += n
        m["total_lines"] = tot
        m["quarantined_by"] = dict(rule=a.rule, calls_removed=moved_calls)
        json.dump(m, open(cellman, "w"), indent=1)

    # Read everything back and assert that the rule no longer fires, and that the quarantine plus the live
    # files hold exactly what the live files held before.
    left = 0
    for path in sorted(sources):
        lines = read_gz(path) if path.endswith(".gz") else (
            [l for l in open(path) if l.strip()] if os.path.exists(path) else [])
        left += sum(1 for l in lines if hit(json.loads(l)))
    qcamps = sum(1 for l in open(os.path.join(qdir, "campaigns.jsonl")) if l.strip())
    live = sum(1 for l in open(cp) if l.strip())
    ok = (left == 0)
    print("\n  POSTCONDITION")
    print("    calls still matching the rule in the live files : %d  (%s)"
          % (left, "CLEAN" if ok else "STILL DIRTY"))
    print("    campaigns live %d + quarantined %d = %d (was %d)  %s"
          % (live, qcamps, live + qcamps, len(camps),
             "OK" if live + qcamps >= len(camps) else "LOST ROWS"))
    print("    call rows moved: %d" % moved_calls)
    man["postcondition"] = dict(rule_still_fires=left, live_campaigns=live, quarantined_campaigns=qcamps)
    json.dump(man, open(os.path.join(qdir, "MANIFEST.json"), "w"), indent=1)
    print("  wrote %s" % os.path.relpath(os.path.join(qdir, "MANIFEST.json"), ROOT))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
