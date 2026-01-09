"""
Neural Activity Visualizer - Waterfall gradient effect.
Creates a smooth scrolling gradient that flows like a waterfall.
"""
import numpy as np
from PIL import Image
import time


class NeuralVisualizer:
    """Creates waterfall gradient visualization."""
    
    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self.frame_count = 0
        self.activity_level = 0.3  # Base activity
        self.hue = 0.6  # Start with blue
        self.history = np.zeros((height, width, 3), dtype=np.float32)
        
    def update(self, text: str = "", activity_type: str = "idle") -> np.ndarray:
        """
        Update visualization with waterfall effect.
        New colors appear at top and flow down.
        """
        self.frame_count += 1
        
        # Activity affects color and intensity
        activity_map = {
            "idle": (0.3, 0.55),      # Low intensity, blue-cyan
            "thinking": (0.7, 0.5),   # Medium, cyan
            "tool_call": (0.9, 0.75), # High, purple/magenta
            "result": (0.6, 0.35),    # Medium, green-yellow
            "complete": (0.8, 0.4),   # High, green
            "error": (0.9, 0.0)       # High, red
        }
        
        intensity, base_hue = activity_map.get(activity_type, (0.5, 0.5))
        
        # Smooth transition to new hue
        self.hue = self.hue * 0.9 + base_hue * 0.1
        self.activity_level = self.activity_level * 0.85 + intensity * 0.15
        
        # Shift everything down (waterfall effect)
        shift_amount = 3  # Pixels to shift per frame
        self.history[shift_amount:, :, :] = self.history[:-shift_amount, :, :]
        
        # Generate new row at top with gradient
        x = np.linspace(0, 1, self.width)
        
        # Create horizontal wave pattern
        wave_freq = 0.02 + 0.01 * np.sin(self.frame_count * 0.1)
        wave = 0.5 + 0.5 * np.sin(x * self.width * wave_freq + self.frame_count * 0.15)
        
        # Add some noise based on text hash
        if text:
            seed = sum(ord(c) for c in text) % 10000
            np.random.seed(seed + self.frame_count)
            noise = np.random.rand(self.width) * 0.3
        else:
            noise = np.random.rand(self.width) * 0.1
        
        # Combine for intensity
        row_intensity = (wave * 0.6 + noise * 0.4) * self.activity_level
        
        # Convert to HSV then RGB for the new rows
        for i in range(shift_amount):
            # Slight vertical variation
            row_hue = (self.hue + i * 0.002 + x * 0.05) % 1.0
            row_sat = 0.7 + 0.3 * row_intensity
            row_val = 0.15 + 0.35 * row_intensity
            
            # HSV to RGB
            rgb_row = self._hsv_to_rgb_row(row_hue, row_sat, row_val)
            self.history[i, :, :] = rgb_row
        
        # Apply vertical fade/blur for smooth waterfall
        result = self.history.copy()
        
        # Add subtle glow effect at high activity areas
        if self.activity_level > 0.6:
            glow = np.maximum(0, result - 0.3) * 0.3
            result = np.clip(result + glow, 0, 1)
        
        return (result * 255).astype(np.uint8)
    
    def _hsv_to_rgb_row(self, h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Convert HSV arrays to RGB for a single row."""
        c = v * s
        x = c * (1 - np.abs((h * 6) % 2 - 1))
        m = v - c
        
        rgb = np.zeros((self.width, 3))
        
        # Vectorized HSV to RGB
        h6 = h * 6
        mask0 = (h6 < 1)
        mask1 = (h6 >= 1) & (h6 < 2)
        mask2 = (h6 >= 2) & (h6 < 3)
        mask3 = (h6 >= 3) & (h6 < 4)
        mask4 = (h6 >= 4) & (h6 < 5)
        mask5 = (h6 >= 5)
        
        rgb[mask0, 0] = c[mask0]; rgb[mask0, 1] = x[mask0]; rgb[mask0, 2] = 0
        rgb[mask1, 0] = x[mask1]; rgb[mask1, 1] = c[mask1]; rgb[mask1, 2] = 0
        rgb[mask2, 0] = 0; rgb[mask2, 1] = c[mask2]; rgb[mask2, 2] = x[mask2]
        rgb[mask3, 0] = 0; rgb[mask3, 1] = x[mask3]; rgb[mask3, 2] = c[mask3]
        rgb[mask4, 0] = x[mask4]; rgb[mask4, 1] = 0; rgb[mask4, 2] = c[mask4]
        rgb[mask5, 0] = c[mask5]; rgb[mask5, 1] = 0; rgb[mask5, 2] = x[mask5]
        
        rgb = rgb + m[:, np.newaxis]
        return rgb
    
    def save(self, path: str = "neural_bg.png") -> str:
        """Save current frame."""
        frame = self.update()
        img = Image.fromarray(frame)
        img.save(path)
        return path
    
    def get_css_background(self) -> str:
        """Generate CSS for animated gradient background."""
        # This creates a pure CSS animated gradient as fallback
        return """
        @keyframes waterfall {
            0% { background-position: 0% 0%; }
            100% { background-position: 0% 100%; }
        }
        
        body, .gradio-container {
            background: linear-gradient(
                180deg,
                #0a0a1a 0%,
                #1a1a3e 15%,
                #0d2d4a 30%,
                #0a3d5c 45%,
                #1a4a5a 60%,
                #2a5a6a 75%,
                #1a3a4a 90%,
                #0a1a2a 100%
            );
            background-size: 100% 400%;
            animation: waterfall 15s ease-in-out infinite;
        }
        """


# Singleton
_visualizer = None

def get_visualizer() -> NeuralVisualizer:
    global _visualizer
    if _visualizer is None:
        _visualizer = NeuralVisualizer(512, 512)  # Smaller for performance
    return _visualizer
