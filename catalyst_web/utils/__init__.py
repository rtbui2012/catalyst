"""
Utility functions for the Catalyst Web UI.

This module provides utility functions and helpers for the Flask application.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from functools import wraps
from flask import request, jsonify, current_app, session

# Configure logger
logger = logging.getLogger(__name__)

def setup_logging(app):
    """Configure logging for the application."""
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
    log_format = app.config.get('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format
    )
    
    # Log application startup
    logger.info(f"Starting Catalyst Web UI in {app.config.get('ENV')} mode")

def is_valid_email(email):
    """Check if an email address is valid."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def format_datetime(dt, format_str='%Y-%m-%d %H:%M:%S'):
    """Format a datetime object as a string."""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            return dt
    
    if isinstance(dt, datetime):
        return dt.strftime(format_str)
    
    return str(dt)

def sanitize_input(text):
    """Sanitize user input to prevent XSS attacks."""
    if not text:
        return ""
    
    # Replace potentially harmful characters
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    return text

def api_required(f):
    """Decorator to ensure the request has valid API credentials."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the API key from the header or query parameter
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        
        if not api_key:
            return jsonify({'error': 'API key is required'}), 401
        
        # In a real application, you would validate the API key against a database
        # This is a simple demonstration
        if api_key != 'demo-api-key':
            return jsonify({'error': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

def login_required(f):
    """Decorator to ensure the user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            # For API requests, return a JSON response
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Authentication required'}), 401
                
            # For web requests, store the original URL and redirect to login
            return current_app.login_manager.unauthorized()
        
        return f(*args, **kwargs)
    
    return decorated_function

def measure_execution_time(func):
    """Decorator to measure the execution time of a function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        logger.debug(f"Function {func.__name__} executed in {execution_time:.4f} seconds")
        
        return result
    
    return wrapper

def create_directory_if_not_exists(directory_path):
    """Create a directory if it doesn't exist."""
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
        logger.info(f"Created directory: {directory_path}")

def load_json_file(file_path):
    """Load a JSON file and return its contents."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading JSON file {file_path}: {str(e)}")
        return None

def save_json_file(data, file_path):
    """Save data to a JSON file."""
    try:
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"Error saving JSON file {file_path}: {str(e)}")
        return False