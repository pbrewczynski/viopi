# main.py

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

# Import all our custom modules
from . import viopi_utils
from . import viopi_ignorer
from . import viopi_printer
from . import viopi_json_output
from .viopi_help import print_help_and_exit
from .viopi_version import get_project_version, print_version_and_exit

# Config constants remain the same
OUTPUT_BASENAME = "_viopi_output"
OUTPUT_EXTENSION = ".viopi"
APPEND_FILENAME = f"{OUTPUT_BASENAME}{OUTPUT_EXTENSION}"

def get_next_versioned_filename(base: str, ext: str, directory: str) -> str:
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
        add_help=False
    )
    parser.add_argument("path_and_patterns", nargs="*")
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-v", "--version", action="store_true")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--stdout", action="store_true")
    output_group.add_argument("--copy", action="store_true")
    output_group.add_argument("--append", action="store_true")
    output_group.add_argument("--json", action="store_true")
    parser.add_argument("--no-follow-links", action="store_true")

    args = parser.parse_args()
    version = get_project_version()

    if args.help:
        print_help_and_exit(version, OUTPUT_BASENAME, OUTPUT_EXTENSION, APPEND_FILENAME)
    if args.version:
        print_version_and_exit()

    # --- 1. Process Path and Patterns ---
    target_dir_str = "."
    patterns = []
    if args.path_and_patterns:
        if os.path.isdir(args.path_and_patterns[0]):
            target_dir_str = args.path_and_patterns[0]
            patterns = args.path_and_patterns[1:]
        else:
            patterns = args.path_and_patterns
    target_dir = os.path.abspath(target_dir_str)
    if not os.path.isdir(target_dir):
        viopi_printer.print_error(f"Directory not found at '{target_dir}'")

    # --- 2. Data Collection (CORRECTED) ---
    # Get the ignore spec AND the root path to check against
    ignore_spec, ignore_root = viopi_ignorer.get_ignore_config(target_dir)
    follow_links = not args.no_follow_links
    
    # Pass both the spec and the root to the file lister
    files_to_process, ignored_count = viopi_utils.get_file_list(
        target_dir, patterns, follow_links, ignore_spec, ignore_root
    )

    if not files_to_process:
        viopi_printer.print_warning("No files found matching the criteria. Exiting.")
        sys.exit(0)

    stats = { "total_files": 0, "total_lines": 0, "total_characters": 0, "files_ignored": ignored_count }
    file_data_list = []
    for file_path in files_to_process:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            stats["total_files"] += 1
            stats["total_lines"] += len(content.splitlines())
            stats["total_characters"] += len(content)
            file_data_list.append({"path": os.path.relpath(file_path, target_dir), "content": content})
        except IOError as e:
            viopi_printer.print_warning(f"Could not read file {file_path}: {e}")

    # --- 3. Output Generation (No changes needed) ---
    if args.json:
        json_string = viopi_json_output.generate_json_output(stats, file_data_list)
        stats["payload_size_bytes"] = len(json_string.encode('utf-8'))
        output_string = viopi_json_output.generate_json_output(stats, file_data_list)
        print(output_string)
    else:
        header = f"Directory Processed: {target_dir}\n"
        tree_output = viopi_utils.generate_tree_output(target_dir, files_to_process)
        file_contents_str = "\n\n---\nCombined file contents:\n"
        for file_data in file_data_list:
            file_contents_str += f"\n--- FILE: {file_data['path']} ---\n{file_data['content']}"
        text_output_string = header + tree_output + file_contents_str + "\n\n--- End of context ---"
        stats["payload_size_bytes"] = len(text_output_string.encode('utf-8'))

        # --- 4. Final Output Handling (No changes needed) ---
        if args.stdout:
            print(text_output_string)
        elif args.copy:
            try:
                import pyperclip
                pyperclip.copy(text_output_string)
                viopi_printer.print_success_copy(stats)
            except (ImportError, pyperclip.PyperclipException) as e:
                viopi_printer.print_error(f"Could not copy to clipboard. {e}")
        elif args.append:
            append_path = Path(target_dir) / APPEND_FILENAME
            try:
                with open(append_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n--- Appended on {datetime.now().isoformat()} ---\n")
                    f.write(text_output_string)
                viopi_printer.print_success_append(stats, str(append_path))
            except IOError as e:
                viopi_printer.print_error(f"Could not append to file {append_path}: {e}")
        else:
            output_filename = get_next_versioned_filename(OUTPUT_BASENAME, OUTPUT_EXTENSION, target_dir)
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    f.write(text_output_string)
                viopi_printer.print_success_file(stats, output_filename)
            except IOError as e:
                viopi_printer.print_error(f"Could not write to file {output_filename}: {e}")

if __name__ == "__main__":
    main()