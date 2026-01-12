"""
Pro Agent UI - Split-screen with Thought Stream and Live Visual Feed.
"""
import gradio as gr
import base64
import os
import time
from agent import Agent
from ollama_client import list_models, DEFAULT_MODEL
from tools.vision import get_vision
from tools.gamecontrol import get_gamecontrol


class ProAgentUI:
    """Pro UI with split-screen layout."""
    
    def __init__(self):
        self.agent = Agent()
        self.vision = get_vision()
        self.game = get_gamecontrol()
        self.current_screenshot = None
        self.thought_log = []
        self.is_running = False
        self.planning_mode = False
        self.waiting_for_human = False  # Flag for human takeover
        
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
            "error": "❌",
            "pause": "⏸️",
            "resume": "▶️"
        }.get(thought_type, "💭")
        
        thought_line = f"[{timestamp}] {icon} {content}"
        self.thought_log.append(thought_line)
        print(thought_line)  # Console output
        if len(self.thought_log) > 50:
            self.thought_log = self.thought_log[-50:]
    
    def get_thought_stream(self) -> str:
        """Get formatted thought stream."""
        return "\n".join(self.thought_log) if self.thought_log else "Waiting for input..."
    
    def capture_screenshot(self) -> str:
        """Capture and save screenshot, return file path."""
        try:
            # Use the correct method name from VisionTool
            screenshot_b64 = self.vision.screenshot_to_base64()
            if screenshot_b64:
                # Save to file
                filepath = os.path.join(os.path.dirname(__file__), "live_view.png")
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(screenshot_b64))
                return filepath
        except Exception as e:
            print(f"Screenshot error: {e}")
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
        self.thought_log = []
        
        # Take initial screenshot of current state
        screenshot_path = self.capture_screenshot()
        
        # Add initial thought
        mode_name = "PLANNING" if planning_mode else "FAST"
        self.add_thought("thinking", f"Mode: {mode_name} | Task: {message[:50]}...")
        yield history, message, self.get_thought_stream(), screenshot_path
        
        # Build task prompt
        if planning_mode:
            task = f"Think step by step, then use ONE tool to complete: {message}"
            self.add_thought("plan", "Planning approach...")
        else:
            task = message
            self.add_thought("action", "Executing...")
        
        yield history, "", self.get_thought_stream(), screenshot_path
        
        # Collect response
        full_response = ""
        
        try:
            for update in self.agent.run(task):
                if update["type"] == "thought":
                    content = update["content"]
                    self.add_thought("thinking", content)
                    yield history, "", self.get_thought_stream(), screenshot_path
                    
                elif update["type"] == "response":
                    content = update["content"]
                    # For intermediate messages, append to history if verbose,
                    # but for now let's just update the last assistant message
                    # or keep it in full_response for the final complete event
                    full_response = content
                    self.add_thought("response", content[:150] + "...")
                    yield history, "", self.get_thought_stream(), screenshot_path
                    
                elif update["type"] == "tool_call":
                    tool = update["tool"]
                    args = update["args"]
                    self.add_thought("tool", f"Calling: {tool}({args})")
                    yield history, "", self.get_thought_stream(), screenshot_path
                    
                    # Take screenshot after visual tools
                    if tool in ["browser_navigate", "browser_click", "browser_type", 
                                "game_screenshot", "screenshot", "game_focus_window"]:
                        time.sleep(0.5)
                        screenshot_path = self.capture_screenshot() or screenshot_path
                        yield history, "", self.get_thought_stream(), screenshot_path
                        
                elif update["type"] == "tool_result":
                    result = update["result"]
                    result_preview = result[:150].replace("\n", " ")
                    self.add_thought("result", result_preview + "...")
                    
                    # Check for human takeover request
                    if "HUMAN_TAKEOVER_REQUESTED" in result:
                        reason = result.split("HUMAN_TAKEOVER_REQUESTED:")[-1].strip()
                        self.waiting_for_human = True
                        self.add_thought("pause", f"⏸️ WAITING FOR HUMAN: {reason}")
                        yield history, "", self.get_thought_stream(), screenshot_path
                        
                        # Wait for human to click continue
                        while self.waiting_for_human:
                            time.sleep(0.5)
                            screenshot_path = self.capture_screenshot() or screenshot_path
                            yield history, "", self.get_thought_stream(), screenshot_path
                        
                        self.add_thought("resume", "▶️ Human completed action, continuing...")
                    
                    # Take screenshot after tool completes
                    screenshot_path = self.capture_screenshot() or screenshot_path
                    yield history, "", self.get_thought_stream(), screenshot_path
                    
                elif update["type"] == "complete":
                    full_response = update["final_response"]
                    self.add_thought("complete", "Task completed!")
                    screenshot_path = self.capture_screenshot() or screenshot_path
                    yield history, "", self.get_thought_stream(), screenshot_path
                    
                elif update["type"] == "max_iterations":
                    self.add_thought("error", "Max iterations reached")
                    yield history, "", self.get_thought_stream(), screenshot_path
                    
        except Exception as e:
            self.add_thought("error", f"Error: {str(e)}")
            full_response = f"Error: {str(e)}"
            yield history, "", self.get_thought_stream(), screenshot_path
        
        self.is_running = False
        
        # Update history
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": full_response})
        
        yield history, "", self.get_thought_stream(), screenshot_path
    
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
    
    # Use Gradio's built-in dark theme
    theme = gr.themes.Base(
        primary_hue="cyan",
        secondary_hue="blue",
        neutral_hue="slate",
    ).set(
        body_background_fill="transparent",
        body_background_fill_dark="transparent",
        block_background_fill="rgba(10, 25, 50, 0.4)",
        block_background_fill_dark="rgba(10, 25, 50, 0.4)",
        input_background_fill="rgba(15, 35, 60, 0.95)",
        input_background_fill_dark="rgba(15, 35, 60, 0.95)",
        button_primary_background_fill="linear-gradient(135deg, #1a5a8a, #2a7aaa)",
        button_primary_background_fill_dark="linear-gradient(135deg, #1a5a8a, #2a7aaa)",
    )
    
    css = """
    body, .gradio-container {
        background: transparent !important;
    }
    #fractal-canvas {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: -1;
        pointer-events: none;
    }
    .block, .form, .panel, .container, .wrap, .gradio-container {
        background: rgba(10, 25, 50, 0.3) !important;
        border: 1px solid rgba(0, 255, 0, 0.2) !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8) !important;
        border-radius: 12px !important;
    }
    label, .label-wrap, .chatbot, .chatbot * {
        background: transparent !important;
        border: none !important;
    }
    *, *::before, *::after {
        color: #00ff00 !important;
        border-color: rgba(0, 255, 0, 0.3) !important;
    }
    .message, [class*="message"] {
        background: rgba(0, 30, 0, 0.4) !important;
        border: 1px solid rgba(0, 255, 0, 0.5) !important;
        border-radius: 8px !important;
    }
    textarea, input, .textbox, select {
        background: rgba(0, 20, 0, 0.6) !important;
        border: 1px solid #00ff00 !important;
        color: #00ff00 !important;
        font-family: 'Consolas', 'Monaco', monospace !important;
    }
    .gradio-textbox textarea, input[type="text"] {
        color: #ff8c00 !important;
    }
    button, .button, .btn {
        background: rgba(0, 80, 0, 0.3) !important;
        border: 1px solid #00ff00 !important;
        color: #00ff00 !important;
        transition: all 0.2s ease !important;
    }
    button:hover {
        background: rgba(0, 120, 0, 0.5) !important;
        box-shadow: 0 0 15px rgba(0, 255, 0, 0.4) !important;
    }
    input[type="checkbox"] {
        accent-color: #00ff00 !important;
        width: 20px !important;
        height: 20px !important;
        cursor: pointer !important;
    }
    input[type="checkbox"]:checked {
        background-color: #00ff00 !important;
        border: 2px solid #00ff00 !important;
        box-shadow: 0 0 10px #00ff00 !important;
    }
    .checkbox-label, label[data-testid="checkbox-label"] {
        font-weight: bold !important;
    }
    /* Hide audio player waveform */
    .gr-audio, [data-testid="waveform-slot"], .waveform-container, audio {
        display: none !important;
    }
    """
    
    with gr.Blocks(title="Pro AI Agent") as demo:
        gr.Markdown("""
        # 🚀 Pro AI Agent
        **Neural Interface** | Live Thought Stream | Visual Feed
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
                        value=False,
                        info="Think before acting"
                    )
                    continue_btn = gr.Button("▶️ Continue", variant="secondary")
                    clear_btn = gr.Button("🗑️ Clear All")
                
                model_dropdown = gr.Dropdown(
                    choices=models,
                    value=DEFAULT_MODEL if DEFAULT_MODEL in models else (models[0] if models else "qwen2.5:14b"),
                    label="Model",
                    interactive=True
                )
                
                gr.Markdown("### 🧠 Thought Stream")
                thought_display = gr.Textbox(
                    label="",
                    value="Waiting for input...",
                    lines=12,
                    max_lines=15,
                    interactive=False
                )
            
            # RIGHT COLUMN: Live Visual Feed
            with gr.Column(scale=1):
                gr.Markdown("### 👁️ Live Visual Feed")
                visual_feed = gr.Image(
                    label="What the AI sees/controls",
                    type="filepath",
                    height=500
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
                
                gr.Markdown("### 🎵 Music")
                audio_player = gr.Audio(
                    label="Music Player",
                    type="filepath",
                    autoplay=True
                )
                next_btn = gr.Button("⏭️ Next Track")
                now_playing = gr.Textbox(
                    label="Now Playing",
                    value="Click 'Next Track' to start",
                    interactive=False,
                    lines=1
                )
        
        # Event handlers
        def on_send(message, history, model, planning):
            yield from ui.run_agent(message, history, model, planning)
        
        def on_clear():
            return ui.clear_all()
        
        def on_refresh():
            return ui.capture_screenshot()
        
        def on_continue():
            """Signal agent to continue after human takeover."""
            ui.waiting_for_human = False
            ui.add_thought("resume", "Human clicked Continue - resuming agent...")
            return ui.get_thought_stream()
        
        # Music player logic
        import os
        import random
        music_folder = os.path.join(os.path.dirname(__file__), "Music")
        music_files = [f for f in os.listdir(music_folder) if f.endswith('.mp3')]
        random.shuffle(music_files)
        music_state = {"index": 0, "files": music_files}
        
        def on_next_track():
            if not music_state["files"]:
                return None, "No music files found"
            music_state["index"] = (music_state["index"] + 1) % len(music_state["files"])
            track = music_state["files"][music_state["index"]]
            track_path = os.path.join(music_folder, track)
            track_name = track.replace('.mp3', '')
            return track_path, track_name
        
        def on_audio_end():
            return on_next_track()
        
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
        continue_btn.click(
            on_continue,
            outputs=[thought_display]
        )
        next_btn.click(
            on_next_track,
            outputs=[audio_player, now_playing]
        )
        audio_player.stop(
            on_next_track,
            outputs=[audio_player, now_playing]
        )
        # Autoplay first track on load
        demo.load(
            on_next_track,
            outputs=[audio_player, now_playing]
        )
    
    return demo, theme, css


if __name__ == "__main__":
    demo, theme, css = create_pro_ui()
    js = """
    (function() {
        console.log("FRACTAL INITIALIZING...");
        const vertexShaderSource = `#version 300 es
            in vec2 a_position;
            void main() { gl_Position = vec4(a_position, 0.0, 1.0); }
        `;

        const glslFragmentCode = `#version 300 es
            precision highp float;
            uniform vec2 u_resolution;
            uniform float u_time;
            uniform vec2 u_fixX_h;
            uniform vec2 u_fixY_h;
            uniform vec2 u_zoom;
            uniform vec2 u_invZoom;  // 1/zoom computed in JS (float64) for deep zoom precision
            uniform float u_maxIter;
            out vec4 fragColor;

            // Double-single arithmetic for deep zoom precision
            vec2 ds_add(vec2 d1, vec2 d2) {
                float s = d1.x + d2.x;
                float t = (s - d1.x) - d2.x;
                float e = (d1.x - (s - t)) + (d2.x - t);
                float low = (d1.y + d2.y) + e;
                float high = s + low;
                return vec2(high, low + (s - high));
            }
            vec2 ds_sub(vec2 d1, vec2 d2) { return ds_add(d1, vec2(-d2.x, -d2.y)); }
            vec2 ds_mul(vec2 d1, vec2 d2) {
                const float split = 4097.0;
                float c1 = d1.x * split;
                float h1 = c1 - (c1 - d1.x);
                float l1 = d1.x - h1;
                float c2 = d2.x * split;
                float h2 = c2 - (c2 - d2.x);
                float l2 = d2.x - h2;
                float p = d1.x * d2.x;
                float e = ((h1 * h2 - p) + h1 * l2 + l1 * h2) + l1 * l2;
                float s = p + (e + d1.x * d2.y + d1.y * d2.x);
                return vec2(s, (p - s) + (e + d1.x * d2.y + d1.y * d2.x));
            }

            // Procedural noise functions for texture overlay
            float hash(vec2 p) {
                return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
            }
            float noise(vec2 p) {
                vec2 i = floor(p);
                vec2 f = fract(p);
                f = f * f * (3.0 - 2.0 * f);
                return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
                           mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
            }
            float fbm(vec2 p) {
                float v = 0.0, a = 0.5;
                mat2 rot = mat2(cos(0.5), sin(0.5), -sin(0.5), cos(0.5));
                for (int i = 0; i < 5; i++) {
                    v += a * noise(p);
                    p = rot * p * 2.0;
                    a *= 0.5;
                }
                return v;
            }

            // UNDERTALE WATERFALL PALETTE
            vec3 palette(float t, float time) {
                // Layer 1: Deep navy/indigo base
                vec3 a1 = vec3(0.08, 0.08, 0.2);      // Dark navy base
                vec3 b1 = vec3(0.1, 0.4, 0.6);        // Blue-cyan range
                vec3 c1 = vec3(1.0, 1.0, 0.8);
                vec3 d1 = vec3(0.5, 0.6, 0.7);
                vec3 col1 = a1 + b1 * cos(6.28318 * (c1 * t + d1));
                
                // Layer 2: Cyan/teal water colors
                vec3 a2 = vec3(0.0, 0.2, 0.3);        // Teal base
                vec3 b2 = vec3(0.0, 0.5, 0.6);        // Cyan range
                vec3 c2 = vec3(0.8, 1.0, 1.0);
                vec3 d2 = vec3(0.3, 0.5, 0.6);
                vec3 col2 = a2 + b2 * cos(6.28318 * (c2 * t * 1.2 + d2));
                
                // Layer 3: Magenta sparkle accents
                vec3 a3 = vec3(0.15, 0.05, 0.2);      // Purple base
                vec3 b3 = vec3(0.4, 0.1, 0.5);        // Magenta range
                vec3 c3 = vec3(1.0, 0.8, 1.2);
                vec3 d3 = vec3(0.6, 0.3, 0.7);
                vec3 col3 = a3 + b3 * cos(6.28318 * (c3 * t * 0.8 + d3));
                
                // Blend: mostly cyan/navy with occasional magenta
                float blend1 = 0.5 + 0.5 * sin(time * 0.12);
                float blend2 = 0.3 + 0.2 * sin(time * 0.18 + 1.0);
                return mix(mix(col1, col2, blend1 * 0.5), col3, blend2 * 0.25);
            }

            // Orbit trap data structure
            struct OrbitData {
                float iter;
                float minDistCircle;   // Distance to circle trap
                float minDistLine;     // Distance to line trap
                float minDistPoint;    // Distance to point trap
                float avgAngle;        // Average orbital angle
                float finalMag;        // Final magnitude
                vec2 lastZ;            // Last z value
            };

            // Main fractal iteration with orbit trap data collection
            OrbitData get_iter_full(vec2 screen_coord) {
                OrbitData data;
                data.minDistCircle = 1e10;
                data.minDistLine = 1e10;
                data.minDistPoint = 1e10;
                data.avgAngle = 0.0;
                data.finalMag = 0.0;
                data.lastZ = vec2(0.0);
                
                vec2 rel_uv = (screen_coord * 2.0 - u_resolution.xy) / u_resolution.y;
                // Use u_invZoom (computed in JS with float64) instead of 1.0/u_zoom.x for deep zoom precision
                vec2 dx = ds_mul(vec2(rel_uv.x, 0.0), u_invZoom);
                vec2 dy = ds_mul(vec2(rel_uv.y, 0.0), u_invZoom);
                
                float max_iter = u_maxIter;
                
                // ====== STABLE ANIMATED POWER ======
                // Use narrow range centered on 2.0 with easing to stay stable
                float rawOsc = sin(u_time * 0.08) * 0.5 + sin(u_time * 0.13) * 0.3;
                // Easing: spend more time near 0, less at extremes
                float easedOsc = sign(rawOsc) * pow(abs(rawOsc), 1.5);
                // Final power: 2.0 to 2.25 range (very conservative)
                float animatedPower = 1.2 + easedOsc * 0.15;
                // Perturbation strength: how much the extra power affects the iteration
                float perturbStrength = (animatedPower - 2.0) * 0.3;
                
                // Orbit trap parameters - animate them!
                float trapCircleRadius = 0.5 + 0.3 * sin(u_time * 0.2);
                vec2 trapPoint = vec2(0.3 * cos(u_time * 0.15), 0.3 * sin(u_time * 0.18));
                float trapLineAngle = u_time * 0.1;
                vec2 trapLineDir = vec2(cos(trapLineAngle), sin(trapLineAngle));
                
                float angleSum = 0.0;
                
                for (float i = 0.0; i < 4000.0; i++) {
                    if (i >= max_iter) break;
                    
                    // Standard high-precision z² iteration (this stays as the BASE)
                    vec2 fixX_dx = ds_mul(u_fixX_h, dx);
                    vec2 fixY_dy = ds_mul(u_fixY_h, dy);
                    vec2 fixX_dy = ds_mul(u_fixX_h, dy);
                    vec2 fixY_dx = ds_mul(u_fixY_h, dx);
                    vec2 dx2 = ds_mul(dx, dx);
                    vec2 dy2 = ds_mul(dy, dy);
                    vec2 dxdy = ds_mul(dx, dy);
                    vec2 term1_x = ds_sub(fixX_dx, fixY_dy);
                    term1_x = ds_add(term1_x, term1_x);
                    dx = ds_add(term1_x, ds_sub(dx2, dy2));
                    vec2 term1_y = ds_add(fixX_dy, fixY_dx);
                    term1_y = ds_add(term1_y, term1_y);
                    dy = ds_add(term1_y, ds_add(dxdy, dxdy));
                    
                    // Get current z from base iteration
                    float cur_x = dx.x + u_fixX_h.x;
                    float cur_y = dy.x + u_fixY_h.x;
                    float mag = sqrt(cur_x * cur_x + cur_y * cur_y);
                    
                    // ====== PERTURBATION: Add small power correction ======
                    // Only apply when magnitude is reasonable (avoids singularities)
                    if (mag > 0.001 && mag < 100.0 && abs(perturbStrength) > 0.001) {
                        float theta = atan(cur_y, cur_x);
                        // Calculate the difference between z^p and z^2
                        // z^p - z^2 = r^2 * (r^(p-2) * e^(i*(p-2)*theta) - 1)
                        float extraPow = animatedPower - 2.0;
                        float r_extra = pow(mag, extraPow);
                        float theta_extra = extraPow * theta;
                        
                        // The perturbation is: r² * (r^(p-2) * (cos,sin)((p-2)*θ) - (1,0))
                        float perturb_x = mag * mag * (r_extra * cos(theta_extra) - 1.0);
                        float perturb_y = mag * mag * (r_extra * sin(theta_extra));
                        
                        // Apply perturbation with strength factor
                        dx.x += perturb_x * perturbStrength;
                        dy.x += perturb_y * perturbStrength;
                        
                        // Recalculate position after perturbation
                        cur_x = dx.x + u_fixX_h.x;
                        cur_y = dy.x + u_fixY_h.x;
                        mag = sqrt(cur_x * cur_x + cur_y * cur_y);
                    }
                    
                    vec2 z = vec2(cur_x, cur_y);
                    
                    // Collect orbit trap distances
                    // Circle trap - distance to circle of given radius
                    float distCircle = abs(mag - trapCircleRadius);
                    data.minDistCircle = min(data.minDistCircle, distCircle);
                    
                    // Point trap - distance to animated point
                    float distPoint = length(z - trapPoint);
                    data.minDistPoint = min(data.minDistPoint, distPoint);
                    
                    // Line trap - distance to rotating line through origin
                    float distLine = abs(dot(z, vec2(-trapLineDir.y, trapLineDir.x)));
                    data.minDistLine = min(data.minDistLine, distLine);
                    
                    // Accumulate angle for spiral effect
                    angleSum += atan(cur_y, cur_x);
                    
                    // Power-compensated escape radius
                    float escapeR = 1.0 + 2.0 * animatedPower;
                    if (mag > escapeR) {
                        float r2 = mag * mag;
                        // Normalized smooth iteration (accounts for variable power)
                        float nu = log2(log2(r2 + 1.0) / log2(escapeR));
                        data.iter = i + 1.0 - nu;
                        data.avgAngle = angleSum / (i + 1.0);
                        data.finalMag = mag;
                        data.lastZ = z;
                        return data;
                    }
                    data.lastZ = z;
                }
                data.iter = max_iter;
                data.avgAngle = angleSum / max_iter;
                data.finalMag = length(data.lastZ);
                return data;
            }

            // Dark void effect (inverted glow - creates dark arms)
            vec3 addGlow(vec3 col, float iter, float maxIter, OrbitData data) {
                // Edge darkness - stronger near escape boundary
                float edgeness = 1.0 - (iter / maxIter);
                float glow = exp(-iter * 0.015) * 2.5;
                
                // Orbit trap darkness contributions
                float circleGlow = exp(-data.minDistCircle * 8.0) * 0.6;
                float pointGlow = exp(-data.minDistPoint * 12.0) * 0.8;
                float lineGlow = exp(-data.minDistLine * 6.0) * 0.4;
                
                // Darken where there would be bright bands (inverted)
                float totalDarkness = glow * 0.3 + circleGlow * 0.5 + pointGlow * 0.4 + lineGlow * 0.6;
                
                // Multiply to darken - Waterfall palette void colors
                vec3 darkFactor = vec3(1.0) - vec3(0.05, 0.1, 0.15) * glow;        // Navy tinted darkness
                darkFactor -= vec3(0.1, 0.25, 0.3) * circleGlow;    // Dark cyan void
                darkFactor -= vec3(0.1, 0.2, 0.25) * pointGlow;     // Dark teal void
                darkFactor -= vec3(0.15, 0.1, 0.25) * lineGlow;     // Dark indigo void
                
                // Clamp to prevent negative colors
                darkFactor = max(darkFactor, vec3(0.03, 0.03, 0.08));
                
                return col * darkFactor;
            }

            // Second fractal layer (Burning Ship variation)
            float burningShipLayer(vec2 screen_coord) {
                vec2 rel_uv = (screen_coord * 2.0 - u_resolution.xy) / u_resolution.y;
                vec2 c = rel_uv / u_zoom.x * 0.5 + vec2(-0.5, -0.5);
                vec2 z = vec2(0.0);
                
                for (float i = 0.0; i < 100.0; i++) {
                    z = vec2(abs(z.x), abs(z.y)); // Burning ship fold
                    float x = z.x * z.x - z.y * z.y + c.x;
                    float y = 2.0 * z.x * z.y + c.y;
                    z = vec2(x, y);
                    if (dot(z, z) > 256.0) {
                        return i / 100.0;
                    }
                }
                return 1.0;
            }

            // Third layer - Mandelbrot with different parameters
            float mandelbrotLayer(vec2 screen_coord) {
                vec2 rel_uv = (screen_coord * 2.0 - u_resolution.xy) / u_resolution.y;
                vec2 c = rel_uv / u_zoom.x * 0.3 + vec2(
                    -0.7 + 0.1 * sin(u_time * 0.08),
                    0.0 + 0.1 * cos(u_time * 0.11)
                );
                vec2 z = vec2(0.0);
                
                for (float i = 0.0; i < 80.0; i++) {
                    float x = z.x * z.x - z.y * z.y + c.x;
                    float y = 2.0 * z.x * z.y + c.y;
                    z = vec2(x, y);
                    if (dot(z, z) > 256.0) {
                        return i / 80.0;
                    }
                }
                return 1.0;
            }

            void main() {
                // 2x2 supersampling for anti-aliasing
                vec3 totalCol = vec3(0.0);
                float aa = 2.0;
                
                for (float ax = 0.0; ax < aa; ax++) {
                    for (float ay = 0.0; ay < aa; ay++) {
                        vec2 offset = (vec2(ax, ay) - 0.5 * (aa - 1.0)) / aa;
                        vec2 sampleCoord = gl_FragCoord.xy + offset;
                        
                        // Get main fractal data with orbit traps
                        OrbitData data = get_iter_full(sampleCoord);
                        float iter = data.iter;
                        
                        float max_iter = 300.0 + 60.0 * log(u_zoom.x + 1.0);
                        if (max_iter > 800.0) max_iter = 800.0;
                        
                        vec3 col = vec3(0.0);
                        
                        if (iter < max_iter) {
                            // Base color from iteration count with enhanced palette
                            col = palette(iter * 0.018 + u_time * 0.006, u_time);
                            
                            // Orbit trap coloring contributions
                            float trapMix = 0.0;
                            
                            // Circle trap - bright cyan (waterfall glow)
                            float circleInfluence = exp(-data.minDistCircle * 5.0);
                            col = mix(col, vec3(0.0, 0.8, 1.0), circleInfluence * 0.4);
                            
                            // Point trap - teal/aqua
                            float pointInfluence = exp(-data.minDistPoint * 8.0);
                            col = mix(col, vec3(0.2, 0.7, 0.8), pointInfluence * 0.5);
                            
                            // Line trap - magenta sparkle
                            float lineInfluence = exp(-data.minDistLine * 4.0);
                            col = mix(col, vec3(0.8, 0.2, 1.0), lineInfluence * 0.3);
                            
                            // Angular coloring for spiral effect
                            float angleFactor = 0.5 + 0.5 * sin(data.avgAngle * 3.0 + u_time * 0.5);
                            col *= 0.8 + 0.2 * angleFactor;
                            
                            // Add glow effects
                            col = addGlow(col, iter, max_iter, data);
                            
                            // Multi-layer fractal blending
                            float burnLayer = burningShipLayer(sampleCoord);
                            float mandLayer = mandelbrotLayer(sampleCoord);
                            
                            // Subtle overlay of secondary fractals
                            vec3 burnColor = palette(burnLayer * 1.5 + 0.3, u_time) * 0.15;
                            vec3 mandColor = palette(mandLayer * 2.0 + 0.5, u_time) * 0.1;
                            
                            col += burnColor * (0.3 + 0.2 * sin(u_time * 0.4));
                            col += mandColor * (0.2 + 0.1 * cos(u_time * 0.35));
                            
                        } else {
                            // ====== UNDERTALE WATERFALL INTERIOR ======
                            vec2 uv = sampleCoord / u_resolution.xy;
                            
                            // Use the final orbit position for dynamic patterns
                            vec2 lastZ = data.lastZ;
                            float lastMag = length(lastZ);
                            float lastAngle = atan(lastZ.y, lastZ.x);
                            
                            // Animated ripple patterns based on orbit (slowed down)
                            float ripple1 = sin(lastMag * 15.0 + u_time * 0.8) * 0.5 + 0.5;
                            float ripple2 = sin(lastAngle * 8.0 - u_time * 0.6) * 0.5 + 0.5;
                            float ripple3 = sin((lastZ.x + lastZ.y) * 12.0 + u_time * 1.0) * 0.5 + 0.5;
                            
                            // Interference pattern
                            float interference = sin(lastZ.x * 25.0) * sin(lastZ.y * 25.0);
                            interference += sin((lastZ.x - lastZ.y) * 18.0 + u_time * 0.4);
                            interference *= 0.5;
                            
                            // Waterfall base - deep navy blue
                            vec3 nebulaBase = vec3(
                                0.02 + 0.02 * sin(lastAngle * 3.0 + u_time * 0.15),
                                0.04 + 0.03 * sin(lastMag * 5.0 + u_time * 0.2),
                                0.12 + 0.06 * sin(lastAngle * 2.0 - u_time * 0.1)
                            );
                            
                            // Waterfall ripple colors - cyan and blue tones
                            col = nebulaBase;
                            col += vec3(0.0, 0.08, 0.18) * ripple1;   // Deep blue ripple
                            col += vec3(0.0, 0.15, 0.2) * ripple2;    // Cyan ripple
                            col += vec3(0.02, 0.1, 0.15) * ripple3;   // Teal ripple
                            col += vec3(0.0, 0.06, 0.12) * interference;
                            
                            // Bioluminescent glow - Waterfall style
                            float circleGlow = exp(-data.minDistCircle * 2.0);
                            float pointGlow = exp(-data.minDistPoint * 3.0);
                            float lineGlow = exp(-data.minDistLine * 1.5);
                            
                            col += vec3(0.0, 0.4, 0.6) * circleGlow * 0.8;    // Cyan circle glow
                            col += vec3(0.0, 0.6, 0.5) * pointGlow * 0.7;     // Teal point glow
                            col += vec3(0.1, 0.3, 0.8) * lineGlow * 0.6;      // Blue line glow
                            
                            // Spiral arms - blue tones
                            float spiral = sin(data.avgAngle * 5.0 + lastMag * 10.0 + u_time * 0.7);
                            col += vec3(0.0, 0.12, 0.22) * (spiral * 0.5 + 0.5) * 0.4;
                            
                            // Slow, gentle breathing effect
                            float pulse = 0.85 + 0.15 * sin(u_time * 0.5 + lastMag * 3.0);
                            col *= pulse;
                            
                            // Nebula texture with waterfall feel
                            float nebulaNoiseVal = fbm(lastZ * 3.0 + u_time * 0.03);
                            col *= 0.75 + 0.4 * nebulaNoiseVal;
                            
                            // Edge glow - bright cyan near boundary
                            float edgeDist = 1.0 - smoothstep(0.0, 2.0, lastMag);
                            col += vec3(0.0, 0.2, 0.3) * edgeDist * 0.6;
                        }
                        
                        // Noise overlay for texture
                        vec2 noiseCoord = sampleCoord * 0.003 + vec2(u_time * 0.02, u_time * 0.015);
                        float n = fbm(noiseCoord);
                        col *= 0.92 + 0.08 * n;  // Subtle texture
                        
                        // Additional fine grain noise
                        float grain = hash(sampleCoord + u_time * 100.0);
                        col += (grain - 0.5) * 0.015;
                        
                        // Vignette effect
                        vec2 vignetteUV = sampleCoord / u_resolution.xy - 0.5;
                        float vignette = 1.0 - dot(vignetteUV, vignetteUV) * 0.5;
                        col *= vignette;
                        
                        totalCol += col;
                    }
                }
                
                totalCol /= (aa * aa);
                
                // Final tone mapping and color grading
                totalCol = pow(totalCol, vec3(0.95));  // Slight gamma
                totalCol = mix(totalCol, totalCol * vec3(1.1, 1.0, 1.15), 0.2);  // Color grade
                
                fragColor = vec4(clamp(totalCol, 0.0, 1.0), 1.0);
            }
        `;

        function start() {
            if (document.getElementById('fractal-canvas')) return;
            const canvas = document.createElement('canvas');
            canvas.id = 'fractal-canvas';
            Object.assign(canvas.style, { position: 'fixed', top: '0', left: '0', width: '100vw', height: '100vh', zIndex: '-1', pointerEvents: 'none' });
            document.body.appendChild(canvas);
            
            const gl = canvas.getContext('webgl2');
            if (!gl) return;

            function createShader(gl, type, source) {
                const s = gl.createShader(type);
                gl.shaderSource(s, source);
                gl.compileShader(s);
                if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
                    console.error("Shader Compile Error:", gl.getShaderInfoLog(s));
                    gl.deleteShader(s);
                    return null;
                }
                return s;
            }

            const program = gl.createProgram();
            console.log("DEBUG: Creating VS");
            const vs = createShader(gl, gl.VERTEX_SHADER, vertexShaderSource);
            console.log("DEBUG: Creating FS");
            const fs = createShader(gl, gl.FRAGMENT_SHADER, glslFragmentCode);
            if (!vs || !fs) { console.error("DEBUG: Shader creation failed"); return; }
            
            console.log("DEBUG: Attaching shaders");
            gl.attachShader(program, vs);
            gl.attachShader(program, fs);
            gl.linkProgram(program);
            
            if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
                 console.error("Program Link Error:", gl.getProgramInfoLog(program));
                 return;
            }
            console.log("DEBUG: Link success, using program");
            gl.useProgram(program);

            const locRes = gl.getUniformLocation(program, "u_resolution");
            const locTime = gl.getUniformLocation(program, "u_time");
            const locFXH = gl.getUniformLocation(program, "u_fixX_h");
            const locFYH = gl.getUniformLocation(program, "u_fixY_h");
            const locZoom = gl.getUniformLocation(program, "u_zoom");
            const locInvZoom = gl.getUniformLocation(program, "u_invZoom");
            const locMaxIter = gl.getUniformLocation(program, "u_maxIter");

            const buffer = gl.createBuffer();
            gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
            gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
            const pos = gl.getAttribLocation(program, "a_position");
            gl.enableVertexAttribArray(pos);
            gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0);

            // ===== CONFIGURABLE PARAMETERS =====
            // These can be tuned via fractal_config.json
            let cfg = {
                zoom: { rate: 0.075, minLog: 0, maxLog: 15, deadspaceThresholdSeconds: 0.5, reverseSlowdown: 0.95, minZoomOutDistance: 2.5 },
                iteration: { baseCount: 300, maxCount: 1000, logMultiplier: 60 },
                animation: { morphRate: 0.12, powerBase: 1.2, powerRange: 0.2, panRadius: 0.01, panSpeed: 0.15 },
                steering: { smoothing: 0.97, strength: 0.015, probeRadius: 0.25, gradientThreshold: 0.05, probeIterations: 250, searchRadiusMultiplier: 4.0 },
                traps: { circleRadiusBase: 0.5, circleRadiusRange: 0.3, circleSpeed: 0.2, pointDistance: 0.3, pointSpeedX: 0.15, pointSpeedY: 0.18, lineSpeed: 0.1 }
            };
            
            // Load config from file (async, non-blocking)
            fetch('/file=fractal_config.json').then(r => r.json()).then(c => { cfg = {...cfg, ...c}; console.log('Fractal config loaded:', cfg); }).catch(() => console.log('Using default fractal config'));

            const startTime = Date.now();
            let currentZoomLog = 0;  // Start zoomed out
            let actualZoomRate = cfg.zoom.rate;
            
            // Smooth steering state - heavily smoothed for seamless motion
            let steerX = 0, steerY = 0;  // Current steering offset (smoothed)
            let targetSteerX = 0, targetSteerY = 0;  // Target steering direction
            const steerSmoothing = 0.97;  // High value = very smooth transitions
            const steerStrength = 0.015;  // How strongly to steer toward complexity

            function splitDouble(d) {
                const hi = Math.fround(d);
                const lo = d - hi;
                return [hi, lo];
            }

            function render() {
                const now = Date.now();
                const time = (now - startTime) * 0.001;

                const dpr = window.devicePixelRatio || 1;
                if (canvas.width !== Math.floor(canvas.clientWidth * dpr)) {
                    canvas.width = Math.floor(canvas.clientWidth * dpr);
                    canvas.height = Math.floor(canvas.clientHeight * dpr);
                    gl.viewport(0, 0, canvas.width, canvas.height);
                }

                // Morphing Julia set - pure mathematical path, no CPU probing
                const morphRate = cfg.animation.morphRate;
                const phi = time * morphRate;
                const spiralRadius = 0.35 - 0.08 * Math.sin(phi * 0.7);
                const cx = spiralRadius * Math.cos(phi) - 0.1 * Math.cos(2.0 * phi + 0.3);
                const cy = spiralRadius * Math.sin(phi) - 0.1 * Math.sin(2.0 * phi + 0.3);
                const wx = 1.0 - 4.0 * cx;
                const wy = -4.0 * cy;
                const r_w = Math.sqrt(wx * wx + wy * wy);
                let sx = Math.sqrt((r_w + wx) * 0.5);
                let sy = Math.sqrt((r_w - wx) * 0.5);
                if (wy < 0.0) sy = -sy;
                let fixX = (1.0 + sx) * 0.5;
                let fixY = sy * 0.5;

                // Constant zoom rate - no CPU probing needed
                currentZoomLog += cfg.zoom.rate * 0.016;
                const zoom = Math.exp(currentZoomLog);

                // Dynamic max iterations for GPU - auto-scale to prevent pixelation
                // Formula: Base + Multiplier * ZoomLog
                let gpuMaxIter = cfg.iteration.baseCount + cfg.iteration.logMultiplier * currentZoomLog;
                // Cap at shader hard limit (4000)
                if (gpuMaxIter > 4000) gpuMaxIter = 4000;

                gl.uniform2f(locRes, canvas.width, canvas.height);
                gl.uniform1f(locTime, time);
                gl.uniform2fv(locFXH, splitDouble(fixX));
                gl.uniform2fv(locFYH, splitDouble(fixY));
                gl.uniform2fv(locZoom, splitDouble(zoom));
                gl.uniform2fv(locInvZoom, splitDouble(1.0 / zoom));  // Compute 1/zoom in JS (float64) for precision
                gl.uniform1f(locMaxIter, gpuMaxIter);

                gl.drawArrays(gl.TRIANGLES, 0, 6);
                requestAnimationFrame(render);
            }
            requestAnimationFrame(render);
            console.log("FRACTAL RUNNING");
        }

        const attempt = () => {
            if (document.body) { start(); }
            else { setTimeout(attempt, 500); }
        };
        attempt();
    })();
    """
    import os
    music_dir = os.path.join(os.path.dirname(__file__), "Music")
    config_path = os.path.join(os.path.dirname(__file__), "fractal_config.json")
    demo.launch(share=False, server_name="127.0.0.1", server_port=7860, theme=theme, css=css, js=js, allowed_paths=[music_dir, config_path])

