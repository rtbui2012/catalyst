"""
LLM Manager for Agentic Core.

This module provides the LLMManager class, which orchestrates interactions
with a configured language model (LLM) provider through an abstraction layer.
It handles planning, response generation, plan reevaluation, and token estimation.
"""

import logging
import json
import textwrap
from typing import List, Dict, Any, Optional, Tuple

# LLM Abstraction and Concrete Implementation
from .llm_base import BaseLLM
from .llm_azure import AzureOpenAILLM
from .llm_gemini import GeminiLLM # Add Gemini import
from .config import AgentConfig
from .utils import setup_logger
from .event_queue import EventQueue # Import EventQueue

from .config import AgentConfig
from .utils import setup_logger

from catalyst_agent.utils.prompt_templates import (
    SYSTEM_GENERATE,
    SYSTEM_REPLAN,
    USER_PLAN,
    TOOLS_FEW_SHOT_EXAMPLES,
    USER_GENERATE,
    USER_REPLAN,
    PLACEHOLDER_INSTRUCTION
)

class LLMManager:
    """
    Manager for LLM interactions in the Agentic Core.
    """

    def __init__(self, config: AgentConfig, event_queue: Optional[EventQueue] = None, llm_client: Optional[BaseLLM] = None):
        """Initialize the LLM manager."""
        self.config = config
        self.logger = setup_logger('agentic.llm',
                                  logging.DEBUG if config.verbose else logging.INFO)
        self.event_queue = event_queue or EventQueue()

        # Initialize the LLM client
        if llm_client:
            self.llm_client = llm_client
            self.logger.info(f"Using provided LLM client: {type(llm_client).__name__}")
        else:
            llm_provider = getattr(config, 'llm_provider', 'azure').lower()
            self.logger.info(f"No LLM client provided, initializing based on config: LLM_PROVIDER='{llm_provider}'")
            try:
                if llm_provider == 'gemini':
                    self.llm_client = GeminiLLM()
                    self.logger.info("Initialized GeminiLLM client.")
                elif llm_provider == 'azure':
                    self.llm_client = AzureOpenAILLM(config, self.logger)
                    self.logger.info("Initialized AzureOpenAILLM client.")
                else:
                    raise ValueError(f"Unsupported LLM provider: {llm_provider}")
            except Exception as e:
                self.logger.error(f"Failed to initialize {llm_provider.upper()} LLM client: {e}")
                raise ValueError(f"LLM client initialization failed for provider {llm_provider}.") from e

        self.logger.info(f"LLM Manager initialized with model: {self.llm_client.model_name}")

        # Initialize current date
        if not hasattr(self.config, 'metadata') or self.config.metadata is None:
            self.config.metadata = {}
        if 'current_date' not in self.config.metadata:
            import datetime
            current_date = datetime.datetime.now().strftime("%B %d, %Y")
            self.config.metadata['current_date'] = current_date
            self.logger.info(f"Initialized default current_date in LLMManager: {current_date}")


    def _get_temporal_context(self, context: Dict[str, Any]) -> Optional[str]:
        """ Get the current date from the context or config metadata. """
        current_date = context.get('current_date')
        if not current_date and 'config' in context and 'metadata' in context['config']:
            config_metadata = context['config']['metadata']
            current_date = config_metadata.get('current_date')
        return current_date

    def _format_tool_descriptions(self, tools: List[Any]) -> str:
        """ Formats tool descriptions including parameters for the LLM prompt. """
        tool_details = []
        for tool in tools:
            schema = tool.get_schema() if hasattr(tool, 'get_schema') else {}
            tool_detail = f"- {tool.name}: {tool.description}\n"
            if 'parameters' in schema:
                tool_detail += "  Parameters:\n"
                for param_name, param_info in schema['parameters'].items():
                    required = param_info.get('required', False)
                    req_text = "REQUIRED" if required else "optional"
                    tool_detail += f"    - {param_name} ({req_text}): {param_info.get('description', '')}\n"
                    if 'enum' in param_info:
                        tool_detail += f"      Allowed values: {', '.join(str(v) for v in param_info['enum'])}\n"
            if 'example' in schema:
                tool_detail += f"  Example: {schema['example']}\n"
            tool_details.append(tool_detail)
        return "\n".join(tool_details)


    def generate_plan(self, goal: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """ Generate a plan for a given goal using the language model. """
        tools = context.get('available_tools', [])
        current_date = self._get_temporal_context(context)
        if not current_date: self.logger.warning("No temporal context found in planning context")
        tool_descriptions = self._format_tool_descriptions(tools)
        conversation_history = context.get('conversation_history', '')

        system_message = SYSTEM_GENERATE.format(
                                current_date=current_date,
                                storage_path=self.config.blob_storage_path) + PLACEHOLDER_INSTRUCTION

        self.logger.info(f"System message for planning: {system_message}")
        user_message = USER_PLAN.format(
            goal=goal,
            tool_descriptions=tool_descriptions,
            conversation_history=conversation_history,
            few_shot_examples=TOOLS_FEW_SHOT_EXAMPLES
        )
        self.logger.info(f"User message for planning: {user_message}")
        self.logger.info(f"Generating plan for goal: {goal}")

        try:
            response_dict = self.llm_client.chat_completion(
                messages=[{"role": "system", "content": system_message}, {"role": "user", "content": user_message}],
                response_format={"type": "json_object"},
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            content = response_dict['choices'][0]['message']['content']

            extracted_json = content
            if content.strip().startswith("```json"): extracted_json = content.split("```json")[1].split("```")[0].strip()
            elif content.strip().startswith("```"): extracted_json = content.split("```")[1].split("```")[0].strip()

            try:
                plan_data = json.loads(extracted_json)
                # Standardize internal key to 'plan' and ensure it's a list
                plan_list = None
                if isinstance(plan_data, list):
                    plan_list = plan_data
                    plan_data = {"plan": plan_list, "reasoning": "Plan generated as a list."} # Wrap list in dict
                elif isinstance(plan_data, dict):
                    if 'plan' in plan_data and isinstance(plan_data['plan'], list):
                        plan_list = plan_data['plan']
                    elif 'steps' in plan_data and isinstance(plan_data['steps'], list):
                        plan_list = plan_data.pop('steps') # Get steps and remove 'steps' key
                        plan_data['plan'] = plan_list # Add as 'plan' key
                    else:
                        plan_data['plan'] = [] # Ensure 'plan' key exists if neither found
                else:
                    # If not list or dict, treat as invalid
                     raise ValueError("Parsed JSON is not a list or dictionary.")

                self.logger.info(f"Successfully parsed plan JSON with {len(plan_data.get('plan', []))} steps")
                self.event_queue.add_planning(goal=goal, plan=plan_data.get('plan', []), reasoning=plan_data.get('reasoning', 'No reasoning provided'))
                return plan_data
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.error(f"Failed to parse plan JSON or invalid structure: {e}. Raw LLM response content:\n---\n{content}\n---")
                self.event_queue.add_error(goal=goal, error="error parsing plan")
                return {"plan": [{"description": "Error parsing plan", "tool_name": None, "tool_args": None}], "reasoning": f"Error: {str(e)}"}

        except Exception as e:
            self.logger.error(f"Error generating plan: {str(e)}")
            return {"plan": [{"description": "Error generating plan", "tool_name": None, "tool_args": None}], "reasoning": f"Error: {str(e)}"}

    def generate_response(self, message: str, context: Dict[str, Any]) -> str:
        """ Generate a response to a user message. """
        conversation_history = context.get('conversation_history', '')
        current_plan = context.get('current_plan', None)
        current_date = self._get_temporal_context(context)

        system_message = textwrap.dedent("""
            You are an AI assistant that helps users accomplish tasks.
            Respond to the user's message based on the conversation history and current plan.
            Be helpful, informative, and concise.
        """)
        if current_date: system_message += f"\nToday's date is {current_date}."
        self.logger.debug(f"System message for response: {system_message}")

        user_message = USER_GENERATE.format(message=message, conversation_history=conversation_history)

        is_default_plan = (current_plan and len(current_plan.steps) == 1 and
                           current_plan.steps[0].description == "Analyze the request and respond to the user" and
                           current_plan.steps[0].tool_name is None)

        if current_plan and not is_default_plan:
            self.logger.info("Including non-default plan details in response generation prompt.")
            plan_str = textwrap.dedent(f"CURRENT PLAN:\nGoal: {current_plan.goal}\nStatus: {current_plan.status.value}\nSteps:\n")
            for i, step in enumerate(current_plan.steps, 1):
                plan_str += f"{i}. [{step.status.value}] {step.description}\n"
                if step.tool_name: plan_str += f"   Tool: {step.tool_name}\n"
                if step.result and step.result != "Step completed successfully": plan_str += f"   Result: {step.result}\n"
                if step.error: plan_str += f"   Error: {step.error}\n"
            user_message += "\n\n" + plan_str
        elif is_default_plan:
             self.logger.info("Skipping default plan details in response generation prompt.")

        self.logger.info(f"Generating response for message: {message}")
        try:
            response_dict = self.llm_client.chat_completion(
                messages=[{"role": "system", "content": system_message}, {"role": "user", "content": user_message}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            content = response_dict['choices'][0]['message']['content']
            self.logger.info(f"Final Solution: {content}")
            return content
        except Exception as e:
            self.logger.error(f"Error generating response: {str(e)}")
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"

    def estimate_tokens(self, text: str) -> int:
        """ Estimate the number of tokens in a text using the configured LLM client. """
        return self.llm_client.estimate_tokens(text)

    def reevaluate_plan(self, goal: str, current_plan: Dict[str, Any],
                       executed_steps: List[Dict[str, Any]],
                       last_step_result: Any,
                       context: Dict[str, Any]) -> Dict[str, Any]: # Return only the plan dict
        """
        Reevaluate and potentially modify the current plan based on the results of the last executed step.
        Returns the plan dictionary that should be used going forward (either original or updated).
        """
        current_date = self._get_temporal_context(context)
        tools = context.get('available_tools', [])
        tool_descriptions = self._format_tool_descriptions(tools)

        # Format executed steps
        executed_steps_str = ""
        for i, step in enumerate(executed_steps, 1):
            executed_steps_str += f"{i}. {step.get('description', 'Unknown step')}\n"
            if step.get('tool_name'): executed_steps_str += f"   Tool: {step.get('tool_name')}\n"
            if step.get('tool_args'): executed_steps_str += f"   Args: {step.get('tool_args')}\n"
            if step.get('result'): executed_steps_str += f"   Result: {step.get('result')}\n"
            if step.get('error'): executed_steps_str += f"   Error: {step.get('error')}\n"

        # Format remaining steps from the *current* plan dict passed in
        remaining_steps = current_plan.get('plan', [])[len(executed_steps):]
        remaining_steps_str = ""
        for i, step in enumerate(remaining_steps, len(executed_steps) + 1):
            remaining_steps_str += f"{i}. {step.get('description', 'Unknown step')}\n"
            if step.get('tool_name'): remaining_steps_str += f"   Tool: {step.get('tool_name')}\n"
            if step.get('tool_args'): remaining_steps_str += f"   Args: {step.get('tool_args')}\n"

        self.logger.info(f"blob_storage_path: {self.config.blob_storage_path}")

        # Construct prompt for the LLM with placeholder instruction
        system_message = SYSTEM_REPLAN.format(
                                current_date=current_date,
                                storage_path=self.config.blob_storage_path) + PLACEHOLDER_INSTRUCTION

        self.logger.info(f"Current plan dict passed to reevaluate_plan: {json.dumps(current_plan, indent=2)}")
        user_message = USER_REPLAN.format(
            goal=goal,
            tool_descriptions=tool_descriptions,
            executed_steps_str=executed_steps_str,
            last_step_result=last_step_result,
            remaining_steps_str=remaining_steps_str,
            reasoning=current_plan.get('metadata', {}).get('reasoning', 'No reasoning provided')
        )

        self.logger.info(f"Reevaluating plan for goal: {goal} after step execution")
        self.logger.info(f"User message for reevaluation: {user_message}")

        try:
            response_dict = self.llm_client.chat_completion(
                messages=[{"role": "system", "content": system_message}, {"role": "user", "content": user_message}],
                response_format={"type": "json_object"},
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            content = response_dict['choices'][0]['message']['content']
            self.logger.info(f"Received plan reevaluation response: {content}")

            try:
                reevaluation_data = json.loads(content)

                # --- Robust check for valid plan structure ---
                updated_plan_steps = None
                plan_key_used = None
                final_plan_dict = None
                new_reasoning = None

                if isinstance(reevaluation_data, list):
                    # Handle case where the root is the list of steps
                    updated_plan_steps = reevaluation_data
                    plan_key_used = '(root list)'
                    new_reasoning = current_plan.get('metadata', {}).get('reasoning', 'Plan updated from list response.')
                    final_plan_dict = {"plan": updated_plan_steps, "reasoning": new_reasoning}

                elif isinstance(reevaluation_data, dict):
                    # Handle case where response is an object
                    if 'plan' in reevaluation_data and isinstance(reevaluation_data['plan'], list):
                        updated_plan_steps = reevaluation_data['plan']
                        plan_key_used = 'plan'
                    elif 'steps' in reevaluation_data and isinstance(reevaluation_data['steps'], list):
                        updated_plan_steps = reevaluation_data['steps']
                        plan_key_used = 'steps'

                    if updated_plan_steps is not None:
                         # Construct the final plan dict from the object
                         new_reasoning = reevaluation_data.get('reasoning', 'No reasoning provided for adjustment')
                         final_plan_dict = {
                             "plan": updated_plan_steps,
                             "reasoning": new_reasoning
                         }
                         # Preserve/merge metadata
                         if 'metadata' in current_plan:
                              final_plan_dict['metadata'] = current_plan['metadata']
                         if 'metadata' in reevaluation_data:
                              final_plan_dict.setdefault('metadata', {}).update(reevaluation_data['metadata'])
                         if 'reasoning' in final_plan_dict: # Update reasoning specifically in metadata
                              final_plan_dict.setdefault('metadata', {})['reasoning'] = final_plan_dict['reasoning']

                # If a valid structure was found and parsed
                if final_plan_dict and updated_plan_steps is not None:
                    self.logger.info(f"LLM provided a valid plan structure (key: '{plan_key_used}'). Using this structure.")
                    # Ensure the 'plan' key exists in the final dict
                    if 'plan' not in final_plan_dict: final_plan_dict['plan'] = updated_plan_steps

                    self.event_queue.add_planning(
                        goal=goal,
                        plan=final_plan_dict.get('plan', []),
                        reasoning=final_plan_dict.get('reasoning', 'No reasoning provided'),
                    )
                    return final_plan_dict # Return the potentially updated plan dict
                else:
                    # If the LLM response didn't contain a valid structure
                    self.logger.warning("LLM reevaluation response lacked a valid plan structure ('plan'/'steps' list or root list). Returning original plan.")
                    return current_plan # Return original plan dict

            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse reevaluation JSON: {e}. Response content: {content}")
                return current_plan # Return original plan dict on parsing error

        except Exception as e:
            self.logger.error(f"Error reevaluating plan: {str(e)}")
            return current_plan # Return original plan dict on general error