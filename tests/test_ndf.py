import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from ndf.cli import main
from ndf.core import parse, load, validate
from ndf.history import History

CONFIG = {'id-prefixes': ['SYS', 'VER', 'Q', 'D'], 'layers': {'L0': 'intent', 'L1': 'contract', 'L2': 'mechanism', 'L3': 'executable'}}


def clause(cid='SYS-001', body='The system MUST count.', layer='L1', extra=''):
    return f'## Counting {{#{cid}}}\n<!-- ndf: kind=req level=must layer={layer} {extra} -->\n\n{body}\n'


class Common(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'ndf.yaml').write_text(json.dumps(CONFIG))

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(['--root', str(self.root), '--json', *args])
        return code, out.getvalue(), err.getvalue()

class Tools(Common):
    def test_parser_ignores_code_and_handles_nested_headings(self):
        text = clause(body='''<!-- ndf: origin="A standard §3" -->
### Subheading
MUST remain here.
````markdown
## Fake {#SYS-999}
<!-- ndf: kind=info -->
[[MISSING]]
```python
x = 1
```
````
# Informative ending
[[ALSO-MISSING]]''')
        records = parse(text, 'a.md')
        self.assertEqual([c.id for c in records], ['SYS-001'])
        self.assertEqual(records[0].meta['origin'], 'A standard §3')
        self.assertEqual(records[0].refs, [])
        self.assertNotIn('Informative ending', records[0].body)

    def test_duplicate_dangling_and_cycle_errors(self):
        (self.root / 'a.md').write_text(clause(extra='refines=SYS-002', body='MUST [[MISSING]].') + clause('SYS-002', extra='refines=SYS-001') + clause('SYS-003') + clause('SYS-003'))
        code, out, _ = self.run_cli('check')
        self.assertEqual(code, 1)
        self.assertIn('duplicate ID', out)
        self.assertIn('dangling reference', out)
        self.assertIn('refinement cycle', out)

    def test_keywords_are_advisory_and_known_conflicts_warn(self):
        (self.root / 'a.md').write_text(clause(body='Count appropriately.', extra='conflicts-with=SYS-002') + clause('SYS-002'))
        code, out, _ = self.run_cli('check')
        self.assertEqual(code, 0)
        self.assertIn('known conflict', out)
        self.assertIn('no normative keyword', out)

    def test_coverage_links_not_tests_and_supersession(self):
        (self.root / 'a.md').write_text(clause() + clause('SYS-002', extra='status=superseded-by=SYS-001') + '''## Check {#VER-001}
<!-- ndf: kind=verif level=must layer=L3 verifies=SYS-001 -->
MUST pass.
''')
        code, out, _ = self.run_cli('coverage')
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(data['L1_must'], 1)
        self.assertEqual(data['linked'], 1)
        self.assertEqual(data['unverified'], [])

    def test_path_references_and_model_validation(self):
        (self.root / 'decisions').mkdir()
        (self.root / 'decisions/D-001.md').write_text('# Choice {#D-001}\n<!-- ndf: kind=decision -->\nChoice.')
        (self.root / 'a.md').write_text(clause(body='MUST use [[decisions/D-001]] and [[decisions/D-001#D-001]].', extra='model=missing.py'))
        code, out, _ = self.run_cli('check')
        self.assertEqual(code, 1)
        self.assertIn('missing or unsafe model', out)
        self.assertNotIn('dangling', out)

    def test_unresolved_merge_markers_fail(self):
        (self.root / 'a.md').write_text(clause(body='MUST count.\n<<<<<<< HEAD\nOne\n=======\nTwo\n>>>>>>> side'))
        code, out, _ = self.run_cli('check')
        self.assertEqual(code, 1)
        self.assertIn('unresolved Git conflict', out)

    def test_test_runner_success_failure_and_empty(self):
        self.assertEqual(self.run_cli('test')[0], 2)
        models = self.root / 'models'
        models.mkdir()
        test = models / 'test_model.py'
        test.write_text('import unittest\nclass Acceptance(unittest.TestCase):\n def test_VER_001(self): self.assertEqual(1 + 1, 2)\n')
        self.assertEqual(self.run_cli('test')[0], 0)
        test.write_text('import unittest\nclass Acceptance(unittest.TestCase):\n def test_VER_001(self): self.fail("SYS-001 violated")\n')
        self.assertEqual(self.run_cli('test')[0], 1)

    def test_init_and_ids(self):
        newroot = self.root / 'new'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--root', str(newroot), 'init']), 0)
        first = json.loads(self.run_cli('new-id', 'SYS-ADM')[1])['id']
        second = json.loads(self.run_cli('new-id', 'SYS-ADM')[1])['id']
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith('SYS-ADM-'))
        self.assertEqual(self.run_cli('new-id', 'UNKNOWN')[0], 2)

    def test_export_status_options_trace_and_deps(self):
        (self.root / 'refs').mkdir()
        (self.root / 'refs/source.md').write_text(clause('SYS-REF', extra='origin="Standard §1"'))
        (self.root / 'a.md').write_text(clause(extra='depends-on=SYS-REF', body='MUST act. ⟨TBD: bound⟩') + '''# Open {#Q-001}
<!-- ndf: kind=question status=open blocks=SYS-001 -->
Choose bound.
# Parameter {#SYS-PAR}
<!-- ndf: kind=option level=tbd layer=L2 default=1 explore=1,2 -->
Choose later.
''')
        for command in ('export', 'status', 'options', 'coverage', 'deps'):
            code, out, _ = self.run_cli(command)
            self.assertEqual(code, 0, out)
            self.assertTrue(json.loads(out))
        self.assertIn('SYS-001', self.run_cli('trace', 'SYS-001')[1])
        self.assertEqual(self.run_cli('trace', 'NOPE')[0], 2)


