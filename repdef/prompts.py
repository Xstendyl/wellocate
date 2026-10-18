"""Prompt templates for the LLM agent, one per information rung.

The rungs are cumulative: each adds one block to the previous one. The instructed rung states
facts and grants permission to re-order; it never recommends replication.

  1 blind       noise exists in the oracle, the prompt does not mention it
  1b baseline   + readings carry measurement error, unquantified
  2 informed    + the exact sigma
  3 instructed  + the averaging mechanism and permission to re-order
  4 forced      the harness reserves one slot per round for the champion; prompt as rung 1
"""

RUNGS = ("blind", "baseline", "informed", "instructed", "forced",
         "aggregated", "decision_rule")

# Two interventions, both built on "instructed":
#   aggregated     the history is shown as n, mean and standard error per variant instead of
#                  a list of raw readings.
#   decision_rule  one sentence telling the agent to report the variant with the highest average.

# --- landscape configuration, so one template serves every cell ------------------------------
# The terms below are substituted per landscape; prompts differ only in these fields.
LANDSCAPES = {
    "gb1_bio": dict(
        domain="protein engineering", system="protein G domain B1 (GB1)",
        positions="Four positions", symbols="the 20 standard amino acids",
        alphabet="ACDEFGHIKLMNPQRSTVWY", metric="binding activity", item="variant",
        candidate_word="candidate", space="160,000", parent="VDGV", example="ADGV",
        anchor_reading="1.0"),
    "phoq_bio": dict(
        domain="protein engineering", system="the E. coli PhoQ kinase interface with PhoP",
        positions="Four positions", symbols="the 20 standard amino acids",
        alphabet="ACDEFGHIKLMNPQRSTVWY", metric="functional score", item="variant",
        candidate_word="candidate", space="160,000", parent="AVST", example="TVST",
        anchor_reading="3.3"),
    "abstract": dict(
        domain="numerical optimization", system="an abstract four-position system",
        positions="Four positions", symbols="20 symbols",
        alphabet="ABCDEFGHIJKLMNOPQRST", metric="score", item="string",
        candidate_word="candidate", space="160,000", parent="AAAA", example="BAAA",
        anchor_reading="1.0"),
}

# --- the frame, identical in every rung -----------------------------------------------------
HEADER = """{opening}

DESIGN SPACE
{positions}, each holding one of {symbols} ({alphabet}).
A {candidate_word} is a 4-letter string, for example "{parent}".
Only a minority of the {space} possible {candidate_word}s are viable. {rejection_rule} The reference point is "{parent}".

GOAL
Find the {candidate_word} with the highest {metric}.{goal_extra}

BUDGET
{rounds} rounds, {budget_slots} orders per round, {total} measurements in total.
This is your entire budget and there is no way to get more.

HOW MEASUREMENT WORKS
- Each order returns a numeric {metric} reading. The reference point reads about {anchor_reading}.
- About {fail_pct}% of orders fail for technical reasons and return nothing. A failed order
  still consumes its slot.
- If your reply does not contain exactly the number of {candidate_word}s asked for, you will be
  asked once more. If the second reply is also not exactly that number, THE WHOLE ROUND IS LOST
  and its slots count against your budget."""

# Optional prompt blocks below are off by default, so default prompts are unchanged.
# Structure block: true facts about the grid landscape's structure, with no advice. The numbers are
# measured from the landscape itself.
STRUCTURE_GRID = (
    "\nSTRUCTURE\n"
    "Number the positions 1 to 4 from the left. The score is the average of four parts. Each part depends on the\n"
    "letters at two neighbouring positions: 1 and 2, 2 and 3, 3 and 4, and 4 and 1. So changing positions 1\n"
    "and 3 together moves the score by the sum of what each change does alone, and the same holds for\n"
    "positions 2 and 4. Changes at neighbouring positions do not add up this way. Of the candidates one letter\n"
    "away from a viable candidate, 26% are viable, against 7% of all candidates.")

# A refused order never enters the history (Oracle.record_capped), so a "capped" history row is an error.
REFUSED_IN_HISTORY = "an order refused by the repeat cap reached the history; it must not"
# A slot lost after the repeat cap refused an order, whatever mix of refusals and non-viable replacements it saw.
CAP_LOST_LINE = "SLOT LOST: its replacements were refused at the order limit or were non-viable"

# Default rejection rule: a limited number of replacement asks per slot.
REJECTION_CAPPED = ("An order for a non-viable\n{candidate_word} is rejected, and you will be asked for a "
                    "replacement for that slot, up to\n{max_reasks} times. If every replacement is also "
                    "non-viable, THE SLOT IS LOST and counts against\nyour budget.")
