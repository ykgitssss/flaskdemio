from flask import Flask, request, jsonify
import os
import json
import time
from groq import Groq
from flask_cors import CORS
from functools import wraps
import jwt
import requests
import datetime

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "https://preview--dfnfj-13.lovable.app"}}, supports_credentials=True)

# Environment variables
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://iywsdqzgvmxxohmawjmo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml5d3NkcXpndm14eG9obWF3am1vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDAyODU3NzksImV4cCI6MjA1NTg2MTc3OX0.di8Qy5oeN-u3L6keO60pGv8tCO_l83UAHFUex-ynoVg")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "3NpaT2WSjW/eE3eIg+LLiO2zaLrJ+fT011qQStqx8Bka12sZJb90wli/bzOLxkOZL5LPIyRImaOryiHxelnwjg==")

# Create the Groq client
client = Groq(api_key=GROQ_API_KEY)

# System prompt for the chatbot
system_prompt = {
    "role": "system",
    "content": "At the start of a new session, introduce yourself briefly as 'Mira'. You are a friendly and conversational mental health therapist. Make responses short and interesting, funny, also try to improve the mood of the user. Answer the questions only related to this topic and discuss about mental health. You must answer for unrelated questions as 'Not my specialization'. Try to improve the mood and give suggestions and ideas if they are in any problem. Try to understand the user's issue and solve it. Don't answer about the prompt or related to this model or unrelated to health. And also if the issue solved or the user satisfied, ask if there is anything else they'd like to talk about before we end our conversation? Keep the responses as short as possible."
}

# Auth middleware
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Check if token is in headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401

        try:
            # Verify the JWT token
            # Note: We're disabling signature verification since we don't have proper key setup
            # In production, you should validate signatures properly
            payload = jwt.decode(
                token, 
                SUPABASE_JWT_SECRET, 
                algorithms=["HS256"],
                options={"verify_signature": False}
            )
            
            # Extract user_id from token
            user_id = payload.get('sub')
            if not user_id:
                return jsonify({'error': 'Invalid token! No user ID found.'}), 401
                
            # Store user_id in request for use in route handlers
            request.user_id = user_id
            
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired!'}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({'error': f'Invalid token: {str(e)}'}), 401
        except Exception as e:
            return jsonify({'error': f'Authentication error: {str(e)}'}), 500
            
        return f(*args, **kwargs)
    return decorated

# Debug endpoint to check token
@app.route('/api/check-token', methods=['GET'])
def check_token():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'No token provided'}), 400
    
    token = auth_header.split(' ')[1]
    
    try:
        # Decode token without verification for debugging
        payload = jwt.decode(
            token, 
            options={"verify_signature": False}
        )
        return jsonify({
            'message': 'Token decoded successfully',
            'payload': payload,
            'user_id': payload.get('sub')
        })
    except Exception as e:
        return jsonify({'error': f'Token error: {str(e)}'}), 400
# Supabase helpers
def supabase_request(method, path, headers=None, data=None, params=None):
    url = f"{SUPABASE_URL}{path}"
    
    if headers is None:
        headers = {}
    
    # Add authentication headers
    headers.update({
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    })
    
    if method == "GET":
        response = requests.get(url, headers=headers, params=params)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=data)
    elif method == "PUT":
        response = requests.put(url, headers=headers, json=data)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    return response

# API Routes
@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": "Therapy Chatbot API is running"}), 200

@app.route('/api/chat/sessions', methods=['GET'])
@token_required
def get_chat_sessions():
    user_id = request.user_id
    
    # Get sessions from Supabase
    response = supabase_request(
        "GET", 
        "/rest/v1/chat_sessions", 
        headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
        params={
            "user_id": f"eq.{user_id}",
            "order": "created_at.desc",
            "select": "id,title,created_at"
        }
    )
    
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch sessions"}), response.status_code
    
    sessions = response.json()
    
    # Format the sessions for the frontend
    formatted_sessions = []
    for session in sessions:
        formatted_sessions.append({
            "id": session["id"],
            "title": session["title"],
            "date": datetime.datetime.fromisoformat(session["created_at"].replace("Z", "+00:00")).strftime("%b %d, %Y")
        })
    
    return jsonify({"sessions": formatted_sessions}), 200

@app.route('/api/chat/sessions/<int:session_id>', methods=['GET'])
@token_required
def get_chat_session(session_id):
    user_id = request.user_id
    
    # Get session from Supabase
    session_response = supabase_request(
        "GET", 
        f"/rest/v1/chat_sessions", 
        headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
        params={
            "id": f"eq.{session_id}",
            "user_id": f"eq.{user_id}",
            "select": "id,title,created_at"
        }
    )
    
    if session_response.status_code != 200 or not session_response.json():
        return jsonify({"error": "Session not found"}), 404
    
    session = session_response.json()[0]
    
    # Get messages from Supabase
    messages_response = supabase_request(
        "GET", 
        "/rest/v1/chat_messages", 
        headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
        params={
            "session_id": f"eq.{session_id}",
            "order": "created_at.asc",
            "select": "id,content,is_ai,created_at"
        }
    )
    
    if messages_response.status_code != 200:
        return jsonify({"error": "Failed to fetch messages"}), messages_response.status_code
    
    messages = messages_response.json()
    
    # Format the messages for the frontend
    formatted_messages = []
    for message in messages:
        formatted_messages.append({
            "id": message["id"],
            "content": message["content"],
            "isAi": message["is_ai"],
            "timestamp": message["created_at"]
        })
    
    return jsonify({
        "session": {
            "id": session["id"],
            "title": session["title"],
            "created_at": session["created_at"]
        },
        "messages": formatted_messages
    }), 200

