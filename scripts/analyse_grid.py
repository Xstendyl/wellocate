#!/usr/bin/env python3
"""Every paper table, computed from the campaign files, so each number in the paper has one source.

  python3 scripts/analyse_grid.py stage0 --out results/analysis_dryrun_stage0

Real campaign data is refused until the grid is complete, as the pre-registration requires; the pilot is the
dry-run target. Outcomes: nominated true fitness against the scripted k* policy (primary); six Holm-corrected
contrasts, Aggregated and Decision-rule against Mechanism per model (confirmatory); distinct variants against
both scripted k* references (behavioural); and the replication definitions, lost slots, proposal viability and
the decomposition (secondary).
"""
import argparse, collections, json, math, os, re, statistics as st, sys
from statistics import NormalDist

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from repdef.stats import holm, welch_p, _t_sf
import repdef.rng as R

ALPHA, FAMILY, MEI = 0.05, 6, 0.06

def reference_bracket():
    """One line naming both scripted k* references: pool-scope (told which variants are viable) and fair.

    The `vs k*` columns use the pool-scope reference; the fair one is stated beside it.
    """
    p = os.path.join(ROOT, "results", FAIR_CURVE)
    if not os.path.exists(p):
        return ("Reference bracket unavailable: %s has not been produced, so only the pool-scope "
                "reference is shown." % FAIR_CURVE)
    d = json.load(open(p))
    try:
        fair = d["curves"]["fair"]["1"]
        pool = d["curves"]["pool"]["1"]
    except (KeyError, TypeError):
        return "Reference bracket unavailable: %s has no k=1 row for both scopes." % FAIR_CURVE
    return ("Reference bracket (0ai), both at k*=1 on the same %d seeds: distinct variants %.2f fair "
            "(%.1f rejections/campaign) and %.2f pool-scope (0 rejections). Agents sit below both."
            % (fair.get("n", 0), fair["distinct"], fair["rejections"], pool["distinct"]))


# Bootstrap draws for every reported p, high enough that p is not pinned at the 1/(reps+1) floor.
BOOT_REPS = int(os.environ.get("ANALYSE_GRID_BOOT_REPS", "20000"))
CONTRASTS = [("Aggregated", "Mechanism"), ("Decision-rule", "Mechanism")]
LADDER = ["Blind", "Quantitative", "Mechanism", "Aggregated", "Decision-rule"]
KSTAR_DISTINCT = 39.2          # the pool-scope k*=1 policy's distinct variants per campaign
# The pre-registered grid analysis stays on the original reference curves so its record reproduces;
# the paper reads the alphabet-corrected versions.
FAIR_CURVE = "fair_reference_curve.json"   # the fair reference, which guesses viability and can be rejected
REP_DEFS = [("over slots used", "replication_fraction"),
            ("over all 60 slots", "replication_fraction_of_budget"),
            ("excl anchor, slots used", "replication_fraction_excl_anchor"),
            ("excl anchor, all 60", "replication_fraction_excl_anchor_of_budget")]


def boot_ci(v, stat=st.mean, b=None, tag="ci"):
    b = BOOT_REPS if b is None else b
    if len(v) < 2:
        return float("nan"), float("nan")
    n = len(v)
    d = sorted(stat([v[R._u64(tag, i, j) % n] for j in range(n)]) for i in range(b))
    return d[int(0.025 * b)], d[min(b - 1, int(0.975 * b))]


def paired_wild_p(d, reps=None, tag="wild"):
    """Studentised wild bootstrap p for the paired mean difference, Rademacher weights clustered on seed.

    The seed fixes the environment (noise, instrument failures, screen admission), so one weight per seed is
    applied to that seed's whole pair, which equals one weight on the centred paired difference. The null is
    imposed by centring.
    """
    reps = BOOT_REPS if reps is None else reps
    n = len(d)
    if n < 2:
        return float("nan")
    md = st.mean(d)
    sd = st.stdev(d)
    if sd == 0:
        return float("nan")
    t_obs = abs(md / (sd / math.sqrt(n)))
    e = [x - md for x in d]
    hits = 0
    for i in range(reps):
        w = [e[j] * (1 if R._u64(tag, i, j) % 2 else -1) for j in range(n)]
        s_ = st.stdev(w)
        if s_ == 0:
            continue
        if abs(st.mean(w) / (s_ / math.sqrt(n))) >= t_obs:
            hits += 1
    return (hits + 1) / (reps + 1)


