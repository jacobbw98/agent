"""
Game Control Tool - Keyboard/mouse input and window control for games.
"""
import time
from typing import Optional, Tuple
import pyautogui
import win32gui
import win32con


# Configure pyautogui for game control
pyautogui.PAUSE = 0.05  # Reduce pause between actions
pyautogui.FAILSAFE = True  # Move mouse to corner to abort


class GameControlTool:
    """Tool for controlling game windows and sending inputs."""
    
    def __init__(self):
        self._active_window: Optional[int] = None
        self._window_title: Optional[str] = None
    
    def list_windows(self) -> str:
        """List all visible windows."""
        windows = []
        
        def enum_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    results.append(f"  [{hwnd}] {title}")
            return True
        
        win32gui.EnumWindows(enum_callback, windows)
        return "Visible windows:\n" + "\n".join(windows[:30])
    
    def focus_window(self, window_title: str) -> str:
        """Focus a window by title (partial match)."""
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
    
    def get_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Get the rectangle of the active window."""
        if self._active_window:
            try:
                return win32gui.GetWindowRect(self._active_window)
            except:
                pass
        return None
    
    def send_key(self, key: str, hold_time: float = 0) -> str:
        """Send a keyboard key press."""
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
        try:
            pyautogui.typewrite(keys, interval=0.02)
            return f"Typed: {keys}"
        except Exception as e:
            return f"Error sending keys: {e}"
    
    def send_hotkey(self, *keys) -> str:
        """Send a hotkey combination (e.g., 'ctrl', 'c')."""
        try:
            pyautogui.hotkey(*keys)
            return f"Sent hotkey: {'+'.join(keys)}"
        except Exception as e:
            return f"Error sending hotkey: {e}"
    
    def move_mouse(self, x: int, y: int, relative: bool = False) -> str:
        """Move mouse to position."""
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
        try:
            pyautogui.moveTo(start_x, start_y)
            pyautogui.drag(end_x - start_x, end_y - start_y, button=button)
            return f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"
        except Exception as e:
            return f"Error dragging: {e}"
    
    def scroll(self, amount: int) -> str:
        """Scroll mouse wheel (positive = up, negative = down)."""
        try:
            pyautogui.scroll(amount)
            direction = "up" if amount > 0 else "down"
            return f"Scrolled {direction} by {abs(amount)}"
        except Exception as e:
            return f"Error scrolling: {e}"
    
    def screenshot(self, region: Tuple[int, int, int, int] = None) -> str:
        """Take a screenshot of the game window or screen."""
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
