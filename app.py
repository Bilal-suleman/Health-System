# app.py
import os
from flask import Flask, jsonify, request, render_template_string
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta
import random
import threading

# --- App & Database Configuration ---
app = Flask(__name__)

# Use a file-based SQLite database for persistence
# This is crucial for deployment and local stability
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'healthsys.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
# For production (e.g., Render, Railway) with PostgreSQL, you'd use:
# app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f'sqlite:///{db_path}')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Database Models ---
class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    qid = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    contact_number = db.Column(db.String(20))
    last_visit = db.Column(db.Date)
    consultations = db.relationship('Consultation', backref='patient', lazy=True)

    def __repr__(self):
        return f'<Patient {self.name}>'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False) # 'Doctor', 'Nurse', 'Admin'
    consultations = db.relationship('Consultation', backref='doctor', lazy=True)

    def __repr__(self):
        return f'<User {self.name}>'

class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    stock_level = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100))
    expiry_date = db.Column(db.Date)
    status = db.Column(db.String(50))

    def __repr__(self):
        return f'<Medicine {self.name}>'

class Consultation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    consultation_date = db.Column(db.Date, nullable=False)
    diagnosis = db.Column(db.String(200))
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Consultation {self.id}>'

# --- Ensure tables are created only once ---
# Use a threading lock to ensure thread safety during initialization
_init_lock = threading.Lock()
_is_initialized = False

def initialize_database():
    """Initialize the database: create tables and seed data if needed."""
    global _is_initialized
    # Acquire the lock to ensure only one thread initializes
    with _init_lock:
        # Double-check the flag inside the lock
        if not _is_initialized:
            print("Initializing database...")
            db.create_all()
            seed_initial_data()
            _is_initialized = True
            print("Database initialization complete.")

