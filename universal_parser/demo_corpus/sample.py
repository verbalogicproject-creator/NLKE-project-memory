"""A tiny Python sample for the code-heuristic parser."""

import json
from pathlib import Path


def load_config(path):
    """Load a config file and return its parsed contents."""
    with open(path) as f:
        return json.load(f)


class ConfigLoader:
    """Wraps `load_config` with a default search path."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
