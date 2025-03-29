"""
Memory implementation classes for the Agentic Core.

This module provides concrete implementations of the memory interfaces
defined in the base module.
"""

import json
from typing import Dict, List, Optional, Any, Union

from .base import Memory, MemoryEntry, MessageEntry, ExecutionEntry


class ShortTermMemory(Memory):
    """
    Memory for recent interactions and execution steps.
    
    This memory has limited capacity and follows a FIFO (First In, First Out) approach.
    """
    
    def __init__(self, capacity: int = 10):
        """
        Initialize short-term memory.
        
        Args:
            capacity: Maximum number of entries to keep
        """
        self.capacity = capacity
        self.entries: List[MemoryEntry] = []
        self.entry_map: Dict[str, MemoryEntry] = {}  # For quick lookup by ID
    
    def add(self, entry: MemoryEntry) -> None:
        """Add an entry to short-term memory, removing oldest entries if at capacity."""
        # Add to entries list and map
        self.entries.append(entry)
        self.entry_map[entry.id] = entry
        
        # Remove oldest entries if we exceed capacity
        while len(self.entries) > self.capacity:
            oldest = self.entries.pop(0)
            del self.entry_map[oldest.id]
    
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get a specific entry by ID."""
        return self.entry_map.get(entry_id)
    
    def search(self, query: Dict[str, Any]) -> List[MemoryEntry]:
        """Search for entries matching the query criteria."""
        results = []
        
        for entry in self.entries:
            match = True
            for key, value in query.items():
                # Check if the entry matches all query conditions
                if key == "entry_type" and entry.entry_type != value:
                    match = False
                    break
                elif key == "sender" and getattr(entry, "sender", None) != value:
                    match = False
                    break
                elif key == "status" and getattr(entry, "status", None) != value:
                    match = False
                    break
                elif key == "content" and value not in str(entry.content):
                    match = False
                    break
                elif key in entry.metadata and entry.metadata[key] != value:
                    match = False
                    break
                elif key not in entry.metadata and key not in ["entry_type", "sender", "status", "content"]:
                    match = False
                    break
            
            if match:
                results.append(entry)
        
        return results
    
    def clear(self) -> None:
        """Clear all entries from short-term memory."""
        self.entries.clear()
        self.entry_map.clear()
    
    def get_recent(self, limit: Optional[int] = None) -> List[MemoryEntry]:
        """
        Get the most recent entries.
        
        Args:
            limit: Maximum number of entries to return (default: all entries)
            
        Returns:
            List of recent memory entries
        """
        if limit is None or limit >= len(self.entries):
            return list(self.entries)
        return self.entries[-limit:]


class LongTermMemory(Memory):
    """
    Persistent memory for storing important information over time.
    
    This memory has unlimited capacity and persists between sessions.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize long-term memory.
        
        Args:
            storage_path: Path to the file for persisting memory (optional)
        """
        self.storage_path = storage_path
        self.entries: Dict[str, MemoryEntry] = {}
        
        # Load from storage if path is provided
        if storage_path:
            try:
                self._load_from_storage()
            except FileNotFoundError:
                # File doesn't exist yet, will be created on first save
                pass
    
    def add(self, entry: MemoryEntry) -> None:
        """Add an entry to long-term memory."""
        self.entries[entry.id] = entry
        
        # Persist to storage if path is provided
        if self.storage_path:
            self._save_to_storage()
    
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get a specific entry by ID."""
        return self.entries.get(entry_id)
    
    def search(self, query: Dict[str, Any]) -> List[MemoryEntry]:
        """Search for entries matching the query criteria."""
        results = []
        
        for entry in self.entries.values():
            match = True
            for key, value in query.items():
                # Check if the entry matches all query conditions
                if key == "entry_type" and entry.entry_type != value:
                    match = False
                    break
                elif key == "sender" and getattr(entry, "sender", None) != value:
                    match = False
                    break
                elif key == "status" and getattr(entry, "status", None) != value:
                    match = False
                    break
                elif key == "content" and value not in str(entry.content):
                    match = False
                    break
                elif key in entry.metadata and entry.metadata[key] != value:
                    match = False
                    break
                elif key not in entry.metadata and key not in ["entry_type", "sender", "status", "content"]:
                    match = False
                    break
            
            if match:
                results.append(entry)
        
        return results
    
    def clear(self) -> None:
        """Clear all entries from long-term memory."""
        self.entries.clear()
        
        # Persist empty state to storage if path is provided
        if self.storage_path:
            self._save_to_storage()
    
    def _save_to_storage(self) -> None:
        """Save memory entries to persistent storage."""
        if not self.storage_path:
            return
        
        # Convert entries to dictionaries
        serialized_entries = {
            entry_id: self._serialize_entry(entry)
            for entry_id, entry in self.entries.items()
        }
        
        # Write to file
        with open(self.storage_path, 'w') as f:
            json.dump(serialized_entries, f, indent=2)
    
    def _load_from_storage(self) -> None:
        """Load memory entries from persistent storage."""
        if not self.storage_path:
            return
        
        # Read from file
        with open(self.storage_path, 'r') as f:
            serialized_entries = json.load(f)
        
        # Convert dictionaries to entries
        self.entries = {
            entry_id: self._deserialize_entry(entry_data)
            for entry_id, entry_data in serialized_entries.items()
        }
    
    def _serialize_entry(self, entry: MemoryEntry) -> Dict[str, Any]:
        """Convert a memory entry to a serializable dictionary."""
        return entry.to_dict()
    
    def _deserialize_entry(self, data: Dict[str, Any]) -> MemoryEntry:
        """Create a memory entry from a dictionary."""
        entry_type = data["entry_type"]
        
        if entry_type == "message":
            return MessageEntry.from_dict(data)
        elif entry_type == "execution":
            return ExecutionEntry.from_dict(data)
        else:
            return MemoryEntry.from_dict(data)