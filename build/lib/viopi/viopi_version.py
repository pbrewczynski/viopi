# viopi_version.py
# Handles version detection and display for the Viopi project.

import sys
from pathlib import Path
import importlib.metadata

# --- TOML Parsing (for development fallback) ---
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

def get_project_version() -> str:
    """Retrieves the project version from package metadata or pyproject.toml."""
    try:
        # First, try the standard way for an installed package
        return importlib.metadata.version("viopi")
    except importlib.metadata.PackageNotFoundError:
        # Fallback for development: search for pyproject.toml
        if tomllib is None:
            return "0.0.0-dev (tomli not found)"
        try:
            # Start from this file's location and go up
            current_dir = Path(__file__).resolve().parent
            while current_dir != current_dir.parent: # Stop at the filesystem root
                pyproject_path = current_dir / 'pyproject.toml'
                if pyproject_path.exists():
                    with open(pyproject_path, "rb") as f:
                        data = tomllib.load(f)
                    return data.get("project", {}).get("version", "0.0.0-dev (version missing)")
                current_dir = current_dir.parent
            return "0.0.0-dev (pyproject.toml not found)"
        except Exception:
            return "0.0.0-dev (pyproject parse error)"

def print_version_and_exit():
    """Prints the formatted version string and exits the program."""
    version = get_project_version()
    print(f"viopi version {version}")
    sys.exit(0)