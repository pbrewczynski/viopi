
"""
viopi_ignorer.py
Handles finding and parsing .viopi_ignore files with git-like layering.
Provides optional annotated / colored output of the combined ignore spec.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

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

# ANSI color codes for pretty output (can be disabled by stripping)
ANSI = {
    "cyan": "\033[36m",
    "magenta": "\033[35m",
    "yellow": "\033[33m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}


@dataclass
class IgnorePattern:
    """Represents a single ignore pattern and its source file."""
    pattern: str
    source: str  # e.g. 'default', '/home/user/.viopi_ignore_global', '/repo/.viopi_ignore'


def _find_git_root(start_path: Path) -> Path | None:
    """
    Traverse upward from start_path to locate a directory containing a .git folder.
    Returns the Path if found, else None.
    """
    current_dir = start_path.resolve()
    while current_dir.parent != current_dir:
        if (current_dir / ".git").is_dir():
            return current_dir
        current_dir = current_dir.parent
    # Check the filesystem root as well
    if (current_dir / ".git").is_dir():
        return current_dir
    return None


def get_ignore_config(
    start_dir: str,
    return_annotated: bool = False
) -> tuple[pathspec.PathSpec, Path] | tuple[pathspec.PathSpec, Path, list[IgnorePattern]]:
    """
    Build the combined ignore PathSpec plus the root path for path matching.

    Args:
        start_dir: Directory where operation starts.
        return_annotated: If True, also return a list of IgnorePattern with provenance.

    Returns:
        A tuple of (spec, root) or (spec, root, annotated_list) if return_annotated is True.
    """
    start_path = Path(start_dir).resolve()

    # Anchor root: git repo root if present, otherwise start_dir
    project_root = _find_git_root(start_path) or start_path

    annotated: list[IgnorePattern] = []

    # 1. Defaults
    for p in DEFAULT_IGNORE_PATTERNS:
        annotated.append(IgnorePattern(p, "default"))

    # 2. Global ignore (~/.viopi_ignore_global)
    global_ignore_path = Path.home() / GLOBAL_IGNORE_FILENAME
    if global_ignore_path.is_file():
        with open(global_ignore_path, "r", encoding="utf-8") as f:
            for line in f.read().splitlines():
                annotated.append(IgnorePattern(line, str(global_ignore_path)))

    # 3. Collect project-level .viopi_ignore files from project_root down to start_path
    # We walk upward from start_path to project_root, storing any ignore files encountered.
    path_iterator = start_path
    ignore_files_to_read: list[Path] = []
    while True:
        ignore_file = path_iterator / REPO_IGNORE_FILENAME
        if ignore_file.is_file():
            ignore_files_to_read.append(ignore_file)
        if path_iterator == project_root or path_iterator.parent == path_iterator:
            break
        path_iterator = path_iterator.parent

    # We want parent-most first for correct precedence, so reverse the collected list.
    for file_path in reversed(ignore_files_to_read):
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f.read().splitlines():
                annotated.append(IgnorePattern(line, str(file_path)))

    # Combine all patterns (raw; may include blanks/comments)
    all_patterns = [ip.pattern for ip in annotated]

    # Build PathSpec (gitwildmatch semantics handles comments and empty lines)
    spec = pathspec.PathSpec.from_lines("gitwildmatch", all_patterns)

    if return_annotated:
        # We need to cast here because the function signature has an overload-like union.
        # The caller expects a 3-tuple when return_annotated is True.
        return spec, project_root, annotated
    return spec, project_root


def format_combined_ignore(annotated: list[IgnorePattern], color: bool = True) -> str:
    """
    Produce a human-friendly listing of the effective ignore patterns with their source.
    Duplicates (same pattern string encountered later) are summarized at the bottom.

    Args:
        annotated: List of IgnorePattern entries in order encountered.
        color: Toggle ANSI colors.

    Returns:
        A string suitable for printing.
    """
    seen = set()
    lines: list[str] = []
    duplicate_block: list[str] = []

    def c(code: str) -> str:
        # Gracefully handle missing color codes and the color=False flag
        return ANSI.get(code, "") if color else ""

    for ip in annotated:
        # Strip whitespace to treat "  foo  " and "foo" as the same pattern.
        pat = ip.pattern.strip()
        if not pat or pat.startswith("#"):  # Skip empty or pure comment lines
            continue

        # Source-based color choice
        if ip.source == "default":
            color_code = "cyan"
        elif ip.source.endswith(GLOBAL_IGNORE_FILENAME):
            color_code = "magenta"
        else:
            color_code = "yellow"

        if pat in seen:
            duplicate_block.append(pat)
            continue

        seen.add(pat)
        # Pattern line + provenance comment
        lines.append(f"{c(color_code)}{pat}{c('reset')} {c('dim')}# {ip.source}{c('reset')}")

    if duplicate_block:
        lines.append("")
        lines.append(f"{c('dim')}# Duplicates omitted (later occurrences):{c('reset')}")
        # List each unique duplicate pattern only once.
        for d in sorted(set(duplicate_block)):
            lines.append(f"{c('dim')}{d}{c('reset')}")

    return "\n".join(lines)


def get_formatted_ignore_listing(start_dir: str, color: bool = True) -> str:
    """
    Convenience wrapper: build config with annotations and format immediately.

    Args:
        start_dir: Starting directory for resolution.
        color: Whether to use ANSI colors.

    Returns:
        Formatted multi-line string.
    """
    # We know we get 3 items back because we pass return_annotated=True
    result = get_ignore_config(start_dir, return_annotated=True)
    _, _, annotated = result
    return format_combined_ignore(annotated, color=color)


# If run directly: show listing for current directory
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Show combined viopi ignore patterns (debug helper)."
    )
    parser.add_argument("path", nargs="?", default=".", help="Start directory (default: .)")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors.")
    args = parser.parse_args()

    try:
        listing = get_formatted_ignore_listing(args.path, color=not args.no_color)
        print(listing)
    except Exception as e:
        print(f"Error generating ignore listing: {e}", file=sys.stderr)
        sys.exit(1)
