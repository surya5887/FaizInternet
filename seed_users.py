from app import app, db, User
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

def seed_users():
    with app.app_context():
        # 1. Admin: Usman Ali
        admin_email = "usmanali@faizinternet.com"
        admin_pass = "admin@9756"
        
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            print(f"Creating Admin: {admin_email}")
            admin = User(
                name="Usman Ali",
                email=admin_email,
                phone="+91 9756520529",
                password=generate_password_hash(admin_pass),
                plain_password=admin_pass,
                role="admin"
            )
            db.session.add(admin)
        else:
            print(f"Updating Admin: {admin_email}")
            admin.name = "Usman Ali"
            admin.password = generate_password_hash(admin_pass)
            admin.plain_password = admin_pass
            admin.role = "admin"

        # 2. Superuser: Anees Chaudhary
        super_email = "anees@faizinternet.com"
        super_pass = "super@123" # Default, suggest user to change this
        
        superuser = User.query.filter_by(email=super_email).first()
        if not superuser:
            print(f"Creating Superuser: {super_email}")
            superuser = User(
                name="Anees Chaudhary",
                email=super_email,
                phone="",
                password=generate_password_hash(super_pass),
                role="superuser"
            )
            db.session.add(superuser)
        else:
            print(f"Updating Superuser: {super_email}")
            superuser.name = "Anees Chaudhary"
            superuser.password = generate_password_hash(super_pass)
            superuser.role = "superuser"

        db.session.commit()
        print("Seeding complete!")

if __name__ == "__main__":
    seed_users()
