"""One indexed view of clause identity, paths and relationships.

Build once per immutable snapshot, then reuse for checks and reports. Worktree
and Git callers share reference semantics; an optional file inventory preserves
references to empty projection files without inventing clause identities.
"""
from collections import defaultdict
from .paths import relative_path


class SpecIndex:
    def __init__(self, clauses, *, root=None, files=()):
        self.clauses = tuple(clauses)
        self.root = root
        self.by_id = {}
        paths, incoming = defaultdict(list), defaultdict(set)
        self.duplicates = []
        self._typed = {}
        for clause in self.clauses:
            if clause.id in self.by_id:
                self.duplicates.append((clause, self.by_id[clause.id]))
            self.by_id[clause.id] = clause
            paths[clause.path].append(clause.id)
            typed = frozenset(clause.edges())
            self._typed[clause.id] = typed
            for kind, target in typed:
                incoming[kind, target].add(clause.id)
        self.by_path = {path: tuple(sorted(set(ids))) for path, ids in paths.items()}
        self.files = frozenset(set(files) | self.by_path.keys())
        self._incoming = {key: tuple(sorted(ids)) for key, ids in incoming.items()}
        self._resolved = {}
        self._edges = {}

    def resolve(self, reference):
        key = reference.strip()
        if key in self._resolved:
            return self._resolved[key]
        if key in self.by_id:
            result = (key,)
        else:
            path, _, anchor = key.partition('#')
            path = relative_path(path)
            result = () if path is None else tuple(sorted({cid for name in (path, path + '.md')
                       for cid in self.by_path.get(name, ()) if not anchor or cid == anchor}))
        self._resolved[key] = result
        return result

    def valid(self, reference):
        if self.resolve(reference):
            return True
        target = reference.strip()
        if '#' in target or ('/' not in target and not target.endswith('.md')):
            return False
        path = relative_path(target)
        if path is None:
            return False
        candidates = (path, path + '.md')
        return any(name in self.files or self.root is not None and (self.root / name).is_file()
                   for name in candidates)

    def typed(self, cid):
        return self._typed[cid]

    def incoming(self, relation, cid):
        return self._incoming.get((relation, cid), ())

    def edges(self, cid, *, fallback=True):
        key = cid, fallback
        if key not in self._edges:
            clause = self.by_id[cid]
            mentions = {('mention', target) for ref in clause.refs
                        for target in (self.resolve(ref) or ((ref.strip(),) if fallback else ()))}
            self._edges[key] = self.typed(cid) | mentions
        return self._edges[key]
