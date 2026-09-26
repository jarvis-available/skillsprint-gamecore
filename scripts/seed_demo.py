"""
Bootstrap seed: creates ONE admin user and the system defaults
(precedence rules, prompt templates). Everything else - roles, documents,
requirements, employees - must be created through the running app.

Run from the backend directory:
    venv\\Scripts\\python.exe scripts\\seed_demo.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.connection import Base, SessionLocal, engine
from app.models import User  # noqa: F401
from app.schemas.user import UserCreate
from app.services import precedence_rule_service, prompt_service, user_service


ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "123456789"


def main() -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        precedence_rule_service.ensure_defaults(db)
        prompt_service.ensure_default_prompts(db)
        db.commit()

        admin = db.query(User).filter(User.system_role == "admin").first()
        if admin is None:
            admin = user_service.create_user(
                db,
                UserCreate(
                    employee_id="ADM001",
                    name="System Admin",
                    email=ADMIN_EMAIL,
                    password=ADMIN_PASSWORD,
                    system_role="admin",
                    department="Management",
                    experience_level="advanced",
                    joining_date=date.today(),
                ),
            )
            db.commit()
            print(f"Admin created: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        else:
            print(f"Admin already exists: {admin.email}")

        print("Seed complete. No demo data - use the app to create roles, documents, requirements, employees.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
