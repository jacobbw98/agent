"""
Vision Tool - Screenshot and image handling.
"""
import base64
import io
from PIL import Image, ImageGrab
from typing import Optional, Tuple


class VisionTool:
    """Tool for capturing and processing screenshots."""
    
    def capture_screen(self, region: Tuple[int, int, int, int] = None) -> Image.Image:
        """Capture screen or region."""
        if region:
            return ImageGrab.grab(bbox=region)
        return ImageGrab.grab()
    
    def screenshot_to_base64(self, region: Tuple[int, int, int, int] = None) -> str:
        """Capture screenshot and return as base64 string."""
        img = self.capture_screen(region)
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode()
    
    def save_screenshot(self, path: str, region: Tuple[int, int, int, int] = None) -> str:
        """Capture and save screenshot to file."""
        try:
            img = self.capture_screen(region)
            img.save(path)
            return f"Screenshot saved to {path} ({img.size[0]}x{img.size[1]})"
        except Exception as e:
            return f"Error saving screenshot: {e}"
    
    def image_to_base64(self, image_path: str) -> str:
        """Convert an image file to base64."""
        try:
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode()
        except Exception as e:
            return f"Error encoding image: {e}"


# Singleton
_vision_tool: Optional[VisionTool] = None


def get_vision() -> VisionTool:
    """Get vision tool instance."""
    global _vision_tool
    if _vision_tool is None:
        _vision_tool = VisionTool()
    return _vision_tool
