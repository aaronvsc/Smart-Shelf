"""Builds the two folders the professor asks for: Selected/ (Architecture A) and Unselected/ (B).

Each folder is a complete, separate copy of Smart-Shelf with only one architecture:
its source code, the shared code, the UI, the data, its tests, compiled Python
bytecode (compiled/), and one-click launchers for Mac, Linux and Windows.

Run from the Smart-Shelf folder after any code change, then commit both folders:
    .venv/bin/python scripts/build_release.py
"""
from __future__ import annotations

import py_compile
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RELEASES = {
    # folder: (architecture kept, architecture left out, name shown to the TA)
    "Selected": ("arch_a", "arch_b", "Architecture A: Pipe-and-Filter"),
    "Unselected": ("arch_b", "arch_a", "Architecture B: Blackboard"),
}
# Tests that need both architectures at once, so they only make sense in our working repo.
BOTH_ARCHITECTURE_TESTS = ["arch_b/test_acceptance.py", "ui/test_one_architecture.py"]
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".gitkeep", "user_profiles")


def copy_common(out: Path, keep: str, drop: str) -> None:
    """Source code, data, settings and tests for one architecture."""
    shutil.copytree(ROOT / "smart_shelf", out / "smart_shelf",
                    ignore=shutil.ignore_patterns(drop, "__pycache__", "*.pyc", ".DS_Store", ".gitkeep"))
    shutil.copytree(ROOT / "data", out / "data", ignore=SKIP)
    shutil.copytree(ROOT / ".streamlit", out / ".streamlit", ignore=SKIP)
    (out / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "check_data.py", out / "scripts" / "check_data.py")
    for name in ("requirements.txt", "pytest.ini"):
        shutil.copy(ROOT / name, out / name)

    tests = out / "tests"
    for part in ("common", "ui", keep):
        shutil.copytree(ROOT / "tests" / part, tests / part, ignore=SKIP)
    for path in BOTH_ARCHITECTURE_TESTS:
        (tests / path).unlink(missing_ok=True)


def compile_code(out: Path) -> int:
    """compiled/: every source file turned into Python 3.12 bytecode (.pyc), same folder layout."""
    count = 0
    for source in sorted((out / "smart_shelf").rglob("*.py")):
        relative = source.relative_to(out)
        py_compile.compile(str(source), cfile=str(out / "compiled" / relative.with_suffix(".pyc")),
                           dfile=str(relative), doraise=True)
        count += 1
    return count


def write_launchers(out: Path, title: str) -> None:
    """One double-click file per system. The first run sets up a private Python environment."""
    unix = f"""#!/bin/bash
# Starts Smart-Shelf ({title}) in your web browser.
# The first run creates a private Python environment (.venv) and installs packages.
cd "$(dirname "$0")" || exit 1
PY=""
for candidate in python3.14 python3.13 python3.12 python3; do   # newest Python 3.12+ found
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
    PY=$candidate
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Smart-Shelf needs Python 3.12 or newer: https://www.python.org/downloads/"
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "First run: setting up Python packages (about a minute)..."
  "$PY" -m venv .venv && .venv/bin/python -m pip install -r requirements.txt || exit 1
fi
echo "Smart-Shelf is starting at http://localhost:8501  (press Ctrl+C here to stop it)"
(sleep 4; {{OPEN}} http://localhost:8501 >/dev/null 2>&1) &
.venv/bin/python -m streamlit run smart_shelf/ui/app.py --server.headless true --server.port 8501
"""
    windows = f"""@echo off
rem Starts Smart-Shelf ({title}) in your web browser.
rem The first run creates a private Python environment (.venv) and installs packages.
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
%PY% -c "import sys; sys.exit(sys.version_info < (3, 12))" 2>nul
if errorlevel 1 (
  echo Smart-Shelf needs Python 3.12 or newer: https://www.python.org/downloads/
  pause
  exit /b 1
)
if not exist .venv\\Scripts\\python.exe (
  echo First run: setting up Python packages ^(about a minute^)...
  %PY% -m venv .venv || goto failed
  .venv\\Scripts\\python -m pip install -r requirements.txt || goto failed
)
echo Smart-Shelf is starting at http://localhost:8501  ^(close this window to stop it^)
start "" cmd /c "timeout /t 4 >nul & start http://localhost:8501"
.venv\\Scripts\\python -m streamlit run smart_shelf\\ui\\app.py --server.headless true --server.port 8501
pause
exit /b 0
:failed
echo Setup failed. See the messages above.
pause
exit /b 1
"""
    for name, text in (("run_mac.command", unix.replace("{OPEN}", "open")),
                       ("run_linux.sh", unix.replace("{OPEN}", "xdg-open"))):
        path = out / name
        path.write_text(text, newline="\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    (out / "run_windows.bat").write_text(windows, newline="\r\n")


def write_guide(out: Path, folder: str, keep: str, title: str) -> None:
    """HOW_TO_RUN.txt: the short version of the Readme, inside the folder itself."""
    extra = ("\nCommand-line demo (Architecture B only):\n"
             "  .venv/bin/python -m smart_shelf.arch_b --pantry data/sample_pantry.json\n"
             if keep == "arch_b" else "")
    (out / "HOW_TO_RUN.txt").write_text(f"""Smart-Shelf - {folder} ({title})
{"=" * (16 + len(folder) + len(title))}

Needs Python 3.12 or newer (https://www.python.org/downloads/) and an internet
connection the first time, to install packages.

Run it (one click):
  Mac:      double-click run_mac.command  (first time: right-click > Open)
  Linux:    ./run_linux.sh
  Windows:  double-click run_windows.bat
The app opens at http://localhost:8501. The first run takes about a minute.

Run it by hand (Mac/Linux; on Windows use .venv\\Scripts\\python):
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python -m streamlit run smart_shelf/ui/app.py

Run the tests:
  .venv/bin/python -m pytest
{extra}
Folders:
  smart_shelf/   source code ({keep}, the shared common/ code and the ui/)
  compiled/      the same code compiled to Python 3.12 bytecode (.pyc)
  data/          recipes, ingredients, substitutions, the sample profile and a sample pantry
  tests/         automated tests for this architecture

Using the app saves profile changes to data/user_profiles/. Delete that folder
to start again from the clean sample profile.
""")


def build(target: Path = ROOT) -> list[Path]:
    """Rebuild every release folder under `target` (the repo itself, or a temp folder in tests)."""
    built = []
    for folder, (keep, drop, title) in RELEASES.items():
        out = target / folder
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        copy_common(out, keep, drop)
        count = compile_code(out)
        write_launchers(out, title)
        write_guide(out, folder, keep, title)
        print(f"{folder}/: {title}, {count} files compiled")
        built.append(out)
    return built


if __name__ == "__main__":
    if sys.version_info < (3, 12):
        sys.exit("Build with Python 3.12 or newer (the .venv in this folder).")
    build()
