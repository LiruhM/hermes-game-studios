"""
Media Tools - Main Package
"""

from .image import ImageProcessor, create_image_processor
from .audio import AudioProcessor, create_audio_processor
from .video import VideoProcessor, create_video_processor
from .conversion import MediaConverter, create_media_converter

__version__ = "1.0.0"
__all__ = [
    "ImageProcessor", "create_image_processor",
    "AudioProcessor", "create_audio_processor",
    "VideoProcessor", "create_video_processor",
    "MediaConverter", "create_media_converter",
]

def create_media_tools(config: dict = None) -> dict:
    """Factory to create all media tools."""
    return {
        "image": create_image_processor(config),
        "audio": create_audio_processor(config),
        "video": create_video_processor(config),
        "conversion": create_media_converter(config),
    }