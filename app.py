from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from dotenv import load_dotenv
from supabase import create_client, Client

app = Flask(__name__)
# Load environment variables
load_dotenv()

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'faiz_internet_premium_secret_key')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database Configuration (Use Supabase URL if available, else fallback to local SQLite)
database_url = os.getenv("DATABASE_URL")
if database_url:
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
login_manager.login_view = 'admin_login'

# ===================== MODELS =====================


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    plain_password = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(20), default='user')

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    icon_path = db.Column(db.String(100), default='img/service-icon.png')
    docs_new = db.Column(db.Text, nullable=True)     # Text outlining needed docs for a New App
    docs_update = db.Column(db.Text, nullable=True)  # Text outlining needed docs for Correction/Update
    status_link = db.Column(db.String(255), nullable=True) # Direct URL to check official status


class SiteSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

# ===================== HELPERS =====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_setting(key, default=''):
    """Get a site setting value by key."""
    try:
        s = SiteSetting.query.filter_by(key=key).first()
        return s.value if s else default
    except Exception:
        return default

def set_setting(key, value):
    """Set or update a site setting."""
    s = SiteSetting.query.filter_by(key=key).first()
    if s:
        s.value = value
    else:
        db.session.add(SiteSetting(key=key, value=value))

# Context processor — inject settings + services into all templates
@app.context_processor
def inject_globals():
    try:
        services = Service.query.all()
    except Exception:
        services = []
    
    # Build settings dict
    site = {}
    try:
        for s in SiteSetting.query.all():
            site[s.key] = s.value
    except Exception:
        pass
    
    return dict(all_services=services, site=site)

# ===================== PUBLIC ROUTES =====================

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

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/check-status')
def check_status():
    services = Service.query.all()
    return render_template('check_status.html', services=services)

@app.route('/service/<int:service_id>')
def service_detail(service_id):
    service = Service.query.get_or_404(service_id)
    return render_template('service_detail.html', service=service)

