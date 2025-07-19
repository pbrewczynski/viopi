# viopi_utils.py

import os
from pathlib import Path
from pathspec import PathSpec # Import for type hinting

def get_file_list(
    root_dir: str,
    patterns: list[str],
    follow_links: bool,
    ignore_spec: PathSpec
) -> tuple[list[str], int]:
    """
    Finds all files matching patterns, respecting an ignore spec.

    Returns:
        A tuple containing (list of files to include, count of ignored files).
    """
    root_path = Path(root_dir)
    included_files = set()
    ignored_count = 0

    if not patterns:
        patterns = ["**/*"]  # Default to all files if no pattern is given

    # Use os.walk to respect follow_links
    for dirpath, dirnames, filenames in os.walk(root_dir, followlinks=follow_links):
        # Create a list of full paths for checking against ignore spec
        all_paths_in_dir = [Path(dirpath) / name for name in dirnames + filenames]

        # Check paths relative to the root where .viopi_ignore was found
        ignored_paths = set(ignore_spec.match_files(
            [p.relative_to(root_path) for p in all_paths_in_dir]
        ))
        
        # Prune ignored directories from traversal
        dirnames[:] = [
            d for d in dirnames if str(Path(d)) not in ignored_paths
        ]

        for filename in filenames:
            file_path = Path(dirpath) / filename
            relative_file_path = file_path.relative_to(root_path)

            if str(relative_file_path) in ignored_paths:
                ignored_count += 1
                continue

            # Check if the non-ignored file matches any of the user's glob patterns
            if any(file_path.match(p) for p in patterns):
                included_files.add(str(file_path.resolve()))
    
    return sorted(list(included_files)), ignored_count


def generate_tree_output(root_dir: str, file_list: list[str]) -> str:
    """
    Generates a string representing the file tree.
    (Your existing implementation can likely stay the same)
    """
    # This function is fine as-is.
    # A simple placeholder:
    tree_lines = ["--- File Tree ---"]
    root_path = Path(root_dir)
    for f in file_list:
        tree_lines.append(str(Path(f).relative_to(root_path)))
    return "\n".join(tree_lines)