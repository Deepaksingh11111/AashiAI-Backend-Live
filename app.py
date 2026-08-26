from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
import os
import time
import sqlite3
import hashlib
from pypdf import PdfReader
import docx
import io

app = Flask(__name__)
CORS(app)

ADMIN_SECRET_KEY = "AASHI_SUPER_ADMIN_2026"

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def get_db_connection():
    return sqlite3.connect('users.db', timeout=10.0, check_same_thread=False)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE',
            camera_access TEXT DEFAULT 'NOT APPROVED',
            mic_access TEXT DEFAULT 'NOT APPROVED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            message TEXT,
            reply TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Seed Default Super Admin accounts
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, status) VALUES (?, ?, ?)",
                       ('admin', hash_password('admin123'), 'ACTIVE'))
    
    cursor.execute("SELECT id FROM users WHERE username = 'deepak'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, status) VALUES (?, ?, ?)",
                       ('deepak', hash_password('admin123'), 'ACTIVE'))

    conn.commit()
    conn.close()

init_db()

def verify_admin(req_data):
    return req_data.get("admin_key", "") == ADMIN_SECRET_KEY

# =====================================================
# GROQ CONFIGURATION (YOUR REQUESTED MODELS)
# =====================================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
PRIMARY_MODEL = "openai/gpt-oss-120b"
BACKUP_MODEL = "openai/gpt-oss-20b"

client = None
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """
You are Aashi, an intelligent female AI assistant created and developed by Deepak Singh.
Rules:
1. If the user asks in Hindi (Devanagari script), reply ONLY in pure, natural Hindi (Devanagari).
2. If the user asks in Hinglish (Hindi written in Roman script), reply in natural, conversational Hinglish.
3. If the user asks in English, reply in crisp, clear English.
4. For math/numerical queries, solve step-by-step with clear formulas and worked equations.
5. If asked about your creator, always state that you were created and developed by Deepak Singh.
"""

def extract_text_from_file(file_storage):
    filename = file_storage.filename.lower()
    content = ""
    try:
        file_bytes = file_storage.read()
        file_storage.seek(0)
        
        if filename.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    content += text + "\n"
        elif filename.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file_bytes))
            content = "\n".join([p.text for p in doc.paragraphs])
        elif filename.endswith(".txt"):
            content = file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"Extraction error: {e}")
    return content.strip()

def call_groq(model, user_message):
    return client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        temperature=0.7,
        max_tokens=2048
    )

@app.route("/", methods=["GET"])
def home():
    return jsonify({"success": True, "status": "online", "message": "Aashi AI Backend Live 🚀"})

