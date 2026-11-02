"""Ensure the standalone history can be rebuilt without using NDF output."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FixtureReproduction(unittest.TestCase):
    def test_rebuild_preserves_every_named_commit_and_bundle_ref(self):
        expected = json.loads((ROOT / 'tests/fixtures/history.json').read_text())
        with tempfile.TemporaryDirectory(prefix='ndf-reproduce-') as directory:
            bundle = Path(directory) / 'rebuilt.bundle'
            manifest = Path(directory) / 'rebuilt.json'
            result = subprocess.run([sys.executable, str(ROOT / 'tests/fixtures/build_history.py'), '--bundle', str(bundle), '--manifest', str(manifest)], cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(manifest.read_text()), expected)
            result = subprocess.run(['git', 'bundle', 'list-heads', str(bundle)], cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            refs = {ref: commit for commit, ref in (line.split() for line in result.stdout.splitlines())}
            for tag, commit in expected['refs'].items():
                self.assertEqual(refs['refs/tags/' + tag], commit)
            self.assertEqual(refs['HEAD'], expected['pin'])
            self.assertEqual(refs['refs/heads/main'], expected['pin'])


if __name__ == '__main__':
    unittest.main()
