import os
from dotenv import load_dotenv

load_dotenv()

from app import app, db, Service, User
import json

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

with app.app_context():
    print("Creating tables in Supabase Postgres...")
    db.create_all()
    
    if Service.query.count() == 0:
        print("Seeding initial services...")
        services_data = [
            {
                'title': 'Aadhaar Card Services', 
                'desc': 'New Registration, Name Correction, Address Update, DOB Change',
                'icon': 'img/service-icon.png',
                'schema': [
                    {'name': 'applicant_name', 'label': 'Full Name as per records', 'type': 'text', 'required': True},
                    {'name': 'aadhar_number', 'label': 'Aadhaar Number (Leave blank if New)', 'type': 'text', 'required': False},
                    {'name': 'dob', 'label': 'Date of Birth', 'type': 'date', 'required': True},
                    {'name': 'father_husband_name', 'label': 'Father/Husband Name', 'type': 'text', 'required': True},
                    {'name': 'full_address', 'label': 'Complete Address Details', 'type': 'textarea', 'required': True},
                    {'name': 'correction_details', 'label': 'Details of Correction needed', 'type': 'textarea', 'required': False}
                ]
            },
            {
                'title': 'PAN Card Service', 
                'desc': 'New PAN, Correction or Reprint',
                'icon': 'img/service-icon.png',
                'schema': [
                    {'name': 'applicant_name', 'label': 'Full Name', 'type': 'text', 'required': True},
                    {'name': 'pan_number', 'label': 'Existing PAN (if correction)', 'type': 'text', 'required': False},
                    {'name': 'dob', 'label': 'Date of Birth', 'type': 'date', 'required': True},
                    {'name': 'aadhar_link', 'label': 'Aadhaar Number to Link', 'type': 'text', 'required': True}
                ]
            },
            {
                'title': 'Passport Service', 
                'desc': 'Fresh Passport, Re-issue, Police Clearance',
                'icon': 'img/service-icon.png',
                'schema': [
                    {'name': 'applicant_name', 'label': 'Full Name', 'type': 'text', 'required': True},
                    {'name': 'dob', 'label': 'Date of Birth', 'type': 'date', 'required': True},
                    {'name': 'birth_place', 'label': 'Place of Birth', 'type': 'text', 'required': True},
                    {'name': 'marital_status', 'label': 'Marital Status', 'type': 'text', 'required': True},
                    {'name': 'education', 'label': 'Educational Qualification', 'type': 'text', 'required': True}
                ]
            },
            {
                'title': 'Income & Caste Certificate', 
                'desc': 'Apply for state level certificates',
                'icon': 'img/service-icon.png',
                'schema': [
                    {'name': 'applicant_name', 'label': 'Applicant Name', 'type': 'text', 'required': True},
                    {'name': 'father_name', 'label': 'Father Name', 'type': 'text', 'required': True},
                    {'name': 'annual_income', 'label': 'Total Annual Family Income', 'type': 'number', 'required': True},
                    {'name': 'caste_category', 'label': 'Category (SC/ST/OBC/General)', 'type': 'text', 'required': True}
                ]
            }
        ]
        
        for s in services_data:
            db.session.add(Service(
                title=s['title'], 
                description=s['desc'], 
                icon_path=s['icon'],
                form_schema=json.dumps(s['schema'])
            ))
        db.session.commit()
    print("Database initialization complete.")
