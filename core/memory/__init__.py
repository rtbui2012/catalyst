"""
Memory interfaces and implementations for the Agentic Core.

This module provides memory abstractions for storing and retrieving
the agent's experiences, conversations, and execution outcomes.
"""

# Import base memory classes
from .base import MemoryEntry, MessageEntry, ExecutionEntry, Memory

# Import memory implementations
from .implementations import ShortTermMemory, LongTermMemory

# Import memory manager
from .manager import MemoryManager

__all__ = [
    # Base classes
    'MemoryEntry',
    'MessageEntry',
    'ExecutionEntry',
    'Memory',
    
    # Implementation classes
    'ShortTermMemory',
    'LongTermMemory',
    
    # Manager
    'MemoryManager'
]