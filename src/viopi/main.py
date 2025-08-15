# FILE: src/viopi/main.py
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
HUGE_FILE_THRESHOLD_BYTES = 100 * 1024  # 100 KiB

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
    parser.add_argument("-s", "--summary", action="store_true",
                        help="Print a summary of the files that would be "
                             "included (after ignore rules / huge-file prompts) "
                             "and exit.")

    output_group.add_argument("--json", action="store_true")
    parser.add_argument("--no-follow-links", action="store_true")
    parser.add_argument("--show-ignore", action="store_true",
    help="Print the combined .viopi_ignore patterns (with sources) and exit.")

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

    # --- 2. Data Collection ---
    if args.show_ignore:
        _, _, annotated = viopi_ignorer.get_ignore_config(target_dir, return_annotated=True)
        print(viopi_ignorer.format_combined_ignore(annotated))
        sys.exit(0)

    ignore_spec, ignore_root = viopi_ignorer.get_ignore_config(target_dir)
    follow_links = not args.no_follow_links
    
    files_to_process_tuples, ignored_count = viopi_utils.get_file_list(
        target_dir, patterns, follow_links, ignore_spec, ignore_root
    )

    # --- SUMMARY FLAG --------------------------------------------------------
    # If the user asked for a summary we show the final list of logical paths
    # that will be processed, plus a simple count, then exit.
    if args.summary:
        print(f"Directory Processed: {target_dir}")
        print("--- Files that will be included ---")
        for _, logical_path in files_to_process_tuples:
            print(logical_path)
        print(f"\nTotal files: {len(files_to_process_tuples)}")
        sys.exit(0)
    # -------------------------------------------------------------------------

    # --- NEW: INTERACTIVE HUGE FILE HANDLING ---
    final_files_to_process_tuples = []
    newly_ignored_paths = []
    if files_to_process_tuples:
        for physical_path_str, logical_path_str in files_to_process_tuples:
            try:
                # Use the physical path for stat, but the logical path for display/ignore
                file_path = Path(physical_path_str)
                file_size = file_path.stat().st_size

                if file_size > HUGE_FILE_THRESHOLD_BYTES:
                    # Show the user the logical path for context
                    logical_path_for_prompt = Path(logical_path_str)
                    if viopi_printer.prompt_to_ignore_huge_file(logical_path_for_prompt, file_size):
                        rel_path_to_ignore = Path(target_dir) / logical_path_str
                        newly_ignored_paths.append(str(rel_path_to_ignore.relative_to(ignore_root)))
                        ignored_count += 1
                        continue
                
                final_files_to_process_tuples.append((physical_path_str, logical_path_str))
            except (FileNotFoundError, Exception) as e:
                viopi_printer.print_warning(f"Could not stat file {physical_path_str}: {e}. Skipping.")
                ignored_count += 1

    if newly_ignored_paths:
        ignore_file_path = Path(target_dir) / viopi_ignorer.REPO_IGNORE_FILENAME
        try:
            with open(ignore_file_path, 'a', encoding='utf-8') as f:
                f.write("\n# Added by viopi (huge file prompt)\n")
                for path_to_ignore in sorted(newly_ignored_paths):
                    f.write(f"{path_to_ignore}\n")
            viopi_printer.print_info(f"Added {len(newly_ignored_paths)} entr(y/ies) to {ignore_file_path}")
        except IOError as e:
            viopi_printer.print_error(f"Could not write to {ignore_file_path}: {e}", is_fatal=False)

    files_to_process_tuples = final_files_to_process_tuples
    # --- END OF NEW LOGIC ---

    if not files_to_process_tuples:
        viopi_printer.print_warning("No files found matching the criteria. Exiting.")
        sys.exit(0)

    stats = { "total_files": 0, "total_lines": 0, "total_characters": 0, "files_ignored": ignored_count }
    file_data_list = []
    for physical_path, logical_path in files_to_process_tuples:
        try:
            with open(physical_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            stats["total_files"] += 1
            stats["total_lines"] += len(content.splitlines())
            stats["total_characters"] += len(content)
            file_data_list.append({"path": logical_path, "content": content})
        except IOError as e:
            viopi_printer.print_warning(f"Could not read file {physical_path}: {e}")

    # --- 3. Output Generation ---
    if args.json:
        json_string = viopi_json_output.generate_json_output(stats, file_data_list)
        stats["payload_size_bytes"] = len(json_string.encode('utf-8'))
        output_string = viopi_json_output.generate_json_output(stats, file_data_list)
        print(output_string)
    else:
        header = f"Directory Processed: {target_dir}\n"
        logical_paths = [t[1] for t in files_to_process_tuples]
        tree_output = viopi_utils.generate_tree_output(logical_paths)
        file_contents_str = "\n\n---\nCombined file contents:\n"
        for file_data in file_data_list:
            file_contents_str += f"\n--- FILE: {file_data['path']} ---\n{file_data['content']}"
        text_output_string = header + tree_output + file_contents_str + "\n\n--- End of context ---"
        stats["payload_size_bytes"] = len(text_output_string.encode('utf-8'))

        # --- 4. Final Output Handling ---
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