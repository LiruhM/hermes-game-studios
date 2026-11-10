"""
Video Processor - Video processing, conversion, analysis
"""

import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class VideoFormat(str, Enum):
    MP4 = "mp4"
    WEBM = "webm"
    MOV = "mov"
    AVI = "avi"
    MKV = "mkv"

@dataclass
class VideoInfo:
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    bitrate: int
    format: str
    size_bytes: int

class VideoProcessor:
    """Process and manipulate video files using ffmpeg."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.temp_dir = Path(self.config.get("temp_dir", "/tmp/hermes-media"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def get_info(self, path: str) -> VideoInfo:
        """Get video metadata using ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        
        import json
        data = json.loads(result.stdout)
        format_info = data.get("format", {})
        video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        
        return VideoInfo(
            duration=float(format_info.get("duration", 0)),
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            fps=eval(video_stream.get("r_frame_rate", "0/1")),
            codec=video_stream.get("codec_name", "unknown"),
            bitrate=int(format_info.get("bit_rate", 0)),
            format=format_info.get("format_name", "unknown"),
            size_bytes=int(format_info.get("size", 0))
        )
    
    def convert_format(self, path: str, format: VideoFormat, 
                       quality: str = "23", output: str = None) -> str:
        """Convert video to different format using ffmpeg."""
        output = output or str(Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                               f"converted_{Path(path).stem}.{format.value}")
        
        cmd = [
            "ffmpeg", "-y", "-i", path,
            "-c:v", self._get_codec(format),
            "-crf", quality,
            "-preset", "medium",
            output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")
        
        return output
    
    def _get_codec(self, format: VideoFormat) -> str:
        codecs = {
            VideoFormat.MP4: "libx264",
            VideoFormat.WEBM: "libvpx-vp9",
            VideoFormat.MOV: "libx264",
            VideoFormat.AVI: "libx264",
            VideoFormat.MKV: "libx264",
        }
        return codecs.get(format, "libx264")
    
    def resize(self, path: str, width: int = None, height: int = None, 
               output: str = None) -> str:
        """Resize video to specified dimensions."""
        output = output or str(Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                               f"resized_{Path(path).name}")
        
        vf_filter = ""
        if width and height:
            vf_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease"
        elif width:
            vf_filter = f"scale={width}:-2"
        elif height:
            vf_filter = f"scale=-2:{height}"
        
        cmd = [
            "ffmpeg", "-y", "-i", path,
            "-vf", vf_filter,
            "-c:a", "copy",
            output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg resize failed: {result.stderr}")
        
        return output
    
    def trim(self, path: str, start: float, duration: float, 
             output: str = None) -> str:
        """Trim video to specified duration starting from start time."""
        output = output or str(Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                               f"trimmed_{Path(path).name}")
        
        cmd = [
            "ffmpeg", "-y", "-i", path,
            "-ss", str(start),
            "-t", str(duration),
            "-c", "copy",
            output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg trim failed: {result.stderr}")
        
        return output
    
    def extract_frames(self, path: str, output_dir: str = None, 
                       fps: float = 1, format: str = "jpg") -> List[str]:
        """Extract frames from video at specified fps."""
        output_dir = Path(output_dir or Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                          f"frames_{Path(path).stem}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_pattern = str(output_dir / f"frame_%04d.{format}")
        
        cmd = [
            "ffmpeg", "-y", "-i", path,
            "-vf", f"fps={fps}",
            output_pattern
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg frame extraction failed: {result.stderr}")
        
        return sorted([str(p) for p in Path(output_dir).glob(f"*.{format}")])
    
    def extract_audio(self, video_path: str, output: str = None, 
                      format: str = "mp3") -> str:
        """Extract audio from video."""
        output = output or str(Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                               f"audio_{Path(video_path).stem}.mp3")
        
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-c:a", "libmp3lame",
            "-b:a", "192k",
            output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr}")
        
        return output
    
    def create_thumbnail(self, video_path: str, timestamp: float = 0, 
                         output: str = None) -> str:
        """Create thumbnail from video at specified timestamp."""
        output = output or str(Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                               f"thumb_{Path(video_path).stem}.jpg")
        
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-ss", str(timestamp),
            "-vframes", "1",
            "-vf", "scale=320:-1",
            output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg thumbnail failed: {result.stderr}")
        
        return output
    
    def create_gif(self, video_path: str, start: float = 0, duration: float = 5, 
                   output: str = None, fps: int = 10, scale: int = 320) -> str:
        """Create GIF from video segment."""
        output = output or str(Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                               f"gif_{Path(video_path).stem}.gif")
        
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-ss", str(start),
            "-t", str(duration),
            "-vf", f"fps={fps},scale={scale}:-1:flags=lanczos,palettegen",
            "-y", "/tmp/palette.png"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg palette generation failed: {result.stderr}")
        
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-i", "/tmp/palette.png",
            "-ss", str(start),
            "-t", str(duration),
            "-lavfi", f"fps={fps},scale={scale}:-1:flags=lanczos [x]; [x][1:v] paletteuse",
            output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg gif creation failed: {result.stderr}")
        
        return output

def create_video_processor(config: dict = None) -> VideoProcessor:
    return VideoProcessor(config)