#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reject identifiers that Plex's RestrictedPython refuses to compile.

Plex compiles plug-in modules with RestrictedPython. Any *bound* name starting
with an underscore (except dunder methods such as ``__init__``) aborts the
whole bundle at start-up::

    SyntaxError: Line 239: "_BADGE_TOKEN" is an invalid variable name
                 because it starts with "_"
    Exception starting plug-in

``python3 -m py_compile`` cannot catch this: it is perfectly valid Python.
This check runs in CI before a bundle is zipped, so a broken build never
becomes a Release. It uses the AST, so strings/comments that merely mention a
forbidden name (e.g. an explanatory comment) are not false positives.

Usage::

    python3 scripts/check_plex_sandbox.py --self-test
    python3 scripts/check_plex_sandbox.py                 # scan every bundle
    python3 scripts/check_plex_sandbox.py FILE.py ...    # scan given files
"""
import ast
import glob
import io
import os
import re
import sys
import tempfile

# Special methods/attributes are legal and required (every plug-in class has
# __init__). Only names starting with a single underscore, or non-dunder
# double-underscore private names, are rejected by RestrictedPython.
DUNDER = re.compile(r'^__[A-Za-z0-9_]*__$')


class Visitor(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.hits = []

    def add(self, node, name, kind):
        if name and name.startswith('_') and not DUNDER.match(name):
            self.hits.append((self.path, getattr(node, 'lineno', 0),
                              name, kind))

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.add(node, node.id, 'assignment')
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.add(node, node.name, 'function')
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.add(node, node.name, 'class')
        self.generic_visit(node)

    def visit_arg(self, node):
        self.add(node, node.arg, 'argument')
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.add(node, alias.asname, 'import alias')
        self.generic_visit(node)

    visit_ImportFrom = visit_Import

    def visit_ExceptHandler(self, node):
        self.add(node, node.name, 'except alias')
        self.generic_visit(node)


def scan_file(path):
    with io.open(path, encoding='utf-8') as fh:
        source = fh.read()
    visitor = Visitor(path)
    visitor.visit(ast.parse(source, filename=path))
    return visitor.hits


GOOD_SAMPLE = '''\
# Dunder methods and reading __name__ are perfectly legal in a Plex plug-in.
BADGE_TOKEN_PATTERN = r'(U|C)'

class Provider(object):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

print(__name__)
'''

BAD_SAMPLE = '''\
_BADGE_TOKEN = r'(U|C)'
_TOOL_TOKEN = 1
_ = 1

def _helper(_arg):
    return _arg

class _Private(object):
    pass

import os as _os
from sys import version_info as _vi
'''

EXPECTED_BAD = set(['_BADGE_TOKEN', '_TOOL_TOKEN', '_', '_helper', '_arg',
                    '_Private', '_os', '_vi'])


def self_test():
    """Prove the checker catches bad names without flagging legal dunders."""
    tmp = tempfile.mkdtemp(prefix='plex-sandbox-')
    try:
        good = os.path.join(tmp, 'good.py')
        bad = os.path.join(tmp, 'bad.py')
        with io.open(good, 'w', encoding='utf-8') as fh:
            fh.write(GOOD_SAMPLE)
        with io.open(bad, 'w', encoding='utf-8') as fh:
            fh.write(BAD_SAMPLE)
        good_hits = scan_file(good)
        bad_hits = scan_file(bad)
        bad_names = set(hit[2] for hit in bad_hits)
        if good_hits:
            sys.stderr.write('FAIL: clean sample was flagged: %r\n' % good_hits)
            return False
        if not EXPECTED_BAD <= bad_names:
            sys.stderr.write('FAIL: missed bad names: %r\n'
                             % sorted(EXPECTED_BAD - bad_names))
            return False
        print('OK: self-test clean sample passes, %d/%d forbidden names caught'
              % (len(bad_names), len(EXPECTED_BAD)))
        return True
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def default_paths():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return sorted(glob.glob(os.path.join(root, '*.bundle', 'Contents',
                                         'Code', '*.py')))


def main(argv):
    args = list(argv)
    if '--self-test' in args:
        return 0 if self_test() else 1
    paths = [a for a in args if not a.startswith('-')] or default_paths()
    if not paths:
        sys.stderr.write('FAIL: no plug-in Python files found\n')
        return 1

    hits = []
    errors = []
    for path in paths:
        try:
            hits.extend(scan_file(path))
        except (SyntaxError, IOError, OSError) as exc:
            errors.append('%s: %s' % (path, exc))
    for path, lineno, name, kind in hits:
        sys.stderr.write('FAIL %s:%d: %s (%s)\n'
                         % (path, lineno, name, kind))
    for error in errors:
        sys.stderr.write('FAIL %s\n' % error)
    if hits or errors:
        sys.stderr.write(
            'FAIL: %d forbidden name(s), %d file error(s) - Plex would '
            'refuse to start this bundle.\n' % (len(hits), len(errors)))
        return 1
    print('OK: %d file(s) scanned, no RestrictedPython underscore names'
          % len(paths))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
