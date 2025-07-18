#!/usr/bin/env python3
#
# viopi: A powerful tool for preparing project context for LLMs.
#

import sys
from pathlib import Path

# --- Local Module Imports ---
from . import viopi_utils
from . import viopi_version
from . import viopi_help

# --- Constants ---
OUTPUT_BASENAME = "_viopi_output"
OUTPUT_EXTENSION = ".viopi"
APPEND_FILENAME = f"{OUTPUT_BASENAME}{OUTPUT_EXTENSION}"

# --- Dependency Handling ---
try:
    from .viopi_utils import generate_project_context
except ImportError:
    print("Error: The 'viopi_utils.py' module was not found.", file=sys.stderr)
    print("Please make sure it's in the same directory or the package is installed correctly.", file=sys.stderr)
    sys.exit(1)

# --- Git Repository Detection ---
def find_git_root(start_path: Path) -> Path | None:
    """
    Finds the root of a Git repository by traversing up from start_path.
    Returns the repository's root path or None if not in a Git repo.
    """
    current_path = start_path.resolve()
    while True:
        if (current_path / '.git').is_dir():
            return current_path
        if current_path.parent == current_path:
            return None
        current_path = current_path.parent

def get_next_output_filename(basename: str, extension: str) -> str:
    """Finds the next available versioned filename."""
    counter = 1
    while True:
        versioned_path = Path(f"{basename}_{counter}{extension}")
        if not versioned_path.exists():
            return str(versioned_path)
        counter += 1

def print_output_stats(output_string: str):
    """Calculates and prints output statistics."""
    lines = len(output_string.splitlines())
    chars = len(output_string)
    print(f"📊 Stats: {lines:,} lines, {chars:,} characters.", file=sys.stderr)

def main():
    """Parses arguments, calls the core logic, and handles the final output."""
    args = sys.argv[1:]

    # --- Handle Help and Version Arguments First ---
    if "--help" in args or "-h" in args:
        # Delegate to the help module
        version_str = viopi_version.get_project_version()
        viopi_help.print_help_and_exit(
            version=version_str,
            basename=OUTPUT_BASENAME,
            extension=OUTPUT_EXTENSION,
            append_filename=APPEND_FILENAME
        )
    if "--version" in args or "-v" in args:
        # Delegate to the version module
        viopi_version.print_version_and_exit()

    # --- Determine Operational Mode ---
    stdout_mode = "--stdout" in args
    copy_mode = "--copy" in args
    append_mode = "--append" in args
    follow_links_mode = "--no-follow-links" not in args
    
    args = [arg for arg in args if not arg.startswith('--')]

    # --- Separate Path from Patterns ---
    path_args, pattern_args = [], []
    for arg in args:
        if Path(arg).is_dir():
            path_args.append(arg)
        else:
            pattern_args.append(arg)

    if len(path_args) > 1:
        print(f"⚠️  Warning: Multiple directory paths provided. Using the first one: '{path_args[0]}'", file=sys.stderr)

    start_dir = Path(path_args[0]).resolve() if path_args else Path.cwd().resolve()
    
    # --- Set Processing Root (GIT-AWARE) ---
    processing_root = start_dir
    git_root = find_git_root(start_dir)
    if git_root:
        print(f"✅ Git repository detected. Scanning from root: {git_root}", file=sys.stderr)
        processing_root = git_root

    # --- Run Core Logic ---
    print(f"🚀 Processing from: {processing_root}", file=sys.stderr)
    link_status = "enabled" if follow_links_mode else "disabled"
    print(f"ℹ️  Symbolic link following is {link_status}.", file=sys.stderr)

    final_output, summary_report = viopi_utils.generate_project_context(
        processing_root,
        pattern_args,
        follow_links=follow_links_mode
    )
    print(summary_report, file=sys.stderr)

    # --- Handle Final Output ---
    if stdout_mode:
        print(final_output)
        print(f"\n✅ Done. Output sent to stdout.", file=sys.stderr)
    elif copy_mode:
        try:
            import pyperclip
            pyperclip.copy(final_output)
            print(f"\n✅ Combined contents copied to the clipboard.", file=sys.stderr)
        except (ImportError, pyperclip.PyperclipException):
            print("\n❌ Error: Could not copy to clipboard. 'pyperclip' may not be installed.", file=sys.stderr)
            sys.exit(1)
    elif append_mode:
        try:
            append_target = Path(APPEND_FILENAME)
            content_to_write = f"\n{final_output}" if append_target.exists() and append_target.stat().st_size > 0 else final_output
            with open(append_target, "a", encoding="utf-8") as f:
                f.write(content_to_write)
            print(f"\n✅ Combined contents Appended to file: {append_target.resolve()}", file=sys.stderr)
        except IOError as e:
            print(f"\n❌ Error: Could not append to file '{APPEND_FILENAME}'.\n   Details: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            output_filename = get_next_output_filename(OUTPUT_BASENAME, OUTPUT_EXTENSION)
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(final_output)
            print(f"\n✅ Combined contents Saved to new file: {Path(output_filename).resolve()}", file=sys.stderr)
        except IOError as e:
            print(f"\n❌ Error: Could not write to file '{output_filename}'.\n   Details: {e}", file=sys.stderr)
            sys.exit(1)

    print_output_stats(final_output)

if __name__ == "__main__":
    main()