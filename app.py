# app.py
import os
from flask import Flask, jsonify, request, render_template_string, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta, datetime
import random
import threading
import uuid

# --- App & Database Configuration ---
app = Flask(__name__)
# Secret key for sessions (in production, use a strong random key from env var)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_demo_purposes_only_change_this') 

# Use a file-based SQLite database for persistence
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'healthsys.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False) # Simplified for demo
    role = db.Column(db.String(50), nullable=False) # 'Doctor', 'Nurse', 'Admin', 'Pharmacist'
    consultations = db.relationship('Consultation', backref='doctor', lazy=True)

    def set_password(self, password):
        # Very simple "hashing" for demo - DO NOT use in production!
        self.password_hash = str(hash(password + "demo_salt"))

    def check_password(self, password):
        # Very simple "check" for demo - DO NOT use in production!
        return self.password_hash == str(hash(password + "demo_salt"))

    def __repr__(self):
        return f'<User {self.name} ({self.role})>'

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    qid = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    contact_number = db.Column(db.String(20))
    last_visit = db.Column(db.Date)
    date_of_birth = db.Column(db.Date) # New field
    address = db.Column(db.Text) # New field
    consultations = db.relationship('Consultation', backref='patient', lazy=True, cascade="all, delete-orphan")

    def age(self):
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None

    def __repr__(self):
        return f'<Patient {self.name}>'

class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    stock_level = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100))
    expiry_date = db.Column(db.Date)
    status = db.Column(db.String(50)) # 'In Stock', 'Low Stock', 'Reorder'

    def __repr__(self):
        return f'<Medicine {self.name}>'