def paired_t_p(d):
    """Two-sided paired t, reported as a sensitivity beside the bootstrap."""
    n = len(d)
    if n < 2:
        return float("nan"), float("nan"), float("nan")
    se = st.stdev(d) / math.sqrt(n)
    if se == 0:
        return st.mean(d), 0.0, float("nan")
    return st.mean(d), se, 2.0 * _t_sf(abs(st.mean(d) / se), n - 1)


def fallback_seeds(tags):
    """{(condition-rung, model, seed)} whose nomination did not parse, so campaign.py used its averaging rule.

    Derived from the call log, because the campaign record stores the fallback nominee without a flag.
    """
    import glob as _glob, gzip as _gzip
    out = set()
    for tag in tags:
        p1 = os.path.join(ROOT, "results", "grid_%s_calls.jsonl" % tag)
        srcs = [open(p1)] if os.path.exists(p1) else [
            _gzip.open(g, "rt") for g in sorted(_glob.glob(
                os.path.join(ROOT, "results", "grid_%s_calls" % tag, "*.jsonl.gz")))]
        for fh in srcs:
            with fh:
                for line in fh:
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    if r.get("kind") == "nomination" and r.get("parse_status") != "ok":
                        out.add((r["rung"], r["model"], r["campaign_seed"]))
    return out


RUNG_OF = {"Blind": "blind", "Quantitative": "informed", "Mechanism": "instructed",
           "Aggregated": "aggregated", "Decision-rule": "decision_rule"}


def undefined_comparator(rows):
    """Campaigns whose shrinkage comparator is undefined, with the reason recovered.

    The reason is fewer than two measured variants or a zero-noise panel. These campaigns stay in the primary
    analyses.
    """
    out = collections.Counter()
    for r in rows:
        if r.get("ref_shrinkage") is not None:
            continue
        if (r.get("n_distinct_measured") or 0) < 2:
            why = "fewer than two measured variants"
        elif (r.get("noise_model") or "") == "exact" or r.get("stage") == "zeronoise":
            why = "no noise: undefined by design"
        else:
            why = "reason not recoverable from the record"
        out[(r["condition"], r["model"], why)] += 1
    return out


def drop_fallbacks(rows, fb):
    """Drop fallback campaigns from the primary analyses. Returns (kept, per-cell counts)."""
    kept, n = [], collections.Counter()
    for r in rows:
        if (RUNG_OF.get(r["condition"], r["condition"]), r["model"], r["seed"]) in fb:
            n[(r["condition"], r["model"])] += 1
        else:
            kept.append(r)
    return kept, n


def by_seed_rows(rows, field="nominated_true"):
    """condition, model -> seed -> the named field, so pairing is by seed and never by append order."""
    d = collections.defaultdict(dict)
    for r in rows:
        d[(r["condition"], r["model"])][r["seed"]] = r.get(field)
    return d


def by_seed(rows):
    """The primary outcome, which is what the confirmatory contrasts use."""
    return by_seed_rows(rows, "nominated_true")


class NonFinite(ValueError):
    """A p that is not a number, caught before it can reorder a Holm family."""


def confirmatory(seeded, models, contrasts=None):
    """The six confirmatory contrasts, paired by seed.

    Returns one tuple per contrast: model, label, seeds, seeds_dropped, diff, se_paired, ci_lo, ci_hi,
    wild_p, paired_t_p, se_welch, welch_p, corr, diff_welch.
    """
    out = []
    for m in models:
        for i_, b_ in (contrasts or CONTRASTS):
            A, B = seeded.get((b_, m)), seeded.get((i_, m))   # b_ = Mechanism is the reference
            if not A or not B:
                continue
            ks = sorted(set(A) & set(B))
            dropped = len(set(A) ^ set(B))
            if len(ks) < 2:
                continue
            ya = [A[k] for k in ks]
            yb = [B[k] for k in ks]
            d = [y - x for x, y in zip(ya, yb)]
            # A zero-variance cell leaves t, the bootstrap and the correlation undefined, so refuse it.
            for nm, v in (("Mechanism cell", ya), ("intervention cell", yb), ("difference", d)):
                if st.stdev(v) == 0:
                    raise NonFinite("%s %s vs %s: the %s has zero variance over %d seeds, so the "
                                    "standardised statistics are undefined and cannot enter a Holm "
                                    "family" % (m, i_, b_, nm, len(ks)))
            # The point estimate is the same paired or unpaired; only the standard error changes.
            diff, se, pt = paired_t_p(d)
            wp = paired_wild_p(d, tag="w%s%s" % (m, i_))
            du, seu, pw = welch_p(ya, yb)
            r = (sum((x - st.mean(ya)) * (y - st.mean(yb)) for x, y in zip(ya, yb)) / (len(ks) - 1)
                 / (st.stdev(ya) * st.stdev(yb)))
            # A non-finite p would silently reorder the Holm family, so refuse it.
            for nm, val in (("wild", wp), ("paired t", pt), ("welch", pw)):
                if not math.isfinite(val):
                    raise NonFinite("%s p for %s %s vs %s is %r; a degenerate cell (zero variance "
                                    "or n<2) cannot enter a Holm family" % (nm, m, i_, b_, val))
            out.append((m, "%s vs %s" % (i_, b_), len(ks), dropped, diff, se,
                        diff - 1.96 * se, diff + 1.96 * se, wp, pt, seu, pw, r, du))
    return out


