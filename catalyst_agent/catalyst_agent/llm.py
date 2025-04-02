"""
LLM integration for Agentic Core.

This module provides integration with Azure OpenAI for the Agentic Core,
enabling language model capabilities for planning, response generation,
and other AI-powered features.
"""

import os
import logging
import json
import textwrap
from typing import List, Dict, Any, Optional, Union
import tiktoken
from openai import AzureOpenAI

from .config import AgentConfig
from .utils import setup_logger
from catalyst_agent.utils.prompt_templates import SYSTEM_GENERATE, SYSTEM_REPLAN 
from catalyst_agent.utils.prompt_templates import USER_PLAN, TOOLS_FEW_SHOT_EXAMPLES
from catalyst_agent.utils.prompt_templates import USER_GENERATE, USER_REPLAN

from .event_queue import EventQueue, EventType

class LLMManager:
    """
    Manager for LLM interactions in the Agentic Core.
    
    This class handles all interactions with the language model,
    including planning, response generation, and other AI capabilities.
    """
    
    def __init__(self, config: AgentConfig, event_queue: EventQueue = None):
        """
        Initialize the LLM manager.
        
        Args:
            config: Agent configuration with LLM settings
        """
        self.config = config
        self.logger = setup_logger('agentic.llm', 
                                  logging.DEBUG if config.verbose else logging.INFO)
        
        # Initialize the OpenAI client
        self._initialize_client()

        # Initialize event queue
        self.event_queue = event_queue or EventQueue()
        
        # Initialize tokenizer for token counting
        try:
            self._tokenizer = tiktoken.encoding_for_model(self.config.model_name)
            self.logger.info(f"Initialized tokenizer for model: {self.config.model_name}")
        except Exception as e:
            self.logger.warning(f"Failed to initialize tokenizer for {self.config.model_name}: {e}")
            self._tokenizer = None
            
        # Initialize current date if not already set in config metadata
        if not hasattr(self.config, 'metadata') or not self.config.metadata or 'current_date' not in self.config.metadata:
            # Set default current date to today
            import datetime
            current_date = datetime.datetime.now().strftime("%B %d, %Y")
            if not hasattr(self.config, 'metadata'):
                self.config.metadata = {}
            self.config.metadata['current_date'] = current_date
            self.logger.info(f"Initialized current_date in LLMManager: {current_date}")
    
    def _initialize_client(self):
        """Initialize the Azure OpenAI client with configuration settings."""
        # Get API key and endpoint
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        api_version = os.getenv("OPENAI_API_VERSION", "2024-02-15-preview")
        
        # Validate configuration
        if not api_key:
            self.logger.error("Azure OpenAI API key not found in environment variables")
            raise ValueError("Azure OpenAI API key is required")
        
        if not endpoint:
            self.logger.error("Azure OpenAI endpoint not found in environment variables")
            raise ValueError("Azure OpenAI endpoint is required")
        
        # Initialize client
        try:
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=endpoint
            )
            self.logger.info(f"Initialized Azure OpenAI client with endpoint: {endpoint}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Azure OpenAI client: {e}")
            raise
    
    def _get_temporal_context(self, context: Dict[str, Any]) -> Optional[str]:
        """ Get the current date from the context or config metadata. """       
        
        # First try to get it directly from context
        current_date = context.get('current_date')
        
        # If not found directly, try from config metadata
        if not current_date and 'config' in context and 'metadata' in context['config']:
            config_metadata = context['config']['metadata']
            current_date = config_metadata.get('current_date')
        
        return current_date
    
    def generate_plan(self, goal: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """ Generate a plan for a given goal using the language model. """

        # Get available tools for planning
        tools = context.get('available_tools', [])
        
        # Get temporal context
        current_date = self._get_temporal_context(context)
        
        # Log availability of temporal context
        if not current_date:
            self.logger.warning("No temporal context found in planning context")
        
        # Create detailed tool descriptions with parameter schemas
        tool_details = []
        for tool in tools:
            schema = tool.get_schema() if hasattr(tool, 'get_schema') else {}
            tool_detail = f"- {tool.name}: {tool.description}\n"
            
            # Add parameter details if available
            if 'parameters' in schema:
                tool_detail += "  Parameters:\n"
                for param_name, param_info in schema['parameters'].items():
                    required = param_info.get('required', False)
                    req_text = "REQUIRED" if required else "optional"
                    tool_detail += f"    - {param_name} ({req_text}): {param_info.get('description', '')}\n"
                    
                    # Add enum values if available
                    if 'enum' in param_info:
                        tool_detail += f"      Allowed values: {', '.join(str(v) for v in param_info['enum'])}\n"
            
            # Add example if available
            if 'example' in schema:
                tool_detail += f"  Example: {schema['example']}\n"
                
            tool_details.append(tool_detail)
        
        tool_descriptions = "\n".join(tool_details)
        
        # Get conversation history for context
        conversation_history = context.get('conversation_history', '')
        
        # Construct prompt for the LLM
        system_message = SYSTEM_GENERATE.format(
                                current_date=current_date, 
                                storage_path=self.config.blob_storage_path)

        # Log the full system message for debugging
        self.logger.info(f"System message for planning: {system_message}")

        user_message = USER_PLAN.format(
            goal=goal,
            tool_descriptions=tool_descriptions,
            conversation_history=conversation_history,
            few_shot_examples=TOOLS_FEW_SHOT_EXAMPLES
        )

        self.logger.info(f"User message for planning: {user_message}")
        
        # Generate a plan using the LLM
        self.logger.info(f"Generating plan for goal: {goal}")
        
        try:
            response = self.client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", self.config.model_name),
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            # Extract and return the plan
            content = response.choices[0].message.content

            self.logger.info(f"Received plan response: {content}")  
            
            try:
                plan_data = json.loads(content)
                self.logger.info(f"Successfully generated plan with {len(plan_data.get('plan', []))} steps")

                self.event_queue.add_planning(
                    goal=goal,
                    plan=plan_data.get('plan', []),
                    reasoning=plan_data.get('reasoning', 'No reasoning provided'),
                )

                return plan_data
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse plan JSON: {e}. Response content: {content}")
                # Return a basic error plan

                self.event_queue.add_error(
                    goal=goal,
                    error="error parsing plan",
                )

                return {
                    "plan": [
                        {
                            "description": "Error parsing plan",
                            "tool_name": None,
                            "tool_args": None
                        }
                    ],
                    "reasoning": f"Error: {str(e)}"
                }
                
        except Exception as e:
            self.logger.error(f"Error generating plan: {str(e)}")
            # Return a basic error plan
            return {
                "plan": [
                    {
                        "description": "Error generating plan",
                        "tool_name": None,
                        "tool_args": None
                    }
                ],
                "reasoning": f"Error: {str(e)}"
            }
    
    def generate_response(self, message: str, context: Dict[str, Any]) -> str:
        """
        Generate a response to a user message.
        
        Args:
            message: The user message to respond to
            context: Additional context information
            
        Returns:
            Generated response text
        """
        # Get conversation history for context
        conversation_history = context.get('conversation_history', '')
        current_plan = context.get('current_plan', None)
        
        # Get temporal context
        current_date = self._get_temporal_context(context)
        
        # Construct prompt for the LLM
        system_message = textwrap.dedent("""
            You are an AI assistant that helps users accomplish tasks.
            Respond to the user's message based on the conversation history and current plan.
            Be helpful, informative, and concise.
        """)
        
        # Add temporal context to the system message if available
        if current_date:
            system_message += f"\nToday's date is {current_date}. When processing queries about any other time-relative terms use this information as your reference point."
            self.logger.info("Added temporal context to response system message")
        
        # Log the full system message for debugging
        self.logger.debug(f"System message for response: {system_message}")

        user_message = USER_GENERATE.format(
            message=message,
            conversation_history=conversation_history
        )
        
        if current_plan:
            plan_str = textwrap.dedent(f"""
                CURRENT PLAN:
                Goal: {current_plan.goal}
                Status: {current_plan.status.value}
                Steps:
            """)
            for i, step in enumerate(current_plan.steps, 1):
                plan_str += f"{i}. [{step.status.value}] {step.description}\n"
                if step.tool_name:
                    plan_str += f"   Tool: {step.tool_name}\n"
                if step.result:
                    plan_str += f"   Result: {step.result}\n"
                if step.error:
                    plan_str += f"   Error: {step.error}\n"
            
            user_message += plan_str
        
        # Generate a response using the LLM
        self.logger.info(f"Generating response for message: {message}")
        
        try:
            response = self.client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", self.config.model_name),
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            # Extract and return the response
            content = response.choices[0].message.content
            
            self.logger.info(f"Final Solution: {content}")
            return content
                
        except Exception as e:
            self.logger.error(f"Error generating response: {str(e)}")
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a text.
        
        Args:
            text: The text to estimate tokens for
            
        Returns:
            Estimated number of tokens
        """
        if self._tokenizer:
            return len(self._tokenizer.encode(text))
        else:
            # Fallback estimation (rough approximation)
            return len(text) // 4
    
    def reevaluate_plan(self, goal: str, current_plan: Dict[str, Any], 
                       executed_steps: List[Dict[str, Any]], 
                       last_step_result: Any, 
                       context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reevaluate and potentially modify the current plan based on the results of the last executed step.
        """
        
        # Get temporal context
        current_date = self._get_temporal_context(context)

        # Get available tools for planning
        tools = context.get('available_tools', [])
        
        # Create detailed tool descriptions with parameter schemas
        tool_details = []
        for tool in tools:
            schema = tool.get_schema() if hasattr(tool, 'get_schema') else {}
            tool_detail = f"- {tool.name}: {tool.description}\n"
            
            # Add parameter details if available
            if 'parameters' in schema:
                tool_detail += "  Parameters:\n"
                for param_name, param_info in schema['parameters'].items():
                    required = param_info.get('required', False)
                    req_text = "REQUIRED" if required else "optional"
                    tool_detail += f"    - {param_name} ({req_text}): {param_info.get('description', '')}\n"
                    
                    # Add enum values if available
                    if 'enum' in param_info:
                        tool_detail += f"      Allowed values: {', '.join(str(v) for v in param_info['enum'])}\n"
            
            tool_details.append(tool_detail)
        
        tool_descriptions = "\n".join(tool_details)
        
        # Format executed steps
        executed_steps_str = ""
        for i, step in enumerate(executed_steps, 1):
            executed_steps_str += f"{i}. {step.get('description', 'Unknown step')}\n"
            if step.get('tool_name'):
                executed_steps_str += f"   Tool: {step.get('tool_name')}\n"
                if step.get('tool_args'):
                    executed_steps_str += f"   Args: {step.get('tool_args')}\n"
            if step.get('result'):
                executed_steps_str += f"   Result: {step.get('result')}\n"
            if step.get('error'):
                executed_steps_str += f"   Error: {step.get('error')}\n"
        
        # Format remaining steps
        remaining_steps = current_plan.get('plan', [])[len(executed_steps):]
        remaining_steps_str = ""
        for i, step in enumerate(remaining_steps, len(executed_steps) + 1):
            remaining_steps_str += f"{i}. {step.get('description', 'Unknown step')}\n"
            if step.get('tool_name'):
                remaining_steps_str += f"   Tool: {step.get('tool_name')}\n"
                if step.get('tool_args'):
                    remaining_steps_str += f"   Args: {step.get('tool_args')}\n"
        
        self.logger.info(f"blob_storage_path: {self.config.blob_storage_path}")

        # Construct prompt for the LLM
        system_message = SYSTEM_REPLAN.format(
                                current_date=current_date, 
                                storage_path=self.config.blob_storage_path)
             
        self.logger.info(f"current_plan: {json.dumps(current_plan, indent=2)}")

        user_message = USER_REPLAN.format(
            goal=goal,
            tool_descriptions=tool_descriptions,
            executed_steps_str=executed_steps_str,
            last_step_result=last_step_result,
            remaining_steps_str=remaining_steps_str,
            reasoning=current_plan.get('metadata').get('reasoning', 'No reasoning provided')
        )
        
        # Generate an updated plan using the LLM
        self.logger.info(f"Reevaluating plan for goal: {goal} after step execution")
        self.logger.info(f"user_message: {user_message}")
        
        try:
            response = self.client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", self.config.model_name),
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            # Extract and parse the response
            content = response.choices[0].message.content
            self.logger.info(f"Received plan reevaluation response: {content}")
            
            try:
                reevaluation_data = json.loads(content)
                
                # If plan needs adjustment, return the updated plan
                if reevaluation_data.get('plan_needs_adjustment', False):
                    self.logger.info("Plan adjustment needed - returning updated plan")
                    
                    # The executed_steps are already in the correct dictionary format
                    # We just need to safely combine them with the updated_plan
                    final_plan = {
                        "plan": executed_steps + reevaluation_data.get('updated_plan', []),
                        "reasoning": reevaluation_data.get('reasoning', 'No reasoning provided for adjustment')
                    }

                    self.event_queue.add_planning(
                        goal=goal,
                        plan=final_plan.get('plan', []),
                        reasoning=final_plan.get('reasoning', 'No reasoning provided'),
                    )
                    return final_plan
                else:
                    self.logger.info("No plan adjustment needed - returning original plan")
                    return current_plan
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse reevaluation JSON: {e}. Response content: {content}")
                # Return the original plan if we can't parse the response
                return current_plan
                
        except Exception as e:
            self.logger.error(f"Error reevaluating plan: {str(e)}")
            # Return the original plan if there's an error
            return current_plan