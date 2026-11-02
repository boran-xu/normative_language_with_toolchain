import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from ndf.cli import main
from ndf.core import parse, validate
from ndf.glossary import warnings
from ndf.graph import trace, render_trace
from ndf.history import changelog

CONFIG = {'id-prefixes': ['SYS', 'DEF', 'VER'], 'layers': ['L0', 'L1', 'L2', 'L3']}


def record(cid, body='', meta='kind=req level=must layer=L1', title='Requirement'):
    return parse(f'## {title} {{#{cid}}}\n<!-- ndf: {meta} -->\n{body}\n', 'behavior.md')[0]


class Glossary(unittest.TestCase):
    def test_definitions_from_headings_and_proposal_style_bullets(self):
        definitions = [record('DEF-001', meta='kind=def level=must layer=L1', title='Credit Pool'),
                       record('DEF-002', '- **running / stopped** — the states.\n- **FCS** — checksum.', meta='kind=def level=must layer=L1', title='Definitions')]
        clauses = definitions + [record('SYS-001', 'The Credit Pool MUST track FCS while Running or Stopped. The Buffer MUST retain VLAN.')]
        messages = warnings(clauses, CONFIG)
        self.assertEqual(len(messages), 2)
        self.assertIn('"Buffer"', messages[0])
        self.assertIn('"VLAN"', messages[1])

    def test_simple_prose_definitions_and_sentence_capitalization(self):
        definition = record('DEF-001', 'BCD means one decimal digit per nibble.', meta='kind=def level=must layer=L1')
        clauses = [definition, record('SYS-001', 'Stopping MUST preserve BCD. Reset MUST clear it.')]
        self.assertEqual(warnings(clauses, CONFIG), [])

    def test_synonyms_from_glossary_prose_and_manifest(self):
        definition = record('DEF-001', 'An Ethernet unit.\n**Synonyms**: packet, datagram', meta='kind=def level=must layer=L1', title='frame')
        clause = record('SYS-001', 'The packet MUST forward each datagram and preserve the PDU.')
        config = {**CONFIG, 'glossary': {'synonyms': {'PDU': 'frame'}}}
        messages = warnings([definition, clause], config)
        self.assertEqual(len(messages), 3)
        self.assertTrue(all('prefer "frame"' in m for m in messages))
        self.assertFalse(warnings([definition, record('SYS-001', 'The frame MUST pass.')], config))

    def test_ignore_code_references_metadata_and_substrings(self):
        definition = record('DEF-001', '**Aliases**: packet', meta='kind=def level=must layer=L1', title='frame')
        body = '''The system MUST retain packetized data.
`Packet UnknownTerm`
[[UnknownID | UnknownLabel]]
````markdown
Packet UnknownTerm
```python
Something
```
````
<!-- note: UnknownTerm -->'''
        self.assertEqual(warnings([definition, record('SYS-001', body)], CONFIG), [])

    def test_warnings_are_advisory_in_check_and_invalid_mapping_is_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'ndf.yaml').write_text(json.dumps(CONFIG))
            (root / 'a.md').write_text('## Requirement {#SYS-001}\n<!-- ndf: kind=req level=must layer=L1 -->\nThe Buffer MUST count.')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(['--root', directory, '--json', 'check'])
            self.assertEqual(code, 0)
            self.assertIn('undefined capitalized term', output.getvalue())
        with self.assertRaisesRegex(ValueError, 'mapping'):
            warnings([], {**CONFIG, 'glossary': {'synonyms': []}})


