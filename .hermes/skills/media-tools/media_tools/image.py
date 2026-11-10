"""
Image Processor - Image manipulation, processing, analysis
"""

import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from PIL import Image, ImageFilter, ImageEnhance, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

class ImageFormat(str, Enum):
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"
    BMP = "bmp"
    TIFF = "tiff"
    GIF = "gif"

@dataclass
class ImageInfo:
    width: int
    height: int
    format: str
    mode: str
    size_bytes: int
    has_alpha: bool

class ImageProcessor:
    """Process and manipulate images."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.temp_dir = Path(self.config.get("temp_dir", "/tmp/hermes-media"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def load_image(self, path: str) -> Any:
        """Load an image from file."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not installed")
        return Image.open(path)
    
    def get_info(self, path: str) -> ImageInfo:
        """Get image metadata."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not installed")
        
        with Image.open(path) as img:
            return ImageInfo(
                width=img.width,
                height=img.height,
                format=img.format or "unknown",
                mode=img.mode,
                size_bytes=Path(path).stat().st_size,
                has_alpha=img.mode in ("RGBA", "LA", "P") and "A" in img.mode
            )
    
    def resize(self, path: str, width: int = None, height: int = None, 
               maintain_aspect: bool = True, output: str = None) -> str:
        """Resize an image."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not installed")
        
        output = output or str(self.temp_dir / f"resized_{Path(path).name}")
        
        with Image.open(path) as img:
            if maintain_aspect and width and height:
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
            elif width and height:
                img = img.resize((width, height), Image.Resampling.LANCZOS)
            elif width:
                ratio = width / img.width
                img = img.resize((width, int(img.height * ratio)), Image.Resampling.LANCZOS)
            elif height:
                ratio = height / img.height
                img = img.resize((int(img.width * ratio), height), Image.Resampling.LANCZOS)
            
            img.save(output)
        
        return output
    
    def convert_format(self, path: str, format: ImageFormat, 
                       quality: int = 90, output: str = None) -> str:
        """Convert image to different format."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not installed")
        
        output = output or str(self.temp_dir / f"converted_{Path(path).stem}.{format.value}")
        
        with Image.open(path) as img:
            if format == ImageFormat.JPEG and img.mode in ("RGBA", "LA", "P"):
                # JPEG doesn't support alpha, create white background
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = background
            
            save_kwargs = {"quality": quality, "optimize": True}
            if format == ImageFormat.PNG:
                save_kwargs = {"optimize": True}
            
            img.save(output, format=format.value.upper(), **save_kwargs)
        
        return output
    
    def crop(self, path: str, box: Tuple[int, int, int, int], output: str = None) -> str:
        """Crop image to box (left, top, right, bottom)."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not installed")
        
        output = output or str(self.temp_dir / f"cropped_{Path(path).name}")
        
        with Image.open(path) as img:
            cropped = img.crop(box)
            cropped.save(output)
        
        return output
    
    def apply_filter(self, path: str, filter_type: str, output: str = None) -> str:
        """Apply image filter."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not installed")
        
        output = output or str(self.temp_dir / f"filtered_{Path(path).name}")
        
        filters = {
            "blur": ImageFilter.BLUR,
            "contour": ImageFilter.CONTOUR,
            "detail": ImageFilter.DETAIL,
            "edge_enhance": ImageFilter.EDGE_ENHANCE,
            "emboss": ImageFilter.EMBOSS,
            "sharpen": ImageFilter.SHARPEN,
            "smooth": ImageFilter.SMOOTH,
        }
        
        if filter_type not in filters:
            raise ValueError(f"Unknown filter: {filter_type}")
        
        with Image.open(path) as img:
            filtered = img.filter(filters[filter_type])
            filtered.save(output)
        
        return output
    
    def adjust_brightness(self, path: str, factor: float, output: str = None) -> str:
        """Adjust image brightness (factor: 0.0-2.0, 1.0 = original)."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not installed")
        
        output = output or str(self.temp_dir / f"brightness_{Path(path).name}")
        
        with Image.open(path) as img:
            enhancer = ImageEnhance.Brightness(img)
            adjusted = enhancer.enhance(factor)
            adjusted.save(output)
        
        return output
    
    def adjust_contrast(self, path: str, factor: float, output: str = None) -> str:
        """Adjust image contrast (factor: 0.0-2.0, 1.0 = original)."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not installed")
        
        output = output or str(self.temp_dir / f"contrast_{Path(path).name}")
        
        with Image.open(path) as img:
            enhancer = ImageEnhance.Contrast(img)
            adjusted = enhancer.enhance(factor)
            adjusted.save(output)
        
        return output
    
    def create_thumbnail(self, path: str, size: Tuple[int, int] = (128, 128), 
                         output: str = None) -> str:
        """Create thumbnail."""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow not installed")
        
        output = output or str(self.temp_dir / f"thumb_{Path(path).name}")
        
        with Image.open(path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(output)
        
        return output
    
    def batch_process(self, paths: List[str], operations: List[Dict], 
                      output_dir: str = None) -> List[str]:
        """Batch process multiple images."""
        output_dir = Path(output_dir or self.temp_dir / "batch")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        for path in paths:
            for op in operations:
                op_type = op.get("type")
                params = op.get("params", {})
                
                if op_type == "resize":
                    result = self.resize(path, **params)
                elif op_type == "convert":
                    params["format"] = ImageFormat(params["format"])
                    result = self.convert_format(path, **params)
                elif op_type == "filter":
                    result = self.apply_filter(path, params["filter_type"])
                elif op_type == "brightness":
                    result = self.adjust_brightness(path, params["factor"])
                elif op_type == "contrast":
                    result = self.adjust_contrast(path, params["factor"])
                else:
                    continue
                
                results.append(result)
        
        return results

def create_image_processor(config: dict = None) -> ImageProcessor:
    return ImageProcessor(config)