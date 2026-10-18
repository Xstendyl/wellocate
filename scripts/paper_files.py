"""Which .tex files make up the paper, read from the \\input lines of paper/main.tex.

  parts()      {"preamble": [...], "main": [...], "appendix": [...]}: the files each part \\inputs, nested inputs
               (the generated tables) in place, as paths relative to paper/
  text(part)   the files of one part joined in reading order, comments kept
  orphans()    .tex files under paper/ that main.tex never reaches
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "paper")
MAIN_TEX = "main.tex"
INPUT = re.compile(r"\\input\{([^}]+)\}")
# Only an unescaped % starts a comment, so a commented-out \input is not part of the paper.
COMMENT = re.compile(r"(?<!\\)%.*")


def _read(rel):
    with open(os.path.join(PAPER, rel)) as f:
        return f.read()


def _inputs(src):
    return [n if n.endswith(".tex") else n + ".tex" for n in INPUT.findall(COMMENT.sub("", src))]


def _expand(rel, seen):
    """rel and every file it \\inputs, depth first, in reading order."""
    if rel in seen:
        raise SystemExit("REFUSED: %s is \\input twice, or inputs itself" % rel)
    if not os.path.exists(os.path.join(PAPER, rel)):
        raise SystemExit("REFUSED: the paper inputs %s, which does not exist" % rel)
    seen.add(rel)
    out = [rel]
    for child in _inputs(_read(rel)):
        out += _expand(child, seen)
    return out


def parts():
    src = COMMENT.sub("", _read(MAIN_TEX))
    begin = src.index("\\begin{document}")
    split = re.search(r"\\appendix(?![A-Za-z])", src)
    if split is None:
        raise SystemExit("REFUSED: main.tex has no \\appendix")
    seen = set()
    out = {}
    for part, chunk in (("preamble", src[:begin]), ("main", src[begin:split.start()]),
                        ("appendix", src[split.end():])):
        out[part] = [f for rel in _inputs(chunk) for f in _expand(rel, seen)]
    return out


def text(part):
    return "\n".join(_read(rel) for rel in parts()[part])


def orphans():
    reached = {MAIN_TEX} | {f for files in parts().values() for f in files}
    found = []
    for root, _dirs, files in os.walk(PAPER):
        for f in files:
            if f.endswith(".tex"):
                rel = os.path.relpath(os.path.join(root, f), PAPER)
                if rel not in reached:
                    found.append(rel)
    return sorted(found)
