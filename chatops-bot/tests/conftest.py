from __future__ import annotations

import sys
from pathlib import Path


chatops_root = Path(__file__).parents[1]
if str(chatops_root) not in sys.path:
    sys.path.insert(0, str(chatops_root))
