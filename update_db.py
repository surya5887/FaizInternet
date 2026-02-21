from app import app, db, Service

icons = {
    'Aadhaar Card Services': 'fa-solid fa-address-card',
    'PAN Card Service': 'fa-solid fa-credit-card',
    'Passport Service': 'fa-solid fa-passport',
    'Income & Caste Certificate': 'fa-solid fa-file-signature'
}

with app.app_context():
    services = Service.query.all()
    for s in services:
        if s.title in icons:
            s.icon_path = icons[s.title]
    db.session.commit()
    print("Icons updated successfully!")
