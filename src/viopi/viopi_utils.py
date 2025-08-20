# viopi_utils.py
import os
from pathlib import Path
from pathspec import PathSpec
from collections import deque


def format_bytes(size_bytes: int, precision: int = 2) -> str:
    """Converts a size in bytes to a human-readable string (KB, MB, etc.)."""
    if size_bytes == 0:
        return "0 B"
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    power = 1024
    i = 0
    while size_bytes >= power and i < len(units) - 1:
        size_bytes /= power
        i += 1
    return f"{size_bytes:.{precision}f} {units[i]}"


def is_binary_file(filepath: str, chunk_size: int = 1024) -> bool:
    """
    Heuristically determines if a file is binary by checking for null bytes
    in the first chunk of the file.
    """
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(chunk_size)
        return b'\x00' in chunk
    except (IOError, FileNotFoundError):
        return False


def get_file_list(
    scan_dir: str,
    patterns: list[str],
    follow_links: bool,
    ignore_spec: PathSpec,
    ignore_root: Path
) -> tuple[list[tuple[str, str, bool]], int]:
    """
    Finds all files matching patterns, respecting an ignore spec.
    Handles symbolic links by tracking both logical and physical paths.

    Returns:
        A tuple containing:
        - A list of (absolute_physical_path, logical_path_relative_to_scan_dir, is_symlink_flag) tuples.
        - The total number of files and directories that were ignored.
    """
    scan_path = Path(scan_dir).resolve()
    
    if not patterns:
        patterns = ["**/*"]

    # List of (physical_path: Path, logical_path_relative_to_scan_dir: Path, is_symlink: bool)
    all_files_found = []
    
    # Queue for BFS. Tuples are (physical_path: Path, logical_path_relative_to_scan_dir: Path)
    queue = deque([(scan_path, Path('.'))])

    visited_physical_paths = set()
    ignored_count = 0

    while queue:
        physical_dir, logical_dir_rel_to_scan_dir = queue.popleft()

        try:
            real_physical_dir = physical_dir.resolve()
            if real_physical_dir in visited_physical_paths:
                continue
            visited_physical_paths.add(real_physical_dir)
        except (FileNotFoundError, RuntimeError):
            ignored_count += 1
            continue

        # For pathspec, we need path relative to the ignore_root.
        path_of_scan_dir_rel_to_ignore_root = scan_path.relative_to(ignore_root)
        logical_dir_rel_to_ignore_root = path_of_scan_dir_rel_to_ignore_root / logical_dir_rel_to_scan_dir

        try:
            for entry in os.scandir(physical_dir):
                entry_physical_path = Path(entry.path)
                entry_logical_path_rel_to_scan_dir = logical_dir_rel_to_scan_dir / entry.name
                entry_logical_path_rel_to_ignore_root = logical_dir_rel_to_ignore_root / entry.name
                is_symlink = entry.is_symlink()

                path_to_check = str(entry_logical_path_rel_to_ignore_root)
                is_dir_like = entry.is_dir(follow_symlinks=False) or \
                              (follow_links and is_symlink and entry_physical_path.is_dir())
                if is_dir_like:
                    path_to_check += '/'

                if ignore_spec.match_file(path_to_check):
                    ignored_count += 1
                    continue
                
                if entry.is_dir(follow_symlinks=False):
                    queue.append((entry_physical_path, entry_logical_path_rel_to_scan_dir))
                elif entry.is_file(follow_symlinks=False):
                    all_files_found.append((entry_physical_path, entry_logical_path_rel_to_scan_dir, False))
                elif follow_links and is_symlink:
                    try:
                        if entry_physical_path.is_dir():
                            queue.append((entry_physical_path, entry_logical_path_rel_to_scan_dir))
                        elif entry_physical_path.is_file():
                            all_files_found.append((entry_physical_path, entry_logical_path_rel_to_scan_dir, True))
                    except (FileNotFoundError, OSError):
                        ignored_count += 1
                        continue
        except OSError:
            ignored_count += 1
            continue
    
    included_files = []
    for physical_path, logical_path_rel_to_scan_dir, is_symlink in all_files_found:
        if any(physical_path.match(p) for p in patterns):
            included_files.append(
                (str(physical_path.resolve()), str(logical_path_rel_to_scan_dir), is_symlink)
            )

    final_ignored_count = ignored_count + (len(all_files_found) - len(included_files))

    included_files.sort(key=lambda x: x[1])
    
    return included_files, final_ignored_count


def generate_tree_output(logical_path_info_list: list[tuple[str, bool]]) -> str:
    """
    Generates a string representing the file tree from a list of logical paths.
    """
    tree_lines = ["--- File Tree ---"]
    for path, is_symlink in sorted(logical_path_info_list, key=lambda x: x[0]):
        line = path
        if is_symlink:
            line += " -> [symbolic link]"
        tree_lines.append(line)
    return "\n".join(tree_lines)