#!/usr/bin/env python3
"""Verify the skill's verbatim sources, provenance, and local reference closure."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/ndf-spec'


def check():
    data = json.loads((SKILL / 'references/provenance.json').read_text(encoding='utf-8'))
    for record in data['files']:
        original = (ROOT / record['source']).read_bytes()
        bundled = (SKILL / record['bundled']).read_bytes()
        if original != bundled or hashlib.sha256(bundled).hexdigest() != record['sha256']:
            raise ValueError('verbatim reference/provenance mismatch: ' + record['source'])
    # Check only authored skill guides, not source-document illustrative links.
    guides = [SKILL / 'SKILL.md', SKILL / 'references/proposal-map.md', SKILL / 'references/ndf-tool.md']
    for guide in guides:
        for address in re.findall(r'\[[^\]]+\]\(([^)]+)\)', guide.read_text(encoding='utf-8')):
            if '://' in address or address.startswith('#'):
                continue
            path = (guide.parent / address.split('#', 1)[0]).resolve()
            if not path.is_relative_to(SKILL.resolve()) or not path.is_file():
                raise ValueError(f'missing or nonportable local reference in {guide.name}: {address}')
    print('Skill sources are byte-for-byte complete; provenance and local references verified.')


if __name__ == '__main__':
    try:
        check()
    except (OSError, ValueError, KeyError) as exc:
        print(f'ndf skill: {exc}', file=sys.stderr)
        raise SystemExit(1)
