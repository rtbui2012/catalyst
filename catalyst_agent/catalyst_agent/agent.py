"""
Main agent core implementation.

This module contains the AgentCore class that serves as the central
component of the agentic AI system, coordinating between memory,
planning, and tool utilization.
"""

import os
import json
import time
import uuid
import logging
import textwrap
from typing import Dict, List, Optional, Any, Union, Callable

from .config import AgentConfig
from .memory import MemoryManager
from .planning import Plan, PlanStep, PlanStatus, Planner, Executor, PlanningEngine
from .tools import Tool, ToolResult, ToolRegistry, discover_tools, instantiate_tool
from .utils import setup_logger, ensure_directory_exists
from .llm import LLMManager
from .event_queue import EventQueue
from .tools.image_generation import ImageGenerationTool # Added import


class LLMPlanner(Planner):
    """A planner that uses a large language model to create execution plans."""

    def __init__(self, agent_core: 'AgentCore'):
        """Initialize the LLM planner."""
        self.agent_core = agent_core
        self.logger = setup_logger('agentic.catalyst_agent.planner')
        # Use the LLM manager from the agent core
        self.llm_manager = agent_core.llm_manager


    def create_plan(self, goal: str, context: Dict[str, Any]) -> Plan:
        """
        Create an execution plan for a given goal using a large language model.
        """
        # Create a new plan
        plan = Plan(goal=goal)

        # Make sure the config metadata is directly accessible in the context
        if 'config' in context and 'metadata' in context['config']:
            # Extract metadata
            metadata = context['config']['metadata']
            # Add metadata directly to the top level of context for easier access
            for key, value in metadata.items():
                context[key] = value
            self.logger.info(f"Extracted metadata to context: {metadata}")

        # Use the LLM manager to generate a plan
        try:
            plan_data = self.llm_manager.generate_plan(goal, context)

            # Process the generated plan
            if 'plan' in plan_data and isinstance(plan_data['plan'], list):
                # Add steps from the generated plan
                for step_data in plan_data['plan']:
                    description = step_data.get('description', 'Unknown step')
                    tool_name = step_data.get('tool_name')
                    tool_args = step_data.get('tool_args', {})

                    # Skip None or empty tool names
                    if tool_name in [None, "", "null", "None"]:
                        tool_name = None

                    # Skip None tool args
                    if tool_args in [None, "null", "None"]:
                        tool_args = {}

                    # Add the step to the plan
                    plan.add_step(PlanStep(
                        description=description,
                        tool_name=tool_name,
                        tool_args=tool_args
                    ))

                # Store the reasoning in the plan's metadata for use in response generation
                if 'reasoning' in plan_data:
                    plan.metadata['reasoning'] = plan_data['reasoning']

                # Log the plan
                self.logger.info(f"Generated plan with {len(plan.steps)} steps")

                # If the plan is empty, ensure reasoning is set and add a default step
                if len(plan.steps) == 0:
                    # Ensure reasoning is captured even for empty plans
                    if 'reasoning' in plan_data:
                        plan.metadata['reasoning'] = plan_data['reasoning']
                    else:
                        # Add default reasoning if none provided by LLM for empty plan
                        plan.metadata['reasoning'] = "The request is simple and requires a direct response without tools."
                        self.logger.info("Added default reasoning for empty plan.")

                    plan.add_step(PlanStep(
                        description="Analyze the request and respond to the user",
                        tool_name=None
                    ))
            else:
                # If the plan structure is invalid, create a fallback plan
                self.logger.warning(f"Invalid plan structure: {plan_data}")
                plan.add_step(PlanStep(
                    description="Analyze the request and respond to the user",
                    tool_name=None
                ))

            return plan

        except Exception as e:
            self.logger.error(f"Error creating plan: {str(e)}")
            # If there's an error, create a simple fallback plan
            plan = Plan(goal=goal)
            plan.add_step(PlanStep(
                description="Error generating plan, inform the user of the failure",
                tool_name=None
            ))

            return plan


