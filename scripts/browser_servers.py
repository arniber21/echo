"""Run browser-test servers with independent Nuxt output and temporary SQLite data."""

import os
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from dev import ROOT, main

if __name__ == "__main__":
    with TemporaryDirectory(prefix="rewind-browser-") as directory:
        temporary = Path(directory)
        frontend = temporary / "frontend"
        shutil.copytree(
            ROOT / "frontend",
            frontend,
            ignore=shutil.ignore_patterns("node_modules", ".nuxt", ".output", ".git"),
        )
        (frontend / "node_modules").symlink_to(
            ROOT / "frontend/node_modules", target_is_directory=True
        )
        os.environ["DATA_DIR"] = str(temporary / "data")
        os.environ["REWIND_FRONTEND_DIR"] = str(frontend)
        os.environ["REWIND_ANALYSIS_MODE"] = "mock"
        sys.exit(main())
