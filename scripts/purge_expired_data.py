#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.services.retention_service import purge_expired_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply configured data retention windows.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be deleted without committing")
    parser.add_argument("--yes", action="store_true", help="Skip the interactive confirmation")
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        answer = input("This will permanently delete data outside the retention windows. Type 'purge' to continue: ")
        if answer.strip().lower() != "purge":
            print("Aborted.")
            return 1

    with SessionLocal() as db:
        summary = purge_expired_data(db, dry_run=args.dry_run)
    print(json.dumps({"dry_run": args.dry_run, **summary.as_dict()}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
