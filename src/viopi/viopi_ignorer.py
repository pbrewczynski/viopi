# viopi_ignorer.py
# Handles finding and parsing .viopi_ignore files.

from pathlib import Path
import pathspec

# Default patterns to always ignore
DEFAULT_IGNORE_PATTERNS = [
    ".git/",
    ".DS_Store",
    "__pycache__/",
    "*.pyc",
    ".venv/",
    "venv/",
    "node_modules/",
    "_viopi_output*.viopi", # Ignore our own output files
]

def find_ignore_file(start_path: Path) -> Path | None:
    """Searches for a .viopi_ignore file from start_path upwards."""
    current_dir = start_path.resolve()
    while current_dir != current_dir.parent: # Stop at filesystem root
        ignore_file = current_dir / '.viopi_ignore'
        if ignore_file.exists():
            return ignore_file
        current_dir = current_dir.parent
    return None

def get_ignore_spec(start_dir: str) -> pathspec.PathSpec:
    """
    Builds a pathspec.PathSpec object from default patterns and a .viopi_ignore file.
    
    Args:
        start_dir: The directory to start searching for .viopi_ignore.

    Returns:
        A PathSpec object that can be used to match files.
    """
    start_path = Path(start_dir)
    patterns = list(DEFAULT_IGNORE_PATTERNS)

    ignore_file = find_ignore_file(start_path)
    if ignore_file:
        with open(ignore_file, 'r', encoding='utf-8') as f:
            patterns.extend(f.read().splitlines())

    # 'gitwildmatch' is the style used by .gitignore files
    return pathspec.PathSpec.from_lines('gitwildmatch', patterns)