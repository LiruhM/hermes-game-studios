"""
ASCII Generator - Text to ASCII art, image to ASCII
"""

import subprocess
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class ASCIIArt:
    text: str
    width: int
    font: str

class ASCIIGenerator:
    """Generate ASCII art from text or images."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.default_width = self.config.get("width", 80)
        self.default_font = self.config.get("font", "standard")
    
    def text_to_ascii(self, text: str, font: str = None, width: int = None) -> str:
        """Convert text to ASCII art using figlet."""
        font = font or self.default_font
        width = width or self.default_width
        
        try:
            result = subprocess.run(
                ["figlet", "-f", font, "-w", str(width), text],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout
        except FileNotFoundError:
            pass
        
        # Fallback: simple banner
        return self._simple_banner(text, width)
    
    def _simple_banner(self, text: str, width: int) -> str:
        """Simple banner fallback."""
        lines = []
        border = "=" * min(len(text) + 4, width)
        lines.append(border)
        lines.append(f"  {text}  ")
        lines.append(border)
        return "\n".join(lines)
    
    def image_to_ascii(self, image_path: str, width: int = 80) -> str:
        """Convert image to ASCII art."""
        # Try using img2txt (from caca-utils) or pillow
        try:
            result = subprocess.run(
                ["img2txt", "-W", str(width), image_path],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return result.stdout
        except FileNotFoundError:
            pass
        
        # Try with pillow
        try:
            from PIL import Image
            img = Image.open(image_path)
            img = img.convert("L")  # grayscale
            aspect = img.height / img.height
            new_height = int(width * aspect * 0.5)
            img = img.resize((width, new_height))
            
            ascii_chars = "@%#*+=-:. "
            ascii_str = ""
            for y in range(img.height):
                for x in range(img.width):
                    pixel = img.getpixel((x, y))
                    idx = min(pixel * len(ascii_chars) // 256, len(ascii_chars) - 1)
                    ascii_str += ascii_chars[idx]
                ascii_str += "\n"
            return ascii_str
        except ImportError:
            return "[PIL not installed - cannot convert image to ASCII]"
        except Exception as e:
            return f"[Error converting image: {e}]"

def create_ascii_generator(config: dict = None) -> ASCIIGenerator:
    return ASCIIGenerator(config)