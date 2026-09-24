import bcrypt
from sqlalchemy.orm import Session
from app.models.user import User
from app.database.connection import SessionLocal, engine, Base

def create_admin_user(db: Session):
    """Automatically creates a default admin user if one doesn't already exist."""
    admin_email = "admin@gmail.com"
    
    # Check if the admin account already exists
    existing_admin = db.query(User).filter(User.email == admin_email).first()
    
    if not existing_admin:
        # Hash the password '123456789' using bcrypt
        hashed_password = bcrypt.hashpw("123456789".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        
        admin_user = User(
            employee_id="ADMIN001",
            name="System Administrator",
            email=admin_email,
            password_hash=hashed_password,
            system_role="admin",
            training_status="completed",
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        print("Default admin account created successfully: admin@gmail.com")
    else:
        print("Admin account already exists. Skipping creation.")