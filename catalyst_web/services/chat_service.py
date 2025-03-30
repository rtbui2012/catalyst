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
        
        # Initialize the Catalyst Core agent if available
        try:
            logger.info("Initializing Catalyst Core agent")
            config = AgentConfig()
            self.agent = AgentCore(config)
        except Exception as e:
            logger.error(f"Failed to initialize Catalyst Core agent: {str(e)}")
    
    def process_message(self, message_content: str, message_id: str = None) -> Dict:
        """Process a user message and generate a response.
        
        This is now stateless and doesn't maintain conversation history server-side,
        as history is managed in the client's local storage.
        
        Args:
            message_content: The content of the user's message
            message_id: Optional ID of the message, used for referencing edited messages
            
        Returns:
            Dict containing the response message
        """
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
        
        # Create a response with a unique ID and reference to the original message
        response = {
            'id': str(uuid.uuid4()),
            'sender': 'assistant',
            'content': response_content,
            'timestamp': datetime.now().isoformat()
        }
        
        # If a message_id was provided, reference it
        if message_id:
            response['reference_id'] = message_id
        
        return response
    
    def stream_response(self, message_content: str):
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