"""Read complete Git snapshots; never rely on filename rename heuristics."""
import subprocess
from pathlib import Path
from .core import parse


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors='replace').strip())
    return result.stdout


class History:
    def __init__(self, root):
        self.repo = Path(git(root, 'rev-parse', '--show-toplevel').decode().strip())
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
            paths = git(self.repo, 'ls-tree', '-rz', '--name-only', commit).split(b'\0')
            for raw in paths:
                path = raw.decode('utf-8', errors='surrogateescape')
                if not path.endswith('.md') or (self.prefix and not path.startswith(self.prefix + '/')):
                    continue
                relative = path[len(self.prefix) + 1:] if self.prefix else path
                content = git(self.repo, 'show', commit + ':' + path).decode('utf-8')
                for clause in parse(content, relative):
                    if clause.id in records:
                        raise ValueError(f'duplicate ID {clause.id} at Git commit {commit}')
                    records[clause.id] = clause
            self.cache[commit] = records
        return self.cache[commit]

    def events(self, cid, ref='HEAD', all_refs=False):
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
