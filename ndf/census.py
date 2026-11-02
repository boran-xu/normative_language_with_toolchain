"""One definition of active work, shared by coverage and historical deltas."""
from .markdown import visible


def census(clause):
    active = clause is not None and clause.active()
    meta = clause.meta if clause else {}
    body = visible(clause.body) if active else ''
    return {'TBD_markers': body.count('⟨TBD:'),
            'TBD_level': int(active and meta.get('level') == 'tbd' and meta.get('kind') != 'option'),
            'open_options': int(active and meta.get('kind') == 'option' and meta.get('level') == 'tbd'),
            'open_questions': int(active and meta.get('kind') == 'question' and meta.get('status', 'open') not in ('closed', 'resolved')),
            'inline_DSE': body.count('⟨DSE:')}
