"""Interaction regressions: Git entry types, namespace scope and graph identity.

Assertions are authored independently and exercise the CLI in disposable repos.
No source fixture, runtime module or persistent repository is mutated.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'ndf.py'
CONFIG = {'id-prefixes': ['SYS', 'REF'], 'layers': ['L0', 'L1', 'L2', 'L3']}


def clause(cid='SYS-BASE', body='The system MUST count.', meta='kind=req level=must layer=L1'):
    return f'## Contract {{#{cid}}}\n<!-- ndf: {meta} -->\n\n{body}\n'


class InteractionHistory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-interaction-history-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.repo = self.home / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        for key, value in [('user.name', 'Interaction Auditor'), ('user.email', 'audit@example.invalid'), ('commit.gpgsign', 'false'), ('core.hooksPath', os.devnull)]:
            self.git('config', key, value)
        self.spec = self.repo / 'spec'
        self.spec.mkdir()
        (self.spec / 'ndf.yaml').write_text(json.dumps(CONFIG))
        self.write('contract.md', clause())
        self.initial = self.commit('Initial contract')

    def git(self, *args, cwd=None, code=0):
        result = subprocess.run(['git', '-C', str(cwd or self.repo), *args], text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result.stdout.strip()

    def write(self, path, value):
        dest = self.spec / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(value)

    def commit(self, title):
        self.git('add', '.')
        self.git('commit', '-qm', title)
        return self.git('rev-parse', 'HEAD')

    def raw(self, *args, root=None):
        result = subprocess.run([sys.executable, str(CLI), '--root', str(root or self.spec), '--json', *args], text=True, capture_output=True, timeout=20)
        self.assertNotIn('Traceback', result.stderr)
        return result

    def cli(self, *args, root=None):
        result = self.raw(*args, root=root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_tracked_symlink_alias_has_consistent_current_and_snapshot_policy(self):
        (self.spec / 'alias.md').symlink_to('contract.md')
        self.commit('Add a symbolic alias')
        current = self.raw('check')
        historical = self.raw('diff', 'HEAD..HEAD')
        # Both reject aliases explicitly, or both handle/ignore the alias. It is
        # incorrect to treat identical tracked trees as structurally different.
        self.assertEqual(current.returncode == 0, historical.returncode == 0,
                         f'Current: {current.stdout}{current.stderr}; snapshot: {historical.stdout}{historical.stderr}')

    def test_tracked_symlink_child_cannot_produce_false_clean_checkout_review(self):
        self.write('contract.md', clause(meta='kind=arch level=must layer=L0'))
        (self.repo / 'shared.md').write_text(clause('SYS-CHILD', meta='kind=req level=must layer=L1 refines=SYS-BASE'))
        (self.spec / 'linked.md').symlink_to('../shared.md')
        self.commit('Link a tracked child into the specification')
        result = self.raw('check', '--since', 'HEAD')
        if result.returncode:
            self.assertIn('symlink', (result.stdout + result.stderr).lower())
        else:
            report = json.loads(result.stdout)
            self.assertFalse(any(w.startswith('review refinement') for w in report['warnings']),
                             'A clean tracked checkout must not invent clause changes relative to HEAD')

    def test_broken_tracked_symlink_has_consistent_historical_policy(self):
        (self.spec / 'missing.md').symlink_to('absent.md')
        self.commit('Track a broken symlink')
        current = self.raw('check')
        historical = self.raw('diff', 'HEAD..HEAD')
        self.assertEqual(current.returncode == 0, historical.returncode == 0,
                         f'Current: {current.stdout}{current.stderr}; snapshot: {historical.stdout}{historical.stderr}')

    def test_directory_with_markdown_suffix_is_traversed_not_read_as_file(self):
        self.write('appendix.md/nested/contract.md', clause('SYS-NESTED'))
        added = self.commit('Use a directory whose name has a Markdown suffix')
        self.assertEqual(self.cli('check')['clauses'], 2)
        self.assertEqual({c['id'] for c in self.cli('export')}, {'SYS-BASE', 'SYS-NESTED'})
        self.assertEqual([e['commit'] for e in self.cli('log', 'SYS-NESTED')], [added])

    def test_root_directory_symlink_still_resolves_correct_repository(self):
        alias = self.home / 'spec alias'
        alias.symlink_to(self.spec, target_is_directory=True)
        self.assertEqual(self.cli('export', root=alias), self.cli('export'))
        self.assertEqual([e['commit'] for e in self.cli('log', 'SYS-BASE', root=alias)], [self.initial])
        self.assertEqual(self.cli('diff', 'HEAD..HEAD', root=alias), [])

    def test_git_metadata_is_not_scanned_when_root_is_repository_root(self):
        (self.repo / 'ndf.yaml').write_text(json.dumps(CONFIG))
        (self.repo / '.git/notes.md').write_text('<' * 7 + ' HEAD\n' + '=' * 7 + '\n' + '>' * 7 + ' side\n')
        result = self.cli('check', root=self.repo)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['clauses'], 1)
        self.assertEqual([c['id'] for c in self.cli('export', root=self.repo)], ['SYS-BASE'])

    def test_git_named_ancestor_outside_spec_scope_does_not_hide_clauses(self):
        destination = self.home / '.git' / 'ordinary-project'
        destination.parent.mkdir()
        self.repo.rename(destination)
        self.repo, self.spec = destination, destination / 'spec'
        self.assertEqual(self.cli('check')['clauses'], 1)
        self.assertEqual([e['commit'] for e in self.cli('log', 'SYS-BASE')], [self.initial])
        self.assertFalse(any(w.startswith('review refinement') for w in self.cli('check', '--since', 'HEAD')['warnings']))

    def test_explicit_branch_and_tag_namespaces_do_not_choose_wrong_revision(self):
        self.git('tag', 'release')
        self.git('checkout', '-qb', 'release')
        self.write('contract.md', clause(body='The system MUST count to 7.'))
        changed = self.commit('Branch named like a tag')
        self.assertEqual([e['commit'] for e in self.cli('log', 'SYS-BASE', '--ref', 'refs/tags/release')], [self.initial])
        self.assertEqual(self.cli('log', 'SYS-BASE', '--ref', 'refs/heads/release')[0]['commit'], changed)
        self.assertEqual(self.cli('diff', 'refs/tags/release..refs/heads/release')[0]['id'], 'SYS-BASE')

    def test_all_includes_detached_linked_worktree_head_not_just_branches(self):
        linked = self.home / 'detached worktree'
        self.git('worktree', 'add', '-q', '--detach', str(linked), self.initial)
        (linked / 'spec/contract.md').write_text(clause(body='The system MUST count to 5.'))
        self.git('add', '.', cwd=linked)
        self.git('commit', '-qm', 'Detached worktree obligation', cwd=linked)
        detached = self.git('rev-parse', 'HEAD', cwd=linked)
        self.assertNotIn(detached, {e['commit'] for e in self.cli('log', 'SYS-BASE')})
        self.assertIn(detached, {e['commit'] for e in self.cli('log', 'SYS-BASE', '--all')})

    def test_reference_address_spelling_does_not_change_resolved_graph_edge(self):
        self.write('refs/time.md', clause('REF-TIME'))
        self.write('contract.md', clause(body='The system MUST follow [[REF-TIME]].'))
        before = self.commit('Reference by stable ID')
        dependencies = self.cli('deps')
        for reference in ('refs/time.md#REF-TIME', './refs//time.md#REF-TIME'):
            with self.subTest(reference=reference):
                self.write('contract.md', clause(body=f'The system MUST follow [[{reference}]].'))
                self.commit('Spell the same reference using a file anchor')
                self.assertEqual(self.cli('deps'), dependencies)
                row, = self.cli('diff', before + '..HEAD')
                self.assertEqual(row['edges_added'], [])
                self.assertEqual(row['edges_removed'], [])

    def test_reordering_and_duplicate_mentions_do_not_duplicate_edges(self):
        self.write('refs/time.md', clause('REF-TIME'))
        self.write('contract.md', clause(body='The system MUST follow [[REF-TIME]].', meta='kind=req level=must layer=L1 depends-on=REF-TIME,SYS-BASE'))
        before = self.commit('One dependency and mention')
        self.write('contract.md', clause(body='The system MUST follow [[REF-TIME]] and [[REF-TIME | time]].', meta='kind=req level=must layer=L1 depends-on=SYS-BASE,REF-TIME,REF-TIME'))
        self.commit('Reorder list and repeat a mention')
        row, = self.cli('diff', before + '..HEAD')
        self.assertEqual(row['edges_added'], [])
        self.assertEqual(row['edges_removed'], [])
        self.assertEqual(len(self.cli('deps')), 2)

    def test_renaming_reference_file_preserves_reference_target_identity(self):
        self.write('refs/time.md', clause('REF-TIME'))
        self.write('contract.md', clause(body='The system MUST follow [[refs/time.md#REF-TIME]].'))
        before = self.commit('Reference an external projection')
        (self.spec / 'refs/time.md').rename(self.spec / 'refs/time renamed.md')
        self.write('contract.md', clause(body='The system MUST follow [[refs/time renamed.md#REF-TIME]].'))
        self.commit('Move the projected reference file')
        rows = {r['id']: r for r in self.cli('diff', before + '..HEAD')}
        self.assertEqual(rows['REF-TIME']['categories'], ['moved'])
        self.assertEqual(rows['SYS-BASE']['edges_added'], [])
        self.assertEqual(rows['SYS-BASE']['edges_removed'], [])

    def test_whole_file_reference_graph_changes_when_target_file_gains_clause(self):
        self.write('refs/time.md', clause('REF-A'))
        self.write('contract.md', clause(body='The system MUST follow [[refs/time.md]].'))
        before = self.commit('Reference all clauses in a projected file')
        self.write('refs/time.md', clause('REF-A') + clause('REF-B'))
        self.commit('Expand the projection without editing its consumers')
        rows = {r['id']: r for r in self.cli('diff', before + '..HEAD')}
        self.assertIn('SYS-BASE', rows, 'Resolved edge changes must be reported even when source text is unchanged')
        self.assertEqual(rows['SYS-BASE']['edges_added'], [{'type': 'mention', 'target': 'REF-B'}])
        self.assertEqual(rows['SYS-BASE']['edges_removed'], [])
        reverse = {r['id']: r for r in self.cli('diff', 'HEAD..' + before)}
        self.assertEqual(reverse['SYS-BASE']['edges_removed'], [{'type': 'mention', 'target': 'REF-B'}])

    def test_merge_revert_and_reapplication_preserve_full_clause_history(self):
        self.git('checkout', '-qb', 'feature')
        self.write('feature.md', clause('SYS-FEATURE'))
        feature = self.commit('Introduce feature clause')
        self.git('checkout', '-q', 'main')
        (self.repo / 'unrelated.txt').write_text('main-side work\n')
        main = self.commit('Independent main-side change')
        self.git('merge', '--no-ff', '-qm', 'Integrate feature', 'feature')
        merge = self.git('rev-parse', 'HEAD')
        self.git('revert', '-m', '1', '--no-edit', merge)
        reverted = self.git('rev-parse', 'HEAD')
        self.git('cherry-pick', feature)
        reapplied = self.git('rev-parse', 'HEAD')
        events = self.cli('log', 'SYS-FEATURE')
        self.assertEqual({e['commit'] for e in events}, {feature, merge, reverted, reapplied})
        self.assertEqual(next(e for e in events if e['commit'] == reverted)['changes'][0]['change'], 'deleted')
        self.assertEqual(events[0]['changes'][0]['change'], 'added')
        merge_event = next(e for e in events if e['commit'] == merge)
        self.assertEqual([c['parent'] for c in merge_event['changes']], [main])
        self.assertEqual(self.cli('diff', feature + '..HEAD'), [])

    def test_crisscross_merge_equal_snapshots_do_not_invent_final_clause_change(self):
        self.git('checkout', '-qb', 'left')
        self.write('contract.md', clause(body='The system MUST count to 9.'))
        left = self.commit('Left contract revision')
        self.git('checkout', '-qb', 'right', self.initial)
        self.write('other.md', clause('SYS-OTHER'))
        right = self.commit('Right independent clause')
        self.git('checkout', '-q', 'left')
        self.git('merge', '--no-ff', '-qm', 'Left integrates right', right)
        left_merge = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-q', 'right')
        self.git('merge', '--no-ff', '-qm', 'Right integrates old left', left)
        right_merge = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-q', 'left')
        self.git('merge', '--no-ff', '-qm', 'Integrate crisscross histories', 'right')
        final = self.git('rev-parse', 'HEAD')
        events = self.cli('log', 'SYS-BASE')
        self.assertEqual({e['commit'] for e in events}, {self.initial, left, left_merge, right_merge})
        self.assertNotIn(final, {e['commit'] for e in events})
        self.assertEqual(self.cli('diff', left_merge + '..' + right_merge), [])


if __name__ == '__main__':
    unittest.main()
