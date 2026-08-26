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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Initialize DB on server start
init_db()

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


# =====================================================
# GROQ CONFIGURATION
# =====================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

# Current Groq models
PRIMARY_MODEL = "openai/gpt-oss-120b"
BACKUP_MODEL = "openai/gpt-oss-20b"


# =====================================================
# GROQ CLIENT
# =====================================================

client = None

if GROQ_API_KEY:
    client = Groq(
        api_key=GROQ_API_KEY
    )


# =====================================================
# AASHI SYSTEM PROMPT
# =====================================================

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
# HOME & HEALTH CHECK
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
        "groq_key_configured": bool(GROQ_API_KEY),
        "primary_model": PRIMARY_MODEL,
        "backup_model": BACKUP_MODEL
    })


# =====================================================
# LIVE SIGNUP API
# =====================================================

@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "error": "Request body missing"}), 400

        username = str(data.get("username", "")).strip()
        password = str(data.get("password", "")).strip()

        if not username or not password:
            return jsonify({"success": False, "error": "Username aur password dono zaroori hain."}), 400

        if len(password) < 4:
            return jsonify({"success": False, "error": "Password kam se kam 4 characters ka hona chahiye."}), 400

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                       (username, hash_password(password)))
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Account successfully create ho gaya! 🎉"
        }), 200

    except sqlite3.IntegrityError:
        return jsonify({
            "success": False, 
            "error": "Yeh username pehle se registered hai. Doosra username choose karein."
        }), 409
    except Exception as e:
        return jsonify({
            "success": False, 
            "error": f"Signup failed: {str(e)}"
        }), 500


# =====================================================
# LIVE LOGIN API
# =====================================================

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "error": "Request body missing"}), 400

        username = str(data.get("username", "")).strip()
        password = str(data.get("password", "")).strip()

        if not username or not password:
            return jsonify({"success": False, "error": "Username aur password daalna zaroori hai."}), 400

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, username FROM users WHERE username = ? AND password = ?", 
                       (username, hash_password(password)))
        user = cursor.fetchone()
        conn.close()

        if user:
            return jsonify({
                "success": True,
                "message": "Login successful!",
                "user": {
                    "id": user[0],
                    "username": user[1]
                }
            }), 200
        else:
            return jsonify({
                "success": False, 
                "error": "Galat username ya password. Kripya dobara check karein."
            }), 401

    except Exception as e:
        return jsonify({
            "success": False, 
            "error": f"Login failed: {str(e)}"
        }), 500


# =====================================================
# GROQ REQUEST FUNCTION
# =====================================================

def call_groq(model, user_message):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    if client is None:
        raise RuntimeError("Groq client is not initialized")

    print("--------------------------------------")
    print("GROQ REQUEST")
    print("MODEL:", model)
    print("MESSAGE:", user_message[:200])
    print("--------------------------------------")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        temperature=0.7,
        max_tokens=2048
    )

    return response


# =====================================================
# PROCESS GROQ RESPONSE
# =====================================================

def process_success_response(response, model):
    try:
        if response is None or not response.choices:
            return {
                "success": False,
                "error": "Groq returned no response choices",
                "model": model
            }

        message = response.choices[0].message
        if message is None:
            return {
                "success": False,
                "error": "Groq returned an empty message",
                "model": model
            }

        ai_reply = str(message.content or "").strip()

        if not ai_reply:
            return {
                "success": False,
                "error": "Groq returned an empty response",
                "model": model
            }

        return {
            "success": True,
            "reply": ai_reply,
            "model": model,
            "provider": "Groq"
        }

    except Exception as e:
        print("PROCESS RESPONSE ERROR:", str(e))
        return {
            "success": False,
            "error": "Failed to process Groq response",
            "model": model,
            "details": str(e)
        }


# =====================================================
# CHAT API
# =====================================================

@app.route("/chat", methods=["POST"])
def chat():
    try:
        if not GROQ_API_KEY or client is None:
            return jsonify({
                "success": False,
                "error": "Groq client / API Key is not configured on Render"
            }), 500

        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is missing"
            }), 400

        user_message = str(data.get("message", "")).strip()

        if not user_message:
            return jsonify({
                "success": False,
                "error": "Message cannot be empty"
            }), 400

        print("\n======================================")
        print("AASHI CHAT REQUEST")
        print("MESSAGE:", user_message[:200])
        print("======================================")

        # Primary Model Execution
        try:
            response = call_groq(PRIMARY_MODEL, user_message)
            result = process_success_response(response, PRIMARY_MODEL)

            if result.get("success"):
                return jsonify(result)

        except Exception as primary_error:
            print("PRIMARY MODEL ERROR:", str(primary_error))

        # Backup Model Fallback
        time.sleep(0.5)

        try:
            print("Trying backup model:", BACKUP_MODEL)
            backup_response = call_groq(BACKUP_MODEL, user_message)
            backup_result = process_success_response(backup_response, BACKUP_MODEL)

            if backup_result.get("success"):
                backup_result["fallback_used"] = True
                return jsonify(backup_result)

            return jsonify({
                "success": False,
                "error": "Both Groq models returned an invalid response",
                "details": backup_result
            }), 502

        except Exception as backup_error:
            print("BACKUP MODEL ERROR:", str(backup_error))
            return jsonify({
                "success": False,
                "error": "Groq API request failed on all models",
                "details": str(backup_error)
            }), 502

    except Exception as e:
        print("SERVER ERROR:", str(e))
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "details": str(e)
        }), 500


# =====================================================
# SERVER LAUNCHER
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("======================================")
    print("AASHI AI BACKEND LIVE ENGINE")
    print("======================================")
    print("Provider:", "Groq")
    print("Primary:", PRIMARY_MODEL)
    print("Backup:", BACKUP_MODEL)
    print("Port:", port)
    print("======================================")

    app.run(host="0.0.0.0", port=port, debug=False)
