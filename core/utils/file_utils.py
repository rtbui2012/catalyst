"""
File handling utilities for the Agentic Core.

This module provides utility functions for working with files and directories.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Union


def load_json_file(path: str) -> Dict[str, Any]:
    """
    Load JSON data from a file.
    
    Args:
        path: Path to the JSON file
        
    Returns:
        Dictionary containing the JSON data
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger = logging.getLogger('agentic.utils')
        logger.error(f"Error loading JSON file {path}: {str(e)}")
        return {}


def save_json_file(data: Union[Dict[str, Any], List[Any]], path: str) -> bool:
    """
    Save data to a JSON file.
    
    Args:
        data: Data to save
        path: Path where to save the JSON file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger = logging.getLogger('agentic.utils')
        logger.error(f"Error saving JSON file {path}: {str(e)}")
        return False


def ensure_directory_exists(path: str) -> None:
    """
    Ensure that a directory exists, creating it if necessary.
    
    Args:
        path: Path to the directory
    """
    os.makedirs(path, exist_ok=True)