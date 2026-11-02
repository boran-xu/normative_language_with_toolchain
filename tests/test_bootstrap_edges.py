"""Bootstrap is exercised as a public command in disposable outer clones."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BootstrapEdges(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-bootstrap-audit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'outer space ü'
        result = subprocess.run(['git', 'clone', '-q', '--no-local', str(ROOT), str(self.root)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        # Test the current worktree script before its eventual commit as well.
        shutil.copyfile(ROOT / 'tools/bootstrap_history.py', self.root / 'tools/bootstrap_history.py')
        self.manifest = self.root / 'tests/fixtures/history.json'
        self.source = self.root / 'tests/fixtures/history'

    def bootstrap(self):
        return subprocess.run([sys.executable, 'tools/bootstrap_history.py'], cwd=self.root, capture_output=True, text=True, timeout=30)

    def git(self, *args, cwd=None):
        result = subprocess.run(['git', *args], cwd=cwd or self.root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_manifest_shape_errors_are_clean_and_do_not_initialize(self):
        valid = json.loads(self.manifest.read_text())
        for broken in ([], None, {}, {'pin': valid['pin'], 'refs': None}, {'pin': valid['pin'], 'refs': []}):
            with self.subTest(manifest=broken):
                self.manifest.write_text(json.dumps(broken))
                result = self.bootstrap()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse((self.source / '.git').exists())

    def test_bootstrap_is_offline_idempotent_and_preserves_global_config(self):
        before = self.git('config', '--global', '--list') if Path.home().joinpath('.gitconfig').exists() else None
        for _ in range(2):
            result = self.bootstrap()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=self.source).strip(), manifest['pin'])
        self.assertEqual(self.git('status', '--porcelain', cwd=self.source), '')
        if before is not None:
            self.assertEqual(self.git('config', '--global', '--list'), before)

    def test_dirty_or_untracked_fixture_is_not_reset(self):
        self.assertEqual(self.bootstrap().returncode, 0)
        for path in ('spec/notes.md', 'scratch.txt'):
            with self.subTest(path=path):
                changed = self.source / path
                original = changed.read_bytes() if changed.exists() else None
                changed.write_text('user work\n')
                before = self.git('rev-parse', 'HEAD', cwd=self.source)
                result = self.bootstrap()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('dirty', result.stderr)
                self.assertEqual(changed.read_text(), 'user work\n')
                self.assertEqual(self.git('rev-parse', 'HEAD', cwd=self.source), before)
                if original is None:
                    changed.unlink()
                else:
                    changed.write_bytes(original)

    def test_pin_mismatch_is_rejected_before_initialization(self):
        data = json.loads(self.manifest.read_text())
        data['pin'] = '0' * 40
        self.manifest.write_text(json.dumps(data))
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('gitlink', result.stderr)
        self.assertFalse((self.source / '.git').exists())

    def test_ref_mismatch_is_rejected_before_initialization(self):
        data = json.loads(self.manifest.read_text())
        data['refs']['v0.1'] = '0' * 40
        self.manifest.write_text(json.dumps(data))
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse((self.source / '.git').exists(), 'Rejected bundle metadata must not create or reset the fixture first')

    def test_damaged_bundle_does_not_create_the_fixture(self):
        (self.root / 'tests/fixtures/chrono.bundle').write_bytes(b'not a Git bundle\n')
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse((self.source / '.git').exists())


if __name__ == '__main__':
    unittest.main()
