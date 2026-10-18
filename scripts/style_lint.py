#!/usr/bin/env python3
"""Fail the build on writing patterns the paper does not use.

Scans the default paper draft files, plus any file given on the command line (e.g. the LaTeX). Fenced code
blocks, inline code spans and quotations are skipped, so verbatim quotations go in a fence or in backticks.
Sentence length is capped at 30 words in main-text sections only; a heading containing "appendix" opens appendix
scope, which closes at the next heading of the same or higher level that does not.

Usage:
  python3 scripts/style_lint.py                  # the default draft files
  python3 scripts/style_lint.py path [path ...]  # named files, e.g. the LaTeX
  python3 scripts/style_lint.py --stats          # also print a length histogram
Exit code 1 on any hit.
"""
import glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_WORDS = 30

# Each rule: (name, compiled pattern, what to do instead). The patterns match on a line with code and
# quotations removed. A name in MAIN_TEXT_ONLY is checked only outside appendix sections, and a name in
# ADVISORY is reported without failing the run.
MAIN_TEXT_ONLY = {"process narration"}
# ADVISORY holds rules that need a human judgement (e.g. whether a triplet adds content).
ADVISORY = {"rhythm triplet", "passive voice", "unchecked invariance"}
RULES = [
    ("contrast framing", re.compile(
        r"\b(?:it\s+is|it's|this\s+is|that\s+is|they\s+are|these\s+are)\s+not\s+\w[\w\s,'-]{0,40}?,\s*(?:it|this|that|they|these)\s+(?:is|are)\b"
        r"|\bnot\s+just\s+\w[\w\s'-]{0,30}?\s+but\b"
        r"|\bmore\s+than\s+just\b"
        r"|\bless\s+\w+\s+and\s+more\s+\w+\b"
        r"|\bis\s?n[o']t\s+about\s+\w[\w\s'-]{0,40}?,\s*it(?:'s|\s+is)\s+about\b"
        # The same move survives a full stop, which is how it gets past a one-line comma pattern:
        # "That decision is not about chemistry. It is about how to buy information."
        r"|\b(?:is|was|are|were)\s+not\s+(?:about\s+)?[\w\s'-]{1,40}?\.\s+(?:It|This|That|They|These)"
        r"\s+(?:is|are|was|were)\s+", re.I),
     "state the fact directly"),
    ("X, not Y", re.compile(
        # The comma follows the word with no space before it.
        r"(?<![\d)]),\s+(?:and\s+)?not\s+(?!only\b)(?!at\s+all\b)[a-z\"'`(]", re.I),
     "state the positive claim alone, in its own sentence"),
    ("and not Y", re.compile(
        # The antithesis without its comma: "a sizing figure is an estimate and not a number".
        r"\band\s+not\s+(?:a|an|the|its|his|her|their|our|merely|simply|only)\b", re.I),
     "state the positive claim alone"),
    ("rather than", re.compile(r"\brather\s+than\b", re.I), "name the thing you mean"),
    ("em or en dash", re.compile(r"[—–]"), "use a full stop, comma or colon"),
    ("rhetorical question", re.compile(r"\?"), "ask nothing; say the answer"),
    ("reveal opener", re.compile(
        r"\b(?:the\s+result\?|here'?s\s+the\s+thing|so\s+what\s+does\s+this\s+mean|but\s+here'?s)\b", re.I),
     "delete the opener and keep the sentence"),
    ("hype or filler", re.compile(
        r"\b(?:crucial|crucially|importantly|notably|remarkably|pivotal|seamless|seamlessly|delve|delves|"
        r"delving|underscore|underscores|underscoring|leverage|leverages|leveraging|showcase|showcases|"
        r"showcasing|realm|paramount|furthermore|moreover|interestingly)\b"
        r"|\bit\s+is\s+worth\s+noting\b", re.I),
     "delete it, or replace it with the fact"),
    ("robust as praise", re.compile(
        r"\brobust(?:ly)?\b(?!\s+to\b)|\brobustness\b(?!\s+(?:check|checks|analysis|analyses|panel|result|results)\b)",
        re.I),
     "say what holds and under what change"),
    ("landscape as metaphor", re.compile(
        r"\b(?:current|competitive|research|evolving|changing|broader|wider)\s+landscape\b"
        r"|\blandscape\s+of\s+(?:research|work|benchmarks|models|tools|agents)\b", re.I),
     "reserve 'landscape' for the NK landscape"),
    ("vague quantity", re.compile(
        # "how many" asks for a number and "as many" compares two stated ones, so neither is vague.
        r"\b(?<!how )(?<!as )(?:many|several|numerous|various|a\s+handful\s+of|a\s+number\s+of|plenty\s+of|"
        r"a\s+lot\s+of|quite\s+a\s+few|a\s+great\s+deal|substantial|considerable)\b"
        # "significant" is vague only before a noun ("a significant increase"), so it is caught only when a
        # word other than a conjunction or a preposition follows it.
        r"|\bsignificant(?=\s+(?!(?:and|or|but|after|at|under|in|for|with|by|on)\b)[a-z])", re.I),
     "give the number, as in '24% of orders'"),
    ("process narration", re.compile(
        # Change-history wording belongs in an appendix, so this rule is main-text only.
        r"\b(?:I|we)\s+(?:fixed|found|discovered|rewrote|repaired|noticed|corrected|caught|missed|"
        r"realised|realized|spotted|broke)\b"
        r"|\bon\s+20\d\d-\d\d-\d\d\b"
        r"|\bcommit\s+`?[0-9a-f]{7,40}`?", re.I),
     "move it to the appendix"),
    ("rhythm triplet", re.compile(
        # Three bare single-word items in a row. Advisory: whether they add content is a judgement.
        r"\b([a-z]{3,}),\s+([a-z]{3,}),?\s+and\s+([a-z]{3,})\b(?!\s*\()", re.I),
     "keep the items that carry content and delete the rest"),
    ("unchecked invariance", re.compile(
        # Invariance claims. Advisory, because some are true and measured; the rule points at the sentence
        # so the number behind it can be checked.
        r"\b(?:nearly|almost)\s+(?:everywhere|always|never|all)\b"
        r"|\b(?:everywhere|always|never|invariably|uniformly|consistently)\b\s*(?:,|\.|$)"
        r"|\bin\s+every\s+(?:case|setting|cell|condition)\b"
        r"|\bdoes\s+not\s+vary\b|\bthe\s+same\s+(?:everywhere|throughout)\b", re.I),
     "give the range you measured, or drop the claim"),
    ("passive voice", re.compile(
        # Agentless passive with no "by". Advisory, because a methods sentence is sometimes right in the
        # passive and a blind rewrite makes it worse.
        r"\b(?:was|were|is|are|been|being)\s+(?:[a-z]+ly\s+)?(?:observed|performed|conducted|carried\s+out|"
        r"undertaken|noted|seen|shown|demonstrated|found\s+to\s+be)\b(?!\s+by\b)", re.I),
     "name the actor: 'agents re-ordered'"),
    # Scaffolding: a sentence whose whole job is to tell the reader that the next sentence matters.
    ("empty deixis", re.compile(
        r"\b(?:That|This|It)\s+matters(?:\s+here)?\s*\."
        r"|\bworth\s+(?:stating|noting|mentioning|saying)\b"
        r"|\bit\s+is\s+(?:important|worth)\s+to\s+(?:note|say|state)\b"
        r"|\bnote\s+that\b", re.I),
     "delete it and let the next sentence carry itself, or say the thing"),
    ("self-reference as emphasis", re.compile(
        r"\b(?:exactly|precisely)\s+the\s+\w+\s+(?:this|the)\s+paper\b"
        r"|\bwhat\s+this\s+paper\s+is\s+about\b", re.I),
     "name the quantity; the reader knows what the paper is about"),
    ("negated claim", re.compile(
        r"\b(?:That|This)\s+\w+\s+is\s+not\s+\w",
        re.I), "state what IS the case; the negation leaves the reader to guess"),
    # The good-at / poor-at pairing, a form of the corrective antithesis.
    ("good-at / poor-at antithesis", re.compile(
        r"\b(?:good|decent|strong|better|best|reliable|capable)\s+at\b[^.]{0,140}?"
        r"\b(?:poor|bad|worse|worst|weak|weakest|unreliable|incapable)\s+at\b"
        r"|\b(?:poor|bad|worse|worst|weak|weakest|unreliable|incapable)\s+at\b[^.]{0,140}?"
        r"\b(?:good|decent|strong|better|best|reliable|capable)\s+at\b", re.I),
     "state the capability you mean; the second half only negates the first"),
    # Fragment lists: an enumerating lead-in ("We contribute five things.") and a sentence opening with a
    # conjunction, which is how the last item of such a list looks.
    ("enumerating lead-in", re.compile(
        r"\bWe\s+(?:contribute|make|offer|present|provide)\s+"
        r"(?:two|three|four|five|six|seven|\d+)\s+(?:things|contributions|items)\b", re.I),
     "write the contributions as sentences; the count is not a contribution"),
    # Only "And": a complete sentence opening with "But" is ordinary English.
    ("sentence opens with a conjunction", re.compile(
        r"(?:(?<=\.\s)|(?<=\.\s\s)|^)And\s+[a-z]"),
     "join it to the sentence before, or make it a sentence"),
    ("slogan or chiasmus", re.compile(
        r"\bwhich\s+is\s+the\s+whole\s+point\b|\bthis\s+is\s+what\s+makes\b|\bIn\s+words:"
        r"|;\s*the\s+reverse\s+does\s+not\b|\bthe\s+reverse\s+is\s+not\s+true\b", re.I),
     "cut the line; the fact above it already says this"),
]

