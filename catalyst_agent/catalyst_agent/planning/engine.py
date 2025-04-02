"""
Planning engine for the Agentic Core.

This module provides the PlanningEngine class and abstractions for planners
and executors that create and run plans.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from catalyst_agent.utils import setup_logger
from .base import Plan, PlanStep, PlanStatus
from catalyst_agent.utils import setup_logger

class Planner(ABC):
    """Abstract base class for planners that create execution plans."""
    
    @abstractmethod
    def create_plan(self, goal: str, context: Dict[str, Any]) -> Plan:
        """
        Create an execution plan for a given goal.
        
        Args:
            goal: The goal to create a plan for
            context: Context information to consider when planning
            
        Returns:
            An execution plan
        """
        pass


class Executor(ABC):
    """Abstract base class for executors that run plan steps."""
    
    @abstractmethod
    def execute_step(self, step: PlanStep, context: Dict[str, Any]) -> bool:
        """
        Execute a single step in a plan.
        
        Args:
            step: The step to execute
            context: Context information to use during execution
            
        Returns:
            True if execution was successful, False otherwise
        """
        pass


class PlanningEngine:
    """
    Engine that coordinates planning and execution.
    
    This class manages the creation of plans and their execution,
    tracking progress and handling failures.
    """
    
    def __init__(self, planner: Planner, executor: Executor, llm_manager=None):
        """
        Initialize the planning engine.
        
        Args:
            planner: The planner to use for creating plans
            executor: The executor to use for executing plan steps
            llm_manager: LLMManager instance for plan reevaluation (optional)
        """
        self.planner = planner
        self.executor = executor
        self.llm_manager = llm_manager
        self.current_plan: Optional[Plan] = None
        self.execution_context: Dict[str, Any] = {}
        self.executed_steps: List[Dict[str, Any]] = []
        self.logger = setup_logger('agentic.planning')
    
    def create_plan(self, goal: str, context: Dict[str, Any]) -> Plan:
        """
        Create a new execution plan.
        
        Args:
            goal: The goal to create a plan for
            context: Context information to consider when planning
            
        Returns:
            The created plan
        """
        self.logger.info(f"Creating plan for goal: {goal}")
        self.current_plan = self.planner.create_plan(goal, context)
        self.logger.info(f"Plan created: {self.current_plan}")
        self.execution_context = dict(context)  # Create a copy
        return self.current_plan
    
    def execute_plan(
        self, 
        plan: Optional[Plan] = None, 
        step_callback: Optional[Callable[[PlanStep], None]] = None
    ) -> bool:
        """
        Execute a plan step by step.
        
        Args:
            plan: The plan to execute (defaults to current_plan)
            step_callback: Function to call after each step is executed
            
        Returns:
            True if the plan was executed successfully, False otherwise
        """
        if plan:
            self.current_plan = plan
            # Reset executed steps when starting a new plan
            self.executed_steps = []
        
        if not self.current_plan:
            raise ValueError("No plan to execute")
        
        self.current_plan.status = PlanStatus.IN_PROGRESS
        
        # Execute steps one by one using execute_next_step
        while True:
            step = self.execute_next_step()
            
            # If no step was executed, we're done
            if not step:
                break
                
            # If the step failed, return False
            if step.status == PlanStatus.FAILED:
                return False
                
            # Call the step callback if provided
            if step_callback:
                step_callback(step)
        
        # Check if plan is completed
        return self.current_plan.status == PlanStatus.COMPLETED
    
    def execute_next_step(self) -> Optional[PlanStep]:
        """
        Execute the next step in the current plan.
        
        Returns:
            The executed step, or None if no step was executed
        """
        if not self.current_plan:
            raise ValueError("No plan to execute")
        
        # Get the next executable step
        step = self.current_plan.get_next_executable_step()
        if not step:
            # No more steps to execute, update plan status
            self.current_plan.update_status()
            return None
        
        # Check if this step is a duplicate of a previous step
        # This helps prevent infinite loops with identical steps
        is_duplicate = False
        for executed_step in self.executed_steps:
            if (executed_step.get('description', '').lower() == step.description.lower() and
                executed_step.get('tool_name') == step.tool_name):
                is_duplicate = True
                self.logger.warning(f"Detected duplicate step: {step.description}. Skipping execution.")
                break
        
        if is_duplicate:
            # Mark the duplicate step as completed and return it
            step.status = PlanStatus.COMPLETED
            step.result = "Step skipped to avoid duplication of previous step"
            step_dict = step.to_dict()
            self.executed_steps.append(step_dict)
            
            # Update the overall plan status
            self.current_plan.update_status()
            return step
        
        # Execute the step
        step.status = PlanStatus.IN_PROGRESS
        success = self.executor.execute_step(step, self.execution_context)
        
        if success:
            step.status = PlanStatus.COMPLETED
            
            # Store the executed step for plan reevaluation
            step_dict = step.to_dict()
            self.executed_steps.append(step_dict)
            
            # Reevaluate the plan if LLM manager is available
            if self.llm_manager and hasattr(self.llm_manager, 'reevaluate_plan'):
                current_plan_dict = self.current_plan.to_dict()
                
                # Add the current_goal to the context
                self.execution_context['current_goal'] = self.current_plan.goal
                
                # Ensure executed_steps is a list of dictionaries that can be properly processed
                # This fixes the 'self' reference error by ensuring we're passing compatible data types
                safe_executed_steps = []
                for executed_step in self.executed_steps:
                    # Make sure we're working with a plain dictionary
                    if isinstance(executed_step, dict):
                        safe_executed_steps.append(executed_step)
                    elif hasattr(executed_step, 'to_dict'):
                        # If it's an object with a to_dict method, use that
                        safe_executed_steps.append(executed_step.to_dict())
                    else:
                        # Last resort, create a simple dict representation
                        safe_executed_steps.append({
                            'description': str(executed_step),
                            'tool_name': None,
                            'tool_args': {}
                        })
                
                # Reevaluate the plan based on the execution results
                updated_plan_dict = self.llm_manager.reevaluate_plan(
                    goal=self.current_plan.goal,
                    current_plan=current_plan_dict,
                    executed_steps=safe_executed_steps,
                    last_step_result=step.result,
                    context=self.execution_context
                )
                
                # Check if the plan was modified and needs to be updated
                if updated_plan_dict != current_plan_dict:
                    # Create a new plan from the updated plan dictionary
                    remaining_steps = []
                    
                    # Get the updated steps (skip already executed steps)
                    updated_steps = updated_plan_dict.get('plan', [])[len(self.executed_steps):]
                    
                    # Check if the remaining steps would cause an infinite loop
                    # Look for steps that are too similar to previously executed steps
                    safe_steps = []
                    for updated_step_data in updated_steps:
                        updated_description = updated_step_data.get('description', '').lower()
                        # Check if this step is too similar to a previously executed step
                        is_similar_to_previous = False
                        for executed_step in self.executed_steps:
                            executed_description = executed_step.get('description', '').lower()
                            # If descriptions are very similar (80% or more word overlap)
                            # and it's not a tool-based step, consider it a duplicate
                            words1 = set(executed_description.split())
                            words2 = set(updated_description.split())
                            if words1 and words2:  # Avoid division by zero
                                overlap = len(words1.intersection(words2)) / min(len(words1), len(words2))
                                if overlap > 0.8 and not updated_step_data.get('tool_name'):
                                    is_similar_to_previous = True
                                    self.logger.warning(f"Detected similar step: {updated_description}. Skipping.")
                                    break
                        
                        if not is_similar_to_previous:
                            safe_steps.append(updated_step_data)
                    
                    # Only use the safe steps that don't cause loops
                    for updated_step_data in safe_steps:
                        description = updated_step_data.get('description', 'Unknown step')
                        tool_name = updated_step_data.get('tool_name')
                        tool_args = updated_step_data.get('tool_args', {})
                        
                        # Skip None or empty tool names/args
                        if tool_name in [None, "", "null", "None"]:
                            tool_name = None
                        
                        if tool_args in [None, "null", "None"]:
                            tool_args = {}
                        
                        # Create a new plan step
                        new_step = PlanStep(
                            description=description,
                            tool_name=tool_name,
                            tool_args=tool_args
                        )
                        remaining_steps.append(new_step)
                    
                    # Update the current plan with new steps (replacing all pending steps)
                    completed_steps = [s for s in self.current_plan.steps if s.status == PlanStatus.COMPLETED]
                    self.current_plan.steps = completed_steps + remaining_steps
                    
                    # Update the reasoning in metadata
                    self.current_plan.metadata['reevaluation_reasoning'] = updated_plan_dict.get('reasoning', 'Plan was reevaluated')
                    
                    # If updated plan has no steps, mark the plan as completed
                    if not remaining_steps:
                        self.logger.info("No more steps in updated plan, marking plan as completed")
                        self.current_plan.status = PlanStatus.COMPLETED
        else:
            step.status = PlanStatus.FAILED
            self.current_plan.status = PlanStatus.FAILED
        
        # Update the overall plan status
        self.current_plan.update_status()
        
        return step
    
    def get_plan_status(self) -> Optional[PlanStatus]:
        """Get the status of the current plan."""
        if not self.current_plan:
            return None
        
        self.current_plan.update_status()
        return self.current_plan.status
    
    def reset(self) -> None:
        """Reset the planning engine, clearing the current plan."""
        self.current_plan = None
        self.execution_context = {}