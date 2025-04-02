"""
Event queue for Catalyst Agent.

This module provides a simple queue implementation to store event data
such as tool inputs, tool outputs, and execution steps with reasoning.
"""

import time
from enum import Enum
from typing import Dict, List, Any, Optional, Union
import uuid
import queue
import json
from catalyst_agent.utils import setup_logger

logger = setup_logger(__name__)

class EventType(Enum):
    """Types of events that can be stored in the event queue."""
    PLAN_GENERATION = "plan_generation"
    TOOL_INPUT = "tool_input"
    TOOL_OUTPUT = "tool_output"
    PLAN_CHANGE = "plan_change"
    EXECUTION_STEP = "execution_step"
    TOOL_ERROR = "tool_error"
    FINAL_SOLUTION = "final_solution"   


class Event:
    """Event class representing an occurrence in the agent's processing."""
    
    def __init__(self, 
                 event_type: EventType, 
                 data: Dict[str, Any],
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize an event.
        
        Args:
            event_type: Type of the event
            data: Main event data
            metadata: Additional metadata for the event
        """
        self.id = str(uuid.uuid4())
        self.event_type = event_type
        self.timestamp = time.time()
        self.data = data
        self.metadata = metadata or {}
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert the event to a dictionary representation."""
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "data": self.data,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """Convert the event to a JSON string."""
        return json.dumps(self.to_dict(), default=str)


class EventQueue:
    """ A simple queue to store event data for the Catalyst Agent. """
    
    def __init__(self, max_size: int = 1000):
        self.queue = queue.Queue(maxsize=max_size)
        
    def add_tool_input(self, tool_name: str, tool_args: Dict[str, Any], 
                       metadata: Optional[Dict[str, Any]] = None) -> str:
        event = Event(
            event_type=EventType.TOOL_INPUT,
            data={
                "tool_name": tool_name,
                "tool_args": tool_args
            },
            metadata=metadata
        )
        self.queue.put(event)
        return event.id
    
    def add_tool_output(self, tool_name: str, success: bool, data: Any = None,
                        error: Optional[str] = None, 
                        metadata: Optional[Dict[str, Any]] = None) -> str:
        event = Event(
            event_type=EventType.TOOL_OUTPUT,
            data={
                "tool_name": tool_name,
                "success": success,
                "data": data,
                "error": error
            },
            metadata=metadata
        )
        self.queue.put(event)
        return event.id
    
    def add_planning(self, 
                    goal: str,
                    plan: Dict[str, Any],
                    reasoning: str,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        event = Event(
            event_type=EventType.PLAN_GENERATION,
            data={
                "goal": goal,
                "plan": plan,
                "reasoning": reasoning
            },
            metadata=metadata
        )
        self.queue.put(event)
        return event.id
    
    def add_language_opperation(self, 
                    reasoning: str,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        event = Event(
            event_type=EventType.PLAN_GENERATION,
            data={
                "reasoning": reasoning
            },
            metadata=metadata
        )
        self.queue.put(event)
        return event.id    
    
    def add_final_solution(self,
                    solution: str,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        event = Event(
            event_type=EventType.FINAL_SOLUTION,
            data={
                "solution": solution
            },
            metadata=metadata
        )
        self.queue.put(event)
        return event.id    
    
    def add_error(self, 
                    goal: str,
                    error: str,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        event = Event(
            event_type=EventType.PLAN_GENERATION,
            data={
                "goal": goal,
                "error": error
            },
            metadata=metadata
        )
        self.queue.put(event)
        return event.id 
    
    def get_events(self, limit: Optional[int] = None, 
                 event_type: Optional[EventType] = None) -> queue:
        events = list(self.queue)
        
        # Apply event type filter
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        # Apply limit
        if limit and limit > 0:
            return events[-limit:]  # Return the most recent events
        
        return events
    
    def get_events_as_dicts(self, limit: Optional[int] = None,
                          event_type: Optional[EventType] = None) -> List[Dict[str, Any]]:
        """ Get events from the queue as dictionaries with optional filtering."""
        events = self.get_events(limit, event_type)
        return [event.to_dict() for event in events]
    
    def get_latest_event(self, event_type: Optional[EventType] = None) -> Optional[Event]:
        """ Get the most recent event of the specified type. """
        events = self.get_events(limit=1, event_type=event_type)
        return events[0] if events else None
    
    def clear(self) -> None:
        """Clear all events from the queue."""
        self.queue.clear()
    
    def size(self) -> int:
        """Get the current size of the queue."""
        return len(self.queue)