"""Independent adversarial Markdown/reference/glossary CLI contracts.

These tests do not import parser internals. They exercise ordinary Markdown
boundaries and the documented NDF authoring/link formats through fresh processes.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'ndf.py'
CONFIG = {'id-prefixes': ['SYS', 'DEF', 'REF'], 'layers': ['L0', 'L1', 'L2', 'L3']}


def clause(cid='SYS-001', body='The system MUST count.', kind='req', title='Requirement', indent='', close=''):
    return (f'{indent}## {title} {{#{cid}}}{close}\n'
            f'<!-- ndf: kind={kind} level=must layer=L1 -->\n\n{body}\n')


class MarkdownBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-markdown-audit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'spec'
        self.root.mkdir()
        self.write('ndf.yaml', json.dumps(CONFIG))

    def write(self, path, value):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(value, encoding='utf-8')

    def cli(self, *args, status=0):
        result = subprocess.run([sys.executable, str(CLI), '--root', str(self.root), '--json', *args],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return json.loads(result.stdout)

    def ids(self):
        return [c['id'] for c in self.cli('export')]

    def test_html_comment_cannot_create_real_clause(self):
        self.write('behavior.md', '''<!--
## Archived sketch {#SYS-HIDDEN}
This is only a commented draft.
-->
''' + clause())
        self.assertEqual(self.ids(), ['SYS-001'])

    def test_inline_code_comment_delimiter_does_not_hide_later_clauses(self):
        self.write('behavior.md', clause(body='The system MUST retain `<!--` literally.') + clause('SYS-002'))
        self.assertEqual(self.ids(), ['SYS-001', 'SYS-002'])

    def test_html_comment_reference_does_not_create_dependency(self):
        self.write('behavior.md', clause(body='The system MUST count.\n<!-- old link [[NOT-ASSIGNED]] -->'))
        self.assertEqual(self.cli('check')['errors'], [])
        self.assertEqual(self.cli('export')[0]['refs'], [])

    def test_multiline_inline_code_link_remains_an_example(self):
        self.write('behavior.md', clause(body='The system MUST count. A syntax example is `begin\n[[NOT-ASSIGNED]]\nend` within this paragraph.'))
        self.assertEqual(self.cli('check')['errors'], [])
        self.assertEqual(self.cli('export')[0]['refs'], [])

    def test_indented_code_links_and_metadata_are_not_authoritative(self):
        self.write('behavior.md', clause(body='The system MUST count.\n\n    [[NOT-ASSIGNED]]\n    <!-- ndf: kind=info -->\n'))
        data = self.cli('check')
        self.assertEqual(data['errors'], [])
        self.assertEqual(self.cli('export')[0]['meta']['kind'], 'req')

    def test_indented_code_keyword_does_not_supply_obligation(self):
        self.write('behavior.md', clause(body='This paragraph illustrates a keyword.\n\n    MUST\n'))
        data = self.cli('check')
        self.assertTrue(any('no normative keyword' in warning for warning in data['warnings']))

    def test_closing_atx_hashes_do_not_hide_clause(self):
        self.write('behavior.md', clause(close=' ###'))
        self.assertEqual(self.ids(), ['SYS-001'])
        self.assertEqual(self.cli('export')[0]['title'], 'Requirement')

    def test_up_to_three_space_indented_heading_remains_heading(self):
        for width in (1, 2, 3):
            with self.subTest(width=width):
                self.write('behavior.md', clause(indent=' ' * width))
                self.assertEqual(self.ids(), ['SYS-001'])

    def test_escaped_link_delimiters_do_not_create_reference(self):
        self.write('behavior.md', clause(body=r'The system MUST count. Write \[[NOT-ASSIGNED]] as literal text.'))
        self.assertEqual(self.cli('check')['errors'], [])
        self.assertEqual(self.cli('export')[0]['refs'], [])

    def test_relative_dot_paths_resolve_same_clause_and_dependency(self):
        self.write('refs/protocol.md', clause('REF-001', 'The checksum MUST be retained.'))
        self.write('behavior.md', clause(body='The system MUST follow [[./refs/protocol.md#REF-001 | checksum]].'))
        self.assertEqual(self.cli('check')['errors'], [])
        data = self.cli('deps')
        self.assertEqual([(r['id'], r['target']) for r in data], [('SYS-001', 'REF-001')])

    def test_deps_accepts_equivalent_root_relative_directory_spelling(self):
        self.write('refs/protocol.md', clause('REF-001'))
        self.write('behavior.md', clause(body='The system MUST follow [[REF-001]].'))
        expected = self.cli('deps', 'refs')
        self.assertTrue(expected)
        self.assertEqual(self.cli('deps', './refs'), expected)
        self.assertEqual(self.cli('deps', 'refs//'), expected)

    def test_glossary_phrase_survives_prose_line_wrapping(self):
        self.write('glossary.md', clause('DEF-001', 'The shared credit allocation.', kind='def', title='Credit Pool'))
        self.write('behavior.md', clause(body='The Credit\nPool MUST retain the allocation.'))
        messages = self.cli('check')['warnings']
        self.assertFalse(any('undefined capitalized term' in m for m in messages), messages)

    def test_synonym_phrase_survives_prose_line_wrapping(self):
        self.write('glossary.md', clause('DEF-001', 'A transmission unit.\nSynonyms: data packet', kind='def', title='frame'))
        self.write('behavior.md', clause(body='The data\npacket MUST retain its checksum.'))
        messages = self.cli('check')['warnings']
        self.assertTrue(any('inconsistent synonym "data packet"' in m for m in messages), messages)

    def test_deeper_unanchored_headings_remain_inside_clause(self):
        self.write('behavior.md', clause(body='The system MUST count.\n### Detail\nIt MUST preserve the result.\n## Informative ending\nOutside clause.'))
        row, = self.cli('export')
        self.assertIn('### Detail', row['body'])
        self.assertNotIn('Outside clause', row['body'])

    def test_tilde_and_long_backtick_fences_preserve_literal_examples(self):
        for opening, closing in [('~~~markdown', '~~~~'), ('````markdown', '`````')]:
            with self.subTest(opening=opening):
                self.write('behavior.md', clause(body='The system MUST count.\n' + opening + '\n## Fake {#SYS-FAKE}\n[[UNASSIGNED]]\n```python\nrun()\n```\n' + closing))
                self.assertEqual(self.ids(), ['SYS-001'])
                self.assertEqual(self.cli('export')[0]['refs'], [])

    def test_multibackticks_can_quote_a_single_backtick(self):
        self.write('behavior.md', clause(body='The system MUST count. Example: ``[[UNASSIGNED]] and `literal` ``.'))
        self.assertEqual(self.cli('check')['errors'], [])

    def test_crlf_file_and_unicode_path_and_id_are_consistent(self):
        self.write('refs/temps ü.md', clause('REF-É', 'The count MUST remain valid.'))
        text = clause(body='The system MUST follow [[refs/temps ü.md#REF-É]].').replace('\n', '\r\n')
        (self.root / 'behavior.md').write_bytes(text.encode('utf-8'))
        self.assertEqual(self.cli('check')['errors'], [])
        data = self.cli('deps')
        self.assertEqual({r['target'] for r in data}, {'REF-É'})

    def test_metadata_quotes_and_successive_comments_are_retained(self):
        self.write('behavior.md', clause(body='<!-- ndf: origin="A standard §3" origin-status=paraphrase -->\nThe system MUST count.'))
        row, = self.cli('export')
        self.assertEqual(row['meta']['origin'], 'A standard §3')
        self.assertEqual(row['meta']['origin-status'], 'paraphrase')

    def test_whole_file_projection_reference_reports_each_clause_once(self):
        self.write('refs/protocol.md', clause('REF-A') + clause('REF-B'))
        self.write('behavior.md', clause(body='The system MUST follow [[refs/protocol.md]] and [[REF-A]].'))
        rows = self.cli('deps')
        self.assertEqual([(r['id'], r['target']) for r in rows], [('SYS-001', 'REF-A'), ('SYS-001', 'REF-B')])


if __name__ == '__main__':
    unittest.main()
