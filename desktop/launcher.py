"""Double-click entrypoint: start Streamlit from the bundled (or repo) root directory.

When frozen with PyInstaller, `sys._MEIPASS` points at the folder that contains `app.py`,
`contagion/`, and `design/`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def main() -> int:
    root = project_root()
    os.chdir(root)
    app_py = root / "app.py"
    if not app_py.is_file():
        sys.stderr.write(f"Missing app.py — expected at:\n  {app_py}\n")
        return 1

    args = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_py),
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
    ]
    return subprocess.call(args, cwd=str(root))


if __name__ == "__main__":
    raise SystemExit(main())
