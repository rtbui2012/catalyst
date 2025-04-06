"""
Planning engine for the Agentic Core.

This module provides the PlanningEngine class and abstractions for planners
and executors that create and run plans.
"""

from abc import ABC, abstractmethod
import re
import json
import uuid # Import uuid
from typing import Dict, List, Optional, Any, Callable
from catalyst_agent.utils import setup_logger
from .base import Plan, PlanStep, PlanStatus

class Planner(ABC):
    """Abstract base class for planners that create execution plans."""

    @abstractmethod
    def create_plan(self, goal: str, context: Dict[str, Any]) -> Plan:
        """Create an execution plan for a given goal."""
        pass


class Executor(ABC):
    """Abstract base class for executors that run plan steps."""

    @abstractmethod
    def execute_step(self, step: PlanStep, context: Dict[str, Any], executed_steps: List[Dict[str, Any]]) -> bool:
        """
        Execute a single step in a plan.

        Args:
            step: The step to execute.
            context: General context information.
            executed_steps: A list of dictionaries representing previously executed steps and their results.

        Returns:
            True if execution was successful, False otherwise.
        """
        pass


class PlanningEngine:
    """
    Engine that coordinates planning and execution.
    """

    def __init__(self, planner: Planner, executor: Executor, llm_manager=None):
        """Initialize the planning engine."""
        self.planner = planner
        self.executor = executor
        self.llm_manager = llm_manager
        self.current_plan: Optional[Plan] = None
        self.execution_context: Dict[str, Any] = {}
        self.executed_steps: List[Dict[str, Any]] = [] # Stores dict representations of executed steps
        self.logger = setup_logger('agentic.planning')

    def _resolve_placeholders(self, data: Any, executed_steps: List[Dict[str, Any]]) -> Any:
        """Recursively resolve placeholders like '{step_N_result}' in data."""
        placeholder_pattern = re.compile(r"\{step_(\d+)_result\}")

        if isinstance(data, str):
            matches = list(placeholder_pattern.finditer(data))
            if not matches: return data

            if len(matches) == 1 and matches[0].group(0) == data:
                step_index_str = matches[0].group(1)
                step_index = int(step_index_str) - 1
                if 0 <= step_index < len(executed_steps):
                    return executed_steps[step_index].get('result')
                else:
                    self.logger.warning(f"Placeholder '{data}' refers to invalid step index: {step_index + 1}")
                    return data
            else:
                resolved_string = data
                for match in reversed(matches):
                    placeholder = match.group(0)
                    step_index_str = match.group(1)
                    step_index = int(step_index_str) - 1
                    if 0 <= step_index < len(executed_steps):
                        step_result = executed_steps[step_index].get('result')
                        result_str = json.dumps(step_result) if isinstance(step_result, (dict, list)) else str(step_result)
                        resolved_string = resolved_string.replace(placeholder, result_str)
                    else:
                        self.logger.warning(f"Embedded placeholder '{placeholder}' refers to invalid step index: {step_index + 1}")
                return resolved_string
        elif isinstance(data, dict):
            return {k: self._resolve_placeholders(v, executed_steps) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_placeholders(item, executed_steps) for item in data]
        else:
            return data

    def create_plan(self, goal: str, context: Dict[str, Any]) -> Plan:
        """Create a new execution plan."""
        self.logger.info(f"Creating plan for goal: {goal}")
        self.current_plan = self.planner.create_plan(goal, context)
        self.logger.info(f"Plan created: {self.current_plan}")
        self.execution_context = dict(context)
        self.executed_steps = []
        return self.current_plan

    def execute_plan(
        self,
        plan: Optional[Plan] = None,
        step_callback: Optional[Callable[[PlanStep], None]] = None
    ) -> bool:
        """Execute a plan step by step."""
        if plan:
            self.current_plan = plan
            self.executed_steps = []

        if not self.current_plan: raise ValueError("No plan to execute")
        self.current_plan.status = PlanStatus.IN_PROGRESS

        while True:
            step = self.execute_next_step()
            if not step: break
            if step.status == PlanStatus.FAILED: return False
            if step_callback: step_callback(step)

        return self.current_plan.status == PlanStatus.COMPLETED

    def execute_next_step(self) -> Optional[PlanStep]:
        """Execute the next step in the current plan, resolving placeholders first."""
        if not self.current_plan: raise ValueError("No plan to execute")

        step = self.current_plan.get_next_executable_step()
        if not step:
            self.current_plan.update_status()
            return None

        # Duplicate check
        is_duplicate = False
        for executed_step_dict in self.executed_steps:
            if (executed_step_dict.get('description', '').lower() == step.description.lower() and
                executed_step_dict.get('tool_name') == step.tool_name):
                is_duplicate = True
                self.logger.warning(f"Detected duplicate step: {step.description}. Skipping execution.")
                break
        if is_duplicate:
            step.status = PlanStatus.COMPLETED
            step.result = "Step skipped to avoid duplication of previous step"
            self.current_plan.update_status()
            return step

        # Placeholder resolution
        try:
            if step.tool_args:
                self.logger.debug(f"Attempting to resolve placeholders in args for step: {step.description}")
                resolved_args = self._resolve_placeholders(step.tool_args, self.executed_steps)
                if resolved_args != step.tool_args:
                    self.logger.info(f"Resolved placeholders in arguments for step '{step.description}'. New args: {resolved_args}")
                    step.tool_args = resolved_args
                else:
                    self.logger.debug("No placeholders found or resolved.")
        except Exception as e:
            self.logger.error(f"Error resolving placeholders for step '{step.description}': {e}", exc_info=True)

        # Execute the step
        step.status = PlanStatus.IN_PROGRESS
        success = self.executor.execute_step(step, self.execution_context, self.executed_steps)

        if success:
            step.status = PlanStatus.COMPLETED
            step_dict = step.to_dict()
            self.executed_steps.append(step_dict)

            # Reevaluate the plan if LLM manager is available
            if self.llm_manager and hasattr(self.llm_manager, 'reevaluate_plan'):
                updated_plan_dict = self.llm_manager.reevaluate_plan(
                    goal=self.current_plan.goal,
                    current_plan=self.current_plan.to_dict(),
                    executed_steps=self.executed_steps,
                    last_step_result=step.result,
                    context=self.execution_context
                )
                self.logger.debug(f"Plan dict returned from reevaluation: {json.dumps(updated_plan_dict, indent=2)}")

                # --- Force adoption of the returned plan structure ---
                self.logger.info("Adopting plan structure returned by reevaluation.")
                new_plan_steps_data = updated_plan_dict.get('plan', [])
                new_plan_reasoning = updated_plan_dict.get('reasoning', self.current_plan.metadata.get('reasoning'))

                # --- Robust Plan Reconstruction with Key Mapping & ID Generation ---
                current_completed_step_objects = {s.id: s for s in self.current_plan.steps if s.status == PlanStatus.COMPLETED}
                all_new_step_objects = []

                for i, step_data in enumerate(new_plan_steps_data):
                    if not isinstance(step_data, dict):
                        self.logger.error(f"Invalid step data format (not a dict) at index {i}: {step_data}")
                        continue

                    # --- Handle potentially missing/alternative keys ---
                    step_id = step_data.get('id')
                    if not step_id:
                         # If ID is missing in the LLM response, generate a new one
                         step_id = str(uuid.uuid4())
                         self.logger.warning(f"Generated new ID '{step_id}' for step at index {i} from LLM reevaluation as 'id' was missing.")

                    description = step_data.get('description') or step_data.get('task') # Use 'task' as fallback
                    if not description:
                         description = "No description provided" # Default if both missing
                         self.logger.warning(f"Using default description for step ID {step_id} as 'description'/'task' was missing.")

                    status_str = step_data.get('status', PlanStatus.PENDING.value) # Default status if missing

                    # Map tool args keys
                    tool_args = step_data.get('tool_args') or step_data.get('parameters') or step_data.get('arguments', {})
                    # --- End Key Handling ---


                    # If this step was already completed, reuse the original object (important to keep results)
                    # Check status from the LLM data to see if it thinks it's completed
                    is_llm_marked_complete = status_str.lower() != PlanStatus.PENDING.value

                    if step_id in current_completed_step_objects and is_llm_marked_complete:
                         self.logger.debug(f"Reusing existing completed PlanStep object for step ID {step_id}")
                         # Ensure the reused object's status matches the LLM's view if it's not pending
                         current_completed_step_objects[step_id].status = PlanStatus(status_str)
                         all_new_step_objects.append(current_completed_step_objects[step_id])
                    else:
                         # Create the mapped dictionary for PlanStep.from_dict
                         mapped_step_data = {
                             "id": step_id,
                             "description": description,
                             "tool_name": step_data.get("tool_name"),
                             "tool_args": tool_args,
                             "depends_on": step_data.get("depends_on", []),
                             "status": status_str,
                             "result": step_data.get("result"),
                             "error": step_data.get("error"),
                             "metadata": step_data.get("metadata", {})
                         }
                         try:
                              # Create new object for pending or newly introduced steps
                              new_step_obj = PlanStep.from_dict(mapped_step_data)
                              all_new_step_objects.append(new_step_obj)
                         except Exception as e:
                              self.logger.error(f"Error creating PlanStep from mapped dict at index {i}: {e}. Mapped Data: {mapped_step_data}", exc_info=True)
                              continue
                # --- End Robust Plan Reconstruction ---

                # Update the current plan object's steps list entirely
                self.current_plan.steps = all_new_step_objects
                self.current_plan.metadata['reasoning'] = new_plan_reasoning
                if 'metadata' in updated_plan_dict:
                    self.current_plan.metadata.update(updated_plan_dict['metadata'])

                # Check if the just-executed step is still the last completed one
                completed_step_ids_in_new_plan = [s.id for s in self.current_plan.steps if s.status == PlanStatus.COMPLETED]
                if not completed_step_ids_in_new_plan or completed_step_ids_in_new_plan[-1] != step.id:
                     self.logger.warning(f"Step {step.id} is no longer the last completed step after reevaluation.")

                # If the new plan structure has no PENDING steps left, mark complete
                has_pending = any(s.status == PlanStatus.PENDING for s in self.current_plan.steps)
                if not has_pending:
                     self.logger.info("No more pending steps in updated plan, marking plan as completed")
                     self.current_plan.status = PlanStatus.COMPLETED

        else: # if not success
            step.status = PlanStatus.FAILED
            self.current_plan.status = PlanStatus.FAILED

        self.current_plan.update_status()
        return step

    def get_plan_status(self) -> Optional[PlanStatus]:
        """Get the status of the current plan."""
        if not self.current_plan: return None
        self.current_plan.update_status()
        return self.current_plan.status

    def reset(self) -> None:
        """Reset the planning engine, clearing the current plan."""
        self.current_plan = None
        self.execution_context = {}
        self.executed_steps = []