from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
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

# ===================== MODELS =====================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    plain_password = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(20), default='user')
    applications = db.relationship('Application', backref='applicant', lazy=True)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    icon_path = db.Column(db.String(100), default='img/service-icon.png')
    form_schema = db.Column(db.Text, nullable=True)       # JSON: form fields config
    required_documents = db.Column(db.Text, nullable=True) # JSON: list of doc upload field configs
    applications = db.relationship('Application', backref='service', lazy=True)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    application_type = db.Column(db.String(50), nullable=False)
    submitted_data = db.Column(db.Text, nullable=True)
    document_path = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default='Pending')
    admin_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    documents = db.relationship('ApplicationDocument', backref='application', lazy=True, cascade='all, delete-orphan')

class ApplicationDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)        # Storage filename
    original_name = db.Column(db.String(255), nullable=False)   # User-visible name
    doc_label = db.Column(db.String(200), nullable=True)        # e.g. "Aadhaar Copy"
    uploaded_by = db.Column(db.String(20), default='user')      # 'user' or 'admin'
    doc_type = db.Column(db.String(20), default='request')      # 'request' (user->admin) or 'response' (admin->user)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    except:
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
    except:
        services = []
    
    # Build settings dict
    site = {}
    try:
        for s in SiteSetting.query.all():
            site[s.key] = s.value
    except:
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

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# ===================== AUTH ROUTES =====================

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

# ===================== USER DASHBOARD =====================

@app.route('/dashboard')
@login_required
def dashboard():
    applications = Application.query.filter_by(user_id=current_user.id).order_by(Application.created_at.desc()).all()
    
    parsed_apps = []
    for app_item in applications:
        data = None
        if app_item.submitted_data:
            try:
                data = json.loads(app_item.submitted_data)
            except:
                pass
        # Get response documents (admin-uploaded)
        response_docs = ApplicationDocument.query.filter_by(
            application_id=app_item.id, doc_type='response'
        ).all()
        parsed_apps.append({'model': app_item, 'data': data, 'response_docs': response_docs})
        
    return render_template('dashboard.html', applications=parsed_apps)

@app.route('/download/<int:doc_id>')
@login_required
def download_document(doc_id):
    """Generate a signed URL for downloading a document."""
    doc = ApplicationDocument.query.get_or_404(doc_id)
    app_item = Application.query.get_or_404(doc.application_id)
    
    # Security: only the application owner or admin can download
    if app_item.user_id != current_user.id and current_user.role not in ['admin', 'superuser']:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    if supabase:
        try:
            url = supabase.storage.from_('documents').create_signed_url(doc.filename, 60 * 60)
            if url and url.get('signedURL'):
                return redirect(url['signedURL'])
        except:
            pass
    
    flash('Unable to generate download link.', 'danger')
    return redirect(url_for('dashboard'))

# ===================== BOOKING (USER) =====================

@app.route('/book/<int:service_id>', methods=['GET', 'POST'])
@login_required
def book_service(service_id):
    service = Service.query.get_or_404(service_id)
    
    schema = []
    if service.form_schema:
        try:
            schema = json.loads(service.form_schema)
        except:
            pass
    
    doc_fields = []
    if service.required_documents:
        try:
            doc_fields = json.loads(service.required_documents)
        except:
            pass
    
    if request.method == 'POST':
        app_type = request.form.get('application_type', 'New Application')
        
        # Collect dynamic form data
        form_data = {}
        for field in schema:
            field_name = field.get('name')
            if field_name:
                form_data[field_name] = request.form.get(field_name)
        
        # Handle legacy single file upload
        doc_filename = None
        if 'document' in request.files:
            file = request.files['document']
            if file and file.filename != '':
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                filename = secure_filename(f"{current_user.id}_{timestamp}_{file.filename}")
                if supabase:
                    try:
                        file_bytes = file.read()
                        supabase.storage.from_('documents').upload(
                            path=filename,
                            file=file_bytes,
                            file_options={"content-type": file.content_type}
                        )
                        doc_filename = filename
                    except Exception as e:
                        flash(f'Error uploading document: {str(e)}', 'danger')

        new_app = Application(
            user_id=current_user.id,
            service_id=service.id,
            application_type=app_type,
            submitted_data=json.dumps(form_data),
            document_path=doc_filename
        )
        db.session.add(new_app)
        db.session.commit()
        
        # Handle multiple document uploads (Nested & Stylish)
        for i, doc_field in enumerate(doc_fields):
            sub_inputs = doc_field.get('sub_inputs', [])
            
            if sub_inputs and len(sub_inputs) > 0:
                # Handle sub-inputs (e.g. Front/Back)
                for j, sub_label in enumerate(sub_inputs):
                    field_name = f"doc_{i}_{j}"
                    if field_name in request.files:
                        file = request.files[field_name]
                        if file and file.filename != '':
                            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                            fname = secure_filename(f"{current_user.id}_{new_app.id}_{timestamp}_{j}_{file.filename}")
                            if supabase:
                                try:
                                    file_bytes = file.read()
                                    supabase.storage.from_('documents').upload(
                                        path=fname,
                                        file=file_bytes,
                                        file_options={"content-type": file.content_type}
                                    )
                                    new_doc = ApplicationDocument(
                                        application_id=new_app.id,
                                        filename=fname,
                                        original_name=file.filename,
                                        doc_label=f"{doc_field['label']} - {sub_label}",
                                        uploaded_by='user',
                                        doc_type='request'
                                    )
                                    db.session.add(new_doc)
                                except Exception as e:
                                    flash(f'Error uploading {sub_label}: {str(e)}', 'danger')
            else:
                # Handle single document input
                field_name = f"doc_field_{i}"
                if field_name in request.files:
                    file = request.files[field_name]
                    if file and file.filename != '':
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                        fname = secure_filename(f"{current_user.id}_{new_app.id}_{timestamp}_{file.filename}")
                        if supabase:
                            try:
                                file_bytes = file.read()
                                supabase.storage.from_('documents').upload(
                                    path=fname,
                                    file=file_bytes,
                                    file_options={"content-type": file.content_type}
                                )
                                new_doc = ApplicationDocument(
                                    application_id=new_app.id,
                                    filename=fname,
                                    original_name=file.filename,
                                    doc_label=doc_field.get('label', f'Document {i+1}'),
                                    uploaded_by='user',
                                    doc_type='request'
                                )
                                db.session.add(new_doc)
                            except Exception as e:
                                flash(f'Error uploading {doc_field.get("label", "document")}: {str(e)}', 'danger')
        
        db.session.commit()
        flash(f'Your application for {service.title} has been submitted successfully!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('book_service.html', service=service, schema=schema, doc_fields=doc_fields)

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
    total_users = User.query.filter_by(role='user').count()
    total_services = Service.query.count()
    total_applications = Application.query.count()
    pending_applications = Application.query.filter_by(status='Pending').count()
    completed_applications = Application.query.filter_by(status='Completed').count()
    
    # Recent applications
    recent_apps = Application.query.order_by(Application.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                           total_users=total_users,
                           total_services=total_services,
                           total_applications=total_applications,
                           pending_applications=pending_applications,
                           completed_applications=completed_applications,
                           recent_apps=recent_apps)

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
        schema_str = request.form.get('form_schema') 
        docs_str = request.form.get('required_documents')
        
        if not title or not description:
            flash('Title and description are required.', 'danger')
            return redirect(url_for('manage_services'))
            
        if schema_str and schema_str.strip():
            try:
                json.loads(schema_str)
            except Exception as e:
                flash(f'Invalid JSON schema: {e}', 'danger')
                return redirect(url_for('manage_services'))
        else:
            schema_str = None

        if docs_str and docs_str.strip():
            try:
                json.loads(docs_str)
            except:
                docs_str = None
        else:
            docs_str = None
            
        new_service = Service(title=title, description=description, form_schema=schema_str, required_documents=docs_str)
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
        
        schema_str = request.form.get('form_schema')
        if schema_str and schema_str.strip():
            try:
                json.loads(schema_str)
                service.form_schema = schema_str
            except:
                flash('Invalid JSON for form schema.', 'danger')
                return redirect(url_for('edit_service', service_id=service_id))
        elif schema_str is not None:
            service.form_schema = None
        
        docs_str = request.form.get('required_documents')
        if docs_str and docs_str.strip():
            try:
                json.loads(docs_str)
                service.required_documents = docs_str
            except:
                flash('Invalid JSON for required documents.', 'danger')
                return redirect(url_for('edit_service', service_id=service_id))
        elif docs_str is not None:
            service.required_documents = None
        
        db.session.commit()
        flash(f'Service "{service.title}" updated successfully.', 'success')
        return redirect(url_for('manage_services'))
    
    # Parse for display
    schema = []
    if service.form_schema:
        try:
            schema = json.loads(service.form_schema)
        except:
            pass
    doc_fields = []
    if service.required_documents:
        try:
            doc_fields = json.loads(service.required_documents)
        except:
            pass
    
    return render_template('admin/edit_service.html', service=service, schema=schema, doc_fields=doc_fields)

@app.route('/manage/services/<int:service_id>/delete', methods=['POST'])
@admin_required
def delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    Application.query.filter_by(service_id=service.id).delete()
    db.session.delete(service)
    db.session.commit()
    flash(f'Service {service.title} deleted successfully.', 'success')
    return redirect(url_for('manage_services'))

# ===================== ADMIN — APPLICATION MANAGEMENT =====================

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

@app.route('/manage/applications/<int:app_id>')
@admin_required
def application_detail(app_id):
    app_item = Application.query.get_or_404(app_id)
    data = None
    if app_item.submitted_data:
        try:
            data = json.loads(app_item.submitted_data)
        except:
            pass
    
    # Get all documents
    user_docs = ApplicationDocument.query.filter_by(application_id=app_id, doc_type='request').all()
    admin_docs = ApplicationDocument.query.filter_by(application_id=app_id, doc_type='response').all()
    
    # Generate signed URLs
    user_doc_urls = []
    for doc in user_docs:
        url = None
        if supabase:
            try:
                result = supabase.storage.from_('documents').create_signed_url(doc.filename, 60*60)
                if result:
                    url = result.get('signedURL')
            except:
                pass
        user_doc_urls.append({'doc': doc, 'url': url})
    
    admin_doc_urls = []
    for doc in admin_docs:
        url = None
        if supabase:
            try:
                result = supabase.storage.from_('documents').create_signed_url(doc.filename, 60*60)
                if result:
                    url = result.get('signedURL')
            except:
                pass
        admin_doc_urls.append({'doc': doc, 'url': url})
    
    # Legacy single document
    legacy_doc_url = None
    if app_item.document_path and supabase:
        try:
            result = supabase.storage.from_('documents').create_signed_url(app_item.document_path, 60*60)
            if result:
                legacy_doc_url = result.get('signedURL')
        except:
            pass
    
    return render_template('admin/application_detail.html', 
                           app=app_item, data=data, 
                           user_docs=user_doc_urls, admin_docs=admin_doc_urls,
                           legacy_doc_url=legacy_doc_url)

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
    
    # Redirect back to detail page if came from there
    if request.form.get('from_detail'):
        return redirect(url_for('application_detail', app_id=app_id))
    return redirect(url_for('manage_applications'))

@app.route('/manage/applications/<int:app_id>/upload', methods=['POST'])
@admin_required
def admin_upload_document(app_id):
    """Admin uploads completed/updated documents for the user."""
    app_item = Application.query.get_or_404(app_id)
    
    doc_label = request.form.get('doc_label', 'Updated Document')
    
    if 'admin_document' in request.files:
        file = request.files['admin_document']
        if file and file.filename != '':
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            fname = secure_filename(f"admin_{app_id}_{timestamp}_{file.filename}")
            
            if supabase:
                try:
                    file_bytes = file.read()
                    supabase.storage.from_('documents').upload(
                        path=fname,
                        file=file_bytes,
                        file_options={"content-type": file.content_type}
                    )
                    new_doc = ApplicationDocument(
                        application_id=app_id,
                        filename=fname,
                        original_name=file.filename,
                        doc_label=doc_label,
                        uploaded_by='admin',
                        doc_type='response'
                    )
                    db.session.add(new_doc)
                    db.session.commit()
                    flash(f'Document "{doc_label}" uploaded successfully for the user.', 'success')
                except Exception as e:
                    flash(f'Upload error: {str(e)}', 'danger')
            else:
                flash('Storage is not configured.', 'danger')
    
    return redirect(url_for('application_detail', app_id=app_id))

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
    except:
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
                'shop_phone': '+91 9837957711',
                'shop_email': 'contact@faizinternet.com',
                'shop_timings': 'Mon - Sat: 9AM - 8PM',
                'shop_map_url': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3510.123456789!2d78.0!3d28.5!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zMjjCsDMwJzAwLjAiTiA3OMKwMDAnMDAuMCJF!5e0!3m2!1sen!2sin!4v1234567890'
            }
            for k, v in defaults.items():
                db.session.add(SiteSetting(key=k, value=v))
            db.session.commit()
        
        if Service.query.count() == 0:
            services_data = [
                {
                    'title': 'Aadhaar Card Services', 
                    'desc': 'Aadhaar Address Update, Aadhaar Download, Find Lost Aadhaar, Get Aadhaar without OTP',
                    'icon': 'img/aadhaar_logo.jpg',
                    'schema': [
                        {'name': 'applicant_name', 'label': 'Full Name', 'type': 'text', 'required': True},
                        {'name': 'aadhar_number', 'label': 'Aadhaar Number', 'type': 'text', 'required': False},
                        {'name': 'service_type', 'label': 'Select Service', 'type': 'select', 'options': ['Address Update', 'Download Aadhaar', 'Find Lost Aadhaar', 'Aadhaar without OTP'], 'required': True}
                    ],
                    'docs': [
                        {'label': 'Aadhaar Card Copy', 'required': True},
                        {'label': 'Address Proof', 'required': False}
                    ]
                },
                {
                    'title': 'PAN Card Service', 
                    'desc': 'New PAN, Correction or Reprint',
                    'icon': 'img/csc_logo.jpg',
                    'schema': [
                        {'name': 'applicant_name', 'label': 'Full Name', 'type': 'text', 'required': True},
                        {'name': 'pan_number', 'label': 'Existing PAN (if correction)', 'type': 'text', 'required': False}
                    ],
                    'docs': [
                        {'label': 'ID Proof', 'required': True}
                    ]
                },
                {
                    'title': 'eDistrict Services', 
                    'desc': 'Income, Caste, Domicile, Birth & Death Certificate',
                    'icon': 'img/edistrict_logo.jpg',
                    'schema': [
                        {'name': 'applicant_name', 'label': 'Applicant Name', 'type': 'text', 'required': True},
                        {'name': 'certificate_type', 'label': 'Type of Certificate', 'type': 'text', 'required': True}
                    ],
                    'docs': [
                        {'label': 'Supporting Documents', 'required': True}
                    ]
                },
                {
                    'title': 'Voter ID Services', 
                    'desc': 'New Registration, Correction, EPIC Download',
                    'icon': 'img/voter_logo.jpg',
                    'schema': [
                        {'name': 'applicant_name', 'label': 'Voter Name', 'type': 'text', 'required': True}
                    ],
                    'docs': [
                        {'label': 'Photo ID Proof', 'required': True}
                    ]
                }
            ]
            
            for s in services_data:
                db.session.add(Service(
                    title=s['title'], 
                    description=s['desc'], 
                    icon_path=s['icon'],
                    form_schema=json.dumps(s['schema']),
                    required_documents=json.dumps(s.get('docs', []))
                ))
            db.session.commit()

# Ensure tables exist on Vercel (create_all is safe to call multiple times)
with app.app_context():
    try:
        db.create_all()
    except:
        pass

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
