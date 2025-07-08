#!/usr/bin/env python3
#
# Recursively finds text files, concatenates their contents, and saves the
# result. A powerful tool for preparing project context for LLMs.
#
# This script is a controller for the core logic in `viopi_utils.py`.
#
# For detailed usage and options, run: viopi --help
#

import sys
from pathlib import Path

# --- Constants ---
__version__ = "1.1.0"
OUTPUT_FILENAME = "_viopi_output.viopi"

# --- Dependency Handling ---
# Attempt to import shared logic. Provide a helpful error if it's missing.
try:
    from viopi_utils import generate_project_context
except ImportError:
    print("Error: The 'viopi_utils.py' module was not found.", file=sys.stderr)
    print("Please make sure viopi_utils.py is in the same directory as this script.", file=sys.stderr)
    sys.exit(1)


def print_help():
    """Prints the detailed help and usage message to the console."""
    help_text = f"""
viopi v{__version__}
A powerful tool for preparing project context for LLMs by recursively 
finding and concatenating text files.

Usage:
  viopi [options] [path] [pattern_1] [pattern_2] ...

Arguments:
  path                  The root directory to search. Defaults to the current
                        working directory if not provided.
  pattern               Optional glob patterns to include specific files (e.g., 
                        '*.py', '**/*.js'). If no patterns are given, a default
                        set of common text file extensions is used.

Options:
  -h, --help            Show this help message and exit.
  -v, --version         Show the version number and exit.
  
  --stdout              Print the final output to standard output instead of a 
                        file. Ideal for piping to other commands.
                        
  --copy                Copy the final output to the system clipboard. Requires
                        the 'pyperclip' library.
                        
  --append              Append the output to the existing output file. Without
                        this flag, the file is always overwritten.
                        
  --no-follow-links     Disable the default behavior of following symbolic links
                        during the file search.

Default Behavior:
  By default, the script completely overwrites the `{OUTPUT_FILENAME}` file in
  the current directory.

Examples:
  # Process the current directory and overwrite {OUTPUT_FILENAME}
  viopi

  # Process only Python and Markdown files in the 'src' directory
  viopi src/ '*.py' '*.md'

  # Pipe the context of the current directory to another tool
  viopi --stdout | llm -s "Summarize this codebase"

  # Append JS file contexts to the output file
  viopi --append src/app/ '**/*.js'
"""
    print(help_text)


def print_output_stats(output_string):
    """Calculates and prints the line and character count of the final output."""
    lines = len(output_string.splitlines())
    chars = len(output_string)
    print(f"📊 Stats: {lines:,} lines, {chars:,} characters.", file=sys.stderr)


def main():
    """Parses arguments, calls the core logic, and handles the final output."""
    args = sys.argv[1:]

    # --- Handle Informational Flags (Help & Version) ---
    # These flags cause the program to exit immediately after printing.
    if "--help" in args or "-h" in args:
        print_help()
        sys.exit(0)
        
    if "--version" in args or "-v" in args:
        print(f"viopi version {__version__}")
        sys.exit(0)

    # --- Determine Operational Mode ---
    stdout_mode = False
    copy_mode = False
    append_mode = False
    follow_links_mode = True

    if "--stdout" in args:
        stdout_mode = True
        args.remove("--stdout")
    elif "--copy" in args:
        copy_mode = True
        args.remove("--copy")
    elif "--append" in args:
        append_mode = True
        args.remove("--append")

    if "--no-follow-links" in args:
        follow_links_mode = False
        args.remove("--no-follow-links")

    # --- Separate Path Argument from Patterns ---
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
    if follow_links_mode:
        print("ℹ️  Following symbolic links. Use --no-follow-links to disable.", file=sys.stderr)
    else:
        print("ℹ️  Symbolic link following is disabled.", file=sys.stderr)

    final_output, summary_report = generate_project_context(
        root_dir,
        pattern_args,
        follow_links=follow_links_mode
    )

    print(summary_report, file=sys.stderr)

    # --- Handle Final Output ---
    if stdout_mode:
        print(final_output)
        print(f"\n✅ Done. Output sent to stdout.", file=sys.stderr)
        print_output_stats(final_output)
    elif copy_mode:
        try:
            import pyperclip
            pyperclip.copy(final_output)
            print(f"\n✅ Combined contents copied to the clipboard.", file=sys.stderr)
            print_output_stats(final_output)
        except (ImportError, pyperclip.PyperclipException) as e:
            print("\n❌ Error: Could not copy to clipboard.", file=sys.stderr)
            print("   'pyperclip' may not be installed or configured.", file=sys.stderr)
            print("   Install it (`pip install pyperclip`) or use --stdout.", file=sys.stderr)
            print(f"   Details: {e}", file=sys.stderr)
            sys.exit(1)
    else: # Default behavior: save to file
        try:
            full_output_path = Path(OUTPUT_FILENAME).resolve()
            
            if append_mode:
                # This block only runs if --append is used.
                # It opens the file in 'a' (append) mode.
                content_to_write = f"\n{final_output}" if full_output_path.exists() and full_output_path.stat().st_size > 0 else final_output
                with open(OUTPUT_FILENAME, "a", encoding="utf-8") as f:
                    f.write(content_to_write)
                print(f"\n✅ Combined contents Appended to file: {full_output_path}", file=sys.stderr)
            else:
                # This is the default action.
                # It opens the file in 'w' (write) mode, which erases existing content.
                with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
                    f.write(final_output)
                print(f"\n✅ Combined contents Saved to file (overwritten): {full_output_path}", file=sys.stderr)
            
            print_output_stats(final_output)

        except IOError as e:
            print(f"\n❌ Error: Could not write to file '{OUTPUT_FILENAME}'.", file=sys.stderr)
            print(f"   Details: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()