"""
Audio Processor - Audio processing, conversion, analysis
"""

import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class AudioFormat(str, Enum):
    MP3 = "mp3"
    WAV = "wav"
    FLAC = "flac"
    OGG = "ogg"
    M4A = "m4a"
    AAC = "aac"

@dataclass
class AudioInfo:
    duration: float
    sample_rate: int
    channels: int
    bitrate: int
    format: str
    size_bytes: int

class AudioProcessor:
    """Process and manipulate audio files."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.temp_dir = Path(self.config.get("temp_dir", "/tmp/hermes-media"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def get_info(self, path: str) -> AudioInfo:
        """Get audio metadata using ffprobe."""
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
        stream = data.get("streams", [{}])[0]
        
        return AudioInfo(
            duration=float(format_info.get("duration", 0)),
            sample_rate=int(stream.get("sample_rate", 0)),
            channels=int(stream.get("channels", 0)),
            bitrate=int(format_info.get("bit_rate", 0)),
            format=format_info.get("format_name", "unknown"),
            size_bytes=int(format_info.get("size", 0))
        )
    
    def convert_format(self, path: str, format: AudioFormat, 
                       bitrate: str = "192k", output: str = None) -> str:
        """Convert audio to different format using ffmpeg."""
        output = output or str(Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                               f"converted_{Path(path).stem}.{format.value}")
        
        cmd = [
            "ffmpeg", "-y", "-i", path,
            "-c:a", self._get_codec(format),
            "-b:a", bitrate,
            output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")
        
        return output
    
    def _get_codec(self, format: AudioFormat) -> str:
        codecs = {
            AudioFormat.MP3: "libmp3lame",
            AudioFormat.WAV: "pcm_s16le",
            AudioFormat.FLAC: "flac",
            AudioFormat.OGG: "libvorbis",
            AudioFormat.M4A: "aac",
            AudioFormat.AAC: "aac",
        }
        return codecs.get(format, "libmp3lame")
    
    def trim(self, path: str, start: float, duration: float, 
             output: str = None) -> str:
        """Trim audio to specified duration starting from start time."""
        output = output or str(Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                               f"trimmed_{Path(path).name}")
        
        cmd = [
            "ffmpeg", "-y", "-i", path,
            "-ss", str(start),
            "-t", str(duration),
            "-c", "copy",
            output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg trim failed: {result.stderr}")
        
        return output
    
    def concatenate(self, paths: List[str], output: str = None) -> str:
        """Concatenate multiple audio files."""
        output = output or str(Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                               f"concatenated_{Path(paths[0]).stem}.mp3")
        
        # Create file list for concat
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for p in paths:
                f.write(f"file '{p}'\n")
            list_file = f.name
        
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed: {result.stderr}")
        
        return output
    
    def extract_audio(self, video_path: str, output: str = None, 
                      format: AudioFormat = AudioFormat.MP3) -> str:
        """Extract audio from video file."""
        output = output or str(Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                               f"audio_{Path(video_path).stem}.{AudioFormat.MP3.value}")
        
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-c:a", self._get_codec(AudioFormat.MP3),
            "-b:a", "192k",
            output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg extract failed: {result.stderr}")
        
        return output
    
    def adjust_volume(self, path: str, volume_factor: float, 
                      output: str = None) -> str:
        """Adjust audio volume (factor: 0.0-2.0, 1.0 = original)."""
        output = output or str(Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                               f"volume_{Path(path).name}")
        
        cmd = [
            "ffmpeg", "-y", "-i", path,
            "-filter:a", f"volume={volume_factor}",
            output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg volume failed: {result.stderr}")
        
        return output
    
    def change_speed(self, path: str, speed_factor: float, 
                     output: str = None) -> str:
        """Change audio speed without changing pitch (factor: 0.5-2.0)."""
        output = output or str(Path(self.config.get("temp_dir", "/tmp/hermes-media")) / 
                               f"speed_{Path(path).name}")
        
        cmd = [
            "ffmpeg", "-y", "-i", path,
            "-filter:a", f"atempo={speed_factor}",
            output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg speed failed: {result.stderr}")
        
        return output

def create_audio_processor(config: dict = None) -> AudioProcessor:
    return AudioProcessor(config)