"""Third-pass source/token-boundary quality checks using only CLI contracts."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'ndf.py'
CONFIG = {'id-prefixes': ['SYS', 'REF', 'Q'], 'layers': ['L0', 'L1', 'L2', 'L3']}


def clause(cid='SYS-001', body='The system MUST count.', title='Requirement', meta='kind=req level=must layer=L1'):
    return f'## {title} {{#{cid}}}\n<!-- ndf: {meta} -->\n\n{body}\n'


class MarkdownQuality(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-quality-markdown-')
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

    def own_rows(self):
        return [row for row in self.cli('export') if row['path'] == 'behavior.md']

    def test_image_alt_reference_participates_in_dependency_surface(self):
        self.write('behavior.md', clause(body='The system MUST follow ![diagram for [[REF-001]]](diagram.svg).'))
        self.assertEqual([(row['id'], row['target']) for row in self.cli('deps')], [('SYS-001', 'REF-001')])
        self.assertEqual(self.own_rows()[0]['refs'], ['REF-001'])

    def test_image_alt_dangling_reference_is_validated(self):
        self.write('behavior.md', clause(body='The system MUST follow ![diagram for [[REF-MISSING]]](diagram.svg).'))
        report = self.cli('check', status=1)
        self.assertTrue(any('dangling reference REF-MISSING' in error for error in report['errors']))

    def test_image_alt_inline_code_keyword_is_not_obligation(self):
        self.write('behavior.md', clause(body='![The syntax word `MUST`](diagram.svg) illustrates a keyword.'))
        self.assertTrue(any('no normative keyword' in warning for warning in self.cli('check')['warnings']))

    def test_image_destination_and_alt_code_do_not_create_references(self):
        self.write('behavior.md', clause(body='The system MUST show ![example `[[REF-MISSING]]`](https://example.invalid/[[REF-OTHER]]).'))
        self.assertEqual(self.cli('check')['errors'], [])
        self.assertEqual(self.own_rows()[0]['refs'], [])

    def test_formatted_and_standard_link_label_references_remain_visible(self):
        self.write('behavior.md', clause(body='The system MUST follow **[[REF-001]]** and [see [[REF-001]]](https://example.invalid/).'))
        self.assertEqual(self.cli('check')['errors'], [])
        self.assertEqual(self.own_rows()[0]['refs'], ['REF-001', 'REF-001'])

    def test_non_linebreak_control_and_unicode_separators_preserve_source_body(self):
        for character in ('\v', '\f', '\x85', '\u2028', '\u2029'):
            with self.subTest(character=ascii(character)):
                body = 'The system MUST preserve ' + character + ' as document content.'
                self.write('behavior.md', clause(body=body))
                self.assertEqual(self.own_rows()[0]['body'].strip('\r\n'), body)

    def test_non_linebreak_control_does_not_shift_later_clause_maps(self):
        self.write('behavior.md', clause(body='The system MUST preserve \v here.') + '\n' + clause('SYS-002'))
        rows = self.own_rows()
        self.assertEqual([row['id'] for row in rows], ['SYS-001', 'SYS-002'])
        self.assertEqual(rows[1]['line'], 6)
        self.assertEqual(rows[1]['body'].strip(), 'The system MUST count.')

    def test_utf8_bom_before_first_heading_does_not_hide_clause(self):
        self.write('behavior.md', '\ufeff' + clause())
        rows = self.own_rows()
        self.assertEqual([row['id'] for row in rows], ['SYS-001'])
        self.assertEqual(rows[0]['line'], 1)

    def test_nul_body_content_survives_export_without_crash(self):
        self.write('behavior.md', clause(body='The system MUST preserve \x00 in its source example.'))
        self.assertIn('\x00', self.own_rows()[0]['body'])

    def test_entity_escaped_anchor_text_does_not_create_real_clause(self):
        self.write('behavior.md', '## Literal &#123;#SYS-FAKE&#125;\n\nAn explanatory heading.\n\n' + clause())
        self.assertEqual([row['id'] for row in self.own_rows()], ['SYS-001'])

    def test_backslash_escaped_anchor_text_does_not_create_real_clause(self):
        self.write('behavior.md', '## Literal \\{#SYS-FAKE\\}\n\nAn explanatory heading.\n\n' + clause())
        self.assertEqual([row['id'] for row in self.own_rows()], ['SYS-001'])

    def test_entity_escaped_wiki_delimiters_remain_literal_text(self):
        self.write('behavior.md', clause(body='The system MUST display &#91;&#91;REF-MISSING&#93;&#93; literally.'))
        self.assertEqual(self.cli('check')['errors'], [])
        self.assertEqual(self.own_rows()[0]['refs'], [])

    def test_resolution_example_in_fence_does_not_override_actual_resolution(self):
        body = '```markdown\n**Resolution.** Example only.\n```\n\n**Resolution.** Recorded choice.'
        self.write('behavior.md', clause('Q-001', body=body, title='Question', meta='kind=question status=resolved'))
        self.assertEqual(self.cli('status')['questions'][0]['resolution'], 'Recorded choice.')

    def test_resolution_comment_does_not_override_actual_resolution(self):
        body = '<!--\n**Resolution.** Example only.\n-->\n\n**Resolution.** Recorded choice.'
        self.write('behavior.md', clause('Q-001', body=body, title='Question', meta='kind=question status=resolved'))
        self.assertEqual(self.cli('status')['questions'][0]['resolution'], 'Recorded choice.')

    def test_resolution_only_inside_fence_is_still_missing(self):
        body = '```markdown\n**Resolution.** Example only.\n```'
        self.write('behavior.md', clause('Q-001', body=body, title='Question', meta='kind=question status=resolved'))
        self.assertIsNone(self.cli('status')['questions'][0]['resolution'])
        self.assertTrue(any('closed question has no resolution' in warning for warning in self.cli('check')['warnings']))

    def test_explicit_resolution_metadata_overrides_prose_examples(self):
        body = '```markdown\n**Resolution.** Example only.\n```'
        self.write('behavior.md', clause('Q-001', body=body, title='Question', meta='kind=question status=resolved resolution="Chosen value"'))
        self.assertEqual(self.cli('status')['questions'][0]['resolution'], 'Chosen value')

    def test_quoted_directive_looking_origin_remains_a_string(self):
        # The metadata reader must not evaluate command-looking but valid text.
        self.write('behavior.md', clause(body='<!-- ndf: origin="$(printf surprise) `text` [section]" -->\nThe system MUST count.'))
        self.assertEqual(self.own_rows()[0]['meta']['origin'], '$(printf surprise) `text` [section]')


    def test_bom_inside_body_is_content_not_an_encoding_prefix(self):
        body = 'The system MUST retain \ufeff inside its source example.'
        self.write('behavior.md', clause(body=body))
        self.assertEqual(self.own_rows()[0]['body'].strip('\r\n'), body)

    def test_crlf_and_lone_cr_physical_lines_keep_clause_maps(self):
        for ending in ('\r\n', '\r'):
            with self.subTest(ending=ascii(ending)):
                text = clause() + '\n' + clause('SYS-002')
                (self.root / 'behavior.md').write_bytes(text.replace('\n', ending).encode('utf-8'))
                rows = self.own_rows()
                self.assertEqual([(row['id'], row['line']) for row in rows], [('SYS-001', 1), ('SYS-002', 6)])

    def test_anchor_before_trailing_comment_and_closing_hashes_is_real(self):
        self.write('behavior.md', '## Requirement {#SYS-001} <!-- editorial --> ###\n<!-- ndf: kind=req level=must layer=L1 -->\n\nThe system MUST count.\n')
        rows = self.own_rows()
        self.assertEqual([row['id'] for row in rows], ['SYS-001'])
        self.assertEqual(rows[0]['title'], 'Requirement')

    def test_inline_code_anchor_example_stays_informative(self):
        self.write('behavior.md', '## Example `{#SYS-FAKE}`\n\nOnly a syntax example.\n\n' + clause())
        self.assertEqual([row['id'] for row in self.own_rows()], ['SYS-001'])

    def test_resolution_in_quote_or_list_is_not_top_level_field(self):
        for example in ('> **Resolution.** Quoted choice.', '- **Resolution.** Listed choice.'):
            with self.subTest(example=example):
                body = example + '\n\n**Resolution.** Recorded choice.'
                self.write('behavior.md', clause('Q-001', body=body, title='Question', meta='kind=question status=resolved'))
                self.assertEqual(self.cli('status')['questions'][0]['resolution'], 'Recorded choice.')

    def test_resolution_in_image_alt_is_not_top_level_field(self):
        body = '![**Resolution.** Example only.](diagram.svg)\n\n**Resolution.** Recorded choice.'
        self.write('behavior.md', clause('Q-001', body=body, title='Question', meta='kind=question status=resolved'))
        self.assertEqual(self.cli('status')['questions'][0]['resolution'], 'Recorded choice.')

    def test_resolution_with_inline_code_value_is_not_lost(self):
        body = '**Resolution.** `10ms`'
        self.write('behavior.md', clause('Q-001', body=body, title='Question', meta='kind=question status=resolved'))
        self.assertIn(self.cli('status')['questions'][0]['resolution'], ('10ms', '`10ms`'))

    def test_resolution_with_emphasized_value_retains_text(self):
        body = '**Resolution.** **10ms**'
        self.write('behavior.md', clause('Q-001', body=body, title='Question', meta='kind=question status=resolved'))
        self.assertEqual(self.cli('status')['questions'][0]['resolution'], '10ms')



if __name__ == '__main__':
    unittest.main()
