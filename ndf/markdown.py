"""Small Markdown helpers shared by deterministic text checks."""
import re


def without_inline_code(text):
    return re.sub(r'(?<!`)(`+)(?!`)(.*?)\1(?!`)', '', text, flags=re.S)
