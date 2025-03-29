"""
Memory management functionality for the Agentic Core.

This module provides the MemoryManager class that coordinates between
short-term and long-term memory systems.
"""

from typing import Dict, List, Optional, Any, Union

from .base import MemoryEntry, MessageEntry, ExecutionEntry
from .implementations import ShortTermMemory, LongTermMemory


class MemoryManager:
    """
    Manager class that coordinates between short-term and long-term memory.
    
    This class provides a unified interface for storing and retrieving memories.
    """
    
    def __init__(
        self, 
        short_term_capacity: int = 10,
        long_term_enabled: bool = True,
        long_term_storage_path: Optional[str] = None
    ):
        """
        Initialize the memory manager.
        
        Args:
            short_term_capacity: Maximum number of entries in short-term memory
            long_term_enabled: Whether to use long-term memory
            long_term_storage_path: Path for persisting long-term memory
        """
        self.short_term = ShortTermMemory(capacity=short_term_capacity)
        self.long_term_enabled = long_term_enabled
        
        if long_term_enabled:
            self.long_term = LongTermMemory(storage_path=long_term_storage_path)
        else:
            self.long_term = None
    
    def add(self, entry: MemoryEntry, important: bool = False) -> None:
        """
        Add an entry to memory.
        
        Args:
            entry: The memory entry to add
            important: Whether this is an important entry that should be stored
                       in long-term memory
        """
        # Always add to short-term memory
        self.short_term.add(entry)
        
        # Add to long-term memory if enabled and entry is important
        if self.long_term_enabled and important and self.long_term:
            self.long_term.add(entry)
    
    def add_message(
        self, 
        content: str, 
        sender: str, 
        important: bool = False, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> MessageEntry:
        """
        Add a message entry to memory.
        
        Args:
            content: The message text
            sender: The sender of the message
            important: Whether this is an important message
            metadata: Additional information about the message
            
        Returns:
            The created message entry
        """
        entry = MessageEntry(content=content, sender=sender, metadata=metadata)
        self.add(entry, important=important)
        return entry
    
    def add_execution(
        self,
        action: str,
        status: str,
        result: Optional[Any] = None,
        important: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExecutionEntry:
        """
        Add an execution entry to memory.
        
        Args:
            action: The action performed
            status: Status of the execution
            result: Result of the execution if available
            important: Whether this is an important execution entry
            metadata: Additional information about the execution
            
        Returns:
            The created execution entry
        """
        entry = ExecutionEntry(
            action=action, 
            status=status, 
            result=result, 
            metadata=metadata
        )
        self.add(entry, important=important)
        return entry
    
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """
        Get a specific memory entry by ID.
        
        Args:
            entry_id: ID of the entry to retrieve
            
        Returns:
            The memory entry if found, None otherwise
        """
        # First check short-term memory
        entry = self.short_term.get(entry_id)
        if entry:
            return entry
        
        # Then check long-term memory if enabled
        if self.long_term_enabled and self.long_term:
            return self.long_term.get(entry_id)
        
        return None
    
    def search(self, query: Dict[str, Any], include_long_term: bool = True) -> List[MemoryEntry]:
        """
        Search for memory entries matching the query criteria.
        
        Args:
            query: Dictionary of search criteria
            include_long_term: Whether to include long-term memory in the search
            
        Returns:
            List of memory entries matching the criteria
        """
        # Search short-term memory
        results = self.short_term.search(query)
        
        # Search long-term memory if enabled and requested
        if self.long_term_enabled and include_long_term and self.long_term:
            long_term_results = self.long_term.search(query)
            
            # Add long-term results that aren't already in the results
            result_ids = {entry.id for entry in results}
            for entry in long_term_results:
                if entry.id not in result_ids:
                    results.append(entry)
                    result_ids.add(entry.id)
        
        return results
    
    def get_recent_messages(self, limit: Optional[int] = None) -> List[MessageEntry]:
        """
        Get recent message entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of recent message entries
        """
        entries = self.short_term.get_recent(limit)
        return [entry for entry in entries if entry.entry_type == "message"]
    
    def get_conversation_history(self, as_text: bool = False) -> Union[List[MessageEntry], str]:
        """
        Get the conversation history.
        
        Args:
            as_text: Whether to return the history as a formatted text string
            
        Returns:
            List of message entries or formatted text string
        """
        messages = self.get_recent_messages()
        
        if not as_text:
            return messages
        
        # Format as text
        formatted_messages = []
        for msg in messages:
            sender = msg.sender.capitalize()
            content = msg.content
            formatted_messages.append(f"{sender}: {content}")
        
        return "\n".join(formatted_messages)
    
    def clear_short_term(self) -> None:
        """Clear all entries from short-term memory."""
        self.short_term.clear()
    
    def clear_all(self) -> None:
        """Clear all entries from both short-term and long-term memory."""
        self.short_term.clear()
        
        if self.long_term_enabled and self.long_term:
            self.long_term.clear()