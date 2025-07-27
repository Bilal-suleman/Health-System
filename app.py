# app.py
import os
import sys
from datetime import datetime, date, timedelta
import secrets
import logging
from logging.handlers import RotatingFileHandler
# --- External Dependencies ---
from flask import Flask, render_template_string, request, jsonify, redirect, url_for, flash, g, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, DateField, SelectField, IntegerField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Optional, Length
from werkzeug.security import generate_password_hash, check_password_hash
# --- Logging Setup ---
if not os.path.exists('logs'):
    os.mkdir('logs')
file_handler = RotatingFileHandler('logs/healthsys.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
file_handler.setLevel(logging.INFO)
logging.basicConfig(handlers=[file_handler], level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
logger = logging.getLogger(__name__)
# --- Flask App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(16)

# --- Updated Database Path Configuration ---
# Allow overriding the database path with an environment variable, defaulting to the current directory
DB_PATH = os.environ.get('DATABASE_PATH') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'healthsys_advanced.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
# --- End of updated section ---
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# init_db() # Keep this commented or handled as discussed previously
migrate = Migrate(app, db)
# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='Nurse')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    consultations = db.relationship('Consultation', backref='doctor', lazy='dynamic')
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    def __repr__(self):
        return f'<User {self.name} ({self.role})>'
@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))
class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    qid = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    contact_number = db.Column(db.String(20), index=True)
    date_of_birth = db.Column(db.Date)
    address = db.Column(db.Text)
    last_visit = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    consultations = db.relationship('Consultation', backref='patient', lazy='dynamic', cascade="all, delete-orphan")
    def age(self):
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None
class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    stock_level = db.Column(db.Integer, nullable=False, default=0)
    location = db.Column(db.String(100))
    expiry_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def status(self):
        if self.expiry_date and self.expiry_date < date.today():
            return 'Expired'
        elif self.stock_level <= 10:
            return 'Low Stock'
        else:
            return 'In Stock'
class Consultation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    consultation_date = db.Column(db.Date, nullable=False, default=date.today)
    diagnosis = db.Column(db.String(200))
    notes = db.Column(db.Text)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    prescriptions = db.relationship('Prescription', backref='consultation', lazy='dynamic', cascade="all, delete-orphan")
