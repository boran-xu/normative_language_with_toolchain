"""Deterministic generated command matrices with independent graph oracles."""
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'ndf.py'


class GeneratedInvariants(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ndf-generated-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def cli(self, *args):
        result = subprocess.run([sys.executable, str(CLI), '--root', str(self.root), '--json', *args], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_deep_valid_custom_refinement_ladder_is_iterative(self):
        count = 1100
        (self.root / 'ndf.yaml').write_text(json.dumps({'id-prefixes': ['SYS'], 'layers': [f'L{i}' for i in range(count)]}))
        # Reverse file order forces validation to traverse the entire chain.
        (self.root / 'clauses.md').write_text('\n'.join(f'## Depth {i} {{#SYS-{i}}}\n<!-- ndf: kind=arch level=must layer=L{i}' + (f' refines=SYS-{i-1}' if i else '') + ' -->\nThe system MUST retain its state.' for i in reversed(range(count))))
        self.assertEqual(self.cli('check')['clauses'], count)
        rows = self.cli('trace', 'SYS-0')
        self.assertEqual(len(rows), count)
        self.assertEqual(max(row['depth'] for row in rows), count - 1)

    def test_seeded_mixed_graphs_match_independent_reachability_oracle(self):
        (self.root / 'ndf.yaml').write_text(json.dumps({'id-prefixes': ['SYS'], 'layers': ['L0', 'L1', 'L2', 'L3']}))
        for seed in range(8):
            with self.subTest(seed=seed):
                randomizer = random.Random(seed)
                count = 32
                children = {i: [] for i in range(count)}
                dependencies = {i: [] for i in range(count)}
                clauses = []
                for i in range(count):
                    layer = i % 4
                    parents = [j for j in range(i) if j % 4 < layer]
                    parent = randomizer.choice(parents) if parents and randomizer.random() < .8 else None
                    if parent is not None:
                        children[parent].append(i)
                    dependencies[i] = randomizer.sample(range(count), randomizer.randrange(4))
                    fields = f'kind=arch level=must layer=L{layer}'
                    if parent is not None:
                        fields += f' refines=SYS-{parent}'
                    if dependencies[i]:
                        fields += ' depends-on=' + ','.join(f'SYS-{j}' for j in dependencies[i])
                    clauses.append(f'## State {i} {{#SYS-{i}}}\n<!-- ndf: {fields} -->\nThe system MUST retain its state.\n')
                # Deliberately permute source order; identities must survive.
                randomizer.shuffle(clauses)
                (self.root / 'graph.md').write_text(''.join(clauses))
                self.assertEqual(self.cli('check')['clauses'], count)
                for start in (0, 7, 31):
                    reached, queue = set(), [start]
                    while queue:
                        node = queue.pop(0)
                        if node in reached:
                            continue
                        reached.add(node)
                        queue.extend(children[node] + dependencies[node])
                    rows = self.cli('trace', f'SYS-{start}')
                    self.assertEqual({r['id'] for r in rows}, {f'SYS-{i}' for i in reached})
                    self.assertEqual(sum(not row['repeated'] for row in rows), len(reached))
                exported = self.cli('export')
                self.assertEqual(len({c['id'] for c in exported}), count)
                self.assertEqual(self.cli('coverage')['L1_must'], count // 4)

    def test_default_root_module_entrypoint_and_help_matrix(self):
        env = dict(os.environ, PYTHONPATH=str(CLI.parent))
        direct, module = [sys.executable, str(CLI)], [sys.executable, '-m', 'ndf']
        initialized = subprocess.run(direct + ['--json', 'init'], cwd=self.root, capture_output=True, text=True, env=env)
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.assertTrue((self.root / 'spec/ndf.yaml').is_file())
        for command in ('check', 'coverage', 'status', 'options', 'deps', 'export'):
            with self.subTest(command=command):
                outputs = []
                for entrypoint in (direct, module):
                    result = subprocess.run(entrypoint + ['--json', command], cwd=self.root, capture_output=True, text=True, env=env)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    outputs.append(json.loads(result.stdout))
                self.assertEqual(outputs[0], outputs[1])
        for entrypoint in (direct, module):
            result = subprocess.run(entrypoint + ['--help'], cwd=self.root, capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('trace', result.stdout)
            self.assertIn('new-id', result.stdout)

    def test_code_at_start_of_clause_stays_an_example(self):
        (self.root / 'ndf.yaml').write_text(json.dumps({'id-prefixes': ['SYS']}))
        (self.root / 'body.md').write_text('## Example {#SYS-001}\n<!-- ndf: kind=req level=must layer=L1 -->\n\n    MUST [[NOT-REAL]]\n')
        data = self.cli('check')
        self.assertEqual(data['errors'], [])
        self.assertTrue(any('no normative keyword' in warning for warning in data['warnings']))
        self.assertEqual(self.cli('export')[0]['refs'], [])


if __name__ == '__main__':
    unittest.main()
