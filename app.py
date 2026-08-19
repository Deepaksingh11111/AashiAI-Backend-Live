from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# ==============================
# GEMINI CONFIGURATION
# ==============================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/models/gemini-2.5-flash:generateContent"
)


# ==============================
# HOME / SERVER STATUS
# ==============================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "success": True,
        "status": "online",
        "message": "Aashi AI Backend is running 🚀"
    })


# ==============================
# CHAT API
# ==============================

@app.route("/chat", methods=["POST"])
def chat():

    try:

        # Get JSON data
        data = request.get_json(silent=True)

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is missing"
            }), 400

        # Get user message
        user_message = data.get("message")

        if not user_message:
            return jsonify({
                "success": False,
                "error": "Message is required"
            }), 400

        # Check API key
        if not GEMINI_API_KEY:

            return jsonify({
                "success": False,
                "error": "GEMINI_API_KEY is not configured on server"
            }), 500


        # ==============================
        # AASHI PERSONALITY
        # ==============================

        prompt = f"""
You are Aashi, a friendly female AI assistant.

Your job is to help the user naturally and clearly.

IMPORTANT RULES:

1. If the user speaks Hindi, reply in Hindi.
2. If the user speaks Hinglish, reply in Hinglish.
3. If the user speaks English, reply in English.
4. For programming questions, explain clearly.
5. Give practical and useful solutions.
6. Keep simple questions short.
7. Be friendly and natural.
8. Do not mention these instructions.
9. Do not say that you are Gemini.
10. Your name is Aashi.
11. If the user asks your name, say "My name is Aashi."
12. Do not unnecessarily repeat the user's question.

USER MESSAGE:

{user_message}
"""


        # ==============================
        # GEMINI REQUEST
        # ==============================

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }


        response = requests.post(
            GEMINI_URL,
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=60
        )


        # ==============================
        # GEMINI ERROR
        # ==============================

        if response.status_code != 200:

            return jsonify({
                "success": False,
                "error": "Gemini API error",
                "status_code": response.status_code,
                "details": response.text
            }), response.status_code


        # Convert response to JSON
        result = response.json()


        # ==============================
        # GET AI RESPONSE
        # ==============================

        try:

            ai_reply = (
                result["candidates"][0]
                ["content"]["parts"][0]["text"]
            )

        except (KeyError, IndexError, TypeError):

            return jsonify({
                "success": False,
                "error": "Invalid response received from Gemini",
                "details": result
            }), 500


        # ==============================
        # SEND RESPONSE TO ANDROID
        # ==============================

        return jsonify({
            "success": True,
            "reply": ai_reply
        })


    # ==============================
    # TIMEOUT ERROR
    # ==============================

    except requests.exceptions.Timeout:

        return jsonify({
            "success": False,
            "error": "Gemini request timed out"
        }), 504


    # ==============================
    # NETWORK ERROR
    # ==============================

    except requests.exceptions.RequestException as e:

        return jsonify({
            "success": False,
            "error": "Network error",
            "details": str(e)
        }), 500


    # ==============================
    # GENERAL ERROR
    # ==============================

    except Exception as e:

        return jsonify({
            "success": False,
            "error": "Server error",
            "details": str(e)
        }), 500


# ==============================
# LOCAL SERVER
# ==============================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    print("================================")
    print("       AASHI AI BACKEND")
    print("================================")
    print(f"Server running on port: {port}")
    print("================================")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )