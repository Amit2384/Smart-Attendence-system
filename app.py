from flask import Flask, render_template, request, jsonify, make_response
import sqlite3
from datetime import datetime
import cv2
import face_recognition
import numpy as np
import os
import pickle
import base64

app = Flask(__name__)

# Database and Face Encodings
DB_FILE = "attendance.db"
CACHE_FILE = "faces/encodings_cache.pkl"
known_encodings, known_face_names = [], []

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "rb") as f:
        cache_data = pickle.load(f)
        known_encodings, known_face_names = cache_data["encodings"], cache_data["names"]

def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )''')
        conn.commit()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process-image', methods=['POST'])
def process_image():
    data = request.json
    if 'image' not in data:
        return jsonify({"error": "No image data provided"}), 400

    # Decode image
    image_data = base64.b64decode(data['image'].split(',')[1])
    img = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)

    # Face recognition
    face_locations = face_recognition.face_locations(img)
    face_encodings = face_recognition.face_encodings(img, face_locations)

    recognized_faces, new_attendance = [], False
    now, current_date = datetime.now(), datetime.now().strftime("%Y-%m-%d")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.4)
            name = "Unknown"
            if any(matches):
                best_match = np.argmin(face_recognition.face_distance(known_encodings, face_encoding))
                if matches[best_match]:
                    name = known_face_names[best_match]
                    cursor.execute("SELECT 1 FROM attendance WHERE name=? AND timestamp LIKE ?", (name, f"{current_date}%"))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO attendance (name, timestamp) VALUES (?, ?)", (name, now.strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit()
                        new_attendance = True
            recognized_faces.append({"top": top, "right": right, "bottom": bottom, "left": left, "name": name})

    return jsonify({"recognized_faces": recognized_faces, "new_attendance": new_attendance})

@app.route('/get-attendance', methods=['GET'])
def get_attendance():
    with get_db_connection() as conn:
        records = conn.execute("SELECT name, timestamp FROM attendance ORDER BY timestamp DESC").fetchall()
    return jsonify({"attendance": [{"name": r[0], "time": r[1]} for r in records]})

@app.route('/export-attendance', methods=['GET'])
def export_attendance():
    with get_db_connection() as conn:
        records = conn.execute("SELECT name, timestamp FROM attendance ORDER BY timestamp DESC").fetchall()
    csv_output = "time,name,status\n" + "\n".join(f"{r[1]},{r[0]},Present" for r in records)
    response = make_response(csv_output)
    response.headers["Content-Disposition"] = "attachment; filename=attendance.csv"
    response.headers["Content-type"] = "text/csv"
    return response

if __name__ == '__main__':
    app.run(debug=True)
