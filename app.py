from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
import os
import time
import sqlite3
import hashlib

# =====================================================
# FLASK CONFIGURATION
# =====================================================
app = Flask(__name__)
CORS(app)

# =====================================================
# DATABASE SETUP (SQLITE)
# =====================================================
def init_db():
    conn = sqlite3.connect('users.db')
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
    conn.commit()
    conn.close()

init_db()

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

ADMIN_SECRET_KEY = "AASHI_SUPER_ADMIN_2026"

def verify_admin(req_data):
    return req_data.get("admin_key", "") == ADMIN_SECRET_KEY

# =====================================================
# GROQ CONFIGURATION
# =====================================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
PRIMARY_MODEL = "openai/gpt-oss-120b"
BACKUP_MODEL = "openai/gpt-oss-20b"

client = None
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """
You are Aashi, a friendly, intelligent Indian female AI assistant created and developed by Deepak Singh.

PERSONALITY:
- Warm, polite, respectful, and helpful.
- Natural conversational Indian tone.

LANGUAGE RULES:
1. If the user speaks in Hindi (Devanagari script), reply ONLY in pure, natural Hindi (Devanagari).
2. If the user speaks in Hinglish (Hindi written in Roman script), reply in natural, conversational Hinglish.
3. If the user speaks in English, reply in clear, professional English.

MATHEMATICS & TECHNICAL RULES:
1. When solving math or numerical problems, always provide a step-by-step solution with clear formulas and worked calculations.
2. For programming queries, provide complete working code inside standard Markdown code blocks (```python, ```java, etc.).

IMPORTANT RULES:
1. Your name is Aashi.
2. If asked "Who is your creator?" or "Tumhe kisne banaya?", always answer that you were created and developed by Deepak Singh.
3. Never claim you are Gemini, ChatGPT, or developed by Google/OpenAI.
4. Keep answers crisp and avoid unnecessary emojis.
"""

# =====================================================
# PUBLIC ROUTES
# =====================================================
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "success": True,
        "status": "online",
        "message": "Aashi AI Backend is running 🚀",
        "provider": "Groq",
        "primary_model": PRIMARY_MODEL,
        "backup_model": BACKUP_MODEL,
        "groq_key_configured": bool(GROQ_API_KEY)
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "success": True,
        "backend": "online",
        "provider": "Groq",
        "groq_key_configured": bool(GROQ_API_KEY)
    })

@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json(silent=True) or {}
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", "")).strip()

        if not username or not password:
            return jsonify({"success": False, "error": "Username aur password dono zaroori hain."}), 400

        conn = sqlite3.connect('users.db')
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

        conn = sqlite3.connect('users.db')
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

# =====================================================
# ADMIN ENDPOINTS
# =====================================================
@app.route("/admin/users", methods=["POST"])
def get_all_users():
    data = request.get_json(silent=True) or {}
    if not verify_admin(data):
        return jsonify({"success": False, "error": "Unauthorized Access"}), 403

    conn = sqlite3.connect('users.db')
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

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE username = ?", (new_status, username))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"User status updated to {new_status}"}), 200

@app.route("/admin/update_permission", methods=["POST"])
def update_permission():
    data = request.get_json(silent=True) or {}
    if not verify_admin(data):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    username = data.get("username", "")
    perm_type = data.get("type", "")
    perm_val = data.get("value", "REQUESTED")

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    if perm_type == "camera":
        cursor.execute("UPDATE users SET camera_access = ? WHERE username = ?", (perm_val, username))
    elif perm_type == "mic":
        cursor.execute("UPDATE users SET mic_access = ? WHERE username = ?", (perm_val, username))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"{perm_type} permission updated to {perm_val}"}), 200

@app.route("/admin/stats", methods=["POST"])
def get_stats():
    data = request.get_json(silent=True) or {}
    if not verify_admin(data):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    conn = sqlite3.connect('users.db')
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

# =====================================================
# GROQ AI CHAT API
# =====================================================
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

@app.route("/chat", methods=["POST"])
def chat():
    try:
        if not GROQ_API_KEY or client is None:
            return jsonify({"success": False, "error": "Groq client not configured"}), 500

        data = request.get_json(silent=True) or {}
        user_message = str(data.get("message", "")).strip()

        if not user_message:
            return jsonify({"success": False, "error": "Message cannot be empty"}), 400

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