# riskfree_rejection: a non-viable order never costs a slot (enforced in campaign.run).
REJECTION_RISKFREE = ("An order for a non-viable\n{candidate_word} is rejected at no cost and you choose "
                      "again. No slot is ever lost to a non-viable order.")
# goal_true_value: the score is the nominated candidate's true value. Same in every rung and silent on
# readings, so it does not reveal noise to the blind rung. Round and replacement prompts only.
GOAL_TRUE_VALUE = ("At the end you will nominate one {candidate_word}, and your score is that "
                   "{candidate_word}'s true value.")


# Repeat cap line, stated in every prompt kind when the cap is on. Off by default.
REPEAT_CAP_LINE = ("- Each {candidate_word} can be ordered at most {times}. A further order of it is rejected at no "
                   "cost and you choose again.")


def _repeat_cap_line(t, repeat_cap):
    orders = 1 + int(repeat_cap)
    times = {2: "twice", 3: "three times"}.get(orders, "%d times" % orders)
    return REPEAT_CAP_LINE.format(candidate_word=t["candidate_word"], times=times)


def _option_fields(t, max_reasks, goal_true_value=False, riskfree_rejection=False):
    """Render the optional rejection-rule and goal text in the landscape's own words."""
    rule = REJECTION_RISKFREE if riskfree_rejection else REJECTION_CAPPED
    return dict(rejection_rule=rule.format(candidate_word=t["candidate_word"], max_reasks=max_reasks),
                goal_extra=("\n" + GOAL_TRUE_VALUE.format(candidate_word=t["candidate_word"])
                            if goal_true_value else ""))


# Measurement-error sentence, carried by the baseline rung and above (not by blind).
BASELINE_BLOCK = """- Readings are subject to measurement error, so a reading is not exactly the
  {candidate_word}'s true {metric}."""

# --- rung 2 adds the exact noise ------------------------------------------------------------
INFORMED_BLOCK = """- Each measurement carries independent Gaussian error with standard deviation sigma = {sigma}."""

# Under multiplicative noise there is no single sigma, so the informed rung states the noise formula
# and its constants, with no example and no advice.
INFORMED_BLOCK_MULTIPLICATIVE = """- Each measurement carries independent Gaussian error whose standard deviation DEPENDS ON
  the {item}'s own level f, as sigma(f) = sqrt({floor}^2 + ({cv} * f)^2)."""

# Zero-noise environment: the noise sentences of the baseline and informed rungs are replaced by
# statements that are true when sigma = 0. The blind prompt is unchanged.
BASELINE_BLOCK_EXACT = """- Every reading is exact: a reading IS the {item}'s true {metric}."""
INFORMED_BLOCK_EXACT = """- Every reading is exact, so repeating a measurement returns the same number."""
# No averaging sentence under sigma = 0, since it would be false.
INSTRUCTED_BLOCK_EXACT = """- You may order the same {item} more than once, within a round or across rounds."""

# --- rung 3 adds the mechanism and the permission, and recommends nothing --------------------
INSTRUCTED_BLOCK = """- You may order the same {item} more than once, within a round or across rounds.
- Independent measurements of the same {item} can be averaged; n measurements reduce the
  standard error of its mean by a factor of sqrt(n)."""

# --- intervention 2: one sentence at the point of decision ------------------------------------
# Kept to the rule alone, without naming the failure mode.
DECISION_RULE_BLOCK = """- When you report your final answer, report the {item} with the highest
  AVERAGE reading across all of its measurements."""

_BLOCK_TEXT = {"baseline": BASELINE_BLOCK, "informed": INFORMED_BLOCK,
               "informed_multiplicative": INFORMED_BLOCK_MULTIPLICATIVE,
               "baseline_exact": BASELINE_BLOCK_EXACT, "informed_exact": INFORMED_BLOCK_EXACT,
               "instructed_exact": INSTRUCTED_BLOCK_EXACT,
               "instructed": INSTRUCTED_BLOCK, "decision_rule": DECISION_RULE_BLOCK}

FOOTER = """
ROUND {r} OF {rounds}. You have {remaining} measurements remaining.

HISTORY
{history}

Choose {slots} {candidate_word}s to order this round.
Reply with exactly {slots} lines and nothing else. Each line must be:
CANDIDATE | one short reason
for example:
{example} | one short reason here"""

NO_HISTORY = "(no measurements yet)"


