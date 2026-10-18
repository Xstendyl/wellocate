"""LLM policy: prompts a model with the CampaignView, parses its proposals, and logs every call.

Each proposal carries a stated reason, used to classify intent (deliberate replication, apparent
oversight, exploration). Parsing is strict: malformed replies are logged with their raw text and
never repaired, and repeated sequences in one reply are kept as replications.
"""

import collections
import re
import time

from repdef import llm, policies, prompts, tools

# Default alphabet: the 20 amino acids.
AA = set("ACDEFGHIKLMNPQRSTVWY")

# Parsers take the alphabet of the landscape that generated the prompt, since generated landscapes
# use letters outside the amino acids.

Proposal = collections.namedtuple(
    "Proposal", "round seq reason intent already_measured raw_line")

# Intent classes. `already_measured` decides replicate-vs-explore; the wording decides whether a
# replication was deliberate.
CONFIRM_WORDS = ("confirm", "verify", "replicat", "again", "re-measure", "remeasure",
                 "repeat", "average", "averag", "noise", "noisy", "uncertain", "variance",
                 "error", "reliab", "double-check", "double check", "validate", "re-order",
                 "reorder", "recheck", "re-check", "precision", "std", "sigma")
EXPLORE_WORDS = ("explore", "new", "try", "neighbour", "neighbor", "vary", "diversif",
                 "test", "probe", "scan", "sample", "mutat", "substitut", "different")


def classify(seq, reason, already_measured):
    r = (reason or "").lower()
    if already_measured:
        if any(w in r for w in CONFIRM_WORDS):
            return "replicate_to_confirm"
        return "replicate_by_apparent_oversight"
    if any(w in r for w in EXPLORE_WORDS):
        return "explore"
    return "unclear"


# Three line patterns, strictest first. The prompt asks for "CANDIDATE | one short reason". If a reply
# uses the pipe format anywhere, only pipe lines count, so sequences listed in reasoning are not read
# as proposals. Looser patterns apply only to replies with no pipe lines.
PIPE = re.compile(r"^\s*[\-\*\d\.\)\s]*([A-Za-z]{4})\s*\|\s*(.*)$")
LOOSE = re.compile(r"^\s*[\-\*\d\.\)\s]*([A-Za-z]{4})\s*[:\-,]\s*(.*)$")
BARE = re.compile(r"^\s*[\-\*\d\.\)\s]*([A-Za-z]{4})\s*$")
LINE = PIPE          # alias


ANY_SEQ = re.compile(r"\b([A-Za-z]{4})\b")


def candidates_anywhere(text, alphabet=None):
    """Every 4-letter token anywhere in the response that is legal in the alphabet. Logged only.

    Many more tokens than proposals suggests the reasoning mentions sequences."""
    # On the abstract alphabet many English four-letter words are legal tokens, so the count is noisier there.
    allowed = set(AA if alphabet is None else alphabet)
    return [m.group(1).upper() for m in ANY_SEQ.finditer(text or "")
            if set(m.group(1).upper()) <= allowed]


def parse_nomination_b(text, alphabet=None):
    """An independent second parser for the nomination: takes the last "ANSWER:" line instead of the first.

    The two differ when a model states an answer, reconsiders, and states another.
    """
    allowed = set(AA if alphabet is None else alphabet)
    for line in reversed((text or "").splitlines()):
        u = line.strip()
        if u.upper().startswith("ANSWER:"):
            tok = u.split(":", 1)[1].strip().split()
            if tok:
                cand = tok[0].upper()
                if len(cand) == 4 and set(cand) <= allowed:
                    return cand
            return None
    return None


def parse_b(text, n_slots, alphabet=None):
    """An independent second parser: reads only the final block of consecutive pipe lines.

    It shares no code with `parse`; their disagreement rate is logged as a parsing check.
    """
    allowed = set(AA if alphabet is None else alphabet)
    lines = (text or "").splitlines()
    block, seen_any = [], False
    for raw in reversed(lines):
        m = PIPE.match(raw)
        if m:
            seen_any = True
            seq = m.group(1).upper()
            if set(seq) <= allowed:
                block.append(seq)
            else:
                block.append(None)          # out-of-alphabet line: kept in the block, dropped later
        elif seen_any:
            if raw.strip() == "":
                continue                     # a blank line inside the answer block is not a break
            break
    block.reverse()
    return [x for x in block if x is not None]


