"""
Agentic Core Module - The central component of the agentic AI system.

This module provides the core functionality for an agentic AI system that can:
- Receive and analyze messages/requests
- Plan execution steps to accomplish tasks
- Discover and utilize available tools
- Maintain memory of past interactions and execution steps
- Evaluate if a request can be accomplished with available tools
"""

from .agent import AgentCore
from .config import AgentConfig

__all__ = ["AgentCore", "AgentConfig"]