"""Markdown structure comes from CommonMark tokens; NDF adds only wiki links."""
from functools import lru_cache
import re
from markdown_it import MarkdownIt

META = re.compile(r'^\s*<!--\s*ndf:\s*(.*?)\s*-->\s*$', re.S)


def _reference(state, silent):
    if not state.src.startswith('[[', state.pos):
        return False
    end = state.src.find(']]', state.pos + 2, state.posMax)
    if end < 0:
        return False
    content = state.src[state.pos + 2:end]
    target, _, label = content.partition('|')
    if not target.strip() or ']' in target:
        return False
    if not silent:
        token = state.push('ndf_reference', '', 0)
        token.content = content
        token.meta = {'target': target, 'label': label}
    state.pos = end + 2
    return True


_PARSER = MarkdownIt('commonmark', {'maxNesting': 100})
_PARSER.inline.ruler.before('link', 'ndf_reference', _reference)


def normalize_source(text):
    """Match CommonMark physical lines without rewriting Unicode separators."""
    return text.removeprefix('\ufeff').replace('\r\n', '\n').replace('\r', '\n')


def source_lines(text):
    return normalize_source(text).split('\n')


@lru_cache(maxsize=256)
def tokens(text):
    # Consumers read tokens only. Caching avoids reparsing unchanged Git blobs.
    return _PARSER.parse(normalize_source(text))


def inline_text(token, title=False, *, images=True, code=False):
    parts = []
    for child in token.children or []:
        if child.type in ('text', 'text_special'):
            parts.append(child.content)
        elif child.type in ('softbreak', 'hardbreak'):
            parts.append('\n')
        elif child.type == 'ndf_reference':
            parts.append('[[' + child.content + ']]')
        elif (title or code) and child.type == 'code_inline':
            parts.append(child.markup + child.content + child.markup)
        elif title and child.type in ('em_open', 'em_close', 'strong_open', 'strong_close'):
            parts.append(child.markup)
        elif child.type == 'html_inline' and not child.content.startswith('<!--'):
            # Tags are syntax; only their text contents participate in prose.
            continue
        elif child.type == 'image' and images:
            parts.append(inline_text(child, title=title, code=code))
    return ''.join(parts)


def inlines(text):
    for token in tokens(text):
        if token.type == 'inline':
            yield token
        elif token.type == 'html_block' and token.content.lstrip().startswith('<!--'):
            # A comment's closing line can also carry ordinary NDF prose.
            tail = re.sub(r'<!--.*?-->', '', token.content, flags=re.S)
            if tail.strip() and '<!--' not in tail:
                yield from _PARSER.parseInline(tail)


def visible(text, keep_metadata=False):
    parts = [inline_text(token) for token in inlines(text)]
    if keep_metadata:
        parts.extend(token.content for token in tokens(text)
                     if token.type == 'html_block' and META.fullmatch(token.content))
    return '\n'.join(parts)


def inline_children(token):
    for child in token.children or []:
        yield child
        if child.type == 'image':
            yield from inline_children(child)


def references(text):
    return [child.meta['target'] for token in inlines(text)
            for child in inline_children(token) if child.type == 'ndf_reference']


def resolution(text):
    """Read a real top-level prose field, excluding quotes/lists/code/comments."""
    for token in tokens(text):
        if token.type != 'inline' or token.level != 1:
            continue
        value = inline_text(token, images=False, code=True)
        match = re.search(r'^Resolution[.:][ \t]*(\S[^\n]*)$', value, flags=re.I | re.M)
        if match:
            return match[1].strip()
    return None