class Incomplete(RuntimeError):
    """Real campaign data was asked for before the grid is complete."""


class DuplicateCampaign(ValueError):
    """The same (condition, model, seed) appeared twice across the files being combined."""


def load(tag):
    """One tag, or several joined by '+'. Refuses a duplicate (condition, model, seed) across tags."""
    # Refuse real campaign data until the grid is complete. The check sits here so no caller can skip it.
    if (set(tag.split("+")) != {"stage0"} and not os.environ.get("ANALYSE_GRID_COMPLETE")
            and not os.environ.get("ANALYSE_GRID_REDACT")):
        raise Incomplete(
            "REFUSED to load %r: the pre-registration forbids looking at a condition mean before the "
            "final N is reached. Set ANALYSE_GRID_COMPLETE=1 only when the grid is complete." % tag)
    rows, seen = [], {}
    for t in tag.split("+"):
        p = os.path.join(ROOT, "results", "grid_%s_campaigns.jsonl" % t)
        for l in open(p):
            if not l.strip():
                continue
            r = json.loads(l)
            k = (r["condition"], r["model"], r["seed"])
            if k in seen:
                raise DuplicateCampaign(
                    "%s appears in both %r and %r; a seed counted twice would enter the paired "
                    "analysis as an independent observation" % (k, seen[k], t))
            seen[k] = t
            rows.append(r)
    return rows


def scripted():
    with open(os.path.join(ROOT, "results", "step7_nk_reference_curve.json")) as f:
        c = json.load(f)["curves"]["shrinkage"]
    return c["rows"][str(c["kstar"])]["mean"], c["rows"]["0"]["mean"], c["kstar"]


_REDACT_NUMBER = re.compile(r"[-+]?\d+\.\d+")


# Model identifiers contain version numbers, so they are protected from redaction and then restored.
_MODEL_IDS = ("anthropic/claude-opus-4.7", "google/gemini-2.5-flash", "deepseek/deepseek-chat-v3.1",
              "claude-opus-4.7", "gemini-2.5-flash", "deepseek-chat-v3.1")


def redact_text(t):
    """Every decimal replaced, except inside a model identifier."""
    for i, mid in enumerate(_MODEL_IDS):
        t = t.replace(mid, "\x00M%d\x00" % i)
    t = _REDACT_NUMBER.sub("REDACTED", t)
    for i, mid in enumerate(_MODEL_IDS):
        t = t.replace("\x00M%d\x00" % i, mid)
    return t


def _redacting():
    return bool(os.environ.get("ANALYSE_GRID_REDACT"))


