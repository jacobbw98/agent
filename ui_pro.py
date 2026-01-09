"""
Pro Agent UI - Split-screen with Thought Stream and Visual Feed.
"""
import gradio as gr
import base64
import os
import time
import threading
from agent import Agent
from ollama_client import list_models
from tools.vision import get_vision
from tools.gamecontrol import get_gamecontrol
from tools.neural_viz import get_visualizer


class ProAgentUI:
    """Pro UI with split-screen layout."""
    
    def __init__(self):
        self.agent = Agent()
        self.vision = get_vision()
        self.game = get_gamecontrol()
        self.neural_viz = get_visualizer()
        self.current_screenshot = None
        self.thought_log = []
        self.is_running = False
        self.planning_mode = False  # Default to fast mode for less looping
        
    def add_thought(self, thought_type: str, content: str):
        """Add a thought to the log."""
        timestamp = time.strftime("%H:%M:%S")
        icon = {
            "thinking": "🧠",
            "tool": "🔧",
            "result": "📋",
            "plan": "📝",
            "action": "⚡",
            "complete": "✅",
            "error": "❌"
        }.get(thought_type, "💭")
        
        thought_line = f"[{timestamp}] {icon} {content}"
        self.thought_log.append(thought_line)
        # Print to console for real-time visibility
        print(thought_line)
        # Keep only last 50 thoughts
        if len(self.thought_log) > 50:
            self.thought_log = self.thought_log[-50:]
    
    def get_thought_stream(self) -> str:
        """Get formatted thought stream."""
        return "\n".join(self.thought_log) if self.thought_log else "Waiting for input..."
    
    def capture_screenshot(self) -> str:
        """Capture and return screenshot as base64."""
        try:
            img_path = "current_view.png"
            self.vision.save_screenshot(img_path)
            with open(img_path, "rb") as f:
                return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
        except Exception as e:
            return None
    
    def run_agent(self, message: str, history: list, model: str, planning_mode: bool):
        """Run the agent with the given message. Generator for live streaming."""
        if not message.strip():
            yield history, "", self.get_thought_stream(), None
            return
        
        # Update model if changed
        if model != self.agent.client.model:
            self.agent.client.model = model
        
        self.planning_mode = planning_mode
        self.is_running = True
        self.thought_log = []  # Clear for new task
        
        # Generate initial neural viz
        self.neural_viz.update(message, "idle")
        viz_path = self.neural_viz.save("neural_activity.png")
        
        # Add initial thought
        mode_name = "PLANNING" if planning_mode else "FAST"
        self.add_thought("thinking", f"Mode: {mode_name} | Task: {message[:50]}...")
        self.neural_viz.update(message, "thinking")
        viz_path = self.neural_viz.save("neural_activity.png")
        yield history, message, self.get_thought_stream(), viz_path
        
        # If planning mode, just add a note (simpler, less looping)
        if planning_mode:
            task = f"Think step by step, then use ONE tool to complete: {message}"
            self.add_thought("plan", "Planning approach...")
        else:
            task = message
            self.add_thought("action", "Executing...")
        
        self.neural_viz.update(task, "thinking")
        viz_path = self.neural_viz.save("neural_activity.png")
        yield history, "", self.get_thought_stream(), viz_path
        
        # Collect response
        full_response = ""
        
        try:
            for update in self.agent.run(task):
                if update["type"] == "response":
                    content = update["content"]
                    full_response = content
                    preview = content[:150].replace("\n", " ")
                    self.add_thought("thinking", preview + "...")
                    self.neural_viz.update(content, "thinking")
                    viz_path = self.neural_viz.save("neural_activity.png")
                    yield history, "", self.get_thought_stream(), viz_path
                    
                elif update["type"] == "tool_call":
                    tool = update["tool"]
                    args = update["args"]
                    self.add_thought("tool", f"Calling: {tool}({args})")
                    self.neural_viz.update(f"{tool} {args}", "tool_call")
                    viz_path = self.neural_viz.save("neural_activity.png")
                    yield history, "", self.get_thought_stream(), viz_path
                        
                elif update["type"] == "tool_result":
                    result_preview = update["result"][:150].replace("\n", " ")
                    self.add_thought("result", result_preview + "...")
                    self.neural_viz.update(update["result"], "result")
                    viz_path = self.neural_viz.save("neural_activity.png")
                    yield history, "", self.get_thought_stream(), viz_path
                    
                elif update["type"] == "complete":
                    full_response = update["final_response"]
                    self.add_thought("complete", "Task completed!")
                    self.neural_viz.update("complete", "complete")
                    viz_path = self.neural_viz.save("neural_activity.png")
                    yield history, "", self.get_thought_stream(), viz_path
                    
                elif update["type"] == "max_iterations":
                    self.add_thought("error", "Max iterations reached")
                    yield history, "", self.get_thought_stream(), viz_path
                    
        except Exception as e:
            self.add_thought("error", f"Error: {str(e)}")
            full_response = f"Error: {str(e)}"
            yield history, "", self.get_thought_stream(), viz_path
        
        self.is_running = False
        
        # Update history
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": full_response})
        
        yield history, "", self.get_thought_stream(), viz_path
    
    def clear_all(self):
        """Clear chat and thoughts."""
        self.agent.client.reset_conversation()
        self.thought_log = []
        return [], "", "Cleared. Ready for new task.", None


