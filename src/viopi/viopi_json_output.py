# viopi_json_output.py
# Handles the generation of JSON formatted output for Viopi.

import json

def generate_json_output(stats: dict, file_data_list: list) -> str:
    """
    Formats the collected project data into a JSON string.

    Args:
        stats: A dictionary containing statistics (total files, lines, chars).
        file_data_list: A list of dictionaries, where each dictionary
                        represents a file with its path and content.

    Returns:
        A pretty-printed JSON string representing the project data.
    """
    output_data = {
        "stats": stats,
        "files": file_data_list
    }
    # Use indent for pretty-printing the JSON
    return json.dumps(output_data, indent=2)