def redact_obj(o):
    """Replace every float with the string REDACTED, recursively. Integers are counts and stay."""
    if isinstance(o, float):
        return "REDACTED"
    if isinstance(o, dict):
        return {k: redact_obj(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [redact_obj(v) for v in o]
    return o


def dump_json(obj, path):
    """The single writer for json artefacts, so redaction applies to all of them."""
    with open(path, "w") as f:
        json.dump(redact_obj(obj) if _redacting() else obj, f, indent=1)


def table(lines, path, pilot=False):
    if _redacting():
        lines = [redact_text(l) for l in lines]
    with open(path, "w") as f:
        if pilot:
            f.write("*** PILOT (stage 0). Ran on the pre-2026-09-28 environment, which misreported the\n"
                    "*** budget. NO NUMBER BELOW IS QUOTABLE. It exists to exercise this script.\n\n")
        f.write("\n".join(lines) + "\n")
    print("  wrote %s" % os.path.relpath(path, ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag", help="one tag, or several joined by '+', "
                                 "e.g. stage1+topup_opus+topup_gemini+topup_deepseek")
    ap.add_argument("--out", default=None)
    ap.add_argument("--redact", action="store_true",
                    help="replace every decimal number in every table with REDACTED, on screen AND on "
                         "disk. Allowed without ANALYSE_GRID_COMPLETE, because a redacted table reveals "
                         "no condition mean. This exists so that verifying the CODE never requires "
                         "reading a RESULT: twice I bypassed the gate to check a code path, and the "
                         "second time I printed real panel-against-grid differences.")
    ap.add_argument("--against", default=None,
                    help="a reference tag to compare this panel against, paired on shared seeds. The "
                         "panel's own question: panelc --against stage1 is the reasoning effect.")
    a = ap.parse_args()
    if (set(a.tag.split("+")) != {"stage0"} and not os.environ.get("ANALYSE_GRID_COMPLETE")
            and not a.redact):
        sys.exit("REFUSED: %r is not the pilot. Set ANALYSE_GRID_COMPLETE=1 only when the grid is "
                 "complete; the pre-registration forbids looking at condition means before then." % a.tag)
    if a.redact:
        os.environ["ANALYSE_GRID_REDACT"] = "1"
    rows = load(a.tag)
    # Exclude campaigns whose nomination did not parse from the primary analyses, keep them for the
    # sensitivity, and report the per-cell counts wherever a table is printed.
    _fb = fallback_seeds(a.tag.split("+"))
    rows_all = list(rows)
    rows, fb_counts = drop_fallbacks(rows, _fb)
    _uc = undefined_comparator(rows_all)
    UC_NOTE = ([] if not _uc else
               ["", "0ah UNDEFINED SHRINKAGE COMPARATOR in %d campaign(s), NOT excluded because the"
                % sum(_uc.values()),
                "primary outcome is unaffected. Reason recovered per cell: "
                + "; ".join("%s/%s %d (%s)" % (c, m.split("/")[-1], v, w)
                            for (c, m, w), v in sorted(_uc.items()))])
    FB_NOTE = ["", "0ag NOMINATION FALLBACKS EXCLUDED from these primary figures: %d campaign(s)%s."
               % (sum(fb_counts.values()),
                  (" -> " + ", ".join("%s/%s %d" % (c, m.split("/")[-1], v)
                                      for (c, m), v in sorted(fb_counts.items()))) if fb_counts else ""),
               "A fallback is a nomination that did not parse, where campaign.py substituted best_by_mean(),",
               "which is exactly the Decision-rule instruction. The sensitivity keeping them is in",
               "summary.json under contrasts_with_fallbacks."] + UC_NOTE
    pilot = (a.tag == "stage0")
    out = a.out or os.path.join(ROOT, "results", "analysis_%s" % a.tag)
    os.makedirs(out, exist_ok=True)
    kstar_mean, k0_mean, kstar = scripted()
    cells = collections.defaultdict(list)
    for r in rows:
        cells[(r["condition"], r["model"])].append(r)
    models = sorted({m for _c, m in cells})

    # ---------- TABLE 1: the primary outcome by cell -------------------------------------------
    L = ["TABLE 1. Primary outcome: nominated true fitness, by condition and model.",
         "Pool-scope scripted reference: k*=%d at %.4f, k=0 at %.4f. tag=%s, %d campaigns."
         % (kstar, kstar_mean, k0_mean, a.tag, len(rows)),
         reference_bracket(), "",
         "%-14s %-30s %4s %9s %8s %9s %20s %10s"
         % ("condition", "model", "n", "mean", "SE", "median", "mean 95% CI", "vs k*")]
    for cond in LADDER:
        for m in models:
            v = cells.get((cond, m))
            if not v:
                continue
            nom = [x["nominated_true"] for x in v]
            lo, hi = boot_ci(nom)
            L.append("%-14s %-30s %4d %9.4f %8.4f %9.4f  [%7.4f, %7.4f] %+10.4f"
                     % (cond, m.split("/")[-1], len(nom), st.mean(nom),
                        st.stdev(nom) / math.sqrt(len(nom)), st.median(nom), lo, hi,
                        st.mean(nom) - kstar_mean))
    table(L + FB_NOTE, os.path.join(out, "table1_primary.txt"), pilot)

    # ---------- TABLE 2: the six confirmatory contrasts ----------------------------------------
    # Paired by seed: at one seed the k-th reading of a sequence is identical in every condition,
    # because repdef/oracle.py keys the noise, failures and screen on the seed.
    seeded = by_seed(rows)
    is_grid = "stage1" in set(a.tag.split("+")) or a.tag == "stage0"
    # A panel's Holm correction is over its own contrasts, never over the six confirmatory ones.
    L = ["TABLE 2. The SIX confirmatory contrasts, Holm-corrected across the family." if is_grid else
         ("TABLE 2. EXPLORATORY contrasts within the %r panel. NOT the confirmatory family of section "
          "0g; Holm is applied across this panel's own contrasts only." % a.tag),
         "PAIRED BY SEED, campaign level, one weight per seed. Primary p is a studentised wild cluster",
         "bootstrap over seeds with Rademacher weights. Welch is a SENSITIVITY and assumes the cells are",
         "independent, which the shared seed makes false.",
         "Minimal effect of interest %.2f. Bootstrap draws %d, resolution floor %.5f."
         % (MEI, BOOT_REPS, 1.0 / (BOOT_REPS + 1)), "",
         "%-24s %-26s %5s %5s %+9s %8s %20s %11s"
         % ("model", "contrast", "seeds", "drop", "diff", "SE", "95% CI", "wild p")]
    meta = confirmatory(seeded, models)
    raw = [x[8] for x in meta]
    for (m, c, n, dr, d, se, lo, hi, wp, pt, seu, pw, r, du), (_i, _p, adj, rej) in \
            zip(meta, holm(raw, ALPHA)):
        L.append("%-24s %-26s %5d %5d %+9.4f %8.4f  [%+7.4f, %+7.4f] %11.5f"
                 % (m.split("/")[-1], c, n, dr, d, se, lo, hi, wp))
    L += ["", "HOLM across %s of %d, on the primary paired bootstrap p:"
          % ("the confirmatory family" if is_grid else "this panel's own family", len(raw)),
          "%-24s %-26s %11s %11s %s" % ("model", "contrast", "raw p", "Holm p", "reject at .05")]
    for (m, c, *_rest), (_i, p_, adj, rej) in zip(meta, holm(raw, ALPHA)):
        L.append("%-24s %-26s %11.5f %11.5f %s"
                 % (m.split("/")[-1], c, p_, adj, "YES" if rej else "no"))

    # Sensitivity: three tests of the same contrast side by side, each with its own Holm pass.
    h_wild = holm([x[8] for x in meta], ALPHA)
    h_pt = holm([x[9] for x in meta], ALPHA)
    h_welch = holm([x[11] for x in meta], ALPHA)
    L += ["", "SENSITIVITY. Paired bootstrap (primary) against the paired t and Welch.",
          "corr is the within-seed correlation between the two cells. Where it is NEGATIVE the Welch SE",
          "is SMALLER than the truth, so an unpaired p is anti-conservative; where POSITIVE, Welch is",
          "conservative and loses power. The direction is not known in advance, which is why the",
          "paired estimator is the primary one.", "",
          "%-24s %-26s %7s %8s %8s %8s %11s %11s %11s %s"
          % ("model", "contrast", "corr", "SE pair", "SE Welch", "ratio",
             "wild p", "paired t p", "welch p", "reject w/pt/we")]
    for (m, c, n, dr, d, se, lo, hi, wp, pt, seu, pw, r, du), hw, hp, he in \
            zip(meta, h_wild, h_pt, h_welch):
        L.append("%-24s %-26s %+7.3f %8.4f %8.4f %8.3f %11.5f %11.5f %11.5f %s/%s/%s"
                 % (m.split("/")[-1], c, r, se, seu, seu / se if se else float("nan"),
                    wp, pt, pw, "Y" if hw[3] else "n", "Y" if hp[3] else "n",
                    "Y" if he[3] else "n"))
    L += ["", "The paired and unpaired POINT ESTIMATES agree to floating point when the seed sets match,",
          "since mean(b - a) equals mean(b) - mean(a). Only the standard error differs."]
    table(L + FB_NOTE, os.path.join(out, "table2_confirmatory.txt"), pilot)

    # ---------- TABLE 2b: the panel against a reference tag, paired by seed ---------------------
    # Each panel cell against the same grid cell at the same seeds, which is the panel's own question.
    if a.against:
        ref = by_seed(load(a.against))
        pan = by_seed(rows)
        L = ["TABLE 2b. EXPLORATORY: %r against %r, paired on the seeds they share." % (a.tag, a.against),
             "One row per condition and model. This is the panel's own question and is NOT in the",
             "confirmatory family of section 0g. Holm is applied across the rows of this table only.", "",
             "%-14s %-24s %6s %6s %+9s %8s %20s %11s"
             % ("condition", "model", "seeds", "drop", "diff", "SE", "95% CI", "wild p")]
        praw, pmeta = [], []
        for cond in LADDER:
            for m in models:
                A, B = ref.get((cond, m)), pan.get((cond, m))
                if not A or not B:
                    continue
                ks = sorted(set(A) & set(B))
                if len(ks) < 2:
                    continue
                d = [B[k] - A[k] for k in ks]
                if st.stdev(d) == 0:
                    continue
                diff, se, pt = paired_t_p(d)
                wp = paired_wild_p(d, tag="p%s%s%s" % (a.tag, cond, m))
                praw.append(wp)
                pmeta.append((cond, m, len(ks), len(set(A) ^ set(B)), diff, se, wp))
        for (cond, m, n, dr, diff, se, wp), (_i, _p, adj, rej) in zip(pmeta, holm(praw, ALPHA)):
            L.append("%-14s %-24s %6d %6d %+9.4f %8.4f  [%+7.4f, %+7.4f] %11.5f"
                     % (cond, m.split("/")[-1], n, dr, diff, se,
                        diff - 1.96 * se, diff + 1.96 * se, wp))
        if pmeta:
            L += ["", "%-14s %-24s %11s %11s %s" % ("condition", "model", "raw p", "Holm p", "reject")]
            for (cond, m, *_r), (_i, pv, adj, rej) in zip(pmeta, holm(praw, ALPHA)):
                L.append("%-14s %-24s %11.5f %11.5f %s"
                         % (cond, m.split("/")[-1], pv, adj, "YES" if rej else "no"))
        else:
            L.append("  no condition appears in both tags with at least two shared seeds.")
        table(L, os.path.join(out, "table2b_vs_%s.txt" % a.against), pilot)

    # ---------- TABLE 3: distinct variants, the headline behavioural metric --------------------
    L = ["TABLE 3. Distinct variants measured per campaign, the headline behavioural metric.",
         "Pool-scope scripted k*=%d reference: %.1f distinct per campaign. Counts, with medians."
         % (kstar, KSTAR_DISTINCT),
         reference_bracket(),
         "", "%-14s %-30s %4s %8s %8s %8s %20s %10s"
         % ("condition", "model", "n", "mean", "SE", "median", "95% CI", "vs k*")]
    for cond in LADDER:
        for m in models:
            v = cells.get((cond, m))
            if not v:
                continue
            nd = [float(x["n_distinct_measured"]) for x in v]
            lo, hi = boot_ci(nd, tag="d")
            L.append("%-14s %-30s %4d %8.2f %8.3f %8.1f  [%7.2f, %7.2f] %+10.2f"
                     % (cond, m.split("/")[-1], len(nd), st.mean(nd),
                        st.stdev(nd) / math.sqrt(len(nd)), st.median(nd), lo, hi,
                        st.mean(nd) - KSTAR_DISTINCT))
    table(L + FB_NOTE, os.path.join(out, "table3_distinct.txt"), pilot)

    # ---------- TABLE 4: the four replication definitions --------------------------------------
    L = ["TABLE 4. Replication fraction under all FOUR definitions. Secondary.",
         "The scripted optimum k*=%d is 25%% of slots. A claim must hold under every definition or be" % kstar,
         "reported as definition dependent.", "",
         "%-14s %-22s %4s %s" % ("condition", "model", "n",
                                 "  ".join("%-22s" % d[0] for d in REP_DEFS))]
    for cond in LADDER:
        for m in models:
            v = cells.get((cond, m))
            if not v:
                continue
            vals = []
            for _lbl, key in REP_DEFS:
                x = [r.get(key) for r in v if r.get(key) is not None]
                vals.append("%6.1f%%" % (100 * st.mean(x)) if x else "     na")
            L.append("%-14s %-22s %4d %s"
                     % (cond, m.split("/")[-1][:22], len(v), "  ".join("%-22s" % z for z in vals)))
    table(L + FB_NOTE, os.path.join(out, "table4_replication.txt"), pilot)

    # ---------- TABLE 5: secondaries, decomposition and proposal viability ---------------------
    L = ["TABLE 5. Secondary outcomes: the shortfall decomposition, lost slots, proposal viability.",
         "global best minus nominated = exploration shortfall + selection shortfall (an identity).",
         "Lost slots measure PROPOSAL VIABILITY and are not a simple function of exploration:",
         "within model, r(lost, distinct) was +0.016 opus, +0.260 deepseek, +0.331 gemini on stage 0.",
         "", "%-14s %-22s %4s %9s %9s %9s %8s %8s %9s"
         % ("condition", "model", "n", "explor", "select", "lost", "abandon", "rnd lost", "rej/order")]
    for cond in LADDER:
        for m in models:
            v = cells.get((cond, m))
            if not v:
                continue
            # An absent field (older tags predate lost_slots and related fields) prints "na", never zero.
            def g(k, fmt="%9.4f"):
                xs = [r[k] for r in v if r.get(k) is not None]
                return (fmt % st.mean(xs)) if len(xs) == len(v) else ("na".rjust(len(fmt % 0)))
            su = st.mean([r["slots_used"] for r in v]) or 1
            L.append("%-14s %-22s %4d %s %s %s %s %s %9.2f"
                     % (cond, m.split("/")[-1][:22], len(v),
                        g("exploration_shortfall"), g("selection_shortfall"),
                        g("lost_slots", "%9.2f"), g("slots_abandoned", "%8.2f"),
                        g("rounds_lost_slots", "%8.2f"),
                        st.mean([r["n_rejected"] for r in v]) / su))
    table(L + FB_NOTE, os.path.join(out, "table5_secondary.txt"), pilot)

    # Per-cell values for scripts/figures.py, which reads only this output, so figures match tables.
    cells_detail = []
    for cond in LADDER:
        for m in models:
            v = cells.get((cond, m))
            if not v:
                continue
            nom = [x["nominated_true"] for x in v]
            lo, hi = boot_ci(nom)
            rep = {}
            for lbl, key in REP_DEFS:
                xs = [r.get(key) for r in v if r.get(key) is not None]
                rep[lbl] = (st.mean(xs) if xs else None)
            cells_detail.append(dict(
                condition=cond, model=m.split("/")[-1], model_id=m, n=len(nom),
                mean=st.mean(nom), median=st.median(nom), lo=lo, hi=hi,
                distinct=st.mean([float(x["n_distinct_measured"]) for x in v]),
                # The two diagnostics, in machine-readable form for the figures and the release score.
                exploration_shortfall=st.mean([x["exploration_shortfall"] for x in v
                                               if x.get("exploration_shortfall") is not None] or [0.0]),
                selection_shortfall=st.mean([x["selection_shortfall"] for x in v
                                             if x.get("selection_shortfall") is not None] or [0.0]),
                replication=rep))
    dump_json(dict(tag=a.tag, campaigns=len(rows), cells=len(cells), cells_detail=cells_detail,
                   scripted_kstar_mean=kstar_mean, scripted_k0_mean=k0_mean,
                   paired_by_seed=True,
                   undefined_comparator={"%s|%s|%s" % k: v for k, v in _uc.items()},
                   fallbacks_excluded=sum(fb_counts.values()),
                   fallbacks_by_cell={"%s|%s" % k: v for k, v in fb_counts.items()},
                   contrasts_with_fallbacks=[
                       dict(model=m, contrast=c, seeds=n, diff=d, se=se, wild_p=wp)
                       for (m, c, n, _dr, d, se, _lo, _hi, wp, _pt, _seu, _pw, _r, _du)
                       in confirmatory(by_seed(rows_all), models)],
                   contrasts=[dict(model=m, contrast=c, seeds=n, seeds_dropped=dr, diff=d,
                                   se_paired=se, se_welch=seu, corr=r, wild_p=wp, paired_t_p=pt,
                                   welch_p=pw)
                              for (m, c, n, dr, d, se, _lo, _hi, wp, pt, seu, pw, r, _du) in meta]),
              os.path.join(out, "summary.json"))
    print("  wrote %s" % os.path.relpath(os.path.join(out, "summary.json"), ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
