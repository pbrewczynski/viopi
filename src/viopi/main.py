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
from . import viopi_minifier
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

def get_language_from_filename(filename: str) -> str:
    """Guess the markdown language tag from a filename."""
    # A mapping of file extensions to markdown language identifiers
    ext_map = {
        # Web
        ".html": "html", ".css": "css", ".scss": "scss",
        ".js": "javascript", ".jsx": "jsx",
        ".ts": "typescript", ".tsx": "tsx",
        # Python
        ".py": "python",
        # Mobile
        ".swift": "swift", ".kt": "kotlin", ".kts": "kotlin",
        ".java": "java", ".m": "objectivec",
        # C-family
        ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".cs": "csharp",
        # Backend
        ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php",
        # Scripting & Shell
        ".sh": "shell", ".bash": "bash", ".zsh": "zsh", ".ps1": "powershell",
        ".pl": "perl", ".lua": "lua",
        # Data & Config
        ".json": "json", ".xml": "xml", ".yaml": "yaml", ".yml": "yaml",
        ".md": "markdown", ".sql": "sql",
        # Other
        ".r": "r", ".dockerfile": "dockerfile", "Dockerfile": "dockerfile",
    }
    # Handle files with no extension like 'Dockerfile'
    name = Path(filename).name
    if name in ext_map:
        return ext_map[name]

    # Handle extensions
    suffix = Path(filename).suffix.lower()
    return ext_map.get(suffix, "") # Return empty string if not found

def handle_suggest_ignore(files_to_scan_tuples, target_dir_path: Path, ignore_root: Path):
    """
    Scans files for being large or binary and prints a suggested ignore list.
    """
    large_files = []
    binary_files = []

    for physical_path_str, logical_path_str, _ in files_to_scan_tuples:
        try:
            file_path = Path(physical_path_str)

            # The path for ignore file should be relative to ignore_root
            rel_path_to_ignore = (target_dir_path / logical_path_str).relative_to(ignore_root)

            # Check if binary first.
            if viopi_utils.is_binary_file(physical_path_str):
                binary_files.append(str(rel_path_to_ignore))
                continue

            # If not binary, check if it's huge.
            file_size = file_path.stat().st_size
            if file_size > HUGE_FILE_THRESHOLD_BYTES:
                large_files.append((str(rel_path_to_ignore), file_size))

        except (FileNotFoundError, Exception) as e:
            viopi_printer.print_warning(f"Could not process {physical_path_str}: {e}. Skipping.")

    if not binary_files and not large_files:
        viopi_printer.print_info("No binary or large files found to suggest for ignoring.")
        return

    # Print to stdout, as this is the primary output of this mode
    print("# Viopi: Suggested ignores for binary or large files.")
    print("# Add these lines to your .viopi_ignore file to exclude them.\n")

    if binary_files:
        print("# --- Binary Files ---")
        for path in sorted(binary_files):
            print(path)
        print("")

    if large_files:
        print(f"# --- Large Files (over {HUGE_FILE_THRESHOLD_BYTES // 1024} KiB) ---")
        for path, size in sorted(large_files):
            size_str = viopi_utils.format_bytes(size)
            print(f"{path} # {size_str}")
        print("")

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
    output_group.add_argument("--suggest-ignore", action="store_true",
        help="Scan for and print paths of binary or very large files to suggest for .viopi_ignore.")
    parser.add_argument("--minify", action="store_true",
                        help="Minify code files (JS, CSS, Python, HTML, JSON) to reduce token count.")
    parser.add_argument("--no-follow-links", action="store_true")
    parser.add_argument("--show-ignore", action="store_true",
    help="Print the combined .viopi_ignore patterns (with sources) and exit.")
    parser.add_argument("--show-all", action="store_true",
    help="Show all discovered files in the file tree, including those ignored.")
    parser.add_argument("--no-code-fences", action="store_true",
    help="Do not wrap file contents in triple-backtick code fences.")

    args = parser.parse_args()

    # Configure the printer based on args. If --stdout is used, suppress
    # all non-essential stderr output like warnings and info messages.
    if args.stdout:
        viopi_printer.configure(silent=True)

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

    files_to_process_tuples, ignored_files_tuples = viopi_utils.get_file_list(
        target_dir, patterns, follow_links, ignore_spec, ignore_root
    )
    ignored_count = len(ignored_files_tuples)

    # --- SUGGEST IGNORE FLAG ---
    if args.suggest_ignore:
        all_files_for_scan = files_to_process_tuples + ignored_files_tuples
        handle_suggest_ignore(all_files_for_scan, Path(target_dir), ignore_root)
        sys.exit(0)

    # --- SUMMARY FLAG --------------------------------------------------------
    if args.summary:
        print(f"Directory Processed: {target_dir}")
        print("--- Files that will be included ---")
        for _, logical_path, is_symlink in files_to_process_tuples:
            line = logical_path
            if is_symlink:
                line += " -> [symbolic link]"
            print(line)
        print(f"\nTotal files to be included: {len(files_to_process_tuples)}")
        print(f"Total files ignored (by rules or patterns): {ignored_count}")
        sys.exit(0)
    # -------------------------------------------------------------------------

    # --- NEW: INTERACTIVE HUGE FILE HANDLING ---
    final_files_to_process_tuples = []
    newly_ignored_paths = []
    if files_to_process_tuples:
        for file_tuple in files_to_process_tuples:
            physical_path_str, logical_path_str, is_symlink = file_tuple
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

                        # --- FIX ---
                        # Add to ignored list for --show-all and increment count
                        ignored_files_tuples.append(file_tuple)
                        ignored_count += 1
                        continue # Skip adding to final_files_to_process_tuples

                final_files_to_process_tuples.append(file_tuple)
            except (FileNotFoundError, Exception) as e:
                viopi_printer.print_warning(f"Could not stat file {physical_path_str}: {e}. Skipping.")

                # --- FIX ---
                # Add to ignored list for --show-all and increment count
                ignored_files_tuples.append(file_tuple)
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

    stats = { "total_files": 0, "total_lines": 0, "total_characters": 0, "files_ignored": ignored_count, "total_chars_saved_minify": 0 }
    file_data_list = []
    for physical_path, logical_path, _ in files_to_process_tuples:
        try:
            with open(physical_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            if args.minify:
                original_len = len(content)
                minified_content = viopi_minifier.minify_content(content, logical_path)
                if len(minified_content) < original_len:
                    chars_saved = original_len - len(minified_content)
                    stats["total_chars_saved_minify"] += chars_saved
                content = minified_content

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

        tree_items = []
        if args.show_all:
            processed_for_tree = [(lp, sl, False) for _, lp, sl in files_to_process_tuples]
            ignored_for_tree = [(lp, sl, True) for _, lp, sl in ignored_files_tuples]
            tree_items.extend(processed_for_tree)
            tree_items.extend(ignored_for_tree)
        else:
            tree_items = [(lp, sl, False) for _, lp, sl in files_to_process_tuples]

        tree_output = viopi_utils.generate_tree_output(tree_items)

        file_contents_str = "\n\n---\nCombined file contents:"
        for file_data in file_data_list:
            file_contents_str += f"\n\n--- FILE: {file_data['path']} ---"
            if not args.no_code_fences:
                lang = get_language_from_filename(file_data['path'])
                file_contents_str += f"\n```{lang}\n{file_data['content']}\n```"
            else:
                file_contents_str += f"\n{file_data['content']}"

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