def parse(text, n_slots, alphabet=None):
    """Return (proposals, status, notes). `proposals` is a list of (seq, reason).

    Statuses, all logged, none repaired:
      ok                         exactly n_slots well-formed lines
      ambiguous                  more proposals than asked for
      wrong_count                fewer proposals than asked for, none dropped for alphabet
      alphabet_then_wrong_count  wrong count because lines were dropped for alphabet
      bad_alphabet               nothing accepted, and some tokens were outside the alphabet
      unparseable                nothing recoverable
      refusal                    the model declined, hedged or asked a question instead of proposing
    """
    notes = []
    if not (text or "").strip():
        return [], "unparseable", ["empty response"]
    low = text.lower()
    got = []
    lines = text.splitlines()
    tier = "pipe" if any(PIPE.match(l) for l in lines) else (
        "loose" if any(LOOSE.match(l) for l in lines) else "bare")
    notes.append("format tier: %s" % tier)
    for raw in lines:
        if tier == "pipe":
            m = PIPE.match(raw)
        elif tier == "loose":
            m = LOOSE.match(raw) or BARE.match(raw)
        else:
            m = BARE.match(raw)
        if not m:
            continue
        seq = m.group(1).upper()
        reason = (m.group(2).strip() if m.lastindex and m.lastindex >= 2 else "")
        allowed = AA if alphabet is None else set(alphabet)
        if not set(seq) <= allowed:
            notes.append("bad alphabet in %r: %s not in the landscape's alphabet %s"
                         % (seq, sorted(set(seq) - allowed), "".join(sorted(allowed))))
            continue
        got.append((seq, reason))
    if not got:
        if any(w in low for w in ("i cannot", "i can't", "as an ai", "could you",
                                 "clarify", "i'm unable", "i am unable", "?")):
            return [], "refusal", notes + ["no candidate parsed; text reads as a refusal or a question"]
        # Check for an alphabet note specifically; other notes are always present.
        if any("bad alphabet" in n for n in notes):
            return [], "bad_alphabet", notes
        return [], "unparseable", notes + ["no line matched"]
    # A wrong count caused by the alphabet filter gets its own status. Too many proposals is
    # "ambiguous" and is never truncated; the caller re-asks and otherwise spends no slots.
    dropped = sum(1 for n in notes if "bad alphabet" in n)
    if len(got) > n_slots:
        notes.append("asked for %d and %d proposals were accepted, so WHICH ones were meant is "
                     "unknowable; refusing to choose" % (n_slots, len(got)))
        return got, "ambiguous", notes
    if len(got) == n_slots:
        status = "ok"
    elif dropped:
        status = "alphabet_then_wrong_count"
        notes.append("asked for %d, parsed %d, and %d line(s) were dropped by the alphabet filter, "
                     "so the count is a CONSEQUENCE and not an output-format failure"
                     % (n_slots, len(got), dropped))
    else:
        status = "wrong_count"
        notes.append("asked for %d, parsed %d, with no alphabet rejections" % (n_slots, len(got)))
    return got, status, notes


BAD_ALPHABET_NOTE = re.compile(r"bad alphabet in '([A-Za-z]{4})'")


def dropped_for_alphabet(notes):
    """The 4-letter tokens `parse` dropped because a letter is outside the landscape's alphabet."""
    return [m.group(1) for n in notes for m in [BAD_ALPHABET_NOTE.search(n)] if m]


def truthful_reask(dropped, alphabet, n_slots):
    """Re-ask text for replies with lines dropped for out-of-alphabet letters: names them and restates the alphabet."""
    return ("\n\nYour previous reply could not be used. These candidates contain letters that are not in the "
            "alphabet: %s. Every candidate must use only the letters %s. Reply again with exactly %d "
            "lines in the form\nCANDIDATE | one short reason\nand nothing else."
            % (", ".join(dropped), alphabet, n_slots))


