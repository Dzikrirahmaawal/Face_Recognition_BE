#!/usr/bin/env python
from __future__ import annotations

import argparse
import getpass
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.core.exceptions import ConflictError, ValidationAppError  # noqa: E402
from app.core.security import hash_password, validate_password_strength  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.repositories import users as users_repo  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the first SUPER_ADMIN account.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", default="System Administrator")
    parser.add_argument("--password", help="Omit to be prompted securely")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    errors = validate_password_strength(password)
    if errors:
        print("Password does not meet security requirements:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        try:
            if users_repo.get_by_username(db, args.username):
                raise ConflictError("Username is already in use", error_code="USERNAME_EXISTS")
            if users_repo.get_by_email(db, args.email.lower()):
                raise ConflictError("Email is already in use", error_code="EMAIL_EXISTS")
            user = User(
                username=args.username,
                email=args.email.lower(),
                password_hash=hash_password(password),
                full_name=args.full_name,
                role=UserRole.SUPER_ADMIN,
                is_active=True,
            )
            users_repo.add(db, user)
            db.commit()
            db.refresh(user)
        except (ConflictError, ValidationAppError) as exc:
            print(f"Error: {exc.message}", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            print(f"Failed to create SUPER_ADMIN: {type(exc).__name__}", file=sys.stderr)
            # The SQLAlchemy wrapper message embeds the SQL statement and bound
            # parameters (which include the password hash on insert failures),
            # so only the underlying driver error and the traceback are shown.
            orig = getattr(exc, "orig", None)
            if orig is not None:
                print(
                    f"Database error: {type(orig).__module__}.{type(orig).__name__}: {orig}",
                    file=sys.stderr,
                )
            print("Traceback (most recent call last):", file=sys.stderr)
            traceback.print_tb(exc.__traceback__, file=sys.stderr)
            return 1

    print(f"Created SUPER_ADMIN {user.username} ({user.email}) with id {user.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
