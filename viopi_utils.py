# viopi_utils.py
# Shared utilities and core logic for the Viopi project context generator.

import os
import sys
import fnmatch
from pathlib import Path
import subprocess
import magic
import shutil

# --- Configuration (unchanged) ---
# ...

LOCAL_IGNORE_FILES = (".copy_combine_ignore", ".viopi_ignore")
GLOBAL_IGNORE_FILES = (
    Path.home() / ".copy_combine_ignore_global",
    Path.home() / ".viopi_ignore_global",
)
PRESET_PREFIXES = (".copy_combine_ignore_preset_", ".viopi_ignore_preset_")
PRESET_ALIASES = {
    ".xcode_project": ".xcode_strict",
    ".macos_app": ".xcode_strict",
    ".ios_app": ".xcode_strict",
    ".visionos_app": ".xcode_strict",
    ".watchos_app": ".xcode_strict",
    ".react_app": ".node_project",
    ".vue_app": ".node_project",
    ".svelte_app": ".node_project",
    ".nextjs_app": ".node_project",
}


# --- Helper Functions (unchanged) ---
def is_binary(file_path: Path) -> bool:
    """
    Uses python-magic to determine if a file is binary. Resolves symlinks
    to check the actual file content.
    """
    try:
        real_path = file_path.resolve(strict=True)
        if not real_path.is_file() or real_path.stat().st_size == 0:
            return False
    except (FileNotFoundError, RuntimeError):
        return False

    KNOWN_TEXT_MIMES = {
        'application/json', 'application/javascript', 'application/xml',
        'application/x-sh', 'application/x-python', 'application/x-sql',
        'application/vnd.apple.xcode-strings'
    }
    try:
        mime_type = magic.from_file(str(real_path), mime=True)
        if mime_type.startswith("text/") or mime_type in KNOWN_TEXT_MIMES:
            return False
        if mime_type in ['application/octet-stream', 'inode/x-empty']:
            pass
        else:
            return True
    except magic.MagicException:
        pass
    try:
        with open(real_path, "r", encoding="utf-8") as f:
            f.read(1024)
        return False
    except (UnicodeDecodeError, IOError):
        return True

