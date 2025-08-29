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
) -> tuple[list[tuple[str, str, bool]], list[tuple[str, str, bool]]]:
    """
    Walks the directory and classifies all files into 'included' or 'ignored'.
    'included': files not matching ignore spec AND matching user-provided glob patterns.
    'ignored': files matching ignore spec OR not matching user-provided glob patterns.

    Returns:
        A tuple of (included_files, ignored_files).
        Each list contains tuples of (absolute_physical_path, logical_path_relative_to_scan_dir, is_symlink_flag).
    """
    scan_path = Path(scan_dir).resolve()

    if not patterns:
        patterns = ["**/*"]

    included_files = []
    ignored_files = []

    queue = deque([(scan_path, Path('.'))])
    visited_physical_paths = set()

    while queue:
        physical_dir, logical_dir_rel_to_scan_dir = queue.popleft()

        try:
            real_physical_dir = physical_dir.resolve()
            if real_physical_dir in visited_physical_paths:
                continue
            visited_physical_paths.add(real_physical_dir)
        except (FileNotFoundError, RuntimeError):
            continue

        path_of_scan_dir_rel_to_ignore_root = scan_path.relative_to(ignore_root)

        try:
            for entry in sorted(os.scandir(physical_dir), key=lambda e: e.name):
                entry_physical_path = Path(entry.path)
                entry_logical_path_rel_to_scan_dir = logical_dir_rel_to_scan_dir / entry.name
                entry_logical_path_rel_to_ignore_root = path_of_scan_dir_rel_to_ignore_root / entry.name
                is_symlink = entry.is_symlink()

                is_dir = entry.is_dir(follow_symlinks=False)
                if follow_links and is_symlink and not is_dir:
                    try:
                        if entry_physical_path.is_dir():
                            is_dir = True
                    except (FileNotFoundError, OSError):
                        continue

                path_to_check = str(entry_logical_path_rel_to_ignore_root)
                if is_dir:
                    path_to_check += '/'

                is_ignored_by_spec = ignore_spec.match_file(path_to_check)

                if is_dir:
                    queue.append((entry_physical_path, entry_logical_path_rel_to_scan_dir))
                else:
                    try:
                        is_file = entry.is_file(follow_symlinks=False) or \
                                  (follow_links and is_symlink and entry_physical_path.is_file())
                        if not is_file:
                            continue
                    except (FileNotFoundError, OSError):
                        continue

                    file_tuple = (
                        str(entry_physical_path.resolve()), 
                        str(entry_logical_path_rel_to_scan_dir), 
                        is_symlink
                    )

                    if is_ignored_by_spec:
                        ignored_files.append(file_tuple)
                    else:
                        if any(entry_physical_path.match(p) for p in patterns):
                            included_files.append(file_tuple)
                        else:
                            ignored_files.append(file_tuple)
        except OSError:
            continue

    included_files.sort(key=lambda x: x[1])
    ignored_files.sort(key=lambda x: x[1])

    return included_files, ignored_files


def generate_tree_output(path_info_list: list[tuple]) -> str:
    """
    Generates a string representing the file tree from a list of path info tuples.
    Each tuple can be (path, is_symlink) or (path, is_symlink, is_ignored).
    """
    tree_lines = ["--- File Tree ---"]
    for item in sorted(path_info_list, key=lambda x: x[0]):
        path, is_symlink = item[0], item[1]
        is_ignored = item[2] if len(item) > 2 else False

        line = path

        markers = []
        if is_ignored:
            markers.append("ignored")
        if is_symlink:
            markers.append("symbolic link")

        if markers:
            line += f" -> [{', '.join(markers)}]"

        tree_lines.append(line)
    return "\n".join(tree_lines)