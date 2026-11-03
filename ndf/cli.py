import argparse
import json
from pathlib import Path
import re
import sys
import uuid
from .core import load, manifest, validate
from .index import SpecIndex
from . import reports
from .history import History, change, changelog
from .graph import trace as trace_graph, render_trace


def emit(value, as_json):
    if as_json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    elif isinstance(value, list):
        for row in value:
            print(row if isinstance(row, str) else json.dumps(row, ensure_ascii=False))
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description='NDF: clauses, links, coverage, and Git history')
    parser.add_argument('--root', type=Path, default=Path('spec'), help='spec root (default: spec)')
    parser.add_argument('--json', action='store_true', help='machine-readable output')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init', help='create a minimal spec tree')
    sub.add_parser('test', help='run unittest discovery in models/ (executes project Python code)')
    new = sub.add_parser('new-id', help='issue a branch-safe ID (UUID suffix)')
    new.add_argument('prefix')
    check = sub.add_parser('check', help='validate structure and flag clauses needing review')
    check.add_argument('--since', help='compare worktree to this Git commit for refinement review')
    for name in ('coverage', 'status', 'options', 'export'):
        sub.add_parser(name)
    deps = sub.add_parser('deps')
    deps.add_argument('path', nargs='?', default='refs/')
    trace = sub.add_parser('trace')
    trace.add_argument('id')
    log = sub.add_parser('log', help='per-parent history across moves and merges')
    log.add_argument('id')
    log.add_argument('--ref', default='HEAD')
    log.add_argument('--all', action='store_true', help='include all local refs')
    diff = sub.add_parser('diff')
    diff.add_argument('range', help='A..B (commit hashes, branches, or tags)')
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        if args.command == 'init':
            if (root / 'ndf.yaml').exists() or (root / 'ndf.yaml').is_symlink():
                raise ValueError('ndf.yaml already exists; init never overwrites a spec')
            root.mkdir(parents=True, exist_ok=True)
            for name in ('00-charter', '10-architecture', '20-behavior', '30-interfaces', '40-constraints', '50-verification', 'models', 'refs', 'decisions', 'open'):
                (root / name).mkdir(exist_ok=True)
            with (root / 'ndf.yaml').open('x', encoding='utf-8') as stream:
                json.dump({'project': root.name, 'id-prefixes': ['SYS', 'VER', 'D', 'Q'], 'layers': {'L0': 'intent', 'L1': 'contract', 'L2': 'mechanism', 'L3': 'executable'}}, stream, indent=2)
                stream.write('\n')
            emit({'created': str(root)}, args.json)
            return 0
        historical = args.command in ('log', 'diff')
        config = {} if historical else manifest(root)
        clauses = [] if historical or args.command == 'new-id' else load(root)
        if args.command == 'new-id':
            if not any(args.prefix == p or args.prefix.startswith(p + '-') for p in config['id-prefixes']):
                raise ValueError('prefix is not declared in ndf.yaml')
            if not re.fullmatch(r'[A-Za-z][\w.-]*', args.prefix):
                raise ValueError('invalid ID prefix')
            # No counter, lock, shared service, or branch-local allocation state.
            cid = args.prefix + '-' + uuid.uuid4().hex
            emit({'id': cid} if args.json else [cid], args.json)
            return 0
        # Historical queries remain usable even with a broken worktree.
        index = SpecIndex(clauses, root=root)
        errors, warnings = ([], []) if historical else validate(clauses, root, config, spec=index)
        if args.command == 'check':
            if args.since:
                before = History(root).snapshot(args.since)
                current = index.by_id
                changed = {cid for cid in set(before) | set(current) if change(before.get(cid), current.get(cid))}
                pairs = set()
                # Include removed edges as well as current edges.
                for c in list(before.values()) + clauses:
                    for key, parent in c.edges():
                        if key == 'refines' and (c.id in changed or parent in changed):
                            pairs.add((c.id, parent))
                warnings.extend(f'review refinement {child} -> {parent}: related clause changed; semantic consistency not verified' for child, parent in sorted(pairs))
            emit({'errors': errors, 'warnings': warnings, 'clauses': len(clauses)}, args.json)
            return 1 if errors else 0
        if errors:
            emit({'errors': errors}, args.json)
            return 1
        if args.command == 'test':
            import subprocess
            models = root / 'models'
            if not models.is_dir() or not list(models.rglob('test*.py')):
                raise ValueError('no model tests found under models/')
            return subprocess.run([sys.executable, str(Path(__file__).with_name('model_runner.py')), str(models)], cwd=root).returncode
        elif args.command == 'export':
            from dataclasses import asdict
            emit([asdict(c) for c in clauses], True)
        elif args.command in ('coverage', 'status'):
            emit(reports.coverage(index, config, include_questions=args.command == 'status'), args.json)
        elif args.command == 'options':
            emit(reports.options(index), args.json)
        elif args.command == 'deps':
            emit(reports.dependencies(index, args.path), args.json)
        elif args.command == 'trace':
            rows = trace_graph(index, args.id)
            emit(rows if args.json else render_trace(rows), args.json)
        elif args.command == 'log':
            emit(History(root).events(args.id, args.ref, args.all), args.json)
        elif args.command == 'diff':
            if args.range.count('..') != 1 or '...' in args.range:
                raise ValueError('expected A..B')
            a, b = args.range.split('..')
            history = History(root)
            before, after = history.snapshot(a), history.snapshot(b)
            emit(changelog(before, after), args.json)
        return 0
    except (ValueError, OSError, UnicodeError, RuntimeError) as exc:
        print(f'ndf: {exc}', file=sys.stderr)
        return 2
