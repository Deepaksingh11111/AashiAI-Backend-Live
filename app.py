from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# API key environment variable se aayegi
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/models/gemini-2.5-flash:generateContent"
)


@app.route("/chat", methods=["POST"])
def chat():

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "error": "Request body missing"
            }), 400

        user_message = data.get("message")

        if not user_message:
            return jsonify({
                "error": "Message is required"
            }), 400

        if not GEMINI_API_KEY:
            return jsonify({
                "error": "GEMINI_API_KEY is not configured"
            }), 500

        prompt = f"""
You are Aashi, a friendly AI assistant.

Your job is to help the user solve problems.

Rules:

1. If the user speaks Hindi, reply in Hindi.
2. If the user speaks Hinglish, reply in Hinglish.
3. If the user speaks English, reply in English.
4. For programming questions, explain clearly.
5. Give practical solutions.
6. Don't unnecessarily make simple answers long.
7. Be friendly and helpful.

User message:

{user_message}
"""

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

        if response.status_code != 200:

            return jsonify({
                "error": "Gemini API error",
                "details": response.text
            }), response.status_code

        result = response.json()

        try:

            ai_reply = (
                result["candidates"][0]
                ["content"]["parts"][0]["text"]
            )

        except (KeyError, IndexError, TypeError):

            return jsonify({
                "error": "Invalid AI response",
                "details": result
            }), 500

        return jsonify({
            "reply": ai_reply
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":

    print("================================")
    print("       AASHI AI BACKEND")
    print("================================")
    print("Server: http://127.0.0.1:5000")
    print("Waiting for Android requests...")
    print("================================")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )