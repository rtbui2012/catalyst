#!/usr/bin/env python
"""
Catalyst Web UI - Flask application for the Catalyst AI chatbot interface

This module provides a web interface for interacting with the Catalyst AI agent.
It handles user authentication, chat sessions, and integration with the Catalyst
core module.
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, session, Response
from flask_cors import CORS
from dotenv import load_dotenv

# Add the parent directory to sys.path to make core module imports work
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.secret_key = os.environ.get('SECRET_KEY', 'catalyst-dev-key-change-in-production')
app.config['JSON_SORT_KEYS'] = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import routes after app initialization to avoid circular imports
from routes.auth import auth_bp
from routes.chat import chat_bp
from routes.api import api_bp

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(api_bp, url_prefix='/api')

@app.route('/')
def index():
    """Render the main index page"""
    return render_template('index.html')

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    logger.error(f"Server error: {str(e)}")
    return render_template('500.html'), 500

@app.context_processor
def inject_now():
    """Inject current time into templates."""
    return {'now': datetime.utcnow()}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    
    logger.info(f"Starting Catalyst Web UI on port {port} (debug={debug})")
    app.run(host='0.0.0.0', port=port, debug=debug)