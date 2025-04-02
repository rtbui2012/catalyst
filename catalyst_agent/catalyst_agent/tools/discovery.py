"""
Utility functions for tools discovery and management.

This module provides functions for discovering and loading tools from
the tools package.
"""

import os
import importlib
import inspect
import logging
from typing import Dict, Type

from ..utils import setup_logger
from .base import Tool


def discover_tools() -> Dict[str, Type[Tool]]:
    """
    Discover available tool classes in the tools package.
    
    This function scans the tools directory and finds all classes that
    inherit from the Tool base class.
    
    Returns:
        Dictionary mapping tool class names to the tool classes
    """
    logger = setup_logger('agentic.tools.discovery')
    tool_classes = {}
    
    # Get the directory containing the tools
    tools_dir = os.path.dirname(__file__)
    logger.info(f"Discovering tools in {tools_dir}")
    
    # Get a list of all Python files in the tools directory (excluding __init__.py and base.py)
    tool_files = [f[:-3] for f in os.listdir(tools_dir) 
                 if f.endswith('.py') and f != '__init__.py' and f != 'base.py' and f != 'discovery.py']
    
    for file_name in tool_files:
        try:
            # Import the module dynamically
            module_name = f".{file_name}"
            module = importlib.import_module(module_name, package="catalyst_agent.catalyst_agent.tools")
            
            # Find all Tool subclasses in the module
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, Tool) and 
                    obj != Tool and  # Skip the base Tool class itself
                    obj.__module__ == module.__name__):
                    tool_classes[name] = obj
                    logger.info(f"Discovered tool class: {name}")
        except Exception as e:
            logger.error(f"Error discovering tools in {file_name}: {str(e)}")
    
    return tool_classes


def instantiate_tool(tool_class: Type[Tool], event_queue=None, **kwargs) -> Tool:
    """
    Instantiate a tool from its class.
    
    Args:
        tool_class: The tool class to instantiate
        **kwargs: Additional arguments to pass to the tool constructor
    
    Returns:
        An instance of the tool
    """
    try:
        return tool_class(event_queue=event_queue, **kwargs)
    except Exception as e:
        logger = setup_logger('agentic.tools.discovery')
        logger.error(f"Error instantiating tool {tool_class.__name__}: {str(e)}")
        raise