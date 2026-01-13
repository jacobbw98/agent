"""
Game Control Tool - Keyboard/mouse input and window control for games.
Cross-platform support for Windows and Linux.
"""
import time
import sys
from typing import Optional, Tuple

# Platform-specific imports
IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')

# Try to import pyautogui (may fail on Wayland or missing X11 auth)
try:
    import pyautogui
    pyautogui.PAUSE = 0.05  # Reduce pause between actions
    pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    HAS_PYAUTOGUI = True
except Exception as e:
    print(f"Warning: pyautogui not available ({e}). Mouse/keyboard control disabled.")
    pyautogui = None
    HAS_PYAUTOGUI = False

if IS_WINDOWS:
    import win32gui
    import win32con
elif IS_LINUX:
    try:
        import subprocess
        HAS_WMCTRL = subprocess.run(['which', 'wmctrl'], capture_output=True).returncode == 0
        HAS_XDOTOOL = subprocess.run(['which', 'xdotool'], capture_output=True).returncode == 0
    except:
        HAS_WMCTRL = False
        HAS_XDOTOOL = False


class GameControlTool:
    """Tool for controlling game windows and sending inputs."""
    
    def __init__(self):
        self._active_window: Optional[int] = None
        self._window_title: Optional[str] = None
    
    def list_windows(self) -> str:
        """List all visible windows."""
        if IS_WINDOWS:
            return self._list_windows_win32()
        elif IS_LINUX:
            return self._list_windows_linux()
        return "Window listing not supported on this platform"
    
    def _list_windows_win32(self) -> str:
        """Windows implementation."""
        windows = []
        
        def enum_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    results.append(f"  [{hwnd}] {title}")
            return True
        
        win32gui.EnumWindows(enum_callback, windows)
        return "Visible windows:\n" + "\n".join(windows[:30])
    
    def _list_windows_linux(self) -> str:
        """Linux implementation using wmctrl."""
        if not HAS_WMCTRL:
            return "wmctrl not installed. Run: sudo apt install wmctrl"
        try:
            result = subprocess.run(['wmctrl', '-l'], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            formatted = []
            for line in lines[:30]:
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    formatted.append(f"  [{parts[0]}] {parts[3]}")
            return "Visible windows:\n" + "\n".join(formatted)
        except Exception as e:
            return f"Error listing windows: {e}"
    
    def focus_window(self, window_title: str) -> str:
        """Focus a window by title (partial match)."""
        if IS_WINDOWS:
            return self._focus_window_win32(window_title)
        elif IS_LINUX:
            return self._focus_window_linux(window_title)
        return "Window focus not supported on this platform"
    
    def _focus_window_win32(self, window_title: str) -> str:
        """Windows implementation."""
        target_hwnd = None
        search_lower = window_title.lower()
        
        def enum_callback(hwnd, _):
            nonlocal target_hwnd
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if search_lower in title.lower():
                    target_hwnd = hwnd
                    return False  # Stop enumeration
            return True
        
        win32gui.EnumWindows(enum_callback, None)
        
        if target_hwnd:
            try:
                win32gui.SetForegroundWindow(target_hwnd)
                self._active_window = target_hwnd
                self._window_title = win32gui.GetWindowText(target_hwnd)
                time.sleep(0.1)  # Wait for window to focus
                return f"Focused window: {self._window_title}"
            except Exception as e:
                return f"Error focusing window: {e}"
        
        return f"Window containing '{window_title}' not found. Use list_windows to see available windows."
    
    def _focus_window_linux(self, window_title: str) -> str:
        """Linux implementation using wmctrl or xdotool."""
        if HAS_WMCTRL:
            try:
                result = subprocess.run(['wmctrl', '-a', window_title], capture_output=True, text=True)
                if result.returncode == 0:
                    self._window_title = window_title
                    time.sleep(0.1)
                    return f"Focused window: {window_title}"
                return f"Window containing '{window_title}' not found"
            except Exception as e:
                return f"Error focusing window: {e}"
        elif HAS_XDOTOOL:
            try:
                result = subprocess.run(['xdotool', 'search', '--name', window_title], capture_output=True, text=True)
                windows = result.stdout.strip().split('\n')
                if windows and windows[0]:
                    subprocess.run(['xdotool', 'windowactivate', windows[0]])
                    self._window_title = window_title
                    time.sleep(0.1)
                    return f"Focused window: {window_title}"
                return f"Window containing '{window_title}' not found"
            except Exception as e:
                return f"Error focusing window: {e}"
        return "Install wmctrl or xdotool: sudo apt install wmctrl xdotool"
    
    def get_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Get the rectangle of the active window."""
        if IS_WINDOWS and self._active_window:
            try:
                return win32gui.GetWindowRect(self._active_window)
            except:
                pass
        elif IS_LINUX and HAS_XDOTOOL:
            try:
                result = subprocess.run(
                    ['xdotool', 'getactivewindow', 'getwindowgeometry', '--shell'],
                    capture_output=True, text=True
                )
                lines = result.stdout.strip().split('\n')
                geom = {}
                for line in lines:
                    if '=' in line:
                        k, v = line.split('=')
                        geom[k] = int(v)
                if 'X' in geom and 'Y' in geom and 'WIDTH' in geom and 'HEIGHT' in geom:
                    return (geom['X'], geom['Y'], geom['X'] + geom['WIDTH'], geom['Y'] + geom['HEIGHT'])
            except:
                pass
        return None
    
    def send_key(self, key: str, hold_time: float = 0) -> str:
        """Send a keyboard key press."""
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not available (X11/display issue)"
        try:
            if hold_time > 0:
                pyautogui.keyDown(key)
                time.sleep(hold_time)
                pyautogui.keyUp(key)
                return f"Held key '{key}' for {hold_time}s"
            else:
                pyautogui.press(key)
                return f"Pressed key: {key}"
        except Exception as e:
            return f"Error sending key: {e}"
    
    def send_keys(self, keys: str) -> str:
        """Send a sequence of keys."""
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not available (X11/display issue)"
        try:
            pyautogui.typewrite(keys, interval=0.02)
            return f"Typed: {keys}"
        except Exception as e:
            return f"Error sending keys: {e}"
    
    def send_hotkey(self, *keys) -> str:
        """Send a hotkey combination (e.g., 'ctrl', 'c')."""
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not available (X11/display issue)"
        try:
            pyautogui.hotkey(*keys)
            return f"Sent hotkey: {'+'.join(keys)}"
        except Exception as e:
            return f"Error sending hotkey: {e}"
    
    def move_mouse(self, x: int, y: int, relative: bool = False) -> str:
        """Move mouse to position."""
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not available (X11/display issue)"
        try:
            if relative:
                pyautogui.moveRel(x, y)
                return f"Moved mouse by ({x}, {y})"
            else:
                pyautogui.moveTo(x, y)
                return f"Moved mouse to ({x}, {y})"
        except Exception as e:
            return f"Error moving mouse: {e}"
    
    def click_mouse(self, x: int = None, y: int = None, button: str = 'left', clicks: int = 1) -> str:
        """Click mouse at position."""
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not available (X11/display issue)"
        try:
            if x is not None and y is not None:
                pyautogui.click(x, y, clicks=clicks, button=button)
                return f"Clicked {button} at ({x}, {y})"
            else:
                pyautogui.click(clicks=clicks, button=button)
                return f"Clicked {button} at current position"
        except Exception as e:
            return f"Error clicking: {e}"
    
    def drag_mouse(self, start_x: int, start_y: int, end_x: int, end_y: int, button: str = 'left') -> str:
        """Drag mouse from start to end position."""
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not available (X11/display issue)"
        try:
            pyautogui.moveTo(start_x, start_y)
            pyautogui.drag(end_x - start_x, end_y - start_y, button=button)
            return f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"
        except Exception as e:
            return f"Error dragging: {e}"
    
    def scroll(self, amount: int) -> str:
        """Scroll mouse wheel (positive = up, negative = down)."""
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not available (X11/display issue)"
        try:
            pyautogui.scroll(amount)
            direction = "up" if amount > 0 else "down"
            return f"Scrolled {direction} by {abs(amount)}"
        except Exception as e:
            return f"Error scrolling: {e}"
    
    def screenshot(self, region: Tuple[int, int, int, int] = None) -> str:
        """Take a screenshot of the game window or screen."""
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not available (X11/display issue)"
        try:
            if region:
                img = pyautogui.screenshot(region=region)
            elif self._active_window:
                rect = self.get_window_rect()
                if rect:
                    img = pyautogui.screenshot(region=rect)
                else:
                    img = pyautogui.screenshot()
            else:
                img = pyautogui.screenshot()
            
            # Save to temp file
            path = "game_screenshot.png"
            img.save(path)
            return f"Screenshot saved to {path} ({img.size[0]}x{img.size[1]})"
        except Exception as e:
            return f"Error taking screenshot: {e}"
    
    def get_pixel_color(self, x: int, y: int) -> str:
        """Get the color of a pixel at position."""
        if not HAS_PYAUTOGUI:
            return "Error: pyautogui not available (X11/display issue)"
        try:
            color = pyautogui.pixel(x, y)
            return f"Pixel at ({x}, {y}): RGB{color}"
        except Exception as e:
            return f"Error getting pixel color: {e}"


# Singleton instance
_game_tool: Optional[GameControlTool] = None


def get_gamecontrol() -> GameControlTool:
    """Get game control tool instance."""
    global _game_tool
    if _game_tool is None:
        _game_tool = GameControlTool()
    return _game_tool
