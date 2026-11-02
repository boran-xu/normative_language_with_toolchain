"""Advisory terminology checks on ordinary prose; no semantic inference."""
import re
from .markdown import visible, tokens

WORDS = re.compile(r'[A-Za-z][A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)*')
IGNORED = set('MUST SHALL SHOULD MAY NOT TBD DSE TODO The A An When If Then Each Every All Any No On In At By For From To With Without While After Before This That These Those It Its See As And Or But Given Unless Whether'.split())


def prose(text, keep_emphasis=False):
    """Remove fenced/inline code, metadata, destinations and ID references."""
    value = visible(text)
    value = re.sub(r'\[\[[^]]*\]\]', '', value)
    value = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', value)
    return value if keep_emphasis else value.replace('**', '').replace('__', '')


def vocabulary(clauses, config):
    terms, synonyms = set(), {}
    for c in clauses:
        if c.meta.get('kind') != 'def':
            continue
        # A definition may name its term in the heading, or define several
        # bold terms in a list, as in the proposal's worked example.
        title = c.title.strip('*_ ')
        terms.add(title.casefold())
        for block in tokens(c.body):
            children = [child for child in block.children or [] if child.type != 'text' or child.content]
            if block.type != 'inline' or not children or children[0].type != 'strong_open':
                continue
            end = next((i for i, child in enumerate(children) if child.type == 'strong_close'), None)
            if end is None:
                continue
            tail = ''.join(child.content for child in children[end + 1:])
            if re.match(r'^\s*(?:[—–:]|-\s)', tail):
                term = ''.join(child.content for child in children[1:end])
                terms.update(value.strip().casefold() for value in term.split('/'))
        for term in re.findall(r'(?:^|[.!?]\s+)(?:[Aa]n? |[Tt]he )?([A-Za-z][A-Za-z /-]*?)\s+(?:means|is defined as|refers to)\s', prose(c.body)):
            terms.add(term.strip().casefold())
        # Explicit aliases in a definition's prose, not a new reference syntax.
        for aliases in re.findall(r'(?im)^\s*(?:[-*]\s+)?(?:\*\*)?(?:synonyms|aliases)(?:\*\*)?\s*:\s*(.+)$', prose(c.body)):
            for alias in aliases.split(','):
                alias = alias.strip().strip('*_` ')
                if alias:
                    synonyms[alias.casefold()] = title
    glossary = config.get('glossary', {})
    if not isinstance(glossary, dict) or not isinstance(glossary.get('synonyms', {}), dict):
        raise ValueError('glossary.synonyms must be a mapping of synonym to preferred term')
    for alias, preferred in glossary.get('synonyms', {}).items():
        if not isinstance(alias, str) or not isinstance(preferred, str) or not alias.strip() or not preferred.strip():
            raise ValueError('glossary synonyms require nonempty string terms')
        synonyms[alias.strip().casefold()] = preferred.strip()
    return terms, synonyms


def warnings(clauses, config):
    terms, synonyms = vocabulary(clauses, config)
    result = []
    for c in clauses:
        if c.meta.get('kind') == 'def':
            continue
        text = re.sub(r'(?m)^\s*(?:Context|Decision|Rationale|Alternatives rejected|Source|Question|Resolution)[.:]\s*', '', prose(c.body))
        loc = f'{c.path}:{c.line} {c.id}'
        for alias, preferred in sorted(synonyms.items()):
            if re.search(r'(?<!\w)' + r'\s+'.join(re.escape(word) for word in alias.split()) + r'(?!\w)', text, re.I):
                result.append(f'{loc}: inconsistent synonym "{alias}"; prefer "{preferred}"')
        # Mask defined phrases before capitalized-word detection, so a known
        # multiword term does not produce warnings for its individual words.
        for term in sorted(terms | set(synonyms), key=lambda term: (-len(term), term)):
            text = re.sub(r'(?<!\w)' + r'\s+'.join(re.escape(word) for word in term.split()) + r'(?!\w)', '', text, flags=re.I)
        candidates = set()
        for match in WORDS.finditer(text):
            word = match[0]
            prefix = text[:match.start()]
            sentence_start = not prefix.strip() or bool(re.search(r'[.!?]\s+$|\n\s*(?:[-*]\s+)?$', prefix))
            # Sentence capitalization alone is not evidence of a term of art.
            if word[0].isupper() and word not in IGNORED and (word.isupper() or not sentence_start):
                candidates.add(word)
        for word in sorted(candidates):
            result.append(f'{loc}: undefined capitalized term "{word}" (glossary advisory)')
    return result
