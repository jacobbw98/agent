# Local AI Agent

A Python-based agentic AI assistant running locally with Ollama + Nemotron-nano.

## Features

- 🌐 **Browser Automation** - Navigate, click, type, take screenshots
- 📁 **File System** - Read, write, search files
- 📝 **Grading** - Parse DOCX rubrics and grade submissions
- 🎮 **Game Control** - Keyboard/mouse input, window focus
- 📷 **Vision** - Screenshots and image handling

## Setup

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Make sure Ollama is running:**

   ```bash
   ollama serve
   ```

3. **Run the UI:**

   ```bash
   python ui.py
   ```

4. Open <http://127.0.0.1:7860> in your browser.

## Usage

Just type natural language commands like:

- "List the files in the current directory"
- "Open google.com and search for Python tutorials"
- "Grade the submission in student_work.docx using the Avogadro rubric"
- "Focus the Notepad window and type 'Hello World'"

## Files

- `ui.py` - Gradio web interface
- `agent.py` - Main agent loop with tool execution
- `ollama_client.py` - Ollama API wrapper
- `tools/` - Tool implementations
  - `browser.py` - Playwright browser automation
  - `filesystem.py` - File operations
  - `grading.py` - Rubric parsing and grading
  - `gamecontrol.py` - Keyboard/mouse/window control
  - `vision.py` - Screenshot utilities
