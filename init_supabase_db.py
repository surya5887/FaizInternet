"""
Migration script: Add new columns and tables for Phase 9.
Safe to run multiple times.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from app import app, db, Service, SiteSetting, ApplicationDocument
import json

db_url = os.getenv("DATABASE_URL")
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url

with app.app_context():
    print("Step 1: Creating new tables (site_setting, application_document)...")
    db.create_all()
    print("Tables created/verified.")
    
    # Step 2: Add missing columns to existing tables using raw SQL
    print("Step 2: Adding missing columns to 'service' table...")
    try:
        db.session.execute(db.text("ALTER TABLE service ADD COLUMN IF NOT EXISTS required_documents TEXT"))
        db.session.commit()
        print("  -> required_documents column added/verified.")
    except Exception as e:
        db.session.rollback()
        print(f"  -> Column may already exist or error: {e}")
    
    # Step 3: Seed default site settings
    print("Step 3: Seeding site settings...")
    if SiteSetting.query.count() == 0:
        defaults = {
            'shop_name': 'Faiz Internet',
            'shop_tagline': 'Common Service Centre',
            'shop_address': 'Maiz Bazar, Asara, Uttar Pradesh, India',
            'shop_phone': '+91 9837957711',
            'shop_email': 'contact@faizinternet.com',
            'shop_timings': 'Mon - Sat: 9AM - 8PM',
            'shop_map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3510.123456789!2d78.0!3d28.5!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zMjjCsDMwJzAwLjAiTiA3OMKwMDAnMDAuMCJF!5e0!3m2!1sen!2sin!4v1234567890'
        }
        for k, v in defaults.items():
            db.session.add(SiteSetting(key=k, value=v))
        db.session.commit()
        print("  -> Site settings seeded.")
    else:
        print("  -> Site settings already exist, skipping.")
    
    # Step 4: Update existing services with required_documents
    print("Step 4: Updating existing services with document fields...")
    doc_configs = {
        'Aadhaar Card Services': [
            {'label': 'Aadhaar Card Copy', 'required': True},
            {'label': 'Address Proof', 'required': False}
        ],
        'PAN Card Service': [
            {'label': 'ID Proof', 'required': True}
        ],
        'eDistrict Services': [
            {'label': 'Supporting Documents', 'required': True}
        ],
        'Voter ID Services': [
            {'label': 'Photo ID Proof', 'required': True}
        ]
    }
    
    for title, docs in doc_configs.items():
        svc = Service.query.filter_by(title=title).first()
        if svc and not svc.required_documents:
            svc.required_documents = json.dumps(docs)
            print(f"  -> Updated '{title}' with {len(docs)} doc fields.")
    
    db.session.commit()
    print("\n=== Migration complete! ===")
