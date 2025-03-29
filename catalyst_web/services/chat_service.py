"""
Chat service module for Catalyst Web UI.

This module provides integration with the Catalyst core for processing chat messages.
"""

import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add the catalyst_agent package to the Python path
import os

from catalyst_agent import AgentCore, AgentConfig
   
logger = logging.getLogger(__name__)

class ChatService:
    """Service for handling chat interactions."""
    
    def __init__(self):
        """Initialize the chat service."""
        self.agent = None
        self.sessions = {}
        
        # Initialize the Catalyst Core agent if available
        try:
            logger.info("Initializing Catalyst Core agent")
            config = AgentConfig()
            self.agent = AgentCore(config)
        except Exception as e:
            logger.error(f"Failed to initialize Catalyst Core agent: {str(e)}")
    
    def get_or_create_session(self, user_id: str) -> Dict:
        """Get an existing session or create a new one."""
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                'id': str(uuid.uuid4()),
                'created_at': datetime.now().isoformat(),
                'messages': []
            }
        
        return self.sessions[user_id]
    
    def add_message(self, user_id: str, sender: str, content: str) -> Dict:
        """Add a message to a user's session."""
        session = self.get_or_create_session(user_id)
        
        message = {
            'id': str(uuid.uuid4()),
            'sender': sender,
            'content': content,
            'timestamp': datetime.now().isoformat()
        }
        
        session['messages'].append(message)
        return message
    
    def get_message_history(self, user_id: str) -> List[Dict]:
        """Get the message history for a user."""
        session = self.get_or_create_session(user_id)
        return session['messages']
    
    def clear_history(self, user_id: str) -> None:
        """Clear the message history for a user."""
        if user_id in self.sessions:
            self.sessions[user_id]['messages'] = []
    
    def process_message(self, user_id: str, message_content: str) -> Dict:
        """Process a user message and generate a response."""
        # Add the user message to history
        user_message = self.add_message(user_id, 'user', message_content)
        
        # Use the Catalyst Core agent if available
        if self.agent:
            try:
                logger.info(f"Processing message with Catalyst Core: {message_content[:50]}...")
                response_content = self.agent.process_message(message_content)
                
                # Fallback if the response is empty
                if not response_content:
                    response_content = "I processed your message but couldn't generate a response."
            except Exception as e:
                logger.error(f"Error getting response from Catalyst Core: {str(e)}")
                response_content = "I'm having trouble processing your request right now."
        else:
            # Mock response when core agent is not available
            logger.info(f"Processing message with mock response: {message_content[:50]}...")
            
            # Simple response logic based on user message
            if any(greeting in message_content.lower() for greeting in ['hello', 'hi', 'hey']):
                response_content = "Hello! How can I assist you today?"
            elif 'help' in message_content.lower():
                response_content = "I'm Catalyst AI, your intelligent assistant. You can ask me questions, and I'll do my best to help!"
            elif '?' in message_content:
                response_content = "That's an interesting question. When fully integrated with the Catalyst Core, I'll provide detailed answers."
            else:
                response_content = "I received your message. Once fully integrated with the Catalyst Core, I'll process this more intelligently."
        
        # Add the response to history
        assistant_message = self.add_message(user_id, 'assistant', response_content)
        assistant_message['reference_id'] = user_message['id']  # Link the response to the user message
        
        return assistant_message
    
    def stream_response(self, user_id: str, message_content: str):
        """Stream a response for a user message (to be implemented with SSE)."""
        # This method will be implemented in the future for streaming responses
        if self.agent and hasattr(self.agent, 'stream_response'):
            # In the future, this will stream from the core agent
            yield {'type': 'status', 'content': 'Thinking...'}
            yield {'type': 'content', 'content': 'This is a streamed response.'}
            yield {'type': 'end', 'content': 'Done'}
        else:
            # Mock streaming for now
            yield {'type': 'status', 'content': 'Connected'}
            yield {'type': 'content', 'content': 'Streaming will be available in the future.'}
            yield {'type': 'end', 'content': 'Done'}


# Create a singleton instance
chat_service = ChatService()