# ===================== ADMIN DECORATORS =====================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'superuser']:
            flash('Admin access required.', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def superuser_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superuser':
            flash('Superuser access required.', 'danger')
            return redirect(url_for('superuser_login'))
        return f(*args, **kwargs)
    return decorated_function

# ===================== ADMIN AUTH =====================

@app.route('/manage/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.role in ['admin', 'superuser']:
        return redirect(url_for('manage_dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password, password):
            flash('Invalid credentials.', 'danger')
            return redirect(url_for('admin_login'))
            
        if user.role not in ['admin', 'superuser']:
            flash('You do not have admin privileges.', 'danger')
            return redirect(url_for('admin_login'))
            
        login_user(user)
        return redirect(url_for('manage_dashboard'))
        
    return render_template('admin/login.html')

@app.route('/manage/logout')
@admin_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))

# ===================== ADMIN DASHBOARD =====================

@app.route('/manage/dashboard')
@admin_required
def manage_dashboard():
    total_services = Service.query.count()
    
    return render_template('admin/dashboard.html', 
                           total_services=total_services)

# ===================== ADMIN — SERVICE MANAGEMENT =====================

@app.route('/manage/services')
@admin_required
def manage_services():
    services = Service.query.all()
    return render_template('admin/services.html', services=services)

@app.route('/manage/services/add', methods=['POST'])
@admin_required
def add_service():
    try:
        title = request.form.get('title')
        description = request.form.get('description')
        docs_new = request.form.get('docs_new')
        docs_update = request.form.get('docs_update')
        status_link = request.form.get('status_link')
        
        if not title or not description:
            flash('Title and description are required.', 'danger')
            return redirect(url_for('manage_services'))
            
        new_service = Service(title=title, description=description, docs_new=docs_new, docs_update=docs_update, status_link=status_link)
        db.session.add(new_service)
        db.session.commit()
        flash('New service added successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding service: {str(e)}', 'danger')
        
    return redirect(url_for('manage_services'))

@app.route('/manage/services/<int:service_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_service(service_id):
    service = Service.query.get_or_404(service_id)
    
    if request.method == 'POST':
        service.title = request.form.get('title', service.title)
        service.description = request.form.get('description', service.description)
        service.icon_path = request.form.get('icon_path', service.icon_path)
        service.docs_new = request.form.get('docs_new')
        service.docs_update = request.form.get('docs_update')
        service.status_link = request.form.get('status_link')
        
        db.session.commit()
        flash(f'Service "{service.title}" updated successfully.', 'success')
        return redirect(url_for('manage_services'))
    
    return render_template('admin/edit_service.html', service=service)

@app.route('/manage/services/<int:service_id>/delete', methods=['POST'])
@admin_required
def delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    flash(f'Service {service.title} deleted successfully.', 'success')
    return redirect(url_for('manage_services'))



# ===================== ADMIN — SETTINGS =====================

@app.route('/manage/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_password':
            old_pass = request.form.get('old_password')
            new_pass = request.form.get('new_password')
            
            if not check_password_hash(current_user.password, old_pass):
                flash('Incorrect current password.', 'danger')
                return redirect(url_for('admin_settings'))
                
            current_user.password = generate_password_hash(new_pass)
            current_user.plain_password = new_pass
            db.session.commit()
            flash('Password updated successfully.', 'success')
            
        elif action == 'update_site':
            settings_keys = ['shop_name', 'shop_tagline', 'shop_address', 'shop_phone', 
                           'shop_email', 'shop_map_url', 'shop_timings']
            for key in settings_keys:
                val = request.form.get(key)
                if val is not None:
                    set_setting(key, val)
            db.session.commit()
            flash('Site settings updated successfully.', 'success')
        
        return redirect(url_for('admin_settings'))
    
    # Load current settings
    settings = {}
    try:
        for s in SiteSetting.query.all():
            settings[s.key] = s.value
    except Exception:
        pass
        
    return render_template('admin/settings.html', settings=settings)

# ===================== SUPERUSER =====================

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

# ===================== DATABASE INIT =====================

def init_db():
    with app.app_context():
        db.create_all()
        
        # Seed default site settings if empty
        if SiteSetting.query.count() == 0:
            defaults = {
                'shop_name': 'Faiz Internet',
                'shop_tagline': 'Common Service Centre',
                'shop_address': 'Maiz Bazar, Asara, Uttar Pradesh, India',
                'shop_phone': '+91 9756520529',
                'shop_email': 'contact@faizinternet.com',
                'shop_timings': 'Mon - Sat: 9AM - 8PM',
                'shop_map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3510.123456789!2d78.0!3d28.5!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zMjjCsDMwJzAwLjAiTiA3OMKwMDAnMDAuMCJF!5e0!3m2!1sen!2sin!4v1234567890'
            }
            for k, v in defaults.items():
                db.session.add(SiteSetting(key=k, value=v))
            db.session.commit()
        
        if Service.query.count() == 0:
            services_data = [
                ('Labour Card', 'Apply New Labour Card, Renewal Labour Card', 'fa-solid fa-helmet-safety'),
                ('Voter ID Services', 'New Registration, Correction, EPIC Download', 'fa-solid fa-id-card'),
                ('PAN Card Service', 'New PAN, Correction or Reprint', 'fa-solid fa-address-card'),
                ('Aadhaar Card Services', 'Aadhaar Address Update, Aadhaar Download, Find Lost Aadhaar, Get Aadhaar without OTP', 'fa-solid fa-fingerprint'),
                ('eDistrict Services', 'Income, Caste, Domicile, Birth & Death Certificate', 'fa-solid fa-building-columns'),
                ('Passport', 'New Passport, Police Clearance, Correction', 'fa-solid fa-passport'),
                ('Ration Card', 'New Ration Card, Name Add/Delete, Download', 'fa-solid fa-utensils'),
                ('Color Photo and More', 'Passport Photos, Photostat, Lamination', 'fa-solid fa-camera-retro')
            ]
            for title, desc, icon in services_data:
                db.session.add(Service(title=title, description=desc, icon_path=icon))
            db.session.commit()
        else:
            # Migration: Update existing broken image paths to icons
            curr_services = Service.query.all()
            mapping = {
                'Labour Card': 'fa-solid fa-helmet-safety',
                'Voter ID Services': 'fa-solid fa-id-card',
                'PAN Card Service': 'fa-solid fa-address-card',
                'Aadhaar Card Services': 'fa-solid fa-fingerprint',
                'eDistrict Services': 'fa-solid fa-building-columns',
                'Passport': 'fa-solid fa-passport',
                'Ration Card': 'fa-solid fa-utensils',
                'Color Photo and More': 'fa-solid fa-camera-retro'
            }
            for s in curr_services:
                if s.title in mapping and (s.icon_path.startswith('img/') or not s.icon_path.startswith('fa-')):
                    s.icon_path = mapping[s.title]
            db.session.commit()

# Ensure tables exist on Vercel (create_all is safe to call multiple times)
with app.app_context():
    try:
        db.create_all()
    except Exception:
        pass

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
