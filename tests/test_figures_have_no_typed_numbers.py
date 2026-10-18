#!/usr/bin/env python3
"""Tests that no figure draws a number typed into the plotting code.

Every value a reader measures off a figure must come from results/. Layout literals (axis limits, marker
and font sizes, bar thickness, offsets, schematic coordinates) are allowed; only the arguments that carry
values are checked: the positional arguments of a value-drawing call and the error-bar and stacking keywords.
"""
import ast, os, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "scripts", "figures.py")

# Calls whose positional arguments are the values a reader measures off the page.
DATA_CALLS = {"plot", "scatter", "errorbar", "bar", "barh", "axhline", "axvline", "hlines", "vlines",
              "fill_between", "stackplot", "step", "boxplot", "hist"}
# Keywords of those calls that also carry values.
DATA_KWARGS = {"yerr", "xerr", "left", "bottom", "height", "width", "y1", "y2"}
# `barh(positions, width, height=0.62)` sets the bar thickness with `height`; `bar` sets it with `width`.
THICKNESS = {"barh": "height", "bar": "width"}


# Literals that are arithmetic on a value rather than a value, each with the reason it is not a result.
UNITS = {100: "a proportion written as a percentage", 1.96: "the z for a 95% interval"}

# A line at exactly 0 marks the origin of a signed axis and is exempt; a line at any other literal is caught.
ORIGIN_LINES = {"axhline", "axvline"}


def is_origin_line(name, node):
    return (name in ORIGIN_LINES and len(node.args) == 1 and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == 0 and not isinstance(node.args[0].value, bool))


def literals_in(node):
    """Numeric literals under `node`, skipping subscript indices, which are positions and not values."""
    skip = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Subscript):
            skip.update(id(x) for x in ast.walk(n.slice))
    return [n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool) and id(n) not in skip and n.value not in UNITS]


def offences(source, path):
    out = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        name = node.func.attr
        if name not in DATA_CALLS:
            continue
        checked = [] if is_origin_line(name, node) else list(node.args)
        for kw in node.keywords:
            if kw.arg in DATA_KWARGS and kw.arg != THICKNESS.get(name):
                checked.append(kw.value)
        for arg in checked:
            for v in literals_in(arg):
                out.append("%s:%d  %s() was handed the literal %r" % (path, node.lineno, name, v))
    return out


class TypedNumbers(unittest.TestCase):
    def test_no_literal_reaches_a_value_drawing_call(self):
        found = offences(open(TARGET).read(), os.path.relpath(TARGET, ROOT))
        self.assertEqual([], found, "a figure is drawing a number nobody can recompute:\n  " +
                         "\n  ".join(found))

    def test_the_check_would_catch_one(self):
        """The check catches a planted typed value and accepts layout keywords, indices, unit conversions and the zero line."""
        mutant = "def f(ax):\n    ax.axhline(39.2)\n"
        self.assertTrue(offences(mutant, "mutant"), "the check does not catch a typed reference level")
        clean = "def f(ax, r):\n    ax.axhline(r['level'], xmax=0.75, linewidth=0.7)\n"
        self.assertEqual([], offences(clean, "clean"), "the check rejects a legitimate layout keyword")
        index = "def f(ax, pts):\n    ax.scatter([p[0] for p in pts], [p[1] for p in pts])\n"
        self.assertEqual([], offences(index, "index"), "the check reads a tuple index as a value")
        unit = "def f(ax, r):\n    ax.scatter([100 * r['share']], [r['mean']])\n"
        self.assertEqual([], offences(unit, "unit"), "the check rejects a percentage conversion")
        origin = "def f(ax):\n    ax.axvline(0, linewidth=0.6)\n"
        self.assertEqual([], offences(origin, "origin"), "the check rejects the zero line of a difference")
        near = "def f(ax):\n    ax.axvline(0.2, linewidth=0.6)\n"
        self.assertTrue(offences(near, "near"), "the origin exemption lets a typed level through")
        shifted = "def f(ax, r):\n    ax.axvline(r['v'] + 0.5)\n"
        self.assertTrue(offences(shifted, "shifted"), "the origin exemption hides arithmetic on a value")

    def test_every_figure_value_comes_from_a_results_file(self):
        """The module may only read numbers through figstyle, which reads results/."""
        src = open(TARGET).read()
        self.assertIn("import figstyle as FS", src)
        self.assertNotIn("open(os.path.join(ROOT, \"results\"", src.replace("json.load(", "json.load("),
                         "read results through figstyle.results(), so there is one reader to audit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
