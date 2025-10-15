# app.py
import os
import sqlite3
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime

# Initialize the Flask application
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB limit

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

init_db()

def load_authorized_vehicles(filename='authorized_vehicles.txt'):
    vehicles = {}
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            for line in f:
                plate = line.strip().upper().replace(" ", "")
                if plate:
                    vehicles[plate] = {"owner": "N/A", "status": "Authorized"}
    return vehicles

# Simulated Authorized Vehicle Database (In a real project, this would be SQLite or a larger DB)
AUTHORIZED_VEHICLES = load_authorized_vehicles()

# --- Core Logic Functions ---

def verify_vehicle(license_plate):
    """
    Simulates the OCR verification process against the authorized database.
    (In a real app, this function would contain OpenCV/Tesseract logic).
    """
    clean_plate = license_plate.strip().upper().replace(" ", "")
    if clean_plate in AUTHORIZED_VEHICLES:
        return {
            "is_authorized": True,
            "plate": clean_plate,
            "details": AUTHORIZED_VEHICLES[clean_plate],
            "message": f"SUCCESS! Vehicle {clean_plate} is authorized.",
            "alert_type": "success"
        }
    else:
        return {
            "is_authorized": False,
            "plate": clean_plate,
            "details": {"owner": "N/A"},
            "message": f"ALERT! Vehicle {clean_plate} is UNAUTHORIZED.",
            "alert_type": "error"
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
    images = get_images()
    return render_template('index.html', images=images)

@app.route('/scan', methods=['POST'])
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