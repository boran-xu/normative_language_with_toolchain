"""Read complete Git snapshots; never rely on filename rename heuristics."""
import subprocess
from pathlib import Path
from .core import parse, reference_ids
from .census import census


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors='replace').strip())
    return result.stdout


class History:
    def __init__(self, root):
        existing = root.resolve()
        while not existing.exists():
            existing = existing.parent
        self.repo = Path(git(existing, 'rev-parse', '--show-toplevel').decode().removesuffix('\n'))
        self.prefix = root.resolve().relative_to(self.repo.resolve()).as_posix()
        if self.prefix == '.':
            self.prefix = ''
        self.cache = {}

    def revision(self, ref):
        return git(self.repo, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()

    def snapshot(self, ref):
        commit = self.revision(ref)
        if commit not in self.cache:
            records = {}
            paths = git(self.repo, 'ls-tree', '-rz', commit).split(b'\0')
            for raw in paths:
                if not raw:
                    continue
                header, raw_path = raw.split(b'\t', 1)
                mode = header.split()[0]
                path = raw_path.decode('utf-8', errors='surrogateescape')
                if not path.endswith('.md') or (self.prefix and not path.startswith(self.prefix + '/')):
                    continue
                relative = path[len(self.prefix) + 1:] if self.prefix else path
                if mode == b'120000':
                    raise ValueError(f'{relative}: Markdown symlinks are unsupported at commit {commit}')
                if mode not in (b'100644', b'100755'):
                    continue
                content = git(self.repo, 'show', commit + ':' + path).decode('utf-8')
                for clause in parse(content, relative):
                    if clause.id in records:
                        raise ValueError(f'duplicate ID {clause.id} at Git commit {commit}')
                    records[clause.id] = clause
            self.cache[commit] = records
        return self.cache[commit]

    def events(self, cid, ref='HEAD', all_refs=False):
        if git(self.repo, 'rev-parse', '--is-shallow-repository').decode().strip() == 'true':
            raise ValueError('clause log requires complete history; this repository is shallow (fetch --unshallow)')
        revision = self.revision(ref)
        args = ['rev-list', '--topo-order', '--parents']
        args.extend(['--all', revision] if all_refs else [revision])
        events = []
        for row in git(self.repo, *args).decode().splitlines():
            commit, *parents = row.split()
            current = self.snapshot(commit).get(cid)
            changes = []
            for parent in parents or [None]:
                before = self.snapshot(parent).get(cid) if parent else None
                kind = change(before, current)
                if kind:
                    changes.append({'parent': parent, 'change': kind, 'before_path': before.path if before else None})
            if changes:
                subject = git(self.repo, 'show', '-s', '--format=%s', commit).decode().strip()
                events.append({'commit': commit, 'parents': parents, 'subject': subject,
                               'path': current.path if current else None, 'changes': changes})
        return events


def change(before, after):
    if before is None and after is None:
        return None
    if before is None:
        return 'added'
    if after is None:
        return 'deleted'
    if before.signature() != after.signature():
        return 'modified+moved' if before.path != after.path else 'modified'
    return 'moved' if before.path != after.path else None


def normalized_body(body):
    """Ignore prose wrapping/spacing, preserving code and inline-code contents."""
    import re
    # Protect code fragments first. Their whitespace may affect behavior.
    chunks, paragraph, fence = [], [], None
    def flush():
        if paragraph:
            text = '\n'.join(paragraph)
            chunks.append(re.sub(r'(`+).*?\1|\s+', lambda m: m[0] if m[0].startswith('`') else ' ', text, flags=re.S).strip())
            paragraph.clear()
    for line in body.splitlines():
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            chunks.append(line)
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
        elif line.startswith(('    ', '\t')):
            flush()
            chunks.append(line)
        elif marker:
            flush()
            fence = (marker[1][0], len(marker[1]))
            chunks.append(line)
        else:
            paragraph.append(line)
    flush()
    return tuple(chunks)


def normalized_signature(clause):
    from .core import EDGE_KEYS
    meta = dict(clause.meta)
    for key in EDGE_KEYS:
        if key in meta:
            meta[key] = ','.join(sorted(set(t.strip() for t in meta[key].split(',') if t.strip())))
    return ' '.join(clause.title.split()), meta, normalized_body(clause.body)


def changelog(before, after):
    """Clause-level classifications and exact changes; no prose interpretation."""
    import difflib
    rows = []
    def edges(c, snapshot):
        if c is None:
            return set()
        mentions = {('mention', target) for ref in c.refs
                    for target in (reference_ids(ref, list(snapshot.values())) or [ref.strip()])}
        return set(c.edges()) | mentions
    for cid in sorted(set(before) | set(after)):
        old, new = before.get(cid), after.get(cid)
        old_edges, new_edges = edges(old, before), edges(new, after)
        graph_changed = old_edges != new_edges
        raw_change = change(old, new)
        kind = raw_change
        if not kind and not graph_changed:
            continue
        if graph_changed and kind in (None, 'moved'):
            kind = 'modified+moved' if kind == 'moved' else 'modified'
        categories = []
        if old is None or new is None:
            categories.append('added' if old is None else 'deleted')
        else:
            if old.signature() != new.signature() or graph_changed:
                categories.append('formatting-only' if normalized_signature(old) == normalized_signature(new) and not graph_changed else 'modified')
            if old.path != new.path:
                categories.append('moved')
            if old.meta.get('status') != new.meta.get('status'):
                if new.meta.get('status') == 'deprecated':
                    categories.append('deprecated')
            old_sup = {t for k, t in old.edges() if k == 'superseded-by'}
            new_sup = {t for k, t in new.edges() if k == 'superseded-by'}
            if new_sup and old_sup != new_sup:
                categories.append('superseded')
        old_meta, new_meta = old.meta if old else {}, new.meta if new else {}
        old_counts, new_counts = census(old), census(new)
        rows.append({'id': cid, 'change': kind, 'categories': categories, 'graph_only': raw_change is None,
                     'before': old.path if old else None, 'after': new.path if new else None,
                     'metadata_before': old_meta if old else None, 'metadata_after': new_meta if new else None,
                     'metadata_changes': {k: {'before': old_meta.get(k), 'after': new_meta.get(k)} for k in sorted(set(old_meta) | set(new_meta)) if old_meta.get(k) != new_meta.get(k)},
                     'edges_added': [{'type': k, 'target': t} for k, t in sorted(new_edges - old_edges)],
                     'edges_removed': [{'type': k, 'target': t} for k, t in sorted(old_edges - new_edges)],
                     'census_delta': {k: new_counts[k] - old_counts[k] for k in old_counts},
                     'title_before': old.title if old else None, 'title_after': new.title if new else None,
                     'body_diff': '\n'.join(difflib.unified_diff((old.body if old else '').splitlines(), (new.body if new else '').splitlines(), fromfile='before', tofile='after', lineterm=''))})
    return rows