def terms(landscape="gb1_bio", **over):
    """Resolve one landscape's substitutions. Keyword arguments override them; unknown keys raise."""
    if landscape not in LANDSCAPES:
        raise ValueError("unknown landscape %r; known: %s"
                         % (landscape, ", ".join(sorted(LANDSCAPES))))
    t = dict(LANDSCAPES[landscape])
    for k, v in over.items():
        if v is None:
            continue
        if k not in t:
            raise ValueError("unknown substitution %r for landscape %r" % (k, landscape))
        t[k] = v
    return t


# Text blocks per rung. A missing rung raises. `blind` and `forced` share an empty block list.
_BLOCKS = {
    "blind":         (),
    "baseline":      ("baseline",),
    "informed":      ("baseline", "informed"),
    "instructed":    ("baseline", "informed", "instructed"),
    "forced":        (),
    "aggregated":    ("baseline", "informed", "instructed"),
    "decision_rule": ("baseline", "informed", "instructed", "decision_rule"),
}

# Rungs whose history is aggregated per variant; their prompt text otherwise equals "instructed".
AGGREGATED_RUNGS = ("aggregated",)


# The opening sentence is selectable. Framing variants replace only this sentence.
GRID_OPENING = "You are running a {domain} campaign on four positions of {system}."
OPENINGS = {
    "grid": GRID_OPENING,
    "bio_role": ("You are a protein engineer working in a wet lab. You are improving a protein by "
                 "changing four positions, each of which can hold one of 20 building blocks. Each "
                 "order is a sample submitted to the lab's assay facility."),
}
OPENINGS["bio_role_noisy"] = (OPENINGS["bio_role"] + " Assay readings can be noisy, as in any real "
                              "lab: a single reading may not reflect the sample's true value.")
# bio_role_exact uses the bio_role wording and differs only in sigma.
OPENINGS["bio_role_exact"] = OPENINGS["bio_role"]


def _fmt_dict(landscape, parent, example, anchor_reading, rounds, slots, total, fail_pct,
              sigma, cv, noise_floor, max_reasks, opening="grid", riskfree_rejection=False, repeat_cap=None,
              structure_text=None):
    t = terms(landscape, parent=parent, example=example, anchor_reading=anchor_reading)
    if opening not in OPENINGS:
        raise ValueError("unknown opening %r; known: %s" % (opening, sorted(OPENINGS)))
    t = dict(t, opening=OPENINGS[opening].format(**t))
    return dict(t, rounds=rounds, slots=slots, budget_slots=slots, total=total, fail_pct=fail_pct,
                sigma=_fmt(sigma), cv=(_sig(cv) if cv is not None else ""),
                floor=(_sig(noise_floor) if noise_floor is not None else ""),
                max_reasks=max_reasks,
                **_option_fields(t, max_reasks, goal_true_value=False,
                                 riskfree_rejection=riskfree_rejection),
                repeat_cap_line=(_repeat_cap_line(t, repeat_cap) if repeat_cap is not None else None),
                structure_text=structure_text)


def _body(rung, fmt, noise_model):
    """HEADER plus this rung's blocks. The only place the instruction body is assembled."""
    parts = [HEADER.format(**fmt)]
    if fmt.get("repeat_cap_line"):
        parts.append(fmt["repeat_cap_line"])
    if fmt.get("structure_text"):
        parts.append(fmt["structure_text"])
    for name in _BLOCKS[rung]:
        if noise_model == "exact":
            # Replace each measurement-error sentence with one that is true of an exact environment.
            name = {"baseline": "baseline_exact", "informed": "informed_exact",
                    "instructed": "instructed_exact"}.get(name, name)
        elif name == "informed" and noise_model == "multiplicative":
            name = "informed_multiplicative"
        parts.append(_BLOCK_TEXT[name].format(**fmt))
    return "\n".join(parts)


