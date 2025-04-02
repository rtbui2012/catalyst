import time
import logging
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, Response
from catalyst_web.services.chat_service import chat_service
import asyncio

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
        _ = chat_service.process_message(message, message_id)
        return jsonify({
            'event_url': '/chat/eventstream',
            'status': 'success',
            'message_id': message_id
        }), 201
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return jsonify({
            'error': 'Failed to process message',
            'message': str(e)
        }), 500

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


@chat_bp.route('/chat/eventstream', methods=['GET'])
def event_stream():
    try:
        logger.info("Starting event stream")
        return chat_service.poll_agent_events()
    except ValueError as e:
        logger.error(f"Token or domain error: {str(e)}")
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        logger.error(f"Eventstream error: {str(e)}")
        return jsonify({"error": str(e)}), 500