class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medication = db.Column(db.String(200), nullable=False)
    dosage = db.Column(db.String(100), nullable=False)
    instructions = db.Column(db.Text)
    dispensed = db.Column(db.Boolean, default=False, index=True)
    dispensed_at = db.Column(db.DateTime, nullable=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultation.id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'), nullable=True)
    medicine = db.relationship('Medicine')
# --- Forms ---
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')
# --- Permission Decorator (Simplified for clarity and avoiding endpoint conflicts) ---
# Wrap the login_required to ensure unique endpoint handling
def permission_required(permission):
    def decorator(f):
        # Apply login_required first
        f = login_required(f)
        # Then apply our custom logic
        def decorated_function(*args, **kwargs):
            user_role = getattr(current_user, 'role', None)
            if not user_role:
                flash('Access denied.', 'error')
                return redirect(url_for('index'))
            permission_map = {
                'view_patients': ['Admin', 'Doctor', 'Nurse'],
                'add_patient': ['Admin', 'Doctor', 'Nurse'],
                'edit_patient': ['Admin', 'Doctor'],
                'delete_patient': ['Admin'],
                'view_consultations': ['Admin', 'Doctor', 'Nurse'],
                'add_consultation': ['Admin', 'Doctor'],
                'edit_consultation': ['Admin', 'Doctor'],
                'delete_consultation': ['Admin'],
                'view_pharmacy': ['Admin', 'Pharmacist'],
                'manage_pharmacy': ['Admin', 'Pharmacist'],
                'dispense_prescription': ['Admin', 'Pharmacist'],
                'view_users': ['Admin'],
                'manage_users': ['Admin']
            }
            allowed_roles = permission_map.get(permission, [])
            if user_role not in allowed_roles:
                logger.warning(f"User {current_user.email} (Role: {user_role}) denied access to {permission}")
                flash('Access denied.', 'error')
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Access denied.'}), 403
                return redirect(url_for('index'))
            logger.info(f"User {current_user.email} (Role: {user_role}) granted access to {permission}")
            return f(*args, **kwargs)
        # Preserve the original function name to help avoid endpoint conflicts
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator
# --- Database Initialization ---
# Moved the definition BEFORE any call to init_db()
def init_db():
    with app.app_context(): # Ensure app context is available
        db.create_all()
        logger.info("Database tables created/checked.")
        if User.query.first() is None:
            logger.info("Seeding initial data...")
            try:
                users_data = [
                    {'name': 'Dr. Aisha Al-Emadi', 'email': 'a.emadi@healthsys.demo', 'role': 'Doctor', 'password': 'password'},
                    {'name': 'Nadia Hassan', 'email': 'n.hassan@healthsys.demo', 'role': 'Nurse', 'password': 'password'},
                    {'name': 'Dr. Omar Khalid', 'email': 'o.khalid@healthsys.demo', 'role': 'Doctor', 'password': 'password'},
                    {'name': 'Layla Mahmoud', 'email': 'l.mahmoud@healthsys.demo', 'role': 'Pharmacist', 'password': 'password'},
                    {'name': 'Admin User', 'email': 'admin@healthsys.demo', 'role': 'Admin', 'password': 'password'}
                ]
                users = []
                for ud in users_data:
                    user = User(name=ud['name'], email=ud['email'], role=ud['role'])
                    user.set_password(ud['password'])
                    users.append(user)
                db.session.add_all(users)
                db.session.commit()
                patients_data = [
                    {'qid': '29850615001', 'name': 'Fatima Nasser', 'contact_number': '55123456', 'last_visit': date(2025, 7, 20), 'date_of_birth': date(1985, 6, 15), 'address': 'Doha, Qatar'},
                    {'qid': '29901103002', 'name': 'Mohammed Saleh', 'contact_number': '55234567', 'last_visit': date(2025, 7, 18), 'date_of_birth': date(1990, 11, 3), 'address': 'Al Rayyan, Qatar'},
                    {'qid': '29780228003', 'name': 'Yousef Ali', 'contact_number': '55345678', 'last_visit': date(2025, 7, 10), 'date_of_birth': date(1978, 2, 28), 'address': 'Al Wakrah, Qatar'},
                    {'qid': '30010812004', 'name': 'Sana Kamal', 'contact_number': '55456789', 'last_visit': date(2025, 7, 5), 'date_of_birth': date(2001, 8, 12), 'address': 'Umm Salal, Qatar'}
                ]
                patients = [Patient(**pd) for pd in patients_data]
                db.session.add_all(patients)
                db.session.commit()
                medicines_data = [
                    {'name': 'Metformin 500mg', 'stock_level': 150, 'location': 'Doha Main Clinic', 'expiry_date': date(2026, 12, 31)},
                    {'name': 'Amoxicillin 250mg', 'stock_level': 45, 'location': 'Doha Main Clinic', 'expiry_date': date(2026, 8, 31)},
                    {'name': 'Panadol 500mg', 'stock_level': 250, 'location': 'Doha Main Clinic', 'expiry_date': date(2027, 1, 31)},
                    {'name': 'Aspirin 75mg', 'stock_level': 15, 'location': 'Doha Main Clinic', 'expiry_date': date(2026, 2, 28)}
                ]
                medicines = [Medicine(**md) for md in medicines_data]
                db.session.add_all(medicines)
                db.session.commit()
                if len(patients) >= 3 and len(users) >= 3:
                    consultations_data = [
                        {'patient_id': patients[0].id, 'doctor_id': users[0].id, 'consultation_date': date.today() - timedelta(days=1), 'diagnosis': "Hypertension", 'notes': "Patient reports occasional headaches."},
                        {'patient_id': patients[1].id, 'doctor_id': users[0].id, 'consultation_date': date.today() - timedelta(days=3), 'diagnosis': "Type 2 Diabetes", 'notes': "HbA1c checked, results pending."},
                        {'patient_id': patients[2].id, 'doctor_id': users[2].id, 'consultation_date': date.today() - timedelta(days=10), 'diagnosis': "Migraine", 'notes': "Prescribed new medication for prevention."}
                    ]
                    consultations = [Consultation(**cd) for cd in consultations_data]
                    db.session.add_all(consultations)
                    db.session.commit()
                    if len(consultations) >= 3 and len(medicines) >= 2:
                        prescriptions_data = [
                            {'consultation_id': consultations[0].id, 'medication': 'Lisinopril 10mg', 'dosage': '1 tablet daily', 'instructions': 'Take in the morning.'},
                            {'consultation_id': consultations[1].id, 'medication': 'Metformin 500mg', 'dosage': '1 tablet twice daily', 'instructions': 'Take with meals.', 'medicine_id': medicines[0].id},
                            {'consultation_id': consultations[2].id, 'medication': 'Propranolol 40mg', 'dosage': '1 tablet twice daily', 'instructions': 'Take as needed for migraine.'}
                        ]
                        prescriptions = [Prescription(**pd) for pd in prescriptions_data]
                        db.session.add_all(prescriptions)
                        db.session.commit()
                logger.info("Database seeded successfully.")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error seeding database: {e}")
                print(f"Error seeding database: {e}", file=sys.stderr)
        else:
            logger.info("Database already contains data, skipping seeding.")

# --- Call init_db() AFTER its definition ---
# This ensures the function exists before calling it.
# For production/Gunicorn, you might manage this differently (e.g., via a setup script or migration).
# Calling it here will run it every time the app module is imported, which might be okay for simple dev setup.
# Consider if you want this automatic or manual.
# init_db() # <-- Uncomment this line if you want automatic seeding on import.
# It's often better practice to call it manually or via a separate command/script for production.

# --- Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            logger.info(f"User {user.email} logged in.")
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            if not next_page or '.' in next_page:
                next_page = url_for('index')
            return redirect(next_page)
        else:
            flash('Invalid email or password', 'error')
            logger.warning(f"Failed login attempt for {form.email.data}")
    return render_template_string(LOGIN_TEMPLATE, title='Sign In', form=form)
@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    logger.info("User logged out.")
    return redirect(url_for('login'))
@app.route('/')
@app.route('/index')
@login_required
def index():
    return render_template_string(DASHBOARD_TEMPLATE, title='Dashboard')
# --- API Routes ---
@app.route('/api/dashboard')
@permission_required('view_patients')
def api_dashboard():
    one_week_ago = date.today() - timedelta(days=7)
    consultations_this_week = Consultation.query.filter(Consultation.consultation_date >= one_week_ago).count()
    return jsonify({
        'total_patients': Patient.query.count(),
        'consultations_this_week': consultations_this_week,
        'low_stock': Medicine.query.filter(Medicine.stock_level <= 10).count(),
        'recent_consultations': [{
            'consultation_date': c.consultation_date.strftime('%Y-%m-%d'),
            'patient_name': c.patient.name,
            'doctor_name': c.doctor.name,
            'diagnosis': c.diagnosis
        } for c in Consultation.query.order_by(Consultation.consultation_date.desc()).limit(5).all()]
    })
@app.route('/api/users')
@permission_required('view_users')
def api_get_users(): # Renamed function to be more explicit
    users = User.query.all()
    return jsonify([{'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role} for u in users])
@app.route('/api/users/doctors')
@login_required
def api_get_doctors(): # Renamed function
    doctors = User.query.filter_by(role='Doctor').all()
    return jsonify([{'id': d.id, 'name': d.name} for d in doctors])
@app.route('/api/patients')
@permission_required('view_patients')
def api_get_patients(): # Renamed function
    patients = Patient.query.order_by(Patient.id.desc()).all()
    return jsonify([{
        'id': p.id,
        'qid': p.qid,
        'name': p.name,
        'contact_number': p.contact_number,
        'last_visit': p.last_visit.isoformat() if p.last_visit else None,
        'date_of_birth': p.date_of_birth.isoformat() if p.date_of_birth else None,
        'address': p.address,
        'age': p.age()
    } for p in patients])
@app.route('/api/patients/<int:id>')
@permission_required('view_patients')
def api_get_patient(id): # Renamed function
    patient = Patient.query.get_or_404(id)
    return jsonify({
        'id': patient.id,
        'qid': patient.qid,
        'name': patient.name,
        'contact_number': patient.contact_number,
        'last_visit': patient.last_visit.isoformat() if patient.last_visit else None,
        'date_of_birth': patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        'address': patient.address,
        'age': patient.age()
    })
@app.route('/api/patients/<int:id>/consultations')
@permission_required('view_consultations')
def api_get_patient_consultations(id): # Renamed function
    consultations = Consultation.query.filter_by(patient_id=id).order_by(Consultation.consultation_date.desc()).all()
    return jsonify([{
        'id': c.id,
        'consultation_date': c.consultation_date.strftime('%Y-%m-%d'),
        'diagnosis': c.diagnosis,
        'notes': c.notes,
        'doctor_name': c.doctor.name
    } for c in consultations])
# Add other API routes similarly (api_create_patient, api_update_patient, etc.)
# For brevity, I'll stop here, but ensure ALL your API route functions have unique names.
# --- HTML Templates (Embedded) ---
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - HealthSys Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>body { font-family: 'Inter', sans-serif; }</style>
</head>
<body class="bg-slate-100 text-slate-800">
<div class="min-h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded-lg shadow-md w-full max-w-md">
        <h2 class="text-2xl font-bold mb-6 text-center">Login to HealthSys Pro</h2>
        <form method="POST">
            {{ form.hidden_tag() }}
            <div class="mb-4">
                {{ form.email.label(class="block text-sm font-medium text-slate-700 mb-1") }}
                {{ form.email(class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500") }}
                {% if form.email.errors %}
                    <div class="text-red-600 text-sm mt-1">
                        {% for error in form.email.errors %}<span>{{ error }}</span>{% endfor %}
                    </div>
                {% endif %}
            </div>
            <div class="mb-4">
                {{ form.password.label(class="block text-sm font-medium text-slate-700 mb-1") }}
                {{ form.password(class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500") }}
                 {% if form.password.errors %}
                    <div class="text-red-600 text-sm mt-1">
                        {% for error in form.password.errors %}<span>{{ error }}</span>{% endfor %}
                    </div>
                {% endif %}
            </div>
            <div class="flex items-center justify-between mb-6">
                <div class="flex items-center">
                    {{ form.remember_me(class="h-4 w-4 text-blue-600 border-slate-300 rounded focus:ring-blue-500") }}
                    {{ form.remember_me.label(class="ml-2 block text-sm text-slate-700") }}
                </div>
            </div>
            {{ form.submit(class="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2") }}
        </form>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="mt-4">
                    {% for category, message in messages %}
                        <div class="p-3 rounded text-sm {% if category == 'error' %}bg-red-100 text-red-700{% else %}bg-green-100 text-green-700{% endif %}">
                            {{ message }}
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        <div class="mt-4 text-sm text-slate-500">
            <p><strong>Demo Credentials:</strong></p>
            <ul class="list-disc pl-5 space-y-1">
                <li>Admin: admin@healthsys.demo / password</li>
                <li>Doctor: a.emadi@healthsys.demo / password</li>
                <li>Nurse: n.hassan@healthsys.demo / password</li>
                <li>Pharmacist: l.mahmoud@healthsys.demo / password</li>
            </ul>
        </div>
    </div>
</div>
</body>
</html>
"""
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - HealthSys Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .nav-link.active { background-color: #1e293b; color: white; }
    </style>
</head>
<body class="bg-slate-100 text-slate-800">
<div class="flex h-screen">
    <aside class="w-64 bg-slate-900 text-white flex flex-col">
        <div class="p-6 border-b border-slate-800">
            <h1 class="text-xl font-bold">HealthSys Pro</h1>
            <p class="text-sm text-slate-400">{{ current_user.name }}
                <span class="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-0.5 rounded">{{ current_user.role }}</span>
            </p>
        </div>
        <nav class="flex-1 p-4">
            <ul class="space-y-1">
                <li><a href="{{ url_for('index') }}" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700 active">
                    <svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>Dashboard</a></li>
                <li><a href="#" data-target="patients" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700">
                    <svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>Patients</a></li>
                <li><a href="#" data-target="consultations" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700">
                    <svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>Consultations</a></li>
                <li><a href="#" data-target="pharmacy" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700">
                    <svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21a9 9 0 0 0 9-9a9 9 0 0 0-9-9a9 9 0 0 0-9 9a9 9 0 0 0 9 9Z"/><path d="m10 13 2 2 2-2"/><path d="M10 9h4"/></svg>Pharmacy</a></li>
                {% if current_user.role == 'Admin' %}
                <li><a href="#" data-target="settings" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700">
                    <svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>Users</a></li>
                {% endif %}
                <li><a href="{{ url_for('logout') }}" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700 text-red-400">
                    <svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>Logout</a></li>
            </ul>
        </nav>
    </aside>
    <main class="flex-1 overflow-auto p-6">
        <section id="dashboard" class="content-section">
            <h2 class="text-2xl font-bold mb-6">Dashboard</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="bg-white rounded-xl shadow-sm p-6">
                    <div class="flex items-center">
                        <div class="p-3 rounded-lg bg-blue-100 text-blue-600 mr-4">
                            <svg class="w-6 h-6" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>
                        </div>
                        <div>
                            <p class="text-sm text-slate-500">Total Patients</p>
                            <p id="total-patients" class="text-2xl font-bold">0</p>
                        </div>
                    </div>
                </div>
                <div class="bg-white rounded-xl shadow-sm p-6">
                    <div class="flex items-center">
                        <div class="p-3 rounded-lg bg-green-100 text-green-600 mr-4">
                            <svg class="w-6 h-6" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                        </div>
                        <div>
                            <p class="text-sm text-slate-500">Consultations (This Week)</p>
                            <p id="consultations-week" class="text-2xl font-bold">0</p>
                        </div>
                    </div>
                </div>
                <div class="bg-white rounded-xl shadow-sm p-6">
                    <div class="flex items-center">
                        <div class="p-3 rounded-lg bg-amber-100 text-amber-600 mr-4">
                            <svg class="w-6 h-6" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21a9 9 0 0 0 9-9a9 9 0 0 0-9-9a9 9 0 0 0-9 9a9 9 0 0 0 9 9Z"/><path d="m10 13 2 2 2-2"/><path d="M10 9h4"/></svg>
                        </div>
                        <div>
                            <p class="text-sm text-slate-500">Low Stock Items</p>
                            <p id="low-stock" class="text-2xl font-bold">0</p>
                        </div>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-xl shadow-sm p-6">
                <h3 class="text-lg font-semibold mb-4">Recent Consultations</h3>
                <div id="recent-consultations" class="space-y-4">
                </div>
            </div>
        </section>
        <section id="patients" class="content-section hidden"> <h2 class="text-2xl font-bold">Patients</h2><p>Implement patient list/view here.</p> </section>
        <section id="consultations" class="content-section hidden"> <h2 class="text-2xl font-bold">Consultations</h2><p>Implement consultation list/view here.</p> </section>
        <section id="pharmacy" class="content-section hidden"> <h2 class="text-2xl font-bold">Pharmacy</h2><p>Implement pharmacy view here.</p> </section>
        <section id="settings" class="content-section hidden"> <h2 class="text-2xl font-bold">Users (Admin)</h2><p>Implement user management here.</p> </section>
    </main>
</div>
<script>
const sections = document.querySelectorAll('.content-section');
const navLinks = document.querySelectorAll('.nav-link:not([href="{{ url_for(\'logout\') }}"])');
function showSection(targetId) {
    sections.forEach(section => section.classList.add('hidden'));
    const targetSection = document.getElementById(targetId);
    if (targetSection) targetSection.classList.remove('hidden');
    navLinks.forEach(link => link.classList.remove('active'));
    const activeLink = document.querySelector(`.nav-link[data-target="${targetId}"]`);
    if (activeLink) activeLink.classList.add('active');
    if(targetId === 'dashboard') loadDashboard();
}
async function loadDashboard() {
    try {
        const response = await fetch(`/api/dashboard`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        document.getElementById('total-patients').textContent = data.total_patients;
        document.getElementById('consultations-week').textContent = data.consultations_this_week;
        document.getElementById('low-stock').textContent = data.low_stock;
        const container = document.getElementById('recent-consultations');
        container.innerHTML = '';
        data.recent_consultations.forEach(c => {
            const item = document.createElement('div');
            item.className = 'flex items-center justify-between p-4 border border-slate-200 rounded-lg';
            item.innerHTML = `
                <div><p class="font-medium">${c.patient_name}</p><p class="text-sm text-slate-500">${c.diagnosis}</p></div>
                <div class="text-right"><p class="text-sm font-medium">${c.doctor_name}</p><p class="text-xs text-slate-500">${c.consultation_date}</p></div>
            `;
            container.appendChild(item);
        });
    } catch (error) { console.error('Dashboard load error:', error); }
}
document.addEventListener('DOMContentLoaded', () => { showSection('dashboard'); });
navLinks.forEach(link => {
    link.addEventListener('click', (e) => { e.preventDefault(); showSection(link.dataset.target); });
});
</script>
</body>
</html>
"""
if __name__ == '__main__':
    # Ensure the database is initialized when running the script directly
    # This is typically used for development. For production (Gunicorn), the app factory pattern or migrations are preferred.
    # init_db() # You can uncomment this if you want seeding to happen only when running `python app.py`
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask application on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False) # Set debug=False for production
