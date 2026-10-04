"""Run the repository checks using the checkout's virtual environment when available."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("all", "engineering", "learning"), default="all")
    args = parser.parse_args()
    environment = ROOT / ".venv"
    installed = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    python = str(installed) if installed.is_file() else sys.executable
    commands = []
    if args.scope in ("all", "engineering"):
        commands.extend(
            [
                [python, "-m", "ruff", "check", "."],
                [python, "-m", "ruff", "format", "--check", "."],
                [python, "-m", "pytest", "-q"],
            ]
        )
    if args.scope in ("all", "learning"):
        commands.append([python, "-m", "unittest", "discover", "-s", "learning/tests", "-q"])
        node = shutil.which("node")
        if node:
            commands.extend(
                [
                    [node, "--check", "learning/assets/learning.js"],
                    [node, "learning/tests/test_labs.cjs"],
                ]
            )
        else:
            print(
                "Node.js unavailable: JavaScript checks skipped; CI runs them with Node 22.",
                flush=True,
            )
    for command in commands:
        print("Running: " + " ".join(command), flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
