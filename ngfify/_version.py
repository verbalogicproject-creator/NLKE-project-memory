"""Single source of truth for the package version (avoids an import cycle
between `ngfify/__init__.py` and `ngfify/pipeline.py`, both of which need it).
"""

from __future__ import annotations

__version__ = "0.1.1"
