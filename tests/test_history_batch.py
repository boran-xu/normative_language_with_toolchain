"""Git object batching/cache correctness and operation-count regressions.

History is exercised directly to count Git subprocess calls without timing
thresholds. Every test builds independent authored objects in a disposable repo.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ndf.history import History, changelog
from ndf.core import parse


def clause(cid='SYS-001', body='The system MUST retain its count.'):
    return f'## Contract {{#{cid}}}\n<!-- ndf: kind=req level=must layer=L1 -->\n\n{body}\n'


class HistoryBatch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-history-batch-')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        for key, value in [('user.name', 'Batch Auditor'), ('user.email', 'batch@example.invalid'), ('commit.gpgsign', 'false'), ('core.hooksPath', os.devnull)]:
            self.git('config', key, value)
        self.root = self.repo / 'design/spec'
        self.root.mkdir(parents=True)
        (self.root / 'ndf.yaml').write_text(json.dumps({'id-prefixes': ['SYS'], 'layers': ['L0', 'L1', 'L2', 'L3']}))

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.repo), *args], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def commit(self, title):
        self.git('add', '.')
        self.git('commit', '-qm', title)
        return self.git('rev-parse', 'HEAD')

    def test_history_git_processes_do_not_scale_with_files_times_commits(self):
        for number in range(32):
            self.write(f'subsystem/{number:03}/contract.md', clause(f'SYS-{number:03}'))
        commits = [self.commit('Initial system')]
        for number in range(12):
            self.write('subsystem/000/contract.md', clause('SYS-000', f'The system MUST count to {number}.'))
            commits.append(self.commit(f'Adjust bound {number}'))
        real_run = subprocess.run
        with patch('ndf.history.subprocess.run', wraps=real_run) as runs:
            history = History(self.root)
            events = history.events('SYS-000')
        self.assertEqual({e['commit'] for e in events}, set(commits))
        git_commands = [call.args[0] for call in runs.call_args_list if call.args and call.args[0][0] == 'git']
        self.assertLessEqual(len(git_commands), 12,
                             f'Git process fan-out must depend on hierarchy depth, not files×commits: {len(git_commands)} processes')

    def test_identical_blob_is_parsed_once_across_unchanged_commits_and_move(self):
        content = clause()
        self.write('requirements.md', content)
        commits = [self.commit('Contract introduced')]
        for number in range(6):
            (self.repo / 'build-notes.txt').write_text(f'Unrelated change {number}\n')
            commits.append(self.commit(f'Build housekeeping {number}'))
        old = self.root / 'requirements.md'
        new = self.root / 'nested/Unicode ü\nname.md'
        new.parent.mkdir()
        old.rename(new)
        moved = self.commit('Move requirement')
        with patch('ndf.history.parse', wraps=parse) as parse_calls:
            events = History(self.root).events('SYS-001')
        self.assertEqual(parse_calls.call_count, 1,
                         'Immutable clause content should be parsed once regardless of commits or filename moves')
        self.assertEqual({e['commit'] for e in events}, {commits[0], moved})
        self.assertEqual(events[0]['path'], 'nested/Unicode ü\nname.md')
        self.assertEqual(events[0]['changes'][0]['change'], 'moved')

    def test_reused_blob_at_two_paths_still_rejects_duplicate_identity(self):
        self.write('one.md', clause())
        self.write('two.md', clause())
        self.commit('Duplicate identity at two paths')
        with self.assertRaisesRegex(ValueError, 'duplicate ID SYS-001'):
            History(self.root).snapshot('HEAD')

    def test_symbolic_revision_refreshes_after_branch_moves(self):
        self.write('requirements.md', clause())
        first = self.commit('First contract')
        history = History(self.root)
        self.assertIn('SYS-001', history.snapshot('HEAD'))
        self.write('requirements.md', clause('SYS-002'))
        second = self.commit('Replace contract')
        self.assertEqual(set(history.snapshot('HEAD')), {'SYS-002'})
        self.assertEqual(set(history.snapshot(first)), {'SYS-001'})
        self.assertEqual(set(history.snapshot(second)), {'SYS-002'})

    def test_cached_blob_templates_do_not_share_mutable_clause_state_across_snapshots(self):
        self.write('requirements.md', clause())
        first = self.commit('Original contract')
        (self.repo / 'notes.txt').write_text('Unrelated parent change\n')
        second = self.commit('Same specification in another commit')
        history = History(self.root)
        original = history.snapshot(first)['SYS-001']
        original.meta['level'] = 'may'
        original.refs.append('UNRELATED')
        later = history.snapshot(second)['SYS-001']
        self.assertEqual(later.meta['level'], 'must')
        self.assertEqual(later.refs, [])

    def test_scoped_history_ignores_invalid_markdown_outside_specification(self):
        self.write('requirements.md', clause())
        (self.repo / 'outside.md').write_bytes(b'not UTF-8: \xff')
        first = self.commit('Scoped contract beside unrelated binary document')
        self.assertEqual(set(History(self.root).snapshot(first)), {'SYS-001'})
        self.assertEqual([e['commit'] for e in History(self.root).events('SYS-001')], [first])

    def test_root_path_absent_in_early_commits_is_empty_not_error(self):
        (self.root / 'ndf.yaml').unlink()
        self.root.rmdir()
        (self.repo / 'readme.txt').write_text('Before spec existed\n')
        first = self.commit('Before the specification')
        self.write('requirements.md', clause())
        second = self.commit('Introduce specification')
        history = History(self.root)
        self.assertEqual(history.snapshot(first), {})
        self.assertEqual(set(history.snapshot(second)), {'SYS-001'})
        self.assertEqual([e['commit'] for e in history.events('SYS-001')], [second])

    def test_pretty_subjects_match_git_for_multiline_unicode_and_empty_subjects(self):
        self.write('requirements.md', clause())
        first = self.commit('A multiline\nsubject ü\n\nBody paragraph.')
        self.write('requirements.md', clause(body='The system MUST count to 3.'))
        self.git('add', '.')
        self.git('commit', '-q', '--allow-empty-message', '-m', '')
        second = self.git('rev-parse', 'HEAD')
        events = History(self.root).events('SYS-001')
        self.assertEqual({e['commit'] for e in events}, {first, second})
        for event in events:
            expected = self.git('show', '-s', '--format=%s', event['commit'])
            self.assertEqual(event['subject'], expected)

    def test_large_blob_does_not_desynchronize_batch_object_reads(self):
        self.write('huge.md', clause('SYS-HUGE', 'The system MUST retain this text.\n' + 'ordinary prose ' * 90_000))
        self.write('small.md', clause('SYS-SMALL'))
        self.write('empty.md', '')
        self.commit('Large, small and empty Markdown objects')
        snapshot = History(self.root).snapshot('HEAD')
        self.assertEqual(set(snapshot), {'SYS-HUGE', 'SYS-SMALL'})
        self.assertGreater(len(snapshot['SYS-HUGE'].body), 1_000_000)
        self.assertEqual(snapshot['SYS-SMALL'].body, 'The system MUST retain its count.')

    def test_code_unicode_separators_are_preserved_in_diff_and_classification(self):
        self.write('requirements.md', clause(body='The system MUST retain this code:\n```text ndf:normative\nleft\vright\n```'))
        first = self.commit('Code contains vertical tab')
        self.write('requirements.md', clause(body='The system MUST retain this code:\n```text ndf:normative\nleft\fright\n```'))
        second = self.commit('Code contains form feed instead')
        history = History(self.root)
        row, = changelog(history.snapshot(first), history.snapshot(second))
        self.assertEqual(row['categories'], ['modified'])
        self.assertIn('left\vright', row['body_diff'])
        self.assertIn('left\fright', row['body_diff'])

    def test_added_clause_patch_has_no_invented_empty_old_line(self):
        self.write('requirements.md', clause())
        self.commit('Initial contract')
        row, = changelog({}, History(self.root).snapshot('HEAD'))
        self.assertIn('@@ -0,0 +', row['body_diff'])

    def test_sha256_repository_tree_object_ids_are_supported_when_git_supports_them(self):
        other = Path(self.temp.name) / 'sha256'
        other.mkdir()
        result = subprocess.run(['git', '-C', str(other), 'init', '-q', '--object-format=sha256', '-b', 'main'], capture_output=True, text=True)
        if result.returncode:
            self.skipTest('installed Git does not support SHA-256 repositories')
        self.repo = other
        for key, value in [('user.name', 'Batch Auditor'), ('user.email', 'batch@example.invalid'), ('commit.gpgsign', 'false')]:
            self.git('config', key, value)
        self.root = other / 'spec'
        self.root.mkdir()
        self.write('a/deep/requirement.md', clause())
        first = self.commit('SHA-256 specification')
        self.assertEqual(len(first), 64)
        self.assertEqual(set(History(self.root).snapshot(first)), {'SYS-001'})
        self.assertEqual([e['commit'] for e in History(self.root).events('SYS-001')], [first])


if __name__ == '__main__':
    unittest.main()
