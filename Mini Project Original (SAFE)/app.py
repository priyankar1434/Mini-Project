# app.py
import os
import sqlite3
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps

# Initialize the Flask application
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB limit
app.config['SECRET_KEY'] = 'college_vehicle_auth_2024_secure_key'

# --- Database Setup ---
def init_db():
    if not os.path.exists('vehicles.db'):
        conn = sqlite3.connect('vehicles.db')
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                upload_time TEXT NOT NULL,
                plate TEXT,
                is_authorized INTEGER
            )
        ''')
        conn.commit()
        conn.close()

def init_auth_db():
    if not os.path.exists('auth.db'):
        conn = sqlite3.connect('auth.db')
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'student',
                created_at TEXT NOT NULL
            )
        ''')
        # Add default admin user
        c.execute('''
            INSERT OR IGNORE INTO users (username, password, full_name, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', ('admin', 'admin123', 'Administrator', 'admin', datetime.now().isoformat()))
        # Add sample student users
        sample_users = [
            ('student1', 'pass123', 'Rahul Sharma', 'student'),
            ('student2', 'pass123', 'Priya Patel', 'student'),
            ('faculty1', 'pass123', 'Dr. Amit Kumar', 'faculty'),
        ]
        c.executemany('''
            INSERT OR IGNORE INTO users (username, password, full_name, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', [(u[0], u[1], u[2], u[3], datetime.now().isoformat()) for u in sample_users])
        conn.commit()
        conn.close()

init_db()
init_auth_db()

# --- Vehicle Authorization DB (SQLite: vehicle.db) ---
VEHICLE_DB_PATH = 'vehicle.db'

def init_vehicle_db():
    create_needed = not os.path.exists(VEHICLE_DB_PATH)
    conn = sqlite3.connect(VEHICLE_DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            plate TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            is_authorized INTEGER NOT NULL
        )
    ''')
    # Seed with sample data if empty
    c.execute('SELECT COUNT(*) FROM vehicles')
    count = c.fetchone()[0]
    if count == 0:
        sample_rows = [
            ("MH12AB1234", "Aarav Mehta", 1),
            ("DL8CAF4921", "Isha Kapoor", 1),
            ("KA03MN7788", "Rohan Iyer", 0),
            ("GJ01XY9900", "Priya Shah", 1),
            ("UP16ZZ4321", "Vikram Singh", 0),
        ]
        c.executemany('INSERT OR REPLACE INTO vehicles (plate, owner, is_authorized) VALUES (?, ?, ?)', sample_rows)
        conn.commit()
    conn.close()

init_vehicle_db()

# --- Authentication Functions ---
def authenticate_user(username, password):
    conn = sqlite3.connect('auth.db')
    c = conn.cursor()
    c.execute('SELECT id, username, full_name, role FROM users WHERE username = ? AND password = ?', (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        return {
            'id': user[0],
            'username': user[1],
            'full_name': user[2],
            'role': user[3]
        }
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Core Logic Functions ---

def verify_vehicle(license_plate):
    """
    Lookup the license plate in SQLite vehicle.db and return authorization info.
    """
    clean_plate = license_plate.strip().upper().replace(" ", "")
    conn = sqlite3.connect(VEHICLE_DB_PATH)
    c = conn.cursor()
    c.execute('SELECT owner, is_authorized FROM vehicles WHERE plate = ?', (clean_plate,))
    row = c.fetchone()
    conn.close()
    if row:
        owner, is_auth = row[0], int(row[1])
        return {
            "is_authorized": bool(is_auth),
            "plate": clean_plate,
            "details": {"owner": owner},
            "message": (f"SUCCESS! Vehicle {clean_plate} is authorized." if is_auth else f"ALERT! Vehicle {clean_plate} is UNAUTHORIZED."),
            "alert_type": ("success" if is_auth else "error"),
        }
    else:
        # Unknown vehicle: treat as unauthorized
        return {
            "is_authorized": False,
            "plate": clean_plate,
            "details": {"owner": "UNKNOWN"},
            "message": f"ALERT! Vehicle {clean_plate or 'UNKNOWN'} is UNAUTHORIZED/UNKNOWN.",
            "alert_type": "error",
        }

def save_image(file, plate, is_authorized):
    filename = secure_filename(file.filename)
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    conn = sqlite3.connect('vehicles.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO images (filename, upload_time, plate, is_authorized)
        VALUES (?, ?, ?, ?)
    ''', (filename, datetime.now().isoformat(), plate, int(is_authorized)))
    conn.commit()
    conn.close()
    return filename

def get_images():
    conn = sqlite3.connect('vehicles.db')
    c = conn.cursor()
    c.execute('SELECT filename, upload_time, plate, is_authorized FROM images ORDER BY upload_time DESC')
    images = c.fetchall()
    conn.close()
    return images

# --- Flask Routes ---

@app.route('/')
def index():
    """
    The main route serving the web interface (dashboard).
    """
    if 'user_id' not in session:
        return render_template('login.html')
    images = get_images()
    user = {
        'username': session.get('username'),
        'full_name': session.get('full_name'),
        'role': session.get('role')
    }
    return render_template('index.html', images=images, user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page for college authentication.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = authenticate_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """
    Logout the user and clear session.
    """
    session.clear()
    return redirect(url_for('login'))

@app.route('/scan', methods=['POST'])
@login_required
def scan_vehicle():
    """
    API endpoint to handle the vehicle scan request (triggered by the web interface).
    """
    data = request.get_json()
    license_plate = data.get('license_plate', '').strip()
    if not license_plate:
        return jsonify({
            "is_authorized": False,
            "message": "Error: No license plate detected.",
            "alert_type": "warning"
        }), 400
    result = verify_vehicle(license_plate)
    print(f"[{result['alert_type'].upper()}] Vehicle Scanned: {result['plate']} at {request.host_url}scan") 
    return jsonify(result)

@app.route('/upload', methods=['POST'])
@login_required
def upload_image():
    """
    API endpoint to handle image upload and immediate database save.
    """
    if 'image' not in request.files:
        return jsonify({"message": "No image uploaded"}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400
    plate = request.form.get('license_plate', 'UNKNOWN')
    result = verify_vehicle(plate)
    filename = save_image(file, plate, result['is_authorized'])
    return jsonify({"message": "Image uploaded", "filename": filename, "result": result})

@app.route('/gallery')
@login_required
def gallery():
    """
    API endpoint to fetch all images for gallery display.
    """
    images = get_images()
    return jsonify(images)

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- Application Run ---

if __name__ == '__main__':
    app.run(debug=True)