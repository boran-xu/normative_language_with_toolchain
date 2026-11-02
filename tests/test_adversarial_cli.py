"""Independent CLI/lifecycle/configuration regressions for the second audit.

All expected answers are authored directly from input data. The tests never
import NDF internals and never mutate the real history fixture.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'ndf.py'
CONFIG = {'id-prefixes': ['SYS', 'VER', 'Q', 'PRM'], 'layers': ['L0', 'L1', 'L2', 'L3']}


def clause(cid='SYS-001', body='The system MUST retain its count.', kind='req', level='must', layer='L1', extra=''):
    fields = f'kind={kind}'
    if kind not in ('decision', 'question'):
        fields += f' level={level} layer={layer}'
    return f'## Requirement {{#{cid}}}\n<!-- ndf: {fields} {extra} -->\n\n{body}\n'


class AdversarialCli(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-cli-audit-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.spec = self.base / 'spec'
        self.spec.mkdir()
        self.config(CONFIG)
        self.write('requirements.md', clause())

    def config(self, value):
        (self.spec / 'ndf.yaml').write_text(json.dumps(value), encoding='utf-8')

    def write(self, name, text):
        path = self.spec / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def run_cli(self, *args, root=None, machine=True):
        command = [sys.executable, str(CLI), '--root', str(root or self.spec)]
        if machine:
            command.append('--json')
        return subprocess.run(command + list(args), cwd=self.base, capture_output=True, text=True, timeout=20)

    def data(self, *args, status=0):
        result = self.run_cli(*args)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return json.loads(result.stdout)

    def test_null_layer_ladder_is_a_clean_configuration_error(self):
        self.config({**CONFIG, 'layers': None})
        result = self.run_cli('check')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_repeated_layer_names_cannot_define_an_ordered_ladder(self):
        self.config({**CONFIG, 'layers': ['L0', 'L1', 'L1', 'L2']})
        result = self.run_cli('check')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_invalid_manifest_shapes_fail_without_python_tracebacks(self):
        invalid = [None, [], 'manifest', 12, {}, {'id-prefixes': []}, {'id-prefixes': 'SYS'},
                   {'id-prefixes': [1]}, {**CONFIG, 'layers': []}, {**CONFIG, 'layers': 1},
                   {**CONFIG, 'layers': ['L0', 1]}, {**CONFIG, 'glossary': []}, {**CONFIG, 'glossary': None},
                   {**CONFIG, 'glossary': {'synonyms': []}},
                   {**CONFIG, 'glossary': {'synonyms': {'packet': None}}}]
        for value in invalid:
            with self.subTest(value=value):
                self.config(value)
                result = self.run_cli('check')
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_code_examples_do_not_add_tbd_or_design_space_work(self):
        self.write('requirements.md', clause(body='''The system MUST retain its count.
Example syntax: `⟨TBD: example only⟩` and `⟨DSE: example default=1 range=1,2 → PRM-001⟩`.
````markdown
⟨TBD: another example⟩
⟨DSE: another example default=1 range=1,2 → PRM-001⟩
````
'''))
        data = self.data('coverage')
        self.assertEqual(data['TBD'], [])
        self.assertEqual(data['inline_DSE'], 0)

    def test_archived_design_space_markers_leave_active_census(self):
        self.write('requirements.md', clause(extra='status=deprecated', body='The system MUST use ⟨DSE: old interval default=1 range=1,2 → PRM-001⟩.'))
        self.assertEqual(self.data('coverage')['inline_DSE'], 0)

    def test_archived_conflicts_leave_active_census(self):
        self.write('requirements.md', clause(extra='status=deprecated conflicts-with=SYS-002') + clause('SYS-002'))
        self.assertEqual(self.data('coverage')['conflicts'], [])

    def test_deprecation_census_deltas_match_active_worklist(self):
        self.write('requirements.md', clause(extra='status=stable', body='The system MUST choose ⟨TBD: interval⟩ and ⟨DSE: width default=1 range=1,2 → PRM-001⟩.'))
        def git(*args):
            result = subprocess.run(['git', *args], cwd=self.base, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip()
        git('init', '-q')
        git('config', 'user.name', 'CLI audit')
        git('config', 'user.email', 'cli@example.invalid')
        git('add', '.')
        git('commit', '-qm', 'Active obligation')
        before = git('rev-parse', 'HEAD')
        self.write('requirements.md', clause(extra='status=deprecated', body='The system MUST choose ⟨TBD: interval⟩ and ⟨DSE: width default=1 range=1,2 → PRM-001⟩.'))
        git('add', '.')
        git('commit', '-qm', 'Retire obligation')
        row, = self.data('diff', before + '..HEAD')
        self.assertEqual(row['census_delta']['TBD_markers'], -1)

    def test_empty_typed_edge_elements_are_structural_errors(self):
        for key, value in [('depends-on', ''), ('depends-on', ','), ('depends-on', 'SYS-BASE,'), ('refines', ''), ('verifies', ',SYS-BASE')]:
            with self.subTest(key=key, value=value):
                kind = 'verif' if key == 'verifies' else 'req'
                level = 'L3' if kind == 'verif' else 'L1'
                self.write('requirements.md', clause('SYS-BASE', kind='arch', layer='L0') + clause(kind=kind, layer=level, extra=key + '=' + value))
                result = self.run_cli('check')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertTrue(json.loads(result.stdout)['errors'])
                self.assertNotIn('Traceback', result.stderr)

    def test_options_identity_is_anchored_not_overwritten_by_metadata(self):
        self.write('requirements.md', clause('PRM-001', kind='option', level='tbd', layer='L2', extra='default=10 explore=10,20 id=SYS-WRONG'))
        result = self.run_cli('options')
        self.assertIn(result.returncode, (0, 1), result.stdout + result.stderr)
        if result.returncode == 0:
            rows = json.loads(result.stdout)
            self.assertEqual(rows[0]['id'], 'PRM-001')
        else:
            # Rejecting reserved metadata would also preserve the invariant.
            self.assertTrue(json.loads(result.stdout)['errors'])

    def test_root_directory_is_not_a_relative_dependency_path(self):
        for path in ('/', '///'):
            with self.subTest(path=path):
                result = self.run_cli('deps', path)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_new_id_does_not_require_reading_unrelated_markdown(self):
        # UUID allocation needs the prefix manifest, not the current prose.
        (self.spec / 'damaged.md').write_bytes(b'not UTF-8: \xff')
        result = self.run_cli('new-id', 'SYS-COUNT')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(json.loads(result.stdout)['id'], r'^SYS-COUNT-[0-9a-f]{32}$')

    def test_model_runner_retains_project_root_imports(self):
        self.write('models/__init__.py', '')
        self.write('models/reference.py', 'EXPECTED = 7\n')
        self.write('models/test_reference.py', '''import unittest
from models.reference import EXPECTED
class Acceptance(unittest.TestCase):
    def test_VER_001(self):
        self.assertEqual(EXPECTED, 7)
''')
        baseline = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'models', '-v'], cwd=self.spec, capture_output=True, text=True, timeout=20)
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        result = self.run_cli('test')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Ran 1 test', result.stderr)

    def test_nested_package_model_tests_run(self):
        self.write('models/nested/__init__.py', '')
        self.write('models/nested/test_acceptance.py', '''import unittest
class Acceptance(unittest.TestCase):
    def test_VER_001(self):
        self.assertEqual(3 * 7, 21)
''')
        result = self.run_cli('test')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Ran 1 test', result.stderr)

    def test_all_active_and_retired_requirement_states_have_expected_coverage(self):
        records = []
        active = []
        for index, status in enumerate(('draft', 'stable', 'deprecated', 'superseded-by=SYS-NEW'), 1):
            cid = f'SYS-{index:03}'
            records.append(clause(cid, extra='status=' + status))
            if status in ('draft', 'stable'):
                active.append(cid)
        records.append(clause('SYS-NEW'))
        records.append(clause('VER-001', kind='verif', layer='L3', extra='verifies=SYS-001,SYS-NEW'))
        # A retired acceptance criterion must not count as specified coverage.
        records.append(clause('VER-002', kind='verif', layer='L3', extra='status=deprecated verifies=SYS-002'))
        self.write('requirements.md', ''.join(records))
        result = self.data('coverage')
        self.assertEqual(result['L1_must'], 3)
        self.assertEqual(result['linked'], 2)
        self.assertEqual(result['unverified'], ['SYS-002'])
        self.assertEqual(result['verification_links'], {'SYS-001': ['VER-001'], 'SYS-NEW': ['VER-001']})

    def test_question_states_are_classified_without_deleting_history(self):
        self.write('questions.md', ''.join(clause(f'Q-{i}', kind='question', body='**Resolution.** Recorded.', extra='status=' + status) for i, status in enumerate(('open', 'draft', 'resolved', 'closed', 'deprecated'))))
        data = self.data('status')
        self.assertEqual(set(data['open_questions']), {'Q-0', 'Q-1'})
        self.assertEqual(len(data['questions']), 5)

    def test_resolution_field_spellings(self):
        for field in ('**Resolution.** Recorded.', '**Resolution:** Recorded.', '**Resolution**: Recorded.'):
            with self.subTest(field=field):
                self.write('questions.md', clause('Q-001', kind='question', body=field, extra='status=resolved'))
                self.assertEqual(self.data('status')['questions'][0]['resolution'], 'Recorded.')

    def test_root_paths_with_spaces_and_unicode(self):
        alternate = self.base / 'project space ü' / 'spec'
        init = self.run_cli('init', root=alternate)
        self.assertEqual(init.returncode, 0, init.stderr)
        check = self.run_cli('check', root=alternate)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(json.loads(check.stdout)['clauses'], 0)
        again = self.run_cli('init', root=alternate)
        self.assertEqual(again.returncode, 2)

    def test_default_and_explicit_empty_spec_command_matrix(self):
        for command in ('check', 'coverage', 'status', 'options', 'deps', 'export'):
            with self.subTest(command=command):
                result = self.run_cli(command)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                json.loads(result.stdout)
        (self.spec / 'requirements.md').unlink()
        for command in ('check', 'coverage', 'status', 'options', 'deps', 'export'):
            with self.subTest(empty_command=command):
                result = self.run_cli(command)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                json.loads(result.stdout)

    def test_whole_file_dependency_expands_each_projected_clause_once(self):
        self.write('refs/time.md', clause('SYS-TIME-1') + clause('SYS-TIME-2'))
        self.write('requirements.md', clause(body='The system MUST follow [[refs/time.md]] and [[SYS-TIME-1]].'))
        result = self.data('deps')
        self.assertEqual({(r['id'], r['target'], r['type']) for r in result}, {('SYS-001', 'SYS-TIME-1', 'mention'), ('SYS-001', 'SYS-TIME-2', 'mention')})
        self.assertEqual(len(result), 2)

    def test_invalid_root_and_unknown_options_fail_cleanly(self):
        for command in [('trace',), ('new-id',), ('diff',), ('not-a-command',), ('check', '--nonsense')]:
            with self.subTest(command=command):
                result = self.run_cli(*command)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)
        file_root = self.base / 'file'
        file_root.write_text('ordinary file', encoding='utf-8')
        result = self.run_cli('init', root=file_root)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
