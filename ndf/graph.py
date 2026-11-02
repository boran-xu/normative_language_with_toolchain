"""Cycle-safe traversal of typed clause relationships."""

def trace(clauses, start):
    index = {c.id: c for c in clauses}
    if start not in index:
        raise ValueError('unknown clause ' + start)
    children, verifiers = {}, {}
    for c in clauses:
        for kind, target in c.edges():
            if kind == 'refines':
                children.setdefault(target, []).append(c.id)
            elif kind == 'verifies':
                verifiers.setdefault(target, []).append(c.id)
    rows, seen = [], set()
    # Iterative DFS avoids recursion limits for large dependency graphs.
    pending = [(start, 0, None, None)]
    while pending:
        cid, depth, source, relation = pending.pop()
        c = index[cid]
        repeated = cid in seen
        rows.append({'id': cid, 'layer': c.meta.get('layer'), 'title': c.title,
                     'depth': depth, 'source': source, 'relation': relation,
                     'repeated': repeated, 'verified_by': sorted(verifiers.get(cid, [])),
                     'edges': [{'type': k, 'target': t} for k, t in c.edges()]})
        if repeated:
            continue
        seen.add(cid)
        successors = [('refined-by', child) for child in children.get(cid, [])]
        successors += [('depends-on', target) for kind, target in c.edges() if kind == 'depends-on']
        for kind, target in reversed(sorted(set(successors))):
            pending.append((target, depth + 1, cid, kind))
    return rows


def render_trace(rows):
    lines = []
    for row in rows:
        indent = '  ' * row['depth']
        relation = row['relation'] + ': ' if row['relation'] else ''
        suffix = ' (already shown)' if row['repeated'] else ''
        lines.append(f'{indent}{relation}{row["id"]} [{row["layer"] or "-"}] {row["title"]}{suffix}')
        if not row['repeated']:
            for verifier in row['verified_by']:
                lines.append(indent + '  verified-by: ' + verifier)
            for edge in row['edges']:
                if edge['type'] not in ('depends-on', 'refines'):
                    lines.append(indent + f'  {edge["type"]}: {edge["target"]}')
    return lines
