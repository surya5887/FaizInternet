import sys
from app import app, db
from models import Service, User
from flask import render_template
from flask_login import login_user

with app.app_context():
    # Login a test user to provide current_user context
    user = User.query.first()
    
    # Try rendering the template using fake request context
    with app.test_request_context('/book/10', method='GET'):
        # Mock login process
        login_user(user)
        try:
            from app import book_service
            # the app route relies on the context being /book/10
            # but we can just call book_service directly
            response = book_service(10)
            if isinstance(response, str):
                print("No error rendering template for service 10! The string length is:", len(response))
            else:
                print("Template rendered (Flask Response object). No error!")
        except Exception as e:
            import traceback
            traceback.print_exc()
