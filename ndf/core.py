"""Read heading-anchored clauses without interpreting Markdown code as metadata."""
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import json
import re
import shlex
from .markdown import visible, references, META

HEADING = re.compile(r'^ {0,3}(#{1,6})[ \t]+(.*?)\s*$')
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
    clauses, current, lines = [], None, []
    def finish():
        if current:
            current.body = '\n'.join(lines).strip('\n\r')
            current.refs = references(current.body)
            clauses.append(current)
    raw_lines = text.splitlines()
    for number, (line, exposed) in enumerate(zip(raw_lines, visible(text, keep_metadata=True).splitlines()), 1):
        heading = HEADING.match(exposed)
        heading_text = re.sub(r'[ \t]+#+[ \t]*$', '', heading[2]).rstrip() if heading else ''
        anchor = ANCHOR.search(heading_text) if heading else None
        if heading and (anchor or (current and len(heading[1]) <= current_depth)):
            finish()
            current, lines = None, []
            if anchor:
                current = Clause(anchor[1], heading_text[:anchor.start()].strip(), path, number)
                current_depth = len(heading[1])
            continue
        if current:
            metadata = META.fullmatch(exposed)
            if metadata:
                # Visibility masks code spans; actual metadata values come from
                # the source line after its structural position is established.
                original = META.fullmatch(line)
                try:
                    for token in shlex.split(original[1]):
                        if '=' not in token:
                            raise ValueError('expected key=value: ' + token)
                        key, value = token.split('=', 1)
                        if key in current.meta:
                            raise ValueError('duplicate metadata key: ' + key)
                        current.meta[key] = value
                except ValueError as exc:
                    current.errors.append(str(exc))
            else:
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
    if 'layers' in value and (not isinstance(layers, (dict, list)) or not layers or not all(isinstance(x, str) and x for x in layers) or len(set(layers)) != len(layers)):
        raise ValueError('layers must be a nonempty ordered mapping or list of unique names')
    return value


def relative_path(path):
    """Canonical POSIX spelling; reject absolute paths and parent traversal."""
    rel = PurePosixPath(path)
    if rel.is_absolute() or '..' in rel.parts:
        return None
    return rel.as_posix()


def reference_ids(target, clauses):
    target = target.strip()
    if any(c.id == target for c in clauses):
        return [target]
    path, _, anchor = target.partition('#')
    path = relative_path(path)
    if path is None:
        return []
    return sorted(c.id for c in clauses if c.path in (path, path + '.md')
                  and (not anchor or c.id == anchor))


def resolve(target, clauses, root):
    if reference_ids(target, clauses):
        return True
    target = target.strip()
    if '#' in target or ('/' not in target and not target.endswith('.md')):
        return False
    path = relative_path(target)
    return path is not None and any((root / name).is_file() for name in (path, path + '.md'))


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
        for key in EDGE_KEYS:
            if key in c.meta and any(not part.strip() for part in c.meta[key].split(',')):
                errors.append(f'{loc}: {key} requires nonempty clause IDs')
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
    for start in index:
        pending = [(start, False)]
        while pending:
            cid, exiting = pending.pop()
            if exiting:
                visiting.discard(cid)
                visited.add(cid)
            elif cid in visiting:
                errors.append(f'{cid}: refinement cycle')
            elif cid not in visited:
                visiting.add(cid)
                pending.append((cid, True))
                pending.extend((target, False) for kind, target in index[cid].edges()
                               if kind == 'refines' and target in index)
    from .glossary import warnings as glossary_warnings
    warnings.extend(glossary_warnings(clauses, config))
    return errors, warnings
