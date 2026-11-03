"""Independent CLI quality checks after the interaction audit.

These tests exercise reports through actual command-line processes and author
expected identities/body contents directly. They never import NDF internals or
mutate the pinned source fixture.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'ndf.py'
CONFIG = {'id-prefixes': ['SYS', 'VER', 'Q'], 'layers': ['L0', 'L1', 'L2', 'L3']}


def clause(cid='SYS-001', body='The system MUST count.', kind='req', layer='L1', extra=''):
    fields = f'kind={kind}'
    if kind not in ('question', 'decision'):
        fields += f' level=must layer={layer}'
    return f'## Requirement {{#{cid}}}\n<!-- ndf: {fields} {extra} -->\n\n{body}\n\n'


class QualityCli(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-quality-cli-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.spec = self.base / 'spec'
        self.spec.mkdir()
        (self.spec / 'ndf.yaml').write_text(json.dumps(CONFIG), encoding='utf-8')
        self.write('requirements.md', clause())

    def write(self, path, content):
        file = self.spec / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding='utf-8')

    def cli(self, *args, root=None):
        return subprocess.run([sys.executable, str(CLI), '--root', str(root or self.spec), '--json', *args], cwd=self.base, capture_output=True, text=True, timeout=20)

    def data(self, *args, code=0):
        result = self.cli(*args)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return json.loads(result.stdout)

    def test_non_line_ending_separators_preserve_raw_body_and_clause_boundaries(self):
        # CommonMark source maps count LF/CR/CRLF, unlike Python splitlines(),
        # which also splits these ordinary inline source characters.
        for separator in ('\u2028', '\u2029', '\x85', '\x0b', '\x0c', '\x1c', '\x1d', '\x1e'):
            with self.subTest(separator=repr(separator)):
                first = 'The system MUST preserve x' + separator + 'y.'
                second = 'The second system MUST count.'
                self.write('requirements.md', clause(body=first) + clause('SYS-002', body=second))
                rows = self.data('export')
                self.assertEqual([row['id'] for row in rows], ['SYS-001', 'SYS-002'])
                self.assertEqual(rows[0]['body'], first)
                self.assertEqual(rows[1]['body'], second)
                self.assertEqual(rows[1]['line'], 6)

    def test_real_line_ending_spellings_have_equivalent_exports(self):
        source = clause(body='The system MUST count.\nA second source line is retained.') + clause('SYS-002')
        expected = None
        for separator in ('\n', '\r\n', '\r'):
            with self.subTest(separator=repr(separator)):
                (self.spec / 'requirements.md').write_bytes(source.replace('\n', separator).encode('utf-8'))
                rows = self.data('export')
                if expected is None:
                    expected = rows
                self.assertEqual(rows, expected)

    def test_resolution_samples_cannot_override_the_actual_resolution(self):
        for sample in ('```markdown\n**Resolution.** Fake example.\n```', '<!--\n**Resolution.** Fake example.\n-->'):
            with self.subTest(sample=sample):
                self.write('requirements.md', clause('Q-001', kind='question', extra='status=resolved', body=sample + '\n\n**Resolution.** Actual decision.'))
                data = self.data('status')
                self.assertEqual(data['questions'][0]['resolution'], 'Actual decision.')

    def test_resolution_sample_alone_does_not_hide_a_missing_resolution(self):
        self.write('requirements.md', clause('Q-001', kind='question', extra='status=resolved', body='```markdown\n**Resolution.** Fake example.\n```'))
        self.assertIsNone(self.data('status')['questions'][0]['resolution'])
        self.assertTrue(any('closed question has no resolution' in warning for warning in self.data('check')['warnings']))

    def test_quoted_and_list_resolution_examples_are_not_top_level_fields(self):
        for sample in ('> **Resolution.** Quoted example.', '- **Resolution.** Listed example.', '    **Resolution.** Code example.'):
            with self.subTest(sample=sample):
                self.write('requirements.md', clause('Q-001', kind='question', extra='status=resolved', body=sample))
                self.assertIsNone(self.data('status')['questions'][0]['resolution'])

    def test_explicit_resolution_metadata_has_priority_over_prose(self):
        self.write('requirements.md', clause('Q-001', kind='question', extra='status=resolved resolution="Metadata choice."', body='**Resolution.** Prose alternative.'))
        self.assertEqual(self.data('status')['questions'][0]['resolution'], 'Metadata choice.')

    def test_duplicate_verification_targets_do_not_duplicate_acceptance_criteria(self):
        self.write('requirements.md', clause() + clause('VER-001', kind='verif', layer='L3', extra='verifies=SYS-001'))
        expected = self.data('coverage')
        self.write('requirements.md', clause() + clause('VER-001', kind='verif', layer='L3', extra='verifies=SYS-001,SYS-001'))
        self.assertEqual(self.data('coverage'), expected)
        root = self.data('trace', 'SYS-001')[0]
        self.assertEqual(root['verified_by'], ['VER-001'])

    def test_verification_identity_is_independent_of_file_ownership(self):
        self.write('requirements.md', clause())
        self.write('checks/a.md', clause('VER-002', kind='verif', layer='L3', extra='verifies=SYS-001'))
        self.write('checks/z.md', clause('VER-001', kind='verif', layer='L3', extra='verifies=SYS-001'))
        before = self.data('coverage')
        (self.spec / 'checks/a.md').rename(self.spec / 'checks/zz.md')
        after = self.data('coverage')
        self.assertEqual(before['linked'], after['linked'])
        self.assertEqual(set(before['verification_links']['SYS-001']), set(after['verification_links']['SYS-001']))
        self.assertEqual(before, after)

    def test_duplicate_edge_whitespace_and_order_preserve_the_worklist(self):
        self.write('requirements.md', clause() + clause('VER-002', kind='verif', layer='L3', extra='verifies=SYS-001') + clause('VER-001', kind='verif', layer='L3', extra='verifies=SYS-001'))
        expected = self.data('coverage')
        self.assertEqual(expected['verification_links']['SYS-001'], ['VER-001', 'VER-002'])
        self.write('requirements.md', clause() + clause('VER-001', kind='verif', layer='L3', extra='verifies=" SYS-001 , SYS-001 "') + clause('VER-002', kind='verif', layer='L3', extra='verifies=SYS-001,SYS-001'))
        self.assertEqual(self.data('coverage'), expected)

    def test_resolution_image_alt_text_does_not_override_a_real_field(self):
        self.write('requirements.md', clause('Q-001', kind='question', extra='status=resolved', body='![Resolution. Fake example.](image.png)\n\n**Resolution.** Actual decision.'))
        self.assertEqual(self.data('status')['questions'][0]['resolution'], 'Actual decision.')

    def test_concurrent_init_preserves_one_complete_manifest(self):
        fresh = self.base / 'concurrent-init'
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.cli('init', root=fresh), range(2)))
        self.assertEqual(sorted(result.returncode for result in results), [0, 2])
        for result in results:
            self.assertNotIn('Traceback', result.stderr)
        manifest = json.loads((fresh / 'ndf.yaml').read_text(encoding='utf-8'))
        self.assertEqual(manifest['id-prefixes'], ['SYS', 'VER', 'D', 'Q'])
        self.assertEqual(self.cli('check', root=fresh).returncode, 0)

    def test_init_does_not_follow_an_existing_broken_manifest_symlink(self):
        fresh = self.base / 'fresh'
        fresh.mkdir()
        outside = self.base / 'outside-manifest.yaml'
        manifest = fresh / 'ndf.yaml'
        manifest.symlink_to(outside)
        result = self.cli('init', root=fresh)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertTrue(manifest.is_symlink())
        self.assertFalse(outside.exists(), 'init must not create a manifest outside the selected root through an existing entry')

    def test_init_failure_preserves_a_conflicting_existing_file(self):
        fresh = self.base / 'fresh'
        fresh.mkdir()
        conflicting = fresh / '30-interfaces'
        conflicting.write_text('existing user file', encoding='utf-8')
        result = self.cli('init', root=fresh)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(conflicting.read_text(encoding='utf-8'), 'existing user file')
        self.assertFalse((fresh / 'ndf.yaml').exists())

    def test_init_failure_does_not_replace_existing_nonempty_manifest(self):
        before = (self.spec / 'ndf.yaml').read_bytes()
        result = self.cli('init')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual((self.spec / 'ndf.yaml').read_bytes(), before)

    def test_unicode_area_identifiers_remain_valid_end_to_end(self):
        issued = self.data('new-id', 'SYS-µ')['id']
        self.assertTrue(re.fullmatch('SYS-µ-[0-9a-f]{32}', issued))
        self.write('requirements.md', clause(issued))
        self.assertEqual(self.data('check')['errors'], [])
        self.assertEqual(self.data('trace', issued)[0]['id'], issued)

    def test_display_labels_do_not_change_dependency_identity(self):
        self.write('refs/time.md', clause('SYS-TIME'))
        outputs = []
        for mention in ('[[SYS-TIME]]', '[[SYS-TIME | Time definition]]', '[[refs/time.md#SYS-TIME | Same definition]]'):
            self.write('requirements.md', clause(body='The system MUST follow ' + mention + '.'))
            outputs.append(self.data('deps'))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])


if __name__ == '__main__':
    unittest.main()
