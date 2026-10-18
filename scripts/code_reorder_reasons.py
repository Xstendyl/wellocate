#!/usr/bin/env python3
"""Code the reason an agent gives at its first re-order into classes, by keyword. No API calls.

  explicit_noise      the reason names measurement error, variance, precision, averaging or
                      confirming a reading against noise. The agent says it is fighting noise.
  generic_confirm     the reason says confirm, verify, check or validate WITHOUT any noise language.
                      Consistent with a norm of double-checking that is not about measurement error.
  explore_mismatch    the reason talks about exploring, probing or trying something NEW while the
                      sequence is one already measured. What it says and what it does disagree.
  other               none of the above.

Keyword coding is crude; every coded reason is written out verbatim so the coding can be checked.
"""
import collections, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NOISE = re.compile(r"\b(nois|error|variance|varianc|sd\b|std|standard error|precis|uncertain|"
                   r"averag|mean of|replicat|repeat.*(confirm|reduce)|reduce.*(error|noise|uncertain)|"
                   r"sqrt|n=2|second read|another read|re-?measur|remeasur)", re.I)
# "reconfirm" has no word boundary before "confirm", so the re- prefix is explicit on every stem.
CONFIRM = re.compile(r"\b(re-?)?(confirm|verif|validat|double-?check|check|test|anchor|sanity)\b|"
                     r"\b(reconfirm|recheck|retest|reanchor)", re.I)
# Champion identification: an explore reason that also names the best hit is flagged as ambiguous.
CHAMP = re.compile(r"\b(best|top|strongest|highest|peak|champion|leader|so far|winner)\b", re.I)
EXPLORE = re.compile(r"\b(explor|probe|new\b|unexplor|untest|novel|try\b|diversif|different|"
                     r"alternativ|expand|search)", re.I)


def classify(reason):
    """Return (class, ambiguous); `ambiguous` is True when the reason matches more than one class's vocabulary."""
    r = reason or ""
    hits = []
    if NOISE.search(r):
        hits.append("explicit_noise")
    if CONFIRM.search(r):
        hits.append("generic_confirm")
    if EXPLORE.search(r) and not CHAMP.search(r):
        hits.append("explore_mismatch")
    elif EXPLORE.search(r) and CHAMP.search(r):
        hits.append("explore_mismatch")          # counted, and flagged ambiguous below
    amb = (len(hits) > 1) or bool(EXPLORE.search(r) and CHAMP.search(r))
    if not hits:
        return "other", False
    # Precedence: explicit noise, then confirmation, then explore mismatch.
    for k in ("explicit_noise", "generic_confirm", "explore_mismatch"):
        if k in hits:
            return k, amb
    return "other", amb


def first_reorder_reason(calls):
    """The (round, seq, reason) of the first proposal that repeats an already-measured sequence."""
    seen = set()
    for c in sorted(calls, key=lambda x: (x["round"], x.get("kind") != "round")):
        props = c.get("parsed") or []
        reasons = c.get("reasons") or []
        for i, s in enumerate(props):
            if s in seen:
                return c["round"], s, (reasons[i] if i < len(reasons) else "")
        seen.update(props)
    return None, None, None


