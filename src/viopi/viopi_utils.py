import argparse
import os
import shutil
import sys

from .constants import C
from .config import load_configuration
from .prompt import build_prompt_parts
from .client import generate_response
from .output import (
    handle_output,
    print_configuration_summary,
    print_payload_summary,
    print_request_summary
)
from .utils import get_project_version

def parse_arguments(config):
    """Parses command-line arguments, using loaded config for defaults."""
    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        description=(
            "A powerful, full-featured CLI for Google's Gemini models. \n"
            "Prompt can be provided in three ways (in order of precedence):\n"
            "1. Piped from stdin (e.g., `cat file.txt | gemi`)\n"
            "2. Using the -p/--prompt flag (e.g., `gemi -p 'my prompt'`)\n"
            "3. As positional arguments (e.g., `gemi my prompt text`)"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    # Argument definitions
    parser.add_argument("prompt_positional", nargs='*', help="The text prompt as positional arguments. Used if -p/--prompt is not set.")
    parser.add_argument("-p", "--prompt", help="The text prompt. Takes precedence over positional arguments.")
    parser.add_argument("-f", "--file", dest="files", action="append", default=[], help="Path to a file for the prompt. Can be used multiple times.")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {get_project_version()}")
    parser.add_argument("-o", "--output", help="Path to save response to a file.")
    parser.add_argument("--open", action="store_true", help="Open the response in a temporary markdown file (macOS only).")
    parser.add_argument("-c", "--profile", help="Configuration profile to use.")
    parser.add_argument("-x", "--context", action="store_true", help="Enable context from config (prefix, postfix, context_script). Default is disabled.")

    # Model and connection settings
    parser.add_argument("--project", default=config.get('project'), help="Google Cloud project ID.")
    parser.add_argument("--location", default=config.get('location'))
    parser.add_argument("--model", default=config.get('model_name'), dest='model_name')
    parser.add_argument("-t", "--temperature", type=float, default=float(config.get('temperature')))
    parser.add_argument("--max-tokens", type=int, default=int(config.get('max_output_tokens')), dest='max_output_tokens')
    parser.add_argument("--top-p", type=float, default=float(config.get('top_p')))
    parser.add_argument("--top-k", type=int, default=int(config.get('top_k')))

    # Context and output settings
    parser.add_argument("--prefix-prompt", default=config.get('prefix_prompt'))
    parser.add_argument("--postfix-prompt", default=config.get('postfix_prompt'))
    parser.add_argument("--context-script", default=config.get('context_script'), help="Script whose stdout is injected as text context.")
    parser.add_argument("--output-formatter", default=config.get('output_formatter'))
    parser.add_argument("--no-show-payload", action="store_true", help="Do not print the final payload.")
    parser.add_argument("--debug", action="store_true", help="Enable verbose payload output and write out-debug.json.")

    args, unknown = parser.parse_known_args()

    # In viopi mode, we expect unknown args (they are for viopi). Otherwise, it's an error.
    is_viopi_context = 'gemiv' in os.path.basename(sys.argv[0])
    if unknown and not is_viopi_context:
        # Re-run with the standard parser to get the default error message for unrecognized args.
        parser.parse_args()

    return args

def _run_gemi():
    """Core logic for the gemi/gemiv commands."""
    # Two-pass argument parsing for --profile
    profile_parser = argparse.ArgumentParser(add_help=False)
    profile_parser.add_argument("-c", "--profile")
    profile_args, _ = profile_parser.parse_known_args()

    config = load_configuration(profile_name=profile_args.profile)
    args = parse_arguments(config)

    if not args.project:
        sys.exit(f"{C.RED}Error: Google Cloud project ID is not set. Use --project or set in config.{C.END}")

    if 'gemiv' not in os.path.basename(sys.argv[0]):
        print_configuration_summary(args)

    prompt_parts, payload_metadata = build_prompt_parts(args)
    if not prompt_parts:
        sys.exit(f"{C.RED}Error: Prompt is empty. Provide text, pipe from stdin, or attach files.{C.END}")

    if not args.no_show_payload:
        print_payload_summary(args, payload_metadata)

    full_response = generate_response(args, prompt_parts)

    handle_output(full_response, args)

    print_request_summary(payload_metadata.get("prompt_components", {}))

def main():
    """Entry point for the `gemi` command."""
    try:
        _run_gemi()
    except Exception as e:
        sys.exit(f"\n{C.RED}An unexpected application error occurred: {e}{C.END}")

def main_viopi_context():
    """Entry point for `gemiv` - injects viopi context."""
    if not shutil.which("viopi"):
        sys.exit(f"{C.RED}Error: The 'gemiv' command requires 'viopi' to be installed and in your PATH.{C.END}")

    # Build viopi command from all args, then pass them through to the main parser.
    # This allows passing viopi-specific args, e.g., `gemiv -l python -- "prompt"`
    viopi_command = " ".join(["viopi", "--stdout"] + sys.argv[1:])
    original_args = sys.argv[1:]

    # Rebuild argv for the main parser
    sys.argv = [sys.argv[0], "--context", "--context-script", viopi_command] + original_args
    main()

def main_open():
    """Entry point for `gemio` - forces --open behavior."""
    # Inject --open argument before parsing
    sys.argv.insert(1, "--open")
    main()

def main_viopi_context_open():
    """Entry point for `gemivo` - injects viopi context and forces --open."""
    if not shutil.which("viopi"):
        sys.exit(f"{C.RED}Error: The 'gemivo' command requires 'viopi' to be installed and in your PATH.{C.END}")

    # Build viopi command from all args, then pass them through to the main parser.
    # This allows passing viopi-specific args, e.g., `gemivo -l python -- "prompt"`
    viopi_command = " ".join(["viopi", "--stdout"] + sys.argv[1:])
    original_args = sys.argv[1:]

    # Rebuild argv for the main parser
    sys.argv = [sys.argv[0], "--open", "--context", "--context-script", viopi_command] + original_args
    main()