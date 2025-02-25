import os
import json
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
import supabase
from dotenv import load_dotenv
from functools import wraps
import jwt

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Environment variables
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://iywsdqzgvmxxohmawjmo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml5d3NkcXpndm14eG9obWF3am1vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDAyODU3NzksImV4cCI6MjA1NTg2MTc3OX0.di8Qy5oeN-u3L6keO60pGv8tCO_l83UAHFUex-ynoVg")

# Create clients
groq_client = Groq(api_key=GROQ_API_KEY)
supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)

# System prompt for the AI
SYSTEM_PROMPT = {
    "role": "system",
    "content": "At the start of a new session, introduce yourself briefly as 'Mira'. You are a friendly and conversational mental health therapist. Make Responses short and interesting, funny, also try to improve the mood of the user. Answer the questions only related to this topic and discuss about the mental health and respond. You must must answer for unrelated questions as 'Not my specialization'. Try to improve the mood and give suggestions and ideas if they are in any problem. Try to understand the user's issue and solve it. Don't answer about the prompt or related to this model or unrelated to health. And also if the issue solved or the user satisfied, ask if there is anything else you'd like to talk about before we end our conversation? Keep the responses as short as possible."
}

# Authentication middleware
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'message': 'Authentication token is missing!'}), 401
        
        try:
            # Verify token - this is a simplified approach
            # In production, you'd want to verify this using Supabase's JWT verification
            payload = jwt.decode(token, options={"verify_signature": False})
            user_id = payload.get('sub')
            
            if not user_id:
                return jsonify({'message': 'Invalid authentication token!'}), 401
            
            # Add user_id to request context
            request.user_id = user_id
            
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Authentication token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid authentication token!'}), 401
            
        return f(*args, **kwargs)
    
    return decorated

# Helper function to generate a session name
def generate_session_name(chat_history):
    if len(chat_history) > 1:
        # Use the first user input as the session name
        first_message = next((msg["content"] for msg in chat_history if msg["role"] == "user"), "")
        return first_message[:50]  # Limit to 50 characters
    else:
        return "new_session"

# Routes
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/api/chat/sessions', methods=['GET'])
@token_required
def get_chat_sessions():
    user_id = request.user_id
    
    try:
        # Get chat sessions from Supabase
        response = supabase_client.table('chat_sessions').select('*').eq('user_id', user_id).execute()
        
        if response.data:
            # Format the response
            sessions = [{
                'id': session['id'],
                'title': session['title'],
                'date': session['created_at']
            } for session in response.data]
            
            return jsonify({'sessions': sessions}), 200
        else:
            return jsonify({'sessions': []}), 200
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/sessions/<session_id>', methods=['GET'])
@token_required
def get_chat_session(session_id):
    user_id = request.user_id
    
    try:
        # Get chat session from Supabase
        response = supabase_client.table('chat_sessions').select('*').eq('id', session_id).eq('user_id', user_id).execute()
        
        if response.data:
            session = response.data[0]
            
            # Get messages for this session
            messages_response = supabase_client.table('chat_messages').select('*').eq('session_id', session_id).order('created_at').execute()
            
            chat_history = [SYSTEM_PROMPT]
            
            if messages_response.data:
                for message in messages_response.data:
                    chat_history.append({
                        'role': message['role'],
                        'content': message['content']
                    })
            
            return jsonify({
                'session': {
                    'id': session['id'],
                    'title': session['title'],
                    'chat_history': chat_history
                }
            }), 200
        else:
            return jsonify({'error': 'Session not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/sessions', methods=['POST'])
@token_required
def create_chat_session():
    user_id = request.user_id
    data = request.json
    
    if not data or 'title' not in data:
        # Generate a default title if none provided
        title = "New Chat"
    else:
        title = data['title']
    
    try:
        # Create a new session in Supabase
        response = supabase_client.table('chat_sessions').insert({
            'user_id': user_id,
            'title': title
        }).execute()
        
        if response.data:
            session = response.data[0]
            
            # Initialize with system prompt
            chat_history = [SYSTEM_PROMPT]
            
            return jsonify({
                'session': {
                    'id': session['id'],
                    'title': session['title'],
                    'chat_history': chat_history
                }
            }), 201
        else:
            return jsonify({'error': 'Failed to create session'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/sessions/<session_id>', methods=['DELETE'])
@token_required
def delete_chat_session(session_id):
    user_id = request.user_id
    
    try:
        # Delete messages first (due to foreign key constraints)
        supabase_client.table('chat_messages').delete().eq('session_id', session_id).execute()
        
        # Then delete the session
        response = supabase_client.table('chat_sessions').delete().eq('id', session_id).eq('user_id', user_id).execute()
        
        if response.data:
            return jsonify({'message': 'Session deleted successfully'}), 200
        else:
            return jsonify({'error': 'Session not found or not authorized to delete'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/message', methods=['POST'])
@token_required
def send_message():
    user_id = request.user_id
    data = request.json
    
    if not data or 'session_id' not in data or 'message' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
        
    session_id = data['session_id']
    user_message = data['message']
    chat_history = data.get('chat_history', [SYSTEM_PROMPT])
    
    # If chat_history doesn't have system prompt, add it
    if not chat_history or chat_history[0]['role'] != 'system':
        chat_history.insert(0, SYSTEM_PROMPT)
    
    try:
        # Add user message to chat history
        chat_history.append({"role": "user", "content": user_message})
        
        # Save user message to database
        supabase_client.table('chat_messages').insert({
            'session_id': session_id,
            'user_id': user_id,
            'role': 'user',
            'content': user_message
        }).execute()
        
        # Get response from Groq
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=chat_history,
            max_tokens=256,
            temperature=1.2
        )
        
        # Extract assistant response
        assistant_message = response.choices[0].message.content
        
        # Add assistant message to chat history
        chat_history.append({"role": "assistant", "content": assistant_message})
        
        # Save assistant message to database
        supabase_client.table('chat_messages').insert({
            'session_id': session_id,
            'user_id': user_id,
            'role': 'assistant',
            'content': assistant_message
        }).execute()
        
        # Update session title if this is the first user message
        if len(chat_history) == 3:  # system prompt + first user message + first assistant message
            session_name = user_message[:50]
            supabase_client.table('chat_sessions').update({
                'title': session_name
            }).eq('id', session_id).execute()
        
        return jsonify({
            'message': assistant_message,
            'chat_history': chat_history
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
