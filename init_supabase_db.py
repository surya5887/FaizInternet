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
    
    if True: # Force update for existing services
        print("Updating/Seeding services...")
        services_data = [
            {
                'title': 'Aadhaar Card Services', 
                'desc': 'Aadhaar Address Update, Aadhaar Download, Find Lost Aadhaar, Get Aadhaar without OTP',
                'icon': 'img/aadhaar_logo.jpg',
                'schema': [
                    {'name': 'applicant_name', 'label': 'Full Name', 'type': 'text', 'required': True},
                    {'name': 'aadhar_number', 'label': 'Aadhaar Number', 'type': 'text', 'required': False},
                    {'name': 'service_type', 'label': 'Select Service', 'type': 'select', 'options': ['Address Update', 'Download Aadhaar', 'Find Lost Aadhaar', 'Aadhaar without OTP'], 'required': True}
                ]
            },
            {
                'title': 'PAN Card Service', 
                'desc': 'New PAN, Correction or Reprint',
                'icon': 'img/csc_logo.jpg',
                'schema': [
                    {'name': 'applicant_name', 'label': 'Full Name', 'type': 'text', 'required': True},
                    {'name': 'pan_number', 'label': 'Existing PAN (if correction)', 'type': 'text', 'required': False}
                ]
            },
            {
                'title': 'eDistrict Services', 
                'desc': 'Income, Caste, Domicile, Birth & Death Certificate',
                'icon': 'img/edistrict_logo.jpg',
                'schema': [
                    {'name': 'applicant_name', 'label': 'Applicant Name', 'type': 'text', 'required': True},
                    {'name': 'certificate_type', 'label': 'Type of Certificate', 'type': 'text', 'required': True}
                ]
            },
            {
                'title': 'Voter ID Services', 
                'desc': 'New Registration, Correction, EPIC Download',
                'icon': 'img/voter_logo.jpg',
                'schema': [
                    {'name': 'applicant_name', 'label': 'Voter Name', 'type': 'text', 'required': True}
                ]
            }
        ]
        
        # Clear old services to avoid duplicates during re-seed
        Service.query.delete()
        
        for s in services_data:
            db.session.add(Service(
                title=s['title'], 
                description=s['desc'], 
                icon_path=s['icon'],
                form_schema=json.dumps(s['schema'])
            ))
        db.session.commit()
    print("Database initialization complete.")
