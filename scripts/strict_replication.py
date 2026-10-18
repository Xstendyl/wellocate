#!/usr/bin/env python3
"""The stricter replication share, alongside the headline one, for the 15 cells of the main study.

  python3 scripts/strict_replication.py

The headline share counts an order for any variant ordered before; the stricter share counts only an order for a
variant that already has a successful reading. Both use the used slots as denominator. The per-slot history is
rebuilt from the archived prompts by scripts/post_repeat_replication.py.

The run refuses unless, on every campaign, the rebuilt charged slots equal the recorded slots_used and the rebuilt
headline numerator equals the recorded replication_count, and unless each cell's headline matches the published
analysis value.

Writes results/strict_replication.json.
"""
import collections, json, os, statistics as st, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import post_repeat_replication as PR                                  # noqa: E402
import analyse_grid as AG                                             # noqa: E402

TAGS = ("stage1", "topup_opus", "topup_gemini", "topup_deepseek")
COND = {v: k for k, v in PR.RUNG.items()}


def counts(hist):
    """(charged slots, headline numerator, strict numerator) over one campaign's history."""
    ordered, succeeded = set(), set()
    charged = loose = strict = 0
    for _rnd, seq, kind in hist:
        charged += 1
        if kind not in ("read", "failed"):
            continue                        # a lost slot or lost round: charged, nothing ordered
        if seq in ordered:
            loose += 1                      # campaign.py's replication_count, any earlier order
        if seq in succeeded:
            strict += 1                     # an earlier successful reading
        ordered.add(seq)
        if kind == "read":
            succeeded.add(seq)
    return charged, loose, strict


def main():
    viable = PR.viable_set()
    records = {}
    for t in TAGS:
        for l in open(os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % t)):
            if l.strip():
                c = json.loads(l)
                records[(c["model"], c["rung"], c["seed"])] = c
    strict_by, bad = {}, []
    for t in TAGS:
        byc = collections.defaultdict(list)
        for c in PR.calls_of(t):
            if c.get("kind") in ("round", "replacement", "nomination"):
                byc[(c["model"], c["rung"], c["campaign_seed"])].append(c)
        for key, cs in byc.items():
            if key not in records:
                continue
            cs.sort(key=lambda x: (x["round"], {"round": 0, "replacement": 1}.get(x["kind"], 2)))
            hist = PR.final_history(cs)
            if hist is None:
                hist, _left = PR.reconstruct(cs, key[2], viable)
            charged, loose, strict = counts(hist)
            rec = records[key]
            if charged != rec["slots_used"]:
                bad.append("%s: %d charged slots rebuilt, %d recorded" % (key, charged, rec["slots_used"]))
            if loose != rec["replication_count"]:
                bad.append("%s: headline numerator %d rebuilt, %d recorded" % (key, loose, rec["replication_count"]))
            strict_by[key] = strict / float(charged) if charged else None
    missing = [k for k in records if k not in strict_by]
    if bad or missing:
        print("REFUSED. The rebuilt histories do not match what the campaigns recorded:")
        for b in bad[:20]:
            print("  " + b)
        if missing:
            print("  %d campaign(s) have no rebuilt history, e.g. %s" % (len(missing), missing[:3]))
        return 1

    pub = {(x["condition"], x["model"]): x for x in
           json.load(open(os.path.join(ROOT, "results", "analysis_final", "grid", "summary.json")))["cells_detail"]}
    # Drop campaigns whose nomination did not parse, using analyse_grid's own list, as the published analysis does.
    fb = AG.fallback_seeds(list(TAGS))
    dropped = [k for k in records if (k[1], k[0], k[2]) in fb]
    cells = collections.defaultdict(list)
    for key, rec in records.items():
        if key in dropped:
            continue
        cells[(COND[key[1]], key[0].split("/")[-1])].append(key)
    out, gate3 = [], []
    for (cond, model), keys in sorted(cells.items()):
        headline = st.mean(records[k]["replication_fraction"] for k in keys)
        published = pub[(cond, model)]["replication"]["over slots used"]
        if abs(headline - published) > 1e-9:
            gate3.append("%s %s: %.6f recomputed, %.6f published" % (model, cond, headline, published))
        out.append(dict(condition=cond, model=model, n=len(keys), headline=headline,
                        strict=st.mean(strict_by[k] for k in keys)))
    if gate3:
        print("REFUSED. The campaign set differs from the published analysis:")
        for g in gate3:
            print("  " + g)
        return 1
    json.dump(dict(cells=out, campaigns=len(records)), open(os.path.join(ROOT, "results", "strict_replication.json"), "w"), indent=1)
    print("all three gates pass on %d campaigns\n" % len(records))
    print("  %-20s %-14s %5s %10s %10s %8s" % ("model", "condition", "n", "headline", "strict", "gap pp"))
    for r in out:
        print("  %-20s %-14s %5d %9.1f%% %9.1f%% %8.1f" % (r["model"], r["condition"], r["n"], 100*r["headline"],
                                                       100*r["strict"], 100*(r["headline"]-r["strict"])))
    print("\n  headline %.1f%% to %.1f%%   strict %.1f%% to %.1f%%" % (
        100*min(r["headline"] for r in out), 100*max(r["headline"] for r in out),
        100*min(r["strict"] for r in out), 100*max(r["strict"] for r in out)))
    print("  wrote results/strict_replication.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
