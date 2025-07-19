# viopi_utils.py
import os
from pathlib import Path
from pathspec import PathSpec

def get_file_list(
    scan_dir: str,
    patterns: list[str],
    follow_links: bool,
    ignore_spec: PathSpec,
    ignore_root: Path
) -> tuple[list[str], int]:
    """
    Finds all files matching patterns, respecting an ignore spec relative to the ignore_root.
    """
    scan_path = Path(scan_dir).resolve()
    included_files = set()
    
    if not patterns:
        patterns = ["**/*"]  # Default to all files if no pattern is given

    # First, collect all file paths from the scan directory
    all_found_files = []
    for dirpath, _, filenames in os.walk(scan_path, followlinks=follow_links):
        for f in filenames:
            all_found_files.append(Path(dirpath) / f)

    # Get paths relative to the ignore_root for matching against the spec
    # This is the key step for git-like behavior
    relative_paths_for_spec = [str(p.relative_to(ignore_root)) for p in all_found_files]
    
    # Find which of those relative paths are ignored
    ignored_relative_paths = set(ignore_spec.match_files(relative_paths_for_spec))
    
    # Now, iterate through the original full paths and filter
    for full_path in all_found_files:
        relative_path_str = str(full_path.relative_to(ignore_root))
        
        if relative_path_str in ignored_relative_paths:
            continue

        # If not ignored, check if it matches the user's inclusion patterns
        if any(full_path.match(p) for p in patterns):
            included_files.add(str(full_path.resolve()))
    
    ignored_count = len(all_found_files) - len(included_files)
    
    return sorted(list(included_files)), ignored_count


def generate_tree_output(root_dir: str, file_list: list[str]) -> str:
    """
    Generates a string representing the file tree, relative to the scan directory.
    """
    tree_lines = ["--- File Tree ---"]
    root_path = Path(root_dir)
    paths_to_show = sorted([Path(f).relative_to(root_path) for f in file_list])
    for p in paths_to_show:
        tree_lines.append(str(p))
    return "\n".join(tree_lines)