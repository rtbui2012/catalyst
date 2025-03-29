"""
Authentication-related routes for the Catalyst Web UI.

This module handles user authentication, registration, and account management.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import logging

# Create blueprint
auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if request.method == 'POST':
        # For API requests (JSON)
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            
            # In a real application, you would validate credentials against a database
            # For this demo, we'll accept any credentials
            session['user'] = username
            logger.info(f"User logged in via API: {username}")
            
            return jsonify({
                'status': 'success',
                'message': 'Login successful',
                'user': username
            })
        
        # For form submissions
        username = request.form.get('username')
        password = request.form.get('password')
        
        # In a real application, you would validate credentials against a database
        # For this demo, we'll accept any credentials
        session['user'] = username
        logger.info(f"User logged in: {username}")
        
        return redirect(url_for('chat.chat_page'))
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """Handle user logout."""
    user = session.pop('user', None)
    if user:
        logger.info(f"User logged out: {user}")
    
    # Handle API requests
    if request.headers.get('Accept') == 'application/json':
        return jsonify({
            'status': 'success',
            'message': 'Logged out successfully'
        })
    
    return redirect(url_for('index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration."""
    if request.method == 'POST':
        # For API requests (JSON)
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            email = data.get('email')
            
            # In a real application, you would save user info to a database
            logger.info(f"New user registered via API: {username}")
            
            return jsonify({
                'status': 'success',
                'message': 'Registration successful',
                'user': username
            })
        
        # For form submissions
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        
        # In a real application, you would save user info to a database
        logger.info(f"New user registered: {username}")
        
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')

@auth_bp.route('/profile')
def profile():
    """View and edit user profile."""
    user = session.get('user')
    if not user:
        return redirect(url_for('auth.login'))
    
    return render_template('profile.html', username=user)