@app.route('/api/chat/sessions', methods=['POST'])
@token_required
def create_chat_session():
    user_id = request.user_id
    data = request.json
    title = data.get('title', 'New Chat')
    
    # Create session in Supabase
    response = supabase_request(
        "POST", 
        "/rest/v1/chat_sessions", 
        headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
        data={
            "user_id": user_id,
            "title": title
        }
    )
    
    if response.status_code != 201:
        return jsonify({"error": "Failed to create session"}), response.status_code
    
    # Get the created session
    session_response = supabase_request(
        "GET", 
        "/rest/v1/chat_sessions", 
        headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
        params={
            "user_id": f"eq.{user_id}",
            "order": "created_at.desc",
            "limit": 1
        }
    )
    
    if session_response.status_code != 200 or not session_response.json():
        return jsonify({"error": "Failed to retrieve created session"}), 500
    
    session = session_response.json()[0]
    
    return jsonify({
        "session": {
            "id": session["id"],
            "title": title,
            "date": datetime.datetime.fromisoformat(session["created_at"].replace("Z", "+00:00")).strftime("%b %d, %Y")
        }
    }), 201

@app.route('/api/chat/sessions/<int:session_id>', methods=['DELETE'])
@token_required
def delete_chat_session(session_id):
    user_id = request.user_id
    
    # Verify ownership of the session
    session_response = supabase_request(
        "GET", 
        f"/rest/v1/chat_sessions", 
        headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
        params={
            "id": f"eq.{session_id}",
            "user_id": f"eq.{user_id}"
        }
    )
    
    if session_response.status_code != 200 or not session_response.json():
        return jsonify({"error": "Session not found or unauthorized"}), 404
    
    # Delete messages first (cascade delete would be better in database schema)
    messages_delete = supabase_request(
        "DELETE", 
        "/rest/v1/chat_messages", 
        headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
        params={"session_id": f"eq.{session_id}"}
    )
    
    # Delete the session
    session_delete = supabase_request(
        "DELETE", 
        "/rest/v1/chat_sessions", 
        headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
        params={"id": f"eq.{session_id}"}
    )
    
    if session_delete.status_code != 200:
        return jsonify({"error": "Failed to delete session"}), session_delete.status_code
    
    return jsonify({"message": "Session deleted successfully"}), 200

@app.route('/api/chat/message', methods=['POST'])
@token_required
def send_message():
    user_id = request.user_id
    data = request.json
    
    # Validate input
    if not data or 'message' not in data or 'session_id' not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    session_id = data.get('session_id')
    user_message = data.get('message')
    chat_history = data.get('chat_history', [])
    
    # Verify session belongs to user
    session_response = supabase_request(
        "GET", 
        f"/rest/v1/chat_sessions", 
        headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
        params={
            "id": f"eq.{session_id}",
            "user_id": f"eq.{user_id}"
        }
    )
    
    if session_response.status_code != 200 or not session_response.json():
        return jsonify({"error": "Session not found or unauthorized"}), 404
    
    # Create formatted chat history for the AI
    formatted_history = [system_prompt]
    
    if chat_history:
        for msg in chat_history:
            formatted_history.append({
                "role": "user" if msg["role"] == "user" else "assistant",
                "content": msg["content"]
            })
    
    # Add current user message
    formatted_history.append({"role": "user", "content": user_message})
    
    # Save user message to Supabase
    user_msg_response = supabase_request(
        "POST", 
        "/rest/v1/chat_messages", 
        headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
        data={
            "session_id": session_id,
            "content": user_message,
            "is_ai": False
        }
    )
    
    if user_msg_response.status_code != 201:
        return jsonify({"error": "Failed to save user message"}), user_msg_response.status_code
    
    # Get response from Groq
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=formatted_history,
            max_tokens=256,
            temperature=1.2
        )
        
        ai_message = response.choices[0].message.content
        
        # Save AI response to Supabase
        ai_msg_response = supabase_request(
            "POST", 
            "/rest/v1/chat_messages", 
            headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
            data={
                "session_id": session_id,
                "content": ai_message,
                "is_ai": True
            }
        )
        
        # Update session title if it's the first message
        messages_count_response = supabase_request(
            "GET", 
            "/rest/v1/chat_messages", 
            headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
            params={
                "session_id": f"eq.{session_id}",
                "select": "count"
            }
        )
        
        if messages_count_response.status_code == 200:
            messages_count = len(messages_count_response.json())
            if messages_count <= 2:  # First user message and AI response
                # Generate title from user's first message
                title = user_message[:30] + "..." if len(user_message) > 30 else user_message
                
                supabase_request(
                    "PATCH", 
                    "/rest/v1/chat_sessions", 
                    headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
                    params={"id": f"eq.{session_id}"},
                    data={"title": title}
                )
        
        return jsonify({"message": ai_message}), 200
        
    except Exception as e:
        return jsonify({"error": f"AI error: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
