# main.py

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

# Assuming these modules exist and are updated as needed
from . import viopi_utils
from .viopi_help import print_help_and_exit
from .viopi_version import get_project_version, print_version_and_exit
from . import viopi_json_output  # <-- Import the new module

# --- Configuration Constants (from your help text) ---
OUTPUT_BASENAME = "_viopi_output"
OUTPUT_EXTENSION = ".viopi"
APPEND_FILENAME = f"{OUTPUT_BASENAME}{OUTPUT_EXTENSION}"


def get_next_versioned_filename(base: str, ext: str, directory: str) -> str:
    """Finds the next available versioned filename."""
    version = 1
    while True:
        filename = Path(directory) / f"{base}_{version}{ext}"
        if not filename.exists():
            return str(filename)
        version += 1


def main():
    """Main function to run the viopi tool."""
    parser = argparse.ArgumentParser(
        description="Viopi: A tool for preparing project context for LLMs.",
        add_help=False  # Use custom help
    )

    # --- Arguments based on your viopi_help.py ---
    parser.add_argument(
        "path_and_patterns",
        nargs="*",
        help="Optional path followed by optional glob patterns. E.g., 'src/app \"**/*.js\" \"**/*.css\"'."
    )
    parser.add_argument("-h", "--help", action="store_true", help="Show this help message and exit.")
    parser.add_argument("-v", "--version", action="store_true", help="Show program's version number and exit.")

    # Mutually exclusive output options
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--stdout", action="store_true", help="Print formatted text output to stdout instead of a file.")
    output_group.add_argument("--copy", action="store_true", help="Copy formatted text output to the system clipboard.")
    output_group.add_argument("--append", action="store_true", help=f"Append formatted text output to the base file '{APPEND_FILENAME}'.")
    # --- Add the --json argument to the group ---
    output_group.add_argument("--json", action="store_true", help="Output the data in JSON format to stdout.")

    parser.add_argument("--no-follow-links", action="store_true", help="Disable following symbolic links.")

    args = parser.parse_args()
    version = get_project_version()

    # --- Handle immediate exit arguments ---
    if args.help:
        print_help_and_exit(version, OUTPUT_BASENAME, OUTPUT_EXTENSION, APPEND_FILENAME)

    if args.version:
        print_version_and_exit()

    # --- Process Path and Patterns (Code from previous step, no changes here) ---
    target_dir_str = "."
    patterns = []
    if args.path_and_patterns:
        first_arg = args.path_and_patterns[0]
        if os.path.isdir(first_arg):
            target_dir_str = first_arg
            patterns = args.path_and_patterns[1:]
        else:
            patterns = args.path_and_patterns
    target_dir = os.path.abspath(target_dir_str)
    if not os.path.isdir(target_dir):
        print(f"Error: Directory not found at '{target_dir}'", file=sys.stderr)
        sys.exit(1)

    # --- Data Collection (Code from previous step, no changes here) ---
    follow_links = not args.no_follow_links
    files_to_process = viopi_utils.get_file_list(target_dir, patterns, follow_links)
    if not files_to_process:
        print(f"No files found in '{target_dir}' matching the criteria. Exiting.", file=sys.stderr)
        sys.exit(0)
    stats = {"total_files": 0, "total_lines": 0, "total_characters": 0}
    file_data_list = []
    for file_path in files_to_process:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            relative_path = os.path.relpath(file_path, target_dir)
            stats["total_files"] += 1
            stats["total_lines"] += len(content.splitlines())
            stats["total_characters"] += len(content)
            file_data_list.append({"path": relative_path, "content": content})
        except IOError as e:
            print(f"Warning: Could not read file {file_path}: {e}", file=sys.stderr)

    # --- Output Generation and Handling ---
    stats_str = f"Stats: {stats['total_files']} files, {stats['total_lines']} lines, {stats['total_characters']} characters."

    # --- Handle JSON output first ---
    if args.json:
        output_string = viopi_json_output.generate_json_output(stats, file_data_list)
        print(output_string)
        # JSON mode finishes here
        sys.exit(0)

    # --- Standard Text Output Generation ---
    header = f"Directory Processed: {target_dir}\n"
    tree_output = viopi_utils.generate_tree_output(target_dir, files_to_process)
    file_contents_str = "\n\n---\nCombined file contents:\n"
    for file_data in file_data_list:
        file_contents_str += f"\n--- FILE: {file_data['path']} ---\n{file_data['content']}"
    
    text_output_string = header + tree_output + file_contents_str + "\n\n--- End of context ---"

    # --- Final Text Output Handling ---
    if args.stdout:
        print(text_output_string)
    elif args.copy:
        try:
            import pyperclip
            pyperclip.copy(text_output_string)
            print("Viopi output copied to clipboard.")
            print(stats_str)
        except ImportError:
            print("Error: 'pyperclip' is not installed. Please install it (`pip install pyperclip`) to use the --copy feature.", file=sys.stderr)
            sys.exit(1)
        except pyperclip.PyperclipException as e:
            print(f"Error: Could not copy to clipboard. Ensure xclip/xsel (Linux) or a clipboard mechanism is available.", file=sys.stderr)
            print(f"Pyperclip error: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.append:
        append_path = Path(target_dir) / APPEND_FILENAME
        try:
            with open(append_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n--- Appended on {datetime.now().isoformat()} ---\n")
                f.write(text_output_string)
            print(f"Output appended to {append_path}")
            print(stats_str)
        except IOError as e:
            print(f"Error: Could not append to file {append_path}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Default: Create a new versioned file
        output_filename = get_next_versioned_filename(OUTPUT_BASENAME, OUTPUT_EXTENSION, target_dir)
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(text_output_string)
            print(f"Output saved to {output_filename}")
            print(stats_str)
        except IOError as e:
            print(f"Error: Could not write to file {output_filename}: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()