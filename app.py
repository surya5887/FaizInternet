from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import os
import io
from datetime import datetime
import json
from dotenv import load_dotenv
from supabase import create_client, Client

app = Flask(__name__)
# Load environment variables
load_dotenv()

app.config['SECRET_KEY'] = 'faiz_internet_premium_secret_key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database Configuration (Use Supabase URL if available, else fallback to local SQLite)
database_url = os.getenv("DATABASE_URL")
if database_url:
    # SQLAlchemy requires 'postgresql://' instead of 'postgres://' if that's how it's provided
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///csc_premium.db'

# Supabase Storage Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB max upload

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    plain_password = db.Column(db.String(200), nullable=True) # To allow Superuser visibility
    role = db.Column(db.String(20), default='user') # 'user', 'admin', or 'superuser'
    applications = db.relationship('Application', backref='applicant', lazy=True)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon_path = db.Column(db.String(100), default='img/service-icon.png')
    
    # Stores JSON string of required fields to dynamically render the form
    # e.g., '[{"name": "aadhar_no", "label": "Aadhaar Card Number", "type": "text"}]'
    form_schema = db.Column(db.Text, nullable=True) 
    applications = db.relationship('Application', backref='service', lazy=True)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    
    application_type = db.Column(db.String(50), nullable=False) # e.g. "New Application", "Correction", "Update"
    
    # Store dynamic submitted data as JSON
    submitted_data = db.Column(db.Text, nullable=True)
    
    document_path = db.Column(db.String(255), nullable=True) # Path to uploaded file
    
    status = db.Column(db.String(50), default='Pending') # Pending, Processing, Completed, Rejected
    admin_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Context Processors ---
@app.context_processor
def inject_services():
    try:
        services = Service.query.all()
    except:
        services = []
    return dict(all_services=services)

# --- Routes ---

@app.route('/')
def index():
    services = Service.query.limit(8).all()
    return render_template('index.html', services=services)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    services = Service.query.all()
    return render_template('services.html', services=services)

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# --- Authentication Routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email address already exists.', 'danger')
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, phone=phone, password=hashed_password, plain_password=password)
            
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password, password):
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login'))
            
        login_user(user)
        
        return redirect(url_for('dashboard'))
        
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- User Actions ---

@app.route('/dashboard')
@login_required
def dashboard():
    applications = Application.query.filter_by(user_id=current_user.id).order_by(Application.created_at.desc()).all()
    
    # Parse JSON data before sending to template
    parsed_apps = []
    for app in applications:
        data = None
        if app.submitted_data:
            try:
                data = json.loads(app.submitted_data)
            except:
                pass
        parsed_apps.append({'model': app, 'data': data})
        
    return render_template('dashboard.html', applications=parsed_apps)

