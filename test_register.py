import os
from dotenv import load_dotenv

load_dotenv()

from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    print(f"Connected to DB: {app.config['SQLALCHEMY_DATABASE_URI']}")
    try:
        count = User.query.count()
        print(f"Current users in DB: {count}")
    except Exception as e:
        print(f"Error checking users: {e}")

    # Attempt to create a test user
    try:
        pw = generate_password_hash("testpassword")
        u = User(name="Test User", email="test@test.com", phone="123456", password=pw)
        db.session.add(u)
        db.session.commit()
        print("Successfully created test user!")
        
        test_u = User.query.filter_by(email='test@test.com').first()
        print(f"Added User ID: {test_u.id}, Role: {test_u.role}")

        db.session.delete(test_u)
        db.session.commit()
    except Exception as e:
        print(f"Error creating user: {e}")
