"""Read-only command-line demo: python -m smart_shelf.arch_b --help."""
import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from smart_shelf.common.data_access import load_profile, load_reference_data

from .engine import BlackboardEngine


def main():
    parser = argparse.ArgumentParser(description="Run Smart-Shelf's blackboard architecture")
    parser.add_argument("--pantry", type=Path, required=True, help="JSON array of pantry rows")
    parser.add_argument("--user", default="demo", help="Existing private profile ID")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[2] / "data")
    parser.add_argument("--today", type=date.fromisoformat, help="Fixed date for reproducible demos")
    args = parser.parse_args()
    try:
        reference = load_reference_data(args.data_dir)
        profile = load_profile(args.user, args.data_dir / "profiles")
        rows = json.loads(args.pantry.read_text(encoding="utf-8"))
        result = BlackboardEngine(reference).run(rows, profile, today=args.today)
    except Exception as error:
        parser.exit(1, f"Analysis stopped: {error}\n")
    print(json.dumps(asdict(result), default=str, indent=2))


if __name__ == "__main__":
    main()
