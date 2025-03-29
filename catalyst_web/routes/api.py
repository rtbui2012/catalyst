"""
API routes for the Catalyst Web UI.

This module provides API endpoints for integrating with external services
and for future expansion of functionality.
"""

import sys
import logging
import json
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app as app

# Import the Catalyst core components
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

try:
    from core.agent import AgentCore
    from core.tools.web_search import WebSearchTool
    from core.tools.image_generation import ImageGenerationTool
except ImportError:
    # If we can't import the core module, create mock functionality
    AgentCore = None
    WebSearchTool = None
    ImageGenerationTool = None

# Create blueprint
api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

@api_bp.route('/status', methods=['GET'])
def api_status():
    """Get the API status."""
    core_status = "available" if AgentCore else "unavailable"
    
    return jsonify({
        'status': 'online',
        'version': '0.1.0',
        'services': {
            'core': core_status,
            'chat': 'available',
            'authentication': 'available'
        }
    })

@api_bp.route('/chat/message', methods=['POST'])
def api_message():
    """Process a message via the API."""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
        
    data = request.get_json()
    
    if 'message' not in data:
        return jsonify({'error': 'Message is required'}), 400
    
    message = data['message']
    session_id = data.get('session_id', 'api-user')
    
    # In a production app, we would use the Catalyst core agent here
    # For now, return a simple response
    
    return jsonify({
        'response': f"API received: {message}",
        'session_id': session_id,
        'status': 'success'
    })

@api_bp.route('/tools', methods=['GET'])
def list_tools():
    """Get a list of available tools."""
    # List available tools, with indication of which ones are actually available
    tools = [
        {
            'id': 'web_search',
            'name': 'Web Search',
            'description': 'Search the web for information',
            'available': WebSearchTool is not None
        },
        {
            'id': 'image_generation',
            'name': 'Image Generation',
            'description': 'Generate images based on text descriptions',
            'available': ImageGenerationTool is not None
        },
        {
            'id': 'code_execution',
            'name': 'Code Execution',
            'description': 'Execute Python code',
            'available': AgentCore is not None
        }
    ]
    
    return jsonify({'tools': tools})

@api_bp.route('/tools/<tool_id>', methods=['POST'])
def use_tool(tool_id):
    """
    Use a specific tool via the API.
    This allows direct access to tools without going through the chat interface.
    """
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
        
    data = request.get_json()
    
    # Mock response since we don't have actual tool execution yet
    return jsonify({
        'tool_id': tool_id,
        'status': 'success',
        'result': f"Tool {tool_id} would process: {json.dumps(data)}",
        'message': 'Tool execution will be implemented with Catalyst Core integration'
    })

@api_bp.route('/stream/start', methods=['POST'])
def start_stream():
    """
    Start a streaming session.
    In the future, this will initialize a streaming connection to the core agent.
    """
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
        
    data = request.get_json()
    session_id = data.get('session_id', str(hash(request.remote_addr)))
    
    return jsonify({
        'session_id': session_id,
        'status': 'started',
        'stream_url': f"/api/stream/{session_id}"
    })

@api_bp.route('/integration/<service>', methods=['GET', 'POST'])
def service_integration(service):
    """
    Integration point for external services.
    This can be expanded in the future to support various integrations.
    """
    valid_services = ['slack', 'discord', 'teams', 'webhook']
    
    if service not in valid_services:
        return jsonify({'error': 'Unsupported service', 'valid_services': valid_services}), 404
    
    if request.method == 'POST':
        # Process integration data
        data = request.get_json() if request.is_json else {}
        logger.info(f"Received integration request for {service}: {data}")
        return jsonify({'status': 'received', 'service': service})
    else:
        # Return integration info
        return jsonify({
            'service': service,
            'status': 'available',
            'documentation': f'/api/docs/integration/{service}'
        })