def get_preset_patterns(preset_name: str) -> list[str]:
    """
    Loads ignore patterns from a preset file in the home directory.
    """
    preset_filename_suffix = preset_name.lstrip('.')
    for prefix in PRESET_PREFIXES:
        preset_file = Path.home() / f"{prefix}{preset_filename_suffix}"
        if preset_file.is_file():
            print(f"  (Loading from {preset_file.name})", file=sys.stderr)
            return [
                line for line in preset_file.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
    return []

# --- Core Logic Function ---
def generate_project_context(
    root_dir: Path, 
    custom_patterns: list[str], 
    follow_links: bool
) -> tuple[str, str]:
    """
    Walks a directory, generates a project context string, and returns it
    along with a summary of actions taken.
    """
    # ... (ignore pattern aggregation is unchanged) ...
    status_lines = []
    
    ignore_patterns = {".DS_Store", *LOCAL_IGNORE_FILES, Path(__file__).name, "viopi", "_viopi_output_.txt"}
    sources_of_ignores = {"Defaults": list(ignore_patterns)}

    for ignore_file in GLOBAL_IGNORE_FILES:
        if ignore_file.is_file():
            patterns = [p for p in ignore_file.read_text().splitlines() if p.strip() and not p.strip().startswith("#")]
            if patterns:
                sources_of_ignores[ignore_file.name] = patterns
                ignore_patterns.update(patterns)

    for fname in LOCAL_IGNORE_FILES:
        ignore_file = root_dir / fname
        if ignore_file.is_file():
            patterns = [p for p in ignore_file.read_text().splitlines() if p.strip() and not p.strip().startswith("#")]
            if patterns:
                sources_of_ignores[ignore_file.name] = patterns
                ignore_patterns.update(patterns)

    activated_presets = set()
    literal_args = []
    for arg in custom_patterns:
        preset_to_check = PRESET_ALIASES.get(arg, arg)
        patterns = get_preset_patterns(preset_to_check)
        if patterns:
            activated_presets.add(arg)
            sources_of_ignores[f"Preset: {arg}"] = patterns
            ignore_patterns.update(patterns)
        else:
            literal_args.append(arg)
    
    if literal_args:
        sources_of_ignores["Arguments"] = literal_args
        ignore_patterns.update(literal_args)

    status_lines.append("🔎 Activating ignore patterns...")
    for source, patterns in sources_of_ignores.items():
        status_lines.append(f"  - From {source}:")
        for p in sorted(patterns):
            status_lines.append(f"    - {p}")
    status_lines.append("----------------------------------------")
    
    files_to_cat = []
    unique_ignore_patterns = set(ignore_patterns)

    for root, dirs, files in os.walk(root_dir, topdown=True, followlinks=follow_links):
        current_path = Path(root)
        
        dirs[:] = [d for d in dirs if not any(
            fnmatch.fnmatch(d, p) or fnmatch.fnmatch(str((current_path / d).relative_to(root_dir)), p)
            for p in unique_ignore_patterns
        )]
        
        for filename in files:
            file_path = current_path / filename

            # +++ THIS IS THE CRITICAL FIX +++
            # If the path is a symlink AND we are instructed NOT to follow them,
            # skip it immediately. This prevents it from being processed further.
            if not follow_links and file_path.is_symlink():
                continue
            # +++ END OF CRITICAL FIX +++

            # Determine the path to check against ignore patterns.
            # If it's a link (and we're following), check the target. Otherwise, check the file itself.
            path_to_check_for_ignore = file_path
            if file_path.is_symlink(): # This code only runs if follow_links is True
                try:
                    path_to_check_for_ignore = file_path.resolve(strict=True)
                    if not path_to_check_for_ignore.is_file(): continue # Skip links to dirs, etc.
                except (FileNotFoundError, RuntimeError): continue
            
            # Check the original filename/path AND the target's filename/path against ignore patterns.
            orig_rel_path = str(file_path.relative_to(root_dir))
            target_name = path_to_check_for_ignore.name
            target_rel_path = os.path.relpath(path_to_check_for_ignore, root_dir)

            if any(fnmatch.fnmatch(filename, p) or fnmatch.fnmatch(orig_rel_path, p) or \
                   fnmatch.fnmatch(target_name, p) or fnmatch.fnmatch(target_rel_path, p) for p in unique_ignore_patterns):
                continue
                
            # By this point, `file_path` is either a regular file or a valid symlink that
            # we are allowed to follow. is_binary() will resolve it to check content.
            if is_binary(file_path):
                continue
                
            files_to_cat.append(file_path)

    # --- Build Final Output (unchanged) ---
    output_parts = [f"Current path: {root_dir}\n"]
    
    try:
        if shutil.which("tree"):
            tree_cmd = ["tree"] + [arg for p in unique_ignore_patterns for arg in ["-I", p]]
            if follow_links:
                tree_cmd.append("-l")
            tree_output = "Directory tree (ignoring specified patterns):\n"
            tree_output += subprocess.check_output(tree_cmd, cwd=root_dir, text=True, stderr=subprocess.DEVNULL)
        else:
            tree_output = "Directory tree: ('tree' command not found, skipping)"
    except Exception as e:
        tree_output = f"Directory tree: (failed to generate: {e})"
        
    output_parts.append(tree_output)
    output_parts.append("\n\n---\nCombined file contents:\n")

    if not files_to_cat:
        output_parts.append("No text files found to copy after applying ignore patterns.")
    else:
        for file_path in sorted(files_to_cat):
            try:
                # open() follows symlinks by default. This is now safe because we only
                # add symlinks to `files_to_cat` when `follow_links` is True.
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    output_parts.append(f"\n--- FILE: {file_path.relative_to(root_dir)} ---\n")
                    output_parts.append(content)
            except Exception as e:
                output_parts.append(f"\n--- ERROR: Could not read {file_path.relative_to(root_dir)}: {e} ---\n")
    
    summary_lines = []
    if activated_presets:
        summary_lines.append("Activated presets:")
        for preset in sorted(list(activated_presets)):
            summary_lines.append(f"  - {preset}")

    final_output = "".join(output_parts)
    status_report = "\n".join(status_lines)
    summary_report = "\n".join(summary_lines)
    
    # return final_output, f"{summary_report}",  f"{status_report}"
    return final_output, f"{status_report}\n{summary_report}"