"""Read complete Git snapshots; never rely on filename rename heuristics."""
import subprocess
from pathlib import Path
from .core import parse
from .index import SpecIndex
from .markdown import source_lines
from .census import census


def git(repo, *args, stdin=None):
    result = subprocess.run(['git', '-C', str(repo), *args], input=stdin, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors='replace').strip())
    return result.stdout


class Snapshot(dict):
    """Clause mapping plus regular Markdown paths present in the Git tree."""
    def __init__(self, records=(), *, files=()):
        super().__init__(records)
        self.files = frozenset(files)


class History:
    """Read immutable Git objects in batches, sharing tree/blob work by OID.

    No long-lived subprocess or disk cache is needed. A graph query fetches all
    commits together, scoped trees one depth wave at a time, and all distinct
    Markdown blobs together. Moves reuse parsed text but retain per-path Clause
    instances; symbolic revisions are resolved anew on every public query.
    """
    def __init__(self, root):
        existing = root.resolve()
        while not existing.exists():
            existing = existing.parent
        self.repo = Path(git(existing, 'rev-parse', '--show-toplevel').decode().removesuffix('\n'))
        self.prefix = root.resolve().relative_to(self.repo.resolve()).as_posix()
        if self.prefix == '.':
            self.prefix = ''
        self.cache = {}
        self._objects = {}
        self._commit_trees = {}
        self._trees = {}
        self._files = {}
        self._clauses = {}

    def revision(self, ref):
        if ref in self._commit_trees:
            return ref
        return git(self.repo, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()

    def _read_objects(self, object_ids):
        """Decode cat-file's size-framed batch protocol, including empty blobs."""
        missing = list(dict.fromkeys(oid for oid in object_ids if oid not in self._objects))
        if not missing:
            return
        payload = git(self.repo, 'cat-file', '--batch', stdin=('\n'.join(missing) + '\n').encode('ascii'))
        offset = 0
        for requested in missing:
            end = payload.find(b'\n', offset)
            if end == -1:
                raise ValueError('incomplete Git batch object header')
            header = payload[offset:end].split()
            if len(header) != 3 or header[-1] == b'missing':
                raise ValueError('Git object is unavailable: ' + requested)
            oid, kind, length = header
            size = int(length)
            start, offset = end + 1, end + 1 + size
            if offset >= len(payload) or payload[offset:offset + 1] != b'\n':
                raise ValueError('incomplete Git batch object payload')
            self._objects[requested] = kind, payload[start:offset]
            offset += 1
        if offset != len(payload):
            raise ValueError('unexpected trailing Git batch data')

    def _load_trees(self, object_ids):
        missing = set(object_ids) - self._trees.keys()
        self._read_objects(sorted(missing))
        for oid in missing:
            kind, data = self._objects[oid]
            if kind != b'tree':
                raise ValueError('expected Git tree object: ' + oid)
            entries, offset, hash_size = [], 0, len(oid) // 2
            while offset < len(data):
                separator = data.find(b' ', offset)
                terminator = data.find(b'\0', separator + 1)
                end = terminator + 1 + hash_size
                if separator == -1 or terminator == -1 or end > len(data):
                    raise ValueError('invalid Git tree object: ' + oid)
                mode = data[offset:separator]
                name = data[separator + 1:terminator].decode('utf-8', errors='surrogateescape')
                target = data[terminator + 1:end].hex()
                entries.append((mode, name, target))
                offset = end
            self._trees[oid] = tuple(entries)

    def _scope_trees(self, commits):
        self._read_objects(commits)
        for commit in commits:
            if commit in self._commit_trees:
                continue
            kind, content = self._objects[commit]
            first = content.split(b'\n', 1)[0]
            if kind != b'commit' or not first.startswith(b'tree '):
                raise ValueError('expected Git commit object: ' + commit)
            self._commit_trees[commit] = first[5:].decode('ascii')
        scoped = {commit: self._commit_trees[commit] for commit in commits}
        for component in self.prefix.split('/') if self.prefix else ():
            self._load_trees(oid for oid in scoped.values() if oid is not None)
            for commit, oid in scoped.items():
                scoped[commit] = next((target for mode, name, target in self._trees[oid]
                                      if mode == b'40000' and name == component), None) if oid else None
        return scoped

    def _load_subtrees(self, roots):
        pending, seen = set(roots), set()
        while pending:
            self._load_trees(pending)
            seen.update(pending)
            pending = {target for oid in pending for mode, _, target in self._trees[oid]
                       if mode == b'40000' and target not in seen}

    def _tree_files(self, root):
        pending = [(root, False)]
        while pending:
            oid, expanded = pending.pop()
            if oid in self._files:
                continue
            if expanded:
                files = []
                for mode, name, target in self._trees[oid]:
                    if mode == b'40000':
                        files.extend((child_mode, name + '/' + path, blob)
                                     for child_mode, path, blob in self._files[target])
                    elif name.endswith('.md'):
                        files.append((mode, name, target))
                self._files[oid] = tuple(files)
            else:
                pending.append((oid, True))
                pending.extend((target, False) for mode, _, target in self._trees[oid]
                               if mode == b'40000' and target not in self._files)
        return self._files[root]

    def _prepare(self, commits):
        from dataclasses import replace
        missing = list(dict.fromkeys(commit for commit in commits if commit not in self.cache))
        if not missing:
            return
        scoped = self._scope_trees(missing)
        self._load_subtrees(oid for oid in scoped.values() if oid is not None)
        listings = {commit: self._tree_files(tree) if tree else () for commit, tree in scoped.items()}
        self._read_objects(blob for files in listings.values() for mode, _, blob in files
                           if mode in (b'100644', b'100755'))
        for commit, files in listings.items():
            records, inventory = {}, []
            for mode, path, blob in files:
                if mode == b'120000':
                    raise ValueError(f'{path}: Markdown symlinks are unsupported at commit {commit}')
                if mode not in (b'100644', b'100755'):
                    continue
                inventory.append(path)
                if blob not in self._clauses:
                    kind, content = self._objects[blob]
                    if kind != b'blob':
                        raise ValueError('expected Markdown blob: ' + blob)
                    self._clauses[blob] = tuple(parse(content.decode('utf-8'), ''))
                for template in self._clauses[blob]:
                    clause = replace(template, path=path, meta=dict(template.meta),
                                     refs=list(template.refs), errors=list(template.errors))
                    if clause.id in records:
                        raise ValueError(f'duplicate ID {clause.id} at Git commit {commit}')
                    records[clause.id] = clause
            self.cache[commit] = Snapshot(records, files=inventory)

    def snapshot(self, ref):
        commit = self.revision(ref)
        self._prepare([commit])
        return self.cache[commit]

    def events(self, cid, ref='HEAD', all_refs=False):
        if git(self.repo, 'rev-parse', '--is-shallow-repository').decode().strip() == 'true':
            raise ValueError('clause log requires complete history; this repository is shallow (fetch --unshallow)')
        revision = self.revision(ref)
        args = ['log', '--topo-order', '--no-show-signature', '--format=%H%x00%P%x00%s%x00']
        args.extend(['--all', revision] if all_refs else [revision])
        fields = git(self.repo, *args).split(b'\0')
        if (len(fields) - 1) % 3 or fields[-1].strip():
            raise ValueError('invalid Git history record framing')
        graph = [(fields[i].decode().strip(), fields[i + 1].decode().split(), fields[i + 2].decode().strip())
                 for i in range(0, len(fields) - 1, 3)]
        self._prepare(commit for commit, _, _ in graph)
        events = []
        for commit, parents, subject in graph:
            current = self.cache[commit].get(cid)
            changes = []
            for parent in parents or [None]:
                before = self.cache[parent].get(cid) if parent else None
                kind = change(before, current)
                if kind:
                    changes.append({'parent': parent, 'change': kind, 'before_path': before.path if before else None})
            if changes:
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
    for line in source_lines(body):
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
    before_index = SpecIndex(before.values(), files=getattr(before, 'files', ()))
    after_index = SpecIndex(after.values(), files=getattr(after, 'files', ()))
    def edges(c, index):
        return index.edges(c.id) if c is not None else frozenset()
    for cid in sorted(set(before) | set(after)):
        old, new = before.get(cid), after.get(cid)
        old_edges, new_edges = edges(old, before_index), edges(new, after_index)
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
                     'body_diff': '\n'.join(difflib.unified_diff(source_lines(old.body) if old and old.body else [], source_lines(new.body) if new and new.body else [], fromfile='before', tofile='after', lineterm=''))})
    return rows
