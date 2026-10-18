#!/usr/bin/env python3
"""Move every campaign touched by a transport error out of the live files, so resume reruns those seeds.

An HTTP 402 (exhausted balance) becomes a transport error, which campaign.py charges as a lost round, so the
agent appears to forfeit rounds it never saw. Any campaign with at least one errored call, or with no
successful measurement, is removed. Removed rows go to results/quarantine_credit_402/ and the SHA256 of each
original is recorded, so the live file plus the quarantine file reconstruct the original exactly.
"""
import collections, hashlib, json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QDIR = os.path.join(ROOT, "results", "quarantine_credit_402")
RUNG = {"Blind": "blind", "Quantitative": "informed", "Mechanism": "instructed",
        "Aggregated": "aggregated", "Decision-rule": "decision_rule"}
TAGS = ["topup_opus", "topup_deepseek", "topup_gemini", "panelc", "zeronoise"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def bad_call(r):
    """Any transport or HTTP failure. Not only 402, because the rule is about unmeasured calls."""
    return bool(r.get("error")) or r.get("parse_status") == "transport_error"


def unusable(c):
    """A campaign with no successful measurement is void even if nothing was logged against it."""
    return ((c.get("spend") or 0) == 0
            or (c.get("n_ok") or 0) == 0
            or c.get("nominated") in (None, "", "----"))


def main():
    apply_ = "--apply" in sys.argv
    os.makedirs(QDIR, exist_ok=True)
    report = {}
    print("=" * 104)
    print("QUARANTINE CREDIT-402 CAMPAIGNS   mode=%s" % ("APPLY" if apply_ else "DRY RUN"))
    print("=" * 104)
    print("  %-16s %7s %7s %8s %8s %8s %9s"
          % ("run", "before", "keep", "errored", "unusable", "move", "spend lost"))
    for tag in TAGS:
        cp = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
        lp = os.path.join(ROOT, "results", "grid_%s_calls.jsonl" % tag)
        if not os.path.exists(cp):
            continue
        contaminated = set()
        calls = []
        if os.path.exists(lp):
            with open(lp) as f:
                for l in f:
                    if not l.strip():
                        continue
                    r = json.loads(l)
                    calls.append((r, l))
                    if bad_call(r):
                        contaminated.add((r["rung"], r["campaign_seed"]))
        camps = []
        with open(cp) as f:
            for l in f:
                if l.strip():
                    camps.append((json.loads(l), l))
        keep, move = [], []
        n_err = n_unus = 0
        for c, l in camps:
            k = (RUNG.get(c["condition"], c["condition"]), c["seed"])
            e = k in contaminated
            u = unusable(c)
            n_err += int(e)
            n_unus += int(u)
            (move if (e or u) else keep).append((c, l, k))
        lost = sum(c.get("spend") or 0 for c, _l, _k in move)
        print("  %-16s %7d %7d %8d %8d %8d %9.2f"
              % (tag, len(camps), len(keep), n_err, n_unus, len(move), lost))
        moved_keys = {k for _c, _l, k in move}
        report[tag] = dict(before=len(camps), keep=len(keep), errored=n_err, unusable=n_unus,
                           moved=len(move), spend_lost=lost,
                           campaigns_sha256_before=sha(cp),
                           calls_sha256_before=sha(lp) if os.path.exists(lp) else None)
        if not apply_:
            continue
        with open(os.path.join(QDIR, "grid_%s_campaigns.jsonl" % tag), "a") as f:
            for _c, l, _k in move:
                f.write(l if l.endswith("\n") else l + "\n")
        if os.path.exists(lp):
            with open(os.path.join(QDIR, "grid_%s_calls.jsonl" % tag), "a") as f:
                for r, l in calls:
                    if (r["rung"], r["campaign_seed"]) in moved_keys:
                        f.write(l if l.endswith("\n") else l + "\n")
        # Rewrite the live files. Written to a temp path and renamed, so an interrupted rewrite cannot
        # leave a half file where the resume logic will read it.
        tmp = cp + ".tmp"
        with open(tmp, "w") as f:
            for _c, l, _k in keep:
                f.write(l if l.endswith("\n") else l + "\n")
        os.replace(tmp, cp)
        if os.path.exists(lp):
            tmp = lp + ".tmp"
            with open(tmp, "w") as f:
                for r, l in calls:
                    if (r["rung"], r["campaign_seed"]) not in moved_keys:
                        f.write(l if l.endswith("\n") else l + "\n")
            os.replace(tmp, lp)

    if not apply_:
        print("\n  DRY RUN. Re-run with --apply to move them.")
        return 0

    print("\n  POSTCONDITION CHECK on the live files")
    print("  %-16s %7s %9s %9s  %s" % ("run", "campaigns", "errored", "zero-spend", "verdict"))
    ok = True
    for tag in TAGS:
        cp = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % tag)
        lp = os.path.join(ROOT, "results", "grid_%s_calls.jsonl" % tag)
        if not os.path.exists(cp):
            continue
        contaminated = set()
        if os.path.exists(lp):
            with open(lp) as f:
                for l in f:
                    if l.strip():
                        r = json.loads(l)
                        if bad_call(r):
                            contaminated.add((r["rung"], r["campaign_seed"]))
        camps = [json.loads(l) for l in open(cp) if l.strip()]
        e = sum(1 for c in camps if (RUNG.get(c["condition"], c["condition"]), c["seed"]) in contaminated)
        z = sum(1 for c in camps if unusable(c))
        good = (e == 0 and z == 0)
        ok = ok and good
        print("  %-16s %7d %9d %9d  %s" % (tag, len(camps), e, z, "CLEAN" if good else "STILL DIRTY"))
        report[tag]["after"] = dict(campaigns=len(camps), errored=e, unusable=z,
                                    campaigns_sha256_after=sha(cp),
                                    calls_sha256_after=sha(lp) if os.path.exists(lp) else None)
    with open(os.path.join(QDIR, "MANIFEST.json"), "w") as f:
        json.dump(dict(reason="OpenRouter credits exhausted from about 12:29 on 2026-09-28; HTTP 402 "
                              "was charged to the agent as ROUND_LOST",
                       rule="any campaign with at least one errored call, or with no successful "
                            "measurement, whether or not an error was logged",
                       runs=report), f, indent=1)
    print("\n  wrote %s" % os.path.relpath(os.path.join(QDIR, "MANIFEST.json"), ROOT))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
