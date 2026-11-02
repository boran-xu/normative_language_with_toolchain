"""Black-box CLI matrix against an independently authored, pinned Git submodule.

Expected IDs, counts and transitions below are hand-written from the scenario
story. history.json records Git object identities only, never NDF output.
All checkout, mutation and ref operations happen in disposable independent clones.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tests/fixtures/history'
MANIFEST = json.loads((ROOT / 'tests/fixtures/history.json').read_text())
CLI = ROOT / 'ndf.py'

# These are independent expectations, not golden output captured from NDF.
VERSIONS = {'v0.1': 6, 'v0.2': 17, 'v0.3': 19, 'v0.4': 19, 'v1.0': 19}
KINDS = {'arch', 'def', 'req', 'info', 'question', 'constraint', 'option', 'verif', 'decision'}
COUNTER_HISTORY = {'v0.1', 'v0.4', 'scenario/conflict-main', 'scenario/conflict-side', 'scenario/conflict-resolved'}


def process(command, cwd, **kwargs):
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=30, **kwargs)


class HistoryFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Fail clearly rather than silently skipping an absent integration fixture.
        if not (SOURCE / '.git').is_file():
            raise RuntimeError('Initialize the fixture: python3 tools/bootstrap_history.py')
        index = process(['git', 'ls-files', '--stage', '--', 'tests/fixtures/history'], ROOT)
        if not index.stdout.startswith('160000 ' + MANIFEST['pin'] + ' 0'):
            raise RuntimeError('The fixture must be pinned by the outer Git index')
        if process(['git', 'rev-parse', 'HEAD'], SOURCE).stdout.strip() != MANIFEST['pin']:
            raise RuntimeError('Submodule HEAD differs from its recorded pin; run bootstrap_history.py')
        cls.original_status = process(['git', 'status', '--porcelain'], SOURCE).stdout
        if cls.original_status:
            raise RuntimeError('Fixture submodule must be clean')
        cls.storage = tempfile.TemporaryDirectory(prefix='ndf-integration-base-')
        cls.base = Path(cls.storage.name) / 'base'
        # Exclude invalid commits until a test deliberately fetches one. This also
        # tests that detached checkout does not imply full scenario availability.
        result = process(['git', 'clone', '-q', '--no-local', '--no-tags', '--single-branch', '--branch', 'main', str(SOURCE), str(cls.base)], ROOT)
        if result.returncode:
            raise RuntimeError(result.stderr)
        for pattern in ('refs/tags/v*', 'refs/tags/scenario/*'):
            result = process(['git', 'fetch', '-q', str(SOURCE), '+' + pattern + ':' + pattern], cls.base)
            if result.returncode:
                raise RuntimeError(result.stderr)
        cls.original_head = process(['git', 'rev-parse', 'HEAD'], SOURCE).stdout

    @classmethod
    def tearDownClass(cls):
        try:
            if process(['git', 'rev-parse', 'HEAD'], SOURCE).stdout != cls.original_head:
                raise AssertionError('integration tests changed the source fixture HEAD')
            if process(['git', 'status', '--porcelain'], SOURCE).stdout != cls.original_status:
                raise AssertionError('integration tests changed the source fixture worktree')
        finally:
            cls.storage.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-integration-')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'checkout'
        result = process(['git', 'clone', '-q', '--no-local', str(self.base), str(self.repo)], ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.spec = self.repo / 'spec'
        self.git('config', 'core.autocrlf', 'false')
        self.checkout('v1.0')

    def git(self, *args, code=0):
        result = process(['git', *args], self.repo)
        self.assertEqual(result.returncode, code, result.stderr)
        return result.stdout.strip()

    def checkout(self, tag):
        self.git('checkout', '-q', '--detach', 'refs/tags/' + tag)

    def fetch_scenario(self, tag):
        self.git('fetch', '-q', str(SOURCE), 'refs/tags/' + tag + ':refs/tags/' + tag)
        self.assertEqual(self.git('rev-parse', 'refs/tags/' + tag), MANIFEST['refs'][tag])
        self.checkout(tag)

    def cli(self, *args, code=0, json_output=True, spec=None):
        result = process([sys.executable, str(CLI), '--root', str(spec or self.spec), *(['--json'] if json_output else []), *args], self.repo)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        if args[0] != 'test':
            self.assertNotIn('Traceback', result.stderr)
        if code == 2 or not json_output or args[0] == 'test':
            return result
        return json.loads(result.stdout)

    def test_fixture_pin_refs_full_history_and_deterministic_export(self):
        self.assertEqual(self.git('rev-parse', 'HEAD'), MANIFEST['pin'])
        self.assertEqual(self.git('rev-parse', '--is-shallow-repository'), 'false')
        for ref, commit in MANIFEST['refs'].items():
            if ref.startswith(('v', 'scenario/')):
                with self.subTest(ref=ref):
                    self.assertEqual(self.git('rev-parse', 'refs/tags/' + ref), commit)
        self.assertEqual(self.cli('export'), self.cli('export'))
        data = self.cli('export')
        self.assertEqual({r['meta']['kind'] for r in data}, KINDS)
        self.assertEqual(len({r['id'] for r in data}), 19)

    def test_all_release_versions_parse_and_validate(self):
        for version, count in VERSIONS.items():
            with self.subTest(version=version):
                self.checkout(version)
                result = self.cli('check')
                self.assertEqual(result['errors'], [])
                self.assertEqual(result['clauses'], count)
                self.assertEqual(len(self.cli('export')), count)

    def test_every_valid_branch_and_merge_snapshot_validates_and_runs(self):
        for tag in sorted(MANIFEST['refs']):
            if not tag.startswith('scenario/'):
                continue
            with self.subTest(tag=tag):
                self.checkout(tag)
                self.assertEqual(self.cli('check')['errors'], [])
                self.assertIn('Ran 3 tests', self.cli('test').stderr)

    def test_coverage_evolves_and_closed_items_leave_worklist(self):
        expected = {
            'v0.1': (3, 0, ['CNT-001', 'CTL-001', 'DEF-001'], ['CTL-001'], ['Q-001'], []),
            'v0.2': (6, 3, ['CON-CLK-001', 'DEF-001', 'REF-TIME-001'], ['CTL-001'], ['Q-001'], ['PRM-DEB-001', 'PRM-CLK-001']),
            'v0.3': (6, 3, ['CON-CLK-001', 'DEF-001', 'REF-TIME-001'], [], [], []),
            'v1.0': (6, 3, ['CON-CLK-001', 'DEF-001', 'REF-TIME-001'], [], [], []),
        }
        for version, (must, linked, unverified, tbd, questions, options) in expected.items():
            with self.subTest(version=version):
                self.checkout(version)
                data = self.cli('coverage')
                self.assertEqual((data['L1_must'], data['linked']), (must, linked))
                self.assertEqual(data['unverified'], unverified)
                self.assertEqual(data['TBD'], tbd)
                self.assertEqual(data['open_questions'], questions)
                self.assertEqual(set(data['open_options']), set(options))

    def test_questions_decisions_options_and_provenance(self):
        self.checkout('v0.2')
        questions = self.cli('status')['questions']
        self.assertEqual([(q['id'], q['status'], q['blocks']) for q in questions], [('Q-001', 'open', ['CTL-001'])])
        options = {r['id']: r for r in self.cli('options')}
        self.assertEqual(set(options), {'PRM-DEB-001', 'PRM-CLK-001'})
        self.assertEqual(options['PRM-DEB-001']['default'], '10')
        self.assertEqual(options['PRM-DEB-001']['explore'], '5,10,20')
        self.assertEqual(options['PRM-DEB-001']['couples-with'], 'PRM-CLK-001')
        self.checkout('v0.3')
        self.assertIn('D-002', self.cli('status')['questions'][0]['resolution'])
        self.assertEqual({r['level'] for r in self.cli('options')}, {'must'})
        self.assertEqual({r['status'] for r in self.cli('options')}, {'stable'})
        exported = {r['id']: r for r in self.cli('export')}
        self.assertEqual(exported['CTL-001']['meta']['status'], 'superseded-by=CTL-002')
        self.assertEqual(exported['CTL-OLD-001']['meta']['status'], 'deprecated')
        self.assertIn('Q-001', exported['D-002']['refs'])

    def test_external_dependency_surface_including_path_refs(self):
        expected = {('CNT-MOD-010', 'depends-on'), ('CON-CLK-001', 'depends-on'), ('DSP-001', 'depends-on'), ('DSP-001', 'mention'), ('PRM-DEB-001', 'depends-on')}
        for path in ('refs', 'refs/', 'refs/time.md'):
            with self.subTest(path=path):
                rows = self.cli('deps', path)
                self.assertEqual({(r['id'], r['type']) for r in rows}, expected)
                self.assertEqual(len(rows), 5)
                self.assertEqual({r['target'] for r in rows}, {'REF-TIME-001'})
                self.assertEqual({r['origin'] for r in rows}, {'Toy Time Standard 1.0 §1'})
        self.assertEqual(self.cli('deps', 'does-not-exist'), [])

    def test_trace_shared_dependency_and_disconnected_note(self):
        rows = self.cli('trace', 'CHR-000')
        self.assertEqual({r['id'] for r in rows}, {'CHR-000', 'CNT-001', 'CTL-001', 'CTL-002', 'CON-CLK-001', 'DSP-001', 'CNT-MOD-010', 'PRM-CLK-001', 'PRM-DEB-001', 'REF-TIME-001'})
        self.assertEqual(len([r for r in rows if not r['repeated']]), 10)
        self.assertTrue(any(r['repeated'] for r in rows))
        self.assertEqual({r['relation'] for r in rows}, {None, 'refined-by', 'depends-on'})
        dsp = next(r for r in rows if r['id'] == 'DSP-001' and not r['repeated'])
        self.assertEqual(dsp['verified_by'], ['VER-DSP-001'])
        self.assertEqual([r['id'] for r in self.cli('trace', 'INFO-001')], ['INFO-001'])
        self.assertIn('refined-by:', self.cli('trace', 'CHR-000', json_output=False).stdout)

    def test_dependency_cycle_terminates_and_does_not_expand_mentions(self):
        self.checkout('scenario/dependency-cycle')
        rows = self.cli('trace', 'CNT-001')
        self.assertEqual(len([r for r in rows if not r['repeated']]), 5)
        self.assertTrue(any(r['id'] == 'CNT-001' and r['repeated'] for r in rows))
        self.assertNotIn('D-001', {r['id'] for r in rows})

    def test_full_counter_history_across_move_and_conflicting_merge(self):
        rows = self.cli('log', 'CNT-001')
        self.assertEqual({r['commit'] for r in rows}, {MANIFEST['refs'][ref] for ref in COUNTER_HISTORY})
        merge = next(r for r in rows if r['commit'] == MANIFEST['refs']['scenario/conflict-resolved'])
        self.assertEqual(set(merge['parents']), {MANIFEST['refs']['scenario/conflict-main'], MANIFEST['refs']['scenario/conflict-side']})
        self.assertEqual({r['parent'] for r in merge['changes']}, set(merge['parents']))
        move = next(r for r in rows if r['commit'] == MANIFEST['refs']['v0.4'])
        self.assertEqual(move['changes'][0]['change'], 'modified+moved')
        self.assertEqual(move['path'], '20-behavior/count ü.md')
        # Topological output must put each ancestor event after its descendants.
        order = {r['commit']: i for i, r in enumerate(rows)}
        for row in rows:
            for parent in row['parents']:
                if parent in order:
                    self.assertLess(order[row['commit']], order[parent])

    def test_merge_resolutions_matching_each_parent(self):
        for choice, different in [('side', 'main'), ('main', 'side')]:
            with self.subTest(choice=choice):
                tag = 'scenario/match-' + choice
                rows = self.cli('log', 'CNT-001', '--ref', tag)
                merge = next(r for r in rows if r['commit'] == MANIFEST['refs'][tag])
                self.assertEqual(len(merge['parents']), 2)
                self.assertEqual([c['parent'] for c in merge['changes']], [MANIFEST['refs'][tag + '-' + different]])
                self.assertEqual(self.cli('diff', tag + '-' + choice + '..' + tag), [])

    def test_all_refs_include_experiments_default_log_excludes_them(self):
        ordinary = {r['commit'] for r in self.cli('log', 'CNT-001')}
        everything = {r['commit'] for r in self.cli('log', 'CNT-001', '--all')}
        unmerged = MANIFEST['refs']['scenario/match-side-side']
        self.assertNotIn(unmerged, ordinary)
        self.assertIn(unmerged, everything)
        self.assertTrue(ordinary < everything)
        self.assertEqual(self.cli('log', 'NOT-A-CLAUSE'), [])

    def test_diff_versions_reverse_direction_and_unrelated_branches(self):
        for a, b, ids in [('v0.1', 'v0.2', {'CNT-MOD-010', 'VER-CNT-001', 'VER-CTL-001', 'VER-DSP-001', 'PRM-DEB-001', 'PRM-CLK-001', 'REF-TIME-001', 'CON-CLK-001', 'DSP-001', 'D-001', 'CTL-OLD-001'}),
                          ('scenario/conflict-main', 'scenario/conflict-side', {'CNT-001', 'CNT-MOD-010'}),
                          ('scenario/clean-main', 'scenario/clean-merge', {'DSP-001'})]:
            with self.subTest(a=a, b=b):
                forward = {r['id']: r for r in self.cli('diff', a + '..' + b)}
                reverse = {r['id']: r for r in self.cli('diff', b + '..' + a)}
                self.assertEqual(set(forward), ids)
                self.assertEqual(set(reverse), ids)
                for cid in ids:
                    self.assertEqual(forward[cid]['edges_added'], reverse[cid]['edges_removed'])
                    self.assertEqual(forward[cid]['metadata_before'], reverse[cid]['metadata_after'])
                    self.assertEqual(forward[cid]['census_delta'], {k: -v for k, v in reverse[cid]['census_delta'].items()})
        self.assertEqual(self.cli('diff', 'HEAD..HEAD'), [])
        self.assertEqual(self.cli('diff', MANIFEST['refs']['v1.0'] + '..v1.0'), [])

    def test_lifecycle_changelog_reports_independent_expected_categories(self):
        rows = {r['id']: r for r in self.cli('diff', 'v0.2..v0.3')}
        self.assertEqual(set(rows), {'CTL-001', 'CTL-002', 'D-002', 'VER-CTL-001', 'PRM-DEB-001', 'PRM-CLK-001', 'Q-001', 'CTL-OLD-001'})
        self.assertEqual(rows['CTL-001']['categories'], ['modified', 'superseded'])
        self.assertEqual(rows['CTL-OLD-001']['categories'], ['modified', 'deprecated'])
        self.assertEqual(rows['CTL-002']['categories'], ['added'])
        self.assertEqual(rows['Q-001']['census_delta']['open_questions'], -1)
        self.assertEqual(rows['PRM-DEB-001']['census_delta']['open_options'], -1)
        self.assertIn({'type': 'verifies', 'target': 'CTL-002'}, rows['VER-CTL-001']['edges_added'])
        row, = self.cli('diff', 'v0.3..v0.4')
        self.assertEqual(row['categories'], ['formatting-only', 'moved'])
        self.assertEqual(row['id'], 'CNT-001')

    def test_check_since_flags_related_pairs_after_clean_merge(self):
        self.checkout('scenario/clean-merge')
        data = self.cli('check', '--since', 'scenario/clean-main')
        review = [w for w in data['warnings'] if w.startswith('review refinement')]
        self.assertEqual(len(review), 1)
        self.assertIn('DSP-001 -> CHR-000', review[0])

    def test_invalid_snapshots_fail_and_duplicate_history_fails_explicitly(self):
        for tag, error in [('invalid/duplicate', 'duplicate ID'), ('invalid/dangling', 'dangling refines'), ('invalid/metadata', 'invalid level'), ('invalid/conflict-markers', 'unresolved Git conflict'), ('invalid/refinement-cycle', 'refinement cycle')]:
            with self.subTest(tag=tag):
                self.fetch_scenario(tag)
                self.assertTrue(any(error in e for e in self.cli('check', code=1)['errors']))
        self.checkout('v1.0')
        result = self.cli('log', 'CNT-001', '--all', code=2)
        self.assertIn('duplicate ID', result.stderr)
        self.assertEqual(self.cli('diff', 'v1.0..v1.0'), [])

    def test_note_deletion_restoration_and_known_conflict(self):
        rows = self.cli('log', 'INFO-001', '--ref', 'scenario/restore-note')
        self.assertEqual({r['commit'] for r in rows}, {MANIFEST['refs'][tag] for tag in ('v0.1', 'scenario/delete-note', 'scenario/restore-note')})
        deletion, = self.cli('diff', 'v1.0..scenario/delete-note')
        self.assertEqual(deletion['categories'], ['deleted'])
        restoration, = self.cli('diff', 'scenario/delete-note..scenario/restore-note')
        self.assertEqual(restoration['categories'], ['added'])
        self.checkout('scenario/known-conflict')
        self.assertTrue(any('known conflict' in warning for warning in self.cli('check')['warnings']))
        report = self.cli('coverage')
        self.assertEqual(report['conflicts'], [{'id': 'DSP-001', 'with': 'CON-CLK-001'}])
        self.assertEqual(report['open_questions'], ['Q-002'])
        model = next(r for r in self.cli('export') if r['id'] == 'CNT-MOD-010')
        self.assertEqual(model['meta']['derived-from'], 'REF-TIME-001')

    def test_model_execution_pass_failure_and_missing(self):
        self.assertIn('Ran 3 tests', self.cli('test').stderr)
        self.fetch_scenario('tests/failing')
        self.assertIn('CNT-001 injected failure', self.cli('test', code=1).stderr)
        self.fetch_scenario('tests/missing')
        self.assertIn('no model tests', self.cli('test', code=2).stderr)
        self.checkout('v0.1')
        self.assertIn('no model tests', self.cli('test', code=2).stderr)

    def test_history_ignores_arbitrary_current_state_and_missing_spec_root(self):
        (self.spec / 'broken.md').write_bytes(b'\xff')
        (self.spec / 'ndf.yaml').unlink()
        self.assertEqual({r['commit'] for r in self.cli('log', 'CNT-001')}, {MANIFEST['refs'][t] for t in COUNTER_HISTORY})
        self.assertEqual(self.cli('diff', 'v1.0..v1.0'), [])
        # Move the entire current spec away; Git snapshot history still exists.
        self.spec.rename(self.repo / 'temporarily-away')
        self.assertEqual(len(self.cli('log', 'CNT-001')), 5)

    def test_init_and_concurrent_ids_across_independent_branches(self):
        other = Path(self.temp.name) / 'second'
        result = process(['git', 'clone', '-q', str(self.base), str(other)], ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        roots = [self.spec, other / 'spec']
        with ThreadPoolExecutor(max_workers=8) as executor:
            ids = list(executor.map(lambda i: self.cli('new-id', 'CNT-AREA', spec=roots[i % 2])['id'], range(32)))
        self.assertEqual(len(set(ids)), 32)
        self.assertTrue(all(cid.startswith('CNT-AREA-') for cid in ids))
        self.cli('new-id', 'UNKNOWN', code=2)
        empty = self.repo / 'new-spec'
        self.cli('init', spec=empty)
        self.assertEqual(self.cli('check', spec=empty)['clauses'], 0)
        self.cli('init', spec=empty, code=2)

    def test_invalid_invocations_fail_without_mutating_source_or_checkout(self):
        before = self.git('status', '--porcelain')
        for args in [('trace', 'UNKNOWN'), ('diff', 'v0.1...v1.0'), ('diff', 'missing..HEAD'), ('log', 'CNT-001', '--ref', 'missing'), ('deps', '../')]:
            with self.subTest(args=args):
                self.cli(*args, code=2)
        self.assertEqual(self.git('status', '--porcelain'), before)


if __name__ == '__main__':
    unittest.main()
