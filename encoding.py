from pathlib import Path

from charset_normalizer import from_path


def detect_and_read(path: Path) -> str:
    result = from_path(path).best()
    if result is None:
        raise ValueError(f"Could not detect encoding: {path}")
    return str(result)
