#!/usr/bin/env python3
#
# Recursively finds text files (following symbolic links by default),
# concatenates their contents, and saves the result to _viopi_output.viopi
# A powerful tool for preparing project context for LLMs.
#
# This script is a controller for the core logic in `viopi_utils.py`.
#
# Usage:
#   viopi [path] [p_or_p_1] ...         # Saves to _viopi_output.viopi (Default, follows links)
#   viopi --copy [path] ...             # Copies to clipboard
#   viopi --stdout [path] ...           # Prints to stdout (for piping)
#   viopi --no-follow-links ...         # Disables following symbolic links
#
# New ignore files loaded: .viopi_ignore, .viopi_ignore_global
#

import sys
from pathlib import Path

# Attempt to import shared logic. Provide a helpful error if it's missing.
try:
    from viopi_utils import generate_project_context
except ImportError:
    print("Error: The 'viopi_utils.py' module was not found.", file=sys.stderr)
    print("Please make sure viopi_utils.py is in the same directory as this script.", file=sys.stderr)
    sys.exit(1)


def print_output_stats(output_string):
    """Calculates and prints the line and character count of the final output."""
    lines = len(output_string.splitlines())
    chars = len(output_string)
    # Using f-string with comma for thousands separator for better readability
    print(f"📊 Stats: {lines:,} lines, {chars:,} characters.", file=sys.stderr)


def main():
    """Parses arguments, calls the core logic, and handles the final output."""
    args = sys.argv[1:]
    
    # --- Determine Mode (File vs. Clipboard vs. Stdout vs. Symlinks) ---
    stdout_mode = False
    copy_mode = False
    follow_links_mode = True  # <-- MODIFIED: Default is now True
    output_filename = ".output.viopi"

        
        

    if "--stdout" in args:
        stdout_mode = True
        args.remove("--stdout")
    elif "--copy" in args:
        copy_mode = True
        args.remove("--copy")

    # +++ THIS BLOCK IS MODIFIED to check for the opposite flag +++
    if "--no-follow-links" in args:
        follow_links_mode = False
        args.remove("--no-follow-links")
    # +++ END OF MODIFICATION +++

    # --- Separate Path Argument from Patterns ---
    path_args, pattern_args = [], []
    for arg in args:
        # A simple check: if it looks like an existing directory, it's a path.
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
        print("ℹ️  Following symbolic links by default. Use --no-follow-links to disable.", file=sys.stderr)
    else:
        print("ℹ️  Symbolic link following is disabled.", file=sys.stderr)


    print(follow_links_mode)
    final_output, summary_report = generate_project_context(
        root_dir,
        pattern_args,
        follow_links=follow_links_mode
    )
    
    # Print status and summary reports to stderr so they don't interfere with stdout
    print(summary_report, file=sys.stderr)

    # --- Handle Final Output ---
    if stdout_mode:
        print(final_output)
        print("\n✅ Done. Output sent to stdout.", file=sys.stderr)
        # Also print stats for stdout mode for consistency
        print_output_stats(final_output)
    elif copy_mode:
        try:
            import pyperclip
            pyperclip.copy(final_output)
            print("\n✅ Combined contents copied to the clipboard.", file=sys.stderr)
            print_output_stats(final_output) # Print stats after copying
        except (ImportError, pyperclip.PyperclipException) as e:
            print("\n❌ Error: Could not copy to clipboard.", file=sys.stderr)
            print("   'pyperclip' may not be installed or configured.", file=sys.stderr)
            print("   Install it (`pip install pyperclip`) or use the --stdout flag.", file=sys.stderr)
            print(f"   Details: {e}", file=sys.stderr)
            sys.exit(1)
    else: # Default behavior: save to file
        try:
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(final_output)
            full_output_path = Path(output_filename).resolve()
            print(f"\n✅ Combined contents saved to file: {full_output_path}", file=sys.stderr)
            print_output_stats(final_output) # Print stats after saving
        except IOError as e:
            print(f"\n❌ Error: Could not write to file '{output_filename}'.", file=sys.stderr)
            print(f"   Details: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()