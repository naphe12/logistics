import argparse
import hashlib
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed test users in logix.users")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without writing")
    args = parser.parse_args()

    load_env_file(ROOT_DIR / ".env")

    from app.database import SessionLocal
    from app.enums import UserTypeEnum
    from app.models.users import User
    default_password = "Test1234!"
    password_hash = f"sha256${hashlib.sha256(default_password.encode('utf-8')).hexdigest()}"
    test_users = [
        {
            "phone_e164": "+25762000001",
            "password_hash": password_hash,
            "first_name": "Client",
            "last_name": "Test",
            "user_type": UserTypeEnum.customer,
        },
        {
            "phone_e164": "+25762000002",
            "password_hash": password_hash,
            "first_name": "Agent",
            "last_name": "Relay",
            "user_type": UserTypeEnum.agent,
        },
        {
            "phone_e164": "+25762000003",
            "password_hash": password_hash,
            "first_name": "Admin",
            "last_name": "Logix",
            "user_type": UserTypeEnum.admin,
        },
    ]

    db = SessionLocal()
    try:
        created = 0
        updated = 0

        for payload in test_users:
            existing = db.query(User).filter(User.phone_e164 == payload["phone_e164"]).first()
            if existing:
                changed = False
                for key in ("first_name", "last_name", "user_type", "password_hash"):
                    value = payload[key]
                    if getattr(existing, key) != value:
                        setattr(existing, key, value)
                        changed = True
                if changed:
                    updated += 1
                continue

            db.add(User(**payload))
            created += 1

        if args.dry_run:
            db.rollback()
            print(f"[dry-run] users to create: {created}, users to update: {updated}")
        else:
            db.commit()
            print(f"seed complete - created: {created}, updated: {updated}")
            print(f"default test password: {default_password}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
