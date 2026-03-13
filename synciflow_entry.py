from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
src_dir = project_root / "src"
if src_dir.is_dir():
    sys.path.insert(0, str(src_dir))

from synciflow.cli.main import run

if __name__ == "__main__":
    run()