# --- Seed Initial Data ---
def seed_initial_data():
    """Populate the database with initial data if it's empty."""
    # Check if data already exists to avoid re-seeding
    if Patient.query.first() is None:
        print("Seeding database with initial data...")
        try:
            # Seed Users
            u1 = User(name='Dr. Aisha Al-Emadi', email='a.emadi@healthsys.demo', role='Doctor')
            u2 = User(name='Nadia Hassan', email='n.hassan@healthsys.demo', role='Nurse')
            u3 = User(name='Dr. Omar Khalid', email='o.khalid@healthsys.demo', role='Doctor')
            u4 = User(name='Layla Mahmoud', email='l.mahmoud@healthsys.demo', role='Pharmacist')
            db.session.add_all([u1, u2, u3, u4])
            db.session.commit()

            # Seed Patients
            p1 = Patient(qid='29850615001', name='Fatima Nasser', contact_number='55123456', last_visit=date(2025, 7, 20))
            p2 = Patient(qid='29901103002', name='Mohammed Saleh', contact_number='55234567', last_visit=date(2025, 7, 18))
            p3 = Patient(qid='29780228003', name='Yousef Ali', contact_number='55345678', last_visit=date(2025, 7, 10))
            p4 = Patient(qid='30010812004', name='Sana Kamal', contact_number='55456789', last_visit=date(2025, 7, 5))
            db.session.add_all([p1, p2, p3, p4])
            db.session.commit()

            # Seed Pharmacy
            m1 = Medicine(name='Metformin 500mg', stock_level=150, location='Doha Main Clinic', expiry_date=date(2026, 12, 31), status='In Stock')
            m2 = Medicine(name='Amoxicillin 250mg', stock_level=45, location='Doha Main Clinic', expiry_date=date(2026, 8, 31), status='Low Stock')
            m3 = Medicine(name='Panadol 500mg', stock_level=250, location='Doha Main Clinic', expiry_date=date(2027, 1, 31), status='In Stock')
            m4 = Medicine(name='Aspirin 75mg', stock_level=15, location='Doha Main Clinic', expiry_date=date(2026, 2, 28), status='Reorder')
            db.session.add_all([m1, m2, m3, m4])
            db.session.commit()

            # Seed Consultations (ensure user/patient IDs are committed first)
            c1 = Consultation(patient_id=p1.id, doctor_id=u1.id, consultation_date=date.today() - timedelta(days=1), diagnosis="Hypertension")
            c2 = Consultation(patient_id=p2.id, doctor_id=u1.id, consultation_date=date.today() - timedelta(days=3), diagnosis="Type 2 Diabetes")
            c3 = Consultation(patient_id=p3.id, doctor_id=u3.id, consultation_date=date.today() - timedelta(days=10), diagnosis="Migraine")
            db.session.add_all([c1, c2, c3])
            db.session.commit()
            
            print("Database seeded successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"Error seeding database: {e}")
            # Optionally, log this error properly in production
    else:
        print("Database already contains data, skipping seeding.")

# --- Ensure tables are created before handling any request ---
@app.before_request
def ensure_initialized():
    # This will run before every request, but initialize_database() handles
    # ensuring it only does the work once.
    initialize_database()


# --- HTML Template ---
# We embed the HTML directly into the Python file for a single-file prototype.
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HealthSys Pro - Functional Demo (Qatar)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .nav-link.active {
            background-color: #1e293b; /* slate-800 */
            color: white;
        }
    </style>
</head>
<body class="bg-slate-100 text-slate-800">
    <div class="flex h-screen">
        <!-- Sidebar -->
        <aside class="w-64 bg-slate-900 text-white flex flex-col">
            <div class="p-6 border-b border-slate-800">
                <h1 class="text-xl font-bold">HealthSys Pro</h1>
                <p class="text-sm text-slate-400">Demo Version</p>
            </div>
            <nav class="flex-1 p-4">
                <ul class="space-y-1">
                    <li><a href="#" data-target="dashboard" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700 active"><svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>Dashboard</a></li>
                    <li><a href="#" data-target="patients" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700"><svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>Patients</a></li>
                    <li><a href="#" data-target="consultations" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700"><svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>Consultations</a></li>
                    <li><a href="#" data-target="pharmacy" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700"><svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21a9 9 0 0 0 9-9a9 9 0 0 0-9-9a9 9 0 0 0-9 9a9 9 0 0 0 9 9Z"/><path d="m10 13 2 2 2-2"/><path d="M10 9h4"/></svg>Pharmacy</a></li>
                    <li><a href="#" data-target="settings" class="nav-link flex items-center px-4 py-2.5 rounded-lg transition-colors duration-200 hover:bg-slate-700"><svg class="w-5 h-5 mr-3" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>Users</a></li>
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
                                <p class="text-sm text-slate-500">Appointments</p>
                                <p id="appointments" class="text-2xl font-bold">0</p>
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
                <div class="bg-white rounded-xl shadow-sm overflow-hidden">
                    <table class="min-w-full divide-y divide-slate-200">
                        <thead class="bg-slate-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">QID</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Name</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Contact</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Last Visit</th>
                            </tr>
                        </thead>
                        <tbody id="patients-table-body" class="divide-y divide-slate-200">
                            <!-- Patient rows will be loaded here -->
                        </tbody>
                    </table>
                </div>
            </section>

            <!-- Consultations Section -->
            <section id="consultations" class="content-section hidden">
                <h2 class="text-2xl font-bold mb-6">Recent Consultations</h2>
                <div class="bg-white rounded-xl shadow-sm overflow-hidden">
                    <table class="min-w-full divide-y divide-slate-200">
                        <thead class="bg-slate-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Date</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Patient</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Doctor</th>
                                <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Diagnosis</th>
                            </tr>
                        </thead>
                        <tbody id="consultations-table-body" class="divide-y divide-slate-200">
                            <!-- Consultation rows will be loaded here -->
                        </tbody>
                    </table>
                </div>
            </section>

            <!-- Pharmacy Section -->
            <section id="pharmacy" class="content-section hidden">
                <h2 class="text-2xl font-bold mb-6">Pharmacy Inventory</h2>
                <div class="bg-white rounded-xl shadow-sm overflow-hidden">
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
            </section>

            <!-- Users Section -->
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
                <div class="mb-4">
                    <label for="qid" class="block text-sm font-medium text-slate-700 mb-1">QID</label>
                    <input type="text" id="qid" name="qid" required class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="mb-4">
                    <label for="name" class="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
                    <input type="text" id="name" name="name" required class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="mb-4">
                    <label for="contact_number" class="block text-sm font-medium text-slate-700 mb-1">Contact Number</label>
                    <input type="text" id="contact_number" name="contact_number" required class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="mb-4">
                    <label for="last_visit" class="block text-sm font-medium text-slate-700 mb-1">Last Visit Date</label>
                    <input type="date" id="last_visit" name="last_visit" required class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                </div>
                <div class="flex justify-end space-x-3">
                    <button type="button" id="cancelModalBtn" class="px-4 py-2 text-slate-700 bg-slate-200 rounded-lg hover:bg-slate-300 transition-colors duration-200">Cancel</button>
                    <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200">Register</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        // --- DOM Elements ---
        const sections = document.querySelectorAll('.content-section');
        const navLinks = document.querySelectorAll('.nav-link');
        const modal = document.getElementById('patientModal');
        const newPatientBtn = document.getElementById('newPatientBtn');
        const closeModalBtn = document.getElementById('closeModalBtn');
        const cancelModalBtn = document.getElementById('cancelModalBtn');
        const patientForm = document.getElementById('patientForm');

        // --- Utility Functions ---
        function showSection(targetId) {
            sections.forEach(section => {
                section.classList.add('hidden');
            });
            document.getElementById(targetId).classList.remove('hidden');

            navLinks.forEach(link => {
                link.classList.remove('active');
            });
            // Find the link that corresponds to the target and activate it
            const activeLink = document.querySelector(`.nav-link[data-target="${targetId}"]`);
            if (activeLink) {
                activeLink.classList.add('active');
            }

            // Load data based on the selected section
            switch(targetId) {
                case 'dashboard': loadDashboard(); break;
                case 'patients': loadPatients(); break;
                case 'consultations': loadConsultations(); break;
                case 'pharmacy': loadPharmacy(); break;
                case 'settings': loadUsers(); break;
            }
        }

        // --- Data Loading Functions ---
        const API_BASE = window.location.origin;

        async function loadDashboard() {
            try {
                const response = await fetch(`${API_BASE}/api/dashboard`);
                if (!response.ok) { throw new Error(`HTTP error! status: ${response.status}`); }
                const data = await response.json();
                
                document.getElementById('total-patients').textContent = data.total_patients;
                document.getElementById('appointments').textContent = data.appointments;
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
                // Optionally, display an error message in the UI
            }
        }

        async function loadPatients() {
            try {
                const response = await fetch(`${API_BASE}/api/patients`);
                if (!response.ok) { throw new Error(`HTTP error! status: ${response.status}`); }
                const patients = await response.json();
                
                const tableBody = document.getElementById('patients-table-body');
                tableBody.innerHTML = '';
                patients.forEach(p => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-800">${p.qid}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${p.name}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${p.contact_number}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-800">${p.last_visit}</td>
                    `;
                    tableBody.appendChild(row);
                });
            } catch (error) {
                console.error('Error loading patients:', error);
                 // Optionally, display an error message in the UI
            }
        }

        async function loadConsultations() {
            try {
                const response = await fetch(`${API_BASE}/api/consultations`);
                if (!response.ok) { throw new Error(`HTTP error! status: ${response.status}`); }
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
                    `;
                    tableBody.appendChild(row);
                });
            } catch (error) {
                console.error('Error loading consultations:', error);
                 // Optionally, display an error message in the UI
            }
        }

        async function loadPharmacy() {
            try {
                const response = await fetch(`${API_BASE}/api/pharmacy/inventory`);
                if (!response.ok) { throw new Error(`HTTP error! status: ${response.status}`); }
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
                 // Optionally, display an error message in the UI
            }
        }

        async function loadUsers() {
            try {
                const response = await fetch(`${API_BASE}/api/users`);
                if (!response.ok) { throw new Error(`HTTP error! status: ${response.status}`); }
                const users = await response.json();
                
                const tableBody = document.getElementById('users-table-body');
                tableBody.innerHTML = '';
                users.forEach(u => {
                    let roleClass = '';
                    if (u.role === 'Doctor') roleClass = 'text-blue-800 bg-blue-100';
                    else if (u.role === 'Nurse') roleClass = 'text-indigo-800 bg-indigo-100';
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
                 // Optionally, display an error message in the UI
            }
        }

        // --- Event Listeners ---
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                showSection(link.dataset.target);
            });
        });

        // --- New Patient Modal Logic ---
        newPatientBtn.addEventListener('click', () => {
            modal.classList.remove('hidden');
        });

        closeModalBtn.addEventListener('click', () => {
            modal.classList.add('hidden');
        });

        cancelModalBtn.addEventListener('click', () => {
            modal.classList.add('hidden');
        });

        patientForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            const patientData = Object.fromEntries(formData.entries());

            try {
                const response = await fetch(`${API_BASE}/api/patients`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(patientData)
                });

                if (response.ok) {
                    modal.classList.add('hidden');
                    this.reset();
                    loadPatients(); // Refresh the patient list
                    // Also update dashboard stats if on dashboard
                    if (!document.getElementById('dashboard').classList.contains('hidden')) {
                         loadDashboard();
                    }
                } else {
                    const errorData = await response.json();
                    alert(`Failed to register patient: ${errorData.message || 'Unknown error'}`);
                }
            } catch (error) {
                console.error('Error submitting patient form:', error);
                alert('Failed to register patient due to a network error.');
            }
        });

        // --- Initial Load ---
        // The dashboard is shown by default due to active class on its nav link
        // loadDashboard(); // Not needed as it's triggered by showSection('dashboard') below
        showSection('dashboard');
    </script>
