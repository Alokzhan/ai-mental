import cv2
import sqlite3
import time
from datetime import datetime
from deepface import DeepFace
import pyttsx3
from flask import Flask, render_template_string, jsonify, request, redirect, url_for, send_file
from threading import Thread
from collections import Counter
import os
import csv

# -----------------------------
# Initialize DB
# -----------------------------
def init_db():
    conn = sqlite3.connect("emotions.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS emotion_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            emotion TEXT,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_emotion(emotion, notes=""):
    conn = sqlite3.connect("emotions.db")
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO emotion_log (timestamp, emotion, notes) VALUES (?, ?, ?)", (timestamp, emotion, notes))
    conn.commit()
    conn.close()

# -----------------------------
#  Emotion Detection
# -----------------------------
emotion_messages = {
    "happy": "You seem happy. Keep smiling!",
    "sad": "It's okay to feel sad. You're not alone.",
    "angry": "Take a deep breath. Let’s calm down together.",
    "surprise": "Wow! Something unexpected?",
    "fear": "You're safe. Breathe slowly.",
    "neutral": "Stay grounded.",
    "disgust": "Let’s refocus on something positive."
}

def detect_emotion():
    engine = pyttsx3.init()
    engine.setProperty('rate', 140)
    cap = cv2.VideoCapture(0)
    last_emotion = None
    last_spoken_time = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        try:
            result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            emotion = result[0]['dominant_emotion']
            current_time = time.time()

            if emotion != last_emotion and current_time - last_spoken_time > 5:
                msg = emotion_messages.get(emotion, "You're doing great.")
                engine.say(msg)
                engine.runAndWait()
                log_emotion(emotion)
                last_emotion = emotion
                last_spoken_time = current_time

            cv2.putText(frame, f"Emotion: {emotion}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 100, 100), 2)
        except Exception as e:
            print("Emotion detection error:", e)

        cv2.imshow('AR Emotion Assistant', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()

# -----------------------------
# Flask App (Web UI + Chatbot)
# -----------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string('''
    <h2>Welcome to AR Mental Health Assistant</h2>
    <a href="/trends">📈 View Emotional Trends</a> |
    <a href="/log">📝 Manual Emotion Entry</a> |
    <a href="/journal">📓 Emotion Journal</a> |
    <a href="/chat">💬 Chatbot</a> |
    <a href="/export">📁 Export Logs</a>
    ''')

@app.route('/chat', methods=['GET', 'POST'])
def chatbot():
    response = ""
    if request.method == 'POST':
        user_msg = request.form['message'].lower()
        if "sad" in user_msg:
            response = "I'm here for you. Want to try a breathing exercise?"
        elif "happy" in user_msg:
            response = "Yay! Keep the good vibes going!"
        elif "angry" in user_msg:
            response = "Try taking a deep breath. Let it go."
        elif "alone" in user_msg:
            response = "You're never alone. I'm here. 💙"
        else:
            response = "I'm listening. Tell me more."
    return render_template_string('''
        <h2>Emotion Support Chatbot</h2>
        <form method="POST">
            <input name="message" placeholder="How are you feeling?" style="width:300px">
            <input type="submit" value="Send">
        </form>
        <p><b>Bot:</b> {{response}}</p>
        <a href="/">← Back to Home</a>
    ''', response=response)

@app.route('/log', methods=['GET', 'POST'])
def log_manual():
    if request.method == 'POST':
        emotion = request.form['emotion']
        notes = request.form['notes']
        log_emotion(emotion, notes)
        return redirect(url_for('log_manual'))
    return render_template_string('''
        <h2>Log Emotion Manually</h2>
        <form method="POST">
            <label>Emotion:</label>
            <select name="emotion">
                <option value="happy">Happy</option>
                <option value="sad">Sad</option>
                <option value="angry">Angry</option>
                <option value="fear">Fear</option>
                <option value="disgust">Disgust</option>
                <option value="neutral">Neutral</option>
                <option value="surprise">Surprise</option>
            </select><br><br>
            <label>Notes:</label><br>
            <textarea name="notes" rows="4" cols="40"></textarea><br><br>
            <input type="submit" value="Log">
        </form>
        <a href="/">← Back</a>
    ''')

@app.route('/journal')
def journal():
    conn = sqlite3.connect("emotions.db")
    c = conn.cursor()
    c.execute("SELECT timestamp, emotion, notes FROM emotion_log ORDER BY timestamp DESC")
    logs = c.fetchall()
    conn.close()

    entries = ''.join(
        [f"<li><strong>{t}</strong> - <em>{e}</em><br>Notes: {n}</li><br>" for t, e, n in logs]
    )
    return f"<h2>Emotion Journal</h2><ul>{entries}</ul><a href='/'>← Back</a>"

@app.route('/trends')
def trends():
    return render_template_string('''
    <h2>Emotion Trends</h2>
    <canvas id="chart" width="400" height="400"></canvas>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
    fetch("/api/emotions")
      .then(res => res.json())
      .then(data => {
        const ctx = document.getElementById('chart').getContext('2d');
        new Chart(ctx, {
          type: 'pie',
          data: {
            labels: Object.keys(data),
            datasets: [{
              label: 'Emotions',
              data: Object.values(data),
              backgroundColor: [
                'lightblue', 'lightgreen', 'salmon', 'orange', 'gray', 'plum', 'gold'
              ]
            }]
          }
        });
    });
    </script>
    <a href="/">← Back</a>
    ''')

@app.route('/api/emotions')
def emotion_api():
    conn = sqlite3.connect("emotions.db")
    c = conn.cursor()
    c.execute("SELECT emotion FROM emotion_log")
    rows = c.fetchall()
    conn.close()
    return jsonify(dict(Counter(row[0] for row in rows)))

@app.route('/export')
def export_logs():
    conn = sqlite3.connect("emotions.db")
    c = conn.cursor()
    c.execute("SELECT timestamp, emotion, notes FROM emotion_log")
    rows = c.fetchall()
    conn.close()
    with open("emotion_export.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Emotion", "Notes"])
        writer.writerows(rows)
    return send_file("emotion_export.csv", as_attachment=True)

# -----------------------------
# Entrypoint
# -----------------------------
if __name__ == '__main__':
    init_db()
    t = Thread(target=detect_emotion)
    t.daemon = True
    t.start()
    app.run(debug=True, port=5000)