class Trace(unittest.TestCase):
    def test_recursive_refinements_dependencies_and_verification(self):
        clauses = [record('SYS-000', meta='kind=arch level=must layer=L0'),
                   record('SYS-001', meta='kind=req level=must layer=L1 refines=SYS-000 depends-on=SYS-010'),
                   record('SYS-002', meta='kind=req level=must layer=L2 refines=SYS-001'),
                   record('SYS-010', meta='kind=req level=must layer=L1 depends-on=SYS-011'),
                   record('SYS-011'),
                   record('VER-001', meta='kind=verif level=must layer=L3 verifies=SYS-011')]
        rows = trace(clauses, 'SYS-000')
        self.assertEqual({r['id'] for r in rows}, {'SYS-000', 'SYS-001', 'SYS-002', 'SYS-010', 'SYS-011'})
        leaf = next(r for r in rows if r['id'] == 'SYS-011')
        self.assertEqual(leaf['verified_by'], ['VER-001'])
        self.assertEqual(leaf['relation'], 'depends-on')
        self.assertEqual(leaf['source'], 'SYS-010')
        rendered = '\n'.join(render_trace(rows))
        self.assertIn('refined-by: SYS-001', rendered)
        self.assertIn('verified-by: VER-001', rendered)

    def test_cycle_shared_node_mentions_and_nonrecursive_edges(self):
        clauses = [record('SYS-A', 'MUST [[SYS-Z]].', meta='kind=req level=must layer=L1 depends-on=SYS-B,SYS-C'),
                   record('SYS-B', meta='kind=req level=must layer=L1 depends-on=SYS-C'),
                   record('SYS-C', meta='kind=req level=must layer=L1 depends-on=SYS-A'), record('SYS-Z')]
        rows = trace(clauses, 'SYS-A')
        self.assertNotIn('SYS-Z', [r['id'] for r in rows])
        self.assertEqual(len([r for r in rows if not r['repeated']]), 3)
        self.assertEqual(len(rows), 5)
        self.assertIn('(already shown)', '\n'.join(render_trace(rows)))

    def test_long_dependency_chain_without_recursion_limit(self):
        clauses = [record(f'SYS-{i}', meta='kind=req level=must layer=L1' + (f' depends-on=SYS-{i+1}' if i < 1199 else '')) for i in range(1200)]
        self.assertEqual(len(trace(clauses, 'SYS-0')), 1200)

    def test_json_trace_is_structured(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'ndf.yaml').write_text(json.dumps(CONFIG))
            (root / 'a.md').write_text('## Requirement {#SYS-001}\n<!-- ndf: kind=req level=must layer=L1 -->\nMUST count.')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(['--root', directory, '--json', 'trace', 'SYS-001'])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())[0]['id'], 'SYS-001')


class Diff(unittest.TestCase):
    def test_formatting_vs_text_changes_and_code_whitespace(self):
        before = record('SYS-001', 'The system MUST respond\nwithin 10 ms.')
        after = record('SYS-001', 'The   system MUST respond within 10 ms.')
        row = changelog({before.id: before}, {after.id: after})[0]
        self.assertEqual(row['categories'], ['formatting-only'])
        after.body = 'The system MUST respond within 20 ms.'
        self.assertEqual(changelog({before.id: before}, {after.id: after})[0]['categories'], ['modified'])
        self.assertIn('20 ms', changelog({before.id: before}, {after.id: after})[0]['body_diff'])
        before.body, after.body = '```python\n  run()\n```', '```python\n    run()\n```'
        self.assertEqual(changelog({before.id: before}, {after.id: after})[0]['categories'], ['modified'])
        before.body, after.body = '`a  b` MUST match.', '`a b` MUST match.'
        self.assertEqual(changelog({before.id: before}, {after.id: after})[0]['categories'], ['modified'])

    def test_status_edges_census_and_moves(self):
        old = record('SYS-001', 'MUST [[SYS-002]]. ⟨TBD: bound⟩', meta='kind=req level=must layer=L1 depends-on=SYS-002 status=stable')
        new = record('SYS-001', 'MUST [[SYS-003]].', meta='kind=req level=must layer=L1 depends-on=SYS-003 status=superseded-by=SYS-003')
        new.path = 'archive.md'
        row = changelog({old.id: old}, {new.id: new})[0]
        self.assertEqual(row['categories'], ['modified', 'moved', 'superseded'])
        self.assertIn({'type': 'depends-on', 'target': 'SYS-002'}, row['edges_removed'])
        self.assertIn({'type': 'mention', 'target': 'SYS-003'}, row['edges_added'])
        self.assertEqual(row['census_delta']['TBD_markers'], -1)
        new.meta['status'] = 'deprecated'
        self.assertIn('deprecated', changelog({old.id: old}, {new.id: new})[0]['categories'])

    def test_option_and_question_closure(self):
        for kind, field in [('option', 'open_options'), ('question', 'open_questions')]:
            old = record('SYS-001', meta=f'kind={kind} level=tbd layer=L2 status=draft')
            new = record('SYS-001', meta=f'kind={kind} level=must layer=L2 status=closed')
            self.assertEqual(changelog({old.id: old}, {new.id: new})[0]['census_delta'][field], -1)

    def test_add_delete_and_edge_reordering(self):
        old = record('SYS-001', 'MUST count.', meta='kind=req level=must layer=L1 depends-on=SYS-002,SYS-003')
        new = record('SYS-001', 'MUST count.', meta='kind=req level=must layer=L1 depends-on=SYS-003,SYS-002')
        row = changelog({old.id: old}, {new.id: new})[0]
        self.assertEqual(row['categories'], ['formatting-only'])
        self.assertEqual(row['edges_added'], [])
        self.assertEqual(changelog({}, {new.id: new})[0]['categories'], ['added'])
        self.assertEqual(changelog({old.id: old}, {})[0]['categories'], ['deleted'])


if __name__ == '__main__':
    unittest.main()