</body>
</html>
"""

# --- API Routes ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/dashboard')
def dashboard_data():
    # Ensure tables exist before querying (handled by ensure_initialized)
    # db.create_all() # Not needed here as ensure_initialized handles it
    
    return jsonify({
        'total_patients': Patient.query.count(),
        'appointments': Patient.query.count() * 2, # Dummy data
        'low_stock': Medicine.query.filter(Medicine.status != 'In Stock').count(),
        'recent_consultations': [{
            'consultation_date': c.consultation_date.strftime('%Y-%m-%d'),
            'patient_name': c.patient.name,
            'doctor_name': c.doctor.name,
            'diagnosis': c.diagnosis
        } for c in Consultation.query.order_by(Consultation.consultation_date.desc()).limit(5).all()]
    })

@app.route('/api/users')
def get_users():
    # Ensure tables exist before querying (handled by ensure_initialized)
    # db.create_all() # Not needed here
    
    users = User.query.all()
    return jsonify([{'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role} for u in users])

@app.route('/api/patients')
def get_patients():
    # Ensure tables exist before querying (handled by ensure_initialized)
    # db.create_all() # Not needed here
    
    patients = Patient.query.order_by(Patient.id.desc()).all()
    return jsonify([{
        'id': p.id,
        'qid': p.qid,
        'name': p.name,
        'contact_number': p.contact_number,
        'last_visit': p.last_visit.strftime('%Y-%m-%d') if p.last_visit else None
    } for p in patients])

@app.route('/api/patients', methods=['POST'])
def add_patient():
    # Ensure tables exist before adding (handled by ensure_initialized)
    # db.create_all() # Not needed here
    
    data = request.get_json()
    new_patient = Patient(
        qid=data['qid'],
        name=data['name'],
        contact_number=data['contact_number'],
        last_visit=date.fromisoformat(data['last_visit'])
    )
    db.session.add(new_patient)
    db.session.commit()
    return jsonify({'message': 'Patient added successfully'}), 201

@app.route('/api/consultations')
def get_consultations():
    # Ensure tables exist before querying (handled by ensure_initialized)
    # db.create_all() # Not needed here
    
    consultations = Consultation.query.order_by(Consultation.consultation_date.desc()).limit(5).all()
    return jsonify([{
        'consultation_date': c.consultation_date.strftime('%Y-%m-%d'),
        'patient_name': c.patient.name,
        'doctor_name': c.doctor.name,
        'diagnosis': c.diagnosis
    } for c in consultations])

@app.route('/api/pharmacy/inventory')
def get_inventory():
    # Ensure tables exist before querying (handled by ensure_initialized)
    # db.create_all() # Not needed here
    
    inventory = Medicine.query.all()
    return jsonify([{
        'name': item.name,
        'stock_level': item.stock_level,
        'location': item.location,
        'expiry_date': item.expiry_date.strftime('%Y-%m-%d') if item.expiry_date else None,
        'status': item.status
    } for item in inventory])

# --- Run the Application (for local development) ---
# This block is typically not reached when using Gunicorn, but useful for local `python app.py`
if __name__ == '__main__':
    # Initialize the database when running locally with `python app.py`
    # This ensures tables are created even if no request comes in immediately.
    initialize_database()
    
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask application on port {port}...")
    # Using debug=False can sometimes help with DB stability in simple setups
    app.run(host='0.0.0.0', port=port, debug=True) 
