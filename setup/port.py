#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


import subprocess
import sys

from setup import Command


class To6(Command):

    description = 'Toggle between the Qt6 and master branches building everything needed'

    def ccall(self, *a):
        self.info(*a)
        subprocess.check_call(a)

    def run(self, opts):
        self.ccall('git', 'switch', '-')
        self.ccall(sys.executable, 'setup.py', 'build', '--clean')
        self.ccall(sys.executable, 'setup.py', 'build')
        self.ccall(sys.executable, 'setup.py', 'gui', '--clean')
        self.ccall(sys.executable, 'setup.py', 'gui', '--summary')
