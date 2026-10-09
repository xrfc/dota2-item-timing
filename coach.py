"""Cross-platform launcher; automatically uses this checkout's virtual environment."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

if __name__ == "__main__":
    if PYTHON.is_file() and Path(sys.prefix).resolve() != VENV.resolve():
        raise SystemExit(
            subprocess.call([str(PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
        )
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from dota_items.workflow.cli import main
    except ImportError as error:
        raise SystemExit("Missing dependencies. Run: python scripts/bootstrap.py") from error
    raise SystemExit(main())