def parse_answer(text, alphabet):
    """Parse the nomination reply's ANSWER and REASON lines. Returns (seq, reason, notes); seq is "" if invalid."""
    seq, reason = "", ""
    nom_notes = []
    for line in (text or "").splitlines():
        u = line.strip()
        if u.upper().startswith("ANSWER:"):
            tok = u.split(":", 1)[1].strip().split()
            if tok:
                # A token of the wrong length is a parse failure, never truncated.
                cand = tok[0].upper()
                if len(cand) == 4 and set(cand) <= set(alphabet):
                    seq = cand
                else:
                    nom_notes.append("ANSWER token %r is not a 4-letter sequence in the "
                                     "alphabet, so no nomination was read from it" % cand)
        elif u.upper().startswith("REASON:"):
            reason = u.split(":", 1)[1].strip()
    return seq, reason, nom_notes


# Provider-overload retry, used only when LLMPolicy.provider_retry is set.
# Seconds to wait before attempts 2 to 5 of an identical request.
PROVIDER_RETRY_BACKOFF = (30, 60, 120, 240)


def provider_unavailable(call):
    """True only for an explicit provider overload: an error with code 502 or 503, or error_type provider_unavailable."""
    raw = call.raw if isinstance(call.raw, dict) else {}
    err = raw.get("error")
    if not isinstance(err, dict):
        return False
    try:
        code = int(err.get("code"))
    except (TypeError, ValueError):
        code = None
    meta = err.get("metadata") if isinstance(err.get("metadata"), dict) else {}
    return code in (502, 503) or meta.get("error_type") == "provider_unavailable"


class TransportFailure(RuntimeError):
    """The model call did not complete. Raised so the campaign is abandoned instead of charging the agent.

    An unparseable reply is the agent's failure and costs a round; a failed call is not.
    """

    def __init__(self, model, error, kind):
        RuntimeError.__init__(self, "transport failure on the %s call to %s, campaign abandoned "
                                    "unwritten: %s" % (kind, model, error))
        self.model, self.error, self.kind = model, error, kind


class CreditsExhausted(TransportFailure):
    """HTTP 402 (out of credits). The whole run halts, since every further call would fail the same way."""


def _raise_transport(model, error, kind, failed=None):
    """Raise CreditsExhausted for HTTP 402, otherwise TransportFailure.

    `failed` (the failed request, prompt and raw response) is attached as `failed_request`."""
    exc = CreditsExhausted(model, error, kind) if "402" in str(error) else TransportFailure(model, error, kind)
    exc.failed_request = failed
    raise exc


def call_fields(call):
    """Every logged field taken from a Call, shared by all log row kinds."""
    return {
        # The model the provider says it served, beside the one requested.
        "model_returned": call.model,
        # Which upstream provider served the call; providers can differ in quantisation and defaults.
        "provider": getattr(call, "provider", ""),
        "prompt_tokens": call.prompt_tokens,
        "completion_tokens": call.completion_tokens,
        # Reasoning tokens and finish reason, so empty replies from reasoning models can be counted.
        "reasoning_tokens": call.reasoning_tokens,
        "finish_reason": call.finish_reason,
        "empty_text": not (call.text or "").strip(),
        # Returned reasoning text (never used as the answer) and the answer's own token count.
        "visible_tokens": getattr(call, "visible_tokens", None),
        "reasoning_text": getattr(call, "reasoning_text", ""),
        "cost_usd": call.cost_usd,
        "error": call.error,
        # latency_ms is set per site: the whole slot for rounds, the single call for nominations.
    }


