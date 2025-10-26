"""
Natural Language Processor for JARVIS
Uses GPT-4o-mini to understand natural language and call appropriate functions
"""
import json
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
import httpx
from function_registry import FunctionRegistry


class NaturalLanguageProcessor:
    """
    Natural language understanding using GPT-4o-mini
    Converts natural language commands to function calls
    """

    def __init__(self, api_key: str, function_registry: FunctionRegistry,
                 model: str = "gpt-4o-mini", verbosity: str = "balanced"):
        """
        Initialize NLU processor

        Args:
            api_key: OpenAI API key
            function_registry: FunctionRegistry instance
            model: GPT model to use (default: gpt-4o-mini)
            verbosity: Response verbosity ('concise', 'balanced', 'detailed')
        """
        self.function_registry = function_registry
        self.model = model
        self.verbosity = verbosity
        self.client = self._create_client(api_key) if api_key else None
        self.conversation_history = []

        # System prompt for JARVIS personality
        self.system_prompt = self._build_system_prompt()

    def _create_client(self, api_key: str) -> OpenAI:
        """Create OpenAI client with proper configuration"""
        http_client = httpx.Client(
            timeout=60.0,
            follow_redirects=True
        )
        return OpenAI(api_key=api_key, http_client=http_client)

    def update_api_key(self, api_key: str):
        """Update the API key"""
        self.client = self._create_client(api_key) if api_key else None

    def update_model(self, model: str):
        """Update the GPT model"""
        self.model = model

    def update_verbosity(self, verbosity: str):
        """Update response verbosity"""
        self.verbosity = verbosity
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build system prompt for JARVIS personality"""
        verbosity_instructions = {
            "concise": "Keep responses very brief - one sentence or a few words when possible. Only provide essential information.",
            "balanced": "Provide clear, helpful responses without unnecessary detail. Strike a balance between brevity and completeness.",
            "detailed": "Provide comprehensive responses with explanations and context when helpful."
        }

        return f"""You are JARVIS, an intelligent AI assistant helping control a Windows PC.

Your personality:
- Professional, efficient, and helpful like Tony Stark's JARVIS
- Friendly but not overly casual
- Confident in your capabilities
- Proactive in offering suggestions when appropriate

Your capabilities:
- Window management (move, resize, minimize, maximize windows across multiple monitors)
- Application control (launch, switch, close applications)
- System control (volume, audio settings)
- Automation (keyboard/mouse control, typing, clicking)
- File system operations (open folders, search files, create folders)
- Clipboard management
- Information queries (time, date, system info, monitor info)

Monitor setup:
- Monitor 1 (Left): Vertical monitor - supports top, bottom, or full positions
- Monitor 3 (Center): Horizontal monitor - typically used for fullscreen/maximized windows
- Monitor 2 (Right): Vertical monitor - supports top, bottom, or full positions

Response style:
{verbosity_instructions.get(self.verbosity, verbosity_instructions['balanced'])}

Guidelines:
- When asked to do something, use the available functions to accomplish it
- If a request is ambiguous, ask for clarification
- If something fails, explain why and suggest alternatives
- If asked a question you can't answer with functions, respond conversationally
- Use natural, conversational language in your responses
- When confirming actions, mention what was done (e.g., "Moved Chrome to the top of monitor 1")
- If multiple steps are needed, chain function calls and provide a summary

Remember: You're helping the user control their computer efficiently and naturally."""

    def add_to_conversation_history(self, role: str, content: Any):
        """
        Add a message to conversation history

        Args:
            role: Message role ('user', 'assistant', 'function', 'tool')
            content: Message content
        """
        # Limit history size (keep last 20 messages)
        if len(self.conversation_history) > 20:
            # Keep system prompt and recent messages
            self.conversation_history = self.conversation_history[-20:]

        if isinstance(content, dict):
            self.conversation_history.append({
                "role": role,
                "content": json.dumps(content) if role == "function" else content
            })
        else:
            self.conversation_history.append({
                "role": role,
                "content": content
            })

    def clear_conversation_history(self):
        """Clear conversation history (for new session)"""
        self.conversation_history = []

    def process_command(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Process natural language command

        Args:
            text: User's natural language input

        Returns:
            Tuple of (response_text, function_results)
        """
        if not self.client:
            return "API key not configured. Please set your OpenAI API key.", []

        try:
            # Add user message to history
            self.add_to_conversation_history("user", text)

            # Prepare messages for API call
            messages = [
                {"role": "system", "content": self.system_prompt}
            ] + self.conversation_history

            # Get function definitions
            functions = self.function_registry.get_function_definitions()

            # Call GPT with function calling
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[{"type": "function", "function": func} for func in functions],
                tool_choice="auto"
            )

            # Process response
            response_message = response.choices[0].message
            function_results = []

            # Check if GPT wants to call functions
            if response_message.tool_calls:
                # Execute all function calls
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    print(f"Executing function: {function_name} with args: {function_args}")

                    # Execute the function
                    result = self.function_registry.execute_function(
                        function_name,
                        function_args
                    )
                    function_results.append({
                        "function": function_name,
                        "arguments": function_args,
                        "result": result
                    })

                    # Add function call and result to conversation history
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call]
                    })

                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": json.dumps(result)
                    })

                # Get final response from GPT after function execution
                messages = [
                    {"role": "system", "content": self.system_prompt}
                ] + self.conversation_history

                second_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages
                )

                final_response = second_response.choices[0].message.content
                self.add_to_conversation_history("assistant", final_response)

                return final_response, function_results

            else:
                # No function calls - just conversational response
                response_text = response_message.content
                self.add_to_conversation_history("assistant", response_text)

                return response_text, []

        except Exception as e:
            error_msg = f"Error processing command: {str(e)}"
            print(error_msg)
            return f"I encountered an error: {str(e)}", []

    def process_question(self, text: str) -> str:
        """
        Process a conversational question (no function calls needed)

        Args:
            text: User's question

        Returns:
            Response text
        """
        try:
            # Add to history
            self.add_to_conversation_history("user", text)

            # Prepare messages
            messages = [
                {"role": "system", "content": self.system_prompt}
            ] + self.conversation_history

            # Call GPT without function calling
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )

            response_text = response.choices[0].message.content
            self.add_to_conversation_history("assistant", response_text)

            return response_text

        except Exception as e:
            return f"I encountered an error: {str(e)}"

    def is_configured(self) -> bool:
        """Check if API key is configured"""
        return self.client is not None

    def get_context_info(self) -> Dict[str, Any]:
        """
        Get information about current conversation context

        Returns:
            Dictionary with context information
        """
        return {
            "message_count": len(self.conversation_history),
            "model": self.model,
            "verbosity": self.verbosity
        }