def build(rung, view_history, r, rounds, slots, remaining, sigma, parent=None,
          fail_pct=15, total=60, example=None, landscape="gb1_bio",
          noise_model="additive", cv=None, noise_floor=None, anchor_reading=None,
          max_reasks=3, opening="grid", goal_true_value=False, riskfree_rejection=False,
          slots_per_round=None, repeat_cap=None, ledger_text=None, menu_text=None, at_limit_text=None,
          structure_text=None):
    """Assemble one prompt. `view_history` is a list of (round, seq, outcome, observed).

    `slots` is how many candidates this prompt asks for: 4 in a round prompt, 1 in a replacement.
    With `slots_per_round` given, the budget line states the orders per round from it instead.

    `noise_model` selects the noise statement and must match the noise the oracle applies."""
    if rung not in RUNGS:
        raise ValueError("unknown rung %r; known: %s" % (rung, ", ".join(RUNGS)))
    if noise_model not in ("additive", "multiplicative", "exact"):
        raise ValueError("noise_model must be 'additive', 'multiplicative' or 'exact'")
    if noise_model == "multiplicative" and (cv is None or noise_floor is None):
        raise ValueError("multiplicative noise needs cv and noise_floor to state it exactly")
    t = terms(landscape, parent=parent, example=example, anchor_reading=anchor_reading)
    # max_reasks comes from the harness so the prompt states the real number of replacement asks.
    if opening not in OPENINGS:
        raise ValueError("unknown opening %r; known: %s" % (opening, sorted(OPENINGS)))
    fmt = dict(t, opening=OPENINGS[opening].format(**t),
               rounds=rounds, slots=slots, total=total, fail_pct=fail_pct,
               budget_slots=(slots if slots_per_round is None else slots_per_round),
               sigma=_fmt(sigma), cv=(_sig(cv) if cv is not None else ""),
               floor=(_sig(noise_floor) if noise_floor is not None else ""),
               max_reasks=max_reasks,
               **_option_fields(t, max_reasks, goal_true_value=goal_true_value,
                                riskfree_rejection=riskfree_rejection))
    parts = [HEADER.format(**fmt)]
    if repeat_cap is not None:
        parts.append(_repeat_cap_line(t, repeat_cap))
    if structure_text:
        parts.append(structure_text)
    for name in _BLOCKS[rung]:
        if noise_model == "exact":
            # Replace each measurement-error sentence with one that is true of an exact environment.
            name = {"baseline": "baseline_exact", "informed": "informed_exact",
                    "instructed": "instructed_exact"}.get(name, name)
        elif name == "informed" and noise_model == "multiplicative":
            name = "informed_multiplicative"
        parts.append(_BLOCK_TEXT[name].format(**fmt))
    body = "\n".join(parts)
    hist = _history(view_history, aggregated=(rung in AGGREGATED_RUNGS), sigma=sigma,
                    exact=(noise_model == "exact"))
    # Optional tool text follows the history. None leaves the prompt unchanged.
    for extra in (ledger_text, menu_text, at_limit_text):
        if extra:
            hist = hist + "\n\n" + extra
    return body + FOOTER.format(**dict(fmt, r=r, remaining=remaining, history=hist))


def _fmt(x):
    """Format to two decimals. Use _sig for values that two decimals would misstate."""
    return ("%.2f" % x).rstrip("0").rstrip(".")


def _sig(x, digits=3):
    """Format to significant figures, for small constants such as cv or the noise floor."""
    if not x:
        return "0"
    from math import floor, log10
    p = digits - 1 - int(floor(log10(abs(x))))
    out = ("%.*f" % (max(p, 0), x))
    return out.rstrip("0").rstrip(".") if "." in out else out


def _history(rows, aggregated=False, sigma=None, exact=False):
    """Render the history as one line per slot spent, in order, including failures and rejections.

    With `aggregated`, the same information is shown per variant as n, mean and standard error."""
    if not rows:
        return NO_HISTORY
    if aggregated:
        return _history_aggregated(rows, exact=exact)
    out = ["round  candidate  reading"]
    for (rnd, seq, outcome, obs) in rows:
        if outcome == "ok":
            val = "%.3f" % obs
        elif outcome == "failed":
            val = "order failed, no reading"
        elif outcome == "abandoned":
            val = "SLOT LOST: every replacement for this slot was also non-viable"
        elif outcome == "round_lost":
            val = "ROUND LOST: the reply was not the requested number of candidates"
        elif outcome == "cap_lost":
            val = CAP_LOST_LINE
        elif outcome == "capped":
            raise ValueError(REFUSED_IN_HISTORY)
        else:
            val = "rejected, not viable, a replacement was requested"
        out.append("%5d  %-9s  %s" % (rnd, seq, val))
    return "\n".join(out)


