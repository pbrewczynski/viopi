# viopi_printer.py
# Handles all user-facing print statements and status reports.

def _format_bytes(size_bytes: int, precision: int = 2) -> str:
    """Converts a size in bytes to a human-readable string (KB, MB, etc.)."""
    if size_bytes == 0:
        return "0 B"
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    power = 1024
    i = 0
    while size_bytes >= power and i < len(units) - 1:
        size_bytes /= power
        i += 1
    return f"{size_bytes:.{precision}f} {units[i]}"

def _print_stats(stats: dict):
    """Prints the formatted statistics block."""
    payload_size_str = _format_bytes(stats.get("payload_size_bytes", 0))
    
    print("-" * 20)
    print("Viopi Run Statistics:")
    print(f"  - Files Processed:  {stats.get('total_files', 0)}")
    print(f"  - Files Ignored:    {stats.get('files_ignored', 0)}")
    print(f"  - Total Lines:      {stats.get('total_lines', 0)}")
    print(f"  - Total Characters: {stats.get('total_characters', 0)}")
    print(f"  - Payload Size:     {payload_size_str}")
    print("-" * 20)

def print_success_copy(stats: dict):
    """Prints the success message and stats for clipboard copy."""
    print("Viopi output copied to clipboard.")
    _print_stats(stats)

def print_success_file(stats: dict, filename: str):
    """Prints the success message and stats for file save."""
    print(f"Output saved to {filename}")
    _print_stats(stats)

def print_success_append(stats: dict, filename: str):
    """Prints the success message and stats for file append."""
    print(f"Output appended to {filename}")
    _print_stats(stats)

def print_error(message: str, is_fatal: bool = True):
    """Prints a formatted error message."""
    import sys
    print(f"Error: {message}", file=sys.stderr)
    if is_fatal:
        sys.exit(1)

def print_warning(message: str):
    """Prints a formatted warning message."""
    import sys
    print(f"Warning: {message}", file=sys.stderr)