"""Load the standalone ChatOps package from any verifier working directory."""

from __future__ import annotations

import os
import sys
from pathlib import Path


repository = Path(os.environ.get("INSIGHTHUB_REPO_ROOT", Path(__file__).parents[3])).resolve()
chatops_root = repository / "chatops-bot"
if str(chatops_root) not in sys.path:
    sys.path.insert(0, str(chatops_root))
