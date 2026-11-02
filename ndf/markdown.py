"""Conservative Markdown visibility helpers used by structural checks.

Masks preserve offsets/newlines so parser locations always refer to source text.
"""
import re

FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})([^\r\n]*)[\r\n]*$')
META = re.compile(r'^\s*<!--\s*ndf:\s*(.*?)\s*-->\s*$', re.S)


def blank(text):
    return ''.join('\n' if char == '\n' else '\r' if char == '\r' else ' ' for char in text)


def without_inline_code(text):
    return re.sub(r'(?<!`)(`+)(?!`)(.*?)\1(?!`)', lambda m: blank(m[0]), text, flags=re.S)


def visible(text, keep_metadata=False):
    """Mask fenced/indented code, HTML comments and multiline code spans."""
    output, fence, comment = [], None, False
    inline_lines = without_inline_code(text).splitlines(keepends=True)
    for line, inline_line in zip(text.splitlines(keepends=True), inline_lines):
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
            output.append(blank(line))
            continue
        if not comment:
            if line.startswith(('    ', '\t')):
                output.append(blank(line))
                continue
            if marker and not (marker[1][0] == '`' and '`' in marker[2]):
                fence = marker[1][0], len(marker[1])
                output.append(blank(line))
                continue
            if keep_metadata and META.fullmatch(line):
                output.append(line)
                continue
        position, parts = 0, []
        while position < len(line):
            if comment:
                end = line.find('-->', position)
                stop = len(line) if end == -1 else end + 3
                parts.append(blank(line[position:stop]))
                comment = end == -1
            else:
                start = line.find('<!--', position)
                while start != -1 and inline_line[start:start + 4] != '<!--':
                    start = line.find('<!--', start + 4)
                if start == -1:
                    parts.append(line[position:])
                    break
                parts.append(line[position:start])
                stop = start + 4
                parts.append(blank(line[start:stop]))
                comment = True
            position = stop
        output.append(''.join(parts))
    return without_inline_code(''.join(output))


def references(text):
    result = []
    text = visible(text)
    for match in re.finditer(r'\[\[([^]|]+)(?:\|[^]]*)?\]\]', text):
        offset = match.start()
        escapes = 0
        while offset > 0 and text[offset - 1] == '\\':
            escapes += 1
            offset -= 1
        if escapes % 2 == 0:
            result.append(match[1])
    return result