class AgentExecutor(Executor):
    """An executor that runs plan steps using available tools."""

    def __init__(self, agent_core: 'AgentCore'):
        """Initialize the agent executor."""
        self.agent_core = agent_core
        self.logger = setup_logger('agentic.catalyst_agent.executor')

    def execute_step(self, step: PlanStep, context: Dict[str, Any], executed_steps: List[Dict[str, Any]]) -> bool:
        """Execute a single step in a plan, using results from executed_steps."""
        self.logger.info(f"Executing step: {step.description}")

        # Log the execution in memory
        self.agent_core.memory.add_execution(
            action=step.description,
            status="started"
        )

        try:
            # If the step requires a tool, execute it
            if step.tool_name:
                # Get the tool
                tool_registry = self.agent_core.tool_registry

                # Execute the tool - result will be processed generically
                result = tool_registry.execute_tool(step.tool_name, **step.tool_args)

                # If execution fails, try to fix it using the tool registry's error handling
                if not result.success and result.error:
                    self.logger.info(f"Tool execution failed with error: {result.error}")

                    # Check if any registered tool can handle this error
                    recovery_step = tool_registry.create_recovery_step(result.error, step.to_dict())

                    if recovery_step:
                        # A recovery step was found, execute it
                        self.logger.info(f"Found recovery step: {recovery_step['description']}")

                        # Create temporary PlanStep for recovery
                        recovery_plan_step = PlanStep(
                            description=recovery_step['description'],
                            tool_name=recovery_step['tool_name'],
                            tool_args=recovery_step['tool_args']
                        )

                        # Execute the recovery step
                        self.logger.info(f"Executing recovery step: {recovery_step['description']}")
                        recovery_result = tool_registry.execute_tool(
                            recovery_plan_step.tool_name,
                            **recovery_plan_step.tool_args
                        )

                        if recovery_result.success:
                            self.logger.info("Recovery step succeeded, retrying original step")
                            # Retry the original step
                            result = tool_registry.execute_tool(step.tool_name, **step.tool_args)
                        else:
                            self.logger.info(f"Recovery step failed: {recovery_result.error}")
                    else:
                        # No recovery step was found, try generic fixes
                        if "code" in step.tool_args and isinstance(step.tool_args["code"], str):
                            # This appears to be a code execution step with code, try to fix it generically
                            self.logger.info("Attempting to fix the code...")

                            # Request a fix from the LLM
                            fix_prompt = textwrap.dedent(f"""
                                The following code failed with this error:
                                {result.error}

                                Original code:
                                ```python
                                {step.tool_args["code"]}
                                ```

                                Please provide a corrected version of this code that addresses the error. Only return the fixed code, nothing else.
                                """)

                            # Generate fixed code using the LLM
                            fixed_code = self.agent_core.llm_manager.generate_response(fix_prompt, {})

                            # Extract the actual code from the response (it might include markdown code blocks)
                            if "```python" in fixed_code:
                                fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
                            elif "```" in fixed_code:
                                fixed_code = fixed_code.split("```")[1].split("```")[0].strip()

                            self.logger.info(f"Generated fixed code:\n{fixed_code}")

                            # Try again with the fixed code
                            step.tool_args["code"] = fixed_code
                            self.logger.info("Retrying with fixed code...")
                            result = tool_registry.execute_tool(step.tool_name, **step.tool_args)

                # Store the result
                step.result = result.data if result.success else None
                step.error = result.error if not result.success else None

                # Log the execution result
                self.agent_core.memory.add_execution(
                    action=f"Tool execution: {step.tool_name}",
                    status="completed" if result.success else "failed",
                    result=result.data if result.success else result.error
                )

                return result.success
            else:
                # For steps that don't use tools (language-based tasks), generate output using the LLM
                response = ""
                step_success = True # Assume success unless generation fails

                # Check if the step is about generating content
                generation_keywords = ['generate', 'create', 'tell', 'write', 'compose', 'explain', 'answer', 'provide', 'describe', 'synthesize', 'summarize']
                is_generation_step = any(keyword in step.description.lower() for keyword in generation_keywords)

                if is_generation_step:
                    # Format previous step results for context
                    previous_results_str = "\nPREVIOUS STEP RESULTS:\n"
                    if executed_steps:
                        for i, executed_step in enumerate(executed_steps):
                            previous_results_str += f"Step {i+1}: {executed_step.get('description', 'N/A')}\n"
                            if executed_step.get('result'):
                                # Truncate long results for prompt clarity
                                result_repr = repr(executed_step['result'])
                                if len(result_repr) > 500:
                                    result_repr = result_repr[:497] + "..."
                                previous_results_str += f"  Result: {result_repr}\n"
                            if executed_step.get('error'):
                                previous_results_str += f"  Error: {executed_step['error']}\n"
                    else:
                        previous_results_str += "No previous steps executed.\n"

                    # For content generation steps, use the LLM to create the output
                    prompt = (
                        f"Perform this task: {step.description}\n"
                        f"Based on the overall goal: {context.get('current_goal', 'Not specified')}\n"
                        f"{previous_results_str}\n"
                        f"Provide only the direct output for the task, without any introductory phrases like 'Okay, here is...'."
                    )
                    self.logger.debug(f"Prompt for non-tool generation step:\n{prompt}")
                    response = self.agent_core.llm_manager.generate_response(prompt, {}) # Context is implicitly handled by LLMManager if needed

                    if response:
                        self.logger.info(f"Generated content for step: {step.description}")
                        step.result = response
                        step.error = None
                    else:
                        # If generation was expected but failed, mark as error
                        self.logger.warning(f"LLM returned empty response for generation step: {step.description}")
                        step.result = None
                        step.error = "LLM failed to generate content for this step."
                        step_success = False # Mark step as failed
                else:
                     # If not explicitly a generation step, assume simple completion
                     step.result = "Step completed successfully"
                     step.error = None


                # Log the execution result
                self.agent_core.memory.add_execution(
                    action=step.description,
                    status="completed" if step_success else "failed",
                    result=step.result if step_success else step.error
                )

                return step_success

        except Exception as e:
            self.logger.error(f"Error executing step: {str(e)}", exc_info=True)
            step.error = str(e)
            step.result = None # Ensure result is None on error

            # Log the execution error
            self.agent_core.memory.add_execution(
                action=step.description,
                status="failed",
                result=f"Error: {str(e)}"
            )

            return False


