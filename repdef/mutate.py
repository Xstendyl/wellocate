"""Mutation-testing harness: apply one source edit, run the tests, and report whether they catch it.

Three guards make sure the tests run against the mutant and not stale bytecode:
  1. Delete cached bytecode in both the local `__pycache__` and any `sys.pycache_prefix` mirror.
  2. Append a unique trailing comment so the mutant's file size always differs.
  3. Optionally run a canary subprocess that checks the mutation is visible; if not, raise StaleMutant.
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class StaleMutant(Exception):
    """The mutant did not reach the interpreter, so no verdict about it is meaningful."""


class ConcurrentEdit(Exception):
    """The file changed while a mutant was applied, so it is left unrestored to avoid losing that edit."""


def bytecode_paths(source_path):
    """Every path where bytecode for one source file may be cached."""
    src = os.path.abspath(source_path)
    stem = os.path.basename(src)[:-3]
    tag = sys.implementation.cache_tag or "cpython-%d%d" % sys.version_info[:2]
    out = [os.path.join(os.path.dirname(src), "__pycache__", "%s.%s.pyc" % (stem, tag))]
    prefix = sys.pycache_prefix
    if prefix:
        # The mirror is prefix + the source's absolute path, with the leading separator dropped.
        out.append(os.path.join(prefix, src.lstrip(os.sep)[:-3] + ".%s.pyc" % tag))
        out.append(os.path.join(prefix, os.path.dirname(src).lstrip(os.sep),
                                "%s.%s.pyc" % (stem, tag)))
    return out


def clear_bytecode(source_path=None):
    """Remove cached bytecode. With no argument, clear the whole repo's cache in both layouts."""
    if source_path is not None:
        for p in bytecode_paths(source_path):
            if os.path.exists(p):
                os.remove(p)
        return
    for d, dirs, _ in os.walk(REPO):
        if "__pycache__" in dirs:
            shutil.rmtree(os.path.join(d, "__pycache__"), ignore_errors=True)
    prefix = sys.pycache_prefix
    if prefix:
        mirror = os.path.join(prefix, REPO.lstrip(os.sep))
        shutil.rmtree(mirror, ignore_errors=True)


def _env():
    # Do not write bytecode during a mutation run. This does not stop Python reading an existing
    # cache, so clear_bytecode() is still needed.
    return dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def _run(cmd, cwd=REPO, timeout=None):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=_env(),
                          timeout=timeout)


def observe(expr, imports="from repdef import prompts"):
    """Print one value as the interpreter actually sees it, with the cache cleared first."""
    clear_bytecode()
    r = _run([sys.executable, "-B", "-c", "%s\nprint(repr(%s))" % (imports, expr)])
    if r.returncode != 0:
        return "<error: %s>" % r.stderr.strip().splitlines()[-1:]
    return r.stdout.strip()


def check(source_path, old, new, test_cmd, canary=None, expect=None, imports=None, label="",
          timeout=120, extra_edits=()):
    """Reintroduce one bug and report whether `test_cmd` catches it.

    Returns "CAUGHT" or "MISSED". Raises StaleMutant if the canary cannot confirm the mutant was
    loaded, and ValueError if `old` is not present in the file.
    """
    src = os.path.abspath(source_path)
    orig = io.open(src, encoding="utf-8").read()
    if old not in orig:
        raise ValueError("anchor not found in %s: %r" % (source_path, old[:60]))
    # Snapshot per mutant, so edits made between mutants are preserved on restore.
    orig_digest = hashlib.sha256(orig.encode("utf-8")).hexdigest()
    # Guard 2: the trailing comment guarantees a size change even when `new` is as long as `old`.
    mutant = orig.replace(old, new, 1) + "\n# mutation-harness marker %s\n" % (label or "m")
    # A mutant sometimes needs a companion edit elsewhere to be a real bug instead of a TypeError.
    companions = []
    for (cpath, cold, cnew) in extra_edits:
        cabs = os.path.abspath(cpath)
        if cabs == src:
            # A companion edit to the same file is applied to the mutant text, not re-read from disk.
            if cold not in mutant:
                raise ValueError("companion anchor not found in the mutant of %s: %r"
                                 % (cpath, cold[:60]))
            mutant = mutant.replace(cold, cnew, 1)
            continue
        ctext = io.open(cabs, encoding="utf-8").read()
        if cold not in ctext:
            raise ValueError("companion anchor not found in %s: %r" % (cpath, cold[:60]))
        companions.append((cabs, ctext, ctext.replace(cold, cnew, 1)))
    try:
        io.open(src, "w", encoding="utf-8").write(mutant)
        for cabs, _ctext, cmut in companions:
            io.open(cabs, "w", encoding="utf-8").write(cmut)
        clear_bytecode()                                    # guard 1
        if canary is not None:                              # guard 3
            got = observe(canary, imports or "from repdef import prompts")
            if expect is not None and repr(expect) != got:
                raise StaleMutant(
                    "mutant %r did not reach the interpreter: %s is %s, expected %r"
                    % (label or old[:40], canary, got, expect))
        try:
            rc = _run([sys.executable, "-B", "-m", "unittest"] + list(test_cmd),
                      timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            # A mutant that makes the suite hang counts as caught, reported as a distinct outcome.
            return "CAUGHT (hang)"
        return "CAUGHT" if rc != 0 else "MISSED"
    finally:
        for cabs, ctext, cmut in companions:
            if io.open(cabs, encoding="utf-8").read() == cmut:
                io.open(cabs, "w", encoding="utf-8").write(ctext)
        # Restore only if the file still holds the mutant (or the original); otherwise another
        # writer changed it.
        now = io.open(src, encoding="utf-8").read()
        if now == mutant or hashlib.sha256(now.encode("utf-8")).hexdigest() == orig_digest:
            io.open(src, "w", encoding="utf-8").write(orig)
        else:
            clear_bytecode()
            raise ConcurrentEdit(
                "%s changed while mutant %r was applied, so it was NOT restored. The file on disk "
                "is neither the original nor the mutant; inspect it before trusting any verdict."
                % (source_path, label or old[:40]))
        clear_bytecode()


def baseline(test_cmd):
    """Run the suite unmutated. Returns (passed, output); it must pass before mutations mean anything."""
    clear_bytecode()
    r = _run([sys.executable, "-B", "-m", "unittest"] + list(test_cmd))
    return r.returncode == 0, r.stdout + r.stderr
