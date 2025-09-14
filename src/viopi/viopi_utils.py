import os
from pathlib import Path
from typing import List, Tuple
import pathspec

def format_bytes(size_bytes: int) -> str:
    """Formats a size in bytes into a human-readable string (KiB, MiB, etc.)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    size_kib = size_bytes / 1024
    if size_kib < 1024:
        return f"{size_kib:.1f} KiB"
    size_mib = size_kib / 1024
    if size_mib < 1024:
        return f"{size_mib:.1f} MiB"
    size_gib = size_mib / 1024
    return f"{size_gib:.1f} GiB"

def is_binary_file(file_path: str, chunk_size: int = 1024) -> bool:
    """Heuristically determines if a file is binary by checking for null bytes."""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(chunk_size)
        return b'\0' in chunk
    except IOError:
        return False

def get_file_list(
    target_dir: str,
    patterns: List[str],
    follow_links: bool,
    ignore_spec: pathspec.PathSpec,
    ignore_root: Path
) -> Tuple[List[Tuple[str, str, bool]], List[Tuple[str, str, bool]]]:
    """
    Walks the target directory to get a list of files, filtering by patterns and ignore rules.

    Returns two lists of tuples: (physical_path, logical_path, is_symlink)
    - The first list is for files to process.
    - The second list is for files that were ignored.
    """
    files_to_process = []
    ignored_files = []
    target_path = Path(target_dir)

    pattern_spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns) if patterns else None

    for root, dirs, files in os.walk(target_dir, followlinks=follow_links, topdown=True):
        root_path = Path(root)

        # The path for matching against ignore rules MUST be relative to the ignore_root.
        # This is the key fix for the user's issue.
        paths_for_ignore_check = [root_path.relative_to(ignore_root) / d for d in dirs]
        paths_for_ignore_check.extend(root_path.relative_to(ignore_root) / f for f in files)

        # pathspec can match directories, so we filter them from the `dirs` list in-place.
        # This prevents os.walk from descending into ignored directories.
        ignored_paths = ignore_spec.match_files(paths_for_ignore_check)
        ignored_dir_names = {p.name for p in ignored_paths if (ignore_root / p).is_dir()}
        dirs[:] = [d for d in dirs if d not in ignored_dir_names]

        for file_name in files:
            physical_path = root_path / file_name
            is_symlink = physical_path.is_symlink()
            
            # This path is used for the ignore check. It's relative to the project root.
            path_for_ignore = physical_path.relative_to(ignore_root)
            
            # This path is displayed to the user. It's relative to the command's target directory.
            logical_path = physical_path.relative_to(target_path)
            
            file_tuple = (str(physical_path), str(logical_path), is_symlink)

            # --- Filtering Logic ---
            # 1. Check against .viopi_ignore rules.
            if ignore_spec.match_file(str(path_for_ignore)):
                ignored_files.append(file_tuple)
                continue

            # 2. If user-provided patterns exist, check against them.
            if pattern_spec and not pattern_spec.match_file(str(logical_path)):
                ignored_files.append(file_tuple)
                continue
                
            files_to_process.append(file_tuple)

    files_to_process.sort(key=lambda x: x[1])
    ignored_files.sort(key=lambda x: x[1])
    
    return files_to_process, ignored_files

def generate_tree_output(items: List[Tuple[str, bool, bool]]) -> str:
    """
    Generates a file tree string from a list of paths and their status.
    'items' is a list of (path_str, is_symlink, is_ignored).
    """
    tree_dict = {}
    for path_str, is_symlink, is_ignored in items:
        # Attach metadata to the path for later lookup
        path_with_meta = f"{path_str}"
        if is_ignored:
            path_with_meta += " [ignored]"
        if is_symlink:
            path_with_meta += " -> [symbolic link]"
            
        parts = Path(path_str).parts
        current_level = tree_dict
        for part in parts:
            current_level = current_level.setdefault(part, {})
    
    # This is a simplified tree generator that lists the files.
    lines = ["--- File Tree ---"]
    for logical_path, is_symlink, is_ignored in sorted(items):
        line = "src/viopi/" + logical_path
        if is_symlink:
            line += " -> [symbolic link]"
        if is_ignored:
            line += " [ignored]"
        lines.append(line)
    return "\n".join(lines)