class LLMPolicy(policies.Policy):
    """Policy that asks a model for proposals each round and logs every call."""

    def __init__(self, model, rung, sigma, parent="VDGV", temperature=0.0,
                 max_tokens=3000, env_file=None, log=None, fail_pct=15,
                 reasoning_effort=None, landscape="gb1_bio", noise_model="additive",
                 cv=None, noise_floor=None, anchor_reading=None, example=None, opening="grid"):
        """max_tokens defaults to 3000 because reasoning models spend tokens before visible text."""
        if rung not in prompts.RUNGS:
            raise ValueError("unknown rung %r" % (rung,))
        self.model = model
        self.rung = rung
        self.sigma = sigma
        self.parent = parent
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.env_file = env_file
        self.fail_pct = fail_pct
        # Prompt landscape key and noise model; these must match what the oracle applies.
        self.landscape = landscape
        # Opening sentence, a key of prompts.OPENINGS. "grid" is the default wording.
        if opening not in prompts.OPENINGS:
            raise ValueError("unknown opening %r; known: %s" % (opening, sorted(prompts.OPENINGS)))
        self.opening = opening
        # Condition name for logging, set by the caller. Several conditions can share a rung.
        self.cell = None
        self.noise_model = noise_model
        self.cv = cv
        self.noise_floor = noise_floor
        # The anchor's stated reading and the format example, derived from the landscape by the caller.
        self.anchor_reading = anchor_reading
        self.example = example
        # The parser accepts the same alphabet the prompt states.
        self.alphabet = prompts.LANDSCAPES[landscape]["alphabet"]
        # Number of replacement asks stated in the prompt; the caller sets it to the campaign's real cap.
        self.max_reasks_disclosed = 3
        # Optional prompt options, off by default. riskfree_rejection must match
        # campaign.run(riskfree_rejection=...).
        self.goal_true_value = False
        self.fix_replacement_budget = False
        self.riskfree_rejection = False
        # If set, the re-ask names lines dropped for out-of-alphabet letters. Off by default.
        self.truthful_reask = False
        # Optional tools, off by default. `ledger` and `menu` add a computed block after the history;
        # `repeat_cap` states the order limit and must match campaign.run(repeat_cap=...).
        self.ledger = False
        self.menu = False
        self.repeat_cap = None
        # Optional landscape-structure paragraph for every prompt kind, or None.
        self.structure_text = None
        # Re-asks on an unparseable or ambiguous reply, separate from re-asks on a rejected sequence.
        self.parse_retries = 1
        self.parser_disagreements = 0
        self.log = log if log is not None else []
        self.calls = []
        # Resend an identical request after an explicit provider overload. Off by default. Overloaded
        # attempts are kept in `transport_retries`, not in `calls`.
        self.provider_retry = False
        self.transport_retries = []
        self.name = "llm_%s_%s" % (rung, model.replace("/", "_"))

    def _complete(self, prompt, rnd, kind, n_slots):
        """Send one request via llm.complete.

        With provider_retry on, an explicit provider overload is resent up to 5 attempts in all, after
        30, 60, 120 and 240 s. Any other failure returns at once."""
        call = llm.complete(prompt, self.model, max_tokens=self.max_tokens, temperature=self.temperature,
                            env_file=self.env_file, reasoning_effort=self.reasoning_effort)
        if not self.provider_retry:
            return call
        for attempt, wait in enumerate(PROVIDER_RETRY_BACKOFF, 1):
            if call.ok or not provider_unavailable(call):
                return call
            self.transport_retries.append({
                "kind": "transport_retry", "retry_of": kind, "round": rnd, "rung": self.rung, "cell": self.cell,
                "model": self.model, "n_slots": n_slots, "attempt": attempt, "wait_s": wait, "prompt": prompt,
                "raw_payload": call.raw, **call_fields(call)})
            print("      provider unavailable on the %s call, round %s: attempt %d of %d, resending in %d s"
                  % (kind, rnd, attempt + 1, len(PROVIDER_RETRY_BACKOFF) + 1, wait), flush=True)
            time.sleep(wait)
            call = llm.complete(prompt, self.model, max_tokens=self.max_tokens, temperature=self.temperature,
                                env_file=self.env_file, reasoning_effort=self.reasoning_effort)
        return call

    # -- the only thing the model is shown --------------------------------------------------
    def _remaining(self, view):
        """Measurements the agent can still order, accounting for the per-round slot limit."""
        rounds_left = max(0, view.total_rounds - view.current_round + 1)
        return max(0, min(view.slots_total - view.slots_used,
                          rounds_left * view.slots_per_round))

    def _history_rows(self, view):
        return [(o.round, o.seq, o.outcome, o.observed) for o in view.history]

    def replication_slots(self, view):
        return None                        # not known in advance for an LLM policy

    def _tools(self, view):
        rows = self._history_rows(view)
        ledger = tools.ledger_text(rows) if self.ledger else None
        menu = None
        if self.menu:
            cands, ranked = tools.menu(rows, self.parent, self.alphabet, view.campaign_seed, view.current_round)
            menu = tools.menu_text(cands, ranked, prompts.LANDSCAPES[self.landscape]["candidate_word"])
        return ledger, menu

    def round_prompt(self, view, n_slots, exclude=frozenset()):
        """The exact prompt `propose` sends for a round or replacement ask, built from the view alone.

        Also used by the Wellocate environment's text mode to render prompts without a model call."""
        # `exclude` holds sequences just rejected or refused; they are listed in the prompt below.
        _ledger, _menu = self._tools(view)
        # Candidates the repeat cap now refuses. Empty when there is no cap.
        _limit = tools.at_limit(self._history_rows(view), self.repeat_cap) if self.repeat_cap is not None else []
        prompt = prompts.build(
            self.rung, self._history_rows(view), view.current_round, view.total_rounds,
            n_slots, self._remaining(view), self.sigma,
            parent=self.parent, fail_pct=self.fail_pct, total=view.slots_total,
            landscape=self.landscape, noise_model=self.noise_model, cv=self.cv,
            noise_floor=self.noise_floor, anchor_reading=self.anchor_reading,
            example=self.example, max_reasks=self.max_reasks_disclosed, opening=self.opening,
            goal_true_value=self.goal_true_value, riskfree_rejection=self.riskfree_rejection,
            slots_per_round=(view.slots_per_round if self.fix_replacement_budget else None),
            repeat_cap=self.repeat_cap, ledger_text=_ledger, menu_text=_menu,
            at_limit_text=tools.at_limit_text(_limit, prompts.LANDSCAPES[self.landscape]["candidate_word"]),
            structure_text=self.structure_text)
        # Candidates refused by the repeat cap are listed separately from non-viable ones.
        capped_now = set(_limit) & set(exclude)
        nonviable = set(exclude) - capped_now
        if nonviable:
            prompt += ("\n\nThese candidates were just rejected as non-viable and must not be "
                       "proposed again this round: " + ", ".join(sorted(nonviable)) + ".")
        if capped_now:
            prompt += ("\n\nThese candidates have already been ordered the maximum number of times and cannot "
                       "be ordered again: " + ", ".join(sorted(capped_now)) + ".")
        return prompt

    def reask_prompt(self, prompt, notes, n_slots):
        """The prompt after an unparseable reply, with an alphabet note or a format reminder appended."""
        if self.truthful_reask and dropped_for_alphabet(notes):
            return prompt + truthful_reask(dropped_for_alphabet(notes), self.alphabet, n_slots)
        # Default re-ask: append a format reminder.
        return prompt + (
            "\n\nYour previous reply did not contain exactly %d candidates, one per line, in the "
            "form\nCANDIDATE | one short reason\nReply again with exactly %d such lines and "
            "nothing else." % (n_slots, n_slots))

    def propose(self, view, n_slots, exclude=frozenset(), kind="round"):
        prompt = self.round_prompt(view, n_slots, exclude)
        t0 = time.time()
        attempts, call, got, status, notes = 0, None, [], "", []
        # Dropped tokens from every attempt, since `notes` is replaced on each attempt.
        out_of_alphabet = []
        while attempts <= self.parse_retries:
            attempts += 1
            call = self._complete(prompt, view.current_round, kind, n_slots)
            if not call.ok:
                # The call failed: abandon the campaign instead of charging a lost round.
                _raise_transport(self.model, call.error, "round",
                                 failed=dict(round=view.current_round, kind=kind, n_slots=n_slots, attempt=attempts,
                                             prompt=prompt, raw_payload=call.raw, **call_fields(call)))
            got, status, notes = parse(call.text, n_slots, alphabet=self.alphabet)
            out_of_alphabet += dropped_for_alphabet(notes)
            if status == "ok":
                break
            notes.append("re-asked: attempt %d of %d produced status %r"
                         % (attempts, self.parse_retries + 1, status))
            prompt = self.reask_prompt(prompt, notes, n_slots)
        # If the count still does not match, this round spends no slots.
        if status != "ok" and len(got) != n_slots:
            notes.append("spending NO slots this round: %d proposals for %d slots after %d attempts"
                         % (len(got), n_slots, attempts))
            got = []
        second = parse_b(call.text, n_slots, alphabet=self.alphabet) if call.ok else []
        anywhere = candidates_anywhere(call.text, self.alphabet) if call.ok else []
        agree = [g[0] for g in got] == second
        if not agree:
            self.parser_disagreements += 1
        measured = view.measured()
        props = []
        for seq, reason in got:
            props.append(Proposal(view.current_round, seq, reason,
                                  classify(seq, reason, seq in measured),
                                  seq in measured, "%s | %s" % (seq, reason)))
        self.calls.append({
            "round": view.current_round, "rung": self.rung, "cell": self.cell, "model": self.model,
            "prompt_landscape": self.landscape,
            "noise_model": self.noise_model, "cv": self.cv, "noise_floor": self.noise_floor,
            "kind": kind, "n_slots": n_slots, "temperature": self.temperature,
            "sigma": self.sigma, "prompt": prompt, "raw_response": call.text,
            "parse_status": status, "parse_notes": notes, "parse_attempts": attempts,
            "out_of_alphabet": out_of_alphabet,
            # Parsing diagnostics: which pattern matched, legal tokens anywhere in the reply, and the
            # second parser's result.
            "format_tier": next((n.split(": ", 1)[1] for n in notes if n.startswith("format tier")),
                                ""),
            "n_candidates_anywhere": len(anywhere),
            "n_accepted": len(got),
            "parsed_secondary": second,
            "parsers_agree": agree,
            "parsed": [p.seq for p in props], "reasons": [p.reason for p in props],
            "intents": [p.intent for p in props],
            "already_measured": [p.already_measured for p in props],
            # Whole slot, including every re-ask.
            "latency_ms": int(1000 * (time.time() - t0)),
            "n_measured_before": len(measured),
            **call_fields(call)
        })
        self.log.append(self.calls[-1])
        # Never truncated: the list is either exactly n_slots long or empty.
        out = [p.seq for p in props]
        assert len(out) in (0, n_slots), \
            "propose would have truncated %d proposals to %d slots" % (len(out), n_slots)
        return out

    def nomination_prompt(self, view):
        """The exact nomination prompt `nominate` sends, built from the view alone."""
        return prompts.build_nomination(
            self.rung, self._history_rows(view), view.total_rounds, view.slots_per_round,
            self.sigma, parent=self.parent, fail_pct=self.fail_pct, total=view.slots_total,
            landscape=self.landscape, noise_model=self.noise_model, cv=self.cv,
            noise_floor=self.noise_floor, anchor_reading=self.anchor_reading,
            example=self.example, max_reasks=self.max_reasks_disclosed, opening=self.opening,
            riskfree_rejection=self.riskfree_rejection, repeat_cap=self.repeat_cap,
            structure_text=self.structure_text)

    def nominate(self, view):
        """Ask the agent for its own final answer. Returns (seq, reason, call_record)."""
        prompt = self.nomination_prompt(view)
        call = self._complete(prompt, view.total_rounds, "nomination", 1)
        seq, reason, nom_notes = parse_answer(call.text, self.alphabet)
        if not call.ok:
            # Without a nomination the campaign has no outcome, so it is abandoned.
            _raise_transport(self.model, call.error, "nomination",
                             failed=dict(round=view.total_rounds, kind="nomination", n_slots=1, attempt=1,
                                         prompt=prompt, raw_payload=call.raw, **call_fields(call)))
        second_nom = parse_nomination_b(call.text, self.alphabet)
        if second_nom != seq:
            self.parser_disagreements += 1
        rec = {"nominate_notes": nom_notes,
               "parsed_secondary": second_nom, "parsers_agree": (second_nom == seq),
               "round": view.total_rounds, "rung": self.rung, "cell": self.cell, "model": self.model,
               "kind": "nomination", "prompt": prompt, "raw_response": call.text,
               "nominated": seq, "reason": reason, "sigma": self.sigma,
               "parse_status": "ok" if seq else "unparseable", "parse_notes": [],
               "parsed": [seq] if seq else [], "reasons": [reason], "intents": [],
               "already_measured": [], "n_slots": 1, "temperature": self.temperature,
               "latency_ms": call.latency_ms,      # single call
               "n_measured_before": len(view.measured())}
        rec.update(call_fields(call))
        self.calls.append(rec)
        self.log.append(rec)
        return seq, reason, rec

    # -- accounting -------------------------------------------------------------------------
    @property
    def spend_usd(self):
        return sum(c["cost_usd"] for c in self.calls)

    def intent_counts(self):
        c = collections.Counter()
        for call in self.calls:
            c.update(call["intents"])
        return c

    def status_counts(self):
        return collections.Counter(call["parse_status"] for call in self.calls)
