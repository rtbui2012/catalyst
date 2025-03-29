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
from .memory import MemoryManager, MessageEntry, ExecutionEntry
from .planning import Plan, PlanStep, PlanStatus, Planner, Executor, PlanningEngine
from .tools import Tool, ToolResult, ToolRegistry, discover_tools, instantiate_tool
from .utils import setup_logger, ensure_directory_exists
from .llm import LLMManager  # Import the LLMManager


class LLMPlanner(Planner):
    """A planner that uses a large language model to create execution plans."""
    
    def __init__(self, agent_core: 'AgentCore'):
        """
        Initialize the LLM planner.
        
        Args:
            agent_core: Reference to the agent core
        """
        self.agent_core = agent_core
        self.logger = setup_logger('agentic.catalyst_agent.planner')
        # Use the LLM manager from the agent core
        self.llm_manager = agent_core.llm_manager
    
    def create_plan(self, goal: str, context: Dict[str, Any]) -> Plan:
        """
        Create an execution plan for a given goal using a large language model.
        
        This implementation creates a plan based on the available tools and the goal.
        
        Args:
            goal: The goal to create a plan for
            context: Context information for planning
            
        Returns:
            An execution plan
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
                
                # If the plan is empty, add a default step
                if len(plan.steps) == 0:
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
        """
        Initialize the agent executor.
        
        Args:
            agent_core: Reference to the agent core
        """
        self.agent_core = agent_core
        self.logger = setup_logger('agentic.catalyst_agent.executor')
    
    def execute_step(self, step: PlanStep, context: Dict[str, Any]) -> bool:
        """
        Execute a single step in a plan.
        
        Args:
            step: The step to execute
            context: Context information for execution
            
        Returns:
            True if execution was successful, False otherwise
        """
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
                
                # Check if the step is about generating content
                generation_keywords = ['generate', 'create', 'tell', 'write', 'compose', 'explain', 'answer', 'provide', 'describe']
                is_generation_step = any(keyword in step.description.lower() for keyword in generation_keywords)
                
                if is_generation_step:
                    # For content generation steps, use the LLM to create the output
                    prompt = f"Perform this task: {step.description}\nBased on the goal: {context.get('current_goal', '')}"
                    response = self.agent_core.llm_manager.generate_response(prompt, {})
                    self.logger.info(f"Generated content for step: {step.description}")
                
                # Store the result
                step.result = response if response else "Step completed successfully"
                
                # Log the execution result
                self.agent_core.memory.add_execution(
                    action=step.description,
                    status="completed",
                    result=step.result
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error executing step: {str(e)}")
            step.error = str(e)
            
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
    
    This class serves as the central component that receives messages,
    manages memory, creates and executes plans, and utilizes tools.
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the agent core.
        
        Args:
            config: Configuration settings (optional, defaults to AgentConfig())
        """
        self.config = config or AgentConfig()
        self.logger = setup_logger('agentic.catalyst_agent.core', 
                                  logging.DEBUG if self.config.verbose else logging.INFO)
        
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
        self.llm_manager = LLMManager(self.config)
        
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
                        tool_instance = instantiate_tool(tool_class)
                        # Register the tool
                        self.register_tool(tool_instance)
                        self.logger.info(f"Automatically registered tool: {tool_instance.name}")
                    except Exception as e:
                        self.logger.error(f"Error instantiating tool {tool_name}: {str(e)}")
            except Exception as e:
                self.logger.error(f"Error during tool discovery: {str(e)}")
        
        # Register specifically requested tools
        for tool_name in self.config.available_tools:
            if not self.tool_registry.get_tool(tool_name):
                self.logger.info(f"Explicit tool registration for {tool_name} would happen here")
        
        # Set up planning engine
        self.planner = LLMPlanner(self)
        self.executor = AgentExecutor(self)
        self.planning_engine = PlanningEngine(self.planner, self.executor, self.llm_manager)
    
    def process_message(self, message: str, sender: str = "user") -> str:
        """
        Process an incoming message and generate a response.
        
        Args:
            message: The message to process
            sender: The sender of the message
            
        Returns:
            The agent's response message
        """
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
        context = {
            'conversation_history': self.memory.get_conversation_history(as_text=True),
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
        """
        Evaluate if a task can be accomplished with the current tools.
        
        Args:
            task: The task to evaluate
            
        Returns:
            Dictionary with 'can_accomplish' boolean and 'reason' string
        """
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
        """
        Register a tool for the agent to use.
        
        Args:
            tool: The tool to register
        """
        self.logger.info(f"Registering tool: {tool.name}")
        self.tool_registry.register_tool(tool)
    
    def _generate_success_response(self, plan: Plan) -> str:
        """
        Generate a response message for a successful plan execution.
        
        Args:
            plan: The executed plan
            
        Returns:
            Response message
        """
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
                
        if non_tool_step_with_result:
            # If we have a direct result from a non-tool step, use it
            return non_tool_step_with_result.result
        elif not tool_steps and not deliberate_no_tools:
            # If no tools were used and it wasn't a deliberate choice, use a template response
            return (
                "I understand your request. However, I currently don't have the necessary tools "
                "to accomplish this task. As my capabilities develop, I'll be able to assist "
                "with more complex requests."
            )
        else:
            # For language tasks that deliberately don't use tools, generate a direct response
            if not tool_steps and deliberate_no_tools:
                # Perform the language task directly
                if "count" in plan.goal.lower() or "how many" in plan.goal.lower():
                    content_prompt = f"Please directly answer this question: {plan.goal}"
                    return self.llm_manager.generate_response(content_prompt, context)
                else:
                    # For other language tasks
                    return self.llm_manager.generate_response(plan.goal, context)
            else:
                # Either tools were used or it was a deliberate choice not to use tools
                # Generate a response based on the executed plan
                return self.llm_manager.generate_response(plan.goal, context)
    
    def _generate_failure_response(self, plan: Plan) -> str:
        """
        Generate a response message for a failed plan execution.
        
        Args:
            plan: The executed plan
            
        Returns:
            Response message
        """
        # Create context for response generation
        context = {
            'conversation_history': self.memory.get_conversation_history(as_text=True),
            'current_plan': plan
        }
        
        # Find the first failed step to report
        failed_step = None
        for step in plan.steps:
            if step.status == PlanStatus.FAILED:
                failed_step = step
                break
        
        if failed_step:
            error_details = failed_step.error if failed_step.error else "Unknown error"
            self.logger.error(f"Plan execution failed at step: {failed_step.description}. Error: {error_details}")
            
            # Attempt to recover from any failure by analyzing the error and reevaluating the plan
            self.logger.info(f"Attempting to recover from failure by reevaluating the plan...")
            
            # Create the context for plan reevaluation
            reevaluation_context = {
                'conversation_history': self.memory.get_conversation_history(as_text=True),
                'available_tools': self.tool_registry.get_all_tools(),
                'config': self.config.to_dict(),
                'failed_step': failed_step.to_dict(),
                'error_details': error_details
            }
            
            # First, check if the tool registry can create a recovery step
            recovery_step_data = self.tool_registry.create_recovery_step(error_details, failed_step.to_dict())
            predefined_recovery = False
            
            if recovery_step_data:
                predefined_recovery = True
                self.logger.info(f"Found predefined recovery step for this error type: {recovery_step_data['description']}")
                
                # Create a recovery step using the predefined handler
                recovery_step = PlanStep(
                    description=recovery_step_data['description'],
                    tool_name=recovery_step_data['tool_name'],
                    tool_args=recovery_step_data['tool_args']
                )
                recovery_step.status = PlanStatus.PENDING
                
                # Add the recovery step to the plan
                plan.add_step(recovery_step)
                
                # If this recovery is for a missing module, add a retry step for the original code
                if "Install missing" in recovery_step.description and recovery_step.tool_name == "package_installer":
                    retry_step = PlanStep(
                        description=f"Retry the original step after addressing the dependency issue",
                        tool_name=failed_step.tool_name,
                        tool_args=failed_step.tool_args
                    )
                    retry_step.status = PlanStatus.PENDING
                    plan.add_step(retry_step)
                    self.logger.info("Added retry step for original action after dependency resolution")
            
            # If no predefined recovery step was found, ask the LLM for help
            if not predefined_recovery:
                # Create a recovery step to find an alternative approach
                recovery_prompt = textwrap.dedent(f"""
                    The step "{failed_step.description}" failed with error: {error_details}

                    Please analyze this failure and determine if there's an alternative way to accomplish 
                    the same goal using a different tool or approach. 

                    Original goal: {plan.goal}
                    """)
                # Add a recovery plan step
                recovery_step = PlanStep(
                    description=f"Analyze failure and find alternative approach for: {failed_step.description}",
                    tool_name=None
                )
                recovery_step.status = PlanStatus.PENDING
                
                # Add the recovery step to the plan
                plan.add_step(recovery_step)
                
                # Execute the recovery step
                recovery_step.status = PlanStatus.IN_PROGRESS
                recovery_result = self.llm_manager.generate_response(recovery_prompt, reevaluation_context)
                recovery_step.result = recovery_result
                recovery_step.status = PlanStatus.COMPLETED
                
                # Now use the recovery analysis to create an alternative approach step
                alternative_prompt = textwrap.dedent(f"""
                Based on your analysis:

                {recovery_result}

                Please provide a SINGLE alternative step to replace the failed step:
                "{failed_step.description}"

                You MUST provide an alternative approach that can be executed by an AI agent using available tools.
                DO NOT suggest manual steps that would require human intervention.

                Available tools: {', '.join([tool.name for tool in self.tool_registry.get_all_tools()])}

                Format your response as a JSON object with these fields:
                {{
                  "description": "Step description",
                  "tool_name": "name_of_tool or null if no tool is needed",
                  "tool_args": {{ "param1": "value1", "param2": "value2" }} or null if no tool is used
                }}
                """)
                alternative_json = self.llm_manager.generate_response(alternative_prompt, reevaluation_context)
                
                try:
                    # Parse the alternative step JSON
                    import json
                    alternative_step_data = json.loads(alternative_json)
                    
                    # Create a new step from the alternative approach
                    description = alternative_step_data.get('description', 'Alternative approach')
                    tool_name = alternative_step_data.get('tool_name')
                    tool_args = alternative_step_data.get('tool_args', {})
                    
                    # Normalize None values
                    if tool_name in [None, "", "null", "None"]:
                        tool_name = None
                    
                    if tool_args in [None, "null", "None"]:
                        tool_args = {}
                    
                    # Validate that the tool exists if one is specified
                    if tool_name and not self.tool_registry.get_tool(tool_name):
                        self.logger.warning(f"Alternative approach specified a non-existent tool: {tool_name}")
                        # Remove tool-specific fallback and use a generic approach
                        tool_name = None
                        tool_args = {}
                        description = f"Analyze alternative ways to accomplish: {plan.goal}"
                    
                    # Add the alternative step to the plan
                    recovery_step = PlanStep(
                        description=description,
                        tool_name=tool_name,
                        tool_args=tool_args
                    )
                    recovery_step.status = PlanStatus.PENDING
                    plan.add_step(recovery_step)
                    
                except Exception as e:
                    self.logger.error(f"Error creating alternative step from LLM response: {str(e)}")
                    # Create a generic recovery step instead of tool-specific fallback
                    recovery_step = PlanStep(
                        description=f"Analyze the error and suggest an alternative approach for: {plan.goal}",
                        tool_name=None,
                        tool_args={}
                    )
                    recovery_step.status = PlanStatus.PENDING
                    plan.add_step(recovery_step)
                    self.logger.info("Added generic recovery step after JSON parsing failure")
            
            # Execute the recovery steps
            recovery_success = False
            for step in plan.steps:
                if step.status == PlanStatus.PENDING:
                    self.logger.info(f"Executing recovery step: {step.description}")
                    step.status = PlanStatus.IN_PROGRESS
                    step_success = self.executor.execute_step(step, reevaluation_context)
                    step.status = PlanStatus.COMPLETED if step_success else PlanStatus.FAILED
                    
                    if step_success:
                        self.logger.info(f"Recovery step succeeded: {step.description}")
                        recovery_success = True
                        
                        # If this was a retry step after a successful recovery, we're done
                        if "Retry the original" in step.description:
                            self.logger.info("Original step retry succeeded after recovery")
                            return self._generate_success_response(plan)
                    else:
                        self.logger.warning(f"Recovery step failed: {step.description}")
            
            # If any recovery step succeeded, generate a success response
            if recovery_success:
                self.logger.info("At least one recovery step succeeded, generating success response")
                return self._generate_success_response(plan)
            
            # All recovery attempts failed, generate a failure response
            response_prompt = textwrap.dedent(f"""
                The following task failed: "{plan.goal}"

                The error occurred at step: "{failed_step.description}"
                Error details: {error_details}

                Recovery attempts were made but were unsuccessful.

                Please generate a helpful response for the user about this failure, explaining what went wrong
                and suggesting alternatives if possible.
                """)
            return self.llm_manager.generate_response(response_prompt, context)
        else:
            # If no specific failed step found, provide a generic failure message
            self.logger.error(f"Plan execution failed but no failed step identified for plan: {plan.goal}")
            return (
                "I'm sorry, but I encountered an issue while trying to complete your request. "
                "There was a problem with the execution process. Please try again or rephrase your request."
            )


# Import these for easier access when importing the module
from typing import Dict, List, Any, Optional, Union