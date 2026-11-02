"""Independent history/layout regressions and Git graph invariants.

All repositories are disposable; no bundled fixture or implementation imports.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'ndf.py'
CONFIG = {'id-prefixes': ['SYS', 'VER', 'Q'], 'layers': ['L0', 'L1', 'L2', 'L3']}


def clause(cid='SYS-BASE', body='The system MUST count.', extra=''):
    return f'## Contract {{#{cid}}}\n<!-- ndf: kind=req level=must layer=L1 {extra} -->\n\n{body}\n'


class AdversarialHistory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-history-audit-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.repo = self.home / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'History Auditor')
        self.git('config', 'user.email', 'history@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'core.hooksPath', os.devnull)
        self.spec = self.repo / 'spec'
        self.spec.mkdir()
        (self.spec / 'ndf.yaml').write_text(json.dumps(CONFIG))
        self.write('contract.md', clause())
        self.initial = self.commit('Initial contract')

    def git(self, *args, cwd=None, status=0):
        result = subprocess.run(['git', '-C', str(cwd or self.repo), *args], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return result.stdout.strip()

    def write(self, path, value):
        destination = self.spec / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(value, encoding='utf-8')

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def cli(self, *args, root=None, status=0):
        result = subprocess.run([sys.executable, str(CLI), '--root', str(root or self.spec), '--json', *args], capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return json.loads(result.stdout) if status == 0 else result

    def test_repo_directory_ending_in_space_is_not_stripped(self):
        for name in ('repository with trailing space ', 'repository with tab\t', 'repository with newline\n'):
            with self.subTest(name=name):
                moved = self.home / name
                self.repo.rename(moved)
                self.repo, self.spec = moved, moved / 'spec'
                events = self.cli('log', 'SYS-BASE')
                self.assertEqual([r['commit'] for r in events], [self.initial])
                self.assertEqual(self.cli('diff', 'HEAD..HEAD'), [])

    def test_linked_worktree_uses_its_own_root_and_branch(self):
        worktree = self.home / 'linked worktree'
        self.git('worktree', 'add', '-qb', 'linked', str(worktree))
        (worktree / 'spec/contract.md').write_text(clause(body='The system MUST count to 10.'))
        self.git('add', '.', cwd=worktree)
        self.git('commit', '-qm', 'Linked change', cwd=worktree)
        linked = self.git('rev-parse', 'HEAD', cwd=worktree)
        self.assertEqual(self.cli('log', 'SYS-BASE', root=worktree / 'spec')[0]['commit'], linked)
        self.assertEqual([r['commit'] for r in self.cli('log', 'SYS-BASE')], [self.initial])
        self.assertEqual(self.cli('diff', 'main..linked', root=worktree / 'spec')[0]['categories'], ['modified'])

    def test_octopus_merge_compares_all_three_parents(self):
        self.git('checkout', '-qb', 'side-b')
        self.write('b.md', clause('SYS-B'))
        side_b = self.commit('Add B')
        self.git('checkout', '-qb', 'side-c', self.initial)
        self.write('c.md', clause('SYS-C'))
        side_c = self.commit('Add C')
        self.git('checkout', '-q', 'main')
        self.write('a.md', clause('SYS-A'))
        main = self.commit('Add A')
        self.git('merge', '--no-ff', '-qm', 'Octopus integration', 'side-b', 'side-c')
        merged = self.git('rev-parse', 'HEAD')
        events = self.cli('log', 'SYS-B')
        merge = next(e for e in events if e['commit'] == merged)
        self.assertEqual(set(merge['parents']), {main, side_b, side_c})
        self.assertEqual({e['parent'] for e in merge['changes']}, {main, side_c})
        self.assertTrue(all(e['change'] == 'added' for e in merge['changes']))
        self.assertEqual({e['commit'] for e in events}, {side_b, merged})
        self.assertEqual(len(self.cli('diff', self.initial + '..HEAD')), 3)

    def test_annotated_tag_and_branch_names_resolve_exact_snapshots(self):
        self.git('tag', '-a', 'release/one', '-m', 'First release')
        self.git('checkout', '-qb', 'feature/subsystem/rework')
        self.write('contract.md', clause(body='The system MUST count to 17.'))
        changed = self.commit('Adjust bound')
        self.assertEqual([e['commit'] for e in self.cli('log', 'SYS-BASE', '--ref', 'release/one')], [self.initial])
        self.assertEqual(self.cli('diff', 'release/one..feature/subsystem/rework')[0]['id'], 'SYS-BASE')
        self.assertEqual(self.cli('diff', changed + '..HEAD'), [])
        self.assertEqual(self.cli('diff', 'HEAD~1..release/one'), [])

    def test_move_one_clause_from_shared_document_to_deep_hierarchy(self):
        self.write('contract.md', clause() + clause('SYS-OTHER'))
        shared = self.commit('Put two contracts together')
        self.write('contract.md', clause('SYS-OTHER'))
        self.write('subsystem/ingress/stage 2/requirements.md', clause())
        moved = self.commit('Split document by subsystem')
        row, = self.cli('diff', shared + '..HEAD')
        self.assertEqual(row['id'], 'SYS-BASE')
        self.assertEqual(row['categories'], ['moved'])
        self.assertEqual(row['after'], 'subsystem/ingress/stage 2/requirements.md')
        event = self.cli('log', 'SYS-BASE')[0]
        self.assertEqual(event['commit'], moved)
        self.assertEqual(event['changes'][0]['change'], 'moved')

    def test_unusual_tracked_file_names_do_not_break_history(self):
        for name in ('colon:name.md', 'tab\tname.md', 'line\nname.md', 'brackets[1].md', '-dash.md'):
            with self.subTest(name=name):
                (self.spec / 'contract.md').rename(self.spec / name)
                commit = self.commit('Move to unusual path')
                row, = self.cli('diff', 'HEAD~1..HEAD')
                self.assertEqual(row['after'], name)
                self.assertEqual(self.cli('log', 'SYS-BASE')[0]['commit'], commit)
                (self.spec / name).rename(self.spec / 'contract.md')
                self.commit('Restore ordinary name')

    def test_reflog_only_commit_is_excluded_until_referenced(self):
        self.write('contract.md', clause(body='The system MUST count to 4.'))
        detached = self.commit('Ephemeral change')
        self.git('checkout', '-q', '--detach', self.initial)
        # Advance main back by a temporary reference operation, without rewriting
        # repository files. The old object is retained only through reflog.
        self.git('update-ref', 'refs/heads/main', self.initial)
        self.assertNotIn(detached, {e['commit'] for e in self.cli('log', 'SYS-BASE', '--all')})
        self.git('tag', 'retained', detached)
        self.assertIn(detached, {e['commit'] for e in self.cli('log', 'SYS-BASE', '--all')})

    def test_mode_only_change_does_not_modify_clause_history(self):
        self.git('update-index', '--chmod=+x', 'spec/contract.md')
        self.git('commit', '-qm', 'Executable-bit-only change')
        self.assertEqual(self.cli('diff', 'HEAD~1..HEAD'), [])
        self.assertEqual([r['commit'] for r in self.cli('log', 'SYS-BASE')], [self.initial])

    def test_metadata_key_reordering_is_not_substantive_change(self):
        self.write('contract.md', '## Contract {#SYS-BASE}\n<!-- ndf: layer=L1 level=must kind=req -->\n\nThe system MUST count.\n')
        self.commit('Reorder metadata')
        self.assertEqual(self.cli('diff', 'HEAD~1..HEAD'), [])
        self.assertEqual([r['commit'] for r in self.cli('log', 'SYS-BASE')], [self.initial])

    def test_indented_code_whitespace_is_not_classified_formatting_only(self):
        self.write('contract.md', clause(body='The system MUST execute this reference:\n\n    if running:\n        count += 1'))
        before = self.commit('Indented code reference')
        self.write('contract.md', clause(body='The system MUST execute this reference:\n\n    if running:\n    count += 1'))
        self.commit('Change code indentation')
        row, = self.cli('diff', before + '..HEAD')
        self.assertEqual(row['categories'], ['modified'])

    def test_multibacktick_code_span_content_remains_substantive(self):
        self.write('contract.md', clause(body='The system MUST retain ``a ` b  c`` exactly.'))
        before = self.commit('Multi-backtick code span')
        self.write('contract.md', clause(body='The system MUST retain ``a ` b c`` exactly.'))
        self.commit('Change code span spacing')
        self.assertEqual(self.cli('diff', before + '..HEAD')[0]['categories'], ['modified'])

    def test_diff_forward_reverse_edges_and_census_are_inverses(self):
        self.write('target.md', clause('SYS-TARGET'))
        a = self.commit('Dependency target')
        self.write('contract.md', clause(body='The system MUST count. ⟨TBD: upper bound⟩', extra='depends-on=SYS-TARGET'))
        b = self.commit('Add dependency and open bound')
        self.write('contract.md', clause(body='The system MUST count to 8.', extra='depends-on=SYS-TARGET status=stable'))
        c = self.commit('Resolve bound')
        self.write('contract.md', clause(body='The system MUST count to 8.', extra='status=deprecated'))
        d = self.commit('Deprecate obligation')
        for left, right in ((a, b), (a, c), (a, d), (b, c), (b, d), (c, d)):
            with self.subTest(left=left, right=right):
                forward, = self.cli('diff', left + '..' + right)
                reverse, = self.cli('diff', right + '..' + left)
                self.assertEqual(forward['edges_added'], reverse['edges_removed'])
                self.assertEqual(forward['edges_removed'], reverse['edges_added'])
                self.assertEqual(forward['census_delta'], {k: -v for k, v in reverse['census_delta'].items()})
                self.assertEqual(forward['metadata_before'], reverse['metadata_after'])

    def test_deprecated_tbd_census_delta_agrees_with_coverage(self):
        self.write('contract.md', clause(body='The system MUST count. ⟨TBD: upper bound⟩'))
        before = self.commit('Open upper bound')
        old = self.cli('coverage')
        self.write('contract.md', clause(body='The system MUST count. ⟨TBD: upper bound⟩', extra='status=deprecated'))
        self.commit('Retire obligation with historical TBD retained')
        new = self.cli('coverage')
        row, = self.cli('diff', before + '..HEAD')
        self.assertEqual(row['census_delta']['TBD_markers'], len(new['TBD']) - len(old['TBD']))

    def test_shallow_boundary_is_not_reported_as_a_proven_addition(self):
        self.write('contract.md', clause(body='The system MUST count to 12.'))
        latest = self.commit('Modify existing obligation')
        shallow = self.home / 'shallow'
        result = subprocess.run(['git', 'clone', '-q', '--depth=1', self.repo.as_uri(), str(shallow)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, str(CLI), '--root', str(shallow / 'spec'), '--json', 'log', 'SYS-BASE'], capture_output=True, text=True, timeout=20)
        self.assertIn(result.returncode, (0, 2), result.stdout + result.stderr)
        if result.returncode == 2:
            self.assertIn('shallow', result.stderr.lower())
        else:
            events = json.loads(result.stdout)
            boundary = next(e for e in events if e['commit'] == latest)
            self.assertTrue(boundary.get('incomplete') or any(change['change'] == 'boundary' for change in boundary['changes']), 'A shallow boundary cannot prove the requirement was newly added')


if __name__ == '__main__':
    unittest.main()
