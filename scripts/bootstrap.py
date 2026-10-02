"""Create an isolated environment on Windows, macOS, or Linux."""

import argparse
import subprocess
import sys
import venv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", action="store_true", help="Install optional local .dem parser")
    parser.add_argument("--dev", action="store_true", help="Install pytest and Ruff")
    args = parser.parse_args()
    if sys.version_info < (3, 11):  # noqa: UP036 -- bootstrap can run before package installation
        raise SystemExit("Python 3.11 or newer is required")
    root = Path(__file__).resolve().parents[1]
    environment = root / ".venv"
    if not (environment / "pyvenv.cfg").is_file():
        venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    extras = [name for name, enabled in (("replay", args.replay), ("dev", args.dev)) if enabled]
    requirement = "." + ("[" + ",".join(extras) + "]" if extras else "")
    subprocess.run([str(python), "-m", "pip", "install", "-e", requirement], cwd=root, check=True)
    print("Ready. Run: python coach.py demo")


if __name__ == "__main__":
    main()
