"""Second-pass interaction checks, independently specified through the CLI.

These combine supported Markdown features rather than repeating isolated
comment/code/path tests from the first adversarial pass.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'ndf.py'
CONFIG = {'id-prefixes': ['SYS', 'REF'], 'layers': ['L0', 'L1', 'L2', 'L3']}


def clause(cid='SYS-001', body='The system MUST count.', title='Requirement'):
    return f'## {title} {{#{cid}}}\n<!-- ndf: kind=req level=must layer=L1 -->\n\n{body}\n'


class MarkdownInteractions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-markdown-interaction-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'spec'
        self.root.mkdir()
        self.write('ndf.yaml', json.dumps(CONFIG))
        self.write('refs/source.md', clause('REF-001'))

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')

    def cli(self, *args, status=0):
        result = subprocess.run([sys.executable, str(CLI), '--root', str(self.root), '--json', *args], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return json.loads(result.stdout)

    def own_ids(self):
        return [row['id'] for row in self.cli('export') if row['path'] == 'behavior.md']

    def assert_reference_visible(self, body):
        self.write('behavior.md', clause(body=body))
        rows = self.cli('deps')
        self.assertEqual([(row['id'], row['target']) for row in rows], [('SYS-001', 'REF-001')])

    def test_backtick_in_comment_cannot_corrupt_later_code_visibility(self):
        body = '<!-- A lone ` in a comment. -->\nThe system MUST retain `<!--` literally.'
        self.write('behavior.md', clause(body=body) + clause('SYS-002'))
        self.assertEqual(self.own_ids(), ['SYS-001', 'SYS-002'])

    def test_backtick_in_tilde_fence_cannot_corrupt_later_code_visibility(self):
        body = '~~~text\nA lone ` in a code example.\n~~~\nThe system MUST retain `<!--` literally.'
        self.write('behavior.md', clause(body=body) + clause('SYS-002'))
        self.assertEqual(self.own_ids(), ['SYS-001', 'SYS-002'])

    def test_unmatched_backticks_cannot_form_span_across_clause_blocks(self):
        self.write('behavior.md', clause(body='The system MUST show a literal unmatched ` character.') + '\n' + clause('SYS-002', body='The system MUST show an unmatched ` character too.'))
        self.assertEqual(self.own_ids(), ['SYS-001', 'SYS-002'])

    def test_unmatched_backticks_cannot_form_span_across_blank_paragraph(self):
        self.assert_reference_visible('The system MUST show an unmatched ` character.\n\nIt MUST follow [[REF-001]] and show another unmatched ` character.')

    def test_escaped_backticks_do_not_hide_real_references(self):
        self.assert_reference_visible(r'The system MUST show \` literally, follow [[REF-001]], and show another \` literally.')

    def test_even_backslashes_leave_real_backtick_code_span(self):
        body = r'The system MUST show \\`[[UNASSIGNED]]` as a code example.'
        self.write('behavior.md', clause(body=body))
        self.assertEqual(self.cli('check')['errors'], [])
        row = next(row for row in self.cli('export') if row['id'] == 'SYS-001')
        self.assertEqual(row['refs'], [])

    def test_inline_code_inside_heading_is_preserved_in_title(self):
        self.write('behavior.md', clause(title='Set `running` state'))
        row = next(row for row in self.cli('export') if row['id'] == 'SYS-001')
        self.assertEqual(row['title'], 'Set `running` state')

    def test_comment_inside_heading_is_not_preserved_as_title_text(self):
        self.write('behavior.md', clause(title='Set <!-- editorial note --> running state'))
        row = next(row for row in self.cli('export') if row['id'] == 'SYS-001')
        self.assertEqual(' '.join(row['title'].split()), 'Set running state')

    def test_four_space_unordered_list_continuation_is_prose(self):
        self.assert_reference_visible('- The system MUST follow\n    [[REF-001]].')

    def test_tab_indented_list_continuation_is_prose(self):
        self.assert_reference_visible('- The system MUST follow\n\t[[REF-001]].')

    def test_ordered_list_content_alignment_is_prose(self):
        self.assert_reference_visible('10. The system MUST follow\n    [[REF-001]].')

    def test_four_space_nested_list_is_not_code(self):
        self.assert_reference_visible('- Outer condition:\n    - The system MUST follow [[REF-001]].')

    def test_indented_code_inside_list_stays_informative(self):
        self.write('behavior.md', clause(body='- The system MUST count.\n\n      [[UNASSIGNED]]\n'))
        self.assertEqual(self.cli('check')['errors'], [])
        row = next(row for row in self.cli('export') if row['id'] == 'SYS-001')
        self.assertEqual(row['refs'], [])

    def test_indented_line_cannot_interrupt_ordinary_paragraph(self):
        self.assert_reference_visible('The system MUST follow\n    [[REF-001]] on every tick.')

    def test_ordinary_link_destination_is_not_a_wiki_reference(self):
        self.write('behavior.md', clause(body='The system MUST retain [the example](<https://example.invalid/[[UNASSIGNED]]>).'))
        self.assertEqual(self.cli('check')['errors'], [])
        row = next(row for row in self.cli('export') if row['id'] == 'SYS-001')
        self.assertEqual(row['refs'], [])

    def test_code_in_ordinary_link_label_cannot_open_html_comment(self):
        self.write('behavior.md', clause(body='The system MUST retain [`<!--`](https://example.invalid/) literally.') + clause('SYS-002'))
        self.assertEqual(self.own_ids(), ['SYS-001', 'SYS-002'])

    def test_comment_closing_line_exposes_same_line_reference(self):
        self.assert_reference_visible('<!-- editor\nnotes --> The system MUST follow [[REF-001]].')

    def test_comment_like_text_in_code_span_is_not_comment(self):
        self.assert_reference_visible('The system MUST show `<!-- [[UNASSIGNED]] -->` and follow [[REF-001]].')


    def test_commonmark_token_maps_preserve_clause_line_and_raw_body(self):
        body = 'The system MUST retain `x`.\n\n~~~python\nx = "[[UNASSIGNED]]"\n~~~'
        self.write('behavior.md', '<!-- introduction -->\n\n' + clause(body=body))
        row = next(row for row in self.cli('export') if row['id'] == 'SYS-001')
        self.assertEqual(row['line'], 3)
        self.assertEqual(row['body'].strip(), body)
        self.assertEqual(row['refs'], [])

    def test_nested_container_heading_examples_do_not_create_clauses(self):
        body = ('The system MUST count.\n\n'
                '> ## Quoted example {#SYS-QUOTED}\n'
                '> <!-- ndf: kind=info level=must layer=L1 -->\n\n'
                '- Example list:\n'
                '  ## Nested example {#SYS-NESTED}\n'
                '  <!-- ndf: kind=info level=must layer=L1 -->')
        self.write('behavior.md', clause(body=body) + '\n' + clause('SYS-002'))
        self.assertEqual(self.own_ids(), ['SYS-001', 'SYS-002'])

    def test_metadata_backticks_are_values_not_code_spans(self):
        self.write('behavior.md', clause(body='<!-- ndf: origin="Specification `tick` version" -->\nThe system MUST count.'))
        row = next(row for row in self.cli('export') if row['id'] == 'SYS-001')
        self.assertEqual(row['meta']['origin'], 'Specification `tick` version')
        self.assertEqual(row['meta']['kind'], 'req')

    def test_successive_metadata_comments_stay_separate(self):
        self.write('behavior.md', clause(body='<!-- ndf: since=0.2 -->\n<!-- ndf: origin="A standard" -->\nThe system MUST count.'))
        row = next(row for row in self.cli('export') if row['id'] == 'SYS-001')
        self.assertEqual(row['meta']['since'], '0.2')
        self.assertEqual(row['meta']['origin'], 'A standard')
        self.assertNotIn('ndf:', row['body'])

    def test_pre_clause_metadata_does_not_attach_to_next_clause(self):
        self.write('behavior.md', '<!-- ndf: kind=info level=may layer=L0 -->\n\n' + clause())
        self.assertEqual(self.own_ids(), ['SYS-001'])
        row = next(row for row in self.cli('export') if row['id'] == 'SYS-001')
        self.assertEqual(row['meta']['kind'], 'req')

    def test_heading_emphasis_and_inline_code_preserve_meaningful_title(self):
        self.write('behavior.md', clause(title='**Set** `running` state <!-- editorial -->'))
        row = next(row for row in self.cli('export') if row['id'] == 'SYS-001')
        self.assertEqual(row['title'], '**Set** `running` state')

    def test_standard_link_label_is_visible_without_destination_reference(self):
        self.write('behavior.md', clause(title='[Count](https://example.invalid/)', body='The system MUST [count](https://example.invalid/[[UNASSIGNED]]).'))
        row = next(row for row in self.cli('export') if row['id'] == 'SYS-001')
        self.assertIn('Count', row['title'])
        self.assertEqual(row['refs'], [])

    def test_long_fence_closes_before_next_real_clause(self):
        body = 'The system MUST count.\n\n````markdown\n## Example {#SYS-FAKE}\n```python\npass\n```\n`````'
        self.write('behavior.md', clause(body=body) + '\n' + clause('SYS-002'))
        self.assertEqual(self.own_ids(), ['SYS-001', 'SYS-002'])



if __name__ == '__main__':
    unittest.main()
