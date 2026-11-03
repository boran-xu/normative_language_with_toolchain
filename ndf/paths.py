"""The specification namespace always uses root-relative POSIX paths."""
from pathlib import PurePosixPath


def relative_path(path):
    rel = PurePosixPath(path)
    if rel.is_absolute() or '..' in rel.parts:
        return None
    return rel.as_posix()
