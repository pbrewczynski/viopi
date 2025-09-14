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
        return f"{size_kib:.2f} KiB"
    size_mib = size_kib / 1024
    if size_mib < 1024:
        return f"{size_mib:.2f} MiB"
    size_gib = size_mib / 1024
    return f"{size_gib:.2f} GiB"

def is_binary_file(filepath: str, chunk_size: int = 1024) -> bool:
    """
    Checks if a file is likely binary by reading a chunk and looking for null bytes.
    """
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(chunk_size)
        return b'\0' in chunk
    except IOError:
        return False # File cannot be read, treat as not binary for safety

def get_file_list(
    target_dir: str,
    patterns: List[str],
    follow_links: bool,
    ignore_spec: pathspec.PathSpec,
    ignore_root: Path,
) -> Tuple[List[Tuple[str, str, bool]], List[Tuple[str, str, bool]]]:
    """
    Walks the target directory to get a list of files, filtering based on
    ignore specs and glob patterns.
    """
    files_to_process = []
    ignored_files = []
    
    target_path = Path(target_dir).resolve()

    # Use PathSpec for pattern matching as well for consistency.
    pattern_spec = None
    if patterns:
        pattern_spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    all_files_in_walk = []
    for root, _, files in os.walk(target_dir, followlinks=follow_links):
        root_path = Path(root)
        for name in files:
            # Ensure we have a fully resolved path to avoid ambiguity
            all_files_in_walk.append((root_path / name).resolve())
    
    # Pathspec needs paths as strings, relative to the ignore_root, with POSIX separators.
    # This dictionary maps the full physical path to the relative path for the ignore check.
    paths_to_check_for_ignore = {
        p: p.relative_to(ignore_root).as_posix() for p in all_files_in_walk
    }
    
    # Get a set of all paths (as posix strings) that are ignored.
    ignored_paths_by_spec = set(ignore_spec.match_files(paths_to_check_for_ignore.values()))

    for physical_path in all_files_in_walk:
        path_for_ignore_check = paths_to_check_for_ignore[physical_path]

        # Logical path for display and pattern matching is relative to the target directory.
        logical_path_str = str(physical_path.relative_to(target_path))
        is_symlink = os.path.islink(physical_path) # Use os.path.islink for unresolved paths
        file_tuple = (str(physical_path), logical_path_str, is_symlink)

        # 1. Primary check: .viopi_ignore rules
        if path_for_ignore_check in ignored_paths_by_spec:
            ignored_files.append(file_tuple)
            continue

        # 2. Secondary check: CLI glob patterns (if provided)
        if pattern_spec:
            # Match patterns against the logical path
            if not pattern_spec.match_file(logical_path_str):
                ignored_files.append(file_tuple)
                continue
        
        files_to_process.append(file_tuple)

    return files_to_process, ignored_files

def generate_tree_output(items: List[Tuple[str, bool, bool]]) -> str:
    """
    Generates a visual tree structure from a list of file paths.
    items: list of (logical_path, is_symlink, is_ignored)
    """
    tree_dict = {}
    # Sort items by path parts to ensure correct ordering
    sorted_items = sorted(items, key=lambda x: Path(x[0]).parts)

    for path, is_symlink, is_ignored in sorted_items:
        parts = Path(path).parts
        current_level = tree_dict
        for part in parts[:-1]: # Iterate through directories
            current_level = current_level.setdefault(part, {})
        
        # Set file data at the final level
        filename = parts[-1]
        current_level[filename] = {'__meta__': {'is_symlink': is_symlink, 'is_ignored': is_ignored}}

    def build_tree_lines(d, prefix=""):
        lines = []
        # Sort keys to ensure consistent order: directories first, then files
        entries = sorted(d.keys(), key=lambda k: '__meta__' not in d[k])
        
        for i, name in enumerate(entries):
            content = d[name]
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(prefix + connector + name)
            
            if '__meta__' not in content: # It's a directory
                extension = "    " if i == len(entries) - 1 else "│   "
                lines.extend(build_tree_lines(content, prefix + extension))
        return lines

    tree_lines = build_tree_lines(tree_dict)
    header = "\n--- File Tree ---\n"
    return header + "\n".join(tree_lines) if tree_lines else ""