def _history_aggregated(rows, exact=False):
    """n / mean / SE per variant, ordered by first appearance so the order implies no ranking.

    Lost slots and lost rounds are reported separately from rejections.
    """
    order, readings, fails, rejects, lost = [], {}, {}, {}, {}
    cap_lost = {}
    rounds_lost = 0
    for (rnd, seq, outcome, obs) in rows:
        if outcome == "round_lost":
            # Not a candidate. Counted and reported on its own line.
            rounds_lost += 1
            continue
        if outcome == "capped":
            raise ValueError(REFUSED_IN_HISTORY)
        if seq not in readings:
            order.append(seq)
            readings[seq], fails[seq], rejects[seq], lost[seq] = [], 0, 0, 0
            cap_lost[seq] = 0
        if outcome == "ok":
            readings[seq].append(obs)
        elif outcome == "failed":
            fails[seq] += 1
        elif outcome == "abandoned":
            lost[seq] += 1
        elif outcome == "cap_lost":
            cap_lost[seq] += 1
        else:
            rejects[seq] += 1
    out = ["candidate  n  mean     standard error of the mean"]
    for seq in order:
        v = readings[seq]
        extra = ""
        if fails[seq]:
            extra += "   (%d further order(s) failed)" % fails[seq]
        if lost[seq]:
            extra += ("   (SLOT LOST %d time(s): every replacement was also non-viable, and those "
                      "slots count against your budget)" % lost[seq])
        if cap_lost[seq]:
            extra += ("   (SLOT LOST %d time(s): its replacements were refused at the order limit or were "
                      "non-viable, and those slots count against your budget)" % cap_lost[seq])
        if not v:
            if cap_lost[seq]:
                note = CAP_LOST_LINE + ", and the slot counts against your budget"
            elif lost[seq]:
                note = ("SLOT LOST: every replacement for this slot was also non-viable, and the slot "
                        "counts against your budget")
            elif fails[seq]:
                note = "all %d orders failed" % fails[seq]
            else:
                note = "rejected, not viable, a replacement was requested"
            out.append("%-9s  0  %s" % (seq, note))
            continue
        n = len(v)
        mean = sum(v) / n
        if exact:
            # Under exact readings the SE is known to be zero, so it is not shown as unknown.
            se = "0 (readings are exact)"
        elif n > 1:
            var = sum((x - mean) ** 2 for x in v) / (n - 1)
            se = "%.3f" % ((var / n) ** 0.5)
        else:
            se = "not estimable from 1 measurement"
        out.append("%-9s  %d  %-7.3f  %s%s" % (seq, n, mean, se, extra))
    if rounds_lost:
        out.append("ROUND LOST %d time(s): a reply was not the requested number of candidates, and "
                   "those rounds' slots count against your budget" % rounds_lost)
    return "\n".join(out)


# --------------------------------------------------------------------------------------------
# Final nomination: the agent itself picks the variant to report at the end of the campaign.
# The wording recommends nothing and names no selection rule.
NOMINATE = """{header}
ROUND {rounds} OF {rounds} IS COMPLETE. Your budget is spent.

HISTORY
{history}

Name the single {candidate_word} you believe has the highest true {metric}.
Reply with exactly two lines and nothing else:
ANSWER: XXXX
REASON: one short sentence"""


def build_nomination(rung, view_history, rounds, slots, sigma, parent=None,
                     fail_pct=15, total=60, metric=None, landscape="gb1_bio",
                     noise_model="additive", cv=None, noise_floor=None, anchor_reading=None,
                     example=None, max_reasks=3, opening="grid", riskfree_rejection=False, repeat_cap=None,
                     structure_text=None):
    """The end-of-campaign nomination prompt, with the same rung blocks and history format as the round prompts."""
    if rung not in RUNGS:
        raise ValueError("unknown rung %r; known: %s" % (rung, ", ".join(RUNGS)))
    if noise_model not in ("additive", "multiplicative", "exact"):
        raise ValueError("noise_model must be 'additive', 'multiplicative' or 'exact'")
    t = terms(landscape, parent=parent, metric=metric, anchor_reading=anchor_reading)
    fmt = _fmt_dict(landscape, parent, example, anchor_reading, rounds, slots, total, fail_pct,
                    sigma, cv, noise_floor, max_reasks, opening=opening,
                    riskfree_rejection=riskfree_rejection, repeat_cap=repeat_cap,
                    structure_text=structure_text)
    if metric is not None:
        fmt["metric"] = metric
    # Assembled from parts by _body, never by splitting text.
    header = _body(rung, fmt, noise_model).rstrip()
    return NOMINATE.format(header=header, rounds=rounds, metric=t["metric"],
                           candidate_word=t["candidate_word"],
                           history=_history(view_history,
                                            aggregated=(rung in AGGREGATED_RUNGS), sigma=sigma,
                                            exact=(noise_model == "exact")))
