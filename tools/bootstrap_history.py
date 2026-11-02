#!/usr/bin/env python3
"""Initialize the pinned fixture submodule offline from its tracked Git bundle."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATH = 'tests/fixtures/history'
NAME = 'history-fixture'


def git(*args, cwd=ROOT):
    result = subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def bootstrap():
    record = git('ls-files', '--stage', '--', PATH).split()
    if len(record) != 4 or record[0] != '160000' or record[2] != '0':
        raise RuntimeError(f'{PATH} must be a tracked, unconflicted submodule')
    pin = record[1]
    manifest = json.loads((ROOT / 'tests/fixtures/history.json').read_text())
    if pin != manifest['pin']:
        raise RuntimeError('gitlink differs from history.json; update both deliberately')
    bundle = ROOT / 'tests/fixtures/chrono.bundle'
    target = ROOT / PATH
    if (target / '.git').exists() and git('status', '--porcelain', cwd=target):
        raise RuntimeError('fixture submodule is dirty; refusing to change it')
    git('-c', 'protocol.file.allow=always', '-c', f'submodule.{NAME}.url={bundle}',
        'submodule', 'update', '--init', '--checkout', '--', PATH)
    # Explicitly fetch every advertised branch and tag, even from detached HEAD.
    git('fetch', str(bundle), '+refs/heads/*:refs/remotes/origin/*', '+refs/tags/*:refs/tags/*', cwd=target)
    if git('rev-parse', 'HEAD', cwd=target) != pin:
        raise RuntimeError('fixture checkout differs from pinned gitlink')
    if git('rev-parse', '--is-shallow-repository', cwd=target) != 'false':
        raise RuntimeError('fixture must have complete history')
    for ref, expected in manifest['refs'].items():
        if git('rev-parse', 'refs/tags/' + ref, cwd=target) != expected:
            raise RuntimeError('fixture ref mismatch: ' + ref)
    print(f'Fixture ready: {PATH} @ {pin} ({len(manifest["refs"])} snapshots)')


if __name__ == '__main__':
    try:
        bootstrap()
    except (RuntimeError, OSError, ValueError) as exc:
        raise SystemExit(f'fixture setup: {exc}')
