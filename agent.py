"""
Agent - Main agentic loop with tool execution.
"""
import json
import re
from typing import Dict, Any, Callable, Optional, Generator
from ollama_client import OllamaClient, SYSTEM_PROMPT
from tools.browser import get_browser
from tools.filesystem import get_filesystem
from tools.grading import get_grading
from tools.gamecontrol import get_gamecontrol
from tools.vision import get_vision


class Agent:
    """Agentic AI with tool-calling capabilities."""
    
    def __init__(self, model: str = "nemotron-3-nano:latest"):
        self.client = OllamaClient(model)
        self.tools = self._register_tools()
        self.max_iterations = 10
        self.verbose = True
    
    def _register_tools(self) -> Dict[str, Callable]:
        """Register all available tools."""
        browser = get_browser()
        fs = get_filesystem()
        grading = get_grading()
        game = get_gamecontrol()
        vision = get_vision()
        
        return {
            # Browser tools
            "browser_navigate": lambda url: browser.navigate(url),
            "browser_click": lambda selector=None, x=None, y=None: browser.click(selector, x, y),
            "browser_type": lambda text, selector=None: browser.type_text(text, selector),
            "browser_press_key": lambda key: browser.press_key(key),
            "browser_screenshot": lambda: browser.screenshot(),
            "browser_get_content": lambda: browser.get_content(),
            
            # File system tools
            "file_read": lambda path: fs.read_file(path),
            "file_write": lambda path, content: fs.write_file(path, content),
            "file_list": lambda path: fs.list_directory(path),
            "file_search": lambda directory, pattern: fs.search_files(directory, pattern),
            
            # Grading tools
            "list_rubrics": lambda: grading.list_rubrics(),
            "load_rubric": lambda rubric_name: grading.load_rubric(rubric_name),
            "grade_submission": lambda submission_path, rubric_name: grading.grade_submission(submission_path, rubric_name),
            
            # Game control tools
            "game_list_windows": lambda: game.list_windows(),
            "game_focus_window": lambda window_title: game.focus_window(window_title),
            "game_send_key": lambda key, hold_time=0: game.send_key(key, hold_time),
            "game_send_keys": lambda keys: game.send_keys(keys),
            "game_send_hotkey": lambda *keys: game.send_hotkey(*keys),
            "game_move_mouse": lambda x, y, relative=False: game.move_mouse(x, y, relative),
            "game_click": lambda x=None, y=None, button='left', clicks=1: game.click_mouse(x, y, button, clicks),
            "game_scroll": lambda amount: game.scroll(amount),
            "game_screenshot": lambda: game.screenshot(),
            "game_pixel_color": lambda x, y: game.get_pixel_color(x, y),
            
            # Vision tools
            "screenshot": lambda: vision.save_screenshot("screenshot.png"),
        }
    
    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Execute a tool and return the result."""
        if tool_name not in self.tools:
            return f"Error: Unknown tool '{tool_name}'"
        
        try:
            tool_fn = self.tools[tool_name]
            result = tool_fn(**args)
            return str(result)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"
    
    def parse_tool_call(self, response: str) -> Optional[Dict]:
        """Extract tool call from response."""
        # 1. Try to find ```tool_call ... ``` blocks
        pattern = r"```tool_call\s*\n?(.*?)\n?```"
        match = re.search(pattern, response, re.DOTALL)
        
        json_content = None
        if match:
            json_content = match.group(1).strip()
        else:
            # 2. Key fallback: Look for any JSON-like object if no code block found
            # This helps if the model outputs raw JSON
            json_pattern = r"\{.*\}"
            json_match = re.search(json_pattern, response, re.DOTALL)
            if json_match:
                json_content = json_match.group(0).strip()

        if json_content:
            try:
                data = json.loads(json_content)
                
                # Case A: Our requested format {"tool": "name", "args": {}}
                if "tool" in data:
                    return data
                
                # Case B: OpenAI style {"tool_calls": [{"name": "...", "arguments": {}}]}
                # Some models default to this even if instructed otherwise
                if "tool_calls" in data and isinstance(data["tool_calls"], list):
                    call = data["tool_calls"][0]
                    return {
                        "tool": call.get("name") or call.get("function", {}).get("name"),
                        "args": call.get("arguments") or call.get("function", {}).get("arguments") or {}
                    }
                    
            except json.JSONDecodeError:
                pass
                
        return None
    
    def run(self, task: str) -> Generator[Dict[str, Any], None, None]:
        """
        Run the agent loop for a task.
        Yields status updates for each step.
        """
        self.client.reset_conversation()
        
        yield {"type": "start", "task": task}
        
        # Initial message to LLM
        response = self.client.chat(task)
        if self.verbose:
            print(f"[DEBUG] Raw response: {response}")
        yield {"type": "response", "content": response}
        
        iteration = 0
        while iteration < self.max_iterations:
            # Check for tool call
            tool_call = self.parse_tool_call(response)
            
            if not tool_call:
                # No tool call = task complete
                yield {"type": "complete", "final_response": response}
                break
            
            # Execute tool
            tool_name = tool_call.get("tool", "")
            tool_args = tool_call.get("args", {})
            
            yield {"type": "tool_call", "tool": tool_name, "args": tool_args}
            
            result = self.execute_tool(tool_name, tool_args)
            yield {"type": "tool_result", "tool": tool_name, "result": result}
            
            # Send result back to LLM
            self.client.add_tool_result(tool_name, result)
            response = self.client.chat("Continue with the task based on the tool result.")
            if self.verbose:
                print(f"[DEBUG] Raw response: {response}")
            yield {"type": "response", "content": response}
            
            iteration += 1
        
        if iteration >= self.max_iterations:
            yield {"type": "max_iterations", "message": "Reached maximum iterations"}
    
    def run_sync(self, task: str) -> str:
        """Run the agent and return the final response."""
        final = ""
        for update in self.run(task):
            if self.verbose:
                print(f"[{update['type']}]", update.get('content', update.get('result', '')))
            if update["type"] == "complete":
                final = update["final_response"]
            elif update["type"] == "max_iterations":
                final = update["message"]
        return final


if __name__ == "__main__":
    # Quick test
    agent = Agent()
    result = agent.run_sync("List the files in the current directory.")
    print("\n=== FINAL RESULT ===")
    print(result)