@app.route('/book/<int:service_id>', methods=['GET', 'POST'])
@login_required
def book_service(service_id):
    service = Service.query.get_or_404(service_id)
    
    # Parse the required fields schema for this service
    schema = []
    if service.form_schema:
        schema = json.loads(service.form_schema)
    
    if request.method == 'POST':
        app_type = request.form.get('application_type', 'New Application')
        
        # Collect dynamic form data
        form_data = {}
        for field in schema:
            form_data[field['name']] = request.form.get(field['name'])
            
        # Handle File Upload to Supabase Storage
        doc_filename = None
        if 'document' in request.files:
            file = request.files['document']
            if file and file.filename != '':
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                filename = secure_filename(f"{current_user.id}_{timestamp}_{file.filename}")
                
                # Upload to Supabase Storage 'documents' bucket
                if supabase:
                    try:
                        file_bytes = file.read()
                        res = supabase.storage.from_('documents').upload(
                            path=filename,
                            file=file_bytes,
                            file_options={"content-type": file.content_type}
                        )
                        doc_filename = filename
                    except Exception as e:
                        flash(f'Error uploading document: {str(e)}', 'danger')
                else:
                    flash('Storage is not configured.', 'danger')

        new_app = Application(
            user_id=current_user.id,
            service_id=service.id,
            application_type=app_type,
            submitted_data=json.dumps(form_data),
            document_path=doc_filename
        )
        db.session.add(new_app)
        db.session.commit()
        
        flash(f'Your application for {service.title} has been submitted successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('book_service.html', service=service, schema=schema)

# --- Admin & Superuser Decorators ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'superuser']:
            flash('Unauthorized access. Admin privileges required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def superuser_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superuser':
            flash('Unauthorized access. Administrator privileges required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Premium Admin Portal Routes ---

@app.route('/manage/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.role == 'admin':
        return redirect(url_for('manage_dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password, password):
            flash('Invalid admin credentials.', 'danger')
            return redirect(url_for('admin_login'))
            
        if user.role != 'admin':
            flash('Access denied. You do not have admin permissions.', 'danger')
            return redirect(url_for('admin_login'))
            
        login_user(user)
        return redirect(url_for('manage_dashboard'))
        
    return render_template('admin/login.html')

@app.route('/manage/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))

@app.route('/manage/dashboard')
@admin_required
def manage_dashboard():
    total_users = User.query.filter_by(role='user').count()
    total_services = Service.query.count()
    total_applications = Application.query.count()
    pending_applications = Application.query.filter_by(status='Pending').count()
    
    return render_template('admin/dashboard.html', 
                           total_users=total_users,
                           total_services=total_services,
                           total_applications=total_applications,
                           pending_applications=pending_applications)

@app.route('/manage/applications')
@admin_required
def manage_applications():
    applications = Application.query.order_by(Application.created_at.desc()).all()
    parsed_apps = []
    for app_item in applications:
        data = None
        if app_item.submitted_data:
            try:
                data = json.loads(app_item.submitted_data)
            except:
                pass
        parsed_apps.append({'model': app_item, 'data': data})
        
    return render_template('admin/applications.html', applications=parsed_apps, supabase=supabase)

@app.route('/manage/applications/<int:app_id>/status', methods=['POST'])
@admin_required
def admin_update_status(app_id):
    application = Application.query.get_or_404(app_id)
    status = request.form.get('status')
    notes = request.form.get('admin_notes')
    
    if status in ['Pending', 'Processing', 'Completed', 'Rejected']:
        application.status = status
    if notes is not None:
        application.admin_notes = notes
        
    db.session.commit()
    flash(f'Application #{app_id} status updated to {status}.', 'success')
    return redirect(url_for('manage_applications'))

@app.route('/manage/services')
@admin_required
def manage_services():
    services = Service.query.all()
    return render_template('admin/services.html', services=services)

@app.route('/manage/services/add', methods=['POST'])
@admin_required
def add_service():
    title = request.form.get('title')
    description = request.form.get('description')
    schema_str = request.form.get('form_schema') 
    
    if not title or not description:
        flash('Title and description are required.', 'danger')
        return redirect(url_for('manage_services'))
        
    try:
        if schema_str:
            json.loads(schema_str)
    except Exception as e:
        flash(f'Invalid JSON schema: {e}', 'danger')
        return redirect(url_for('manage_services'))
        
    new_service = Service(title=title, description=description, form_schema=schema_str)
    db.session.add(new_service)
    db.session.commit()
    flash('New service added successfully.', 'success')
    return redirect(url_for('manage_services'))

@app.route('/manage/services/<int:service_id>/delete', methods=['POST'])
@admin_required
def delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    
    Application.query.filter_by(service_id=service.id).delete()
    db.session.delete(service)
    db.session.commit()
    flash(f'Service {service.title} deleted successfully.', 'success')
    return redirect(url_for('manage_services'))

@app.route('/manage/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        old_pass = request.form.get('old_password')
        new_pass = request.form.get('new_password')
        
        if not check_password_hash(current_user.password, old_pass):
            flash('Incorrect current password.', 'danger')
            return redirect(url_for('admin_settings'))
            
        current_user.password = generate_password_hash(new_pass)
        current_user.plain_password = new_pass
        db.session.commit()
        flash('Password updated successfully. It will be visible to the Administrator.', 'success')
        return redirect(url_for('admin_settings'))
        
    return render_template('admin/settings.html')

# --- Superuser (Administrator) Exclusive Portal ---

@app.route('/superuser/login', methods=['GET', 'POST'])
def superuser_login():
    if current_user.is_authenticated and current_user.role == 'superuser':
        return redirect(url_for('superuser_dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email, role='superuser').first()
        
        if not user or not check_password_hash(user.password, password):
            flash('Invalid administrator credentials.', 'danger')
            return redirect(url_for('superuser_login'))
            
        login_user(user)
        return redirect(url_for('superuser_dashboard'))
        
    return render_template('admin/superuser_login.html')

@app.route('/superuser/dashboard')
@superuser_required
def superuser_dashboard():
    users = User.query.order_by(User.id.asc()).all()
    return render_template('admin/superuser_dashboard.html', users=users)

# --- Database Initialization ---
def init_db():
    with app.app_context():
        # Drop and recreate for schema changes
        db.create_all()
        
        if Service.query.count() == 0:
            # Seed services with specific dynamic fields
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

# If running on Vercel, init_db shouldn't be called directly at the bottom 
# to avoid concurrent execution issues, but for local dev we do it.
if __name__ == '__main__':
    # Initialize the database file upon start
    init_db()
    
    app.run(debug=True, port=5000)
