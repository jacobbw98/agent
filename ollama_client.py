"""
Ollama Client - Wrapper for Ollama API with tool-calling support.
"""
import json
import ollama
from typing import Generator, Optional, Callable

DEFAULT_MODEL = "nemotron-3-nano:latest"

SYSTEM_PROMPT = """You are a helpful AI assistant with access to tools.

To use a tool, reply with JSON in this format:
```tool_call
{"tool": "tool_name", "args": {"arg1": "value"}}
```

IMPORTANT RULES:
1. Use SINGLE backslashes in paths like: C:\\Users\\Jacob\\Desktop
2. After receiving a tool result, SUMMARIZE the result for the user - do NOT call another tool unless absolutely necessary
3. If the task is complete, just respond normally without any tool call

Available tools:
- file_list(path) - List directory contents
- file_read(path) - Read file contents
- file_write(path, content) - Write to file
- browser_navigate(url) - Open a URL
- browser_click(selector) - Click element
- browser_type(text) - Type text
- screenshot() - Take screenshot
- game_focus_window(window_title) - Focus a window
- game_send_key(key) - Send keyboard input

Example - List files:
User: List files in C:\\Users\\Jacob\\Desktop
Assistant:
```tool_call
{"tool": "file_list", "args": {"path": "C:\\Users\\Jacob\\Desktop"}}
```

After tool returns results, SUMMARIZE them for the user."""


class OllamaClient:
    """Client for interacting with Ollama API."""
    
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.client = ollama.Client()
        self.conversation_history = []
    
    def reset_conversation(self):
        """Clear conversation history."""
        self.conversation_history = []
    
    def chat(self, message: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        """Send a message and get a response."""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": message})
        
        # Options for nemotron - disable thinking traces for cleaner output
        options = {
            "num_predict": 1024,  # Max tokens
        }
        
        response = self.client.chat(
            model=self.model,
            messages=messages,
            options=options
        )
        
        assistant_message = response["message"]["content"]
        
        # Strip thinking traces if present (nemotron outputs these)
        if "...done thinking." in assistant_message:
            parts = assistant_message.split("...done thinking.")
            if len(parts) > 1:
                assistant_message = parts[-1].strip()
        
        # Update conversation history
        self.conversation_history.append({"role": "user", "content": message})
        self.conversation_history.append({"role": "assistant", "content": assistant_message})
        
        return assistant_message
    
    def chat_stream(self, message: str, system_prompt: str = SYSTEM_PROMPT) -> Generator[str, None, None]:
        """Send a message and stream the response."""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": message})
        
        full_response = ""
        
        for chunk in self.client.chat(
            model=self.model,
            messages=messages,
            stream=True
        ):
            content = chunk["message"]["content"]
            full_response += content
            yield content
        
        # Update conversation history after streaming completes
        self.conversation_history.append({"role": "user", "content": message})
        self.conversation_history.append({"role": "assistant", "content": full_response})
    
    def add_tool_result(self, tool_name: str, result: str):
        """Add a tool result to the conversation."""
        self.conversation_history.append({
            "role": "user",
            "content": f"Tool `{tool_name}` returned:\n```\n{result}\n```\n\nContinue with the task."
        })
    
    def parse_tool_call(self, response: str) -> Optional[dict]:
        """Extract tool call from response if present."""
        import re
        
        # Look for ```tool_call ... ``` blocks
        pattern = r"```tool_call\s*\n?(.*?)\n?```"
        match = re.search(pattern, response, re.DOTALL)
        
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                return None
        
        return None


def list_models() -> list[str]:
    """List available Ollama models."""
    client = ollama.Client()
    models = client.list()
    return [m["name"] for m in models.get("models", [])]


if __name__ == "__main__":
    # Quick test
    print("Available models:", list_models())
    client = OllamaClient()
    response = client.chat("Hello! What tools do you have available?")
    print("Response:", response)
