# viopi_utils.py
# Shared utilities and core logic for the Viopi project context generator.

import os
import sys
import fnmatch
from pathlib import Path
import subprocess
import magic
import shutil

# --- Configuration ---
LOCAL_IGNORE_FILES = (".copy_combine_ignore", ".viopi_ignore")
GLOBAL_IGNORE_FILES = (
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

def is_binary(file_path: Path) -> bool:
    """
    Determines if a file is binary by checking its MIME type and content.
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
        pass # Fallback to content check
    try:
        with open(real_path, "r", encoding="utf-8") as f:
            f.read(1024)
        return False
    except (UnicodeDecodeError, IOError):
        return True

def get_preset_patterns(preset_name: str) -> list[str]:
    """
    Loads ignore patterns from a preset file in the user's home directory.
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

def generate_project_context(
    scan_dir: Path,
    ignore_search_root: Path,
    custom_patterns: list[str],
    follow_links: bool
) -> tuple[str, str]:
    """
    Walks scan_dir, finds text files respecting a cascade of .viopi_ignore
    files up to ignore_search_root, generates context, and returns it.
    """
    status_lines = []
    
    base_patterns = {
        ".DS_Store", ".git", *LOCAL_IGNORE_FILES, Path(__file__).name,
        "viopi", "_viopi_output*.viopi"
    }
    sources_of_ignores = {"Defaults": sorted(list(base_patterns))}

    for ignore_file in GLOBAL_IGNORE_FILES:
        if ignore_file.is_file():
            patterns = [p for p in ignore_file.read_text().splitlines() if p.strip() and not p.strip().startswith("#")]
            if patterns:
                sources_of_ignores[f"Global: {ignore_file.name}"] = sorted(patterns)
                base_patterns.update(patterns)

    activated_presets = set()
    literal_args = []
    for arg in custom_patterns:
        preset_to_check = PRESET_ALIASES.get(arg, arg)
        patterns = get_preset_patterns(preset_to_check)
        if patterns:
            activated_presets.add(arg)
            sources_of_ignores[f"Preset: {arg}"] = sorted(patterns)
            base_patterns.update(patterns)
        else:
            literal_args.append(arg)
    
    if literal_args:
        sources_of_ignores["Arguments"] = sorted(literal_args)
        base_patterns.update(literal_args)

    files_to_cat = []
    ignore_patterns_cache = {}

    def _load_and_get_patterns_for_path(path: Path) -> set:
        if path in ignore_patterns_cache:
            return ignore_patterns_cache[path]

        if path == ignore_search_root or not ignore_search_root in path.parents:
            parent_patterns = base_patterns
        else:
            parent_patterns = _load_and_get_patterns_for_path(path.parent)

        current_patterns = set(parent_patterns)
        for fname in LOCAL_IGNORE_FILES:
            local_ignore_file = path / fname
            if local_ignore_file.is_file():
                try:
                    new_patterns = {p for p in local_ignore_file.read_text().splitlines() if p.strip() and not p.strip().startswith("#")}
                    if new_patterns:
                        current_patterns.update(new_patterns)
                        source_key = f"Local: {local_ignore_file.relative_to(ignore_search_root)}"
                        if source_key not in sources_of_ignores:
                             sources_of_ignores[source_key] = sorted(list(new_patterns))
                except Exception:
                    pass
        
        ignore_patterns_cache[path] = current_patterns
        return current_patterns

    for root, dirs, files in os.walk(scan_dir, topdown=True, followlinks=follow_links):
        current_path = Path(root)
        active_patterns = _load_and_get_patterns_for_path(current_path)

        dirs[:] = [d for d in dirs if not any(
            fnmatch.fnmatch(d, p) or fnmatch.fnmatch(str((current_path / d).relative_to(ignore_search_root)), p)
            for p in active_patterns
        )]
        
        for filename in files:
            file_path = current_path / filename
            if not follow_links and file_path.is_symlink():
                continue

            rel_path_str = str(file_path.relative_to(ignore_search_root))
            if any(fnmatch.fnmatch(filename, p) or fnmatch.fnmatch(rel_path_str, p) for p in active_patterns):
                continue
            
            if is_binary(file_path):
                continue
                
            files_to_cat.append(file_path)

    status_lines.append("🔎 Applying ignore patterns from the following sources (in order):")
    for source, patterns in sorted(sources_of_ignores.items()):
        status_lines.append(f"  - From {source}:")
        for p in patterns:
            status_lines.append(f"    - {p}")
    status_lines.append("----------------------------------------")
    
    output_parts = [f"Directory Processed: {scan_dir}\n"]
    if scan_dir != ignore_search_root:
        output_parts.append(f"Ignore Rules Root: {ignore_search_root}\n")
    
    try:
        if shutil.which("tree"):
            all_patterns = set().union(*sources_of_ignores.values())
            tree_cmd = ["tree"] + [arg for p in sorted(list(all_patterns)) for arg in ["-I", p]]
            if follow_links:
                tree_cmd.append("-l")
            tree_output = "Directory tree (ignoring specified patterns):\n"
            tree_output += subprocess.check_output(tree_cmd, cwd=scan_dir, text=True, stderr=subprocess.DEVNULL)
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
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    output_parts.append(f"\n--- FILE: {file_path.relative_to(scan_dir)} ---\n")
                    output_parts.append(content)
            except Exception as e:
                output_parts.append(f"\n--- ERROR: Could not read {file_path.relative_to(scan_dir)}: {e} ---\n")
    
    summary_lines = []
    if activated_presets:
        summary_lines.append("Activated presets:")
        for preset in sorted(list(activated_presets)):
            summary_lines.append(f"  - {preset}")

    final_output = "".join(output_parts)
    status_report = "\n".join(status_lines)
    summary_report = "\n".join(summary_lines)
    
    return final_output, f"{status_report}\n{summary_report}"

    
import os                                                                                                               
import fnmatch                                                                                                          
import magic # from python-magic                                                                                        
                                                                                                                        
def read_ignore_file(path):                                                                                             
    """Reads a .gitignore-style file and returns a list of patterns."""                                                 
    patterns = []                                                                                                       
    if os.path.exists(path):                                                                                            
        with open(path, 'r', encoding='utf-8') as f:                                                                    
            for line in f:                                                                                              
                line = line.strip()                                                                                     
                if line and not line.startswith('#'):                                                                   
                    patterns.append(line)                                                                               
    return patterns                                                                                                     
                                                                                                                        
def is_binary(filepath):                                                                                                
    """Check if a file is binary using python-magic."""                                                                 
    try:                                                                                                                
        mime_type = magic.from_file(filepath, mime=True)                                                                
        return not mime_type.startswith('text/')                                                                        
    except magic.MagicException:                                                                                        
        # If magic fails, fall back to a simpler check                                                                  
        try:                                                                                                            
            with open(filepath, 'r', encoding='utf-8') as f:                                                            
                f.read(1024) # Try to read some text                                                                    
            return False                                                                                                
        except UnicodeDecodeError:                                                                                      
            return True                                                                                                 
    return False                                                                                                        
                                                                                                                        

def get_file_list(root_dir: str, patterns: list[str], follow_links: bool) -> list[str]:
    """
    Finds all files in a directory matching given glob patterns, respecting .gitignore.
    (This is a sample implementation, assuming you have .gitignore parsing elsewhere)
    """
    root_path = Path(root_dir)
    # is_ignored = get_gitignore_checker(root_path) # Your existing ignore logic here

    all_files = set()

    if not patterns:
        # Default behavior: find all non-ignored files if no pattern is given
        # This emulates a "find all" behavior.
        patterns = ["**/*"]

    for pattern in patterns:
        # rglob searches recursively.
        # Set follow_symlinks based on the --no-follow-links flag.
        # Note: glob doesn't have a direct 'follow_links' param, this is a simplification.
        # For true symlink following control, you might need os.walk.
        # However, for many cases, this is sufficient.
        
        # A more robust way using os.walk:
        for dirpath, dirnames, filenames in os.walk(root_dir, followlinks=follow_links):
            # Prune ignored directories to walk faster
            # dirnames[:] = [d for d in dirnames if not is_ignored(Path(dirpath) / d)]
            
            for filename in filenames:
                file_path = Path(dirpath) / filename
                # if not is_ignored(file_path) and file_path.match(pattern):
                #     all_files.add(str(file_path.resolve()))
                
                # Simplified version without ignore logic for clarity:
                if file_path.match(pattern):
                     # Add absolute path to avoid duplicates
                    all_files.add(str(file_path.resolve()))

    # Return a sorted list of unique file paths
    return sorted(list(all_files))
                                                                                          
                                                                                                                        
def generate_tree_output(root_dir: str, file_list: list[str]) -> str:
    """
    Generates a string representing the file tree.
    (Your existing implementation can likely stay the same)
    """                                                   
    tree_str = "Directory tree (ignoring specified patterns):\n"                                                        
    structure = {}                                                                                                      
                                                                                                                        
    for path in file_list:                                                                                              
        relative_path = os.path.relpath(path, root_dir)                                                                 
        parts = relative_path.split(os.sep)                                                                             
        current_level = structure                                                                                       
        for part in parts:                                                                                              
            current_level = current_level.setdefault(part, {})                                                          
                                                                                                                        
    def build_tree_lines(d, prefix=""):                                                                                 
        lines = []                                                                                                      
        entries = sorted(d.keys())                                                                                      
        for i, entry in enumerate(entries):                                                                             
            connector = "├── " if i < len(entries) - 1 else "└── "                                                      
            lines.append(f"{prefix}{connector}{entry}")                                                                 
            if d[entry]:                                                                                                
                extension = "│   " if i < len(entries) - 1 else "    "                                                  
                lines.extend(build_tree_lines(d[entry], prefix=prefix + extension))                                     
        return lines                                                                                                    
                                                                                                                        
    tree_str += ".\n"                                                                                                   
    tree_str += "\n".join(build_tree_lines(structure))                                                                  
                                                                                                                        
    # Count directories from the generated tree structure                                                               
    dir_count = str(tree_str).count('├── ') + str(tree_str).count('└── ') - len(file_list)                              
    file_count = len(file_list)                                                                                         
                                                                                                                        
    tree_str += f"\n\n{dir_count} directories, {file_count} files"                                                      
    return tree_str      