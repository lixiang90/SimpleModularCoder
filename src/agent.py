import json
import os
import re
from typing import List, Dict, Any
from openai import OpenAI
from .session import Session
from .types import Message
from .tools import TOOL_DEFINITIONS, ToolSet

class DeepSeekLLM:
    """
    Wrapper for DeepSeek API (OpenAI Compatible)
    """
    def __init__(self, config_path: str = "llm_config.json"):
        # Determine the absolute path to the config file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Try finding config in the same directory as this file
        target_path = os.path.join(base_dir, "..", config_path) # if running from root and file in opencode-basic
        if not os.path.exists(target_path):
             target_path = os.path.join(base_dir, config_path)
             
        if not os.path.exists(target_path):
             # Fallback to direct path if provided or just try opening
             target_path = config_path
             
        try:
            with open(target_path, 'r') as f:
                config = json.load(f)
            self.client = OpenAI(
                api_key=config['api_key'],
                base_url=config['base_url']
            )
            self.model = config['model']
            self.temperature = config.get('temperature', 1.0)
        except Exception as e:
            print(f"Error loading config or initializing client: {e}")
            raise

    def generate(self, messages: List[Dict[str, Any]]) -> Message:
        print(f"\n[LLM] Thinking...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                temperature=self.temperature
            )
            
            choice = response.choices[0]
            msg_data = choice.message
            
            # Convert OpenAI response object to our Message type
            tool_calls_data = None
            if msg_data.tool_calls:
                tool_calls_data = []
                for tc in msg_data.tool_calls:
                    tool_calls_data.append({
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    })
            
            return Message(
                role=msg_data.role,
                content=msg_data.content,
                tool_calls=tool_calls_data
            )
        except Exception as e:
            print(f"[LLM Error]: {e}")
            return Message(role="assistant", content=f"Error communicating with LLM: {e}")

class Agent:
    def __init__(self, base_dir: str, system_prompt: str = "You are a helpful coding assistant."):
        self.session = Session(system_prompt)
        # Try to load config from current directory or package directory
        self.llm = DeepSeekLLM("llm_config.json")
        self.running = True
        
        # Initialize ToolSet with the specified base directory
        self.tool_set = ToolSet(base_dir)
        print(f"Agent initialized with workspace: {self.tool_set.base_dir}")

    def run(self, user_input: str):
        """
        Agent Loop: User Input -> Think -> (Act -> Think)* -> Reply
        Returns the final response content from the assistant.
        """
        # 1. Add user message
        self.session.add_user_message(user_input)

        last_content = None

        # 2. Loop
        while self.running:
            # Get context
            context = self.session.get_context()
            
            # Call LLM
            response = self.llm.generate(context)
            last_content = response.content
            
            # Add assistant message to history
            self.session.add_assistant_message(response.content, response.tool_calls)
            
            # Print response
            if response.content:
                print(f"[Agent]: {response.content}")
            if response.tool_calls:
                print(f"[Agent] wants to use tools: {[tc['function']['name'] for tc in response.tool_calls]}")

            # 3. Handle tools
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    self._execute_tool(tool_call)
                # Continue loop to show tool output to LLM
                continue
            
            # No tools, break
            break
        
        return last_content

    def _execute_tool(self, tool_call: Dict[str, Any]):
        """
        Execute real tools using ToolSet
        """
        func_name = tool_call['function']['name']
        call_id = tool_call['id']
        args_str = tool_call['function']['arguments']
        
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
             # Attempt 1: Remove Markdown code blocks
             repaired_str = re.sub(r'^```json\s*', '', args_str, flags=re.MULTILINE | re.IGNORECASE)
             repaired_str = re.sub(r'^```\s*', '', repaired_str, flags=re.MULTILINE)
             repaired_str = re.sub(r'\s*```$', '', repaired_str, flags=re.MULTILINE)
             repaired_str = repaired_str.strip()
             
             try:
                 args = json.loads(repaired_str)
                 print(f"\n>>> JSON Repair: Successfully stripped Markdown formatting.")
             except json.JSONDecodeError as e:
                 # Attempt 2: Handle Truncated JSON (specifically for write_file/append_file)
                 if func_name in ['write_file', 'append_file']:
                     # Heuristic: Try to close the JSON string and object
                     # 1. Strip trailing whitespace
                     clean_str = args_str.rstrip()
                     # 2. Remove trailing backslash if present (to avoid escaping the closing quote)
                     if clean_str.endswith('\\'):
                         clean_str = clean_str[:-1]
                     
                     repaired_str = clean_str + '"}'
                     
                     try:
                         args = json.loads(repaired_str)
                         print(f"\n>>> JSON Repair: Detected truncated JSON. Auto-completed quotes/braces.")
                         
                         # Execute the tool with partial arguments
                         if hasattr(self.tool_set, func_name):
                             method = getattr(self.tool_set, func_name)
                             real_output = method(**args)
                             
                             output = (
                                 f"WARNING: The tool call argument was TRUNCATED due to length limits.\n"
                                 f"I have auto-repaired the JSON and executed '{func_name}' with the PARTIAL content.\n"
                                 f"Result: {real_output}\n\n"
                                 f"IMPORTANT: The file is INCOMPLETE. \n"
                                 f"You MUST immediately call 'append_file' to write the REST of the content.\n"
                                 f"Resume exactly from the end of the written content."
                             )
                             print(f"\n>>> Auto-Repair Execution: {output}")
                             self.session.add_tool_output(call_id, func_name, output)
                             return
                     except json.JSONDecodeError:
                         pass # Failed to repair, fall through to error reporting

                 # Attempt 3: Escape unescaped newlines in values (Heuristic)
                 # This handles cases where LLM writes: "content": "Line1\nLine2" as actual newlines
                 # We simply try to escape control characters if they cause issues
                 # But robustly, we'll just stash it for now as requested.
                 
                 # Stash invalid JSON for debugging
                 stash_path = os.path.join(self.tool_set.base_dir, "debug_invalid_json.txt")
                 try:
                     with open(stash_path, "w", encoding="utf-8") as f:
                         f.write(args_str)
                     stash_msg = f"Raw arguments stashed to {stash_path}"
                 except Exception as write_err:
                     stash_msg = f"Failed to stash raw arguments: {write_err}"

                 output = f"Error: Invalid JSON arguments for {func_name}: {e}. {stash_msg}"
                 print(f"\n>>> JSON Error: {output}")
                 self.session.add_tool_output(call_id, func_name, output)
                 return

        print(f"\n>>> Executing Tool: {func_name} with args: {args}")
        
        # Check if the tool exists in our ToolSet instance
        if hasattr(self.tool_set, func_name):
            try:
                # Get the method from the instance
                method = getattr(self.tool_set, func_name)
                # Call it with arguments
                output = method(**args)
            except Exception as e:
                output = f"Error executing {func_name}: {str(e)}"
        else:
            output = f"Error: Tool {func_name} not found"
        
        print(f">>> Tool Output: {output[:100]}..." if len(output) > 100 else f">>> Tool Output: {output}")

        # Add result to session
        self.session.add_tool_output(call_id, func_name, output)