class Consultation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    consultation_date = db.Column(db.Date, nullable=False)
    diagnosis = db.Column(db.String(200))
    notes = db.Column(db.Text) # New field
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    prescriptions = db.relationship('Prescription', backref='consultation', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Consultation {self.id} for {self.patient.name}>'

class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medication = db.Column(db.String(200), nullable=False) # Name or description
    dosage = db.Column(db.String(100), nullable=False) # e.g., "1 tablet twice daily"
    instructions = db.Column(db.Text) # e.g., "Take with food"
    dispensed = db.Column(db.Boolean, default=False) # New field for pharmacy
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultation.id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'), nullable=True) # Link to Medicine if applicable

    medicine = db.relationship('Medicine') # Relationship for easy access

    def __repr__(self):
        return f'<Prescription {self.medication}>'

# --- Database Initialization Logic ---
_init_lock = threading.Lock()
_is_initialized = False

def initialize_database():
    """Initialize the database: create tables and seed data if needed."""
    global _is_initialized
    with _init_lock:
        if not _is_initialized:
            print("Initializing database...")
            db.create_all()
            seed_initial_data()
            _is_initialized = True
            print("Database initialization complete.")

def seed_initial_data():
    """Populate the database with initial data if it's empty."""
    if User.query.first() is None:
        print("Seeding database with initial data...")
        try:
            # Seed Users (password is 'password' for all)
            u1 = User(name='Dr. Aisha Al-Emadi', email='a.emadi@healthsys.demo', role='Doctor')
            u1.set_password('password')
            u2 = User(name='Nadia Hassan', email='n.hassan@healthsys.demo', role='Nurse')
            u2.set_password('password')
            u3 = User(name='Dr. Omar Khalid', email='o.khalid@healthsys.demo', role='Doctor')
            u3.set_password('password')
            u4 = User(name='Layla Mahmoud', email='l.mahmoud@healthsys.demo', role='Pharmacist')
            u4.set_password('password')
            u5 = User(name='Admin User', email='admin@healthsys.demo', role='Admin')
            u5.set_password('password')
            db.session.add_all([u1, u2, u3, u4, u5])
            db.session.commit()

            # Seed Patients
            p1 = Patient(qid='29850615001', name='Fatima Nasser', contact_number='55123456', last_visit=date(2025, 7, 20), date_of_birth=date(1985, 6, 15), address='Doha, Qatar')
            p2 = Patient(qid='29901103002', name='Mohammed Saleh', contact_number='55234567', last_visit=date(2025, 7, 18), date_of_birth=date(1990, 11, 3), address='Al Rayyan, Qatar')
            p3 = Patient(qid='29780228003', name='Yousef Ali', contact_number='55345678', last_visit=date(2025, 7, 10), date_of_birth=date(1978, 2, 28), address='Al Wakrah, Qatar')
            p4 = Patient(qid='30010812004', name='Sana Kamal', contact_number='55456789', last_visit=date(2025, 7, 5), date_of_birth=date(2001, 8, 12), address='Umm Salal, Qatar')
            db.session.add_all([p1, p2, p3, p4])
            db.session.commit()

            # Seed Pharmacy
            m1 = Medicine(name='Metformin 500mg', stock_level=150, location='Doha Main Clinic', expiry_date=date(2026, 12, 31), status='In Stock')
            m2 = Medicine(name='Amoxicillin 250mg', stock_level=45, location='Doha Main Clinic', expiry_date=date(2026, 8, 31), status='Low Stock')
            m3 = Medicine(name='Panadol 500mg', stock_level=250, location='Doha Main Clinic', expiry_date=date(2027, 1, 31), status='In Stock')
            m4 = Medicine(name='Aspirin 75mg', stock_level=15, location='Doha Main Clinic', expiry_date=date(2026, 2, 28), status='Reorder')
            db.session.add_all([m1, m2, m3, m4])
            db.session.commit()

            # Seed Consultations
            c1 = Consultation(patient_id=p1.id, doctor_id=u1.id, consultation_date=date.today() - timedelta(days=1), diagnosis="Hypertension", notes="Patient reports occasional headaches.")
            c2 = Consultation(patient_id=p2.id, doctor_id=u1.id, consultation_date=date.today() - timedelta(days=3), diagnosis="Type 2 Diabetes", notes="HbA1c checked, results pending.")
            c3 = Consultation(patient_id=p3.id, doctor_id=u3.id, consultation_date=date.today() - timedelta(days=10), diagnosis="Migraine", notes="Prescribed new medication for prevention.")
            db.session.add_all([c1, c2, c3])
            db.session.commit()

            # Seed Prescriptions
            pr1 = Prescription(consultation_id=c1.id, medication='Lisinopril 10mg', dosage='1 tablet daily', instructions='Take in the morning.')
            pr2 = Prescription(consultation_id=c2.id, medication='Metformin 500mg', dosage='1 tablet twice daily', instructions='Take with meals.', medicine_id=m1.id)
            pr3 = Prescription(consultation_id=c3.id, medication='Propranolol 40mg', dosage='1 tablet twice daily', instructions='Take as needed for migraine.')
            db.session.add_all([pr1, pr2, pr3])
            db.session.commit()
            
            print("Database seeded successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"Error seeding database: {e}")
    else:
        print("Database already contains data, skipping seeding.")

@app.before_request
def ensure_initialized():
    initialize_database()

# --- Authentication Decorator ---
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            user = User.query.get(session['user_id'])
            if not user or user.role != required_role:
                 # Simplified check, could be extended for multiple roles
                 # For demo, redirect to dashboard or show unauthorized message
                 return jsonify({'error': 'Unauthorized access'}), 403 
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- HTML Template ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HealthSys Pro - Enhanced Demo</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .nav-link.active {
            background-color: #1e293b; /* slate-800 */
            color: white;
        }
        .role-badge {
            display: inline-block;
            padding: 0.2em 0.6em 0.3em;
            font-size: 75%;
            font-weight: 700;
            line-height: 1;
            text-align: center;
            white-space: nowrap;
            vertical-align: baseline;
            border-radius: 0.375rem; /* rounded-md */
        }
    </style>
</head>
<body class="bg-slate-100 text-slate-800">
    <!-- Login Modal -->
    <div id="loginModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 {{ 'hidden' if 'user_id' in session else '' }}">
        <div class="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <h3 class="text-lg font-semibold mb-4">Login</h3>
            <form id="loginForm">
                <div class="mb-4">
                    <label for="loginEmail" class="block text-sm font-medium text-slate-700 mb-1">Email</label>
                    <input type="email" id="loginEmail" name="email" required class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="mb-4">
                    <label for="loginPassword" class="block text-sm font-medium text-slate-700 mb-1">Password</label>
                    <input type="password" id="loginPassword" name="password" required class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="flex justify-end space-x-3">
                    <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200">Login</button>
                </div>
            </form>
            <div id="loginError" class="mt-2 text-red-600 text-sm hidden"></div>
        </div>
    </div>

    {% if 'user_id' in session %}
    <div class="flex h-screen">
        <!-- Sidebar -->
        <aside class="w-64 bg-slate-900 text-white flex flex-col">
            <div class="p-6 border-b border-slate-800">
                <h1 class="text-xl font-bold">HealthSys Pro</h1>
                <p class="text-sm text-slate-400">{{ session.get('user_name', 'User') }} 
                    <span class="role-badge bg-blue-100 text-blue-800">{{ session.get('user_role', 'Role') }}</span>
                </p>
            </div>
            <nav class="flex-1 p-4">
                <ul class="space-y-1">
                    <li><a href="#" data-target="dashboard" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700 active"><svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>Dashboard</a></li>
                    
                    <li><a href="#" data-target="patients" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700"><svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>Patients</a></li>
                    
                    <li><a href="#" data-target="consultations" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700"><svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>Consultations</a></li>
                    
                    <li><a href="#" data-target="pharmacy" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700"><svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21a9 9 0 0 0 9-9a9 9 0 0 0-9-9a9 9 0 0 0-9 9a9 9 0 0 0 9 9Z"/><path d="m10 13 2 2 2-2"/><path d="M10 9h4"/></svg>Pharmacy</a></li>
                    
                    {% if session.get('user_role') == 'Admin' %}
                    <li><a href="#" data-target="settings" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700"><svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>Users</a></li>
                    {% endif %}
                    
                    <li><a href="#" id="logoutBtn" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700 text-red-400"><svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>Logout</a></li>
                </ul>
            </nav>
        </aside>

        <!-- Main Content -->
        <main class="flex-1 overflow-auto p-6">
            <!-- Dashboard Section -->
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
                        <!-- Consultations will be loaded here -->
                    </div>
                </div>
            </section>

            <!-- Patients Section -->
            <section id="patients" class="content-section hidden">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-2xl font-bold">Patient Management</h2>
                    <button id="newPatientBtn" class="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg text-sm font-medium transition-colors duration-200">+ New Patient</button>
                </div>
                <div class="bg-white rounded-xl shadow-sm overflow-hidden mb-6">
                    <table class="min-w-full divide-y divide-slate-200">
                        <thead class="bg-slate-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">QID</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Name</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Age</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Contact</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Last Visit</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="patients-table-body" class="divide-y divide-slate-200">
                            <!-- Patient rows will be loaded here -->
                        </tbody>
                    </table>
                </div>
                
                <!-- Patient Detail Modal -->
                <div id="patientDetailModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center hidden z-50">
                     <div class="bg-white rounded-lg shadow-xl w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto">
                        <div class="flex justify-between items-center mb-4">
                            <h3 class="text-lg font-semibold">Patient Details</h3>
                            <button id="closePatientDetailBtn" class="text-slate-500 hover:text-slate-700">
                                <svg class="w-6 h-6" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                            </button>
                        </div>
                        <div id="patient-detail-content">
                            <!-- Patient details will be loaded here -->
                        </div>
                    </div>
                </div>
            </section>

            <!-- Consultations Section -->
            <section id="consultations" class="content-section hidden">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-2xl font-bold">Consultations</h2>
                    <button id="newConsultationBtn" class="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg text-sm font-medium transition-colors duration-200">+ New Consultation</button>
                </div>
                <div class="bg-white rounded-xl shadow-sm overflow-hidden">
                    <table class="min-w-full divide-y divide-slate-200">
                        <thead class="bg-slate-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Date</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Patient</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Doctor</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Diagnosis</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="consultations-table-body" class="divide-y divide-slate-200">
                            <!-- Consultation rows will be loaded here -->
                        </tbody>
                    </table>
                </div>
                
                <!-- Consultation Detail Modal -->
                <div id="consultationDetailModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center hidden z-50">
                     <div class="bg-white rounded-lg shadow-xl w-full max-w-3xl p-6 max-h-[90vh] overflow-y-auto">
                        <div class="flex justify-between items-center mb-4">
                            <h3 class="text-lg font-semibold">Consultation Details</h3>
                            <button id="closeConsultationDetailBtn" class="text-slate-500 hover:text-slate-700">
                                <svg class="w-6 h-6" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                            </button>
                        </div>
                        <div id="consultation-detail-content">
                            <!-- Consultation details will be loaded here -->
                        </div>
                    </div>
                </div>
            </section>

            <!-- Pharmacy Section -->
            <section id="pharmacy" class="content-section hidden">
                <h2 class="text-2xl font-bold mb-6">Pharmacy Inventory</h2>
                <div class="bg-white rounded-xl shadow-sm overflow-hidden mb-6">
                    <table class="min-w-full divide-y divide-slate-200">
                        <thead class="bg-slate-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Medicine</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Stock Level</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Location</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Expiry Date</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                            </tr>
                        </thead>
                        <tbody id="pharmacy-table-body" class="divide-y divide-slate-200">
                            <!-- Medicine rows will be loaded here -->
                        </tbody>
                    </table>
                </div>
                
                <h3 class="text-xl font-semibold mb-4">Pending Prescriptions</h3>
                <div class="bg-white rounded-xl shadow-sm overflow-hidden">
                    <table class="min-w-full divide-y divide-slate-200">
                        <thead class="bg-slate-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Patient</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Medication</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Dosage</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Doctor</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Date</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="prescriptions-table-body" class="divide-y divide-slate-200">
                            <!-- Prescription rows will be loaded here -->
                        </tbody>
                    </table>
                </div>
            </section>

            <!-- Users Section (Admin Only) -->
            <section id="settings" class="content-section hidden">
                <h2 class="text-2xl font-bold mb-6">Users</h2>
                <div class="bg-white rounded-xl shadow-sm overflow-hidden">
                    <table class="min-w-full divide-y divide-slate-200">
                        <thead class="bg-slate-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Name</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Email</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Role</th>
                            </tr>
                        </thead>
                        <tbody id="users-table-body" class="divide-y divide-slate-200">
                            <!-- User rows will be loaded here -->
                        </tbody>
                    </table>
                </div>
            </section>
        </main>
    </div>

    <!-- New Patient Modal -->
    <div id="patientModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center hidden z-50">
        <div class="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-semibold">Register New Patient</h3>
                <button id="closeModalBtn" class="text-slate-500 hover:text-slate-700">
                    <svg class="w-6 h-6" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
            </div>
            <form id="patientForm">
                <input type="hidden" id="patientId" name="id">
                <div class="mb-4">
                    <label for="qid" class="block text-sm font-medium text-slate-700 mb-1">QID *</label>
                    <input type="text" id="qid" name="qid" required class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="mb-4">
                    <label for="name" class="block text-sm font-medium text-slate-700 mb-1">Full Name *</label>
                    <input type="text" id="name" name="name" required class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="mb-4">
                    <label for="contact_number" class="block text-sm font-medium text-slate-700 mb-1">Contact Number</label>
                    <input type="text" id="contact_number" name="contact_number" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="mb-4">
                    <label for="date_of_birth" class="block text-sm font-medium text-slate-700 mb-1">Date of Birth</label>
                    <input type="date" id="date_of_birth" name="date_of_birth" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="mb-4">
                    <label for="address" class="block text-sm font-medium text-slate-700 mb-1">Address</label>
                    <textarea id="address" name="address" rows="2" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
                </div>
                <div class="mb-4">
                    <label for="last_visit" class="block text-sm font-medium text-slate-700 mb-1">Last Visit Date</label>
                    <input type="date" id="last_visit" name="last_visit" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="flex justify-end space-x-3">
                    <button type="button" id="cancelModalBtn" class="px-4 py-2 text-slate-700 bg-slate-200 rounded-lg hover:bg-slate-300 transition-colors duration-200">Cancel</button>
                    <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200">Save</button>
                </div>
            </form>
        </div>
    </div>

    <!-- New Consultation Modal -->
    <div id="consultationModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center hidden z-50">
        <div class="bg-white rounded-lg shadow-xl w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-semibold">New Consultation</h3>
                <button id="closeConsultationModalBtn" class="text-slate-500 hover:text-slate-700">
                    <svg class="w-6 h-6" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
            </div>
            <form id="consultationForm">
                <input type="hidden" id="consultationId" name="id">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div>
                        <label for="consultation_patient_id" class="block text-sm font-medium text-slate-700 mb-1">Patient *</label>
                        <select id="consultation_patient_id" name="patient_id" required class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                            <option value="">Select Patient</option>
                            <!-- Options will be populated dynamically -->
                        </select>
                    </div>
                    <div>
                        <label for="consultation_doctor_id" class="block text-sm font-medium text-slate-700 mb-1">Doctor *</label>
                        <select id="consultation_doctor_id" name="doctor_id" required class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                            <option value="">Select Doctor</option>
                            <!-- Options will be populated dynamically -->
                        </select>
                    </div>
                </div>
                <div class="mb-4">
                    <label for="consultation_date" class="block text-sm font-medium text-slate-700 mb-1">Consultation Date *</label>
                    <input type="date" id="consultation_date" name="consultation_date" required class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="mb-4">
                    <label for="diagnosis" class="block text-sm font-medium text-slate-700 mb-1">Diagnosis</label>
                    <input type="text" id="diagnosis" name="diagnosis" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="mb-4">
                    <label for="notes" class="block text-sm font-medium text-slate-700 mb-1">Notes</label>
                    <textarea id="notes" name="notes" rows="3" class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"></textarea>
                </div>
                
                <h4 class="text-md font-semibold mb-2">Prescriptions</h4>
                <div id="prescriptions-container">
                    <!-- Prescription fields will be added here -->
                </div>
                <button type="button" id="addPrescriptionBtn" class="mb-4 px-3 py-1 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 text-sm">+ Add Prescription</button>
                
                <div class="flex justify-end space-x-3">
                    <button type="button" id="cancelConsultationModalBtn" class="px-4 py-2 text-slate-700 bg-slate-200 rounded-lg hover:bg-slate-300 transition-colors duration-200">Cancel</button>
                    <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200">Save Consultation</button>
                </div>
            </form>
        </div>
    </div>
    {% endif %}

    <script>
        // --- DOM Elements ---
        const sections = document.querySelectorAll('.content-section');
        const navLinks = document.querySelectorAll('.nav-link:not(#logoutBtn)');
        const logoutBtn = document.getElementById('logoutBtn');
        const loginModal = document.getElementById('loginModal');
        const loginForm = document.getElementById('loginForm');
        const loginError = document.getElementById('loginError');
        
        // Modals
        const patientModal = document.getElementById('patientModal');
        const closeModalBtn = document.getElementById('closeModalBtn');
        const cancelModalBtn = document.getElementById('cancelModalBtn');
        const patientForm = document.getElementById('patientForm');
        
        const consultationModal = document.getElementById('consultationModal');
        const closeConsultationModalBtn = document.getElementById('closeConsultationModalBtn');
        const cancelConsultationModalBtn = document.getElementById('cancelConsultationModalBtn');
        const consultationForm = document.getElementById('consultationForm');
        const addPrescriptionBtn = document.getElementById('addPrescriptionBtn');
        const prescriptionsContainer = document.getElementById('prescriptions-container');
        
        const patientDetailModal = document.getElementById('patientDetailModal');
        const closePatientDetailBtn = document.getElementById('closePatientDetailBtn');
        
        const consultationDetailModal = document.getElementById('consultationDetailModal');
        const closeConsultationDetailBtn = document.getElementById('closeConsultationDetailBtn');

        const newPatientBtn = document.getElementById('newPatientBtn');
        const newConsultationBtn = document.getElementById('newConsultationBtn');

        // --- Utility Functions ---
        function showSection(targetId) {
            sections.forEach(section => section.classList.add('hidden'));
            const targetSection = document.getElementById(targetId);
            if (targetSection) targetSection.classList.remove('hidden');

            navLinks.forEach(link => link.classList.remove('active'));
            const activeLink = document.querySelector(`.nav-link[data-target="${targetId}"]`);
            if (activeLink) activeLink.classList.add('active');

            switch(targetId) {
                case 'dashboard': loadDashboard(); break;
                case 'patients': loadPatients(); break;
                case 'consultations': loadConsultations(); break;
                case 'pharmacy': loadPharmacy(); loadPendingPrescriptions(); break;
                case 'settings': loadUsers(); break;
            }
        }

        function showLoginModal() {
            if (loginModal) loginModal.classList.remove('hidden');
        }
        function hideLoginModal() {
            if (loginModal) loginModal.classList.add('hidden');
        }

        // --- Authentication ---
        loginForm?.addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            const loginData = Object.fromEntries(formData.entries());

            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(loginData)
                });

                const data = await response.json();
                if (response.ok) {
                    hideLoginModal();
                    // Reload page to show main app
                    window.location.reload();
                } else {
                    loginError.textContent = data.message || 'Login failed';
                    loginError.classList.remove('hidden');
                }
            } catch (error) {
                console.error('Login error:', error);
                loginError.textContent = 'Network error during login';
                loginError.classList.remove('hidden');
            }
        });

        logoutBtn?.addEventListener('click', async (e) => {
            e.preventDefault();
            try {
                await fetch('/api/logout', { method: 'POST' });
                window.location.reload(); // Reload to show login modal
            } catch (error) {
                console.error('Logout error:', error);
            }
        });

        // --- Data Loading Functions ---
        const API_BASE = window.location.origin;

        async function loadDashboard() {
            try {
                const response = await fetch(`${API_BASE}/api/dashboard`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const data = await response.json();
                
                document.getElementById('total-patients').textContent = data.total_patients;
                document.getElementById('consultations-week').textContent = data.consultations_this_week;
                document.getElementById('low-stock').textContent = data.low_stock;

                const consultationsContainer = document.getElementById('recent-consultations');
                consultationsContainer.innerHTML = '';
                data.recent_consultations.forEach(c => {
                    const item = document.createElement('div');
                    item.className = 'flex items-center justify-between p-4 border border-slate-200 rounded-lg';
                    item.innerHTML = `
                        <div>
                            <p class="font-medium">${c.patient_name}</p>
                            <p class="text-sm text-slate-500">${c.diagnosis}</p>
                        </div>
                        <div class="text-right">
                            <p class="text-sm font-medium">${c.doctor_name}</p>
                            <p class="text-xs text-slate-500">${c.consultation_date}</p>
                        </div>
                    `;
                    consultationsContainer.appendChild(item);
                });
            } catch (error) {
                console.error('Error loading dashboard:', error);
            }
        }

        async function loadPatients() {
            try {
                const response = await fetch(`${API_BASE}/api/patients`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const patients = await response.json();
                
                const tableBody = document.getElementById('patients-table-body');
                tableBody.innerHTML = '';
                patients.forEach(p => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-800">${p.qid}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${p.name}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${p.age || 'N/A'}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${p.contact_number}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${p.last_visit || 'N/A'}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm">
                            <button onclick="viewPatientDetail(${p.id})" class="text-blue-600 hover:underline mr-2">View</button>
                            <button onclick="editPatient(${p.id})" class="text-green-600 hover:underline">Edit</button>
                        </td>
                    `;
                    tableBody.appendChild(row);
                });
            } catch (error) {
                console.error('Error loading patients:', error);
            }
        }

        async function loadConsultations() {
            try {
                const response = await fetch(`${API_BASE}/api/consultations`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const consultations = await response.json();
                
                const tableBody = document.getElementById('consultations-table-body');
                tableBody.innerHTML = '';
                consultations.forEach(c => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${c.consultation_date}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-800">${c.patient_name}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${c.doctor_name}</td>
                        <td class="px-6 py-4 text-sm text-slate-800">${c.diagnosis}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm">
                            <button onclick="viewConsultationDetail(${c.id})" class="text-blue-600 hover:underline">View</button>
                        </td>
                    `;
                    tableBody.appendChild(row);
                });
            } catch (error) {
                console.error('Error loading consultations:', error);
            }
        }

        async function loadPharmacy() {
            try {
                const response = await fetch(`${API_BASE}/api/pharmacy/inventory`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const inventory = await response.json();
                
                const tableBody = document.getElementById('pharmacy-table-body');
                tableBody.innerHTML = '';
                inventory.forEach(item => {
                    let statusClass = '';
                    if (item.status === 'In Stock') statusClass = 'text-green-800 bg-green-100';
                    else if (item.status === 'Low Stock') statusClass = 'text-amber-800 bg-amber-100';
                    else statusClass = 'text-red-800 bg-red-100';
                    
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-800">${item.name}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${item.stock_level}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${item.location}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${item.expiry_date}</td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${statusClass}">
                                ${item.status}
                            </span>
                        </td>
                    `;
                    tableBody.appendChild(row);
                });
            } catch (error) {
                console.error('Error loading pharmacy inventory:', error);
            }
        }
        
        async function loadPendingPrescriptions() {
             try {
                const response = await fetch(`${API_BASE}/api/pharmacy/prescriptions`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const prescriptions = await response.json();
                
                const tableBody = document.getElementById('prescriptions-table-body');
                tableBody.innerHTML = '';
                prescriptions.forEach(p => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-800">${p.patient_name}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${p.medication}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${p.dosage}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${p.doctor_name}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${p.consultation_date}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm">
                            <button onclick="dispensePrescription(${p.id})" class="text-green-600 hover:underline">Dispense</button>
                        </td>
                    `;
                    tableBody.appendChild(row);
                });
            } catch (error) {
                console.error('Error loading prescriptions:', error);
            }
        }

        async function loadUsers() {
             // Check if user is admin before loading
             // This is a UI check, API also enforces it
             try {
                const response = await fetch(`${API_BASE}/api/users`);
                if (!response.ok) {
                     if(response.status === 403) {
                         alert("Access denied. Admin privileges required.");
                         return;
                     }
                     throw new Error(`HTTP error! status: ${response.status}`);
                }
                const users = await response.json();
                
                const tableBody = document.getElementById('users-table-body');
                tableBody.innerHTML = '';
                users.forEach(u => {
                    let roleClass = '';
                    if (u.role === 'Doctor') roleClass = 'text-blue-800 bg-blue-100';
                    else if (u.role === 'Nurse') roleClass = 'text-indigo-800 bg-indigo-100';
                    else if (u.role === 'Pharmacist') roleClass = 'text-amber-800 bg-amber-100';
                    else roleClass = 'text-purple-800 bg-purple-100';
                    
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-800">${u.name}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${u.email}</td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${roleClass}">
                                ${u.role}
                            </span>
                        </td>
                    `;
                    tableBody.appendChild(row);
                });
            } catch (error) {
                console.error('Error loading users:', error);
            }
        }
        
        async function loadDoctorsForSelect(selectElementId) {
            try {
                const response = await fetch(`${API_BASE}/api/users/doctors`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const doctors = await response.json();
                const selectElement = document.getElementById(selectElementId);
                if (selectElement) {
                    selectElement.innerHTML = '<option value="">Select Doctor</option>';
                    doctors.forEach(d => {
                        const option = document.createElement('option');
                        option.value = d.id;
                        option.textContent = d.name;
                        selectElement.appendChild(option);
                    });
                }
            } catch (error) {
                console.error('Error loading doctors:', error);
            }
        }
        
        async function loadPatientsForSelect(selectElementId) {
            try {
                const response = await fetch(`${API_BASE}/api/patients`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const patients = await response.json();
                const selectElement = document.getElementById(selectElementId);
                if (selectElement) {
                    selectElement.innerHTML = '<option value="">Select Patient</option>';
                    patients.forEach(p => {
                        const option = document.createElement('option');
                        option.value = p.id;
                        option.textContent = `${p.name} (${p.qid})`;
                        selectElement.appendChild(option);
                    });
                }
            } catch (error) {
                console.error('Error loading patients for select:', error);
            }
        }

        // --- Patient Management ---
        newPatientBtn?.addEventListener('click', () => {
            // Reset form
            patientForm.reset();
            document.getElementById('patientId').value = '';
            patientModal?.classList.remove('hidden');
        });

        closeModalBtn?.addEventListener('click', () => patientModal?.classList.add('hidden'));
        cancelModalBtn?.addEventListener('click', () => patientModal?.classList.add('hidden'));

        patientForm?.addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            const patientData = Object.fromEntries(formData.entries());
            const patientId = patientData.id;
            delete patientData.id; // Remove ID from data payload

            try {
                let url = `${API_BASE}/api/patients`;
                let method = 'POST';
                if (patientId) {
                    url = `${API_BASE}/api/patients/${patientId}`;
                    method = 'PUT';
                }
                
                const response = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(patientData)
                });

                if (response.ok) {
                    patientModal?.classList.add('hidden');
                    loadPatients();
                    if (!document.getElementById('dashboard')?.classList.contains('hidden')) {
                         loadDashboard();
                    }
                } else {
                    const errorData = await response.json();
                    alert(`Failed to save patient: ${errorData.message || 'Unknown error'}`);
                }
            } catch (error) {
                console.error('Error saving patient:', error);
                alert('Failed to save patient due to a network error.');
            }
        });

        function editPatient(patientId) {
            fetch(`${API_BASE}/api/patients/${patientId}`)
                .then(response => response.json())
                .then(patient => {
                    document.getElementById('patientId').value = patient.id;
                    document.getElementById('qid').value = patient.qid;
                    document.getElementById('name').value = patient.name;
                    document.getElementById('contact_number').value = patient.contact_number || '';
                    document.getElementById('date_of_birth').value = patient.date_of_birth || '';
                    document.getElementById('address').value = patient.address || '';
                    document.getElementById('last_visit').value = patient.last_visit || '';
                    patientModal?.classList.remove('hidden');
                })
                .catch(error => console.error('Error fetching patient:', error));
        }
        
        async function viewPatientDetail(patientId) {
            try {
                const response = await fetch(`${API_BASE}/api/patients/${patientId}`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const patient = await response.json();
                
                const detailContent = document.getElementById('patient-detail-content');
                if (detailContent) {
                    detailContent.innerHTML = `
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                            <div><strong>QID:</strong> ${patient.qid}</div>
                            <div><strong>Name:</strong> ${patient.name}</div>
                            <div><strong>Contact:</strong> ${patient.contact_number || 'N/A'}</div>
                            <div><strong>Age:</strong> ${patient.age || 'N/A'}</div>
                            <div><strong>Date of Birth:</strong> ${patient.date_of_birth || 'N/A'}</div>
                            <div><strong>Last Visit:</strong> ${patient.last_visit || 'N/A'}</div>
                            <div class="md:col-span-2"><strong>Address:</strong> ${patient.address || 'N/A'}</div>
                        </div>
                        <h4 class="text-md font-semibold mb-2">Consultation History</h4>
                        <div id="patient-consultations-history">Loading...</div>
                    `;
                    patientDetailModal?.classList.remove('hidden');
                    loadPatientConsultations(patientId);
                }
            } catch (error) {
                console.error('Error loading patient detail:', error);
            }
        }
        
        async function loadPatientConsultations(patientId) {
            try {
                const response = await fetch(`${API_BASE}/api/patients/${patientId}/consultations`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const consultations = await response.json();
                
                const historyContainer = document.getElementById('patient-consultations-history');
                if (historyContainer) {
                    if (consultations.length === 0) {
                        historyContainer.innerHTML = '<p>No consultations found for this patient.</p>';
                        return;
                    }
                    let html = '<ul class="list-disc pl-5 space-y-2">';
                    consultations.forEach(c => {
                        html += `<li><strong>${c.consultation_date}</strong> - ${c.diagnosis} (Dr. ${c.doctor_name})<br><span class="text-sm">${c.notes || ''}</span></li>`;
                    });
                    html += '</ul>';
                    historyContainer.innerHTML = html;
                }
            } catch (error) {
                console.error('Error loading patient consultations:', error);
                const historyContainer = document.getElementById('patient-consultations-history');
                if (historyContainer) historyContainer.innerHTML = '<p>Error loading consultation history.</p>';
            }
        }
        
        closePatientDetailBtn?.addEventListener('click', () => patientDetailModal?.classList.add('hidden'));

        // --- Consultation Management ---
        newConsultationBtn?.addEventListener('click', async () => {
            // Reset form
            consultationForm.reset();
            document.getElementById('consultationId').value = '';
            prescriptionsContainer.innerHTML = '';
            // Set default date to today
            document.getElementById('consultation_date').valueAsDate = new Date();
            
            // Populate dropdowns
            await Promise.all([
                loadPatientsForSelect('consultation_patient_id'),
                loadDoctorsForSelect('consultation_doctor_id')
            ]);
            
            consultationModal?.classList.remove('hidden');
        });

        closeConsultationModalBtn?.addEventListener('click', () => consultationModal?.classList.add('hidden'));
        cancelConsultationModalBtn?.addEventListener('click', () => consultationModal?.classList.add('hidden'));
        
        addPrescriptionBtn?.addEventListener('click', () => {
            const prescriptionDiv = document.createElement('div');
            prescriptionDiv.className = 'border border-slate-300 rounded-lg p-3 mb-3 prescription-item';
            prescriptionDiv.innerHTML = `
                <div class="grid grid-cols-1 md:grid-cols-2 gap-2 mb-2">
                    <input type="text" name="prescription_medication[]" placeholder="Medication" class="px-2 py-1 border border-slate-300 rounded text-sm" required>
                    <input type="text" name="prescription_dosage[]" placeholder="Dosage (e.g., 1 tablet twice daily)" class="px-2 py-1 border border-slate-300 rounded text-sm" required>
                </div>
                <div class="mb-2">
                    <input type="text" name="prescription_instructions[]" placeholder="Instructions (e.g., Take with food)" class="w-full px-2 py-1 border border-slate-300 rounded text-sm">
                </div>
                <button type="button" onclick="this.parentElement.remove()" class="px-2 py-1 bg-red-100 text-red-700 rounded text-xs hover:bg-red-200">Remove</button>
            `;
            prescriptionsContainer.appendChild(prescriptionDiv);
        });

        consultationForm?.addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            const consultationData = {};
            
            // Collect main consultation data
            for (let [key, value] of formData.entries()) {
                if (!key.startsWith('prescription_')) {
                    consultationData[key] = value;
                }
            }
            
            // Collect prescriptions
            consultationData.prescriptions = [];
            const prescriptionDivs = document.querySelectorAll('.prescription-item');
            prescriptionDivs.forEach(div => {
                const inputs = div.querySelectorAll('input');
                const medInput = inputs[0];
                const doseInput = inputs[1];
                const instInput = inputs[2];
                if (medInput.value && doseInput.value) {
                    consultationData.prescriptions.push({
                        medication: medInput.value,
                        dosage: doseInput.value,
                        instructions: instInput.value || ''
                    });
                }
            });

            const consultationId = consultationData.id;
            delete consultationData.id;

            try {
                let url = `${API_BASE}/api/consultations`;
                let method = 'POST';
                if (consultationId) {
                    url = `${API_BASE}/api/consultations/${consultationId}`;
                    method = 'PUT';
                }
                
                const response = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(consultationData)
                });

                if (response.ok) {
                    consultationModal?.classList.add('hidden');
                    loadConsultations();
                    if (!document.getElementById('dashboard')?.classList.contains('hidden')) {
                         loadDashboard();
                    }
                    if (!document.getElementById('pharmacy')?.classList.contains('hidden')) {
                         loadPendingPrescriptions();
                    }
                } else {
                    const errorData = await response.json();
                    alert(`Failed to save consultation: ${errorData.message || 'Unknown error'}`);
                }
            } catch (error) {
                console.error('Error saving consultation:', error);
                alert('Failed to save consultation due to a network error.');
            }
        });
        
        async function viewConsultationDetail(consultationId) {
            try {
                const response = await fetch(`${API_BASE}/api/consultations/${consultationId}`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const consultation = await response.json();
                
                const detailContent = document.getElementById('consultation-detail-content');
                if (detailContent) {
                    let prescriptionsHtml = '<p class="text-sm text-slate-500">No prescriptions.</p>';
                    if (consultation.prescriptions && consultation.prescriptions.length > 0) {
                        prescriptionsHtml = '<ul class="list-disc pl-5 space-y-1">';
                        consultation.prescriptions.forEach(p => {
                            const statusText = p.dispensed ? '(Dispensed)' : '(Pending)';
                            prescriptionsHtml += `<li><strong>${p.medication}</strong> - ${p.dosage} ${statusText}<br><span class="text-xs">${p.instructions || ''}</span></li>`;
                        });
                        prescriptionsHtml += '</ul>';
                    }
                    
                    detailContent.innerHTML = `
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                            <div><strong>Date:</strong> ${consultation.consultation_date}</div>
                            <div><strong>Patient:</strong> ${consultation.patient_name}</div>
                            <div><strong>Doctor:</strong> ${consultation.doctor_name}</div>
                            <div><strong>Diagnosis:</strong> ${consultation.diagnosis || 'N/A'}</div>
                            <div class="md:col-span-2"><strong>Notes:</strong> ${consultation.notes || 'N/A'}</div>
                        </div>
                        <h4 class="text-md font-semibold mb-2">Prescriptions</h4>
                        <div>${prescriptionsHtml}</div>
                    `;
                    consultationDetailModal?.classList.remove('hidden');
                }
            } catch (error) {
                console.error('Error loading consultation detail:', error);
            }
        }
        
        closeConsultationDetailBtn?.addEventListener('click', () => consultationDetailModal?.classList.add('hidden'));

        // --- Pharmacy Actions ---
        async function dispensePrescription(prescriptionId) {
            if (!confirm("Mark this prescription as dispensed?")) return;
            
            try {
                const response = await fetch(`${API_BASE}/api/pharmacy/prescriptions/${prescriptionId}/dispense`, {
                    method: 'POST'
                });
                if (response.ok) {
                    alert('Prescription marked as dispensed.');
                    if (!document.getElementById('pharmacy')?.classList.contains('hidden')) {
                         loadPendingPrescriptions();
                    }
                    // Optionally, refresh inventory if stock levels changed
                } else {
                    const errorData = await response.json();
                    alert(`Failed to dispense: ${errorData.message || 'Unknown error'}`);
                }
            } catch (error) {
                console.error('Error dispensing prescription:', error);
                alert('Failed to dispense prescription due to a network error.');
            }
        }

        // --- Initial Load ---
        document.addEventListener('DOMContentLoaded', () => {
            // Check if user is logged in (based on session existence in template)
            {% if 'user_id' not in session %}
                showLoginModal();
            {% else %}
                showSection('dashboard');
            {% endif %}
        });
        
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                showSection(link.dataset.target);
            });
        });
    </script>
</body>
</html>
"""

# --- API Routes ---

# --- Authentication Routes ---
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['user_role'] = user.role
        return jsonify({'message': 'Login successful'}), 200
    else:
        return jsonify({'message': 'Invalid email or password'}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_role', None)
    return jsonify({'message': 'Logged out'}), 200

# --- Main Routes ---
@app.route('/')
def index():
    # Pass session data to template for conditional rendering
    return render_template_string(HTML_TEMPLATE, session=session)

# --- Dashboard API ---
@app.route('/api/dashboard')
@login_required
def dashboard_data():
    # Calculate consultations in the last 7 days
    one_week_ago = date.today() - timedelta(days=7)
    consultations_this_week = Consultation.query.filter(Consultation.consultation_date >= one_week_ago).count()
    
    return jsonify({
        'total_patients': Patient.query.count(),
        'consultations_this_week': consultations_this_week,
        'low_stock': Medicine.query.filter(Medicine.status != 'In Stock').count(),
        'recent_consultations': [{
            'consultation_date': c.consultation_date.strftime('%Y-%m-%d'),
            'patient_name': c.patient.name,
            'doctor_name': c.doctor.name,
            'diagnosis': c.diagnosis
        } for c in Consultation.query.order_by(Consultation.consultation_date.desc()).limit(5).all()]
    })

# --- User API ---
@app.route('/api/users')
@login_required
def get_users():
    # Simple role check for demo
    if session.get('user_role') != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    users = User.query.all()
    return jsonify([{'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role} for u in users])

@app.route('/api/users/doctors') # Public endpoint for dropdown
def get_doctors():
    doctors = User.query.filter_by(role='Doctor').all()
    return jsonify([{'id': d.id, 'name': d.name} for d in doctors])

# --- Patient API ---
@app.route('/api/patients')
@login_required
def get_patients():
    patients = Patient.query.order_by(Patient.id.desc()).all()
    return jsonify([{
        'id': p.id,
        'qid': p.qid,
        'name': p.name,
        'contact_number': p.contact_number,
        'last_visit': p.last_visit.strftime('%Y-%m-%d') if p.last_visit else None,
        'date_of_birth': p.date_of_birth.strftime('%Y-%m-%d') if p.date_of_birth else None,
        'address': p.address,
        'age': p.age()
    } for p in patients])

@app.route('/api/patients/<int:patient_id>')
@login_required
def get_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    return jsonify({
        'id': patient.id,
        'qid': patient.qid,
        'name': patient.name,
        'contact_number': patient.contact_number,
        'last_visit': patient.last_visit.strftime('%Y-%m-%d') if patient.last_visit else None,
        'date_of_birth': patient.date_of_birth.strftime('%Y-%m-%d') if patient.date_of_birth else None,
        'address': patient.address,
        'age': patient.age()
    })

@app.route('/api/patients/<int:patient_id>/consultations')
@login_required
def get_patient_consultations(patient_id):
    consultations = Consultation.query.filter_by(patient_id=patient_id).order_by(Consultation.consultation_date.desc()).all()
    return jsonify([{
        'id': c.id,
        'consultation_date': c.consultation_date.strftime('%Y-%m-%d'),
        'diagnosis': c.diagnosis,
        'notes': c.notes,
        'doctor_name': c.doctor.name
    } for c in consultations])

@app.route('/api/patients', methods=['POST'])
@login_required
def add_patient():
    data = request.get_json()
    new_patient = Patient(
        qid=data['qid'],
        name=data['name'],
        contact_number=data.get('contact_number'),
        last_visit=date.fromisoformat(data['last_visit']) if data.get('last_visit') else None,
        date_of_birth=date.fromisoformat(data['date_of_birth']) if data.get('date_of_birth') else None,
        address=data.get('address')
    )
    db.session.add(new_patient)
    db.session.commit()
    return jsonify({'message': 'Patient added successfully'}), 201

@app.route('/api/patients/<int:patient_id>', methods=['PUT'])
@login_required
def update_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    data = request.get_json()
    
    patient.qid = data.get('qid', patient.qid)
    patient.name = data.get('name', patient.name)
    patient.contact_number = data.get('contact_number', patient.contact_number)
    patient.last_visit = date.fromisoformat(data['last_visit']) if data.get('last_visit') else patient.last_visit
    patient.date_of_birth = date.fromisoformat(data['date_of_birth']) if data.get('date_of_birth') else patient.date_of_birth
    patient.address = data.get('address', patient.address)
    
    db.session.commit()
    return jsonify({'message': 'Patient updated successfully'})

# --- Consultation API ---
@app.route('/api/consultations')
@login_required
def get_consultations():
    consultations = Consultation.query.order_by(Consultation.consultation_date.desc()).all()
    return jsonify([{
        'id': c.id,
        'consultation_date': c.consultation_date.strftime('%Y-%m-%d'),
        'patient_name': c.patient.name,
        'doctor_name': c.doctor.name,
        'diagnosis': c.diagnosis
    } for c in consultations])

@app.route('/api/consultations/<int:consultation_id>')
@login_required
def get_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    return jsonify({
        'id': consultation.id,
        'consultation_date': consultation.consultation_date.strftime('%Y-%m-%d'),
        'patient_name': consultation.patient.name,
        'doctor_name': consultation.doctor.name,
        'diagnosis': consultation.diagnosis,
        'notes': consultation.notes,
        'prescriptions': [{
            'id': p.id,
            'medication': p.medication,
            'dosage': p.dosage,
            'instructions': p.instructions,
            'dispensed': p.dispensed
        } for p in consultation.prescriptions]
    })

@app.route('/api/consultations', methods=['POST'])
@login_required
def add_consultation():
    data = request.get_json()
    new_consultation = Consultation(
        patient_id=int(data['patient_id']),
        doctor_id=int(data['doctor_id']),
        consultation_date=date.fromisoformat(data['consultation_date']),
        diagnosis=data.get('diagnosis'),
        notes=data.get('notes')
    )
    db.session.add(new_consultation)
    db.session.flush() # Get the ID before committing

    # Add prescriptions
    prescriptions_data = data.get('prescriptions', [])
    for p_data in prescriptions_data:
        new_prescription = Prescription(
            consultation_id=new_consultation.id,
            medication=p_data['medication'],
            dosage=p_data['dosage'],
            instructions=p_data.get('instructions', '')
            # medicine_id could be linked if medicine name matches inventory
        )
        db.session.add(new_prescription)

    db.session.commit()
    return jsonify({'message': 'Consultation added successfully'}), 201

@app.route('/api/consultations/<int:consultation_id>', methods=['PUT'])
@login_required
def update_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    data = request.get_json()
    
    consultation.patient_id = int(data.get('patient_id', consultation.patient_id))
    consultation.doctor_id = int(data.get('doctor_id', consultation.doctor_id))
    consultation.consultation_date = date.fromisoformat(data.get('consultation_date', consultation.consultation_date.isoformat()))
    consultation.diagnosis = data.get('diagnosis', consultation.diagnosis)
    consultation.notes = data.get('notes', consultation.notes)
    
    # For simplicity, this example doesn't handle updating prescriptions via PUT
    # A full implementation would need to manage adding/editing/removing prescriptions
    
    db.session.commit()
    return jsonify({'message': 'Consultation updated successfully'})

# --- Pharmacy API ---
@app.route('/api/pharmacy/inventory')
@login_required
def get_inventory():
    inventory = Medicine.query.all()
    return jsonify([{
        'id': item.id,
        'name': item.name,
        'stock_level': item.stock_level,
        'location': item.location,
        'expiry_date': item.expiry_date.strftime('%Y-%m-%d') if item.expiry_date else None,
        'status': item.status
    } for item in inventory])

@app.route('/api/pharmacy/prescriptions')
@login_required
def get_pending_prescriptions():
    # Get prescriptions not yet dispensed
    pending_prescriptions = Prescription.query.filter_by(dispensed=False).join(Consultation).order_by(Consultation.consultation_date.desc()).all()
    return jsonify([{
        'id': p.id,
        'patient_name': p.consultation.patient.name,
        'medication': p.medication,
        'dosage': p.dosage,
        'doctor_name': p.consultation.doctor.name,
        'consultation_date': p.consultation.consultation_date.strftime('%Y-%m-%d'),
        'consultation_id': p.consultation_id
    } for p in pending_prescriptions])

@app.route('/api/pharmacy/prescriptions/<int:prescription_id>/dispense', methods=['POST'])
@login_required
def dispense_prescription(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    if prescription.dispensed:
        return jsonify({'message': 'Prescription already dispensed'}), 400
        
    prescription.dispensed = True
    # Here you could also decrement stock level in Medicine table if linked
    # if prescription.medicine_id:
    #     medicine = Medicine.query.get(prescription.medicine_id)
    #     if medicine and medicine.stock_level > 0:
    #         medicine.stock_level -= 1
    #         # Update status if needed based on new stock_level
    
    db.session.commit()
    return jsonify({'message': 'Prescription dispensed successfully'})

# --- Run the Application ---
if __name__ == '__main__':
    initialize_database() # Ensure DB is ready when running locally
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask application on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True) 