class GitHistory(Common):
    def git(self, *args, ok=True):
        result = subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD').stdout.strip()

    def setUp(self):
        super().setUp()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'NDF Test')
        self.git('config', 'user.email', 'ndf@example.invalid')
        (self.root / 'a.md').write_text(clause())
        self.base = self.commit('initial')

    def test_conflict_merge_history_has_both_parents_and_moves(self):
        self.git('checkout', '-qb', 'side')
        (self.root / 'a.md').write_text(clause(body='The system MUST count to 16.'))
        side = self.commit('side changes contract')
        self.git('checkout', '-q', 'main')
        (self.root / 'a.md').write_text(clause(body='The system MUST count to 9.'))
        main = self.commit('main changes contract')
        self.assertNotEqual(self.git('merge', 'side', ok=False).returncode, 0)
        (self.root / 'a.md').write_text(clause(body='The system MUST count to 12.'))
        merged = self.commit('resolve contract deliberately')
        (self.root / 'a.md').rename(self.root / 'moved space ü.md')
        moved = self.commit('move clause')
        history = History(self.root)
        events = history.events('SYS-001')
        self.assertEqual({e['commit'] for e in events}, {self.base, side, main, merged, moved})
        merge = next(e for e in events if e['commit'] == merged)
        self.assertEqual(set(merge['parents']), {side, main})
        self.assertEqual(len(merge['changes']), 2)
        self.assertEqual(events[0]['changes'][0]['change'], 'moved')
        code, out, _ = self.run_cli('diff', self.base + '..HEAD')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)[0]['change'], 'modified+moved')
        # Broken current prose cannot disable queries of valid historical snapshots.
        (self.root / 'bad.md').write_text(clause())
        self.assertEqual(self.run_cli('log', 'SYS-001')[0], 0)

    def test_merge_matching_one_parent_and_all_refs(self):
        self.git('checkout', '-qb', 'side')
        (self.root / 'a.md').write_text(clause(body='The system MUST count to 16.'))
        side = self.commit('side contract')
        self.git('checkout', '-q', 'main')
        (self.root / 'other.txt').write_text('unrelated')
        self.commit('main unrelated')
        self.git('merge', '--no-ff', '-qm', 'merge side', 'side')
        merge = self.git('rev-parse', 'HEAD').stdout.strip()
        events = History(self.root).events('SYS-001')
        event = next(e for e in events if e['commit'] == merge)
        self.assertEqual(len(event['changes']), 1)  # same as side; changed versus main
        self.assertIn(side, {e['commit'] for e in events})
        self.git('checkout', '-qb', 'unmerged')
        (self.root / 'a.md').write_text(clause(body='The system MUST count to 20.'))
        unmerged = self.commit('unmerged edit')
        self.git('checkout', '-q', 'main')
        self.assertNotIn(unmerged, {e['commit'] for e in History(self.root).events('SYS-001')})
        self.assertIn(unmerged, {e['commit'] for e in History(self.root).events('SYS-001', all_refs=True)})

    def test_deleted_and_reintroduced_clause(self):
        (self.root / 'a.md').write_text('No clauses.')
        deleted = self.commit('delete for test')
        self.assertEqual(History(self.root).events('SYS-001')[0]['changes'][0]['change'], 'deleted')
        (self.root / 'new.md').write_text(clause())
        self.commit('restore')
        self.assertEqual(len(History(self.root).events('SYS-001')), 3)

    def test_since_review_flag_even_for_clean_git_merge(self):
        (self.root / 'child.md').write_text(clause('SYS-002', layer='L2', extra='refines=SYS-001'))
        code, out, _ = self.run_cli('check', '--since', self.base)
        self.assertEqual(code, 0)
        self.assertIn('review refinement SYS-002 -> SYS-001', out)


if __name__ == '__main__':
    unittest.main()
