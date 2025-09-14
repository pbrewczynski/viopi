

# viopi_help.py
# Displays the help message for the Viopi project.

import sys

def print_help_and_exit(version: str, basename: str, extension: str, append_filename: str):
    """
    Prints the detailed help and usage message, then exits.

    Args:
        version: The current version string of the program.
        basename: The base name for output files.
        extension: The extension for output files.
        append_filename: The specific filename used for appending.
    """
    help_text = f"""
viopi v{version}
A tool for preparing project context for LLMs by concatenating files.

Usage:
  viopi [options] [path] [pattern_1] [pattern_2] ...

Default Behavior:
  Creates a new, versioned output file on each run (e.g., {basename}_1{extension},
  {basename}_2{extension}, etc.) to prevent accidental overwrites.

Options:
  -h, --help            Show this help message and exit.
  -v, --version         Show the version number and exit.

  --stdout              Print formatted text output to stdout instead of a file.
  --copy                Copy formatted text output to the system clipboard.
  --json                Output the data in JSON format to stdout.

  --append              Appends formatted text output to the base file `{append_filename}`
                        instead of creating a new versioned file.

  --minify              Minify code (JS, CSS, Py, HTML, JSON) to reduce token count.
                        Requires optional dependencies (e.g., 'pip install jsmin').

  --no-follow-links     Disable following symbolic links.

Examples:
  # Process current directory, save to a new versioned file (e.g., _viopi_output_1.viopi)
  viopi

  # Append JS file contexts to the base _viopi_output.viopi file
  viopi --append src/app/ '**/*.js'

  # Pipe context to another tool
  viopi --stdout | llm -s "Summarize this"

  # Get structured JSON output and save it to a file
  viopi --json src/api > api_context.json
"""
    print(help_text)
    sys.exit(0)