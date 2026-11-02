"""Interaction-focused black-box regressions, independent of NDF internals.

Model tests, malformed manifests and Git/submodule operations use disposable
repositories only. Expected answers come from the documented tool contract.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'ndf.py'
CONFIG = {'id-prefixes': ['SYS', 'VER'], 'layers': ['L0', 'L1', 'L2', 'L3']}


def clause(cid, extra='', layer='L1', kind='req', body='The system MUST count.'):
    return f'## Requirement {{#{cid}}}\n<!-- ndf: kind={kind} level=must layer={layer} {extra} -->\n\n{body}\n'


class InteractionCli(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-interaction-cli-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.spec = self.base / 'spec'
        self.spec.mkdir()
        self.config(CONFIG)
        self.write('requirements.md', clause('SYS-001'))

    def config(self, value):
        (self.spec / 'ndf.yaml').write_text(json.dumps(value), encoding='utf-8')

    def write(self, path, content):
        file = self.spec / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding='utf-8')

    def cli(self, *args, root=None):
        return subprocess.run([sys.executable, str(CLI), '--root', str(root or self.spec), '--json', *args], cwd=self.base, capture_output=True, text=True, timeout=20)

    def data(self, *args, code=0):
        result = self.cli(*args)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return json.loads(result.stdout)

    def test_custom_refinement_layer_names_preserve_coverage(self):
        for layers in ({'Intent': 'intent', 'Contract': 'contract', 'Mechanism': 'mechanism', 'Executable': 'executable'}, ['Intent', 'Contract', 'Mechanism', 'Executable']):
            with self.subTest(layers=layers):
                self.config({**CONFIG, 'layers': layers})
                self.write('requirements.md', clause('SYS-001', layer='Contract') + clause('VER-001', layer='Executable', kind='verif', extra='verifies=SYS-001'))
                self.assertEqual(self.data('check')['errors'], [])
                result = self.data('coverage')
                self.assertEqual(result['contract_layer'], 'Contract')
                self.assertEqual(result['L1_must'], 1)
                self.assertEqual(result['linked'], 1)
                self.assertEqual(result['unverified'], [])

    def test_self_and_cyclic_supersession_are_structural_errors(self):
        cases = [clause('SYS-001', extra='status=superseded-by=SYS-001'),
                 clause('SYS-001', extra='status=superseded-by=SYS-002') + clause('SYS-002', extra='status=superseded-by=SYS-001')]
        for text in cases:
            with self.subTest(text=text):
                self.write('requirements.md', text)
                data = self.data('check', code=1)
                self.assertTrue(data['errors'])

    def test_conflicting_supersession_targets_are_not_silently_discarded(self):
        self.write('requirements.md', clause('SYS-001', extra='status=superseded-by=SYS-002 superseded-by=SYS-003') + clause('SYS-002') + clause('SYS-003'))
        self.assertTrue(self.data('check', code=1)['errors'])

    def test_matching_supersession_encodings_and_shared_terminal_are_valid(self):
        self.write('requirements.md', clause('SYS-001', extra='status=superseded-by=SYS-003 superseded-by=SYS-003') + clause('SYS-002', extra='status=superseded-by=SYS-003') + clause('SYS-003'))
        self.assertEqual(self.data('check')['errors'], [])
        self.assertEqual(self.data('coverage')['unverified'], ['SYS-003'])

    def test_valid_supersession_chain_keeps_only_final_contract_active(self):
        self.write('requirements.md', clause('SYS-001', extra='status=superseded-by=SYS-002') + clause('SYS-002', extra='status=superseded-by=SYS-003') + clause('SYS-003'))
        self.assertEqual(self.data('check')['errors'], [])
        data = self.data('coverage')
        self.assertEqual(data['L1_must'], 1)
        self.assertEqual(data['unverified'], ['SYS-003'])

    def test_test_module_successful_exit_cannot_claim_success_without_tests(self):
        self.write('models/test_exit.py', 'import sys\nsys.exit(0)\n')
        result = self.cli('test')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_test_method_successful_exit_is_reported_as_failure(self):
        self.write('models/test_exit.py', '''import unittest
class Acceptance(unittest.TestCase):
    def test_VER_001(self):
        raise SystemExit(0)
''')
        result = self.cli('test')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('SystemExit', result.stderr)

    def test_skipped_tests_have_visible_unittest_summary(self):
        self.write('models/test_skip.py', '''import unittest
@unittest.skip("platform-only acceptance")
class Acceptance(unittest.TestCase):
    def test_VER_001(self):
        self.fail("not supported on this platform")
''')
        result = self.cli('test')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('skipped=1', result.stderr)
        self.assertIn('platform-only acceptance', result.stderr)

    def test_model_named_like_stdlib_module_matches_unittest_behavior(self):
        self.write('models/json.py', 'EXPECTED_VALUE = 17\n')
        self.write('models/test_local.py', '''import json
import unittest
class Acceptance(unittest.TestCase):
    def test_VER_001(self):
        self.assertEqual(json.EXPECTED_VALUE, 17)
''')
        baseline = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'models', '-v'], cwd=self.spec, capture_output=True, text=True, timeout=20)
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        result = self.cli('test')
        self.assertEqual(result.returncode, baseline.returncode, result.stdout + result.stderr)

    def test_root_symlink_loop_fails_without_python_traceback(self):
        loop = self.base / 'loop'
        loop.symlink_to('loop')
        result = self.cli('check', root=loop)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_check_since_reports_direct_changed_pair_without_inventing_changes(self):
        self.write('requirements.md', clause('SYS-ROOT', layer='L0', kind='arch') + clause('SYS-CONTRACT', layer='L1', extra='refines=SYS-ROOT') + clause('SYS-MECHANISM', layer='L2', extra='refines=SYS-CONTRACT'))
        def git(*args):
            result = subprocess.run(['git', *args], cwd=self.base, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip()
        git('init', '-q')
        git('config', 'user.name', 'Interaction audit')
        git('config', 'user.email', 'audit@example.invalid')
        git('add', '.')
        git('commit', '-qm', 'Initial refinement chain')
        self.write('requirements.md', clause('SYS-ROOT', layer='L0', kind='arch') + clause('SYS-CONTRACT', layer='L1', extra='refines=SYS-ROOT') + clause('SYS-MECHANISM', layer='L2', extra='refines=SYS-CONTRACT', body='The system MUST count twice.'))
        warnings = self.data('check', '--since', 'HEAD')['warnings']
        review = [w for w in warnings if w.startswith('review refinement')]
        self.assertEqual(len(review), 1)
        self.assertIn('SYS-MECHANISM -> SYS-CONTRACT', review[0])


class BootstrapInteraction(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-bootstrap-interaction-')
        self.addCleanup(self.temp.cleanup)
        self.checkout = Path(self.temp.name) / 'outer space ü'
        result = subprocess.run(['git', 'clone', '--no-local', '-q', str(ROOT), str(self.checkout)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        # Test the current helper, including fixes not committed yet, in an
        # independent outer checkout whose fixture artifacts remain pinned.
        shutil.copy2(ROOT / 'tools/bootstrap_history.py', self.checkout / 'tools/bootstrap_history.py')
        self.target = self.checkout / 'tests/fixtures/history'
        self.manifest = self.checkout / 'tests/fixtures/history.json'

    def bootstrap(self):
        return subprocess.run([sys.executable, 'tools/bootstrap_history.py'], cwd=self.checkout, capture_output=True, text=True, timeout=30)

    def test_bootstrap_manifest_shape_errors_are_clean_and_do_not_initialize(self):
        original = json.loads(self.manifest.read_text())
        for value in (None, [], {}, {'pin': original['pin'], 'refs': []}, {'pin': original['pin'], 'refs': None}):
            with self.subTest(value=value):
                self.manifest.write_text(json.dumps(value))
                result = self.bootstrap()
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse((self.target / '.git').exists(), 'malformed metadata must be rejected before submodule mutation')

    def test_wrong_advertised_tag_hash_is_rejected_before_initialization(self):
        manifest = json.loads(self.manifest.read_text())
        tag = next(iter(manifest['refs']))
        manifest['refs'][tag] = '0' * 40
        self.manifest.write_text(json.dumps(manifest))
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse((self.target / '.git').exists())

    def test_damaged_bundle_is_rejected_before_initialization(self):
        (self.checkout / 'tests/fixtures/chrono.bundle').write_bytes(b'not a Git bundle')
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse((self.target / '.git').exists())

    def test_uninitialized_fixture_with_user_files_is_not_reported_ready(self):
        self.target.mkdir(parents=True, exist_ok=True)
        note = self.target / 'my-unsaved-notes.txt'
        note.write_text('user notes must survive')
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(note.read_text(), 'user notes must survive')
        self.assertFalse((self.target / '.git').exists())

    def test_initialized_dirty_fixture_is_rejected_without_losing_edits(self):
        result = self.bootstrap()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        note = self.target / 'my-unsaved-notes.txt'
        note.write_text('user notes must survive')
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('dirty', result.stderr.lower())
        self.assertEqual(note.read_text(), 'user notes must survive')

    def test_fresh_bootstrap_under_unicode_space_path_is_idempotent(self):
        first = self.bootstrap()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.bootstrap()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertTrue((self.target / '.git').is_file())

    def test_missing_bundle_has_a_clean_failure(self):
        (self.checkout / 'tests/fixtures/chrono.bundle').unlink()
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
