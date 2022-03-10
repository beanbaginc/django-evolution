#!/usr/bin/env python
from __future__ import print_function, unicode_literals

import sys

import pytest


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] != '--':
        args = ['--db', sys.argv[1]] + sys.argv[2:]
    else:
        args = sys.argv[1:]

    sys.exit(pytest.main(args))
