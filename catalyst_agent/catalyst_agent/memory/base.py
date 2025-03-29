"""
Core memory abstractions for the Agentic Core.

This module provides base classes for storing and retrieving the agent's
experiences, conversations, and execution outcomes.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid


class MemoryEntry:
    """Base class for items stored in agent memory."""
    
    def __init__(self, content: Any, entry_type: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a memory entry.
        
        Args:
            content: The main content of the memory entry
            entry_type: Type of memory entry (e.g., "message", "execution", "observation")
            metadata: Additional information about the entry
        """
        self.id = str(uuid.uuid4())
        self.timestamp = datetime.now().isoformat()
        self.content = content
        self.entry_type = entry_type
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the memory entry to a dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "content": self.content,
            "entry_type": self.entry_type,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        """Create a memory entry from a dictionary."""
        entry = cls(
            content=data["content"],
            entry_type=data["entry_type"],
            metadata=data.get("metadata", {})
        )
        entry.id = data["id"]
        entry.timestamp = data["timestamp"]
        return entry


class MessageEntry(MemoryEntry):
    """Memory entry for messages/requests received by the agent."""
    
    def __init__(self, content: str, sender: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a message entry.
        
        Args:
            content: The message text
            sender: The sender of the message (e.g., "user", "system", "agent")
            metadata: Additional information about the message
        """
        super().__init__(content, "message", metadata)
        self.sender = sender
        self.metadata["sender"] = sender
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageEntry':
        """Create a message entry from a dictionary."""
        entry = super().from_dict(data)
        entry.sender = data.get("metadata", {}).get("sender", "unknown")
        return entry


class ExecutionEntry(MemoryEntry):
    """Memory entry for execution steps performed by the agent."""
    
    def __init__(
        self, 
        action: str, 
        status: str,
        result: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize an execution entry.
        
        Args:
            action: The action performed
            status: Status of the execution (e.g., "started", "completed", "failed")
            result: Result of the execution if available
            metadata: Additional information about the execution
        """
        super().__init__(action, "execution", metadata)
        self.status = status
        self.result = result
        self.metadata["status"] = status
        if result is not None:
            self.metadata["result"] = str(result)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionEntry':
        """Create an execution entry from a dictionary."""
        entry = super().from_dict(data)
        entry.status = data.get("metadata", {}).get("status", "unknown")
        entry.result = data.get("metadata", {}).get("result")
        return entry


class Memory(ABC):
    """Abstract base class for agent memory implementations."""
    
    @abstractmethod
    def add(self, entry: MemoryEntry) -> None:
        """
        Add an entry to memory.
        
        Args:
            entry: The memory entry to add
        """
        pass
    
    @abstractmethod
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """
        Retrieve a specific memory entry by ID.
        
        Args:
            entry_id: ID of the entry to retrieve
            
        Returns:
            The memory entry if found, None otherwise
        """
        pass
    
    @abstractmethod
    def search(self, query: Dict[str, Any]) -> List[MemoryEntry]:
        """
        Search for memory entries matching the query criteria.
        
        Args:
            query: Dictionary of search criteria
            
        Returns:
            List of memory entries matching the criteria
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all entries from memory."""
        pass