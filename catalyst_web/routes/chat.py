"""
Chat-related routes for the Catalyst Web UI.

This module handles chat sessions, message processing, and integration with
the Catalyst core agent.
"""

import logging
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, Response
from services.chat_service import chat_service

# Create blueprint
chat_bp = Blueprint('chat', __name__)
logger = logging.getLogger(__name__)

@chat_bp.route('/chat')
def chat_page():
    """Render the main chat interface."""
    # Initialize chat session if it doesn't exist
    user = session.get('user', f'Guest-{uuid.uuid4().hex[:8]}')
    
    return render_template('chat.html', username=user)

@chat_bp.route('/chat/send', methods=['POST'])
def send_message():
    """Process a user message and get a response from the AI."""
    data = request.json
    message = data.get('message', '').strip()
    user = session.get('user', f'Guest-{uuid.uuid4().hex[:8]}')
    
    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    try:
        # Process the message using the chat service
        response = chat_service.process_message(user, message)
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return jsonify({
            'error': 'Failed to process message',
            'message': str(e)
        }), 500

@chat_bp.route('/chat/history')
def get_history():
    """Get the chat history for the current user."""
    user = session.get('user', f'Guest-{uuid.uuid4().hex[:8]}')
    
    # Get message history from the chat service
    history = chat_service.get_message_history(user)
    
    return jsonify(history)

@chat_bp.route('/chat/clear', methods=['POST'])
def clear_history():
    """Clear the chat history for the current user."""
    user = session.get('user', f'Guest-{uuid.uuid4().hex[:8]}')
    
    # Clear history using the chat service
    chat_service.clear_history(user)
    
    return jsonify({'status': 'success', 'message': 'Chat history cleared'})

@chat_bp.route('/chat/stream')
def stream():
    """
    Stream chat responses using Server-Sent Events (SSE).
    This endpoint will be implemented for streaming responses from the core agent.
    """
    def generate():
        user = session.get('user', f'Guest-{uuid.uuid4().hex[:8]}')
        
        # Send a connected status message
        yield "data: " + jsonify({'status': 'connected', 'message': 'SSE connection established'}).data.decode('utf-8') + "\n\n"
        
        # In the future, this will stream responses from the chat service
        for chunk in chat_service.stream_response(user, "Test streaming message"):
            yield "data: " + jsonify(chunk).data.decode('utf-8') + "\n\n"
    
    return Response(generate(), mimetype='text/event-stream')