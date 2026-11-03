"""Pure current-snapshot reports built on the same clause index."""
from .census import census
from .paths import relative_path


def coverage(index, config, *, include_questions=False):
    clauses = index.clauses
    eligible = {v.id for v in clauses if v.active() and v.meta.get('kind') == 'verif'}
    links = {c.id: sorted(set(index.incoming('verifies', c.id)) & eligible) for c in clauses}
    links = {cid: values for cid, values in links.items() if values}
    layers = list(config.get('layers', ['L0', 'L1', 'L2', 'L3']))
    contract_layer = layers[1] if len(layers) > 1 else None
    must = [c.id for c in clauses if c.active() and contract_layer is not None
            and c.meta.get('layer') == contract_layer and c.meta.get('level') == 'must'
            and c.meta.get('kind') != 'info']
    metrics = {c.id: census(c) for c in clauses}
    result = {'contract_layer': contract_layer, 'L1_must': len(must),
              'linked': sum(cid in links for cid in must),
              'unverified': sorted(cid for cid in must if cid not in links),
              'verification_links': links,
              'open_questions': [c.id for c in clauses if metrics[c.id]['open_questions']],
              'TBD': [c.id for c in clauses if metrics[c.id]['TBD_level'] or metrics[c.id]['TBD_markers']],
              'open_options': [c.id for c in clauses if metrics[c.id]['open_options']],
              'inline_DSE': sum(m['inline_DSE'] for m in metrics.values()),
              'conflicts': [{'id': c.id, 'with': target} for c in clauses if c.active()
                            for kind, target in sorted(index.typed(c.id)) if kind == 'conflicts-with'],
              'note': 'Links measure specified coverage, not implemented or passing tests.'}
    if include_questions:
        result['questions'] = [{'id': c.id, 'status': c.meta.get('status', 'open'),
              'blocks': [target for kind, target in sorted(index.typed(c.id)) if kind == 'blocks'],
              'resolution': c.resolution(), 'body': c.body}
              for c in clauses if c.meta.get('kind') == 'question']
    return result


def options(index):
    return [{**c.meta, 'id': c.id} for c in index.clauses if c.meta.get('kind') == 'option']


def dependencies(index, path='refs/'):
    prefix = relative_path(path)
    if prefix is None:
        raise ValueError('dependency path must be relative to the spec root')
    external = {c.id for c in index.clauses if prefix == '.' or c.path == prefix or c.path.startswith(prefix + '/')}
    rows = {(c.id, kind, target) for c in index.clauses if c.id not in external
            for kind, target in index.edges(c.id, fallback=False) if target in external}
    return [{'id': cid, 'target': target, 'type': kind, 'origin': index.by_id[target].meta.get('origin')}
            for cid, kind, target in sorted(rows)]
