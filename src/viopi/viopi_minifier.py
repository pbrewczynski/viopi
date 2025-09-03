# viopi_minifier.py
# Handles minification of various code files to reduce token count.

from pathlib import Path
from . import viopi_printer
import json

# --- Minifier Imports (with fallbacks) ---
# These are optional dependencies. The tool will function without them,
# but the --minify feature for the corresponding file type will be disabled.
try:
    import python_minifier
except ImportError:
    python_minifier = None

try:
    import jsmin
except ImportError:
    jsmin = None

try:
    import csscompressor
except ImportError:
    csscompressor = None

try:
    import htmlmin
except ImportError:
    htmlmin = None

# A set to keep track of which missing minifier warnings have been shown.
_minifiers_warned = set()

def _check_minifier_availability(lang: str, library_module, library_name: str) -> bool:
    """Helper to print a one-time warning if a minifier library is missing."""
    if library_module is None:
        if lang not in _minifiers_warned:
            viopi_printer.print_warning(
                f"Minification for '{lang}' is skipped. To enable, install the '{library_name}' "
                f"package (e.g., 'pip install {library_name}')."
            )
            _minifiers_warned.add(lang)
        return False
    return True

def minify_content(content: str, filename: str) -> str:
    """
    Minifies the given content based on the filename's extension.
    If a corresponding minifier is not installed or an error occurs during
    minification, it returns the original content.
    """
    suffix = Path(filename).suffix.lower()

    try:
        if suffix == ".py":
            if _check_minifier_availability("python", python_minifier, "python-minifier"):
                # remove_literal_statements is great for removing docstrings and other literals
                return python_minifier.minify(content, remove_literal_statements=True)
        elif suffix == ".js":
            if _check_minifier_availability("javascript", jsmin, "jsmin"):
                return jsmin.jsmin(content)
        elif suffix == ".css":
            if _check_minifier_availability("css", csscompressor, "csscompressor"):
                return csscompressor.compress(content)
        elif suffix == ".html":
            if _check_minifier_availability("html", htmlmin, "htmlmin"):
                return htmlmin.minify(content, remove_comments=True, remove_empty_space=True)
        elif suffix == ".json":
            # JSON minification is just compact encoding. No external library needed.
            return json.dumps(json.loads(content), separators=(',', ':'))

    except Exception as e:
        # This catches errors from the minifier libraries (e.g., syntax error in the file)
        viopi_printer.print_warning(f"Could not minify {filename}: {e}. Using original content.")
        return content

    # If no minifier was found or applied for this file type, return original content
    return content