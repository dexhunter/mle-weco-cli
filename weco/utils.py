from typing import Any, Dict, List, Tuple, Union
import json
import os
import time
import subprocess
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
import pathlib
import requests
from packaging.version import parse as parse_version


# Env/arg helper functions
def read_api_keys_from_env() -> Dict[str, Any]:
    """Read API keys from environment variables."""
    keys = {}
    keys_to_check = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
    for key in keys_to_check:
        value = os.getenv(key)
        if value is not None and len(value) > 0:
            keys[key] = value
    return keys


def determine_default_model(llm_api_keys: Dict[str, Any]) -> str:
    """Determine the default model based on available API keys.

    Uses priority: OpenAI > Anthropic > Gemini

    Args:
        llm_api_keys: Dictionary of available LLM API keys

    Returns:
        str: The default model name to use

    Raises:
        ValueError: If no LLM API keys are found
    """
    if "OPENAI_API_KEY" in llm_api_keys:
        return "o4-mini"
    elif "ANTHROPIC_API_KEY" in llm_api_keys:
        return "claude-sonnet-4-0"
    elif "GEMINI_API_KEY" in llm_api_keys:
        return "gemini-2.5-pro"
    else:
        raise ValueError(
            "No LLM API keys found in environment. Please set one of the following: OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY."
        )


def read_additional_instructions(additional_instructions: str | None) -> str | None:
    """Read additional instructions from a file path string or return the string itself."""
    if additional_instructions is None:
        return None

    # Try interpreting as a path first
    potential_path = pathlib.Path(additional_instructions)
    try:
        if potential_path.exists() and potential_path.is_file():
            return read_from_path(potential_path, is_json=False)  # type: ignore # read_from_path returns str when is_json=False
        else:
            # If it's not a valid file path, return the string itself
            return additional_instructions
    except OSError:
        # If the path can't be read, return the string itself
        return additional_instructions


# File helper functions
def read_from_path(fp: pathlib.Path, is_json: bool = False) -> Union[str, Dict[str, Any]]:
    """Read content from a file path, optionally parsing as JSON."""
    with fp.open("r", encoding="utf-8") as f:
        if is_json:
            return json.load(f)
        return f.read()


def write_to_path(fp: pathlib.Path, content: Union[str, Dict[str, Any]], is_json: bool = False) -> None:
    """Write content to a file path, optionally as JSON."""
    with fp.open("w", encoding="utf-8") as f:
        if is_json:
            json.dump(content, f, indent=4)
        elif isinstance(content, str):
            f.write(content)
        else:
            raise TypeError("Content must be str or Dict[str, Any]")


# Visualization helper functions
def format_number(n: Union[int, float]) -> str:
    """Format large numbers with K, M, B, T suffixes for better readability."""
    if n >= 1e12:
        return f"{n / 1e12:.1f}T"
    elif n >= 1e9:
        return f"{n / 1e9:.1f}B"
    elif n >= 1e6:
        return f"{n / 1e6:.1f}M"
    elif n >= 1e3:
        return f"{n / 1e3:.1f}K"
    # Handle potential floats that don't need suffix but might need formatting
    if isinstance(n, float):
        # Format floats nicely, avoid excessive precision unless needed
        return f"{n:.4g}"  # Use general format, up to 4 significant digits
    return str(n)


def smooth_update(
    live: Live, layout: Layout, sections_to_update: List[Tuple[str, Panel]], transition_delay: float = 0.05
) -> None:
    """
    Update sections of the layout with a small delay between each update for a smoother transition effect.

    Args:
        live: The Live display instance
        layout: The Layout to update
        sections_to_update: List of (section_name, content) tuples to update
        transition_delay: Delay in seconds between updates (default: 0.05)
    """
    for section, content in sections_to_update:
        layout[section].update(content)
        live.refresh()
        time.sleep(transition_delay)


# Other helper functions
DEFAULT_MAX_LINES = 50
DEFAULT_MAX_CHARS = 5000

def truncate_output(output: str, max_lines: int = DEFAULT_MAX_LINES, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Truncate the output to a reasonable size."""
    lines = output.splitlines()
    # Determine what truncations are needed based on original output
    lines_truncated = len(lines) > max_lines
    chars_truncated = len(output) > max_chars
    # Apply truncations to the original output
    if lines_truncated:
        output = "\n".join(lines[-max_lines:])
    if chars_truncated:
        output = output[-max_chars:]
    # Add prefixes for truncations that were applied
    prefixes = []
    if lines_truncated:
        prefixes.append(f"truncated to last {max_lines} lines")
    if chars_truncated:
        prefixes.append(f"truncated to last {max_chars} characters")
    if prefixes:
        prefix_text = ", ".join(prefixes)
        output = f"... ({prefix_text})\n{output}"
    return output

def run_evaluation(eval_command: str) -> str:
    """Run the evaluation command on the code and return the output."""

    # Run the eval command as is
    result = subprocess.run(eval_command, shell=True, capture_output=True, text=True, check=False)

    # Combine stdout and stderr for complete output
    output = result.stderr if result.stderr else ""
    if result.stdout:
        if len(output) > 0:
            output += "\n"
        output += result.stdout
    return truncate_output(output)


# Update Check Function
def check_for_cli_updates():
    """Checks PyPI for a newer version of the weco package and notifies the user."""
    try:
        from . import __pkg_version__

        pypi_url = "https://pypi.org/pypi/weco/json"
        response = requests.get(pypi_url, timeout=5)  # Short timeout for non-critical check
        response.raise_for_status()
        latest_version_str = response.json()["info"]["version"]

        current_version = parse_version(__pkg_version__)
        latest_version = parse_version(latest_version_str)

        if latest_version > current_version:
            yellow_start = "\033[93m"
            reset_color = "\033[0m"
            message = f"WARNING: New weco version ({latest_version_str}) available (you have {__pkg_version__}). Run: pip install --upgrade weco"
            print(f"{yellow_start}{message}{reset_color}")
            time.sleep(2)  # Wait for 2 second

    except requests.exceptions.RequestException:
        # Silently fail on network errors, etc. Don't disrupt user.
        pass
    except (KeyError, ValueError):
        # Handle cases where the PyPI response format might be unexpected
        pass
    except Exception:
        # Catch any other unexpected error during the check
        pass
