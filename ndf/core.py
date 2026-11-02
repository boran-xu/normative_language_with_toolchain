"""Read heading-anchored clauses without interpreting Markdown code as metadata."""
from dataclasses import dataclass, field
from pathlib import Path
import json
import re
import shlex
from .markdown import without_inline_code

HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*$')
ANCHOR = re.compile(r'\{#([A-Za-z][\w.-]*)\}\s*$')
EDGE_KEYS = ('refines', 'depends-on', 'conflicts-with', 'verifies', 'derived-from',
             'affects', 'blocks', 'blocks-by', 'couples-with', 'superseded-by')

@dataclass
class Clause:
    id: str
    title: str
    path: str
    line: int
    meta: dict = field(default_factory=dict)
    body: str = ''
    refs: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def edges(self):
        for key in EDGE_KEYS:
            value = self.meta.get(key, '')
            if key == 'superseded-by' and not value:
                value = self.meta.get('status', '').removeprefix('superseded-by=') if self.meta.get('status', '').startswith('superseded-by=') else ''
            for target in value.split(','):
                if target.strip():
                    yield key, target.strip()

    def signature(self):
        return self.title, self.meta, self.body

    def resolution(self):
        match = re.search(r'(?im)^\*\*Resolution[.:]?\*\*[.:]?\s*(.+)$', self.body)
        return self.meta.get('resolution') or (match[1] if match else None)

    def active(self):
        return self.meta.get('status') != 'deprecated' and not any(k == 'superseded-by' for k, _ in self.edges())


def parse(text, path):
    clauses, current, fence, lines = [], None, None, []
    def finish():
        if current:
            current.body = '\n'.join(lines).strip()
            clauses.append(current)
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})(.*)$', line)
        if marker:
            marks, tail = marker.groups()
            if fence is None:
                fence = (marks[0], len(marks))
            elif marks[0] == fence[0] and len(marks) >= fence[1] and not tail.strip():
                fence = None
            if current:
                lines.append(line)
            continue
        if fence:
            if current:
                lines.append(line)
            continue
        heading = HEADING.match(line)
        anchor = ANCHOR.search(heading[2]) if heading else None
        if heading and (anchor or (current and len(heading[1]) <= current_depth)):
            finish()
            current, lines = None, []
            if anchor:
                current = Clause(anchor[1], heading[2][:anchor.start()].strip(), path, number)
                current_depth = len(heading[1])
            continue
        if current:
            metadata = re.fullmatch(r'\s*<!--\s*ndf:\s*(.*?)\s*-->\s*', line)
            if metadata:
                try:
                    for token in shlex.split(metadata[1]):
                        if '=' not in token:
                            raise ValueError('expected key=value: ' + token)
                        key, value = token.split('=', 1)
                        if key in current.meta:
                            raise ValueError('duplicate metadata key: ' + key)
                        current.meta[key] = value
                except ValueError as exc:
                    current.errors.append(str(exc))
            else:
                current.refs.extend(re.findall(r'\[\[([^]|]+)(?:\|[^]]*)?\]\]', without_inline_code(line)))
                lines.append(line)
    finish()
    return clauses


def load(root):
    return [c for p in sorted(root.rglob('*.md')) if '.git' not in p.parts
            for c in parse(p.read_text(encoding='utf-8'), p.relative_to(root).as_posix())]


def manifest(root):
    path = root / 'ndf.yaml'
    if not path.exists():
        raise ValueError('missing ndf.yaml (run ndf init)')
    text = path.read_text(encoding='utf-8')
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError:
            raise ValueError('Use JSON syntax in ndf.yaml (valid YAML), or install PyYAML for YAML syntax.') from None
        try:
            value = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f'invalid YAML manifest: {exc}') from None
    if not isinstance(value, dict) or not isinstance(value.get('id-prefixes'), list) or not value['id-prefixes']:
        raise ValueError('ndf.yaml requires a nonempty id-prefixes list')
    if any(not isinstance(p, str) or not re.fullmatch(r'[A-Za-z][\w.-]*', p) for p in value['id-prefixes']):
        raise ValueError('invalid id-prefixes')
    layers = value.get('layers')
    if layers is not None and (not isinstance(layers, (dict, list)) or not layers or not all(isinstance(x, str) for x in layers)):
        raise ValueError('layers must be a nonempty ordered mapping or list')
    return value


def resolve(target, clauses, root):
    target = target.strip()
    ids = {c.id for c in clauses}
    if target in ids:
        return True
    if '/' not in target and '#' not in target and not target.endswith('.md'):
        return False
    path, _, anchor = target.partition('#')
    rel = Path(path)
    if rel.is_absolute() or '..' in rel.parts:
        return False
    candidates = [path, path + '.md']
    for name in candidates:
        if anchor:
            if any(c.path == name and c.id == anchor for c in clauses):
                return True
        elif (root / name).is_file():
            return True
    return False


