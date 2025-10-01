from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__, static_folder=".")

messages = [{"role": "system", "content": "You are FluxAI, a god-tier coding assistant."}]

# Serve index.html at root
@app.route("/")
def home():
    return send_from_directory(".", "index.html")

# Serve CSS
@app.route("/style.css")
def styles():
    return send_from_directory(".", "style.css")

# Serve JS
@app.route("/script.js")
def script():
    return send_from_directory(".", "script.js")

# Chat endpoint
@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message")
    messages.append({"role": "user", "content": user_msg})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
    )

    reply = response.choices[0].message.content
    messages.append({"role": "assistant", "content": reply})
    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(debug=True)
