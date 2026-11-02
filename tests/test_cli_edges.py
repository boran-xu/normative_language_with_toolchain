"""Independent black-box regressions for invalid states and graph boundaries.

Expected behavior is specified here without importing implementation internals.
Every invocation is a fresh process; histories and mutations are disposable.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'ndf.py'
CONFIG = {'id-prefixes': ['SYS', 'VER', 'Q'], 'layers': ['L0', 'L1', 'L2', 'L3']}


def clause(cid='SYS-001', body='The system MUST count.', extra='', kind='req', layer='L1'):
    level = '' if kind in {'question', 'decision'} else f'level=must layer={layer}'
    return f'## Requirement {{#{cid}}}\n<!-- ndf: kind={kind} {level} {extra} -->\n\n{body}\n'


class CliEdges(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.root = self.repo / 'spec'
        self.root.mkdir()
        (self.root / 'ndf.yaml').write_text(json.dumps(CONFIG), encoding='utf-8')
        self.write('behavior.md', clause())

    def write(self, path, content):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding='utf-8')

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), '--root', str(self.root), '--json', *args],
                              text=True, capture_output=True, timeout=20)

    def data(self, *args, status=0):
        result = self.cli(*args)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.repo), *args], text=True,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def history(self):
        self.git('init', '-q')
        self.git('config', 'user.name', 'NDF fixture tester')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('add', '.')
        self.git('commit', '-qm', 'Initial contract')
        return self.git('rev-parse', 'HEAD')

    def test_inline_code_reference_examples_do_not_create_dangling_links(self):
        self.write('behavior.md', clause(body='The system MUST count. Write `[[UNASSIGNED]]` only as a syntax example.'))
        result = self.data('check')
        self.assertEqual(result['errors'], [])

    def test_quoted_keyword_in_inline_code_does_not_establish_obligation(self):
        self.write('behavior.md', clause(body='The word `MUST` is shown here as syntax; no obligation is stated.'))
        result = self.data('check')
        self.assertTrue(any('no normative keyword' in w for w in result['warnings']))

    def test_fenced_conflict_example_is_informative(self):
        self.write('behavior.md', clause(body='''The system MUST count.
````markdown
<<<<<<< HEAD
Count to 10.
=======
Count to 20.
>>>>>>> other
````
'''))
        result = self.data('check')
        self.assertEqual(result['errors'], [])

    def test_path_references_contribute_to_external_dependency_surface(self):
        self.write('refs/protocol.md', clause('SYS-REF', body='The frame MUST contain a checksum.'))
        self.write('behavior.md', clause(body='The system MUST follow [[refs/protocol.md#SYS-REF | protocol checksum]].'))
        rows = self.data('deps')
        self.assertEqual({(row['id'], row['target']) for row in rows}, {('SYS-001', 'SYS-REF')})

    def test_external_directory_filter_does_not_match_sibling_prefix(self):
        self.write('refs/protocol.md', clause('SYS-REF'))
        self.write('refs-old/legacy.md', clause('SYS-OLD'))
        self.write('behavior.md', clause(body='The system MUST follow [[SYS-REF]] and [[SYS-OLD]].'))
        with_slash = self.data('deps', 'refs/')
        without_slash = self.data('deps', 'refs')
        expected = {('SYS-001', 'SYS-REF')}
        self.assertEqual({(r['id'], r['target']) for r in with_slash}, expected)
        self.assertEqual({(r['id'], r['target']) for r in without_slash}, expected)

    def test_archived_questions_do_not_reappear_as_open_work(self):
        self.write('questions.md', clause('Q-OLD', body='Old question.', kind='question', extra='status=deprecated') +
                   clause('Q-NEW', body='New question.', kind='question', extra='status=open'))
        coverage = self.data('coverage')
        self.assertEqual(coverage['open_questions'], ['Q-NEW'])

    def test_empty_supersession_target_is_rejected(self):
        self.write('behavior.md', clause(extra='status=superseded-by='))
        result = self.data('check', status=1)
        self.assertTrue(result['errors'])

    def test_historical_queries_ignore_non_utf8_worktree_markdown(self):
        revision = self.history()
        (self.root / 'broken.md').write_bytes(b'not UTF-8: \xff')
        rows = self.data('log', 'SYS-001')
        self.assertEqual([row['commit'] for row in rows], [revision])
        self.assertEqual(self.data('diff', revision + '..' + revision), [])

    def test_model_runner_cannot_pass_when_discovery_executes_zero_tests(self):
        # unittest discovery does not descend into non-package directories.
        # A test runner must either discover this failing test or reject the
        # zero-executed-test situation, rather than claim success.
        self.write('models/nested/test_failure.py', '''import unittest
class Acceptance(unittest.TestCase):
    def test_VER_001(self):
        self.fail("SYS-001 must not silently pass")
''')
        result = self.cli('test')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dependency_cycle_and_disconnected_clause_trace(self):
        self.write('behavior.md', clause('SYS-A', extra='depends-on=SYS-B') +
                   clause('SYS-B', extra='depends-on=SYS-A') + clause('SYS-ISOLATED'))
        rows = self.data('trace', 'SYS-A')
        self.assertEqual({r['id'] for r in rows}, {'SYS-A', 'SYS-B'})
        self.assertEqual(sum(not r['repeated'] for r in rows), 2)
        self.assertEqual(sum(r['repeated'] for r in rows), 1)

    def test_duplicate_metadata_and_invalid_manifest_fail_cleanly(self):
        self.write('behavior.md', clause(extra='level=should'))
        self.assertTrue(self.data('check', status=1)['errors'])
        (self.root / 'ndf.yaml').write_text('[]', encoding='utf-8')
        result = self.cli('check')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Traceback', result.stderr)

    def test_unknown_ref_fails_cleanly_without_changing_worktree(self):
        self.history()
        before = self.git('status', '--porcelain')
        result = self.cli('diff', 'not-a-real-ref..HEAD')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(self.git('status', '--porcelain'), before)


if __name__ == '__main__':
    unittest.main()