@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json(silent=True) or {}
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", "")).strip()

        if not username or not password:
            return jsonify({"success": False, "error": "Username aur password dono zaroori hain."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                       (username, hash_password(password)))
        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "Account successfully create ho gaya! 🎉"}), 200
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Yeh username pehle se registered hai."}), 409
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json(silent=True) or {}
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", "")).strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, status FROM users WHERE username = ? AND password = ?", 
                       (username, hash_password(password)))
        user = cursor.fetchone()
        conn.close()

        if user:
            if user[2] == "BLOCKED":
                return jsonify({"success": False, "error": "Aapka account admin dwara block kar diya gaya hai."}), 403
            return jsonify({"success": True, "message": "Login successful!", "user": {"id": user[0], "username": user[1]}}), 200
        else:
            return jsonify({"success": False, "error": "Galat username ya password."}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/user/check_requests", methods=["POST"])
def check_user_requests():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")

    if not username:
        return jsonify({"success": False, "error": "Username required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, camera_access, mic_access FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    if row:
        status = row[0]
        if status == "BLOCKED":
            return jsonify({"success": True, "is_blocked": True, "error": "BLOCKED_USER"}), 200

        return jsonify({
            "success": True,
            "is_blocked": False,
            "camera_access": row[1],
            "mic_access": row[2]
        }), 200
    return jsonify({"success": False, "error": "User not found"}), 404

# DOCUMENT UPLOAD & QA ENDPOINT
@app.route("/analyze_file", methods=["POST"])
def analyze_file():
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "File attach nahi ki gayi."}), 400
            
        uploaded_file = request.files['file']
        if uploaded_file.filename == '':
            return jsonify({"success": False, "error": "Koi file select nahi ki gayi."}), 400

        user_query = request.form.get("query", "Summarize and extract key insights from this document.")
        username = request.form.get("username", "")

        if username:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM users WHERE username = ?", (username,))
            user_row = cursor.fetchone()
            conn.close()
            if user_row and user_row[0] == "BLOCKED":
                return jsonify({"success": False, "error": "BLOCKED_USER"}), 403

        extracted_text = extract_text_from_file(uploaded_file)
        if not extracted_text or len(extracted_text.strip()) == 0:
            return jsonify({"success": False, "error": "File se readable text extract nahi ho saka."}), 400

        truncated_doc = extracted_text[:8000]
        prompt = f"Document Text:\n\"\"\"\n{truncated_doc}\n\"\"\"\n\nUser Instruction: {user_query}\n\nPlease analyze and explain clearly."

        try:
            response = call_groq(PRIMARY_MODEL, prompt)
            reply = response.choices[0].message.content
        except Exception:
            time.sleep(0.5)
            response = call_groq(BACKUP_MODEL, prompt)
            reply = response.choices[0].message.content

        return jsonify({"success": True, "reply": reply}), 200
    except Exception as e:
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500

# CHAT API (TEXT & VOICE)
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        username = str(data.get("username", "")).strip()
        user_message = str(data.get("message", "")).strip()

        if username:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM users WHERE username = ?", (username,))
            user_row = cursor.fetchone()
            conn.close()

            if user_row and user_row[0] == "BLOCKED":
                return jsonify({
                    "success": False, 
                    "error": "BLOCKED_USER", 
                    "reply": "Aapka account admin dwara block kar diya gaya hai."
                }), 403

        if not user_message:
            return jsonify({"success": False, "error": "Message cannot be empty"}), 400

        if not GROQ_API_KEY or client is None:
            return jsonify({"success": False, "error": "Groq client not configured"}), 500

        try:
            response = call_groq(PRIMARY_MODEL, user_message)
            reply = response.choices[0].message.content
            return jsonify({"success": True, "reply": reply, "model": PRIMARY_MODEL})
        except Exception:
            time.sleep(0.5)
            response = call_groq(BACKUP_MODEL, user_message)
            reply = response.choices[0].message.content
            return jsonify({"success": True, "reply": reply, "model": BACKUP_MODEL, "fallback": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ADMIN ENDPOINTS
@app.route("/admin/users", methods=["POST"])
def get_all_users():
    data = request.get_json(silent=True) or {}
    if not verify_admin(data):
        return jsonify({"success": False, "error": "Unauthorized Access"}), 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, status, camera_access, mic_access, created_at FROM users")
    rows = cursor.fetchall()
    conn.close()

    user_list = [{
        "id": r[0],
        "username": r[1],
        "status": r[2],
        "camera": r[3],
        "mic": r[4],
        "created_at": r[5]
    } for r in rows]

    return jsonify({"success": True, "total_users": len(user_list), "users": user_list}), 200

@app.route("/admin/update_user_status", methods=["POST"])
def update_user_status():
    data = request.get_json(silent=True) or {}
    if not verify_admin(data):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    username = data.get("username", "")
    new_status = data.get("status", "BLOCKED")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE username = ?", (new_status, username))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"User status updated to {new_status}"}), 200

@app.route("/admin/stats", methods=["POST"])
def get_stats():
    data = request.get_json(silent=True) or {}
    if not verify_admin(data):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'ACTIVE'")
    active_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM chats")
    total_chats = cursor.fetchone()[0]
    conn.close()

    return jsonify({
        "success": True,
        "total_users": total_users,
        "active_users": active_users,
        "total_chats": total_chats,
        "server_status": "ONLINE 🟢"
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
