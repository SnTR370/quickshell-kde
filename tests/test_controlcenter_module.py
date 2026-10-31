#!/usr/bin/env python3
"""
P1-6: modules/controlcenter/test_controlcenter.py in the default regression suite.

`python3 -m unittest discover -s tests` only scans tests/, so the
controlcenter module suite (unit contracts, qmllint, service-integration
wiring and an isolated quickshell runtime probe) was never executed by the
standard regression command. This shim loads it from its module directory
so it runs with everything else. The suite itself is session-safe: its
runtime probe runs offscreen inside a private D-Bus session.
"""
import importlib.util
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CC_TEST_PATH = os.path.join(REPO, "modules", "controlcenter", "test_controlcenter.py")

_spec = importlib.util.spec_from_file_location("controlcenter_module_test", CC_TEST_PATH)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


def load_tests(loader, tests, pattern):
    return loader.loadTestsFromModule(_module)


if __name__ == "__main__":
    unittest.main()