def reference_ids(target, clauses):
    """Resolve a mention to clause IDs, including whole-file projections."""
    target = target.strip()
    if any(c.id == target for c in clauses):
        return [target]
    path, _, anchor = target.partition('#')
    if Path(path).is_absolute() or '..' in Path(path).parts:
        return []
    return sorted(c.id for c in clauses if c.path in (path, path + '.md')
                  and (not anchor or c.id == anchor))


def validate(clauses, root, config):
    from .glossary import prose as visible_prose
    errors, warnings, index = [], [], {}
    for path in root.rglob('*.md'):
        if re.search(r'(?m)^(<{7}|={7}|>{7})(?: |$)', visible_prose(path.read_text(encoding='utf-8'))):
            errors.append(f'{path.relative_to(root)}: unresolved Git conflict marker')
    kinds = {'req', 'def', 'arch', 'constraint', 'option', 'verif', 'info', 'decision', 'question'}
    layers = config.get('layers', {'L0': 'intent', 'L1': 'contract', 'L2': 'mechanism', 'L3': 'executable'})
    for c in clauses:
        loc = f'{c.path}:{c.line} {c.id}'
        if c.id in index:
            errors.append(f'{loc}: duplicate ID (also {index[c.id].path})')
        index[c.id] = c
        errors.extend(f'{loc}: {e}' for e in c.errors)
        if not any(c.id.startswith(p + '-') for p in config['id-prefixes']):
            errors.append(f'{loc}: undeclared ID prefix')
        if c.meta.get('kind') not in kinds:
            errors.append(f'{loc}: missing or invalid kind')
        if c.meta.get('kind') not in {'decision', 'question'}:
            if c.meta.get('level') not in {'must', 'should', 'may', 'tbd'}:
                errors.append(f'{loc}: missing or invalid level')
            if c.meta.get('layer') not in layers:
                errors.append(f'{loc}: missing or invalid layer')
        # Keywords in rationale or example code do not establish an obligation.
        prose = '\n'.join(l for l in c.body.splitlines() if not l.lstrip().startswith('>'))
        prose = visible_prose(prose)
        if c.meta.get('kind') == 'req' and not re.search(r'\b(MUST|SHALL|SHOULD|MAY)\b', prose):
            warnings.append(f'{loc}: requirement has no normative keyword')
        if c.meta.get('kind') == 'info' and re.search(r'\b(MUST|SHALL)\b', prose):
            warnings.append(f'{loc}: normative keyword in informative clause')
        if c.meta.get('kind') == 'option' and not all(c.meta.get(k) for k in ('default', 'explore')):
            errors.append(f'{loc}: option requires default and explore')
        if c.meta.get('level') == 'must':
            for phrase in ('appropriately', 'as needed', 'etc.'):
                if phrase in prose.lower():
                    warnings.append(f'{loc}: ambiguous wording: {phrase}')
        status = c.meta.get('status')
        if status and status not in {'draft', 'stable', 'deprecated', 'open', 'closed', 'resolved'} and not status.startswith('superseded-by='):
            errors.append(f'{loc}: invalid status {status}')
        if (status and status.startswith('superseded-by=') and not status.split('=', 1)[1].strip()) or ('superseded-by' in c.meta and not c.meta['superseded-by'].strip()):
            errors.append(f'{loc}: empty supersession target')
        if c.meta.get('kind') == 'question' and status in {'closed', 'resolved'} and not c.resolution():
            warnings.append(f'{loc}: closed question has no resolution')
        for target in c.refs:
            if not resolve(target, clauses, root):
                errors.append(f'{loc}: dangling reference {target.strip()}')
        for key, target in c.edges():
            if target not in {x.id for x in clauses}:
                errors.append(f'{loc}: dangling {key}={target}')
            if key == 'conflicts-with':
                warnings.append(f'{loc}: known conflict with {target}')
        model = c.meta.get('model')
        if model and (Path(model).is_absolute() or '..' in Path(model).parts or not (root / model).is_file()):
            errors.append(f'{loc}: missing or unsafe model path {model}')
    for c in clauses:
        for key, target in c.edges():
            if key == 'verifies' and c.meta.get('kind') != 'verif':
                errors.append(f'{c.id}: verifies edge must originate in a verif clause')
            if key == 'refines' and target in index:
                child, parent = c.meta.get('layer', ''), index[target].meta.get('layer', '')
                order = list(layers)
                if child in order and parent in order and order.index(child) <= order.index(parent):
                    errors.append(f'{c.id}: refines must point to a lower layer: {target}')
    # Refinement must be acyclic, even when layer metadata is absent.
    visited, visiting = set(), set()
    def visit(cid):
        if cid in visiting:
            errors.append(f'{cid}: refinement cycle')
            return
        if cid in visited:
            return
        visiting.add(cid)
        for k, target in index[cid].edges():
            if k == 'refines' and target in index:
                visit(target)
        visiting.remove(cid)
        visited.add(cid)
    for cid in index:
        visit(cid)
    from .glossary import warnings as glossary_warnings
    warnings.extend(glossary_warnings(clauses, config))
    return errors, warnings
