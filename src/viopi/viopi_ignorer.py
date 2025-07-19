# viopi_ignorer.py
# Handles finding and parsing .viopi_ignore files with git-like behavior.

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
    "*.viopi",  # Ignore all viopi output files
]
GLOBAL_IGNORE_FILENAME = ".viopi_ignore_global"
REPO_IGNORE_FILENAME = ".viopi_ignore"

def _find_git_root(start_path: Path) -> Path | None:
    """Traverses up from start_path to find the git repository root (.git)."""
    current_dir = start_path.resolve()
    while current_dir.parent != current_dir:  # Stop at the filesystem root
        if (current_dir / '.git').is_dir():
            return current_dir
        current_dir = current_dir.parent
    # Check the root directory itself
    if (current_dir / '.git').is_dir():
        return current_dir
    return None

def get_ignore_config(start_dir: str) -> tuple[pathspec.PathSpec, Path]:
    """
    Builds a PathSpec object and determines the root for path matching.
    
    Args:
        start_dir: The directory where the operation starts.

    Returns:
        A tuple containing:
        - A PathSpec object for matching files.
        - The Path object of the root directory against which paths should be matched.
    """
    start_path = Path(start_dir).resolve()
    
    # Use git root if available, otherwise the start dir. This is our anchor.
    project_root = _find_git_root(start_path) or start_path

    # 1. Start with default patterns
    all_patterns = list(DEFAULT_IGNORE_PATTERNS)

    # 2. Add patterns from the global ignore file
    global_ignore_path = Path.home() / GLOBAL_IGNORE_FILENAME
    if global_ignore_path.is_file():
        with open(global_ignore_path, 'r', encoding='utf-8') as f:
            all_patterns.extend(f.read().splitlines())

    # 3. Collect all .viopi_ignore files from the project root down to the start path
    path_iterator = start_path
    ignore_files_to_read = []
    while True:
        ignore_file = path_iterator / REPO_IGNORE_FILENAME
        if ignore_file.is_file():
            ignore_files_to_read.append(ignore_file)
        
        if path_iterator == project_root or path_iterator.parent == path_iterator:
            break
        path_iterator = path_iterator.parent
    
    # Read files from parent -> child (by reversing the list)
    for file_path in reversed(ignore_files_to_read):
        with open(file_path, 'r', encoding='utf-8') as f:
            all_patterns.extend(f.read().splitlines())

    spec = pathspec.PathSpec.from_lines('gitwildmatch', all_patterns)
    return spec, project_root