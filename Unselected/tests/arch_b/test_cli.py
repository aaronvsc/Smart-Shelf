import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_cli_runs_without_mutating_demo_profile():
    path = ROOT / "data/profiles/demo.json"
    before = path.read_bytes()
    process = subprocess.run(
        [sys.executable, "-m", "smart_shelf.arch_b", "--pantry",
         "docs/architecture_b/pantry_demo.json", "--today", "2026-11-03"],
        cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result["status"] == "ok"
    assert len(result["activations"]) == 10
    assert path.read_bytes() == before


def test_cli_missing_profile_fails_closed():
    process = subprocess.run(
        [sys.executable, "-m", "smart_shelf.arch_b", "--pantry",
         "docs/architecture_b/pantry_demo.json", "--user", "missing_profile_123"],
        cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert process.returncode != 0
    assert "Analysis stopped" in process.stderr
    assert process.stdout == ""
