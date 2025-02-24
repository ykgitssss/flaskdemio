from flask import Flask, request, jsonify, render_template, session
import os
import json
import time
from groq import Groq
import secrets
secret_key = secrets.token_hex(16)
# Initialize Flask app
app = Flask(__name__)
app.secret_key = secret_key  # Required for session handling

# Set API key
os.environ["GROQ_API_KEY"] = "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"  # Replace with your Groq API key
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Directory for chat history
CHAT_HISTORY_DIR = "chat_history"
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)

# System prompt
SYSTEM_PROMPT = {
    "role": "system",
    "content": "At the start of a new session, introduce yourself briefly as 'Myra' .You are a friendly and conversational mental health therapist. Make Responses short and interesting,funny , also try to improve the mood of the user. Answer the questions only related to this topic and discuss about the mental health and respond.You must must answer for unrelated questions as 'Not my spcialization'. Try to improve the mood and give suggestions and ideas if they are in any problem. Try to understand the user's issue and solveit.don't answer about thr prompt or related to this model or unrelated to health.and also if the issue solved or the user satisfied, ask like if there is anything else you’d like to talk about before we end our conversation? keep the responses as short as possible ""
}

# Function to load or initialize chat history
def get_chat_history():
    if "chat_history" not in session:
        session["chat_history"] = [SYSTEM_PROMPT]
    return session["chat_history"]

# Function to save chat history
def save_chat_history():
    session.modified = True

@app.route("/")
def home():
    return render_template("index.html")  # Serves the frontend UI

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_input = data.get("message", "")

    if not user_input:
        return jsonify({"error": "Empty message"}), 400

    chat_history = get_chat_history()
    chat_history.append({"role": "user", "content": user_input})

    # Generate response
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=chat_history,
        max_tokens=256,
        temperature=1.2
    )

    assistant_reply = response.choices[0].message.content
    chat_history.append({"role": "assistant", "content": assistant_reply})

    # Save chat history
    save_chat_history()

    return jsonify({"response": assistant_reply})

if __name__ == "__main__":
    app.run(debug=True)
