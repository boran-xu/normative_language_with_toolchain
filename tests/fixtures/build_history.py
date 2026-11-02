#!/usr/bin/env python3
"""Build the standalone fixture history. Does not import or call NDF.

Fixed authors, timestamps, file bytes, merge messages and refs make rebuilding
verifiable. Run with --bundle PATH --manifest PATH; construction is temporary.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile


class Builder:
    def __init__(self, root):
        self.root = root
        self.tick = 0
        self.refs = {}
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_AUTHOR_NAME='NDF Fixture', GIT_COMMITTER_NAME='NDF Fixture',
                        GIT_AUTHOR_EMAIL='fixture@example.invalid', GIT_COMMITTER_EMAIL='fixture@example.invalid',
                        LC_ALL='C', TZ='UTC')
        self.git('init', '-q', '--object-format=sha1', '-b', 'main')
        for key, value in [('commit.gpgsign', 'false'), ('core.autocrlf', 'false'), ('core.filemode', 'false'), ('core.hooksPath', os.devnull), ('merge.conflictStyle', 'merge')]:
            self.git('config', key, value)

    def git(self, *args, code=0):
        date = (datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=self.tick)).isoformat()
        env = dict(self.env, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        result = subprocess.run(['git', '-C', str(self.root), *args], env=env, capture_output=True, text=True)
        if result.returncode != code:
            raise RuntimeError(f'git {args}: {result.returncode}\n{result.stdout}\n{result.stderr}')
        return result.stdout.strip()

    def write(self, path, content):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding='utf-8')

    def read(self, path):
        return (self.root / path).read_text(encoding='utf-8')

    def replace(self, path, old, new):
        text = self.read(path)
        if old not in text:
            raise ValueError(f'{old!r} missing from {path}')
        self.write(path, text.replace(old, new))

    def save(self, message, tag):
        self.tick += 1
        self.git('add', '.')
        self.git('commit', '-qm', message)
        self.tag(tag)

    def tag(self, tag):
        self.git('tag', tag)
        self.refs[tag] = self.git('rev-parse', 'HEAD')

    def branch(self, name, ref):
        self.git('checkout', '-qb', name, ref)


def clause(cid, title, meta, body):
    return f'## {title} {{#{cid}}}\n<!-- ndf: {meta} -->\n\n{body}\n'


def models(b, limit):
    b.write('spec/models/chrono.py', f'''class Chrono:
    def __init__(self):
        self.count = 0
        self.running = False

    def step(self, reset=False, startstop=False, tick=False):
        if reset:
            self.count, self.running = 0, False
        else:
            if startstop:
                self.running = not self.running
            if tick and self.running:
                self.count = (self.count + 1) % {limit}

    @property
    def bcd(self):
        return self.count // 10, self.count % 10
''')
    b.write('spec/models/test_chrono.py', f'''import unittest
from chrono import Chrono

class Acceptance(unittest.TestCase):
    def test_VER_CNT_001_wrap(self):
        clock = Chrono()
        clock.step(startstop=True)
        for _ in range({limit - 1}):
            clock.step(tick=True)
        self.assertEqual(clock.count, {limit - 1}, "CNT-001 pre-wrap")
        clock.step(tick=True)
        self.assertEqual(clock.count, 0, "CNT-001 wrap")

    def test_VER_CTL_001_reset_priority(self):
        clock = Chrono()
        clock.step(startstop=True, tick=True)
        clock.step(reset=True, startstop=True, tick=True)
        self.assertEqual((clock.count, clock.running), (0, False), "CTL-002 reset priority")

    def test_VER_DSP_001_bcd(self):
        clock = Chrono()
        clock.step(startstop=True)
        for count in range({limit}):
            self.assertEqual(clock.bcd, divmod(count, 10), "DSP-001 BCD")
            clock.step(tick=True)
''')


def build(b):
    b.write('.gitignore', '__pycache__/\n*.pyc\n')
    b.write('README.md', '# Stopwatch development fixture\n\nSee the outer repository for scenario assertions and the command matrix.\n')
    b.write('spec/ndf.yaml', json.dumps({'project': 'history-chrono', 'id-prefixes': ['CHR', 'DEF', 'CNT', 'CTL', 'CON', 'DSP', 'VER', 'PRM', 'REF', 'INFO', 'D', 'Q'], 'layers': {'L0': 'intent', 'L1': 'contract', 'L2': 'mechanism', 'L3': 'executable'}}, indent=2) + '\n')
    b.write('spec/00-charter/charter.md', clause('CHR-000', 'Intent', 'kind=arch level=must layer=L0 status=stable since=0.1', 'The stopwatch counts whole seconds while running and exposes two decimal digits.') + clause('DEF-001', 'Definitions', 'kind=def level=must layer=L1 status=stable since=0.1', '- **tick** — one elapsed second.\n- **BCD** — one decimal digit per nibble.'))
    b.write('spec/20-behavior/counting.md', clause('CNT-001', 'Counting contract', 'kind=req level=must layer=L1 refines=CHR-000 status=stable since=0.1', 'While running, the count MUST advance on each tick.\nAfter 99, the count MUST wrap to zero.'))
    b.write('spec/20-behavior/controls.md', clause('CTL-001', 'Reset contract', 'kind=req level=must layer=L1 refines=CHR-000 status=draft since=0.1 blocks-by=Q-001', 'Reset MUST clear the count and stop.\nButton conditioning is ⟨TBD: debounce interval⟩.'))
    b.write('spec/open/Q-001.md', clause('Q-001', 'Debounce interval', 'kind=question status=open blocks=CTL-001', '**Question.** Which interval rejects switch bounce?\n**Resolution.** Undecided.'))
    b.write('spec/notes.md', clause('INFO-001', 'Independent note', 'kind=info level=may layer=L0 status=draft since=0.1', 'This disconnected note explains the toy scope.'))
    b.save('Capture intent, initial contracts and an open question', 'v0.1')

    b.write('spec/20-behavior/mechanism.md', clause('CNT-MOD-010', 'Counter mechanism', 'kind=req level=must layer=L2 refines=CNT-001 depends-on=REF-TIME-001 model=models/chrono.py status=stable since=0.2', 'The counter MUST follow the reference model.\n```python ndf:normative\ncount = (count + 1) % 100\n```'))
    b.write('spec/50-verification/acceptance.md', clause('VER-CNT-001', 'Count acceptance', 'kind=verif level=must layer=L3 verifies=CNT-001,CNT-MOD-010 status=stable since=0.2', 'The wrap test MUST pass.') + clause('VER-CTL-001', 'Control acceptance', 'kind=verif level=must layer=L3 verifies=CTL-001 status=stable since=0.2', 'Reset priority tests MUST pass.') + clause('VER-DSP-001', 'Display acceptance', 'kind=verif level=must layer=L3 verifies=DSP-001 status=stable since=0.2', 'Every output digit MUST match the model.'))
    b.write('spec/40-constraints/options.md', clause('PRM-DEB-001', 'Debounce interval', 'kind=option level=tbd layer=L2 refines=CTL-001 default=10 explore=5,10,20 unit=ms couples-with=PRM-CLK-001 depends-on=REF-TIME-001 status=draft since=0.2', 'The interval is a design-space parameter. ⟨DSE: debounce default=10 range=5,10,20 → PRM-DEB-001⟩') + clause('PRM-CLK-001', 'Clock rate', 'kind=option level=tbd layer=L2 refines=CNT-001 default=1000 explore=1000,2000 unit=Hz couples-with=PRM-DEB-001 status=draft since=0.2', 'The clock rate sets the interval granularity.'))
    b.write('spec/refs/time.md', clause('REF-TIME-001', 'tick', 'kind=def level=must layer=L1 status=stable since=0.2 origin="Toy Time Standard 1.0 §1" origin-status=paraphrase', 'A tick represents one elapsed second.\nAliases: second pulse'))
    b.write('spec/40-constraints/timing.md', clause('CON-CLK-001', 'Clock accuracy', 'kind=constraint level=must layer=L1 refines=CHR-000 depends-on=REF-TIME-001 status=stable since=0.2', 'The clock MUST generate exactly one tick per second.'))
    b.write('spec/30-interfaces/display.md', clause('DSP-001', 'Display contract', 'kind=req level=must layer=L1 refines=CHR-000 depends-on=CNT-001,REF-TIME-001 status=stable since=0.2', 'The display MUST expose BCD digits. See [[REF-TIME-001]] and [[refs/time.md#REF-TIME-001 | timing source]].'))
    b.write('spec/decisions/D-001.md', clause('D-001', 'Rollover decision', 'kind=decision date=2025-01-01 affects=CNT-001', '**Decision.** Use the full two-digit range.\n**Source.** Initial design review.'))
    b.write('spec/20-behavior/legacy.md', clause('CTL-OLD-001', 'Legacy switch input', 'kind=req level=should layer=L1 status=draft since=0.2', 'A legacy switch SHOULD be supported.'))
    models(b, 100)
    b.save('Add mechanisms, models, acceptance, projections and coupled options', 'v0.2')

    b.replace('spec/20-behavior/controls.md', 'status=draft since=0.1 blocks-by=Q-001', 'status=superseded-by=CTL-002 since=0.1')
    b.write('spec/20-behavior/reset.md', clause('CTL-002', 'Reset and debounce', 'kind=req level=must layer=L1 refines=CHR-000 depends-on=PRM-DEB-001 status=stable since=0.3', 'Reset MUST clear the count and stop, dominating simultaneous events.\nButton inputs MUST be stable for 10 ms; see [[D-002]].'))
    b.replace('spec/50-verification/acceptance.md', 'verifies=CTL-001', 'verifies=CTL-002')
    b.replace('spec/open/Q-001.md', 'status=open', 'status=resolved')
    b.replace('spec/open/Q-001.md', '**Resolution.** Undecided.', '**Resolution.** Use 10 ms; see [[D-002]].')
    b.replace('spec/40-constraints/options.md', 'kind=option level=tbd', 'kind=option level=must')
    b.replace('spec/40-constraints/options.md', 'status=draft since=0.2', 'status=stable since=0.3')
    b.replace('spec/40-constraints/options.md', 'refines=CTL-001', 'refines=CTL-002')
    b.replace('spec/20-behavior/legacy.md', 'status=draft', 'status=deprecated')
    b.write('spec/decisions/D-002.md', clause('D-002', 'Debounce resolution', 'kind=decision date=2025-01-01 affects=CTL-001,CTL-002,PRM-DEB-001,PRM-CLK-001', '**Decision.** Choose 10 ms at 1000 Hz.\n**Source.** Resolves [[Q-001]].'))
    b.save('Resolve debounce, close options, supersede reset and retire legacy input', 'v0.3')

    b.git('mv', 'spec/20-behavior/counting.md', 'spec/20-behavior/count ü.md')
    b.replace('spec/20-behavior/count ü.md', 'on each tick.\nAfter 99', 'on each\ntick. After 99')
    b.save('Move contract through a Unicode filename and reflow prose', 'v0.4')
    countpath = 'spec/20-behavior/count ü.md'
    def wrap(old, new):
        b.replace(countpath, f'After {old}', f'After {new}')
        models(b, new + 1)
        # Keep normative snippet consistent with the same model limit.
        b.replace('spec/20-behavior/mechanism.md', f'% {old + 1}', f'% {new + 1}')

    b.branch('feature/short-wrap', 'v0.4')
    wrap(99, 59)
    b.save('Explore a clock-like wrap policy', 'scenario/conflict-side')
    b.git('checkout', '-q', 'main')
    wrap(99, 89)
    b.save('Reserve part of the display range', 'scenario/conflict-main')
    b.git('merge', '--no-ff', '-m', 'Integrate wrap alternatives', 'feature/short-wrap', code=1)
    # Resolve conflicted files from the main parent, then deliberately choose 79.
    b.git('checkout', 'HEAD', '--', countpath, 'spec/20-behavior/mechanism.md', 'spec/models/chrono.py', 'spec/models/test_chrono.py')
    wrap(89, 79)
    b.save('Resolve both proposals with an explicit 79 wrap', 'scenario/conflict-resolved')

    b.branch('feature/display', 'scenario/conflict-resolved')
    b.replace('spec/30-interfaces/display.md', 'expose BCD digits.', 'expose BCD digits atomically.')
    b.save('Require atomic display updates', 'scenario/clean-side')
    b.git('checkout', '-q', 'main')
    b.replace('spec/40-constraints/timing.md', 'per second.', 'per second while enabled.')
    b.save('Clarify clock enable behavior', 'scenario/clean-main')
    b.tick += 1
    b.git('merge', '--no-ff', '-m', 'Integrate independent display and clock changes', 'feature/display')
    b.tag('scenario/clean-merge')

    # Two independent conflicted merge scenarios: choose precisely one parent.
    for chosen, side_limit, main_limit in [('side', 69, 39), ('main', 49, 29)]:
        b.branch('feature/match-' + chosen, 'scenario/clean-merge')
        wrap(79, side_limit)
        b.save('Side wrap candidate ' + chosen, 'scenario/match-' + chosen + '-side')
        b.branch('integration/match-' + chosen, 'scenario/clean-merge')
        wrap(79, main_limit)
        b.save('Main wrap candidate ' + chosen, 'scenario/match-' + chosen + '-main')
        b.git('merge', '--no-ff', '-m', 'Compare wrap candidates ' + chosen, 'feature/match-' + chosen, code=1)
        selected = 'feature/match-' + chosen if chosen == 'side' else 'HEAD'
        b.git('checkout', selected, '--', countpath, 'spec/20-behavior/mechanism.md', 'spec/models/chrono.py', 'spec/models/test_chrono.py')
        b.save('Resolve by retaining the ' + chosen + ' parent', 'scenario/match-' + chosen)
    b.git('checkout', '-q', 'main')
    b.tag('v1.0')

    b.branch('experiment/cycle', 'v1.0')
    b.replace('spec/20-behavior/mechanism.md', 'depends-on=REF-TIME-001', 'depends-on=DSP-001,REF-TIME-001')
    b.save('Explore cyclic cross-subsystem dependencies', 'scenario/dependency-cycle')

    scenarios = {
        'invalid/duplicate': lambda: b.write('spec/duplicate.md', b.read(countpath)),
        'invalid/dangling': lambda: b.replace(countpath, 'refines=CHR-000', 'refines=CHR-MISSING'),
        'invalid/metadata': lambda: b.replace(countpath, 'level=must', 'level=always'),
        'invalid/conflict-markers': lambda: b.write('spec/unresolved.md', '<<<<<<< HEAD\nfirst\n=======\nsecond\n>>>>>>> feature\n'),
        'invalid/refinement-cycle': lambda: b.replace('spec/00-charter/charter.md', 'kind=arch level=must layer=L0', 'kind=arch level=must layer=L0 refines=CNT-MOD-010'),
        'tests/failing': lambda: b.write('spec/models/test_failure.py', 'import unittest\nclass Broken(unittest.TestCase):\n def test_VER_CNT_001(self): self.fail("CNT-001 injected failure")\n'),
        'tests/missing': lambda: b.git('rm', 'spec/models/test_chrono.py'),
    }
    for name, mutate in scenarios.items():
        b.branch(name, 'v1.0')
        mutate()
        b.save('Fixture scenario: ' + name, name)
    b.branch('experiment/note-lifecycle', 'v1.0')
    note = b.read('spec/notes.md')
    b.git('rm', 'spec/notes.md')
    b.save('Remove an informative note', 'scenario/delete-note')
    b.write('spec/notes.md', note)
    b.save('Restore the informative note', 'scenario/restore-note')
    b.branch('experiment/known-conflict', 'v1.0')
    b.replace('spec/30-interfaces/display.md', 'depends-on=CNT-001,REF-TIME-001', 'depends-on=CNT-001,REF-TIME-001 conflicts-with=CON-CLK-001')
    b.replace('spec/20-behavior/mechanism.md', 'model=models/chrono.py', 'model=models/chrono.py derived-from=REF-TIME-001')
    b.write('spec/open/Q-002.md', clause('Q-002', 'Clock versus display timing', 'kind=question status=open blocks=DSP-001,CON-CLK-001', '**Question.** Reconcile the recorded timing conflict.'))
    b.save('Record a known conflict and reference derivation', 'scenario/known-conflict')
    b.git('checkout', '-q', 'main')
    return b.refs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='ndf-history-build-') as directory:
        b = Builder(Path(directory))
        refs = build(b)
        args.bundle.parent.mkdir(parents=True, exist_ok=True)
        b.git('bundle', 'create', str(args.bundle.resolve()), '--all')
        args.manifest.write_text(json.dumps({'pin': refs['v1.0'], 'refs': dict(sorted(refs.items()))}, indent=2) + '\n')
        print(f'Built {len(refs)} named snapshots; pin {refs["v1.0"]}')


if __name__ == '__main__':
    main()
