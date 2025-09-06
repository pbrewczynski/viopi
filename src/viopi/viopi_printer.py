
# Handles all user-facing print statements and status reports.
import sys
from pathlib import Path

from . import viopi_utils

# Module-level configuration to control verbosity.
_SILENT_MODE = False

def configure(silent: bool = False):
    """
    Configure the printer's behavior.
    In silent mode, all non-essential output to stderr (warnings, info,
    stats, prompts) is suppressed. Fatal errors are still shown.
    """
    global _SILENT_MODE
    _SILENT_MODE = silent

def _print_stats(stats: dict):
    """Prints the formatted statistics block to stderr."""
    if _SILENT_MODE:
        return
    payload_size_str = viopi_utils.format_bytes(stats.get("payload_size_bytes", 0))

    print("-" * 20, file=sys.stderr)
    print("Viopi Run Statistics:", file=sys.stderr)
    print(f"  - Files Processed:  {stats.get('total_files', 0)}", file=sys.stderr)
    print(f"  - Files Ignored:    {stats.get('files_ignored', 0)}", file=sys.stderr)
    print(f"  - Total Lines:      {stats.get('total_lines', 0)}", file=sys.stderr)
    print(f"  - Total Characters: {stats.get('total_characters', 0)}", file=sys.stderr)
    if stats.get("total_chars_saved_minify", 0) > 0:
        saved_str = viopi_utils.format_bytes(stats.get("total_chars_saved_minify", 0))
        print(f"  - Minification Saved: {saved_str}", file=sys.stderr)
    print(f"  - Payload Size:     {payload_size_str}", file=sys.stderr)
    print("-" * 20, file=sys.stderr)

def print_success_copy(stats: dict):
    """Prints the success message and stats for clipboard copy to stderr."""
    if not _SILENT_MODE:
        print("Viopi output copied to clipboard.", file=sys.stderr)
    _print_stats(stats)

def print_success_file(stats: dict, filename: str):
    """Prints the success message and stats for file save to stderr."""
    if not _SILENT_MODE:
        print(f"Output saved to {filename}", file=sys.stderr)
    _print_stats(stats)

def print_success_append(stats: dict, filename: str):
    """Prints the success message and stats for file append to stderr."""
    if not _SILENT_MODE:
        print(f"Output appended to {filename}", file=sys.stderr)
    _print_stats(stats)

def print_info(message: str):
    """Prints a standard informational message to stderr."""
    if _SILENT_MODE:
        return
    print(f"Info: {message}", file=sys.stderr)

def prompt_to_ignore_huge_file(path: Path, size_bytes: int) -> bool:
    """
    Prompts the user about a large file and asks if it should be ignored.
    In silent mode, this does not prompt and returns False.
    """
    if _SILENT_MODE:
        return False

    size_str = viopi_utils.format_bytes(size_bytes)
    # Using stderr for prompts to not interfere with stdout piping
    print(f"\nWarning: File '{path.name}' is large ({size_str}).", file=sys.stderr)
    print(f"  Full path: {path}", file=sys.stderr)

    while True:
        try:
            # Default to 'N' for safety
            response = input("Add this file to .viopi_ignore and skip it? (y/N): ").lower().strip()
            if response in ['y', 'yes']:
                print("", file=sys.stderr) # Add a blank line for readability
                return True
            if response in ['n', 'no', '']: # Empty input defaults to No
                print("", file=sys.stderr)
                return False
            print("Please enter 'y' or 'n'.", file=sys.stderr)
        except EOFError: # Handle case where input stream is closed
            print("\nInput stream closed. Defaulting to 'No'.", file=sys.stderr)
            return False

def print_error(message: str, is_fatal: bool = True):
    """Prints a formatted error message. Non-fatal errors are suppressed in silent mode."""
    if _SILENT_MODE and not is_fatal:
        return
    print(f"Error: {message}", file=sys.stderr)
    if is_fatal:
        sys.exit(1)

def print_warning(message: str):
    """Prints a formatted warning message. Suppressed in silent mode."""
    if _SILENT_MODE:
        return
    print(f"Warning: {message}", file=sys.stderr)
