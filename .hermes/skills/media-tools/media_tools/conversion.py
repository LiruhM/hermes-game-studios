"""
Media Converter - High-level media conversion and batch processing
"""

import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .image import ImageProcessor, ImageFormat
from .audio import AudioProcessor, AudioFormat
from .video import VideoProcessor, VideoFormat

class MediaConverter:
    """High-level media conversion and batch processing."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.temp_dir = Path(self.config.get("temp_dir", "/tmp/hermes-media"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.image_processor = ImageProcessor(config)
        self.audio_processor = AudioProcessor(config)
        self.video_processor = VideoProcessor(config)
    
    def detect_type(self, path: str) -> str:
        """Detect media type from file extension."""
        ext = Path(path).suffix.lower()
        image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif"}
        audio_exts = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}
        video_exts = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
        
        ext = Path(path).suffix.lower()
        if ext in image_exts:
            return "image"
        elif ext in audio_exts:
            return "audio"
        elif ext in video_exts:
            return "video"
        else:
            return "unknown"
    
    def convert(self, path: str, target_format: str, 
                output: str = None, **kwargs) -> str:
        """Convert any media file to target format."""
        media_type = self.detect_type(path)
        
        if media_type == "image":
            fmt = ImageFormat(target_format.lower())
            return self.image_processor.convert_format(path, fmt, output=output)
        elif media_type == "audio":
            fmt = AudioFormat(target_format.lower())
            return self.audio_processor.convert_format(path, fmt, output=output)
        elif media_type == "video":
            fmt = VideoFormat(target_format.lower())
            return self.video_processor.convert_format(path, fmt, output=output)
        else:
            raise ValueError(f"Unknown media type for {path}")
    
    def batch_convert(self, paths: List[str], target_format: str,
                      output_dir: str = None, **kwargs) -> List[str]:
        """Convert multiple files to target format."""
        output_dir = Path(output_dir or self.config.get("temp_dir", "/tmp/hermes-media") / "batch")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        for path in paths:
            try:
                output_name = Path(path).stem + "." + target_format.lower()
                output = str(Path(output_dir) / output_name)
                result = self.convert(path, target_format, output=output)
                results.append(result)
            except Exception as e:
                print(f"Failed to convert {path}: {e}")
                results.append("")
        
        return results
    
    def optimize_for_web(self, path: str, output: str = None) -> str:
        """Optimize media for web delivery."""
        media_type = self.detect_type(path)
        
        if media_type == "image":
            return self.image_processor.convert_format(
                path, ImageFormat.WEBP, quality=80, output=output
            )
        elif media_type == "video":
            return self.video_processor.convert_format(
                path, VideoFormat.MP4, quality="28", output=output
            )
        elif media_type == "audio":
            return self.audio_processor.convert_format(
                path, AudioFormat.MP3, bitrate="128k", output=output
            )
        else:
            raise ValueError(f"Unknown media type for {path}")
    
    def create_preview(self, path: str, output: str = None) -> str:
        """Create preview/thumbnail for any media."""
        media_type = self.detect_type(path)
        
        if media_type == "image":
            return self.image_processor.create_thumbnail(path, output=output)
        elif media_type == "video":
            return self.video_processor.create_thumbnail(path, output=output)
        elif media_type == "audio":
            # For audio, return waveform image or just info
            info = self.audio_processor.get_info(path)
            return f"Audio: {info.duration:.1f}s, {info.sample_rate}Hz, {info.channels}ch"
        else:
            raise ValueError(f"Unknown media type for {path}")

def create_media_converter(config: dict = None) -> MediaConverter:
    return MediaConverter(config)