# Headings get their own rules, applied to the heading text before `blank_quotes_and_code` blanks it.
HEADING_RULES = [
    ("heading asks a question", re.compile(r"\?"),
     "a heading states what the paragraph shows; ask nothing"),
    ("heading as slogan", re.compile(r"\bis\s+the\s+(?:skill|point|key|answer|reason|whole\s+story)\b",
                                     re.I),
     "name the finding the paragraph supports"),
    ("heading states a negative", re.compile(r"\b(?:is|are|was|were|does|do|did)\s+not\b"
                                             r"|\bnot\s+(?:trivial|easy|hard|simple|obvious|new)\b", re.I),
     "state the positive claim the paragraph supports"),
    ("heading echoes itself", re.compile(r",\s+and\s+so\s+(?:are|is|do|does|was|were)\b", re.I),
     "say the claim once; a later paragraph can make the second half"),
    # A caption is exempt from this one: a figure caption is meant to be several sentences.
    ("two sentences in a heading", re.compile(r"\.\s+\S"),
     "a heading is one phrase; move the second sentence into the body"),
]
HEADING_RULES_NOT_FOR_CAPTIONS = {"two sentences in a heading"}

CODE_SPAN = re.compile(r"`[^`]*`")
# Quoted spans are removed before the wording rules run and do not count toward the sentence cap, since
# a verbatim quotation cannot be reworded. `tests/test_the_related_work_quotes_are_real.py` checks every
# quote against its source.
# LaTeX heading macros. Their text is structure, not prose: "\\paragraph{Is the environment too easy?}"
# is an ordinary academic heading and not the reveal the rhetorical-question rule exists to catch.
HEADING_MACRO = re.compile(r"\\(?:section|subsection|subsubsection|paragraph|subparagraph|title|caption)"
                           r"\*?\{[^{}]*\}")
