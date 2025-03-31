"""
Chat-related routes for the Catalyst Web UI.

This module handles message processing and integration with
the Catalyst core agent. Chat history is now managed client-side.
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
    message_id = data.get('messageId')
    conversation_history = data.get('conversation_history', [])
    
    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    try:
        # Process the message using the chat service
        response = chat_service.process_message(message, message_id)
        
        # Generate a conversation title if we have enough context now
        if len(conversation_history) > 0:
            # Add the current message to conversation history for title generation
            conversation_with_new_msg = conversation_history + [
                {'sender': 'user', 'content': message},
                {'sender': 'assistant', 'content': response['content']}
            ]
            
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return jsonify({
            'error': 'Failed to process message',
            'message': str(e)
        }), 500

@chat_bp.route('/chat/stream')
def stream():
    """
    Stream chat responses using Server-Sent Events (SSE).
    This endpoint will be implemented for streaming responses from the core agent.
    """
    def generate():
        # Send a connected status message
        yield "data: " + jsonify({'status': 'connected', 'message': 'SSE connection established'}).data.decode('utf-8') + "\n\n"
        
        # In the future, this will stream responses from the chat service
        for chunk in chat_service.stream_response("Test streaming message"):
            yield "data: " + jsonify(chunk).data.decode('utf-8') + "\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@chat_bp.route('/chat/generate_title', methods=['POST'])
def generate_title():
    """Generate a title for a conversation based on its content."""

    data = request.json

    if not data:
        logger.warning("No conversation history or message provided for title generation")
        return jsonify({
            'title': 'Unknown Conversation',
            'icon': '💬'
        })
    
    try:
        # Generate a title based on the conversation history
        title_data = chat_service.generate_conversation_title(data)
        logger.info(f"Generated title: {title_data.get('title', 'unknown')}")
        return jsonify(title_data)
        
    except Exception as e:
        logger.error(f"Error generating conversation title: {str(e)}")
        return jsonify({
            'error': 'Failed to generate title',
            'message': str(e),
            'title': 'Unknown Topic',
            'icon': '❓'
        }), 500