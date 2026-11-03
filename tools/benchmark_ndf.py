#!/usr/bin/env python3
"""Reproducible history workload; verifies events and counts actual Git processes."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run_git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def build(repo, commits, files):
    if repo.exists():
        raise ValueError('benchmark construction never overwrites an existing path')
    repo.mkdir(parents=True)
    run_git(repo, 'init', '-q', '-b', 'main')
    for key, value in [('user.name', 'NDF benchmark'), ('user.email', 'benchmark@example.invalid'), ('commit.gpgsign', 'false'), ('core.hooksPath', '/dev/null'), ('core.autocrlf', 'false')]:
        run_git(repo, 'config', key, value)
    spec = repo / 'spec'
    spec.mkdir()
    (spec / 'ndf.yaml').write_text(json.dumps({'id-prefixes': ['SYS']}))
    def write(index, value):
        (spec / f'contract-{index:04}.md').write_text(f'## Counter {{#SYS-{index:04}}}\n<!-- ndf: kind=req level=must layer=L1 -->\n\nThe system MUST count to {value}.\n')
    for index in range(files):
        write(index, 0)
    run_git(repo, 'add', '.')
    run_git(repo, 'commit', '-qm', 'Initial contracts')
    expected = [run_git(repo, 'rev-parse', 'HEAD')]
    for revision in range(commits):
        index = revision % files
        write(index, revision + 1)
        run_git(repo, 'add', '.')
        run_git(repo, 'commit', '-qm', f'Update contract {index} at revision {revision + 1}')
        if index == 0:
            expected.append(run_git(repo, 'rev-parse', 'HEAD'))
    (repo / 'expected.json').write_text(json.dumps({'events': expected, 'commits': commits + 1, 'files': files}))


@contextmanager
def count_git_processes():
    real = subprocess.Popen
    count = [0]
    def observed(*args, **kwargs):
        command = args[0] if args else kwargs.get('args', [])
        if command and Path(command[0]).name == 'git':
            count[0] += 1
        return real(*args, **kwargs)
    subprocess.Popen = observed
    try:
        yield count
    finally:
        subprocess.Popen = real


def measure(repo):
    from ndf.history import History
    expected = json.loads((repo / 'expected.json').read_text())
    with count_git_processes() as counter:
        started = time.perf_counter()
        history = History(repo / 'spec')
        events = history.events('SYS-0000')
        elapsed = time.perf_counter() - started
    assert {event['commit'] for event in events} == set(expected['events']), 'history output differs from the authored event oracle'
    return {'workload': {key: expected[key] for key in ('commits', 'files')}, 'seconds': elapsed,
            'git_processes': counter[0], 'events': len(events), 'correct': True}


def measure_references(count, method):
    from ndf.core import Clause
    from ndf.index import SpecIndex
    from ndf.paths import relative_path
    clauses = [Clause(f'SYS-{i}', 'Term', f'area/{i}.md', 1,
                      {'kind': 'req', 'level': 'must', 'layer': 'L1'}) for i in range(count)]
    def legacy_scan(target):
        # The pre-index implementation, retained only as an explicit benchmark
        # control. Production callers use the shared SpecIndex.
        if any(c.id == target for c in clauses):
            return [target]
        path, _, anchor = target.partition('#')
        path = relative_path(path)
        return sorted(c.id for c in clauses if c.path in (path, path + '.md')
                      and (not anchor or c.id == anchor))
    started = time.perf_counter()
    index = SpecIndex(clauses) if method == 'index' else None
    for i in range(count):
        ref = f'area/{i}.md#SYS-{i}'
        actual = index.resolve(ref) if index is not None else legacy_scan(ref)
        assert list(actual) == [f'SYS-{i}']
    return {'clauses': count, 'lookups': count, 'method': method,
            'seconds': time.perf_counter() - started, 'correct': True,
            'includes_index_construction': index is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, help='existing benchmark repo, or new path with --build')
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--commits', type=int, default=180)
    parser.add_argument('--files', type=int, default=160)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--references', action='store_true')
    parser.add_argument('--clauses', type=int, default=10000)
    parser.add_argument('--reference-method', choices=('scan', 'index'), default='index')
    args = parser.parse_args()
    if args.commits < 1 or args.files < 1 or args.clauses < 1:
        parser.error('workload sizes must be positive')
    if args.build and args.repo is not None and args.repo.exists():
        parser.error('--build requires a new repository path')
    if args.references:
        result = measure_references(args.clauses, args.reference_method)
    else:
        with tempfile.TemporaryDirectory(prefix='ndf-benchmark-') as temporary:
            repo = args.repo.resolve() if args.repo else Path(temporary) / 'repo'
            if args.build or args.repo is None:
                build(repo, args.commits, args.files)
            result = measure(repo)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + '\n')
    print(rendered)


if __name__ == '__main__':
    main()