QUOTED = re.compile(r"\"[^\"]{2,400}?\"|“[^”]{2,400}?”")
# LaTeX writes a quotation as ``...''. It is blanked first, before CODE_SPAN can read the opening `` as an
# empty code span.
LATEX_QUOTED = re.compile(r"``[^`']{2,400}?''")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
# An explicit marker for sections that are appendix material whatever their heading says.
SCOPE_MARK = re.compile(r"<!--\s*lint-scope:\s*(appendix|main)\s*-->"
                        # The LaTeX form, and `\appendix` itself, which is what a .tex file uses to say
                        # that everything after it is appendix material.
                        r"|%\s*lint-scope:\s*(appendix|main)\b"
                        r"|(\\appendix)\b")
# A sentence ends at . ! or ? followed by space and a capital, a digit (bolded or not), a quote, a bracket,
# a LaTeX macro or maths, or at end of line.
SENT_END = re.compile(r"(?<=[A-Za-z0-9\)\]\}\$\"'%*])[.!?]\**\}*(?=\s+\**[\"'(A-Z0-9\\$]|\s*$)")
SKIP_LINE = re.compile(r"^\s*(?:\||:?-{3,}|\*Written|<!--"
                       # LaTeX scaffolding, including tabular bodies, is not prose.
                       r"|\\(?:begin|end|toprule|midrule|bottomrule|cmidrule|includegraphics|label"
                       r"|centering|small|footnotesize|bibliography|input|maketitle|appendix|graphicspath"
                       r"|usepackage|documentclass|title|author|date|newcommand|setlength|captionsetup)\b"
                       r"|%)")
