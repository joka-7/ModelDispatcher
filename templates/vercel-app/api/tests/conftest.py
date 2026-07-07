"""Put the ``api/`` directory on ``sys.path`` so ``_lib`` imports resolve.

On Vercel the function's own directory is already importable; locally we add it
here so ``pytest`` can exercise the wrapper the same way.
"""

from __future__ import annotations

import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parent.parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))
