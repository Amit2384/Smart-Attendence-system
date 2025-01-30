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

# Load database and face encodings (similar to previous code)
db_file = "attendance.db"
cache_file = "faces/encodings_cache.pkl"
known_encodings = []
known_face_names = []

if os.path.exists(cache_file):
    with open(cache_file, "rb") as f:
        cache_data = pickle.load(f)
        known_encodings = cache_data["encodings"]
        known_face_names = cache_data["names"]

def init_db():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process-image', methods=['POST'])
def process_image():
    data = request.json
    if 'image' not in data:
        return jsonify({"error": "No image data provided"}), 400

    # Decode the base64 image
    image_data = base64.b64decode(data['image'].split(',')[1])
    nparr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Recognize faces
    face_locations = face_recognition.face_locations(img)
    face_encodings = face_recognition.face_encodings(img, face_locations)

    attendance = []
    recognized_faces = []
    new_attendance = False

    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
        matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.4)
        face_distances = face_recognition.face_distance(known_encodings, face_encoding)

        name = "Unknown"
        if len(face_distances) > 0:
            best_match_index = np.argmin(face_distances)
            if matches[best_match_index]:
                name = known_face_names[best_match_index]

                # Mark attendance if not already marked today
                now = datetime.now()
                timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
                current_date = now.strftime("%Y-%m-%d")

                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 1 FROM attendance 
                    WHERE name = ? AND timestamp LIKE ?
                """, (name, f"{current_date}%"))
                record_exists = cursor.fetchone()

                if not record_exists:
                    cursor.execute("INSERT INTO attendance (name, timestamp) VALUES (?, ?)", (name, timestamp))
                    conn.commit()
                    new_attendance = True

                conn.close()

        # Append face details for drawing
        recognized_faces.append({
            "top": top,
            "right": right,
            "bottom": bottom,
            "left": left,
            "name": name
        })

    return jsonify({
        "recognized_faces": recognized_faces,
        "new_attendance": new_attendance
    })

@app.route('/get-attendance', methods=['GET'])
def get_attendance():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name, timestamp FROM attendance ORDER BY timestamp DESC")
    records = cursor.fetchall()
    conn.close()

    attendance = [{"name": row[0], "time": row[1]} for row in records]
    return jsonify({"attendance": attendance})

@app.route('/export-attendance', methods=['GET'])
def export_attendance():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name, timestamp FROM attendance ORDER BY timestamp DESC")
    records = cursor.fetchall()
    conn.close()

    output = "time,name,status\n"
    for record in records:
        output += f'{record[1]},{record[0]},Present\n'

    # Creating a response object with CSV data
    response = make_response(output)
    response.headers["Content-Disposition"] = "attachment; filename=attendance.csv"
    response.headers["Content-type"] = "text/csv"

    return response

if __name__ == '__main__':
    app.run(debug=True)