def create_pro_ui():
    """Create the Pro Gradio interface."""
    
    ui = ProAgentUI()
    # Get available models
    try:
        models = list_models()
    except:
        models = ["nemotron-3-nano:latest"]
    # Simpler CSS - static gradient background, white text
    custom_css = """
    /* Dark gradient background */
    body, .gradio-container, .main, .contain, .app {
        background: linear-gradient(180deg, #0a0a1a 0%, #0d2040 50%, #0a1a30 100%) !important;
        min-height: 100vh;
    }
    
    .gradio-container {
        max-width: 100% !important;
    }
    
    /* Semi-transparent panels */
    .block, .form, .panel {
        background: rgba(10, 20, 40, 0.85) !important;
        border: 1px solid rgba(100, 200, 255, 0.2) !important;
        border-radius: 12px !important;
    }
    
    /* CHAT - Green monospace like thought stream */
    .chatbot, .chatbot * {
        font-family: 'Consolas', 'Monaco', monospace !important;
        color: #00ff88 !important;
    }
    
    .chatbot .message {
        background: rgba(10, 30, 50, 0.9) !important;
        border-radius: 8px !important;
        color: #00ff88 !important;
        border: 1px solid rgba(0, 255, 136, 0.2) !important;
    }
    
    .chatbot .user .message {
        background: rgba(20, 50, 70, 0.9) !important;
        border-left: 3px solid #00aaff !important;
    }
    
    .chatbot .bot .message {
        background: rgba(10, 40, 60, 0.9) !important;
        border-left: 3px solid #00ff88 !important;
    }
    
    /* Thought stream - green text */
    .thought-stream, .thought-stream textarea {
        font-family: 'Consolas', 'Monaco', monospace !important;
        font-size: 12px !important;
        background: rgba(10, 30, 50, 0.9) !important;
        color: #00ff88 !important;
        padding: 12px !important;
        border-radius: 10px !important;
        border: 1px solid rgba(0, 255, 136, 0.3) !important;
    }
    
    /* Text colors */
    h1, h2, h3, .markdown, p, span, label {
        color: #ffffff !important;
    }
    
    /* Dropdown/select - match background */
    select, .dropdown, [data-testid="dropdown"] {
        background: rgba(15, 35, 60, 0.9) !important;
        color: #ffffff !important;
        border: 1px solid rgba(100, 180, 255, 0.3) !important;
        border-radius: 8px !important;
    }
    
    /* Input fields */
    textarea, input, .textbox {
        background: rgba(15, 35, 60, 0.9) !important;
        border: 1px solid rgba(100, 180, 255, 0.3) !important;
        color: #ffffff !important;
    }
    
    /* Buttons */
    .primary, button.primary {
        background: linear-gradient(135deg, #1a5a8a, #2a7aaa) !important;
        color: #ffffff !important;
        border: none !important;
    }
    
    .primary:hover {
        background: linear-gradient(135deg, #2a7aaa, #3a9aca) !important;
    }
    
    /* Neural viz image styling */
    .neural-viz img {
        border: 2px solid rgba(100, 150, 255, 0.4) !important;
        border-radius: 12px !important;
    }
    """
    
    with gr.Blocks(title="Pro AI Agent") as demo:
        # Inject CSS via HTML
        gr.HTML(f"<style>{custom_css}</style>")
        
        gr.Markdown("""
        # 🚀 Pro AI Agent
        **Neural Interface** | Live Thought Stream | Waterfall Visualization
        """)
        
        with gr.Row():
            # LEFT COLUMN: Chat + Thoughts
            with gr.Column(scale=1):
                gr.Markdown("### 💬 Chat")
                chatbot = gr.Chatbot(
                    label="Conversation",
                    height=300
                )
                
                with gr.Row():
                    msg = gr.Textbox(
                        label="Message",
                        placeholder="Give me a task...",
                        scale=4,
                        lines=1
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)
                
                with gr.Row():
                    planning_mode = gr.Checkbox(
                        label="🧠 Planning Mode",
                        value=True,
                        info="Think before acting"
                    )
                    clear_btn = gr.Button("🗑️ Clear All")
                
                model_dropdown = gr.Dropdown(
                    choices=models,
                    value=models[0] if models else "nemotron-3-nano:latest",
                    label="Model",
                    interactive=True
                )
                
                gr.Markdown("### 🧠 Thought Stream")
                thought_display = gr.Textbox(
                    label="",
                    value="Waiting for input...",
                    lines=15,
                    max_lines=20,
                    interactive=False,
                    elem_classes=["thought-stream"]
                )
            
            # RIGHT COLUMN: Neural Activity Visualization
            with gr.Column(scale=1):
                gr.Markdown("### 🧬 Neural Activity")
                visual_feed = gr.Image(
                    label="Model thinking patterns",
                    type="filepath",
                    height=500,
                    elem_classes=["visual-feed"]
                )
                
                with gr.Row():
                    refresh_btn = gr.Button("📷 Capture Screen")
                
                gr.Markdown("""
                ### Available Tools
                - 🌐 Browser: Navigate, click, type
                - 📁 Files: Read, write, search
                - 📝 Grading: Parse rubrics
                - 🎮 Game: Keys, mouse, windows
                - 📷 Screenshot: Capture screen
                """)
        
        # Event handlers
        def on_send(message, history, model, planning):
            yield from ui.run_agent(message, history, model, planning)
        
        def on_clear():
            return ui.clear_all()
        
        def on_refresh():
            screenshot = ui.capture_screenshot()
            if screenshot:
                # Save to file for display
                import base64
                data = screenshot.split(",")[1]
                with open("current_view.png", "wb") as f:
                    f.write(base64.b64decode(data))
                return "current_view.png"
            return None
        
        send_btn.click(
            on_send,
            inputs=[msg, chatbot, model_dropdown, planning_mode],
            outputs=[chatbot, msg, thought_display, visual_feed]
        )
        msg.submit(
            on_send,
            inputs=[msg, chatbot, model_dropdown, planning_mode],
            outputs=[chatbot, msg, thought_display, visual_feed]
        )
        clear_btn.click(
            on_clear,
            outputs=[chatbot, msg, thought_display, visual_feed]
        )
        refresh_btn.click(
            on_refresh,
            outputs=[visual_feed]
        )
    
    return demo


if __name__ == "__main__":
    demo = create_pro_ui()
    demo.launch(share=False, server_name="127.0.0.1", server_port=7860)