class AgentCore:
    """
    Core agent class that coordinates all aspects of the agentic AI system.
    """
    def __init__(self, config: Optional[AgentConfig] = None):
        """ Initialize the agent core.  """
        self.config = config or AgentConfig()
        self.logger = setup_logger('agentic.catalyst_agent.core',
                        logging.DEBUG if self.config.verbose else logging.INFO)

        self.event_queue = EventQueue()

        # Set up memory
        memory_path = None
        if self.config.long_term_memory_enabled:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            memory_dir = os.path.join(base_dir, '..', '..', 'data', 'memory')
            ensure_directory_exists(memory_dir)
            memory_path = os.path.join(memory_dir, 'long_term_memory.json')

        self.memory = MemoryManager(
            short_term_capacity=self.config.short_term_memory_capacity,
            long_term_enabled=self.config.long_term_memory_enabled,
            long_term_storage_path=memory_path
        )

        # Set up tool registry
        self.tool_registry = ToolRegistry()

        # Set up LLM manager
        self.llm_manager = LLMManager(self.config, self.event_queue)

        # Automatically discover and register tools if enabled
        if self.config.tool_discovery_enabled:
            self.logger.info("Tool discovery is enabled. Discovering available tools...")
            try:
                # Discover available tool classes
                tool_classes = discover_tools()
                self.logger.info(f"Discovered {len(tool_classes)} tool classes")

                # Instantiate and register discovered tools
                for tool_name, tool_class in tool_classes.items():
                    try:
                        # Create an instance of the tool
                        tool_instance = instantiate_tool(tool_class, event_queue=self.event_queue)
                        # Register the tool
                        self.register_tool(tool_instance)
                        self.logger.info(f"Automatically registered tool: {tool_instance.name}")
                    except Exception as e:
                        self.logger.error(f"Error instantiating tool {tool_name}: {str(e)}")
            except Exception as e:
                self.logger.error(f"Error during tool discovery: {str(e)}")

        # --- Post-discovery configuration for specific tools ---
        # Configure ImageGenerationTool with a save directory if discovered
        if 'generate_image' in self.tool_registry._tools: # Corrected attribute access
            self.logger.info("Configuring ImageGenerationTool with save directory...")
            try:
                # Define the save path within the configured blob storage
                image_save_path = os.path.join(self.config.blob_storage_path, 'generated_images')

                # Remove the default instance created by discovery
                del self.tool_registry._tools['generate_image'] # Corrected attribute access

                # Create a new instance with the save_directory configured
                # Note: This assumes API keys/endpoints are handled by environment variables
                # as per ImageGenerationTool's __init__ defaults.
                configured_image_tool = ImageGenerationTool(
                    save_directory=image_save_path,
                    event_queue=self.event_queue
                    # Add api_key/endpoint here if they should come from config instead of env
                    # api_key=self.config.get('azure_openai_dalle_key'),
                    # endpoint=self.config.get('azure_openai_dalle_endpoint')
                )

                # Register the properly configured tool instance
                self.register_tool(configured_image_tool)
                self.logger.info(f"ImageGenerationTool configured to save files to: {image_save_path}")

            except Exception as e:
                self.logger.error(f"Error configuring ImageGenerationTool: {str(e)}")
        # --- End specific tool configuration ---

        # Register specifically requested tools (if not already configured)
        for tool_name in self.config.available_tools:
            if not self.tool_registry.get_tool(tool_name):
                # This part might need adjustment if specific tools require manual config
                self.logger.warning(f"Tool '{tool_name}' requested but not auto-discovered or manually configured.")
                # Potentially add logic here to instantiate other specific tools from config

        # Set up planning engine
        self.planner = LLMPlanner(self)
        self.executor = AgentExecutor(self)
        self.planning_engine = PlanningEngine(self.planner, self.executor, self.llm_manager)

    def process_message(self, message: str, sender: str = "user", conversation_history: Optional[List[Dict]] = None) -> str:
        """ Process an incoming message and generate a response, optionally using provided history. """

        self.logger.info(f"Processing message from {sender}: {message}")

        # Add message to memory
        self.memory.add_message(content=message, sender=sender)

        # Ensure temporal context is initialized
        if not hasattr(self.config, 'metadata') or not self.config.metadata:
            self.config.metadata = {}

        # Make sure current_date is set - if not in metadata, set it now
        if 'current_date' not in self.config.metadata:
            import datetime
            current_date = datetime.datetime.now().strftime("%B %d, %Y")
            self.config.metadata['current_date'] = current_date
            self.logger.info(f"Set current_date in config metadata: {current_date}")

        # Create planning context
        # Use provided history if available, otherwise use internal memory
        history_for_context = conversation_history if conversation_history is not None else self.memory.get_conversation_history()
        # Convert history to text format if needed by the LLM/planner
        history_text = "\n".join([f"{msg.sender}: {msg.content}" for msg in history_for_context])

        context = {
            'conversation_history': history_text,
            'available_tools': self.tool_registry.get_all_tools(),
            'config': self.config.to_dict()
        }

        # Directly add temporal context at the top level for easier access
        # This needs to be set even if None to ensure consistency
        context['current_date'] = self.config.metadata.get('current_date')
        self.logger.info(f"Added current_date to context: {context['current_date']}")

        # Determine if the message requires a plan
        if self.config.planning_enabled:
            # Create a plan for the message
            plan = self.planning_engine.create_plan(goal=message, context=context)

            # Execute the plan
            self.logger.info(f"Executing plan for message: {message}")
            success = self.planning_engine.execute_plan(plan)

            # Update context with the current plan
            context['current_plan'] = self.planning_engine.current_plan

            # Generate response based on plan execution
            if success:
                response = self._generate_success_response(plan)
            else:
                response = self._generate_failure_response(plan)
        else:
            # If planning is disabled, generate a direct response
            response = self._generate_direct_response(message, context)

        # Add response to memory
        self.memory.add_message(content=response, sender="agent")

        return response

    def can_accomplish(self, task: str) -> Dict[str, Any]:
        """ Evaluate if a task can be accomplished with the current tools. """

        self.logger.info(f"Evaluating if task can be accomplished: {task}")

        # Create planning context
        context = {
            'conversation_history': self.memory.get_conversation_history(as_text=True),
            'available_tools': self.tool_registry.get_all_tools(),
            'config': self.config.to_dict()
        }

        # Create a plan for the task
        plan = self.planning_engine.create_plan(goal=task, context=context)

        # Check if the plan can be executed
        tools_needed = []
        for step in plan.steps:
            if step.tool_name and not self.tool_registry.get_tool(step.tool_name):
                tools_needed.append(step.tool_name)

        if not tools_needed:
            return {
                'can_accomplish': True,
                'reason': 'The task can be accomplished with the current tools.',
                'plan': plan.to_dict() if self.config.verbose else None
            }
        else:
            return {
                'can_accomplish': False,
                'reason': f'The task requires the following tools that are not available: {", ".join(tools_needed)}',
                'missing_tools': tools_needed,
                'plan': plan.to_dict() if self.config.verbose else None
            }

    def register_tool(self, tool: Tool) -> None:
        """Register a tool for the agent to use."""
        self.logger.info(f"Registering tool: {tool.name}")
        self.tool_registry.register_tool(tool)

    def _generate_success_response(self, plan: Plan) -> str:
        """Generate a response message for a successful plan execution."""
        # Create context for response generation
        context = {
            'conversation_history': self.memory.get_conversation_history(as_text=True),
            'current_plan': plan
        }

        # Use the LLM to generate a response
        tool_steps = [step for step in plan.steps if step.tool_name]

        # Check for a deliberate decision not to use tools (check metadata for reasoning)
        deliberate_no_tools = False

        # Check if the plan has reasoning that explains why no tools were needed
        if 'reasoning' in plan.metadata and not tool_steps:
            reasoning_lower = plan.metadata['reasoning'].lower()
            # Check if reasoning mentions not needing tools for a valid reason
            if any(phrase in reasoning_lower for phrase in
                  ['no tools needed', 'no tool required', 'language generation',
                   'can be accomplished directly', 'without using tools', 'language task',
                   'creative', 'explanation', 'general knowledge', 'straightforward',
                   'counting', 'analysis', 'directly']):
                deliberate_no_tools = True

        # If we have a non-tool step with a result, use that result
        non_tool_step_with_result = None
        for step in plan.steps:
            if not step.tool_name and step.result and step.result != "Step completed successfully":
                non_tool_step_with_result = step
                break

        # Commented out the early return for non-tool steps:
        # if non_tool_step_with_result:
        #     # If we have a direct result from a non-tool step, use it
        #     self.logger.info("Using direct result from non-tool step for response.")
        #     return non_tool_step_with_result.result

        # If there are tool steps or it was a deliberate non-tool plan, generate a summary
        if tool_steps or deliberate_no_tools:
            self.logger.info("Generating summary response based on successful plan execution.")
            # Pass the plan object directly to generate_response
            response = self.llm_manager.generate_response(
                message=f"The plan to achieve the goal '{plan.goal}' was executed successfully.",
                context=context
            )
            return response
        else:
            # Fallback if no tool steps and no clear non-tool result or reasoning
            self.logger.warning("Plan succeeded but has no tool steps and no clear non-tool result/reasoning. Generating generic success message.")
            return f"I have successfully completed the task: {plan.goal}"


    def _generate_failure_response(self, plan: Plan) -> str:
        """Generate a response message for a failed plan execution."""
        # Create context for response generation
        context = {
            'conversation_history': self.memory.get_conversation_history(as_text=True),
            'current_plan': plan
        }

        # Find the failed step
        failed_step = None
        for step in plan.steps:
            if step.status == PlanStatus.FAILED:
                failed_step = step
                break

        # Construct the failure message
        if failed_step:
            failure_reason = f"Step '{failed_step.description}' failed"
            if failed_step.error:
                failure_reason += f" with error: {failed_step.error}"
            else:
                failure_reason += "."
        else:
            failure_reason = "The plan failed, but the specific step could not be identified."

        self.logger.info(f"Generating failure response: {failure_reason}")

        # Use the LLM to generate a response explaining the failure
        response = self.llm_manager.generate_response(
            message=f"I encountered an issue while trying to achieve the goal '{plan.goal}'. {failure_reason}",
            context=context
        )

        return response

    def _generate_direct_response(self, message: str, context: Dict[str, Any]) -> str:
        """Generate a direct response when planning is disabled."""
        self.logger.info("Planning disabled, generating direct response.")
        # Use the LLM manager to generate a direct response
        response = self.llm_manager.generate_response(message, context)
        return response

    def get_event_queue(self) -> EventQueue:
        """ Returns the event queue instance. """
        return self.event_queue