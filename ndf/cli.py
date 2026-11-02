import argparse
import json
from pathlib import Path
import re
import sys
import uuid
from .core import load, manifest, validate
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
    root = args.root.resolve()
    try:
        if args.command == 'init':
            if (root / 'ndf.yaml').exists():
                raise ValueError('ndf.yaml already exists; init never overwrites a spec')
            root.mkdir(parents=True, exist_ok=True)
            for name in ('00-charter', '10-architecture', '20-behavior', '30-interfaces', '40-constraints', '50-verification', 'models', 'refs', 'decisions', 'open'):
                (root / name).mkdir(exist_ok=True)
            (root / 'ndf.yaml').write_text(json.dumps({'project': root.name, 'id-prefixes': ['SYS', 'VER', 'D', 'Q'], 'layers': {'L0': 'intent', 'L1': 'contract', 'L2': 'mechanism', 'L3': 'executable'}}, indent=2) + '\n')
            emit({'created': str(root)}, args.json)
            return 0
        config = manifest(root)
        clauses = load(root)
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
        historical = args.command in ('log', 'diff')
        errors, warnings = ([], []) if historical else validate(clauses, root, config)
        if args.command == 'check':
            if args.since:
                before = History(root).snapshot(args.since)
                index = {c.id: c for c in clauses}
                changed = {cid for cid in set(before) | set(index) if change(before.get(cid), index.get(cid))}
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
        index = {c.id: c for c in clauses}
        if args.command == 'test':
            import subprocess
            models = root / 'models'
            if not models.is_dir() or not list(models.rglob('test*.py')):
                raise ValueError('no model tests found under models/')
            return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(models), '-v'], cwd=root).returncode
        elif args.command == 'export':
            from dataclasses import asdict
            emit([asdict(c) for c in clauses], True)
        elif args.command in ('coverage', 'status'):
            links = {}
            for c in clauses:
                if c.active() and c.meta.get('kind') == 'verif':
                    for key, target in c.edges():
                        if key == 'verifies':
                            links.setdefault(target, []).append(c.id)
            must = [c.id for c in clauses if c.active() and c.meta.get('layer') == 'L1' and c.meta.get('level') == 'must' and c.meta.get('kind') != 'info']
            questions = [c.id for c in clauses if c.meta.get('kind') == 'question' and c.meta.get('status', 'open') not in ('resolved', 'closed')]
            result = {'L1_must': len(must), 'linked': len([cid for cid in must if cid in links]),
                      'unverified': sorted(cid for cid in must if cid not in links),
                      'verification_links': links, 'open_questions': questions,
                      'TBD': [c.id for c in clauses if c.active() and (c.meta.get('level') == 'tbd' and c.meta.get('kind') != 'option' or '⟨TBD:' in c.body)],
                      'open_options': [c.id for c in clauses if c.active() and c.meta.get('kind') == 'option' and c.meta.get('level') == 'tbd'],
                      'inline_DSE': sum(c.body.count('⟨DSE:') for c in clauses),
                      'conflicts': [{'id': c.id, 'with': target} for c in clauses for key, target in c.edges() if key == 'conflicts-with'],
                      'note': 'Links measure specified coverage, not implemented or passing tests.'}
            if args.command == 'status':
                result['questions'] = [{'id': c.id, 'status': c.meta.get('status', 'open'), 'blocks': [t for k, t in c.edges() if k == 'blocks'], 'resolution': c.resolution(), 'body': c.body} for c in clauses if c.meta.get('kind') == 'question']
            emit(result, args.json)
        elif args.command == 'options':
            emit([{'id': c.id, **c.meta} for c in clauses if c.meta.get('kind') == 'option'], args.json)
        elif args.command == 'deps':
            external = {c.id for c in clauses if c.path.startswith(args.path)}
            emit([{'id': c.id, 'target': target, 'type': key, 'origin': index[target].meta.get('origin')} for c in clauses if c.id not in external for key, target in list(c.edges()) + [('mention', r.strip()) for r in c.refs] if target in external], args.json)
        elif args.command == 'trace':
            rows = trace_graph(clauses, args.id)
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
    except (ValueError, OSError, UnicodeError, RecursionError) as exc:
        print(f'ndf: {exc}', file=sys.stderr)
        return 2
