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
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'healthsys_advanced.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# Removed init_db() call from here - moved below its definition
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
# ... (LOGIN_TEMPLATE and DASHBOARD_TEMPLATE remain the same) ...
# ... (Rest of the file remains the same) ...

if __name__ == '__main__':
    # Ensure the database is initialized when running the script directly
    # This is typically used for development. For production (Gunicorn), the app factory pattern or migrations are preferred.
    # init_db() # You can uncomment this if you want seeding to happen only when running `python app.py`
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask application on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False) # Set debug=False for production
