"""
Chat service module for Catalyst Web UI.

This module provides integration with the Catalyst core for processing chat messages.
"""

import logging
import time
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from flask import Response

# Add the catalyst_agent package to the Python path
import os

from catalyst_agent import AgentCore, AgentConfig
from openai import AzureOpenAI  

logger = logging.getLogger(__name__)

class ChatService:
    """Service for handling chat interactions."""
    
    def __init__(self, agent: Optional[AgentCore] = None):
        """Initialize the chat service."""
        self.agent = agent
        self.openai_client = None
        
        # Initialize the Azure OpenAI client if credentials are available
        try:
            logger.info("Initializing Azure OpenAI client")
            self.openai_client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("OPENAI_API_VERSION", "2025-01-01-preview"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI client: {str(e)}")
        
        # Initialize the Catalyst Core agent if available
        try:
            logger.info("Initializing Catalyst Core agent")
            config = AgentConfig(blob_storage_path="./blob_storage")
            self.agent = AgentCore(config)
        except Exception as e:
            logger.error(f"Failed to initialize Catalyst Core agent: {str(e)}")
    
    def process_message(self, message_content: str, message_id: str = None) -> Dict:
        """Process a user message and return a response."""

        logger.info(f"Processing message with Catalyst Core: {message_content[:50]}...")
        content = self.agent.process_message(message_content)

        self.agent.event_queue.add_final_solution(
            solution=content,
            metadata={
                "message_id": message_id
            }
        )
    
    def generate_conversation_title(self, conversation_history: List[Dict]) -> Dict:
        """Generate a title for the conversation using Azure OpenAI."""

        if not self.openai_client:
            # Fallback if OpenAI client is not available
            return {
                'title': conversation_history[0].get('content', 'Unknown Topic')[:20],
                'icon': '❓'
            }
            
        try:
            # Extract the conversation text to feed to the model
            conversation_text = ""
            for msg in conversation_history[:5]:  # Limit to first 5 messages to keep it focused
                sender = "User" if msg.get('sender') == 'user' else "Assistant"
                content = msg.get('content', '')[:100]  # Truncate long messages
                conversation_text += f"{sender}: {content}\n"
            
            logger.info("Generating conversation title with Azure OpenAI")
            
            # Create the prompt for title generation
            prompt = [
                {
                    "role": "system", 
                    "content": (
                        "Generate a creative, short, and clever title with a relevant emoji icon for "
                        "a conversation. The title should be very concise (4-6 words max) and capture the "
                        "essence or topic of the conversation. The emoji should be relevant to the title theme. "
                        "Return ONLY a JSON object with 'title' and 'icon' keys. Example: "
                        "{'title': 'Travel Plans for Summer', 'icon': '✈️'}"
                    )
                },
                {
                    "role": "user",
                    "content": f"Based on this conversation, generate a title and icon:\n\n{conversation_text}"
                }
            ]
            
            # Call the Azure OpenAI model with a smaller title-specific deployment
            response = self.openai_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME_FOR_TITLE", "gpt-4o-mini"),
                messages=prompt,
                temperature=0.7,
                max_tokens=100,
                response_format={"type": "json_object"}
            )
            
            # Extract and parse the JSON response
            title_data = json.loads(response.choices[0].message.content)
            
            # Ensure we have valid title data with fallbacks
            title = title_data.get('title', 'Unknown Topic')[:50]
            icon = title_data.get('icon', '❓')  
                      
            logger.info(f"Generated title: {icon} {title}")
            
            return {
                'title': title,
                'icon': icon
            }
            
        except Exception as e:
            logger.error(f"Error generating conversation title: {str(e)}")
            # Return a default title if generation fails
            return {
                'title': 'Unknown Topic',
                'icon': '❓'
            }
    
    def poll_agent_events(self):
        """Stream a response for a user message (to be implemented with SSE)."""
    
        def generate():
            """Generator function to yield events from the chat service."""
            try:
                event = self.agent.event_queue.queue.get().to_json()
            except IndexError:
                event = None
        
            if event:
                yield f"data: {event}\n\n"
            else:
                time.sleep(.01) 

        return Response(generate(), mimetype='text/event-stream')

# Create a singleton instance
agent_core = AgentCore(AgentConfig(blob_storage_path="./blob_storage"))
chat_service = ChatService(agent=agent_core)