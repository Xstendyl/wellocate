"""The one way a generator writes into paper/: only when told to, with --write-paper.

  (no flag)        render and print to stdout; nothing is written
  --out PATH       write the rendered text to PATH, refused if PATH is inside paper/
  --write-paper    write the generator's own file in paper/
  --list           print only the macro names and values (make_paper_numbers.py)
  anything else    refused: argparse exits with an error before anything is rendered

scripts/verify_paper_numbers.py compares each generator's render() with the file in paper/ and never writes, and
scripts/build_paper.py passes --write-paper to the generators it runs.
"""
import argparse, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "paper")


def inside_paper(path):
    p = os.path.realpath(os.path.abspath(path))
    return p == os.path.realpath(PAPER) or p.startswith(os.path.realpath(PAPER) + os.sep)


def run(prog, dst, render, argv=None, lister=None):
    rel = os.path.relpath(dst, ROOT)
    ap = argparse.ArgumentParser(prog=os.path.basename(prog),
                                 description="Render %s. Nothing is written unless --write-paper or --out is given."
                                             % rel)
    ap.add_argument("--write-paper", action="store_true", help="write %s" % rel)
    ap.add_argument("--out", default="", help="write the rendered text to this path (never inside paper/)")
    if lister is not None:
        ap.add_argument("--list", action="store_true", help="print the macro names and values only")
    a = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if a.write_paper and a.out:
        ap.error("--write-paper and --out are exclusive")
    if lister is not None and a.list:
        sys.stdout.write(lister())
        return 0
    text = render()
    if a.write_paper:
        with open(dst, "w") as f:
            f.write(text)
        print("wrote %s" % rel)
        return 0
    if a.out:
        if inside_paper(a.out):
            ap.error("--out %s is inside paper/; pass --write-paper to write %s" % (a.out, rel))
        with open(a.out, "w") as f:
            f.write(text)
        print("wrote %s (paper/ untouched)" % a.out)
        return 0
    sys.stdout.write(text)
    return 0
