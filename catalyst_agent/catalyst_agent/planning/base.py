"""
Core planning abstractions for the Agentic Core.

This module provides the base classes for planning, including plan status,
steps, and complete plans.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
import uuid


class PlanStatus(Enum):
    """Status of a plan or step in the execution process."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class PlanStep:
    """A single step in an execution plan."""
    
    def __init__(
        self, 
        description: str, 
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
        depends_on: Optional[List[str]] = None
    ):
        """
        Initialize a plan step.
        
        Args:
            description: Human-readable description of the step
            tool_name: Name of the tool to use for this step (if applicable)
            tool_args: Arguments to pass to the tool (if applicable)
            depends_on: IDs of steps that must be completed before this one
        """
        self.id = str(uuid.uuid4())
        self.description = description
        self.tool_name = tool_name
        self.tool_args = tool_args or {}
        self.depends_on = depends_on or []
        self.status = PlanStatus.PENDING
        self.result = None
        self.error = None
        self.metadata: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the plan step to a dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlanStep':
        """Create a plan step from a dictionary."""
        step = cls(
            description=data["description"],
            tool_name=data.get("tool_name"),
            tool_args=data.get("tool_args", {}),
            depends_on=data.get("depends_on", [])
        )
        step.id = data["id"]
        step.status = PlanStatus(data["status"])
        step.result = data.get("result")
        step.error = data.get("error")
        step.metadata = data.get("metadata", {})
        return step
    
    def __str__(self) -> str:
        """String representation of the plan step."""
        if self.tool_name:
            return f"{self.description} (using {self.tool_name})"
        return self.description


class Plan:
    """A full execution plan consisting of multiple steps."""
    
    def __init__(self, goal: str, steps: Optional[List[PlanStep]] = None):
        """
        Initialize an execution plan.
        
        Args:
            goal: The overall goal of the plan
            steps: Initial list of steps in the plan (optional)
        """
        self.id = str(uuid.uuid4())
        self.goal = goal
        self.steps: List[PlanStep] = steps or []
        self.status = PlanStatus.PENDING
        self.metadata: Dict[str, Any] = {}
    
    def add_step(self, step: PlanStep) -> None:
        """Add a step to the plan."""
        self.steps.append(step)
    
    def get_step(self, step_id: str) -> Optional[PlanStep]:
        """Get a specific step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def update_status(self) -> None:
        """Update the overall status of the plan based on its steps."""
        if not self.steps:
            self.status = PlanStatus.PENDING
            return
        
        # Check if all steps are completed
        if all(step.status == PlanStatus.COMPLETED for step in self.steps):
            self.status = PlanStatus.COMPLETED
            return
        
        # Check if any step is failed
        if any(step.status == PlanStatus.FAILED for step in self.steps):
            self.status = PlanStatus.FAILED
            return
        
        # Check if any step is in progress
        if any(step.status == PlanStatus.IN_PROGRESS for step in self.steps):
            self.status = PlanStatus.IN_PROGRESS
            return
        
        # Check if all remaining steps are blocked
        pending_steps = [step for step in self.steps if step.status == PlanStatus.PENDING]
        if all(self._is_step_blocked(step) for step in pending_steps):
            self.status = PlanStatus.BLOCKED
            return
        
        # Default to in progress if there are pending steps
        self.status = PlanStatus.IN_PROGRESS
    
    def _is_step_blocked(self, step: PlanStep) -> bool:
        """Check if a step is blocked by dependencies."""
        if not step.depends_on:
            return False
        
        for dep_id in step.depends_on:
            dep_step = self.get_step(dep_id)
            if not dep_step or dep_step.status != PlanStatus.COMPLETED:
                return True
        
        return False
    
    def get_next_executable_step(self) -> Optional[PlanStep]:
        """Get the next step that can be executed based on dependencies."""
        for step in self.steps:
            if step.status != PlanStatus.PENDING:
                continue
            
            # Check if all dependencies are satisfied
            dependencies_met = True
            for dep_id in step.depends_on:
                dep_step = self.get_step(dep_id)
                if not dep_step or dep_step.status != PlanStatus.COMPLETED:
                    dependencies_met = False
                    break
            
            if dependencies_met:
                return step
        
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the plan to a dictionary."""
        return {
            "id": self.id,
            "goal": self.goal,
            "steps": [step.to_dict() for step in self.steps],
            "status": self.status.value,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Plan':
        """Create a plan from a dictionary."""
        steps = [PlanStep.from_dict(step_data) for step_data in data.get("steps", [])]
        plan = cls(goal=data["goal"], steps=steps)
        plan.id = data["id"]
        plan.status = PlanStatus(data["status"])
        plan.metadata = data.get("metadata", {})
        return plan
    
    def __str__(self) -> str:
        """String representation of the plan."""
        result = [f"Plan: {self.goal} (Status: {self.status.value})"]
        for i, step in enumerate(self.steps, 1):
            status_str = f"[{step.status.value}]"
            result.append(f"{i}. {status_str} {step}")
        return "\n".join(result)