# A tabular row: cells separated by & and ended with \\.
TABLE_ROW = re.compile(r"&.*\\\\\s*$")
# A list item is its own unit, so items are not joined across lines.
LIST_ITEM = re.compile(r"^\s*(?:[-*+]\s+|\d+\.\s+|>\s*[-*+]\s+|>\s*\d+\.\s+)")


def blank_quotes_and_code(text):
    """Blank out inline code and quotations across the whole file, keeping every line number.

    The whole text is processed at once because a quotation can wrap across lines.
    """
    def blank(m):
        # An uppercase 'X' run keeps sentence boundaries intact, matches no rule, and counts as one word.
        return "".join("\n" if c == "\n" else "X" for c in m.group(0))
    text = HEADING_MACRO.sub(blank, text)
    text = LATEX_QUOTED.sub(blank, text)
    text = CODE_SPAN.sub(blank, text)
    return QUOTED.sub(blank, text)


def scan(path, appendix_too=False):
    """(rule hits, long sentences) for one file. `appendix_too` also length-checks appendix sections."""
    hits, advice, longs, lengths = [], [], [], []
    # The joined sentence is scanned too, so a phrase that wraps across lines is caught; a match already
    # reported from the line pass is not reported twice.
    seen = set()
    fenced = False
    appendix_depth = None      # heading level that opened appendix scope
    in_appendix = False
    buf, buf_raw, buf_line = [], [], None
    original = open(path).read()
    lines = blank_quotes_and_code(original).splitlines()
    raw_lines = original.splitlines()

    def flush():
        """Close the sentence buffer: wording rules everywhere, the length cap in main text only."""
        if not buf:
            return
        length_ok = not (in_appendix and not appendix_too)
        text = " ".join(buf).strip()
        shown = " ".join(buf_raw).strip()
        del buf[:]
        del buf_raw[:]
        pieces = [p.strip() for p in SENT_END.split(text)]
        shown_pieces = [p.strip() for p in SENT_END.split(shown)]
        for k, piece in enumerate(pieces):
            if not piece:
                continue
            for name, pat, fix in RULES:
                if name in MAIN_TEXT_ONLY and in_appendix:
                    continue
                for m in pat.finditer(piece):
                    key = (name, " ".join(m.group(0).split()).lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    a, b = max(0, m.start() - 45), min(len(piece), m.end() + 45)
                    (advice if name in ADVISORY else hits).append(
                        (buf_line, name, fix, piece[a:b].strip()))
            if not length_ok:
                continue
            toks = piece.split()
            placeholders = sum(1 for t in toks if set(t) <= set("X.,;:)('\"*"))
            n = len(toks) - placeholders
            lengths.append(n)
            if n > MAX_WORDS:
                # The raw text can split into a different number of pieces than the blanked text; when
                # the indexes do not line up, show the blanked piece.
                disp = shown_pieces[k] if k < len(shown_pieces) and shown_pieces[k] else piece
                if len(shown_pieces) != len(pieces):
                    disp = piece
                longs.append((buf_line, n, placeholders, disp))

    # Heading text, read from the original line, because the blanked copy has none left.
    for i, raw in enumerate(raw_lines, 1):
        for hm in HEADING_MACRO.finditer(raw):
            inner = hm.group(0).split("{", 1)[1].rstrip("}")
            is_caption = hm.group(0).startswith("\\caption")
            for name, pat, fix in HEADING_RULES:
                if is_caption and name in HEADING_RULES_NOT_FOR_CAPTIONS:
                    continue
                for m in pat.finditer(inner):
                    hits.append((i, name, fix, inner.strip()))
                    break                       # one report per heading per rule

    for i, raw in enumerate(lines, 1):
        if raw.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        sm = SCOPE_MARK.search(raw)
        if sm:
            flush()
            got = sm.group(1) or sm.group(2) or ("appendix" if sm.group(3) else "main")
            in_appendix = (got == "appendix")
            appendix_depth = 0 if in_appendix else None
            continue
        h = HEADING.match(raw)
        if h:
            flush()
            level, title = len(h.group(1)), h.group(2)
            if re.search(r"appendix", title, re.I):
                in_appendix, appendix_depth = True, level
            elif in_appendix and level <= appendix_depth:
                in_appendix, appendix_depth = False, None
            continue
        line = raw
        for name, pat, fix in RULES:
            if name in MAIN_TEXT_ONLY and in_appendix:
                continue
            for m in pat.finditer(line):
                a, b = max(0, m.start() - 45), min(len(line), m.end() + 45)
                src = raw_lines[i - 1] if i - 1 < len(raw_lines) else line
                key = (name, " ".join(m.group(0).split()).lower())
                if key in seen:
                    continue
                seen.add(key)
                (advice if name in ADVISORY else hits).append((i, name, fix, src[a:b].strip()))
        if not raw.strip():
            flush()
            continue
        if SKIP_LINE.match(raw) or TABLE_ROW.search(raw):
            flush()
            continue
        if LIST_ITEM.match(raw):
            flush()
        if not buf:
            buf_line = i
        strip_marks = r"^>\s?|^[-*]\s+|^\d+\.\s+"
        buf.append(re.sub(strip_marks, "", line).strip())
        buf_raw.append(re.sub(strip_marks, "", raw_lines[i - 1]).strip())
    flush()
    return hits, advice, longs, lengths


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    stats = "--stats" in sys.argv
    # --appendix also reports over-cap sentences in appendix sections, as advice only.
    appendix_too = "--appendix" in sys.argv
    paths = args or sorted(glob.glob(os.path.join(ROOT, "spec", "PAPER_*.md")))
    total_hits = total_long = total_advice = 0
    averages = []
    print("=" * 100)
    print("STYLE LINT   %d file(s)   sentence cap %d words in %s"
          % (len(paths), MAX_WORDS, "EVERY section (--appendix)" if appendix_too else "main-text sections"))
    print("=" * 100)
    allnums = []
    for p in paths:
        hits, advice, longs, lengths = scan(p, appendix_too)
        allnums += [n for _l, n, _q, _s in longs]
        if lengths:
            avg = sum(lengths) / float(len(lengths))
            averages.append((os.path.relpath(p, ROOT), avg, len(lengths)))
        if not hits and not longs and not advice:
            continue
        rel = os.path.relpath(p, ROOT)
        print("\n%s" % rel)
        for line, name, fix, frag in hits:
            print("  %s:%d  %-22s %s" % (rel, line, name, frag))
            print("  %s  -> %s" % (" " * (len(rel) + len(str(line)) + 1), fix))
        for line, n, q, sent in longs:
            note = "%d words" % n if not q else "%d own words, %d quotation(s) excluded" % (n, q)
            print("  %s:%d  %-22s %s: %s" % (rel, line, "sentence over cap", note, sent))
        for line, name, fix, frag in advice:
            print("  %s:%d  %-22s %s" % (rel, line, name + " (advisory)", frag))
            print("  %s  -> %s" % (" " * (len(rel) + len(str(line)) + 1), fix))
        total_hits += len(hits)
        total_long += len(longs)
        total_advice += len(advice)
    print("\n" + "=" * 100)
    if stats and allnums:
        allnums.sort()
        print("  main-text sentences over the cap: %d, longest %d words" % (len(allnums), allnums[-1]))
    if averages:
        print("  average sentence length in main-text sections (target 15 to 20 words)")
        for rel, avg, n in sorted(averages, key=lambda r: -r[1]):
            flag = "" if 15.0 <= avg <= 20.0 else "   OUTSIDE 15-20"
            print("    %-44s %5.1f words over %4d sentences%s" % (rel, avg, n, flag))
        allw = [a * n for _r, a, n in averages]
        alln = sum(n for _r, _a, n in averages)
        print("    %-44s %5.1f words over %4d sentences" % ("ALL FILES", sum(allw) / alln, alln))
    print("  %d banned-pattern hit(s), %d sentence(s) over %d words, %d advisory"
          % (total_hits, total_long, MAX_WORDS, total_advice))
    if total_hits or total_long:
        print("  BAR IS ZERO. Fix every line above before a draft leaves this machine.")
        return 1
    print("  clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
