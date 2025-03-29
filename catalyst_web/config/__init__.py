"""
Configuration module for the Catalyst Web UI.

This module provides configuration settings for the Flask application.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

class Config:
    """Base configuration class for the Catalyst Web UI."""
    
    # Load environment variables from .env file if it exists
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'catalyst-dev-key-change-in-production')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']
    TESTING = False
    
    # Server configuration
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds
    
    # API settings
    API_VERSION = 'v1'
    API_PREFIX = f'/api/{API_VERSION}'
    
    # Catalyst core integration
    CORE_ENABLED = os.environ.get('CORE_ENABLED', 'False').lower() in ['true', '1', 't']
    
    # Logging configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Static assets
    STATIC_FOLDER = 'static'
    TEMPLATES_FOLDER = 'templates'
    
    @staticmethod
    def init_app(app):
        """Initialize Flask application with this configuration."""
        pass


class DevelopmentConfig(Config):
    """Development configuration."""
    
    DEBUG = True
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        # Additional development-specific initialization


class TestingConfig(Config):
    """Testing configuration."""
    
    TESTING = True
    WTF_CSRF_ENABLED = False
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        # Additional testing-specific initialization


class ProductionConfig(Config):
    """Production configuration."""
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        # Additional production-specific initialization


# Dictionary of configuration environments
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

# Get the active configuration
def get_config():
    """Get the active configuration based on environment variables."""
    env = os.environ.get('FLASK_ENV', 'development').lower()
    return config.get(env, config['default'])