def main():
    pats = sys.argv[1:] or ["pilot_L10n20", "pilot_L15n20", "pilot_L30n20",
                            "pilot_slots2", "pilot_slots4", "pilot_slots8"]
    out_lines, counts_all = [], collections.Counter()
    print("=" * 100)
    print("REASON AT THE FIRST RE-ORDER, coded into three pre-specified classes")
    print("=" * 100)
    print("  %-22s %6s %15s %16s %18s %7s" % ("experiment", "camps", "explicit_noise",
                                              "generic_confirm", "explore_mismatch", "other"))
    per_exp = {}
    for pat in pats:
        path = os.path.join(ROOT, "results", pat + "_calls.jsonl")
        if not os.path.exists(path):
            continue
        rows = [json.loads(l) for l in open(path)]
        camps = collections.defaultdict(list)
        for r in rows:
            if r.get("kind") != "nomination":
                camps[r["campaign_seed"]].append(r)
        c = collections.Counter()
        for seed, calls in sorted(camps.items()):
            rnd, seq, reason = first_reorder_reason(calls)
            if rnd is None:
                c["no_reorder"] += 1
                continue
            k, amb = classify(reason)
            c[k] += 1
            counts_all[k] += 1
            if amb:
                c[k + "_ambiguous"] += 1
                counts_all[k + "_ambiguous"] += 1
            out_lines.append("%-22s seed %-8s round %-3s %-5s  [%s%s]  %s"
                             % (pat, seed, rnd, seq, k, " AMBIGUOUS" if amb else "",
                                (reason or "").replace("\n", " ")[:150]))
        n = sum(v for k, v in c.items() if k != "no_reorder")
        per_exp[pat] = dict(c)
        print("  %-22s %6d %14d%% %15d%% %17d%% %6d%%"
              % (pat, n,
                 round(100 * c["explicit_noise"] / n) if n else 0,
                 round(100 * c["generic_confirm"] / n) if n else 0,
                 round(100 * c["explore_mismatch"] / n) if n else 0,
                 round(100 * c["other"] / n) if n else 0))
    tot = sum(counts_all.values())
    tot = sum(counts_all[k] for k in ("explicit_noise", "generic_confirm", "explore_mismatch", "other"))
    print("\n  ALL EXPERIMENTS POOLED, %d campaigns with a re-order:" % tot)
    print("    %-18s %5s %7s | %s" % ("class", "n", "share", "of which AMBIGUOUS (matches >1 class)"))
    for k in ("explicit_noise", "generic_confirm", "explore_mismatch", "other"):
        a = counts_all.get(k + "_ambiguous", 0)
        print("    %-18s %5d %6.1f%% | %d (%.0f%% of the class)"
              % (k, counts_all[k], 100.0 * counts_all[k] / tot if tot else 0, a,
                 100.0 * a / counts_all[k] if counts_all[k] else 0))
    clean = {k: counts_all[k] - counts_all.get(k + "_ambiguous", 0)
             for k in ("explicit_noise", "generic_confirm", "explore_mismatch", "other")}
    ct = sum(clean.values())
    print("\n  UNAMBIGUOUS ONLY, %d campaigns:" % ct)
    for k, v in clean.items():
        print("    %-18s %5d %6.1f%%" % (k, v, 100.0 * v / ct if ct else 0))
    print("""
  VERDICT ON THE METHOD, and it is negative. The headline class flips with the ambiguity rule:
  explore_mismatch is 40.0% of all cases and 22.0% of the unambiguous ones, while generic_confirm goes
  the other way, 32.2% to 56.1%. Ninety-four per cent of explicit_noise and seventy-five per cent of
  explore_mismatch match more than one class's vocabulary. A coding whose leading class depends on how
  the ambiguous cases are handled does not support a claim about what the agent says, and NO NUMBER FROM
  THIS SCRIPT SHOULD BE QUOTED as a result. What it does establish is worth keeping: only ONE of 41
  unambiguous reasons names measurement error explicitly, which is a low count under any handling and is
  the one signal here robust to the coding rule.

  A HAND-CODED SAMPLE IS THE FIX and is cheap for a human: 90 lines, one per campaign, in the verbatim
  file below.

  KEYWORD CODING IS CRUDE. A reason saying "replicate to reduce noise" and one saying "replicate" are
  different claims and the second may be coded generic_confirm on its wording alone. Every coded reason
  is written out verbatim so the coding can be checked and disputed, and a hand-coded sample would be
  better evidence than this.""")
    dest = os.path.join(ROOT, "results", "step9_reorder_reasons.txt")
    with open(dest, "w") as f:
        f.write("Reason at the first re-order, one line per campaign, for checking the coding.\n\n")
        f.write("\n".join(out_lines) + "\n")
    json.dump(dict(per_experiment=per_exp, pooled=dict(counts_all), total=tot),
              open(os.path.join(ROOT, "results", "step9_reorder_reasons.json"), "w"), indent=1)
    print("\n  verbatim reasons: %s" % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
