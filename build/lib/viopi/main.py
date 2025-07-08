#!/usr/bin/env python3
#
# viopi: A powerful tool for preparing project context for LLMs.
#
# This script is the main entry point for the 'viopi' command-line tool.
# It recursively finds text files, concatenates their contents, and handles
# output to a file, the clipboard, or stdout.
#
# It dynamically reads its version from the project's pyproject.toml.
#

import sys
from pathlib import Path
import importlib.metadata
from . import viopi_utils

# --- TOML Parsing (for development fallback) ---
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

# --- Constants ---
# Base name for versioned output files
OUTPUT_BASENAME = "_viopi_output"
OUTPUT_EXTENSION = ".viopi"
# Specific target for the --append flag
APPEND_FILENAME = f"{OUTPUT_BASENAME}{OUTPUT_EXTENSION}"

# --- Dependency Handling ---
try:
    from .viopi_utils import generate_project_context
except ImportError:
    print("Error: The 'viopi_utils.py' module was not found.", file=sys.stderr)
    print("Please make sure it's in the same directory or the package is installed correctly.", file=sys.stderr)
    sys.exit(1)
    

# --- Dynamic Version Loading ---
def get_project_version() -> str:
    """Retrieves the project version from package metadata or pyproject.toml."""
    try:
        return importlib.metadata.version("viopi")
    except importlib.metadata.PackageNotFoundError:
        if tomllib is None:
            return "0.0.0-dev (tomli not found)"
        try:
            current_dir = Path(__file__).resolve().parent
            while current_dir != current_dir.parent:
                pyproject_path = current_dir / 'pyproject.toml'
                if pyproject_path.exists():
                    with open(pyproject_path, "rb") as f:
                        data = tomllib.load(f)
                    return data.get("project", {}).get("version", "0.0.0-dev (version missing)")
                current_dir = current_dir.parent
            return "0.0.0-dev (pyproject.toml not found)"
        except Exception:
            return "0.0.0-dev (pyproject parse error)"

__version__ = get_project_version()




def get_next_output_filename(basename: str, extension: str) -> str:
    """
    Finds the next available versioned filename.
    Checks for `basename_1.ext`, `basename_2.ext`, etc.
    """
    counter = 1
    while True:
        versioned_path = Path(f"{basename}_{counter}{extension}")
        if not versioned_path.exists():
            return str(versioned_path)
        counter += 1

def print_help():
    """Prints the detailed help and usage message."""
    help_text = f"""
viopi v{__version__}
A tool for preparing project context for LLMs by concatenating files.

Usage:
  viopi [options] [path] [pattern_1] [pattern_2] ...

Default Behavior:
  Creates a new, versioned output file on each run (e.g., `{OUTPUT_BASENAME}_1.viopi`, 
  `{OUTPUT_BASENAME}_2.viopi`, etc.) to prevent accidental overwrites.

Options:
  -h, --help            Show this help message and exit.
  -v, --version         Show the version number and exit.
  
  --stdout              Print output to stdout instead of a file.
  --copy                Copy output to the system clipboard.
  
  --append              Appends output to the base file `{APPEND_FILENAME}`
                        instead of creating a new versioned file.
                        
  --no-follow-links     Disable following symbolic links.

Examples:
  # Process current directory, save to a new versioned file (e.g., _viopi_output_1.viopi)
  viopi

  # Append JS file contexts to the base _viopi_output.viopi file
  viopi --append src/app/ '**/*.js'

  # Pipe context to another tool
  viopi --stdout | llm -s "Summarize this"
"""
    print(help_text)

def print_output_stats(output_string: str):
    """Calculates and prints output statistics."""
    lines = len(output_string.splitlines())
    chars = len(output_string)
    print(f"📊 Stats: {lines:,} lines, {chars:,} characters.", file=sys.stderr)

def main():
    """Parses arguments, calls the core logic, and handles the final output."""
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print_help()
        sys.exit(0)
    if "--version" in args or "-v" in args:
        print(f"viopi version {__version__}")
        sys.exit(0)

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

    root_dir = Path(path_args[0]).resolve() if path_args else Path.cwd().resolve()

    # --- Run Core Logic ---
    print(f"🚀 Processing directory: {root_dir}", file=sys.stderr)
    link_status = "enabled" if follow_links_mode else "disabled"
    print(f"ℹ️  Symbolic link following is {link_status}.", file=sys.stderr)

    final_output, summary_report = generate_project_context(
        root_dir, pattern_args, follow_links=follow_links_mode
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
        # --- APPEND LOGIC ---
        # This block only runs if --append is used. It targets the base file.
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
        # --- DEFAULT VERSIONED FILE LOGIC ---
        # This is now the default. It *always* creates a new file.
        try:
            output_filename = get_next_output_filename(OUTPUT_BASENAME, OUTPUT_EXTENSION)
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(final_output)
            print(f"\n✅ Combined contents Saved to new file: {Path(output_filename).resolve()}", file=sys.stderr)
        except IOError as e:
            print(f"\n❌ Error: Could not write to file '{output_filename}'.\n   Details: {e}", file=sys.stderr)
            sys.exit(1)

    # Print stats for any mode that produced content (i.e., not an error exit)
    print_output_stats(final_output)

if __name__ == "__main__":
    main()