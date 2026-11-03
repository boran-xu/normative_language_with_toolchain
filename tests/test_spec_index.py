"""Shared-index contracts: identity, resolution, graph consistency and scaling."""
from pathlib import Path
import tempfile
import unittest

from ndf.core import Clause
from ndf.index import SpecIndex
from ndf import reports


def clause(cid, path, **meta):
    return Clause(cid, 'Term', path, 1, {'kind': 'req', 'level': 'must', 'layer': 'L1', **meta})


class SpecIndexTests(unittest.TestCase):
    def test_identity_and_equivalent_paths_share_one_resolution(self):
        index = SpecIndex([clause('SYS-001', 'refs/time.md'), clause('SYS-002', 'refs/time.md')])
        for ref in ('SYS-001', 'refs/time.md#SYS-001', './refs//time.md#SYS-001'):
            self.assertEqual(index.resolve(ref), ('SYS-001',))
        self.assertEqual(index.resolve('refs/time'), ('SYS-001', 'SYS-002'))
        self.assertEqual(index.resolve('../refs/time.md#SYS-001'), ())
        self.assertEqual(index.resolve('/refs/time.md#SYS-001'), ())
        self.assertEqual(index.resolve('refs/time.md#MISSING'), ())

    def test_file_inventory_supports_empty_and_informative_files(self):
        index = SpecIndex([], files=('refs/empty.md',))
        self.assertTrue(index.valid('refs/empty.md'))
        self.assertEqual(index.resolve('refs/empty.md'), ())
        self.assertFalse(index.valid('refs/missing.md'))
        self.assertFalse(index.valid('refs/empty.md#MISSING'))
        self.assertIsInstance(index.files, frozenset)

    def test_graph_reports_share_canonical_identity_and_unique_backlinks(self):
        source = clause('SYS-001', 'behavior.md')
        source.refs = ['REF-001', './refs/time.md#REF-001', 'REF-001 | incorrect target']
        target = clause('REF-001', 'refs/time.md', origin='A source')
        criterion = clause('VER-001', 'acceptance.md', kind='verif', layer='L3', verifies='SYS-001,SYS-001')
        index = SpecIndex([source, target, criterion])
        self.assertEqual(index.incoming('verifies', 'SYS-001'), ('VER-001',))
        self.assertIn(('mention', 'REF-001'), index.edges('SYS-001'))
        self.assertNotIn(('mention', 'REF-001 | incorrect target'), index.edges('SYS-001', fallback=False))
        self.assertEqual(reports.coverage(index, {})['verification_links']['SYS-001'], ['VER-001'])
        self.assertEqual(reports.dependencies(index), [{'id': 'SYS-001', 'target': 'REF-001', 'type': 'mention', 'origin': 'A source'}])

    def test_root_resolution_preserves_non_markdown_asset_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'images').mkdir()
            (root / 'images/diagram.svg').write_text('<svg/>')
            index = SpecIndex([], root=root)
            self.assertTrue(index.valid('images/diagram.svg'))
            self.assertFalse(index.valid('../diagram.svg'))

    def test_repeated_lookups_do_not_rescan_clause_paths(self):
        reads = [0]
        class Counted:
            def __init__(self, number):
                self.id = f'SYS-{number}'
                self.number = number
                self.refs = []
            @property
            def path(self):
                reads[0] += 1
                return f'subsystem/{self.number}.md'
            def edges(self):
                return iter(())
        count = 500
        index = SpecIndex(Counted(i) for i in range(count))
        for _ in range(3):
            for i in range(count):
                self.assertEqual(index.resolve(f'subsystem/{i}.md#SYS-{i}'), (f'SYS-{i}',))
        self.assertLessEqual(reads[0], count * 2,
                             'Indexed resolution must not scan every clause for every lookup')


if __name__ == '__main__':
    unittest.main()
