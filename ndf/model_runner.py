"""Run explicitly requested project tests; never claim success for zero tests."""
import sys
import unittest

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.discover(sys.argv[1])
    if suite.countTestCases() == 0:
        print('ndf: unittest discovery found zero tests (nested directories need __init__.py)', file=sys.stderr)
        raise SystemExit(2)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
